# inclined_master.py

import streamlit as st
import numpy as np
import io
import os
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
# 1. Advanced 2D Frame FEA Solver for Inclined Systems
# =========================================================
def solve_inclined_fea(nodes, elements):
    num_nodes = len(nodes)
    NDOF = num_nodes * 3
    K = np.zeros((NDOF, NDOF))
    F = np.zeros(NDOF)
    
    for idx, el in enumerate(elements):
        n1, n2 = el['n1'], el['n2']
        x1, y1 = nodes[n1][0], nodes[n1][1]
        x2, y2 = nodes[n2][0], nodes[n2][1]
        
        L = np.hypot(x2 - x1, y2 - y1)
        if L < 1e-5: continue
        
        c, s = (x2 - x1) / L, (y2 - y1) / L
        el['L'], el['c'], el['s'] = L, c, s
        
        E_raw = el.get('E', 210000000.0)
        E = E_raw if E_raw > 1000000 else E_raw * 10000.0 
        A_raw = el.get('A', 0.00343)
        A = A_raw if A_raw < 0.1 else A_raw / 10000.0 
        I_raw = el.get('I', 0.00000122)
        I = I_raw if I_raw < 0.001 else I_raw / 100000000.0 
        
        T = np.array([
            [c, s, 0, 0, 0, 0], [-s, c, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0], [0, 0, 0, -s, c, 0], [0, 0, 0, 0, 0, 1]
        ])
        
        if el['type'] == 'truss':
            k_loc = np.zeros((6, 6))
            k_loc[0, 0] = k_loc[3, 3] = E * A / L
            k_loc[0, 3] = k_loc[3, 0] = -E * A / L
        else:
            k_loc = np.array([
                [E*A/L, 0, 0, -E*A/L, 0, 0],
                [0, 12*E*I/L**3, 6*E*I/L**2, 0, -12*E*I/L**3, 6*E*I/L**2],
                [0, 6*E*I/L**2, 4*E*I/L, 0, -6*E*I/L**2, 2*E*I/L],
                [-E*A/L, 0, 0, E*A/L, 0, 0],
                [0, -12*E*I/L**3, -6*E*I/L**2, 0, 12*E*I/L**3, -6*E*I/L**2],
                [0, 6*E*I/L**2, 2*E*I/L, 0, -6*E*I/L**2, 4*E*I/L]
            ])
            
        k_glob = T.T @ k_loc @ T
        dof_idx = [3*n1, 3*n1+1, 3*n1+2, 3*n2, 3*n2+1, 3*n2+2]
        
        for r in range(6):
            for col in range(6):
                K[dof_idx[r], dof_idx[col]] += k_glob[r, col]
                
        # --- حساب Equivalent Nodal Forces بناءً على شكل الحمل ---
        ld_type = el.get('ld_type', 'None')
        if ld_type != 'None':
            W1 = el.get('W1', 0.0)
            W2 = el.get('W2', 0.0)
            ld_dir = el.get('dir', 'Gravity (Vertical ↓)')
            
            if ld_dir == 'Gravity (Vertical ↓)':
                px1, py1 = -W1 * s, -W1 * c
                px2, py2 = -W2 * s, -W2 * c
            else:
                px1, py1 = 0.0, -W1
                px2, py2 = 0.0, -W2
                
            if ld_type == 'Uniform':
                px2, py2 = px1, py1
                
            if ld_type in ['Uniform', 'Trapezoidal/Triangular']:
                f_eq_loc = np.array([
                    (2*px1 + px2)*L/6.0,
                    (7*py1 + 3*py2)*L/20.0,
                    (3*py1 + 2*py2)*L**2/60.0,
                    (px1 + 2*px2)*L/6.0,
                    (3*py1 + 7*py2)*L/20.0,
                    -(2*py1 + 3*py2)*L**2/60.0
                ])
            elif ld_type == 'Point Load (Center)':
                f_eq_loc = np.array([
                    px1 / 2.0,
                    py1 / 2.0,
                    py1 * L / 8.0,
                    px1 / 2.0,
                    py1 / 2.0,
                    -py1 * L / 8.0
                ])
                
            f_eq_glob = T.T @ f_eq_loc
            for r in range(6):
                F[dof_idx[r]] += f_eq_glob[r]
            
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
    
    # --- استخراج القوى الداخلية ورسم الـ Diagrams ---
    for el in elements:
        n1, n2 = el['n1'], el['n2']
        c, s, L = el['c'], el['s'], el['L']
        
        E_raw = el.get('E', 210000000.0)
        E = E_raw if E_raw > 1000000 else E_raw * 10000.0 
        A_raw = el.get('A', 0.00343)
        A = A_raw if A_raw < 0.1 else A_raw / 10000.0 
        I_raw = el.get('I', 0.00000122)
        I = I_raw if I_raw < 0.001 else I_raw / 100000000.0 
        
        dof_idx = [3*n1, 3*n1+1, 3*n1+2, 3*n2, 3*n2+1, 3*n2+2]
        u_glob = U[dof_idx]
        T = np.array([
            [c, s, 0, 0, 0, 0], [-s, c, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0], [0, 0, 0, -s, c, 0], [0, 0, 0, 0, 0, 1]
        ])
        u_loc = T @ u_glob
        
        if el['type'] == 'truss':
            N = (E * A / L) * (u_loc[3] - u_loc[0])
            el['internal'] = {'N': N, 'V': np.zeros(11), 'M': np.zeros(11), 'x': np.linspace(0, L, 11)}
        else:
            k_loc = np.array([
                [E*A/L, 0, 0, -E*A/L, 0, 0],
                [0, 12*E*I/L**3, 6*E*I/L**2, 0, -12*E*I/L**3, 6*E*I/L**2],
                [0, 6*E*I/L**2, 4*E*I/L, 0, -6*E*I/L**2, 2*E*I/L],
                [-E*A/L, 0, 0, E*A/L, 0, 0],
                [0, -12*E*I/L**3, -6*E*I/L**2, 0, 12*E*I/L**3, -6*E*I/L**2],
                [0, 6*E*I/L**2, 2*E*I/L, 0, -6*E*I/L**2, 4*E*I/L]
            ])
            
            ld_type = el.get('ld_type', 'None')
            W1 = el.get('W1', 0.0)
            W2 = el.get('W2', 0.0)
            ld_dir = el.get('dir', 'Gravity (Vertical ↓)')
            
            if ld_dir == 'Gravity (Vertical ↓)':
                px1, py1 = -W1 * s, -W1 * c
                px2, py2 = -W2 * s, -W2 * c
            else:
                px1, py1 = 0.0, -W1
                px2, py2 = 0.0, -W2
                
            if ld_type == 'Uniform':
                px2, py2 = px1, py1

            if ld_type in ['Uniform', 'Trapezoidal/Triangular']:
                f_eq_loc = np.array([
                    (2*px1 + px2)*L/6.0,
                    (7*py1 + 3*py2)*L/20.0,
                    (3*py1 + 2*py2)*L**2/60.0,
                    (px1 + 2*px2)*L/6.0,
                    (3*py1 + 7*py2)*L/20.0,
                    -(2*py1 + 3*py2)*L**2/60.0
                ])
            elif ld_type == 'Point Load (Center)':
                f_eq_loc = np.array([
                    px1 / 2.0, py1 / 2.0, py1 * L / 8.0,
                    px1 / 2.0, py1 / 2.0, -py1 * L / 8.0
                ])
            else:
                f_eq_loc = np.zeros(6)
                
            f_end = k_loc @ u_loc - f_eq_loc
            
            xs = np.linspace(0, L, 11)
            N_arr = np.zeros_like(xs)
            V_arr = np.zeros_like(xs)
            M_arr = np.zeros_like(xs)
            
            if ld_type in ['Uniform', 'Trapezoidal/Triangular']:
                for i, x in enumerate(xs):
                    N_arr[i] = -f_end[0] - (px1*x + (px2-px1)*x**2/(2*L))
                    V_arr[i] = f_end[1] + (py1*x + (py2-py1)*x**2/(2*L))
                    M_arr[i] = -f_end[2] + f_end[1]*x + py1*x**2/2.0 + (py2-py1)*x**3/(6*L)
            elif ld_type == 'Point Load (Center)':
                for i, x in enumerate(xs):
                    N_arr[i] = -f_end[0] - (px1 if x > L/2.0 + 1e-5 else 0.0)
                    V_arr[i] = f_end[1] + (py1 if x > L/2.0 + 1e-5 else 0.0)
                    M_arr[i] = -f_end[2] + f_end[1]*x + (py1*(x-L/2.0) if x > L/2.0 + 1e-5 else 0.0)
            else:
                for i, x in enumerate(xs):
                    N_arr[i] = -f_end[0]
                    V_arr[i] = f_end[1]
                    M_arr[i] = -f_end[2] + f_end[1]*x
                    
            el['internal'] = {'N': N_arr, 'V': V_arr, 'M': M_arr, 'x': xs}
            
    return U, R_reactions, nodes, elements

# =========================================================
# 2. Engines for Plotting (Live Preview & Full Results)
# =========================================================
def plot_live_geometry(nodes, elements, angle_deg):
    # 💡 حجم مدمج وصغير للرسمة عشان تظهر جنب المعطيات بدون Scrolling
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True, linestyle=':', alpha=0.3)

    # 1. رسم الركائز والعناصر
    for i, n in enumerate(nodes):
        x, y = n[0], n[1]
        if n[2] and n[3]: ax.plot(x, y, marker='^', color='orange', markersize=12, zorder=5)
        elif not n[2] and n[3]: ax.plot(x, y, marker='o', color='green', markersize=10, zorder=5)

    inc_idx = 0
    base_idx = 0
    for idx, el in enumerate(elements):
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        x1, y1 = n1[0], n1[1]
        x2, y2 = n2[0], n2[1]
        
        L_val = np.hypot(x2 - x1, y2 - y1)
        c_val = (x2 - x1) / L_val if L_val != 0 else 1
        s_val = (y2 - y1) / L_val if L_val != 0 else 0
        
        color = 'blue' if el['type'] == 'frame' else 'red'
        style = '-' if el['type'] == 'frame' else '--'
        lw = 4 if el['type'] == 'frame' else 1.5
        ax.plot([x1, x2], [y1, y2], color=color, linestyle=style, linewidth=lw)

        # 💡 توقيع الرموز L و X بلون رمادي خفيف
        if el['type'] == 'frame':
            mid_x = x1 + c_val * L_val/2
            mid_y = y1 + s_val * L_val/2
            if s_val > 0.1: # Inclined element
                inc_idx += 1
                ax.text(mid_x - s_val*0.3, mid_y + c_val*0.3, f"L{inc_idx}={L_val:.2f}m", color='gray', fontsize=7, alpha=0.7, ha='center', va='center', rotation=angle_deg)
            else: # Base element
                base_idx += 1
                ax.text(mid_x, mid_y - 0.4, f"X{base_idx}={L_val:.2f}m", color='gray', fontsize=7, alpha=0.7, ha='center', va='center')

        # 💡 توقيع الأسهم المعبرة عن شكل الحمل (مثلث، موزع، أو مركز)
        ld_type = el.get('ld_type', 'None')
        if ld_type != 'None':
            W1 = el.get('W1', 0.0)
            W2 = el.get('W2', 0.0)
            dir_type = el.get('dir', 'Gravity (Vertical ↓)')
            
            if ld_type in ['Uniform', 'Trapezoidal/Triangular']:
                num_arrows = max(3, int(L_val / 0.4)) 
                xs = np.linspace(0, L_val, num_arrows)
                for x_dist in xs:
                    w_current = W1 + (W2 - W1) * (x_dist / L_val)
                    if abs(w_current) < 0.5: continue # لا ترسم سهم لو الحمل بصفر
                    
                    px = x1 + c_val * x_dist
                    py = y1 + s_val * x_dist
                    arrow_len = 0.6 * (abs(w_current) / max(abs(W1), abs(W2), 1))
                    
                    if dir_type == 'Gravity (Vertical ↓)':
                        ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.1, head_length=0.1, fc='magenta', ec='magenta', zorder=4)
                    else:
                        start_x = px - s_val * (arrow_len + 0.1)
                        start_y = py + c_val * (arrow_len + 0.1)
                        ax.arrow(start_x, start_y, s_val * arrow_len, -c_val * arrow_len, head_width=0.1, head_length=0.1, fc='magenta', ec='magenta', zorder=4)
                
                mid_x = x1 + c_val * L_val/2
                mid_y = y1 + s_val * L_val/2
                text_w = f"{W1}" if ld_type == 'Uniform' else f"{W1} to {W2}"
                if dir_type == 'Gravity (Vertical ↓)':
                    ax.text(mid_x, mid_y + 1.2, f"{text_w}\n(kN/m)", color='magenta', fontsize=7, fontweight='bold', ha='center')
                else:
                    ax.text(mid_x - s_val*1.2, mid_y + c_val*1.2, f"{text_w}\n(kN/m)", color='magenta', fontsize=7, fontweight='bold', ha='center', rotation=angle_deg)

            elif ld_type == 'Point Load (Center)':
                x_dist = L_val / 2.0
                px = x1 + c_val * x_dist
                py = y1 + s_val * x_dist
                arrow_len = 0.8
                if dir_type == 'Gravity (Vertical ↓)':
                    ax.arrow(px, py + arrow_len + 0.1, 0, -arrow_len, head_width=0.15, head_length=0.15, fc='fuchsia', ec='fuchsia', zorder=4)
                    ax.text(px, py + 1.2, f"{W1} kN", color='fuchsia', fontsize=7, fontweight='bold', ha='center')
                else:
                    start_x = px - s_val * (arrow_len + 0.1)
                    start_y = py + c_val * (arrow_len + 0.1)
                    ax.arrow(start_x, start_y, s_val * arrow_len, -c_val * arrow_len, head_width=0.15, head_length=0.15, fc='fuchsia', ec='fuchsia', zorder=4)
                    ax.text(start_x - s_val*0.3, start_y + c_val*0.3, f"{W1} kN", color='fuchsia', fontsize=7, fontweight='bold', ha='center', rotation=angle_deg)

    plt.axis('off')
    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight', transparent=True)
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

def plot_inclined_system(nodes, elements, R_reactions):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    ax_geom, ax_n, ax_v, ax_m = axes.flatten()
    
    for ax in axes.flatten():
        ax.set_aspect('equal', adjustable='datalim')
        ax.grid(True, linestyle=':', alpha=0.5)
        
    def draw_supports(ax):
        for i, n in enumerate(nodes):
            x, y = n[0], n[1]
            if n[2] and n[3]: 
                ax.plot(x, y, marker='^', color='orange', markersize=12, zorder=5)
            elif not n[2] and n[3]: 
                ax.plot(x, y, marker='o', color='green', markersize=10, zorder=5)

    ax_geom.set_title("System Geometry & Supports", fontsize=12, fontweight='bold')
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        color = 'blue' if el['type'] == 'frame' else 'red'
        style = '-' if el['type'] == 'frame' else '--'
        ax_geom.plot([n1[0], n2[0]], [n1[1], n2[1]], color=color, linestyle=style, linewidth=2)
    draw_supports(ax_geom)
    
    ax_n.set_title("Axial Force Diagram (kN)", fontsize=12, fontweight='bold')
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        x1, y1, x2, y2 = n1[0], n1[1], n2[0], n2[1]
        c, s = el['c'], el['s']
        if el['type'] == 'truss':
            val = el['internal']['N']
            ax_n.plot([x1, x2], [y1, y2], color='red', linestyle='--', linewidth=1.5)
            ax_n.text((x1+x2)/2, (y1+y2)/2, f"{val:.1f}", color='red', fontsize=9, fontweight='bold')
        else:
            N_vals = el['internal']['N']
            xs = el['internal']['x']
            scale = 0.02
            for j in range(len(xs)-1):
                x_start = x1 + c * xs[j] - s * (N_vals[j]*scale)
                y_start = y1 + s * xs[j] + c * (N_vals[j]*scale)
                x_end = x1 + c * xs[j+1] - s * (N_vals[j+1]*scale)
                y_end = y1 + s * xs[j+1] + c * (N_vals[j+1]*scale)
                color = 'blue' if N_vals[j] < 0 else 'red'
                ax_n.plot([x_start, x_end], [y_start, y_end], color=color, linewidth=1.5)
            ax_n.plot([x1, x2], [y1, y2], color='black', linewidth=1)
            ax_n.text(x1 + c*xs[5], y1 + s*xs[5] + 0.5, f"Max: {np.max(np.abs(N_vals)):.1f}", color='black', fontsize=9)
    draw_supports(ax_n)

    ax_v.set_title("Shear Force Diagram (kN)", fontsize=12, fontweight='bold')
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        x1, y1, x2, y2 = n1[0], n1[1], n2[0], n2[1]
        c, s = el['c'], el['s']
        if el['type'] == 'frame':
            V_vals = el['internal']['V']
            xs = el['internal']['x']
            scale = 0.02
            for j in range(len(xs)-1):
                x_start = x1 + c * xs[j] - s * (V_vals[j]*scale)
                y_start = y1 + s * xs[j] + c * (V_vals[j]*scale)
                x_end = x1 + c * xs[j+1] - s * (V_vals[j+1]*scale)
                y_end = y1 + s * xs[j+1] + c * (V_vals[j+1]*scale)
                ax_v.plot([x_start, x_end], [y_start, y_end], color='purple', linewidth=1.5)
            ax_v.plot([x1, x2], [y1, y2], color='black', linewidth=1)
            ax_v.text(x1 + c*xs[5], y1 + s*xs[5] + 0.5, f"Max: {np.max(np.abs(V_vals)):.1f}", color='black', fontsize=9)
    draw_supports(ax_v)
    
    ax_m.set_title("Bending Moment Diagram (kN.m)", fontsize=12, fontweight='bold')
    for el in elements:
        n1, n2 = nodes[el['n1']], nodes[el['n2']]
        x1, y1, x2, y2 = n1[0], n1[1], n2[0], n2[1]
        c, s = el['c'], el['s']
        if el['type'] == 'frame':
            M_vals = el['internal']['M']
            xs = el['internal']['x']
            scale = 0.05
            for j in range(len(xs)-1):
                x_start = x1 + c * xs[j] - s * (M_vals[j]*scale)
                y_start = y1 + s * xs[j] + c * (M_vals[j]*scale)
                x_end = x1 + c * xs[j+1] - s * (M_vals[j+1]*scale)
                y_end = y1 + s * xs[j+1] + c * (M_vals[j+1]*scale)
                ax_m.plot([x_start, x_end], [y_start, y_end], color='green', linewidth=1.5)
            ax_m.plot([x1, x2], [y1, y2], color='black', linewidth=1)
            ax_m.text(x1 + c*xs[5], y1 + s*xs[5] + 0.5, f"Max: {np.max(np.abs(M_vals)):.1f}", color='black', fontsize=9)
    draw_supports(ax_m)
    
    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# =========================================================
# 3. Report Generator for Inclined Systems
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
    add_line(f"- Loads Applied = As per detailed Load Diagram")
    
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
# 4. Main UI Module for Inclined Systems
# =========================================================
def render_inclined_module():
    st.markdown("## 📐 Inclined Formwork System (Advanced FEA)")
    st.info("💡 **Live Geometry Module:** The geometry and complex loads update instantly on the right. Hit Run to calculate Internal Forces.")
    
    c_top1, c_top2 = st.columns(2)
    angle_deg = c_top1.number_input("Inclination Angle (Degrees, < 90)", value=60.0, step=5.0)
    angle_rad = np.radians(angle_deg)
    num_struts = c_top2.number_input("Number of Push-Pulls", min_value=1, max_value=5, value=2, step=1)
        
    st.markdown("---")
    
    # 💡 تقسيم الشاشة لمنطقة إدخال البيانات ومنطقة الرسم اللحظي لعدم الـ Scrolling
    c_in, c_plot = st.columns([1.3, 1])
    
    with c_in:
        st.markdown("#### 🪵 1. Inclined Soldier Configuration")
        inc_sec = st.selectbox("Profile (Inclined)", list(SECTIONS_DB.keys()) if SECTIONS_DB else ["Soldier U100"])
        
        elements_data = [] # To store all data temporarily before building the arrays
        
        L_segs = []
        for j in range(int(num_struts)):
            with st.expander(f"Segment L{j+1} Setup", expanded=False):
                L_val = st.number_input(f"Length L{j+1} (m)", value=2.0, step=0.5, key=f"L_{j}")
                L_segs.append(L_val)
                ltype = st.selectbox("Load Type", ["Uniform", "Trapezoidal/Triangular", "Point Load (Center)", "None"], key=f"lt_{j}")
                
                cl1, cl2 = st.columns(2)
                w1 = cl1.number_input("Value 1 (kN/m or kN)", value=15.0, step=1.0, key=f"w1_{j}")
                w2 = 0.0
                if ltype == "Trapezoidal/Triangular":
                    w2 = cl2.number_input("Value 2 (kN/m)", value=0.0, step=1.0, key=f"w2_{j}")
                ldir = st.radio("Direction", ["Gravity (Vertical ↓)", "Perpendicular (Local ↘)"], key=f"ldir_{j}", horizontal=True)
                
                elements_data.append({'type': 'frame', 'sec': inc_sec, 'L': L_val, 'ld_type': ltype, 'W1': w1, 'W2': w2, 'dir': ldir})
                
        with st.expander("Cantilever Top (Remaining Length)", expanded=False):
            L_rem = st.number_input("Length Top (m)", value=1.0, step=0.5)
            ltype = st.selectbox("Load Type", ["Uniform", "Trapezoidal/Triangular", "Point Load (Center)", "None"], key="lt_top")
            cl1, cl2 = st.columns(2)
            w1 = cl1.number_input("Value 1 (kN/m or kN)", value=15.0, step=1.0, key="w1_top")
            w2 = 0.0
            if ltype == "Trapezoidal/Triangular":
                w2 = cl2.number_input("Value 2 (kN/m)", value=0.0, step=1.0, key="w2_top")
            ldir = st.radio("Direction", ["Gravity (Vertical ↓)", "Perpendicular (Local ↘)"], key="ldir_top", horizontal=True)
            
            L_tot = sum(L_segs) + L_rem
            st.success(f"Total Inclined Length = {L_tot:.2f} m")
            
            if L_rem > 0:
                elements_data.append({'type': 'frame', 'sec': inc_sec, 'L': L_rem, 'ld_type': ltype, 'W1': w1, 'W2': w2, 'dir': ldir})

        st.markdown("#### ⚓ 2. Base Configuration & Struts")
        base_sec = st.selectbox("Profile (Base)", list(SECTIONS_DB.keys()) if SECTIONS_DB else ["Soldier U100"])
        
        X_segs = []
        strut_types = []
        for j in range(int(num_struts)):
            cx1, cx2 = st.columns(2)
            X_segs.append(cx1.number_input(f"Base Segment X{j+1} (m)", value=1.5, step=0.5, key=f"X_seg_{j}"))
            strut_types.append(cx2.selectbox(f"Strut {j+1} Profile", list(STRUTS_DB.keys()) if STRUTS_DB else ["PPH601"], key=f"st_type_{j}"))
        
        X_rem = st.number_input("Remaining Base Length (m)", value=0.5, step=0.5)
        X_tot = sum(X_segs) + X_rem
        st.success(f"Total Base Length = {X_tot:.2f} m")

    # 💡 بناء Nodes & Elements خلف الكواليس
    nodes = [[0.0, 0.0, False, True, False]]
    L_cum = 0.0
    inc_node_indices = [0]
    
    for i, seg in enumerate(L_segs):
        L_cum += seg
        nodes.append([L_cum * np.cos(angle_rad), L_cum * np.sin(angle_rad), False, False, False])
        inc_node_indices.append(len(nodes)-1)
    if L_rem > 0:
        L_cum += L_rem
        nodes.append([L_cum * np.cos(angle_rad), L_cum * np.sin(angle_rad), False, False, False])
        inc_node_indices.append(len(nodes)-1)
        
    X_cum = 0.0
    base_node_indices = [0]
    for X_seg in X_segs:
        X_cum += X_seg
        nodes.append([X_cum, 0.0, True, True, False])
        base_node_indices.append(len(nodes)-1)
    if X_rem > 0:
        X_cum += X_rem
        nodes.append([X_cum, 0.0, False, False, False]) 
        base_node_indices.append(len(nodes)-1)
        
    elements = []
    E_st = 210000000.0 
    
    # ربط بيانات الـ Elements بالـ Nodes
    for j in range(len(inc_node_indices)-1):
        ed = elements_data[j]
        inc_props = SECTIONS_DB.get(ed['sec'], {'E': E_st, 'A': 0.00343, 'I': 0.00000122})
        elements.append({
            'type': 'frame', 'sec': ed['sec'],
            'n1': inc_node_indices[j], 'n2': inc_node_indices[j+1],
            'E': inc_props.get('E', E_st), 'A': inc_props.get('A', 0.00343), 'I': inc_props.get('I', 0.00000122),
            'ld_type': ed['ld_type'], 'W1': ed['W1'], 'W2': ed['W2'], 'dir': ed['dir']
        })
        
    base_props = SECTIONS_DB.get(base_sec, {'E': E_st, 'A': 0.00343, 'I': 0.00000122})
    for j in range(len(base_node_indices)-1):
        elements.append({
            'type': 'frame', 'sec': base_sec,
            'n1': base_node_indices[j], 'n2': base_node_indices[j+1],
            'E': base_props.get('E', E_st), 'A': base_props.get('A', 0.00343), 'I': base_props.get('I', 0.00000122),
            'ld_type': 'None'
        })
        
    struts_results_placeholder = []
    for j in range(int(num_struts)):
        n_inc = inc_node_indices[j+1]
        n_base = base_node_indices[j+1]
        st_type = strut_types[j]
        st_props = STRUTS_DB.get(st_type, {'A': 0.001}) 
        elements.append({
            'type': 'truss', 'sec': st_type,
            'n1': n_base, 'n2': n_inc,
            'E': E_st, 'A': st_props.get('A', 0.001),
            'ld_type': 'None'
        })
        struts_results_placeholder.append({'idx': len(elements)-1, 'type': st_type})

    with c_plot:
        st.markdown("<h4 style='text-align: center;'>📡 Live Assigned Loads</h4>", unsafe_allow_html=True)
        live_img_buf = plot_live_geometry(nodes, elements, angle_deg)
        st.image(live_img_buf, use_container_width=True)

    st.markdown("---")
    
    if st.button("🚀 Run Advanced FEA & Generate Report", type="primary", use_container_width=True):
        with st.spinner("Building Stiffness Matrix & Solving..."):
            U, R, final_nodes, final_elements = solve_inclined_fea(nodes, elements)
            
            img_buf = plot_inclined_system(final_nodes, final_elements, R)
            st.image(img_buf, use_container_width=True)
            
            max_M_inc, max_V_inc = 0, 0
            max_M_base, max_V_base = 0, 0
            
            for el in final_elements:
                if el['type'] == 'frame':
                    if el['sec'] == inc_sec:
                        max_M_inc = max(max_M_inc, np.max(np.abs(el['internal']['M'])))
                        max_V_inc = max(max_V_inc, np.max(np.abs(el['internal']['V'])))
                    elif el['sec'] == base_sec:
                        max_M_base = max(max_M_base, np.max(np.abs(el['internal']['M'])))
                        max_V_base = max(max_V_base, np.max(np.abs(el['internal']['V'])))
            
            for st_res in struts_results_placeholder:
                el = final_elements[st_res['idx']]
                st_res['N'] = abs(el['internal']['N'])
                
            sys_data = {
                'L_tot': L_tot,
                'angle': angle_deg,
                'W': "Variable",
                'ld_dir': "Variable",
                'inc_sec': inc_sec,
                'base_sec': base_sec,
                'max_M_inc': max_M_inc,
                'max_V_inc': max_V_inc,
                'max_M_base': max_M_base,
                'max_V_base': max_V_base,
                'struts_res': struts_results_placeholder,
                'img_bytes': img_buf
            }
            
            docx_out = generate_inclined_report(sys_data)
            
            st.success("✅ Analysis Complete!")
            st.download_button("⬇️ Download Inclined System Calculation Sheet", 
                               data=docx_out.getvalue(), 
                               file_name="Inclined_System_Report.docx", 
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
