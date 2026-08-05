# bridge_master.py

import streamlit as st
import numpy as np
import pandas as pd
import io
import os
import re
import ast
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# =========================================================
# 1. HTML Parser Engine
# =========================================================
def parse_bridge_html(html_content):
    """Parses JavaScript arrays from the provided HTML file into Python dictionaries."""
    
    # استخراج مصفوفات النقاط والعناصر من الكود
    nodes_match = re.search(r'const globalNodes\s*=\s*(\[.*?\]);', html_content, re.DOTALL)
    elems_match = re.search(r'const globalElements\s*=\s*(\[.*?\]);', html_content, re.DOTALL)
    
    if not nodes_match or not elems_match:
        return None, None
        
    def clean_js_to_python(js_str):
        # وضع علامات تنصيص حول المفاتيح غير المحاطة بتنصيص
        js_str = re.sub(r'(?<!")([a-zA-Z_][a-zA-Z0-9_]*)(?=\s*:)', r'"\1"', js_str)
        # تحويل القيم المنطقية لصيغة البايثون
        js_str = js_str.replace(': false', ': False').replace(': true', ': True')
        js_str = js_str.replace(':false', ':False').replace(':true', ':True')
        return js_str
        
    try:
        nodes_str = clean_js_to_python(nodes_match.group(1))
        elems_str = clean_js_to_python(elems_match.group(1))
        
        nodes = ast.literal_eval(nodes_str)
        elements = ast.literal_eval(elems_str)
        return nodes, elements
    except Exception as e:
        st.error(f"⚠️ خطأ في قراءة البيانات من الملف: {e}")
        return None, None

# =========================================================
# 2. Plotting Engine (SAP2000 Style)
# =========================================================
def get_img_buf(fig):
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=200, bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf

def draw_sap2000_diagram(val_key, nodes, elements, scale, is_axial=False):
    mpl.rcParams['font.family'] = 'sans-serif'
    mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    mpl.rcParams['font.size'] = 7
    
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.set_aspect('equal', adjustable='datalim')
    ax.axis('off')
    
    nodes_dict = {n['id']: n for n in nodes}
    
    # رسم خطوط العناصر الأساسية
    for el in elements:
        n1, n2 = nodes_dict[el['i']], nodes_dict[el['j']]
        ax.plot([n1['x'], n2['x']], [n1['y'], n2['y']], color='black', linewidth=0.8, zorder=1)
        
    # رسم الركائز (Supports) بشكل مفرغ ولون أخضر فاتح
    for n in nodes:
        if n.get('fixX') or n.get('fixY') or n.get('fixT'):
            x, y = n['x'], n['y']
            t = 'Fixed' if (n.get('fixX') and n.get('fixY') and n.get('fixT')) else \
                'Hinged' if (n.get('fixX') and n.get('fixY')) else 'Roller'
                
            if t == 'Hinged' or t == 'Fixed':
                h, w = 0.5, 0.4
                p1, p2, p3 = (x, y), (x + w/2, y - h), (x - w/2, y - h)
                poly = Polygon([p1, p2, p3], facecolor='none', edgecolor='limegreen', lw=1.2, zorder=5)
                ax.add_patch(poly)
                ax.plot([x - w, x + w], [y - h, y - h], color='limegreen', lw=1.5, zorder=4)
            elif t == 'Roller':
                h, w, r = 0.4, 0.3, 0.12
                p1, p2, p3 = (x, y), (x + w/2, y - h), (x - w/2, y - h)
                poly = Polygon([p1, p2, p3], facecolor='none', edgecolor='limegreen', lw=1.2, zorder=5)
                ax.add_patch(poly)
                circle = plt.Circle((x, y - h - r), r, facecolor='none', edgecolor='limegreen', lw=1.2, zorder=5)
                ax.add_patch(circle)
                base_dist = h + 2*r
                line_w = 0.2
                ax.plot([x - line_w, x + line_w], [y - base_dist, y - base_dist], color='limegreen', lw=1.5, zorder=4)

    plotted_texts = set()
    def write_val(txt_x, txt_y, v, rot=0):
        if abs(v) >= 0.1:
            lbl = f"{abs(v):.1f}"
            sig = f"{round(txt_x,1)}_{round(txt_y,1)}"
            if sig not in plotted_texts:
                ax.text(txt_x, txt_y, lbl, color='black', fontsize=6, fontname='Arial', ha='center', va='center', rotation=rot)
                plotted_texts.add(sig)

    # رسم المخططات (Diagrams)
    for el in elements:
        n1, n2 = nodes_dict[el['i']], nodes_dict[el['j']]
        x1, y1 = n1['x'], n1['y']
        x2, y2 = n2['x'], n2['y']
        dx, dy = x2 - x1, y2 - y1
        L_s = np.hypot(dx, dy)
        if L_s < 1e-5: continue
        
        c, s = dx/L_s, dy/L_s
        rot_ang = np.degrees(np.arctan2(dy, dx))
        
        diag_arr = el.get('axialDiag' if is_axial else 'diag', [])
        if not diag_arr: continue
        
        ts = np.array([pt['t'] for pt in diag_arr])
        vals_orig = np.array([pt['n' if is_axial else val_key.lower()] for pt in diag_arr])
        
        # SAP2000 Convention: Negative moment drawn on tension side (+y typically for beams if normal is up).
        # Normal vector: nx = -s, ny = c
        plot_vals = -vals_orig if val_key != 'N' else vals_orig
        
        px_arr = x1 + c * (ts * L_s) - s * plot_vals * scale
        py_arr = y1 + s * (ts * L_s) + c * plot_vals * scale
        
        color_pos, color_neg = 'blue', 'red'
        
        # رسم خط التغطية الخارجي (Outline)
        ax.plot([x1, px_arr[0]], [y1, py_arr[0]], color=color_pos if vals_orig[0] >= 0 else color_neg, linewidth=0.8)
        for k in range(len(px_arr)-1):
            avg_v = (vals_orig[k] + vals_orig[k+1]) / 2.0
            seg_color = color_pos if avg_v >= 0 else color_neg
            ax.plot([px_arr[k], px_arr[k+1]], [py_arr[k], py_arr[k+1]], color=seg_color, linewidth=0.8)
        ax.plot([px_arr[-1], x2], [py_arr[-1], y2], color=color_pos if vals_orig[-1] >= 0 else color_neg, linewidth=0.8)
        
        # رسم التهشير الداخلي (Hatching)
        num_lines = max(2, int(L_s / 0.4))
        for i in range(1, num_lines):
            frac = i / num_lines
            lx, ly = x1 + frac * dx, y1 + frac * dy
            idx_val = int(frac * (len(plot_vals)-1))
            lv = plot_vals[idx_val]
            hx, hy = lx - s * lv * scale, ly + c * lv * scale
            line_color = color_pos if vals_orig[idx_val] >= 0 else color_neg
            ax.plot([lx, hx], [ly, hy], color=line_color, linewidth=0.3, alpha=0.6)
            
        # كتابة أقصى قيم
        offset = 0.4
        max_idx = np.argmax(np.abs(vals_orig))
        v_max = plot_vals[max_idx]
        if abs(vals_orig[max_idx]) > 0.1:
            txt_x = px_arr[max_idx] - s * np.sign(v_max) * offset
            txt_y = py_arr[max_idx] + c * np.sign(v_max) * offset
            write_val(txt_x, txt_y, vals_orig[max_idx], 0)

    return get_img_buf(fig)

# =========================================================
# 3. Report Generator
# =========================================================
def generate_bridge_report(nodes, elements, img_bufs):
    if os.path.exists("Acrow_Template.docx"):
        doc = Document("Acrow_Template.docx")
        doc.add_page_break()
    else:
        doc = Document()
        
    def force_ltr_left(p):
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pPr = p._element.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        bidi.set(qn('w:val'), '0')
        pPr.append(bidi)
        
    def add_line(text, bold=False, color=None, size=11):
        p = doc.add_paragraph()
        force_ltr_left(p)
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(text)
        r.font.name = 'Arial'
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.rtl = False
        if color: r.font.color.rgb = color
        return p

    p_title = doc.add_paragraph()
    force_ltr_left(p_title)
    run_title = p_title.add_run("CALCULATION SHEET FOR BRIDGE STRUCTURE")
    run_title.font.name = 'Arial'
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    run_title.font.rtl = False
    
    add_line("="*50, bold=True)
    add_line("1. Extracted Model Information:", bold=True)
    add_line(f"- Total Nodes Analyzed: {len(nodes)}")
    add_line(f"- Total Elements Analyzed: {len(elements)}")
    
    # حساب أقصى قيم
    max_m, max_v, max_n_tens, max_n_comp = 0, 0, 0, 0
    for el in elements:
        if 'maxM' in el: max_m = max(max_m, abs(el['maxM']))
        if 'maxV' in el: max_v = max(max_v, abs(el['maxV']))
        if 'maxN' in el:
            if el['maxN'] > 0: max_n_tens = max(max_n_tens, el['maxN'])
            else: max_n_comp = min(max_n_comp, el['maxN']) # Compression is negative
    
    add_line("\n2. Global Force Extremes:", bold=True)
    add_line(f"- Maximum Bending Moment = {max_m:.2f} kN.m")
    add_line(f"- Maximum Shear Force = {max_v:.2f} kN")
    add_line(f"- Maximum Axial Tension = {max_n_tens:.2f} kN")
    add_line(f"- Maximum Axial Compression = {abs(max_n_comp):.2f} kN")
    
    add_line("\n3. Support Reactions:", bold=True)
    for n in nodes:
        if n.get('fixX') or n.get('fixY') or n.get('fixT'):
            rx = n.get('rx', 0)
            ry = n.get('ry', 0)
            add_line(f"- Node {n['name']}: Rx = {rx:.2f} kN | Ry = {ry:.2f} kN", color=RGBColor(0, 100, 0))

    doc.add_page_break()
    add_line("4. Structural Diagrams (SAP2000 Convention):", bold=True, size=14)
    
    titles = {
        'N': "Axial Force Diagram (kN) [Blue = Tension, Red = Compression]",
        'V': "Shear Force Diagram (kN)",
        'M': "Bending Moment Diagram (kN.m)"
    }
    
    for key in ['N', 'V', 'M']:
        buf = img_bufs[key]
        buf.seek(0)
        
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(io.BytesIO(buf.read()), width=Cm(16.0))
        
        p_txt = doc.add_paragraph()
        p_txt.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_txt = p_txt.add_run(titles[key])
        r_txt.font.name = 'Arial'
        r_txt.font.size = Pt(10)
        r_txt.underline = True
        r_txt.font.rtl = False
        
        doc.add_page_break()
    
    out = io.BytesIO()
    doc.save(out)
    return out

# =========================================================
# 4. Main UI Module
# =========================================================
def render_bridge_module():
    st.markdown("## 🌉 Bridge Formwork & Structures (Extractor & Analyzer)")
    st.info("💡 **Upload Mode:** Upload your Acrow Bridge HTML Report to extract calculation data, convert diagrams to SAP2000 style, and generate a Word calculation sheet automatically.")
    
    uploaded_file = st.file_uploader("📂 Upload Acrow Bridge FEA HTML File", type=["html"])
    
    if uploaded_file is not None:
        html_content = uploaded_file.getvalue().decode("utf-8")
        
        with st.spinner("Extracting Nodes and Elements Data..."):
            nodes, elements = parse_bridge_html(html_content)
            
        if nodes and elements:
            st.success(f"✅ Data Extracted Successfully! Found **{len(nodes)} Nodes** and **{len(elements)} Elements**.")
            
            st.markdown("### 🎛️ Customize Diagram Scales")
            c_s1, c_s2, c_s3 = st.columns(3)
            sc_n = c_s1.slider("Axial Scale", 0.001, 0.050, 0.005, step=0.001)
            sc_v = c_s2.slider("Shear Scale", 0.001, 0.050, 0.010, step=0.001)
            sc_m = c_s3.slider("Moment Scale", 0.001, 0.100, 0.010, step=0.001)
            scales = {'N': sc_n, 'V': sc_v, 'M': sc_m}
            
            if st.button("🚀 Process & Generate Calculation Sheet", type="primary", use_container_width=True):
                with st.spinner("Rendering SAP2000-Style Diagrams..."):
                    img_bufs = {
                        'N': draw_sap2000_diagram('N', nodes, elements, scales['N'], is_axial=True),
                        'V': draw_sap2000_diagram('V', nodes, elements, scales['V']),
                        'M': draw_sap2000_diagram('M', nodes, elements, scales['M'])
                    }
                    
                    c_p1, c_p2 = st.columns(2)
                    c_p1.image(img_bufs['N'], caption="Axial Force Diagram (kN)")
                    c_p2.image(img_bufs['M'], caption="Bending Moment Diagram (kN.m)")
                    
                    docx_out = generate_bridge_report(nodes, elements, img_bufs)
                    st.download_button(
                        "⬇️ Download Bridge Calculation Sheet (Word)", 
                        data=docx_out.getvalue(), 
                        file_name="Acrow_Bridge_Calculation_Sheet.docx", 
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
