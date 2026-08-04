# backprop_master.py

import streamlit as st
import numpy as np
import pandas as pd
import io
import os
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ---------------------------------------------------------
# استدعاء دوال الحسابات للشدات والدعامات
# ---------------------------------------------------------
try:
    from math_solver import get_prop_allowable, get_scaffold_allowable
except ImportError:
    st.error("⚠️ لم يتم العثور على math_solver.py. برجاء التأكد من مسار الملفات.")
    def get_prop_allowable(*args): return 20.0
    def get_scaffold_allowable(*args): return 30.0

# =========================================================
# 1. Back-propping Logic Engine
# =========================================================
def calculate_backprop_loads(fresh_slab, existing_slabs):
    results = []
    
    W_attacking = fresh_slab['total_load']
    results.append({'level': 'Fresh Slab', 'attacking': W_attacking, 'capacity': 0, 'transferred': W_attacking})
    
    current_P = W_attacking
    for i, slab in enumerate(existing_slabs):
        avail_cap = slab['capacity'] - slab['self_weight']
        if avail_cap < 0: avail_cap = 0 
        
        absorbed = min(current_P, avail_cap)
        current_P = max(0, current_P - avail_cap)
        
        results.append({
            'level': f'Existing Slab {i+1}', 
            'attacking': results[-1]['transferred'], 
            'capacity': avail_cap, 
            'transferred': current_P
        })
        
        if current_P <= 0:
            break
            
    return results, current_P

# =========================================================
# 2. Engine for Plotting the Results
# =========================================================
def plot_backprop_system(results):
    num_levels = len(results)
    fig, ax = plt.subplots(figsize=(10, num_levels * 1.5))
    
    y_pos = np.arange(num_levels, 0, -1) * 2
    
    for i, res in enumerate(results):
        y = y_pos[i]
        color = 'gray' if 'Existing' in res['level'] else 'blue'
        rect = plt.Rectangle((1, y-0.2), 8, 0.4, facecolor=color, alpha=0.5, edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        ax.text(5, y, res['level'], ha='center', va='center', fontsize=12, fontweight='bold', color='white')
        
        if i < num_levels - 1 and res['transferred'] > 0:
            next_y = y_pos[i+1]
            ax.annotate('', xy=(5, next_y+0.2), xytext=(5, y-0.2),
                        arrowprops=dict(facecolor='red', shrink=0.05, width=4, headwidth=10))
            ax.text(5.2, (y + next_y)/2, f"{res['transferred']:.2f} kN/m²", color='red', fontsize=11, fontweight='bold')
            
            ax.plot([3, 3], [y-0.2, next_y+0.2], color='black', linewidth=3)
            ax.plot([7, 7], [y-0.2, next_y+0.2], color='black', linewidth=3)
            
    ax.set_xlim(0, 10)
    ax.set_ylim(0, max(y_pos) + 1)
    ax.axis('off')
    plt.title("Back-propping Load Transfer Diagram", fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# =========================================================
# 3. Report Generator for Back-propping
# =========================================================
def generate_backprop_report(results, grid_data, img_buf, ref_code):
    if os.path.exists("Acrow_Template.docx"):
        doc = Document("Acrow_Template.docx")
        doc.add_page_break()
    else:
        doc = Document()
        
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("CALCULATION SHEET FOR RE-PROPPING (BACK-PROPPING)")
    run_title.font.name = 'Arial'
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    
    doc.add_paragraph("="*50)
    
    def add_line(text, bold=False):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.font.name = 'Arial'
        r.font.size = Pt(12)
        r.font.bold = bold

    add_line(f"Code Reference: {ref_code}", bold=True)
    add_line("1. Load Transfer Iterations:", bold=True)
    
    for res in results:
        add_line(f"• {res['level']}:")
        add_line(f"  - Attacking Load = {res['attacking']:.2f} kN/m²")
        if 'Existing' in res['level']:
            add_line(f"  - Available Capacity = {res['capacity']:.2f} kN/m²")
        add_line(f"  - Load Transferred to props below = {res['transferred']:.2f} kN/m²", bold=True)
        doc.add_paragraph()
        
    add_line("2. Shoring System Design:", bold=True)
    if grid_data['needed']:
        add_line(f"- Selected System: {grid_data['system']}")
        add_line(f"- Allowable Load per Leg: {grid_data['allowable']:.2f} kN")
        add_line(f"- Maximum Load to be supported: {grid_data['max_P']:.2f} kN/m²")
        add_line(f"- Required Area per Leg: {grid_data['area_req']:.2f} m²")
        add_line(f"- Recommended Grid Spacing: {grid_data['rec_grid']}", bold=True)
    else:
        add_line("- Maximum Load transferred is Zero. No Back-propping required.", bold=True)
        
    doc.add_page_break()
    add_line("3. Load Path Diagram:", bold=True)
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.add_run().add_picture(io.BytesIO(img_buf.read()), width=Cm(15.0))
    
    out = io.BytesIO()
    doc.save(out)
    return out

# =========================================================
# 4. Main UI Module for Back-propping
# =========================================================
def render_backprop_module(ref_code):
    st.markdown("## 🏗️ Slab Re-propping (Back-propping) Designer")
    st.info("💡 **Independent Module:** This module calculates load propagation through previously cast slabs and determines the required shoring grid.")
    
    LL_const = 1.50 if "BS" in ref_code else 2.40
    FW_load = 0.50
    st.success(f"**Code Detected:** {ref_code}  →  Construction Live Load = {LL_const} kN/m², Formwork = {FW_load} kN/m²")
    
    st.markdown("### 1. Fresh Slab Data (Top Slab)")
    c1, c2 = st.columns(2)
    gamma_c = c1.number_input("Concrete Density (kN/m³)", value=25.0, step=0.5, key='bp_gamma')
    ts_fresh = c2.number_input("Fresh Slab Thickness (m)", value=0.30, step=0.05, key='bp_ts')
    
    W_fresh = (gamma_c * ts_fresh) + LL_const + FW_load
    st.info(f"**Total Fresh Load attacking the first slab = {W_fresh:.2f} kN/m²**")
    
    st.markdown("### 2. Existing Slabs Data")
    num_slabs = st.number_input("Number of Existing Slabs below", min_value=1, max_value=5, value=2)
    
    existing_slabs = []
    for i in range(int(num_slabs)):
        with st.expander(f"Existing Slab {i+1} (Directly Below)"):
            cb1, cb2, cb3, cb4 = st.columns(4)
            ts_i = cb1.number_input("Thickness (m)", value=0.30, step=0.05, key=f'bp_tsi_{i}')
            LL_des = cb2.number_input("Design Live Load (kN/m²)", value=3.0, step=0.5, key=f'bp_ll_{i}')
            SIDL_des = cb3.number_input("Design SIDL (kN/m²)", value=2.5, step=0.5, key=f'bp_sidl_{i}')
            strength = cb4.number_input("Strength Achieved (%)", value=80.0, max_value=100.0, step=5.0, key=f'bp_str_{i}')
            
            SW_i = gamma_c * ts_i
            Total_Des = SW_i + SIDL_des + LL_des
            Cap_i = Total_Des * (strength / 100.0)
            
            existing_slabs.append({
                'self_weight': SW_i,
                'capacity': Cap_i
            })
            st.caption(f"Calculated Capacity = {Cap_i:.2f} kN/m² | Self Weight = {SW_i:.2f} kN/m²")
            
    st.markdown("### 3. Shoring System Details")
    c_s1, c_s2 = st.columns(2)
    sys_opts = ["Acrow Prop", "Cup-lock", "Ring-lock", "Shorebrace Frame"]
    t_nm = c_s1.selectbox("Shoring Type", sys_opts, key='bp_sys')
    
    t_al = 20.0
    if t_nm == "Shorebrace Frame":
        t_al = 54.40
    elif t_nm == "Cup-lock":
        subtype = c_s2.selectbox("Steel Grade", ["S355 (st.52)", "S235"], key="bp_cup_sub")
        unb = c_s2.number_input("Unbraced Length (m)", value=1.5, step=0.5, key="bp_cup_unb")
        t_al = get_scaffold_allowable("Cup-lock", subtype, unb)
    elif t_nm == "Ring-lock":
        subtype = c_s2.selectbox("Diameter", ["Ringlock 1.5\"", "Ringlock 2.0\""], key="bp_ring_sub")
        unb = c_s2.number_input("Unbraced Length (m)", value=1.5, step=0.5, key="bp_ring_unb")
        t_al = get_scaffold_allowable("Ring-lock", subtype, unb)
    elif t_nm == "Acrow Prop":
        from config import PROP_DB
        req_ext = c_s2.number_input("Prop Extension (m)", value=3.0, step=0.1, key="bp_prop_ext")
        valid_props = [k for k, v in PROP_DB.items() if v['min'] <= req_ext <= v['max']] if PROP_DB else ["Prop No.2", "Prop No.3"]
        if valid_props:
            sel_prop = c_s2.selectbox("Select Valid Prop", valid_props, key="bp_prop_sel")
            t_al = get_prop_allowable(sel_prop, req_ext, True)
        else:
            t_al = 0.0
            
    st.info(f"**Allowable Load per Leg = {t_al:.2f} kN**")
    
    st.markdown("---")
    if st.button("🚀 Calculate Load Propagation & Generate Report", type="primary", use_container_width=True):
        fresh_slab = {'total_load': W_fresh}
        results, unabsorbed = calculate_backprop_loads(fresh_slab, existing_slabs)
        
        max_transferred = max([r['transferred'] for r in results[:-1]]) 
        
        grid_data = {'needed': False}
        if max_transferred > 0 and t_al > 0:
            area_req = t_al / max_transferred
            
            # Simple grid suggestion logic
            grid_sugg = "1.00m x 1.00m"
            if area_req >= 1.44: grid_sugg = "1.20m x 1.20m"
            elif area_req >= 1.20: grid_sugg = "1.00m x 1.20m"
            
            grid_data = {
                'needed': True,
                'system': t_nm,
                'allowable': t_al,
                'max_P': max_transferred,
                'area_req': area_req,
                'rec_grid': grid_sugg
            }
            
            st.success(f"**Calculated Required Area per Leg = {area_req:.2f} m²**")
            st.success(f"**Recommended Safe Grid Spacing = {grid_sugg}**")
        elif max_transferred <= 0:
            st.success("🎉 Existing slabs can safely carry the load! No Back-propping required.")
            
        if unabsorbed > 0:
            st.warning(f"⚠️ Warning: The load is not fully absorbed by the defined existing slabs. {unabsorbed:.2f} kN/m² reaches the ground/lowest level.")
            
        img_buf = plot_backprop_system(results)
        st.image(img_buf, use_container_width=True)
        
        docx_out = generate_backprop_report(results, grid_data, img_buf, ref_code)
        
        st.download_button("⬇️ Download Back-propping Calculation Sheet", 
                           data=docx_out.getvalue(), 
                           file_name="Back_Propping_Report.docx", 
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
