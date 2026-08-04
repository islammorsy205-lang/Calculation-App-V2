# inclined_master.py

import streamlit as st
import numpy as np
import pandas as pd
import io
import os
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
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
# 0. Helper Functions
# =========================================================
def get_valid_struts(req_len, struts_db):
    valid = []
    for name, props in struts_db.items():
        min_l, max_l = 0.0, 99.0
        if isinstance(props, dict) and 'min' in props and 'max' in props:
            min_l, max_l = props['min'], props['max']
        else:
            m = re.search(r"\((\d+\.?\d*):(\d+\.?\d*)m\)", name)
            if m:
                min_l, max_l = float(m.group(1)), float(m.group(2))
        
        if min_l <= req_len <= max_l:
            valid.append(name)
            
    if not valid:
        return list(struts_db.keys()) if struts_db else ["PPH (Fallback)"]
        
    def priority(name):
        n = name.upper()
        if "PPH" in n: return 1
        if "PPS" in n: return 2
        if "TILT" in n: return 3
        if "MMP" in n: return 4
        return 5
        
    return sorted(valid, key=priority)

def apply_plot_styles():
    mpl.rcParams['font.family'] = 'sans-serif'
    mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    mpl.rcParams['axes.linewidth'] = 0.3
    mpl.rcParams['font.size'] = 7
    mpl.rcParams['font.weight'] = 'normal'

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
    
    for ld in applied_loads:
        inc_key_pts.append(ld['start'])
        if ld['type'] != 'Point Load':
            inc_key_pts.append(ld['end'])
            
    inc_key_pts = sorted(list(set([round(p, 4) for p in inc_key_pts if 0 <= p <= L_tot + 1e-5])))
    
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
    
    nodes.append([0.0, 0.0, False, True, False])
    inc_node_indices.append(0)
    
    for L_val in inc_nodes_L[1:]:
        nodes.append([L_val * np.cos(angle_rad), L_val * np.sin(angle_rad), False, False, False])
        inc_node_indices.append(len(nodes)-1)
        
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
                
    base_props = SECTIONS_DB.get(base_sec, {'E': E_st, 'A': 0.00343, 'I': 0.00000122})
    for i in range(len(base_node_indices)-1):
        elements.append({
            'type': 'frame', 'group': 'base', 'sec': base_sec,
            'n1': base_node_indices[i], 'n2': base_node_indices[i+1],
            'px1': 0.0, 'py1': 0.0, 'px2': 0.0, 'py2': 0.0,
            'E': base_props.get('E', E_st), 'A': base_props.get('A', 0.00343), 'I': base_props.get('I', 0.00000122)
        })
        
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
            el['internal'] = {'N': [N_val, N_val], 'V': [0,0], 'M': [0,0], 'x': [0, L]}
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
            
            xs = np.linspace(0, L, 11)
            N_arr = np.zeros_like(xs)
            V_arr = np.zeros_like(xs)
            M_arr = np.zeros_like(xs)
            
            for i, x in enumerate(xs):
                N_arr[i] = -f_end[0] - (px1*x + (px2-px1)*x**2/(2*L))
                V_arr[i] = f_end[1] + (py1*x + (py2-py1)*x**2/(2*L))
                M_arr[i] = -f_end[2] + f_end[1]*x + py1*x**2/2.0 + (py2-py1)*x**3/(6*L)
                
            el['internal'] = {'N': N_arr, 'V': V_arr, 'M': M_arr, 'x': xs}
            
    return U, R_reactions

# =========================================================
# 3. Engines for Plotting (Live Preview & SAP2000 Style)
# =========================================================
def plot_live_geometry(nodes, elements, applied_loads, L_segs, X_segs, angle_deg, inc_sec, base_sec):
    apply_plot_styles()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True, linestyle=':', alpha=0.3)
    ax.axis('off')

    for i, n in enumerate(nodes):
        x, y = n[0], n[1]
        if n[2] and n[3]: ax.plot(x, y, marker='^', color='orange', markersize=8, zorder=5)
        elif not n[2] and n[3]: ax.plot(x, y, marker='o', color='green', markersize=6, zorder=5)

    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        color = 'blue' if el['type'] == 'frame' else 'red'
        style = '-' if el['type'] == 'frame' else '--'
        lw = 1.0 if el['type'] == 'frame' else 0.8
        ax.plot([n1[0], n2[0]], [n1[1], n2[1]], color=color, linestyle=style, linewidth=lw)

    angle_rad = np.radians(angle_deg)
    c_ang, s_ang = np.cos(angle_rad), np.sin(angle_rad)
    
    curr_l = 0.0
    for i, seg in enumerate(L_segs):
        px = (curr_l + seg/2) * c_ang
        py = (curr_l + seg/2) * s_ang
        ax.text(px - s_ang*0.6, py + c_ang*0.6, f"L{i+1}={seg:.2f}m", color='gray', fontsize=7, rotation=angle_deg, ha='center', va='center')
        curr_l += seg
        
    curr_x = 0.0
    for i, seg in enumerate(X_segs):
        px = curr_x + seg/2
        py = 0.0
        ax.text(px, py - 0.6, f"X{i+1}={seg:.2f}m", color='gray', fontsize=7, ha='center', va='center')
        curr_x += seg

    for ld in applied_loads:
        w1, w2 = ld['w1'], ld['w2']
        start_L, end_L = ld['start'], ld['end']
        dir_type = ld['dir']
        
        if ld['type'] == 'Point Load':
            px = start_L * c_ang
            py = start_L * s_ang
            arrow_len = 1.0
            if dir_type == 'Gravity (Vertical ↓)':
                ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.15, head_length=0.2, fc='fuchsia', ec='fuchsia', zorder=4, linewidth=0.5)
                ax.text(px, py + arrow_len + 0.4, f"{w1} kN", color='fuchsia', fontsize=8, ha='center')
            else:
                ax.arrow(px - s_ang*(arrow_len+0.1), py + c_ang*(arrow_len+0.1), s_ang*arrow_len, -c_ang*arrow_len, head_width=0.15, head_length=0.2, fc='fuchsia', ec='fuchsia', zorder=4, linewidth=0.5)
                ax.text(px - s_ang*(arrow_len+0.4), py + c_ang*(arrow_len+0.4), f"{w1} kN", color='fuchsia', fontsize=8, ha='center', rotation=angle_deg)
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
                    ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.1, head_length=0.15, fc='magenta', ec='magenta', zorder=4, linewidth=0.5)
                else:
                    ax.arrow(px - s_ang*(arrow_len+0.1), py + c_ang*(arrow_len+0.1), s_ang*arrow_len, -c_ang*arrow_len, head_width=0.1, head_length=0.15, fc='magenta', ec='magenta', zorder=4, linewidth=0.5)
                    
            mid_L = (start_L + end_L) / 2.0
            mid_x = mid_L * c_ang
            mid_y = mid_L * s_ang
            txt = f"{w1}" if ld['type'] == 'Uniform' else f"{w1} to {w2}"
            if dir_type == 'Gravity (Vertical ↓)':
                ax.text(mid_x, mid_y + 1.2, f"{txt} kN/m\n({dir_type.split()[0]})", color='magenta', fontsize=7, ha='center')
            else:
                ax.text(mid_x - s_ang*1.2, mid_y + c_ang*1.2, f"{txt} kN/m", color='magenta', fontsize=7, ha='center', rotation=angle_deg)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight', transparent=True)
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

def plot_sap2000_diagrams(nodes, elements, R_reactions, scales, inc_sec, base_sec):
    apply_plot_styles()
    fig = plt.figure(figsize=(18, 12))
    
    # 💡 توزيع جديد للوحات يشمل الـ Reactions
    ax_geom = plt.subplot(2, 3, 1)
    ax_react = plt.subplot(2, 3, 2)
    ax_n = plt.subplot(2, 3, 3)
    ax_v = plt.subplot(2, 3, 4)
    ax_m = plt.subplot(2, 3, 5)
    
    axes = [ax_geom, ax_react, ax_n, ax_v, ax_m]
    for ax in axes:
        ax.set_aspect('equal', adjustable='datalim')
        ax.axis('off')
        
    def draw_bottom_title(ax, title):
        ax.text(0.5, -0.05, title, transform=ax.transAxes, ha='center', va='top', fontname='Arial', fontsize=11, fontweight='normal')
        w = len(title) * 0.012
        ax.plot([0.5 - w, 0.5 + w], [-0.10, -0.10], transform=ax.transAxes, color='black', lw=0.6, clip_on=False)

    def draw_base(ax):
        for i, n in enumerate(nodes):
            x, y = n[0], n[1]
            if n[2] and n[3]: ax.plot(x, y, marker='^', color='orange', markersize=8, zorder=5)
            elif not n[2] and n[3]: ax.plot(x, y, marker='o', color='green', markersize=6, zorder=5)
        for el in elements:
            n1, n2 = nodes[el['n1']], nodes[el['n2']]
            color = 'black' if el['type'] == 'frame' else 'gray'
            style = '-' if el['type'] == 'frame' else '--'
            ax.plot([n1[0], n2[0]], [n1[1], n2[1]], color=color, linestyle=style, linewidth=0.5, zorder=1)

    for ax in axes: draw_base(ax)
    
    draw_bottom_title(ax_geom, "System Geometry")
    draw_bottom_title(ax_react, "Reactions Diagram (kN)")
    draw_bottom_title(ax_n, "Axial Force Diagram (kN)")
    draw_bottom_title(ax_v, "Shear Force Diagram (kN)")
    draw_bottom_title(ax_m, "Bending Moment Diagram (kN.m)")
    
    # --- Geometry Names ---
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        mid_x, mid_y = (n1[0]+n2[0])/2, (n1[1]+n2[1])/2
        if el['group'] == 'inclined':
            ax_geom.text(mid_x - 0.4, mid_y + 0.4, el['sec'], color='dimgray', fontsize=8, rotation=np.degrees(np.arctan2(el['s'], el['c'])), ha='center')
        elif el['group'] == 'base':
            ax_geom.text(mid_x, mid_y - 0.4, el['sec'], color='dimgray', fontsize=8, ha='center')
        elif el['group'] == 'strut':
            ax_geom.text(mid_x, mid_y + 0.2, el['sec'], color='dimgray', fontsize=7, rotation=np.degrees(np.arctan2(n2[1]-n1[1], n2[0]-n1[0])), ha='center')

    # --- Reactions Plot ---
    for i, n in enumerate(nodes):
        if n[2] or n[3]:
            Rx, Ry = R_reactions[3*i], R_reactions[3*i+1]
            x, y = n[0], n[1]
            if abs(Rx) > 0.1:
                ax_react.annotate("", xy=(x, y), xytext=(x - 1.2*np.sign(Rx), y), arrowprops=dict(color='purple', width=0.5, headwidth=4))
                ax_react.text(x - 1.5*np.sign(Rx), y, f"{abs(Rx):.1f}", color='purple', fontname='Arial', fontsize=8, ha='center', va='center')
            if abs(Ry) > 0.1:
                ax_react.annotate("", xy=(x, y), xytext=(x, y - 1.2*np.sign(Ry)), arrowprops=dict(color='purple', width=0.5, headwidth=4))
                ax_react.text(x, y - 1.5*np.sign(Ry), f"{abs(Ry):.1f}", color='purple', fontname='Arial', fontsize=8, ha='center', va='center')

    # --- 💡 Hatching Function (Outline with vertical lines, no fill) ---
    def hatch_diagram(ax, val_key, scale, color_pos, color_neg):
        for el in elements:
            n1, n2 = nodes[el['n1']], nodes[el['n2']]
            x1, y1 = n1[0], n1[1]
            x2, y2 = n2[0], n2[1]
            dx, dy = x2 - x1, y2 - y1
            L_s = np.hypot(dx, dy)
            if L_s < 1e-5: continue
            
            c, s = dx/L_s, dy/L_s
            
            # --- رسم أسماء القطاعات على كل دياجرام بلون خفيف ---
            mid_x, mid_y = x1 + dx/2, y1 + dy/2
            if el['type'] == 'frame':
                offset_c, offset_s = -c*0.4, s*0.4
                ax.text(mid_x + offset_s, mid_y + offset_c, el['sec'], color='gray', fontsize=6, alpha=0.8, ha='center', va='center', rotation=np.degrees(np.arctan2(dy, dx)))
            
            if el['type'] == 'truss' and val_key == 'N':
                val = el['internal']['N'][0]
                if abs(val) < 0.1: continue
                nx, ny = -dy/L_s, dx/L_s
                h = val * scale
                color = color_pos if val >= 0 else color_neg
                
                p1, p2 = (x1, y1), (x2, y2)
                p3, p4 = (x2 + nx * h, y2 + ny * h), (x1 + nx * h, y1 + ny * h)
                
                ax.plot([x1, p4[0], p3[0], x2, x1], [y1, p4[1], p3[1], y2, y1], color=color, linewidth=0.8)
                
                num_lines = max(5, int(L_s / 0.15))
                for i in range(1, num_lines):
                    frac = i / num_lines
                    lx, ly = x1 + frac * dx, y1 + frac * dy
                    ax.plot([lx, lx + nx * h], [ly, ly + ny * h], color=color, linewidth=0.3, alpha=0.6)
                    
                mid_h_x, mid_h_y = x1 + dx/2 + nx*h/2, y1 + dy/2 + ny*h/2
                ax.text(mid_h_x, mid_h_y, f"{abs(val):.1f}", color='black', fontsize=7, fontname='Arial', ha='center', va='center', rotation=np.degrees(np.arctan2(dy, dx)))
                
                # اسم القطاع موازي وملاصق للنهيز من الأسفل
                ax.text(x1 + dx/2 - nx*0.2, y1 + dy/2 - ny*0.2, el['sec'], color='black', fontsize=6, fontname='Arial', ha='center', va='center', rotation=np.degrees(np.arctan2(dy, dx)))
                continue
                
            if el['type'] == 'frame':
                xs_arr = el['internal']['x']
                vals = el['internal'][val_key]
                v_start, v_end = vals[0], vals[-1]
                
                px_arr = x1 + c * xs_arr - s * vals * scale
                py_arr = y1 + s * xs_arr + c * vals * scale
                
                ax.plot(np.append(x1, np.append(px_arr, x2)), np.append(y1, np.append(py_arr, y2)), color=color_pos, linewidth=0.8)
                ax.plot([x1, x2], [y1, y2], color='black', linewidth=0.5)
                
                num_lines = max(4, int(L_s / 0.2))
                for i in range(1, num_lines):
                    frac = i / num_lines
                    lx, ly = x1 + frac * dx, y1 + frac * dy
                    idx_val = int(frac * (len(vals)-1))
                    lv = vals[idx_val]
                    hx, hy = lx - s * lv * scale, ly + c * lv * scale
                    line_color = color_pos if lv >= 0 else color_neg
                    ax.plot([lx, hx], [ly, hy], color=line_color, linewidth=0.3, alpha=0.6)
                    
                # 💡 طباعة القيم في البداية، النهاية، والـ Max
                def write_val(x_base, y_base, v, offset=0.2):
                    if abs(v) > 0.1:
                        txt_x = x_base - s * v * scale - s * np.sign(v) * offset
                        txt_y = y_base + c * v * scale + c * np.sign(v) * offset
                        ax.text(txt_x, txt_y, f"{abs(v):.1f}", color='black', fontsize=7, fontname='Arial', ha='center', va='center')
                
                write_val(x1, y1, v_start)
                write_val(x2, y2, v_end)
                
                max_idx = np.argmax(np.abs(vals))
                if 0 < max_idx < len(vals)-1:
                    v_max = vals[max_idx]
                    x_m = x1 + c * xs_arr[max_idx]
                    y_m = y1 + s * xs_arr[max_idx]
                    write_val(x_m, y_m, v_max, offset=0.3)

    hatch_diagram(ax_n, 'N', scales['N'], 'blue', 'red')    
    hatch_diagram(ax_v, 'V', scales['V'], 'purple', 'magenta') 
    hatch_diagram(ax_m, 'M', scales['M'], 'green', 'yellow')
    
    plt.subplots_adjust(hspace=0.4, bottom=0.1)
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
    
    # تهيئة الذاكرة لحفظ نتائج الحل
    if 'inclined_solved' not in st.session_state:
        st.session_state.inclined_solved = False
        
    c_in, c_plot = st.columns([1.3, 1])
    
    with c_in:
        st.markdown("#### 🪵 1. Geometry Setup")
        c_top1, c_top2 = st.columns(2)
        angle_deg = c_top1.number_input("Inclination Angle (Degrees, < 90)", value=60.0, step=5.0, on_change=lambda: st.session_state.update(inclined_solved=False))
        angle_rad = np.radians(angle_deg)
        num_struts = c_top2.number_input("Number of Push-Pulls", min_value=1, max_value=5, value=2, step=1, on_change=lambda: st.session_state.update(inclined_solved=False))
        
        c_p1, c_p2 = st.columns(2)
        sec_list = list(SECTIONS_DB.keys()) if SECTIONS_DB else ["Soldier U100"]
        default_idx = next((i for i, sec in enumerate(sec_list) if 'Soldier' in sec), 0)
        
        inc_sec = c_p1.selectbox("Profile (Inclined)", sec_list, index=default_idx, on_change=lambda: st.session_state.update(inclined_solved=False))
        base_sec = c_p2.selectbox("Profile (Base)", sec_list, index=default_idx, on_change=lambda: st.session_state.update(inclined_solved=False))
        
        st.markdown("**Struts Connections & Segments**")
        L_segs, X_segs, strut_types = [], [], []
        L_cum, X_cum = 0.0, 0.0
        
        for j in range(int(num_struts)):
            cl1, cl2, cl3 = st.columns([1, 1, 1.5])
            l_val = cl1.number_input(f"L{j+1} on Inclined (m)", value=2.0, step=0.5, key=f"L_{j}", on_change=lambda: st.session_state.update(inclined_solved=False))
            x_val = cl2.number_input(f"X{j+1} on Base (m)", value=1.5, step=0.5, key=f"X_{j}", on_change=lambda: st.session_state.update(inclined_solved=False))
            
            L_segs.append(l_val)
            X_segs.append(x_val)
            L_cum += l_val
            X_cum += x_val
            
            req_len = np.hypot(X_cum - L_cum * np.cos(angle_rad), 0 - L_cum * np.sin(angle_rad))
            valid_struts = get_valid_struts(req_len, STRUTS_DB)
            st_type = cl3.selectbox(f"Strut {j+1} (Req: {req_len:.2f}m)", valid_struts, key=f"st_{j}", on_change=lambda: st.session_state.update(inclined_solved=False))
            strut_types.append(st_type)
            
        cr1, cr2 = st.columns(2)
        L_rem = cr1.number_input("Remaining Inclined Top L (m)", value=1.0, step=0.5, on_change=lambda: st.session_state.update(inclined_solved=False))
        X_rem = cr2.number_input("Remaining Base Right X (m)", value=0.5, step=0.5, on_change=lambda: st.session_state.update(inclined_solved=False))
        
        st.markdown("#### 🎯 2. Applied Loads on Inclined Soldier")
        num_loads = st.number_input("Number of Load Blocks", 1, 5, 1, on_change=lambda: st.session_state.update(inclined_solved=False))
        applied_loads = []
        for i in range(int(num_loads)):
            with st.expander(f"Load Block {i+1}", expanded=True):
                l_type = st.selectbox("Load Type", ["Uniform", "Trapezoidal/Triangular", "Point Load"], key=f"lt_{i}", on_change=lambda: st.session_state.update(inclined_solved=False))
                cl1, cl2 = st.columns(2)
                start_l = cl1.number_input("Start Distance from bottom (m)", value=0.0, step=0.5, key=f"ls_{i}", on_change=lambda: st.session_state.update(inclined_solved=False))
                if l_type == "Point Load":
                    end_l = start_l
                else:
                    len_l = cl2.number_input("Load Length (m)", value=sum(L_segs)+L_rem, step=0.5, key=f"ll_{i}", on_change=lambda: st.session_state.update(inclined_solved=False))
                    end_l = start_l + len_l
                    
                cw1, cw2, cw3 = st.columns(3)
                w1 = cw1.number_input("W1 (kN/m or kN)", value=15.0, step=1.0, key=f"w1_{i}", on_change=lambda: st.session_state.update(inclined_solved=False))
                w2 = cw2.number_input("W2 (kN/m)", value=15.0 if l_type=='Uniform' else 0.0, step=1.0, key=f"w2_{i}", on_change=lambda: st.session_state.update(inclined_solved=False)) if l_type != "Point Load" else w1
                ldir = cw3.selectbox("Direction", ["Gravity (Vertical ↓)", "Perpendicular (Local ↘)"], key=f"ldir_{i}", on_change=lambda: st.session_state.update(inclined_solved=False))
                
                applied_loads.append({'type': l_type, 'start': start_l, 'end': end_l, 'w1': w1, 'w2': w2, 'dir': ldir})

    nodes, elements, nodal_loads, L_tot, X_tot = build_fea_mesh(L_segs, L_rem, X_segs, X_rem, angle_rad, applied_loads, inc_sec, base_sec, strut_types)

    with c_plot:
        st.markdown("<h4 style='text-align: center; font-family: Arial; font-weight: normal; border-bottom: 1px solid black; padding-bottom: 5px;'>Live Assigned Loads</h4>", unsafe_allow_html=True)
        live_img_buf = plot_live_geometry(nodes, elements, applied_loads, L_segs, X_segs, angle_deg, inc_sec, base_sec)
        st.image(live_img_buf, use_container_width=True)

    st.markdown("---")
    
    col_btn, col_blank = st.columns([1, 2])
    with col_btn:
        if st.button("🚀 Run Advanced FEA & Generate Report", type="primary", use_container_width=True):
            with st.spinner("Building Matrix & Solving FEA..."):
                U, R = solve_fea_engine(nodes, elements, nodal_loads)
                st.session_state.inclined_fea_data = {
                    'U': U, 'R': R, 'nodes': nodes, 'elements': elements,
                    'sys_data': {
                        'L_tot': L_tot, 'angle': angle_deg, 'W': "Variable", 'ld_dir': "Variable",
                        'inc_sec': inc_sec, 'base_sec': base_sec
                    }
                }
                st.session_state.inclined_solved = True
    
    # 💡 إظهار أدوات التحكم والنتائج فقط بعد الضغط على Run مع الاحتفاظ بها نشطة
    if st.session_state.inclined_solved:
        fea_data = st.session_state.inclined_fea_data
        
        st.markdown("### 🎛️ Analysis Results & Formatting")
        with st.expander("⚙️ Diagram Scale Controls", expanded=True):
            c_s1, c_s2, c_s3 = st.columns(3)
            sc_n = c_s1.slider("Axial Force Scale", 0.001, 0.100, 0.02, step=0.005)
            sc_v = c_s2.slider("Shear Force Scale", 0.001, 0.100, 0.02, step=0.005)
            sc_m = c_s3.slider("Moment Scale", 0.01, 0.50, 0.10, step=0.01)
            scales = {'N': sc_n, 'V': sc_v, 'M': sc_m}
            
        img_buf = plot_sap2000_diagrams(fea_data['nodes'], fea_data['elements'], fea_data['R'], scales, fea_data['sys_data']['inc_sec'], fea_data['sys_data']['base_sec'])
        st.image(img_buf, use_container_width=True)
        
        max_M_inc, max_V_inc = 0, 0
        max_M_base, max_V_base = 0, 0
        
        for el in fea_data['elements']:
            if el['type'] == 'frame':
                max_M = max(abs(el['internal']['M'][0]), abs(el['internal']['M'][-1]))
                if len(el['internal']['M']) > 2: max_M = max(max_M, np.max(np.abs(el['internal']['M'])))
                max_V = max(abs(el['internal']['V'][0]), abs(el['internal']['V'][-1]))
                if len(el['internal']['V']) > 2: max_V = max(max_V, np.max(np.abs(el['internal']['V'])))
                
                if el['group'] == 'inclined':
                    max_M_inc = max(max_M_inc, max_M); max_V_inc = max(max_V_inc, max_V)
                elif el['group'] == 'base':
                    max_M_base = max(max_M_base, max_M); max_V_base = max(max_V_base, max_V)
        
        struts_results = []
        for el in fea_data['elements']:
            if el['type'] == 'truss':
                struts_results.append({'type': el['sec'], 'N': abs(el['internal']['N'][0])})
            
        fea_data['sys_data'].update({
            'max_M_inc': max_M_inc, 'max_V_inc': max_V_inc,
            'max_M_base': max_M_base, 'max_V_base': max_V_base,
            'struts_res': struts_results,
            'img_bytes': img_buf
        })
        
        docx_out = generate_inclined_report(fea_data['sys_data'])
        
        st.success("✅ SAP2000-Style Analysis Complete!")
        st.download_button("⬇️ Download Inclined System Calculation Sheet", 
                           data=docx_out.getvalue(), 
                           file_name="Inclined_System_Report.docx", 
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
