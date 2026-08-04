# inclined_master.py

import streamlit as st
import numpy as np
import pandas as pd
import io
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

try:
    from config import SECTIONS_DB, STRUTS_DB
except ImportError:
    st.error("⚠️ برجاء التأكد من وجود ملف config.py")
    SECTIONS_DB = {}
    STRUTS_DB = {}

# =========================================================
# 1. Geometry & Mesh Generator
# =========================================================
def build_fea_mesh(L_segs, L_rem, X_segs, X_rem, angle_rad, applied_loads, inc_sec, base_sec, strut_types):
    inc_key_pts = [0.0]
    curr = 0.0
    for seg in L_segs:
        curr += seg
        inc_key_pts.append(curr)
    if L_rem > 0:
        inc_key_pts.append(curr + L_rem)
    
    L_tot = curr + L_rem
    
    # إضافة حدود الأحمال كنقاط رئيسية لتجنب تداخل الأحمال مع العناصر
    for ld in applied_loads:
        inc_key_pts.append(ld['start'])
        if ld['type'] != 'Point Load':
            inc_key_pts.append(ld['end'])
            
    inc_key_pts = sorted(list(set([round(p, 4) for p in inc_key_pts if 0 <= p <= L_tot + 1e-5])))
    
    # Subdivide elements for perfect SAP2000 style parabolic plots (Auto-Meshing)
    inc_nodes_L = []
    for i in range(len(inc_key_pts)-1):
        A = inc_key_pts[i]
        B = inc_key_pts[i+1]
        num_sub = max(1, int(np.ceil((B - A) / 0.15))) 
        pts = np.linspace(A, B, num_sub+1)
        for p in pts[:-1]:
            inc_nodes_L.append(p)
    inc_nodes_L.append(inc_key_pts[-1])
    
    nodes = []
    inc_node_indices = []
    
    # Base connection node
    nodes.append([0.0, 0.0, False, True, False])
    inc_node_indices.append(0)
    
    # Inclined Nodes
    for L_val in inc_nodes_L[1:]:
        nodes.append([L_val * np.cos(angle_rad), L_val * np.sin(angle_rad), False, False, False])
        inc_node_indices.append(len(nodes)-1)
        
    # Base Nodes
    base_node_indices = [0]
    X_cum = 0.0
    for X_seg in X_segs:
        X_cum += X_seg
        nodes.append([X_cum, 0.0, True, True, False])
        base_node_indices.append(len(nodes)-1)
    if X_rem > 0:
        X_cum += X_rem
        nodes.append([X_cum, 0.0, False, False, False])
        base_node_indices.append(len(nodes)-1)
        
    elements = []
    nodal_loads = []
    E_st = 210000000.0 
    inc_props = SECTIONS_DB.get(inc_sec, {'E': E_st, 'A': 0.00343, 'I': 0.00000122})
    
    # 1. Inclined Elements
    for i in range(len(inc_node_indices)-1):
        n1 = inc_node_indices[i]
        n2 = inc_node_indices[i+1]
        L_mid = (inc_nodes_L[i] + inc_nodes_L[i+1]) / 2.0
        
        p_x1, p_y1 = 0.0, 0.0
        p_x2, p_y2 = 0.0, 0.0
        
        for ld in applied_loads:
            if ld['type'] == 'Point Load': continue
            if ld['start'] - 1e-4 <= L_mid <= ld['end'] + 1e-4:
                L_len = max(ld['end'] - ld['start'], 1e-5)
                w_a = ld['w1'] + (ld['w2'] - ld['w1']) * (inc_nodes_L[i] - ld['start']) / L_len
                w_b = ld['w1'] + (ld['w2'] - ld['w1']) * (inc_nodes_L[i+1] - ld['start']) / L_len
                
                if ld['dir'] == 'Gravity (Vertical ↓)':
                    c, s = np.cos(angle_rad), np.sin(angle_rad)
                    p_x1 += -w_a * s; p_y1 += -w_a * c
                    p_x2 += -w_b * s; p_y2 += -w_b * c
                else:
                    p_y1 += -w_a; p_y2 += -w_b
                    
        elements.append({
            'type': 'frame', 'group': 'inclined', 'sec': inc_sec,
            'n1': n1, 'n2': n2, 'px1': p_x1, 'py1': p_y1, 'px2': p_x2, 'py2': p_y2,
            'E': inc_props.get('E', E_st), 'A': inc_props.get('A', 0.00343), 'I': inc_props.get('I', 0.00000122)
        })
        
    # Apply Point Loads
    for ld in applied_loads:
        if ld['type'] == 'Point Load':
            try:
                idx = inc_nodes_L.index(round(ld['start'], 4))
                n_idx = inc_node_indices[idx]
                c, s = np.cos(angle_rad), np.sin(angle_rad)
                if ld['dir'] == 'Gravity (Vertical ↓)':
                    nodal_loads.append({'node': n_idx, 'Fx': 0.0, 'Fy': -ld['w1']})
                else:
                    nodal_loads.append({'node': n_idx, 'Fx': ld['w1']*s, 'Fy': -ld['w1']*c})
            except ValueError:
                pass
                
    # 2. Base Elements
    base_props = SECTIONS_DB.get(base_sec, {'E': E_st, 'A': 0.00343, 'I': 0.00000122})
    for i in range(len(base_node_indices)-1):
        elements.append({
            'type': 'frame', 'group': 'base', 'sec': base_sec,
            'n1': base_node_indices[i], 'n2': base_node_indices[i+1],
            'px1': 0.0, 'py1': 0.0, 'px2': 0.0, 'py2': 0.0,
            'E': base_props.get('E', E_st), 'A': base_props.get('A', 0.00343), 'I': base_props.get('I', 0.00000122)
        })
        
    # 3. Struts
    target_Ls = [sum(L_segs[:j+1]) for j in range(len(L_segs))]
    for j in range(len(L_segs)):
        target_L = round(target_Ls[j], 4)
        if target_L in inc_nodes_L:
            idx = inc_nodes_L.index(target_L)
            n_inc = inc_node_indices[idx]
            n_base = base_node_indices[j+1]
            st_props = STRUTS_DB.get(strut_types[j], {'A': 0.001}) 
            elements.append({
                'type': 'truss', 'group': 'strut', 'sec': strut_types[j],
                'n1': n_base, 'n2': n_inc,
                'E': E_st, 'A': st_props.get('A', 0.001)
            })
            
    return nodes, elements, nodal_loads, L_tot, sum(X_segs)+X_rem

# =========================================================
# 2. Advanced 2D Frame FEA Solver
# =========================================================
def solve_fea_engine(nodes, elements, nodal_loads):
    num_nodes = len(nodes)
    NDOF = num_nodes * 3
    K = np.zeros((NDOF, NDOF))
    F = np.zeros(NDOF)
    
    for el in elements:
        n1, n2 = el['n1'], el['n2']
        x1, y1 = nodes[n1][0], nodes[n1][1]
        x2, y2 = nodes[n2][0], nodes[n2][1]
        L = np.hypot(x2 - x1, y2 - y1)
        if L < 1e-5: continue
        c, s = (x2 - x1) / L, (y2 - y1) / L
        el['L'], el['c'], el['s'] = L, c, s
        
        E_raw = el['E']; E = E_raw if E_raw > 1000000 else E_raw * 10000.0 
        A_raw = el['A']; A = A_raw if A_raw < 0.1 else A_raw / 10000.0 
        
        T = np.array([
            [c, s, 0, 0, 0, 0], [-s, c, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0], [0, 0, 0, -s, c, 0], [0, 0, 0, 0, 0, 1]
        ])
        
        if el['type'] == 'truss':
            k_loc = np.zeros((6, 6))
            k_loc[0, 0] = k_loc[3, 3] = E * A / L
            k_loc[0, 3] = k_loc[3, 0] = -E * A / L
        else:
            I_raw = el['I']; I = I_raw if I_raw < 0.001 else I_raw / 100000000.0 
            k_loc = np.array([
                [E*A/L, 0, 0, -E*A/L, 0, 0],
                [0, 12*E*I/L**3, 6*E*I/L**2, 0, -12*E*I/L**3, 6*E*I/L**2],
                [0, 6*E*I/L**2, 4*E*I/L, 0, -6*E*I/L**2, 2*E*I/L],
                [-E*A/L, 0, 0, E*A/L, 0, 0],
                [0, -12*E*I/L**3, -6*E*I/L**2, 0, 12*E*I/L**3, -6*E*I/L**2],
                [0, 6*E*I/L**2, 2*E*I/L, 0, -6*E*I/L**2, 4*E*I/L]
            ])
            
            px1, py1, px2, py2 = el['px1'], el['py1'], el['px2'], el['py2']
            f_eq_loc = np.array([
                (2*px1 + px2)*L/6.0,
                (7*py1 + 3*py2)*L/20.0,
                (3*py1 + 2*py2)*L**2/60.0,
                (px1 + 2*px2)*L/6.0,
                (3*py1 + 7*py2)*L/20.0,
                -(2*py1 + 3*py2)*L**2/60.0
            ])
            f_eq_glob = T.T @ f_eq_loc
            dof_idx = [3*n1, 3*n1+1, 3*n1+2, 3*n2, 3*n2+1, 3*n2+2]
            for r in range(6): F[dof_idx[r]] += f_eq_glob[r]
            
        k_glob = T.T @ k_loc @ T
        dof_idx = [3*n1, 3*n1+1, 3*n1+2, 3*n2, 3*n2+1, 3*n2+2]
        for r in range(6):
            for col in range(6):
                K[dof_idx[r], dof_idx[col]] += k_glob[r, col]
                
    for nl in nodal_loads:
        F[3*nl['node'] + 0] += nl['Fx']
        F[3*nl['node'] + 1] += nl['Fy']
            
    free_dof = []
    for i, n in enumerate(nodes):
        if not n[2]: free_dof.append(3*i)   
        if not n[3]: free_dof.append(3*i+1) 
        if not n[4]: free_dof.append(3*i+2) 
        
    K_ff = K[np.ix_(free_dof, free_dof)]
    F_f = F[free_dof]
    
    U = np.zeros(NDOF)
    try:
        U_f = np.linalg.solve(K_ff, F_f)
    except np.linalg.LinAlgError:
        U_f = np.linalg.lstsq(K_ff, F_f, rcond=None)[0]
    
    U[free_dof] = U_f
    R_reactions = K @ U - F
    
    # Internal forces
    for el in elements:
        n1, n2 = el['n1'], el['n2']
        c, s, L = el['c'], el['s'], el['L']
        E_raw = el['E']; E = E_raw if E_raw > 1000000 else E_raw * 10000.0 
        A_raw = el['A']; A = A_raw if A_raw < 0.1 else A_raw / 10000.0 
        
        dof_idx = [3*n1, 3*n1+1, 3*n1+2, 3*n2, 3*n2+1, 3*n2+2]
        u_glob = U[dof_idx]
        T = np.array([
            [c, s, 0, 0, 0, 0], [-s, c, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0], [0, 0, 0, -s, c, 0], [0, 0, 0, 0, 0, 1]
        ])
        u_loc = T @ u_glob
        
        if el['type'] == 'truss':
            N_val = (E * A / L) * (u_loc[3] - u_loc[0])
            el['internal'] = {'N': [N_val, N_val], 'V': [0,0], 'M': [0,0]}
        else:
            I_raw = el['I']; I = I_raw if I_raw < 0.001 else I_raw / 100000000.0 
            k_loc = np.array([
                [E*A/L, 0, 0, -E*A/L, 0, 0],
                [0, 12*E*I/L**3, 6*E*I/L**2, 0, -12*E*I/L**3, 6*E*I/L**2],
                [0, 6*E*I/L**2, 4*E*I/L, 0, -6*E*I/L**2, 2*E*I/L],
                [-E*A/L, 0, 0, E*A/L, 0, 0],
                [0, -12*E*I/L**3, -6*E*I/L**2, 0, 12*E*I/L**3, -6*E*I/L**2],
                [0, 6*E*I/L**2, 2*E*I/L, 0, -6*E*I/L**2, 4*E*I/L]
            ])
            px1, py1, px2, py2 = el['px1'], el['py1'], el['px2'], el['py2']
            f_eq_loc = np.array([
                (2*px1 + px2)*L/6.0,
                (7*py1 + 3*py2)*L/20.0,
                (3*py1 + 2*py2)*L**2/60.0,
                (px1 + 2*px2)*L/6.0,
                (3*py1 + 7*py2)*L/20.0,
                -(2*py1 + 3*py2)*L**2/60.0
            ])
            f_end = k_loc @ u_loc - f_eq_loc
            el['internal'] = {
                'N': [-f_end[0], f_end[3]],
                'V': [f_end[1], -f_end[4]],
                'M': [-f_end[2], f_end[5]]
            }
            
    return U, R_reactions

# =========================================================
# 3. Engines for Plotting (Live Preview & SAP2000 Style)
# =========================================================
def plot_live_geometry(nodes, elements, applied_loads, L_segs, X_segs, angle_deg, inc_sec, base_sec):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True, linestyle=':', alpha=0.3)
    ax.axis('off')

    for i, n in enumerate(nodes):
        x, y = n[0], n[1]
        if n[2] and n[3]: ax.plot(x, y, marker='^', color='orange', markersize=10, zorder=5)
        elif not n[2] and n[3]: ax.plot(x, y, marker='o', color='green', markersize=8, zorder=5)

    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        color = 'blue' if el['type'] == 'frame' else 'red'
        style = '-' if el['type'] == 'frame' else '--'
        lw = 3 if el['type'] == 'frame' else 1.5
        ax.plot([n1[0], n2[0]], [n1[1], n2[1]], color=color, linestyle=style, linewidth=lw)

    # 💡 توقيع الأبعاد L و X بأسلوب هندسي
    angle_rad = np.radians(angle_deg)
    c_ang, s_ang = np.cos(angle_rad), np.sin(angle_rad)
    
    curr_l = 0.0
    for i, seg in enumerate(L_segs):
        px = (curr_l + seg/2) * c_ang
        py = (curr_l + seg/2) * s_ang
        ax.text(px - s_ang*0.6, py + c_ang*0.6, f"L{i+1}={seg:.2f}m", color='gray', fontsize=8, rotation=angle_deg, ha='center', va='center')
        curr_l += seg
        
    curr_x = 0.0
    for i, seg in enumerate(X_segs):
        px = curr_x + seg/2
        py = 0.0
        ax.text(px, py - 0.6, f"X{i+1}={seg:.2f}m", color='gray', fontsize=8, ha='center', va='center')
        curr_x += seg

    # 💡 توقيع أسهم الأحمال المتغيرة
    for ld in applied_loads:
        w1, w2 = ld['w1'], ld['w2']
        start_L, end_L = ld['start'], ld['end']
        dir_type = ld['dir']
        
        if ld['type'] == 'Point Load':
            px = start_L * c_ang
            py = start_L * s_ang
            arrow_len = 1.0
            if dir_type == 'Gravity (Vertical ↓)':
                ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.15, head_length=0.2, fc='fuchsia', ec='fuchsia', zorder=4)
                ax.text(px, py + arrow_len + 0.4, f"{w1} kN", color='fuchsia', fontsize=8, fontweight='bold', ha='center')
            else:
                ax.arrow(px - s_ang*(arrow_len+0.1), py + c_ang*(arrow_len+0.1), s_ang*arrow_len, -c_ang*arrow_len, head_width=0.15, head_length=0.2, fc='fuchsia', ec='fuchsia', zorder=4)
                ax.text(px - s_ang*(arrow_len+0.4), py + c_ang*(arrow_len+0.4), f"{w1} kN", color='fuchsia', fontsize=8, fontweight='bold', ha='center', rotation=angle_deg)
        else:
            num_arrows = max(3, int((end_L - start_L) / 0.5))
            xs = np.linspace(start_L, end_L, num_arrows)
            for x_dist in xs:
                w_curr = w1 + (w2 - w1) * (x_dist - start_L) / max(end_L - start_L, 1e-5)
                if abs(w_curr) < 0.1: continue
                px = x_dist * c_ang
                py = x_dist * s_ang
                arrow_len = 0.8 * (abs(w_curr) / max(abs(w1), abs(w2), 1))
                if dir_type == 'Gravity (Vertical ↓)':
                    ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.1, head_length=0.15, fc='magenta', ec='magenta', zorder=4)
                else:
                    ax.arrow(px - s_ang*(arrow_len+0.1), py + c_ang*(arrow_len+0.1), s_ang*arrow_len, -c_ang*arrow_len, head_width=0.1, head_length=0.15, fc='magenta', ec='magenta', zorder=4)
                    
            mid_L = (start_L + end_L) / 2.0
            mid_x = mid_L * c_ang
            mid_y = mid_L * s_ang
            txt = f"{w1}" if ld['type'] == 'Uniform' else f"{w1} to {w2}"
            if dir_type == 'Gravity (Vertical ↓)':
                ax.text(mid_x, mid_y + 1.2, f"{txt} kN/m\n({dir_type.split()[0]})", color='magenta', fontsize=8, fontweight='bold', ha='center')
            else:
                ax.text(mid_x - s_ang*1.2, mid_y + c_ang*1.2, f"{txt} kN/m", color='magenta', fontsize=8, fontweight='bold', ha='center', rotation=angle_deg)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight', transparent=True)
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

def plot_sap2000_diagrams(nodes, elements, scales, inc_sec, base_sec):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    ax_geom, ax_n, ax_v, ax_m = axes.flatten()
    
    for ax in axes.flatten():
        ax.set_aspect('equal', adjustable='datalim')
        ax.grid(True, linestyle=':', alpha=0.3)
        ax.axis('off')
        
    def draw_base(ax, title):
        ax.set_title(title, fontsize=14, fontweight='bold')
        for i, n in enumerate(nodes):
            x, y = n[0], n[1]
            if n[2] and n[3]: ax.plot(x, y, marker='^', color='orange', markersize=12, zorder=5)
            elif not n[2] and n[3]: ax.plot(x, y, marker='o', color='green', markersize=10, zorder=5)
        for el in elements:
            n1, n2 = nodes[el['n1']], nodes[el['n2']]
            color = 'black' if el['type'] == 'frame' else 'gray'
            style = '-' if el['type'] == 'frame' else '--'
            ax.plot([n1[0], n2[0]], [n1[1], n2[1]], color=color, linestyle=style, linewidth=1, zorder=1)

    draw_base(ax_geom, "System Geometry & Profiles")
    draw_base(ax_n, "Axial Force Diagram (kN)")
    draw_base(ax_v, "Shear Force Diagram (kN)")
    draw_base(ax_m, "Bending Moment Diagram (kN.m)")
    
    # Names on Geometry
    inc_drawn, base_drawn = False, False
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        if el['group'] == 'inclined' and not inc_drawn:
            ax_geom.text((n1[0]+n2[0])/2 - 0.5, (n1[1]+n2[1])/2 + 0.5, inc_sec, color='blue', fontsize=10, fontweight='bold', rotation=np.degrees(np.arctan2(el['s'], el['c'])))
            inc_drawn = True
        elif el['group'] == 'base' and not base_drawn:
            ax_geom.text((n1[0]+n2[0])/2, -0.4, base_sec, color='blue', fontsize=10, fontweight='bold', ha='center')
            base_drawn = True
        elif el['group'] == 'strut':
            ax_geom.text((n1[0]+n2[0])/2, (n1[1]+n2[1])/2, el['sec'], color='red', fontsize=9, rotation=np.degrees(np.arctan2(n2[1]-n1[1], n2[0]-n1[0])))

    # 💡 رسم الدياجرامات بنظام البوليجونز (SAP2000 Style)
    def fill_diagram(ax, val_key, scale, color_pos, color_neg):
        max_vals = {'inclined': 0, 'base': 0}
        max_pts = {'inclined': None, 'base': None}
        
        for el in elements:
            if el['type'] == 'truss' and val_key == 'N':
                val = el['internal']['N'][0]
                n1, n2 = nodes[el['n1']], nodes[el['n2']]
                ax.plot([n1[0], n2[0]], [n1[1], n2[1]], color='red' if val>0 else 'blue', linestyle='--', linewidth=2)
                ax.text((n1[0]+n2[0])/2, (n1[1]+n2[1])/2, f"{val:.1f}", color='red' if val>0 else 'blue', fontsize=9, fontweight='bold')
                continue
            if el['type'] == 'frame':
                n1, n2 = nodes[el['n1']], nodes[el['n2']]
                c, s = el['c'], el['s']
                v1, v2 = el['internal'][val_key][0], el['internal'][val_key][1]
                
                px1 = n1[0] - s * v1 * scale
                py1 = n1[1] + c * v1 * scale
                px2 = n2[0] - s * v2 * scale
                py2 = n2[1] + c * v2 * scale
                
                pts = [(n1[0],n1[1]), (px1,py1), (px2,py2), (n2[0],n2[1])]
                color = color_pos if (v1+v2) >= 0 else color_neg
                ax.add_patch(Polygon(pts, facecolor=color, alpha=0.4, edgecolor='black', linewidth=0.5, zorder=2))
                
                grp = el['group']
                max_v = max(abs(v1), abs(v2))
                if max_v > max_vals[grp]:
                    max_vals[grp] = max_v
                    max_pts[grp] = (px1, py1) if abs(v1) > abs(v2) else (px2, py2)

        for grp, pt in max_pts.items():
            if pt and max_vals[grp] > 0.1:
                ax.text(pt[0], pt[1] + 0.2, f"Max: {max_vals[grp]:.1f}", color='black', fontsize=9, fontweight='bold', ha='center')

    fill_diagram(ax_n, 'N', scales['N'], 'blue', 'red')    # Compression = Blue, Tension = Red
    fill_diagram(ax_v, 'V', scales['V'], 'purple', 'magenta') 
    fill_diagram(ax_m, 'M', scales['M'], 'green', 'yellow')
    
    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# =========================================================
# 4. Report Generator for Inclined Systems
# =========================================================
def generate_inclined_report(sys_data):
    if os.path.exists("Acrow_Template.docx"):
        doc = Document("Acrow_Template.docx")
        doc.add_page_break()
    else:
        doc = Document()
    
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("CALCULATION SHEET FOR INCLINED FORMWORK SYSTEM")
    run_title.font.name = 'Arial'
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    
    doc.add_paragraph("="*50)
    
    def add_line(text, bold=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(text)
        r.font.name = 'Arial'
        r.font.size = Pt(12)
        r.font.bold = bold
        
    def add_check(component, param, act, allw, unit):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.5
        p.add_run(f"• Check {component} ({param}):\n").bold = True
        r_act = p.add_run(f"  Actual = {act:.2f} {unit}  <  Allowable = {allw:.2f} {unit}  ")
        res = "SAFE" if act <= allw else "UNSAFE"
        r_res = p.add_run(res)
        r_res.font.bold = True
        r_res.font.color.rgb = RGBColor(0, 128, 0) if res == "SAFE" else RGBColor(255, 0, 0)
        
    add_line(f"1. Geometry & Inputs:", bold=True)
    add_line(f"- Inclined Soldier Length = {sys_data['L_tot']:.2f} m")
    add_line(f"- Inclination Angle = {sys_data['angle']:.1f} degrees")
    add_line(f"- Applied Loads = Variable (Refer to Diagram)")
    
    doc.add_paragraph()
    add_line(f"2. Safety Checks:", bold=True)
    
    inc_sec = sys_data['inc_sec']
    add_line(f"A. Inclined Soldier ({inc_sec})", bold=True)
    add_check("Moment", "M_max", sys_data['max_M_inc'], SECTIONS_DB.get(inc_sec, {}).get('Mall', 999), "kN.m")
    add_check("Shear", "V_max", sys_data['max_V_inc'], SECTIONS_DB.get(inc_sec, {}).get('Qall', 999), "kN")
    
    base_sec = sys_data['base_sec']
    add_line(f"B. Horizontal Base Soldier ({base_sec})", bold=True)
    add_check("Moment", "M_max", sys_data['max_M_base'], SECTIONS_DB.get(base_sec, {}).get('Mall', 999), "kN.m")
    add_check("Shear", "V_max", sys_data['max_V_base'], SECTIONS_DB.get(base_sec, {}).get('Qall', 999), "kN")
    
    add_line("C. Push-Pull Struts (Axial Force)", bold=True)
    for idx, st_val in enumerate(sys_data['struts_res']):
        allow = STRUTS_DB.get(st_val['type'], {}).get('allow', 999) 
        add_check(f"Strut {idx+1} ({st_val['type']})", "N_max", st_val['N'], allow, "kN")
        
    doc.add_page_break()
    add_line("3. Analysis Diagrams", bold=True)
    
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.add_run().add_picture(io.BytesIO(sys_data['img_bytes'].read()), width=Cm(16.5))
    
    out = io.BytesIO()
    doc.save(out)
    return out

# =========================================================
# 5. Main UI Module for Inclined Systems
# =========================================================
def render_inclined_module():
    st.markdown("## 📐 Inclined Formwork System (Advanced FEA)")
    
    c_in, c_plot = st.columns([1.3, 1])
    
    with c_in:
        st.markdown("#### 🪵 1. Geometry Setup")
        c_top1, c_top2 = st.columns(2)
        angle_deg = c_top1.number_input("Inclination Angle (Degrees, < 90)", value=60.0, step=5.0)
        angle_rad = np.radians(angle_deg)
        num_struts = c_top2.number_input("Number of Push-Pulls", min_value=1, max_value=5, value=2, step=1)
        
        c_p1, c_p2 = st.columns(2)
        inc_sec = c_p1.selectbox("Profile (Inclined)", list(SECTIONS_DB.keys()) if SECTIONS_DB else ["Soldier U100"])
        base_sec = c_p2.selectbox("Profile (Base)", list(SECTIONS_DB.keys()) if SECTIONS_DB else ["Soldier U100"])
        
        st.markdown("**Struts Connections & Segments**")
        L_segs, X_segs, strut_types = [], [], []
        for j in range(int(num_struts)):
            cl1, cl2, cl3 = st.columns([1, 1, 1.5])
            L_segs.append(cl1.number_input(f"L{j+1} on Inclined (m)", value=2.0, step=0.5, key=f"L_{j}"))
            X_segs.append(cl2.number_input(f"X{j+1} on Base (m)", value=1.5, step=0.5, key=f"X_{j}"))
            strut_types.append(cl3.selectbox(f"Strut {j+1}", list(STRUTS_DB.keys()) if STRUTS_DB else ["PPH601"], key=f"st_{j}"))
            
        cr1, cr2 = st.columns(2)
        L_rem = cr1.number_input("Remaining Inclined Top L (m)", value=1.0, step=0.5)
        X_rem = cr2.number_input("Remaining Base Right X (m)", value=0.5, step=0.5)
        
        # 💡 قسم جديد ومستقل للأحمال كما طلبت
        st.markdown("#### 🎯 2. Applied Loads on Inclined Soldier")
        num_loads = st.number_input("Number of Load Blocks", 1, 5, 1)
        applied_loads = []
        for i in range(int(num_loads)):
            with st.expander(f"Load Block {i+1}", expanded=True):
                l_type = st.selectbox("Load Type", ["Uniform", "Trapezoidal/Triangular", "Point Load"], key=f"lt_{i}")
                cl1, cl2 = st.columns(2)
                start_l = cl1.number_input("Start Distance from bottom (m)", value=0.0, step=0.5, key=f"ls_{i}")
                if l_type == "Point Load":
                    end_l = start_l
                else:
                    len_l = cl2.number_input("Load Length (m)", value=sum(L_segs)+L_rem, step=0.5, key=f"ll_{i}")
                    end_l = start_l + len_l
                    
                cw1, cw2, cw3 = st.columns(3)
                w1 = cw1.number_input("W1 (kN/m or kN)", value=15.0, step=1.0, key=f"w1_{i}")
                w2 = cw2.number_input("W2 (kN/m)", value=15.0 if l_type=='Uniform' else 0.0, step=1.0, key=f"w2_{i}") if l_type != "Point Load" else w1
                ldir = cw3.selectbox("Direction", ["Gravity (Vertical ↓)", "Perpendicular (Local ↘)"], key=f"ldir_{i}")
                
                applied_loads.append({'type': l_type, 'start': start_l, 'end': end_l, 'w1': w1, 'w2': w2, 'dir': ldir})

    # بناء الشبكة (Auto-Meshing) خلف الكواليس
    nodes, elements, nodal_loads, L_tot, X_tot = build_fea_mesh(L_segs, L_rem, X_segs, X_rem, angle_rad, applied_loads, inc_sec, base_sec, strut_types)

    with c_plot:
        st.markdown("<h4 style='text-align: center;'>📡 Live Assigned Loads</h4>", unsafe_allow_html=True)
        live_img_buf = plot_live_geometry(nodes, elements, applied_loads, L_segs, X_segs, angle_deg, inc_sec, base_sec)
        st.image(live_img_buf, use_container_width=True)
        
        # 💡 أدوات التحكم في مقياس الرسم (Scale) لضبط الدياجرامات
        with st.expander("⚙️ Diagram Scale Controls", expanded=True):
            sc_n = st.slider("Axial Force Scale", 0.001, 0.100, 0.02, step=0.005)
            sc_v = st.slider("Shear Force Scale", 0.001, 0.100, 0.02, step=0.005)
            sc_m = st.slider("Moment Scale", 0.01, 0.50, 0.10, step=0.01)
            scales = {'N': sc_n, 'V': sc_v, 'M': sc_m}

    st.markdown("---")
    
    if st.button("🚀 Run Advanced FEA & Generate Report", type="primary", use_container_width=True):
        with st.spinner("Building Matrix & Solving FEA..."):
            U, R = solve_fea_engine(nodes, elements, nodal_loads)
            
            img_buf = plot_sap2000_diagrams(nodes, elements, scales, inc_sec, base_sec)
            st.image(img_buf, use_container_width=True)
            
            max_M_inc, max_V_inc = 0, 0
            max_M_base, max_V_base = 0, 0
            
            for el in elements:
                if el['type'] == 'frame':
                    max_M = max(abs(el['internal']['M'][0]), abs(el['internal']['M'][1]))
                    max_V = max(abs(el['internal']['V'][0]), abs(el['internal']['V'][1]))
                    if el['group'] == 'inclined':
                        max_M_inc = max(max_M_inc, max_M); max_V_inc = max(max_V_inc, max_V)
                    elif el['group'] == 'base':
                        max_M_base = max(max_M_base, max_M); max_V_base = max(max_V_base, max_V)
            
            struts_results = []
            for el in elements:
                if el['type'] == 'truss':
                    struts_results.append({'type': el['sec'], 'N': abs(el['internal']['N'][0])})
                
            sys_data = {
                'L_tot': L_tot,
                'angle': angle_deg,
                'inc_sec': inc_sec,
                'base_sec': base_sec,
                'max_M_inc': max_M_inc,
                'max_V_inc': max_V_inc,
                'max_M_base': max_M_base,
                'max_V_base': max_V_base,
                'struts_res': struts_results,
                'img_bytes': img_buf
            }
            
            docx_out = generate_inclined_report(sys_data)
            
            st.success("✅ SAP2000-Style Analysis Complete!")
            st.download_button("⬇️ Download Inclined System Calculation Sheet", 
                               data=docx_out.getvalue(), 
                               file_name="Inclined_System_Report.docx", 
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
