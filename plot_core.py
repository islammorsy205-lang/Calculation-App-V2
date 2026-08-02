# plot_core.py

import io
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
from math_solver import solve_beam_advanced, fmt_name

def style_axes(ax, tbg):
    text_color = '#666666'
    ax.tick_params(axis='both', which='major', labelsize=8, colors=text_color)
    for spine in ax.spines.values(): 
        spine.set_color('#A0A0A0')
        spine.set_linewidth(1.0)
    ax.grid(True, alpha=0.3, color='#CCCCCC')
    if tbg: 
        ax.patch.set_alpha(0.0)
    return text_color

def draw_system_sketch(L_total, supports_x, loads, transparent_bg=False):
    fig, ax = plt.subplots(figsize=(10, 3.5))
    text_color = style_axes(ax, transparent_bg)
    if not transparent_bg: fig.patch.set_facecolor('white')
    else: fig.patch.set_alpha(0.0)
        
    beam_y = 0.5
    ax.plot([0, L_total], [beam_y, beam_y], color='#555555', linewidth=4)
    
    for sx in supports_x:
        ax.add_patch(patches.Polygon([[sx-0.075, beam_y-0.15], [sx+0.075, beam_y-0.15], [sx, beam_y]], closed=True, fill=False, edgecolor='#00FF00', linewidth=1.5))
        ax.plot([sx, sx], [0, beam_y-0.15], color='#3399FF', linewidth=0.8, linestyle='--')
        
    ax.plot([0, 0], [0, beam_y], color='#3399FF', linewidth=0.8, linestyle='--')
    ax.plot([L_total, L_total], [0, beam_y], color='#3399FF', linewidth=0.8, linestyle='--')
    ax.plot([0, L_total], [0.1, 0.1], color='#3399FF', linewidth=1)
    ax.plot([0, L_total], [-0.4, -0.4], color='#3399FF', linewidth=1)
    
    pts = sorted(list(set([0] + list(supports_x) + [L_total])))
    for i in range(len(pts)-1):
        mid = (pts[i] + pts[i+1]) / 2
        dist = pts[i+1] - pts[i]
        if dist > 0.01:
            ax.text(mid, 0.15, f"L = {dist:.2f}", ha='center', fontsize=9, color=text_color, fontweight='normal', fontname='Arial')
            ax.plot([pts[i], pts[i]], [0.05, 0.15], color='#3399FF', linewidth=1)
            ax.plot([pts[i+1], pts[i+1]], [0.05, 0.15], color='#3399FF', linewidth=1)
            
    ax.text(L_total/2, -0.35, f"Beam Length = {L_total:.2f} m", ha='center', fontsize=10, color=text_color, fontweight='normal', fontname='Arial')

    max_w = max([max(ld.get('w1', 0), ld.get('w2', 0)) for ld in loads if ld['type'] in ['linear', 'Trapezoidal']] + [ld.get('p', 0) for ld in loads if ld['type'] == 'point'] + [1])
    scale_h = 1.0
    
    for idx, ld in enumerate(loads):
        if ld['type'] in ['linear', 'Trapezoidal']:
            h1 = beam_y + (ld['w1'] / max_w) * scale_h
            h2 = beam_y + (ld['w2'] / max_w) * scale_h
            ax.add_patch(patches.Polygon([[ld['x1'], beam_y], [ld['x1'], h1], [ld['x2'], h2], [ld['x2'], beam_y]], closed=True, fill=False, hatch='||', edgecolor='blue', linewidth=1))
            ax.plot([ld['x1'], ld['x2']], [h1, h2], color='blue', linewidth=1.5)
            ax.text((ld['x1']+ld['x2'])/2, max(h1, h2) + 0.1, f"Load {idx+1}", ha='center', fontsize=9, color='black', fontweight='normal', fontname='Arial')
            ax.plot([ld['x1'], ld['x2']], [beam_y + scale_h + 0.5, beam_y + scale_h + 0.5], color='#3399FF', linewidth=0.8)
            ax.plot([ld['x1'], ld['x1']], [beam_y, beam_y + scale_h + 0.55], color='#3399FF', linewidth=0.5, linestyle='--')
            ax.plot([ld['x2'], ld['x2']], [beam_y, beam_y + scale_h + 0.55], color='#3399FF', linewidth=0.5, linestyle='--')
            ax.text((ld['x1']+ld['x2'])/2, beam_y + scale_h + 0.55, f"D{idx+1}={ld['x2']-ld['x1']:.2f}", ha='center', fontsize=8, color=text_color, fontweight='normal', fontname='Arial')
        elif ld['type'] == 'point':
            arr_y = beam_y + scale_h + 0.3
            ax.arrow(ld['x'], arr_y, 0, -0.3, head_width=0.104, head_length=0.13, fc='black', ec='black', zorder=5)
            ax.text(ld['x'], arr_y + 0.1, f"P = {ld['p']:.1f} kN\n@ x={ld['x']:.2f}m", ha='center', fontsize=9, color='black', fontweight='normal', fontname='Arial')

    ax.set_xlim(-0.5, L_total + 0.5)
    ax.set_ylim(-0.8, beam_y + scale_h + 1.0)
    ax.axis('off')
    
    img_stream = io.BytesIO()
    fig.savefig(img_stream, format='png', bbox_inches='tight', dpi=300, transparent=transparent_bg)
    plt.close(fig)
    return img_stream.getvalue()

def generate_acrow_diagrams(section_name, L_total, supports_x, loads, E, I, Mall, Qall, Rall=None, transparent_bg=False):
    nodes, V, M, D, R = solve_beam_advanced(L_total, supports_x, loads, E, I)
    fig = plt.figure(figsize=(8.5, 10.5))
    if transparent_bg: fig.patch.set_alpha(0.0)
    else: fig.patch.set_facecolor('#FAFAFA')
        
    gs = gridspec.GridSpec(4, 2, width_ratios=[5, 3.4], hspace=0.6, wspace=0.3)
    line_col, beam_col = '#E10000', '#0033CC'
    
    abs_max_D = max(abs(max(D)), abs(min(D)))
    max_D_x = nodes[np.argmax(np.abs(D))]
    is_generic_timber = "Timber" in section_name and "H20" not in section_name
    
    if max_D_x < supports_x[0]: 
        L_mm = int(round(supports_x[0] * 1000))
        all_def = L_mm / 200.0
        def_txt = f"L/200 = {L_mm}/200 = {all_def:.2f} mm"
    elif max_D_x > supports_x[-1]: 
        L_mm = int(round((L_total - supports_x[-1]) * 1000))
        all_def = L_mm / 200.0
        def_txt = f"L/200 = {L_mm}/200 = {all_def:.2f} mm"
    else:
        for i in range(len(supports_x)-1):
            if supports_x[i] <= max_D_x <= supports_x[i+1]:
                L_mm = int(round((supports_x[i+1] - supports_x[i]) * 1000))
                all_def = L_mm * 0.003 if is_generic_timber else L_mm / 400.0
                def_txt = f"0.003L = 0.003 x {L_mm} = {all_def:.2f} mm" if is_generic_timber else f"L/400 = {L_mm}/400 = {all_def:.2f} mm"
                break
    
    def annotate_extrema_and_supports(ax, x, y, is_moment=False, invert_y=False):
        idx_max, idx_min = np.argmax(y), np.argmin(y)
        y_range = max(y) - min(y)
        if y_range == 0: y_range = 1
        offset = y_range * 0.12  
        
        va_max = 'bottom' if y[idx_max] >= 0 else 'top'
        dy_max = offset if y[idx_max] >= 0 else -offset
        if invert_y: 
            va_max = 'top' if y[idx_max] >= 0 else 'bottom'
            dy_max = -offset if y[idx_max] >= 0 else offset
            
        ax.text(x[idx_max], y[idx_max] + dy_max, f"{y[idx_max]:.2f}", color='black', fontweight='normal', fontname='Arial', ha='center', va=va_max, fontsize=7.5)
        ax.plot(x[idx_max], y[idx_max], 'ko', markersize=3)
        
        va_min = 'top' if y[idx_min] <= 0 else 'bottom'
        dy_min = -offset if y[idx_min] <= 0 else offset
        if invert_y: 
            va_min = 'bottom' if y[idx_min] <= 0 else 'top'
            dy_min = offset if y[idx_min] <= 0 else -offset
            
        ax.text(x[idx_min], y[idx_min] + dy_min, f"{y[idx_min]:.2f}", color='black', fontweight='normal', fontname='Arial', ha='center', va=va_min, fontsize=7.5)
        ax.plot(x[idx_min], y[idx_min], 'ko', markersize=3)
        
        for sx in supports_x:
            idx = np.argmin(np.abs(x - sx))
            val = y[idx]
            ax.plot(sx, 0, marker='^', markersize=8, color='gray', alpha=0.5)
            if abs(val) > max(abs(max(y)), abs(min(y))) * 0.05 and idx not in [idx_max, idx_min]:
                va_sup = 'bottom' if val >= 0 else 'top'
                dy_sup = offset * 0.6 if val >= 0 else -offset * 0.6
                if invert_y: 
                    va_sup = 'top' if val >= 0 else 'bottom'
                    dy_sup = -offset * 0.6 if val >= 0 else offset * 0.6
                ax.text(sx, val + dy_sup, f"{val:.2f}", color='#3399FF', fontsize=7.5, ha='center', va=va_sup, fontweight='normal', fontname='Arial')
                
        ax.margins(y=0.25)
        style_axes(ax, transparent_bg)
        return y[idx_max], x[idx_max], y[idx_min], x[idx_min]
        
    def add_side_table(row_idx, title, max_v, max_x, min_v, min_x, allow_val=None):
        ax_t = fig.add_subplot(gs[row_idx, 1])
        ax_t.axis('off')
        cell_text = [["Max =", f"{max_v:.2f}", f"{max_x:.2f}"], ["Min =", f"{min_v:.2f}", f"{min_x:.2f}"]]
        if allow_val is not None:
            act_val = max(abs(max_v), abs(min_v))
            is_safe = act_val <= allow_val
            s_icon = "SAFE" if is_safe else "UNSAFE"
            cell_text.append(["Allow =", f"{allow_val:.2f}", s_icon])
        else: 
            cell_text.append(["Allow =", "-", "-"])
            
        tab = ax_t.table(cellText=cell_text, colLabels=[title, "Value", "X, m"], loc='center', cellLoc='center', colLoc='center', colWidths=[0.40, 0.25, 0.35])
        tab.auto_set_font_size(False)
        tab.set_fontsize(10)
        tab.scale(1.0, 2.0)
        
        if allow_val is not None:
            is_safe = max(abs(max_v), abs(min_v)) <= allow_val
            color = "#198754" if is_safe else "#dc3545" 
            cell = tab[3, 2]
            cell.get_text().set_color(color)
            cell.get_text().set_fontweight('bold')
            
        for (r, c), cell_obj in tab.get_celld().items():
            if not (allow_val is not None and r == 3 and c == 2): 
                cell_obj.set_text_props(color='#666666' if transparent_bg else 'black')
            cell_obj.set_edgecolor('#A0A0A0')
            cell_obj.set_text_props(ha='center', va='center')
            if transparent_bg: 
                cell_obj.set_facecolor('none')

    ax_M = fig.add_subplot(gs[0, 0])
    ax_M.plot([0, L_total], [0, 0], color=beam_col, linewidth=2)
    ax_M.plot(nodes, M, color=line_col, linewidth=1.5)
    ax_M.invert_yaxis() 
    max_M, mx_M, min_M, mnx_M = annotate_extrema_and_supports(ax_M, nodes, M, is_moment=True, invert_y=True)
    add_side_table(0, "Moment", max_M, mx_M, min_M, mnx_M, allow_val=Mall)

    ax_V = fig.add_subplot(gs[1, 0])
    ax_V.plot([0, L_total], [0, 0], color=beam_col, linewidth=2)
    ax_V.plot(nodes, V, color=line_col, linewidth=1.5)
    max_V, mx_V, min_V, mnx_V = annotate_extrema_and_supports(ax_V, nodes, V)
    add_side_table(1, "Shear", max_V, mx_V, min_V, mnx_V, allow_val=Qall)

    ax_D = fig.add_subplot(gs[2, 0])
    ax_D.plot([0, L_total], [0, 0], color=beam_col, linewidth=2)
    ax_D.plot(nodes, D, color=line_col, linewidth=1.5)
    max_D, mx_D, min_D, mnx_D = annotate_extrema_and_supports(ax_D, nodes, D)
    add_side_table(2, "Deflection", max_D, mx_D, min_D, mnx_D, allow_val=all_def)

    ax_R = fig.add_subplot(gs[3, 0])
    style_axes(ax_R, transparent_bg)
    ax_R.plot([0, L_total], [0, 0], color=beam_col, linewidth=2)
    for i, sx in enumerate(supports_x):
        ax_R.plot([sx, sx], [0, R[i]], color=line_col, linewidth=3)
        ax_R.text(sx, R[i] + max(R)*0.1, f"{R[i]:.2f}", fontweight='normal', fontname='Arial', ha='center', va='bottom', fontsize=9, color='black')
        ax_R.plot(sx, 0, marker='^', markersize=8, color='gray', alpha=0.5)
        
    ax_R.margins(y=0.25)
    
    max_R = np.max(R) if len(R) > 0 else 0
    min_R = np.min(R) if len(R) > 0 else 0
    max_R_x = supports_x[np.argmax(R)] if len(R) > 0 else 0
    min_R_x = supports_x[np.argmin(R)] if len(R) > 0 else 0
    add_side_table(3, "Reaction", max_R, max_R_x, min_R, min_R_x, allow_val=Rall)

    img_stream = io.BytesIO()
    fig.savefig(img_stream, format='png', bbox_inches='tight', dpi=300, transparent=transparent_bg)
    plt.close(fig)
    
    abs_max_M = max(abs(max_M), abs(min_M))
    abs_max_V = max(abs(max_V), abs(min_V))
    return img_stream.getvalue(), abs_max_M, abs_max_V, abs_max_D, np.max(R) if len(R)>0 else 0, all_def, def_txt

# =========================================================================
# دوال السترونج باك والـ SAP2000 (بدون Fill، دعامة 45 حقيقية، تهشير واسع، نصوص Arial)
# =========================================================================

def get_major_nodes(nodes, elements):
    connected_mems = [set() for _ in range(len(nodes))]
    node_degrees = [0] * len(nodes)
    for el in elements:
        if el['mem'] != 'Tie':
            n1, n2 = el['n1'], el['n2']
            connected_mems[n1].add(el['mem'])
            connected_mems[n2].add(el['mem'])
            node_degrees[n1] += 1
            node_degrees[n2] += 1

    major_nodes = set()
    for i, n in enumerate(nodes):
        if n[2] or n[3]: major_nodes.add(i) 
        elif node_degrees[i] == 1: major_nodes.add(i) 
        elif len(connected_mems[i]) > 1: major_nodes.add(i) 
        
    for el in elements:
        if el['type'] == 'truss' and el['mem'] == 'D':
            major_nodes.add(el['n1'])
            major_nodes.add(el['n2'])
            
    return major_nodes

def add_val_text(ax, px, py, val, color, drawn_texts):
    if abs(val) < 0.1: return
    for (dx, dy) in drawn_texts:
        if abs(dx - px) < 0.2 and abs(dy - py) < 0.2: return 
    ax.text(px, py, f"{val:.2f}", color=color, fontsize=7, ha='center', va='center', fontname='Arial', fontweight='normal', bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.3))
    drawn_texts.append((px, py))

def draw_diagram_with_hatching(ax, x1, y1, c, s, L, vals, sc, color, is_moment=False):
    num_pts = max(20, int(L / 0.05))
    dense_xs = np.linspace(0, L, num_pts) 
    dense_val = np.interp(dense_xs, np.linspace(0, L, len(vals)), vals)
    
    if is_moment:
        px_out = x1 + dense_xs*c + dense_val*(-s)*sc
        py_out = y1 + dense_xs*s - dense_val*c*sc
    else:
        px_out = x1 + dense_xs*c - dense_val*(-s)*sc
        py_out = y1 + dense_xs*s + dense_val*c*sc
        
    bx_out = x1 + dense_xs*c
    by_out = y1 + dense_xs*s
    
    poly_pts = [[bx_out[i], by_out[i]] for i in range(len(dense_xs))] + [[px_out[i], py_out[i]] for i in range(len(dense_xs)-1, -1, -1)]
    ax.add_patch(patches.Polygon(poly_pts, closed=True, fill=False, edgecolor=color, lw=1.2))
    
    num_hatches = max(3, int(L / 0.4))
    hatch_xs = np.linspace(0, L, num_hatches)
    hatch_val = np.interp(hatch_xs, np.linspace(0, L, len(vals)), vals)
    
    if is_moment:
        px_h = x1 + hatch_xs*c + hatch_val*(-s)*sc
        py_h = y1 + hatch_xs*s - hatch_val*c*sc
    else:
        px_h = x1 + hatch_xs*c - hatch_val*(-s)*sc
        py_h = y1 + hatch_xs*s + hatch_val*c*sc
        
    bx_h = x1 + hatch_xs*c
    by_h = y1 + hatch_xs*s
    
    for i in range(len(hatch_xs)):
        ax.plot([bx_h[i], px_h[i]], [by_h[i], py_h[i]], color=color, lw=0.6, alpha=0.5)
        
    return px_out, py_out

def draw_truss_axial(ax, x1, y1, x2, y2, N, sc, color):
    L = np.hypot(x2-x1, y2-y1)
    c, s = (x2-x1)/L, (y2-y1)/L
    nx, ny = -s, c
    
    px1, py1 = x1 + N*nx*sc, y1 + N*ny*sc
    px2, py2 = x2 + N*nx*sc, y2 + N*ny*sc
    
    ax.add_patch(patches.Polygon([[x1,y1], [px1,py1], [px2,py2], [x2,y2]], closed=True, fill=False, edgecolor=color, lw=1.2))
    
    num_hatches = max(3, int(L / 0.4))
    h_xs = np.linspace(x1, x2, num_hatches)
    h_ys = np.linspace(y1, y2, num_hatches)
    for i in range(num_hatches):
        ax.plot([h_xs[i], h_xs[i] + N*nx*sc], [h_ys[i], h_ys[i] + N*ny*sc], color=color, lw=0.6, alpha=0.5)
        
    angle = np.degrees(np.arctan2(y2-y1, x2-x1))
    if angle < -90: angle += 180
    elif angle > 90: angle -= 180
    
    mid_x = (x1 + x2)/2 + (N*nx*sc)/2
    mid_y = (y1 + y2)/2 + (N*ny*sc)/2
    ax.text(mid_x, mid_y, f"{abs(N):.2f}", color=color, fontsize=7, ha='center', va='center', rotation=angle, fontname='Arial', fontweight='normal', bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.3))

def draw_sap_base_frame(ax, nodes, elements, invert_y_axis=False):
    valid_nodes = [n for n in nodes if not (n[0] < -0.1 and n[1] < -0.1)]
    if not valid_nodes: valid_nodes = nodes
    
    ax.set_xlim(min([n[0] for n in valid_nodes]) - 1.5, max([n[0] for n in valid_nodes]) + 1.5)
    ax.set_ylim(-1.5 if any(n[1] < 0 for n in valid_nodes) else -0.5, max([n[1] for n in valid_nodes]) + 1.5)
    ax.set_aspect('equal', adjustable='datalim') 
    ax.axis('off')
    if invert_y_axis: ax.invert_yaxis()
        
    drawn_v, drawn_h = False, False
    major_nodes = get_major_nodes(nodes, elements)
    
    for el in elements:
        if el['mem'] == 'Tie': continue 
            
        x1, y1 = nodes[el['n1']][:2]
        x2, y2 = nodes[el['n2']][:2]
        ax.plot([x1, x2], [y1, y2], color='blue', lw=1.0, zorder=1)
        
        if el['type'] == 'truss':
            angle = np.degrees(np.arctan2(y2-y1, x2-x1))
            if angle < -90: angle += 180
            elif angle > 90: angle -= 180
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, el['sec'].split()[0], color='black', fontsize=7, rotation=angle, ha='center', va='bottom', fontname='Arial', fontweight='normal')
            
        elif el['type'] == 'frame':
            if el['mem'] == 'V' and not drawn_v:
                v_ys = [n[1] for n in nodes if abs(n[0]) < 1e-3]
                mid_y = (min(v_ys)+max(v_ys))/2 if v_ys else (y1+y2)/2
                ax.text(-0.25, mid_y, el['sec'], color='black', fontsize=8, ha='center', va='center', rotation=90, fontname='Arial', fontweight='normal')
                drawn_v = True
            elif el['mem'] == 'H' and not drawn_h:
                h_xs = [n[0] for n in nodes if abs(n[1]) < 1e-3]
                mid_x = (min(h_xs)+max(h_xs))/2 if h_xs else (x1+x2)/2
                ax.text(mid_x, -0.25 if not invert_y_axis else 0.25, el['sec'], color='black', fontsize=8, ha='center', va='center', fontname='Arial', fontweight='normal')
                drawn_h = True
                
    for idx in major_nodes:
        n = nodes[idx]
        if not (n[2] or n[3]): 
            ax.plot(n[0], n[1], 'o', color='blue', markersize=3.5, zorder=3)
            
    for i, n in enumerate(nodes):
        if n[2] or n[3]:
            if n[0] < -0.1 and n[1] < -0.1: continue 

            dy = -0.15 if not invert_y_axis else 0.15
            y_base = n[1]
            
            if abs(n[0]) < 1e-3 and abs(n[1]) < 1e-3:
                theta = np.radians(-45)
                c, s = np.cos(theta), np.sin(theta)
                def rot(px, py): return px*c - py*s, px*s + py*c
                p1, p2, p3 = rot(0,0), rot(-0.1,-0.15), rot(0.1,-0.15)
                ax.add_patch(patches.Polygon([[p1[0]+n[0], p1[1]+n[1]], [p2[0]+n[0], p2[1]+n[1]], [p3[0]+n[0], p3[1]+n[1]]], fill=False, edgecolor='#00FF00', lw=1.5))
                l1, l2 = rot(-0.15,-0.15), rot(0.15,-0.15)
                ax.plot([l1[0]+n[0], l2[0]+n[0]], [l1[1]+n[1], l2[1]+n[1]], color='#00FF00', lw=1.5)
                continue

            if n[2] and n[3]: 
                ax.add_patch(patches.Polygon([[n[0], y_base], [n[0]-0.1, y_base+dy], [n[0]+0.1, y_base+dy]], fill=False, edgecolor='#00FF00', lw=1.5))
                ax.plot([n[0]-0.15, n[0]+0.15], [y_base+dy, y_base+dy], color='#00FF00', lw=1.5)
            elif not n[2] and n[3]: 
                ax.add_patch(patches.Polygon([[n[0], y_base], [n[0]-0.075, y_base+dy*0.8], [n[0]+0.075, y_base+dy*0.8]], fill=False, edgecolor='#00FF00', lw=1.5))
                ax.add_patch(plt.Circle((n[0]-0.04, y_base+dy*0.9), abs(dy*0.1), color='#00FF00', fill=False, lw=1.5))
                ax.add_patch(plt.Circle((n[0]+0.04, y_base+dy*0.9), abs(dy*0.1), color='#00FF00', fill=False, lw=1.5))
                ax.plot([n[0]-0.15, n[0]+0.15], [y_base+dy, y_base+dy], color='#00FF00', lw=1.5)

def draw_sap_loads_single(nodes, elements, custom_loads=None, dist_loads=None, scale_factor=1.0):
    fig, ax = plt.subplots(figsize=(6, 8))
    fig.patch.set_facecolor('white')
    draw_sap_base_frame(ax, nodes, elements)
    major_nodes = get_major_nodes(nodes, elements)
    
    y_nodes_v = sorted(list(set([round(nodes[idx][1],3) for idx in major_nodes if nodes[idx][0] == 0])))
    for y in y_nodes_v:
        if y > 0:
            ax.plot([-0.2, 0], [y, y], color='black', lw=0.5)
            ax.text(-0.3, y, f"{y:.1f}", color='black', ha='right', va='center', fontsize=7, fontname='Arial', fontweight='normal')
            
    x_nodes_h = sorted(list(set([round(nodes[idx][0],3) for idx in major_nodes if nodes[idx][1] == 0])))
    for x in x_nodes_h:
        if x > 0:
            ax.plot([x, x], [-0.2, 0], color='black', lw=0.5)
            ax.text(x, -0.3, f"{x:.2f}", color='black', ha='center', va='top', fontsize=7, fontname='Arial', fontweight='normal')
            
    if dist_loads:
        sc = (1.0 / max([max(abs(dl['w1']), abs(dl['w2'])) for dl in dist_loads] + [1])) * scale_factor
        for dl in dist_loads:
            y1, y2 = dl['y1'], dl['y2']
            w1, w2 = dl['w1'], dl['w2']
            w_dir = dl.get('dir', 'right')
            if w1 > 0 or w2 > 0:
                hw1, hw2 = w1*sc, w2*sc
                if w_dir == 'right':
                    ax.add_patch(patches.Polygon([[0, y1], [-hw1, y1], [-hw2, y2], [0, y2]], closed=True, fill=False, edgecolor='blue', lw=0.8))
                    for y_arr in np.linspace(y1, y2, 5):
                        w_arr = w1 + (w2-w1)*(y_arr-y1)/(y2-y1) if y2 > y1 else w1
                        ax.arrow(-w_arr*sc, y_arr, w_arr*sc - 0.05, 0, head_width=0.104, head_length=0.065, fc='blue', ec='blue', lw=0.5)
                    ax.text(-hw1, y1, f"{w1:.1f}", color='black', ha='right', va='bottom', fontsize=7, fontname='Arial', fontweight='normal')
                    if abs(y2 - y1) > 0.1: ax.text(-hw2, y2, f"{w2:.1f}", color='black', ha='right', va='bottom', fontsize=7, fontname='Arial', fontweight='normal')
                else:
                    ax.add_patch(patches.Polygon([[0, y1], [hw1, y1], [hw2, y2], [0, y2]], closed=True, fill=False, edgecolor='blue', lw=0.8))
                    for y_arr in np.linspace(y1, y2, 5):
                        w_arr = w1 + (w2-w1)*(y_arr-y1)/(y2-y1) if y2 > y1 else w1
                        ax.arrow(w_arr*sc, y_arr, -w_arr*sc + 0.05, 0, head_width=0.104, head_length=0.065, fc='blue', ec='blue', lw=0.5)
                    ax.text(hw1, y1, f"{w1:.1f}", color='black', ha='left', va='bottom', fontsize=7, fontname='Arial', fontweight='normal')
                    if abs(y2 - y1) > 0.1: ax.text(hw2, y2, f"{w2:.1f}", color='black', ha='left', va='bottom', fontsize=7, fontname='Arial', fontweight='normal')

    if custom_loads:
        for ld in custom_loads:
            if ld.get('is_moment', False):
                ax.plot(0, ld['y'], marker='$\circlearrowleft$', markersize=15, color='black')
                ax.text(-0.3, ld['y'], f"{abs(ld['p']):.2f}", color='black', ha='right', va='center', fontsize=7, fontname='Arial', fontweight='normal')
            else:
                arr_x_start = -0.6 if ld['p'] > 0 else 0.6
                arr_len = 0.55 if ld['p'] > 0 else -0.55
                ax.arrow(arr_x_start, ld['y'], arr_len, 0, head_width=0.104, head_length=0.065, fc='black', ec='black', lw=1.0)
                ax.text(arr_x_start - 0.1 if ld['p'] > 0 else arr_x_start + 0.1, ld['y'], f"{abs(ld['p']):.2f}", color='black', ha='right' if ld['p'] > 0 else 'left', va='center', fontsize=7, fontname='Arial', fontweight='normal')
                
    ax.autoscale_view()
    ax.margins(0.25)
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    return img.getvalue()

def draw_sap_axial_single(nodes, elements, scale_factor=1.0):
    fig, ax = plt.subplots(figsize=(6, 8))
    fig.patch.set_facecolor('white')
    draw_sap_base_frame(ax, nodes, elements)
    
    max_n = max([abs(el['N_ax']) for el in elements if el['type']=='truss'] + [abs(el['N'].mean()) for el in elements if el['type']=='frame'] + [1e-5])
    sc_n = (1.0 / max_n) * scale_factor
    major_nodes = get_major_nodes(nodes, elements)
    drawn_texts = []
    
    for el in elements:
        x1, y1 = nodes[el['n1']][:2]
        x2, y2 = nodes[el['n2']][:2]
        c, s = el['c'], el['s']
        if el['mem'] == 'Tie': continue
            
        if el['type'] == 'truss':
            N = el['N_ax']
            color = 'blue' if N < 0 else 'red'
            draw_truss_axial(ax, x1, y1, x2, y2, N, sc_n, color)
            
        elif el['type'] == 'frame':
            N_arr = el['N']
            color = 'blue' if N_arr.mean() < 0 else 'red'
            px, py = draw_diagram_with_hatching(ax, x1, y1, c, s, el['L'], N_arr, sc_n, color, is_moment=False)
            
            if el['n1'] in major_nodes: add_val_text(ax, px[0], py[0], N_arr[0], color, drawn_texts)
            if el['n2'] in major_nodes: add_val_text(ax, px[-1], py[-1], N_arr[-1], color, drawn_texts)
                
    ax.autoscale_view()
    ax.margins(0.25)
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    return img.getvalue()

def draw_sap_shear_single(nodes, elements, scale_factor=1.0):
    fig, ax = plt.subplots(figsize=(6, 8))
    fig.patch.set_facecolor('white')
    draw_sap_base_frame(ax, nodes, elements)
    
    max_v = max([max(abs(el['V'])) for el in elements if el['type']=='frame'] + [1e-5])
    sc_v = (1.0 / max_v) * scale_factor
    major_nodes = get_major_nodes(nodes, elements)
    drawn_texts = []
    
    for el in elements:
        if el['type'] == 'truss':
            N = el['N_ax']
            x1, y1 = nodes[el['n1']][:2]
            x2, y2 = nodes[el['n2']][:2]
            color = 'blue' if N < 0 else 'red'
            add_val_text(ax, (x1+x2)/2, (y1+y2)/2, N, color, drawn_texts)
            
        elif el['type'] == 'frame':
            x1, y1 = nodes[el['n1']][:2]
            c, s = el['c'], el['s']
            color = 'blue' 
            px, py = draw_diagram_with_hatching(ax, x1, y1, c, s, el['L'], el['V'], sc_v, color, is_moment=False)
            
            if el['n1'] in major_nodes: add_val_text(ax, px[0], py[0], el['V'][0], 'blue' if el['V'][0]>0 else 'red', drawn_texts)
            if el['n2'] in major_nodes: add_val_text(ax, px[-1], py[-1], el['V'][-1], 'blue' if el['V'][-1]>0 else 'red', drawn_texts)
                
    ax.autoscale_view()
    ax.margins(0.25)
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    return img.getvalue()

def draw_sap_moment_single(nodes, elements, scale_factor=1.0):
    fig, ax = plt.subplots(figsize=(6, 8))
    fig.patch.set_facecolor('white')
    draw_sap_base_frame(ax, nodes, elements, invert_y_axis=False)
    
    max_m = max([max(abs(el['M'])) for el in elements if el['type']=='frame'] + [1e-5])
    sc_m = (1.0 / max_m) * scale_factor
    major_nodes = get_major_nodes(nodes, elements)
    drawn_texts = []
    
    for el in elements:
        if el['type'] == 'truss':
            N = el['N_ax']
            x1, y1 = nodes[el['n1']][:2]
            x2, y2 = nodes[el['n2']][:2]
            color = 'blue' if N < 0 else 'red'
            add_val_text(ax, (x1+x2)/2, (y1+y2)/2, N, color, drawn_texts)
            
        elif el['type'] == 'frame':
            x1, y1 = nodes[el['n1']][:2]
            c, s = el['c'], el['s']
            color = 'blue'
            px, py = draw_diagram_with_hatching(ax, x1, y1, c, s, el['L'], el['M'], sc_m, color, is_moment=True)
            
            if el['n1'] in major_nodes: add_val_text(ax, px[0], py[0], el['M'][0], 'blue' if el['M'][0]<0 else 'red', drawn_texts)
            if el['n2'] in major_nodes: add_val_text(ax, px[-1], py[-1], el['M'][-1], 'blue' if el['M'][-1]<0 else 'red', drawn_texts)
                
    ax.autoscale_view()
    ax.margins(0.25)
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    return img.getvalue()

def draw_sap_rxn_single(nodes, elements, R_total, corner_sup="Hinged"):
    fig, ax = plt.subplots(figsize=(6, 8))
    fig.patch.set_facecolor('white')
    draw_sap_base_frame(ax, nodes, elements)
    
    for i, n in enumerate(nodes):
        # =========================================================================
        # التعديل: تدوير الركيزة (Corner) واستخراج الـ Axial/Shear بناءً على حالة الـ Support
        # =========================================================================
        if abs(n[0]) < 1e-3 and abs(n[1]) < 1e-3:
            c, s = 0.70710678, 0.70710678
            if corner_sup == "Hinged":
                rx, ry = R_total[3*i], R_total[3*i+1]
                R_axial = rx * c + ry * s
                R_shear = -rx * s + ry * c
            else:
                tie_el = next((e for e in elements if e['mem'] == 'Tie'), None)
                R_axial = tie_el['N_ax'] if tie_el else 0.0
                R_shear = 0.0
            
            if abs(R_axial) > 0.1:
                nx, ny = -c, -s
                mag = abs(R_axial)
                sign = np.sign(R_axial) if R_axial != 0 else 1
                tail_x = -0.25 * nx * sign
                tail_y = -0.25 * ny * sign
                ax.annotate("", xy=(0, 0), xytext=(tail_x, tail_y), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
                ax.text(tail_x * 1.5, tail_y * 1.5, f"{mag:.2f}", color='black', rotation=45, ha='center', va='center', fontsize=8, fontname='Arial')
                
            if abs(R_shear) > 0.1:
                nx, ny = s, -c
                mag = abs(R_shear)
                sign = np.sign(R_shear) if R_shear != 0 else 1
                tail_x = -0.25 * nx * sign
                tail_y = -0.25 * ny * sign
                ax.annotate("", xy=(0, 0), xytext=(tail_x, tail_y), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
                ax.text(tail_x * 1.5, tail_y * 1.5, f"{mag:.2f}", color='black', rotation=-45, ha='center', va='center', fontsize=8, fontname='Arial')
            continue

        rx, ry = R_total[3*i], R_total[3*i+1]
        if abs(rx) > 0.1 or abs(ry) > 0.1:
            if abs(ry) > 0.1:
                dy_arr = -0.25 if ry > 0 else 0.25
                text_dy = -0.35 if ry > 0 else 0.35
                ax.annotate("", xy=(n[0], n[1]), xytext=(n[0], n[1]+dy_arr), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
                ax.text(n[0], n[1]+text_dy, f"{abs(ry):.2f}", color='black', ha='center', va='top' if ry>0 else 'bottom', fontsize=8, fontname='Arial', fontweight='normal')
            if abs(rx) > 0.1:
                dx_arr = -0.25 if rx > 0 else 0.25
                text_dx = -0.35 if rx > 0 else 0.35
                ax.annotate("", xy=(n[0], n[1]), xytext=(n[0]+dx_arr, n[1]), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
                ax.text(n[0]+text_dx, n[1], f"{abs(rx):.2f}", color='black', ha='right' if rx>0 else 'left', va='center', fontsize=8, fontname='Arial', fontweight='normal')
                
    ax.autoscale_view()
    ax.margins(0.25)
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    return img.getvalue()

def draw_dim(ax, x1, y1, x2, y2, text, is_vertical=False, fontsize=6, color='#AAAAAA'):
    ax.plot([x1, x2], [y1, y2], color=color, lw=0.5) 
    t = 0.05 
    ax.plot([x1-t, x1+t], [y1-t, y1+t], color=color, lw=0.6)
    ax.plot([x2-t, x2+t], [y2-t, y2+t], color=color, lw=0.6)
    if is_vertical: 
        ax.text(x1 - 0.05, (y1+y2)/2, text, color=color, ha='right', va='center', fontsize=fontsize, rotation=90, fontname='Arial', fontweight='normal')
    else: 
        ax.text((x1+x2)/2, y1 - 0.05, text, color=color, ha='center', va='top', fontsize=fontsize, fontname='Arial', fontweight='normal')

def draw_tilting_diagrams(H, struts, w_dist, bkt_data=None, transparent_bg=False):
    max_x = max([st['x_base'] for st in struts] + [1.0])
    y_pts = [0] + sorted([st['y'] for st in struts]) + [H]
    x_pts = [0] + sorted(list(set([st['x_base'] for st in struts])))
    
    total_Rx, total_Ry, max_N = {}, {}, 0
    for st_c in struts:
        xb = st_c['x_base']
        if xb not in total_Rx: total_Rx[xb] = 0
        if xb not in total_Ry: total_Ry[xb] = 0

    for st_c in struts:
        y_att = st_c['y']
        x_b = st_c['x_base']
        N_val = st_c['N']
        L = np.sqrt(x_b**2 + y_att**2)
        max_N = max(max_N, abs(N_val))
        if L > 0:
            Rx = abs(N_val * (x_b / L))
            Ry = abs(N_val * (y_att / L))
            total_Rx[x_b] += Rx
            total_Ry[x_b] += Ry
            
    def draw_roller(ax, x, y):
        dy = -0.15 
        ax.add_patch(patches.Polygon([[x, 0], [x-0.075, dy*0.8], [x+0.075, dy*0.8]], fill=False, edgecolor='#00FF00', lw=1.5))
        ax.add_patch(plt.Circle((x-0.04, dy*0.9), abs(dy*0.1), color='#00FF00', fill=False, lw=1.5))
        ax.add_patch(plt.Circle((x+0.04, dy*0.9), abs(dy*0.1), color='#00FF00', fill=False, lw=1.5))
        ax.plot([x-0.15, x+0.15], [dy, dy], color='#00FF00', lw=1.5)
        
    def draw_hinge(ax, x, y):
        dy = -0.15
        ax.add_patch(patches.Polygon([[x, 0], [x-0.1, dy], [x+0.1, dy]], fill=False, edgecolor='#00FF00', lw=1.5))
        ax.plot([x-0.15, x+0.15], [dy, dy], color='#00FF00', lw=1.5)

    def add_strut_text(ax, x_b, y_att, text, color='#555555', fontsize=7, offset_dist=0.12):
        angle = np.degrees(np.arctan2(-y_att, x_b))
        if angle < -90: angle += 180
        elif angle > 90: angle -= 180
        L = np.sqrt(x_b**2 + y_att**2)
        if L > 0:
            nx, ny = -y_att/L, -x_b/L
            ax.text(x_b/2 + nx*offset_dist, y_att/2 + ny*offset_dist, text, rotation=angle, color=color, ha='center', va='center', fontsize=fontsize, fontname='Arial', fontweight='normal')

    def draw_bracket(ax, show_ll=True, show_forces=True):
        if bkt_data and bkt_data.get('active'):
            yt, yb, L1, LL = bkt_data['y_top'], bkt_data['y_bot'], bkt_data['L1'], bkt_data['LL']
            ax.plot([0, L1], [yt, yt], color='#008080', lw=1.5)
            ax.plot([L1, 0], [yt, yb], color='#008080', lw=1.5)
            if show_ll:
                ax.plot([0, L1], [yt + 0.3, yt + 0.3], color='#0055FF', lw=1.0)
                ax.plot([L1, L1], [yt, yt + 0.3], color='#0055FF', lw=1.0)
                for x_arr in np.arange(0, L1 + 0.01, 0.20):
                    ax.arrow(x_arr, yt + 0.3, 0, -0.25, head_width=0.104, head_length=0.065, fc='black', ec='black', lw=0.6)
                ax.text(L1/2, yt + 0.35, f"L.L = {LL} kN/m²", color='black', ha='center', va='bottom', fontsize=7, fontname='Arial', fontweight='normal')

    def setup_common_ax(ax):
        b_xmin, b_xmax = -2.5, max_x + 1.5
        if bkt_data and bkt_data.get('active'): b_xmax = max(b_xmax, bkt_data['L1'] + 1.0)
        ax.plot([b_xmin, b_xmax], [-0.8, H + 0.5], alpha=0.0)
        ax.plot([0, 0], [0, H], 'k-', lw=1.5) 
        ax.text(-0.15, H/2, 'Panel', rotation=90, color='#555555', ha='center', va='center', fontsize=7, fontname='Arial', fontweight='normal')
        draw_roller(ax, 0, 0)
        for bx in list(total_Rx.keys()):
            if any(st['x_base'] == bx and st.get('support') == 'Hinged' for st in struts): draw_hinge(ax, bx, 0)
            else: draw_roller(ax, bx, 0)
        ax.set_aspect('equal', adjustable='datalim') 
        ax.axis('off')
        
    fig1, ax1 = plt.subplots(figsize=(4.0, 6.0))
    if not transparent_bg: fig1.patch.set_facecolor('white')
    else: fig1.patch.set_alpha(0.0)
    setup_common_ax(ax1)
    
    for y in np.linspace(0, H, max(5, int(H*1.5))): ax1.arrow(-0.8, y, 0.7, 0, head_width=0.104, head_length=0.065, fc='black', ec='black', lw=0.6)
    ax1.plot([-0.8, -0.8], [0, H], 'k-', lw=1.0)
    ax1.text(-0.4, H + 0.2, f"W = {w_dist:.2f} kN/m'", color='black', ha='center', fontsize=9, fontname='Arial', fontweight='normal')
    draw_dim(ax1, -2.0, 0, -2.0, H, f"{H:.2f}m", is_vertical=True, fontsize=7)
    
    for i in range(len(y_pts)-1):
        if y_pts[i+1] - y_pts[i] > 0.05: draw_dim(ax1, -1.4, y_pts[i], -1.4, y_pts[i+1], f"{y_pts[i+1]-y_pts[i]:.2f}m", is_vertical=True)
            
    sorted_x_pts = sorted(list(total_Rx.keys()))
    if sorted_x_pts:
        draw_dim(ax1, 0, -0.4, sorted_x_pts[0], -0.4, f"{sorted_x_pts[0]:.2f}m")
        for i in range(len(sorted_x_pts)-1):
            if sorted_x_pts[i+1] - sorted_x_pts[i] > 0.05: draw_dim(ax1, sorted_x_pts[i], -0.4, sorted_x_pts[i+1], -0.4, f"{sorted_x_pts[i+1]-sorted_x_pts[i]:.2f}m")
    
    for st_c in struts:
        ax1.plot([0, st_c['x_base']], [st_c['y'], 0], '#E10000', lw=1.2)
        add_strut_text(ax1, st_c['x_base'], st_c['y'], st_c['type'].split()[0] if "No strut" not in st_c['type'] else "Invalid")
        
    draw_bracket(ax1, show_ll=True, show_forces=False)
    img1_stream = io.BytesIO()
    fig1.savefig(img1_stream, format='png', bbox_inches='tight', dpi=300, transparent=transparent_bg)
    plt.close(fig1)
    
    fig2, ax2 = plt.subplots(figsize=(4.0, 6.0))
    if not transparent_bg: fig2.patch.set_facecolor('white')
    else: fig2.patch.set_alpha(0.0)
    setup_common_ax(ax2)
    
    for st_c in struts:
        y_att, x_b, N_val = st_c['y'], st_c['x_base'], st_c['N']
        L = np.sqrt(x_b**2 + y_att**2)
        ax2.plot([0, x_b], [y_att, 0], '#E10000', lw=1.2)
        if L > 0:
            scale = 0.5 
            nx, ny = y_att/L, x_b/L
            ax2.add_patch(patches.Polygon([[0, y_att], [scale*nx, y_att+scale*ny], [x_b+scale*nx, scale*ny], [x_b, 0]], closed=True, fill=False, edgecolor='black', lw=1))
            num_lines = max(5, int(L/0.4))
            for i in range(1, num_lines + 1):
                t = i / (num_lines + 1)
                ax2.plot([t*x_b, t*x_b + scale*nx], [y_att - t*y_att, y_att - t*y_att + scale*ny], color='black', lw=0.6)
            angle = np.degrees(np.arctan2(-y_att, x_b))
            if angle < -90: angle += 180
            elif angle > 90: angle -= 180
            ax2.text(x_b/2 + (scale/2)*nx, y_att/2 + (scale/2)*ny, f"{abs(N_val):.1f}", rotation=angle, color='black', ha='center', va='center', fontsize=7, fontname='Arial', fontweight='normal')
            add_strut_text(ax2, x_b, y_att, st_c['type'].split()[0] if "No strut" not in st_c['type'] else "Invalid")

    draw_bracket(ax2, show_ll=False, show_forces=False)
    img2_stream = io.BytesIO()
    fig2.savefig(img2_stream, format='png', bbox_inches='tight', dpi=300, transparent=transparent_bg)
    plt.close(fig2)

    fig3, ax3 = plt.subplots(figsize=(4.0, 6.0))
    if not transparent_bg: fig3.patch.set_facecolor('white')
    else: fig3.patch.set_alpha(0.0)
    setup_common_ax(ax3)
    
    for st_c in struts:
        ax3.plot([0, st_c['x_base']], [st_c['y'], 0], '#E10000', lw=1.2)
        add_strut_text(ax3, st_c['x_base'], st_c['y'], st_c['type'].split()[0] if "No strut" not in st_c['type'] else "Invalid")

    for bx, rx in total_Rx.items():
        ry = total_Ry[bx]
        ax3.annotate("", xy=(bx - 0.25, -0.1), xytext=(bx, -0.1), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
        ax3.text(bx - 0.35, -0.1, f"{rx:.2f}", color='black', fontsize=9, ha='right', va='center', fontname='Arial', fontweight='normal')
        ax3.annotate("", xy=(bx + 0.1, 0.25), xytext=(bx + 0.1, 0), arrowprops=dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15))
        ax3.text(bx + 0.2, 0.35, f"{ry:.2f}", color='black', fontsize=9, ha='left', va='center', rotation=90, fontname='Arial', fontweight='normal')

    draw_bracket(ax3, show_ll=False, show_forces=False)
    img3_stream = io.BytesIO()
    fig3.savefig(img3_stream, format='png', bbox_inches='tight', dpi=300, transparent=transparent_bg)
    plt.close(fig3)
    
    return img1_stream.getvalue(), img2_stream.getvalue(), img3_stream.getvalue(), max(total_Rx.values()) if total_Rx else 0, max(total_Ry.values()) if total_Ry else 0, max_N

def generate_s2k_file(nodes, elements, custom_loads=None, dist_loads=None, corner_sup="Hinged"):
    s2k_header = """File SAP2000 exported by Acrow Program
 
TABLE:  "ACTIVE DEGREES OF FREEDOM"
   UX=Yes   UY=No   UZ=Yes   RX=No   RY=Yes   RZ=No
 
TABLE:  "ANALYSIS OPTIONS"
   Solver=Advanced   SolverProc=Auto   Force32Bit=No   StiffCase=None   GeomMod=None   HingeOpt="In Elements"
 
TABLE:  "LOAD PATTERN DEFINITIONS"
   LoadPat=DEAD   DesignType=Dead   SelfWtMult=0
 
TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"
   Material=steel   Type=Steel   Grade="Grade 50"   SymType=Isotropic   TempDepend=No   Color=Gray8Dark
   Material=TIMBER   Type=Other   SymType=Isotropic   TempDepend=No   Color=Yellow
   
TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"
   Material=steel   UnitWeight=76.97   UnitMass=7.849   E1=199947978.79   G12=76903068.76   U12=0.3   A1=1.17E-05
   Material=TIMBER   UnitWeight=8   UnitMass=0.815   E1=9066248.10   G12=3777603.37   U12=0.2   A1=1.17E-06
   
TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"
   SectionName="Soldier ][10"   Material=steel   Shape="Double Channel"   t3=0.1   t2=0.152   tf=0.008433   tw=0.006   dis=0.052   Area=0.002684208   TorsConst=4.71598771842043E-08   I33=4.1198870893659E-06   I22=5.580202752E-06   I23=0
   SectionName="Soldier U100"   Material=steel   Shape="Double Channel"   t3=0.1   t2=0.152   tf=0.008433   tw=0.006   dis=0.052   Area=0.002684208   TorsConst=4.71598771842043E-08   I33=4.1198870893659E-06   I22=5.580202752E-06   I23=0
   SectionName="Soldier ][8"   Material=steel   Shape="Double Channel"   t3=0.08   t2=0.12   tf=0.006   tw=0.005   dis=0.052   Area=0.002   TorsConst=4.71598E-08   I33=2.22E-06   I22=3.58E-06   I23=0
   SectionName="Soldier ][12"   Material=steel   Shape="Double Channel"   t3=0.12   t2=0.16   tf=0.008   tw=0.006   dis=0.052   Area=0.003   TorsConst=4.71598E-08   I33=6.56E-06   I22=7.58E-06   I23=0
   SectionName=PPH164   Material=steel   Shape=Pipe   t3=0.048   tw=0.002   Area=0.000289026
   SectionName=PPH203   Material=steel   Shape=Pipe   t3=0.048   tw=0.002   Area=0.000289026
   SectionName=PPH254   Material=steel   Shape=Pipe   t3=0.048   tw=0.002   Area=0.000289026
   SectionName=PPH304   Material=steel   Shape=Pipe   t3=0.06   tw=0.0025   Area=0.0004516
   SectionName=PPS132   Material=steel   Shape=Pipe   t3=0.06   tw=0.0025   Area=0.0004516
   SectionName=MPP6   Material=steel   Shape=Pipe   t3=0.0966   tw=0.004   Area=0.0011636
   SectionName=MPP9   Material=steel   Shape=Pipe   t3=0.0966   tw=0.004   Area=0.0011636
   SectionName=Tie   Material=steel   Shape="SD Section"   Area=0.000176   I33=0   I22=0
"""
    lines = [s2k_header]
    
    lines.append('TABLE:  "JOINT COORDINATES"')
    for i, n in enumerate(nodes):
        lines.append(f'   Joint={i+1}   CoordSys=GLOBAL   CoordType=Cartesian   XorR={n[0]:.4f}   Y=0   Z={n[1]:.4f}   SpecialJt=Yes')
    
    lines.append('')
    lines.append('TABLE:  "JOINT RESTRAINT ASSIGNMENTS"')
    for i, n in enumerate(nodes):
        # التعديل: تطبيق الركيزة وتدويرها في الـ SAP
        if abs(n[0]) < 1e-3 and abs(n[1]) < 1e-3:
            u3_val = 'Yes' if corner_sup == "Hinged" else 'No'
            lines.append(f'   Joint={i+1}   U1=Yes   U2=No   U3={u3_val}   R1=No   R2=No   R3=No')
        elif n[2] or n[3] or n[4]: 
            u1 = 'Yes' if n[2] else 'No' 
            u3 = 'Yes' if n[3] else 'No' 
            r2 = 'Yes' if n[4] else 'No' 
            lines.append(f'   Joint={i+1}   U1={u1}   U2=No   U3={u3}   R1=No   R2={r2}   R3=No')
            
    lines.append('')
    lines.append('TABLE:  "JOINT LOCAL AXES ASSIGNMENTS 1 - TYPICAL"')
    for i, n in enumerate(nodes):
        if abs(n[0]) < 1e-3 and abs(n[1]) < 1e-3:
            lines.append(f'   Joint={i+1}   AngleA=0   AngleB=45   AngleC=0')
            
    # تفريغ العنصر الوهمي من التصدير
    export_elements = [el for el in elements if el['mem'] != 'Tie']
            
    lines.append('')
    lines.append('TABLE:  "CONNECTIVITY - FRAME"')
    for i, el in enumerate(export_elements):
        lines.append(f'   Frame={i+1}   JointI={el["n1"]+1}   JointJ={el["n2"]+1}   IsCurved=No')
        
    lines.append('')
    lines.append('TABLE:  "FRAME SECTION ASSIGNMENTS"')
    for i, el in enumerate(export_elements):
        sec = el['sec']
        lines.append(f'   Frame={i+1}   AutoSelect=N.A.   AnalSect="{sec}"   MatProp=Default')
        
    lines.append('')
    lines.append('TABLE:  "FRAME RELEASE ASSIGNMENTS 1 - GENERAL"')
    for i, el in enumerate(export_elements):
        if el['type'] == 'truss':
            lines.append(f'   Frame={i+1}   PI=No   V2I=No   V3I=No   TI=No   M2I=Yes   M3I=Yes   PJ=No   V2J=No   V3J=No   TJ=No   M2J=Yes   M3J=Yes')
            
    if custom_loads:
        lines.append('')
        lines.append('TABLE:  "JOINT LOADS - FORCE"')
        for ld in custom_loads:
            closest_j, min_dist = -1, 9999
            for j, n in enumerate(nodes):
                if abs(n[0]) < 1e-3: 
                    dist = abs(n[1] - ld['y'])
                    if dist < min_dist:
                        min_dist = dist
                        closest_j = j
            if min_dist < 0.1:
                lines.append(f'   Joint={closest_j+1}   LoadPat=DEAD   CoordSys=GLOBAL   F1={ld["p"]:.3f}   F2=0   F3=0   M1=0   M2=0   M3=0')
                
    if dist_loads:
        lines.append('')
        lines.append('TABLE:  "FRAME DISTRIBUTED LOADS"')
        for dl in dist_loads:
            y1, y2, w1, w2 = dl['y1'], dl['y2'], dl['w1'], dl['w2']
            for i, el in enumerate(export_elements):
                if el['mem'] == 'V':
                    ny1, ny2 = nodes[el['n1']][1], nodes[el['n2']][1]
                    ymin, ymax = min(ny1, ny2), max(ny1, ny2)
                    overlap_y1 = max(y1, ymin)
                    overlap_y2 = min(y2, ymax)
                    if overlap_y2 > overlap_y1 + 1e-3:
                        w_start = w1 + (w2-w1)*(overlap_y1-y1)/(y2-y1) if y2 > y1 else w1
                        w_end = w1 + (w2-w1)*(overlap_y2-y1)/(y2-y1) if y2 > y1 else w2
                        d1 = (overlap_y1 - ymin) / (ymax - ymin)
                        d2 = (overlap_y2 - ymin) / (ymax - ymin)
                        if ny1 > ny2: 
                            d1, d2 = 1 - d2, 1 - d1
                            w_start, w_end = w_end, w_start
                        lines.append(f'   Frame={i+1}   LoadPat=DEAD   CoordSys=GLOBAL   Dir=X   DistType=RelDist   RelDistA={d1:.4f}   RelDistB={d2:.4f}   ValA={w_start:.3f}   ValB={w_end:.3f}')
                        
    lines.append('')
    lines.append('END TABLE DATA')
    return "\n".join(lines)
