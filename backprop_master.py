# backprop_master.py

import streamlit as st
import numpy as np
import io
import os
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

try:
    from math_solver import get_prop_allowable, get_scaffold_allowable
except ImportError:
    st.error("⚠️ لم يتم العثور على math_solver.py. برجاء التأكد من مسار الملفات.")
    def get_prop_allowable(*args): return 20.0
    def get_scaffold_allowable(*args): return 30.0

def get_shoring_capacity(t_nm, subtype, unb, req_ext):
    t_al = 20.0
    if t_nm == "Shorebrace Frame":
        t_al = 54.00
    elif t_nm == "Cup-lock":
        t_al = get_scaffold_allowable("Cup-lock", subtype, unb)
    elif t_nm == "Ring-lock":
        t_al = get_scaffold_allowable("Ring-lock", subtype, unb)
    elif t_nm == "Acrow Prop":
        t_al = get_prop_allowable(subtype, req_ext, True)
    return t_al

def generate_backprop_report(configs, ref_code):
    if os.path.exists("Acrow_Template.docx"):
        doc = Document("Acrow_Template.docx")
        doc.add_page_break()
    else:
        doc = Document()
        
    def add_p(text, bold=False, underline=False, color=None, size=12, indent=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.5
        if indent > 0:
            p.paragraph_format.left_indent = Cm(indent)
        r = p.add_run(text)
        r.font.name = 'Arial'
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.underline = underline
        if color:
            r.font.color.rgb = color
        return p

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("CALCULATION SHEET FOR RE-PROPPING (BACK-PROPPING)")
    run_title.font.name = 'Arial'
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    
    p_code = doc.add_paragraph()
    p_code.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_code = p_code.add_run("="*50 + f"\nCode Reference: {ref_code}")
    r_code.font.name = 'Arial'
    r_code.font.bold = True

    for z_idx, conf in enumerate(configs):
        if z_idx > 0: doc.add_page_break()
        
        add_p(f"Zone {z_idx+1} Calculation:", bold=True, size=14, color=RGBColor(0, 0, 128))
        add_p("Design Loads for Slabs Back-Propping", bold=True, underline=True, color=RGBColor(192, 0, 0), size=14)
        
        add_p("A. Dead load:", indent=1)
        add_p(f"-  O.W of Concrete (Concrete density = {conf['gamma_c']:.1f} KN/m³)", indent=2)
        add_p(f"-  O.W of Formwork = {conf['FW']:.2f} KN/m²", indent=2)
        
        add_p("B. Live load:", indent=1)
        add_p(f"-  Live load = {conf['LL']:.2f} KN/m²", indent=2)
        
        add_p("\nLoad Acting on \"1st Level Slabs\" while Casting Level \"2nd Slabs\".", bold=True, underline=True)
        add_p(f"-  Slabs: {conf['ts_fresh'] * 1000:.0f} mm.", indent=1)
        
        W_slab_str = f"W Slab (KN/m²) = O.W of Slab + Live Load + O.W of Formwork"
        add_p(W_slab_str, bold=True, indent=1)
        calc_str = f"               = {conf['gamma_c']:.1f}X{conf['ts_fresh']:.2f} + {conf['LL']:.2f} + {conf['FW']:.2f} = {conf['W_fresh']:.2f} KN/m²"
        add_p(calc_str, bold=True, indent=1)

        # ---------------- Check Level 1 (Under Fresh Slab) ----------------
        add_p("\nRe-Shoring Check for the System loaded on Existing Slab 1 (Props directly under Fresh Slab)", bold=True)
        add_p(f"➢ Total Re-Shoring Loads from upper level = {conf['W_fresh']:.2f} KN/m²", indent=1)
        
        grid_1 = conf['level_1_shore']
        add_p(f"Therefore; -", bold=True)
        add_p(f"Max. Loaded Area \"Back Propped area at 1st Level\" = {grid_1['gx']:.2f}x{grid_1['gy']:.2f} = {grid_1['area']:.2f} m²", indent=1)
        load_leg_1 = grid_1['area'] * conf['W_fresh']
        
        check_txt = f"Area Load on one leg of {grid_1['sys']} = {grid_1['area']:.2f} x {conf['W_fresh']:.2f} = {load_leg_1:.2f} KN < {grid_1['cap']:.2f} KN"
        p_check = doc.add_paragraph()
        p_check.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_check.paragraph_format.line_spacing = 1.5
        p_check.paragraph_format.left_indent = Cm(1)
        r_c1 = p_check.add_run(check_txt)
        r_c1.font.name = 'Arial'
        r_c1.font.size = Pt(12)
        r_res = p_check.add_run("   SAFE" if load_leg_1 <= grid_1['cap'] else "   UNSAFE")
        r_res.font.name = 'Arial'
        r_res.font.size = Pt(12)
        r_res.font.bold = True
        r_res.font.color.rgb = RGBColor(0, 128, 0) if load_leg_1 <= grid_1['cap'] else RGBColor(255, 0, 0)

        # ---------------- Iterate Existing Slabs ----------------
        current_transferred = conf['W_fresh']
        for i, slab in enumerate(conf['existing_slabs']):
            if current_transferred <= 0: break
            
            add_p(f"\n❖ Characteristic Surface Loads for Critical Zone (Existing Slab {i+1}):", bold=True, underline=True)
            add_p(f"-  Super-imposed Dead Load (SDL) = {slab['sidl']:.2f} KN/m²", indent=1)
            add_p(f"-  Live Load (L.L) = {slab['ll']:.2f} KN/m²", indent=1)
            
            unfactored = slab['sidl'] + slab['ll']
            add_p(f"\nTotal un-Factored Load (W) = {slab['sidl']:.2f} + {slab['ll']:.2f} = {unfactored:.2f} KN/m²")
            add_p(f"Assume the concrete reach {slab['strength']:.0f}% from its strength.")
            capacity = unfactored * (slab['strength'] / 100.0)
            add_p(f"Therefore: - Total resisting load = {unfactored:.2f} x {slab['strength']/100:.2f} = {capacity:.2f} KN/m²")
            
            add_p(f"\nRe-Shoring Check for the System loaded on Existing Slab {i+2}", bold=True)
            add_p(f"➢ Total Re-Shoring Loads from upper level = {current_transferred:.2f} KN/m²", indent=1)
            
            next_transferred = max(0, current_transferred - capacity)
            add_p("Therefore; -", bold=True)
            add_p(f"The Transferred Loads to the Lower Level = {current_transferred:.2f} - {capacity:.2f} = {next_transferred:.2f} KN/m²")
            
            if next_transferred > 0:
                grid_i = slab['shore']
                add_p(f"Max. Loaded Area \"Back Propped area at Level {i+2}\" = {grid_i['gx']:.2f}x{grid_i['gy']:.2f} = {grid_i['area']:.2f} m²", indent=1)
                load_leg_i = grid_i['area'] * next_transferred
                
                check_txt_i = f"Area Load on one leg of {grid_i['sys']} = {grid_i['area']:.2f} x {next_transferred:.2f} = {load_leg_i:.2f} KN < {grid_i['cap']:.2f} KN"
                p_check_i = doc.add_paragraph()
                p_check_i.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_check_i.paragraph_format.line_spacing = 1.5
                p_check_i.paragraph_format.left_indent = Cm(1)
                r_ci = p_check_i.add_run(check_txt_i)
                r_ci.font.name = 'Arial'
                r_ci.font.size = Pt(12)
                r_resi = p_check_i.add_run("   SAFE" if load_leg_i <= grid_i['cap'] else "   UNSAFE")
                r_resi.font.name = 'Arial'
                r_resi.font.size = Pt(12)
                r_resi.font.bold = True
                r_resi.font.color.rgb = RGBColor(0, 128, 0) if load_leg_i <= grid_i['cap'] else RGBColor(255, 0, 0)
                
            current_transferred = next_transferred
            
    out = io.BytesIO()
    doc.save(out)
    return out

def render_backprop_module(ref_code):
    st.markdown("## 🏗️ Multi-Zone Slab Re-propping (Back-propping)")
    st.info("💡 **Independent Module:** Evaluate multiple independent zones of fresh slabs. Each floor can have a distinct shoring grid and system.")
    
    LL_const = 1.50 if "BS" in ref_code else 2.40
    FW_load = 0.50
    st.success(f"**Code Detected:** {ref_code}  →  Construction Live Load = {LL_const} kN/m², Formwork = {FW_load} kN/m²")
    
    num_zones = st.number_input("Number of Fresh Slab Zones to Check", min_value=1, max_value=5, value=1)
    tabs = st.tabs([f"Zone {i+1}" for i in range(int(num_zones))])
    
    configs = []
    sys_opts = ["Acrow Prop", "Cup-lock", "Ring-lock", "Shorebrace Frame"]
    
    for idx, tab in enumerate(tabs):
        with tab:
            st.markdown(f"### Zone {idx+1} Properties")
            c1, c2 = st.columns(2)
            gamma_c = c1.number_input("Concrete Density (kN/m³)", value=25.0, step=0.5, key=f'g_{idx}')
            ts_fresh = c2.number_input("Fresh Slab Thickness (m)", value=0.28, step=0.01, key=f'ts_{idx}')
            W_fresh = (gamma_c * ts_fresh) + LL_const + FW_load
            st.info(f"**Total Fresh Slab Load = {W_fresh:.2f} kN/m²**")
            
            st.markdown("#### Level 1 Shoring (Props Directly Under Fresh Slab)")
            sc1, sc2, sc3 = st.columns(3)
            sys_1 = sc1.selectbox("Shoring Type", sys_opts, key=f's1_{idx}')
            gx_1 = sc2.number_input("Grid X (m)", value=1.0, step=0.1, key=f'gx1_{idx}')
            gy_1 = sc3.number_input("Grid Y (m)", value=1.2, step=0.1, key=f'gy1_{idx}')
            
            subtype_1, unb_1, ext_1 = "", 1.5, 3.0
            if sys_1 == "Cup-lock":
                subtype_1 = sc1.selectbox("Grade", ["S355 (st.52)", "S235"], key=f'c1_{idx}')
                unb_1 = sc2.number_input("Unbraced (m)", value=1.5, key=f'cu1_{idx}')
            elif sys_1 == "Ring-lock":
                subtype_1 = sc1.selectbox("Size", ["Ringlock 1.5\"", "Ringlock 2.0\""], key=f'r1_{idx}')
                unb_1 = sc2.number_input("Unbraced (m)", value=1.5, key=f'ru1_{idx}')
            elif sys_1 == "Acrow Prop":
                try: 
                    from config import PROP_DB
                    subtype_1 = sc1.selectbox("Prop Type", list(PROP_DB.keys()), key=f'p1_{idx}')
                except: subtype_1 = "Prop No.2"
                ext_1 = sc2.number_input("Extension (m)", value=3.0, key=f'pe1_{idx}')
            
            cap_1 = get_shoring_capacity(sys_1, subtype_1, unb_1, ext_1)
            st.caption(f"Leg Capacity = {cap_1:.2f} kN | Load on Leg = {(gx_1*gy_1*W_fresh):.2f} kN")
            
            level_1_shore = {'sys': sys_1, 'gx': gx_1, 'gy': gy_1, 'area': gx_1*gy_1, 'cap': cap_1}
            
            st.markdown("---")
            num_exist = st.number_input("Number of Existing Slabs Below", 1, 5, 2, key=f'nx_{idx}')
            existing_slabs = []
            
            for j in range(int(num_exist)):
                st.markdown(f"#### Existing Slab {j+1}")
                ec1, ec2, ec3 = st.columns(3)
                ll_des = ec1.number_input("Design L.L (kN/m²)", value=2.50, step=0.5, key=f'll_{idx}_{j}')
                sidl_des = ec2.number_input("Design SIDL (kN/m²)", value=0.50, step=0.5, key=f'sidl_{idx}_{j}')
                strength = ec3.number_input("Strength Achieved (%)", value=80.0, step=5.0, key=f'str_{idx}_{j}')
                
                st.markdown(f"**Level {j+2} Shoring (Props Under Existing Slab {j+1})**")
                ssc1, ssc2, ssc3 = st.columns(3)
                sys_j = ssc1.selectbox("Shoring Type", sys_opts, key=f'sj_{idx}_{j}')
                gx_j = ssc2.number_input("Grid X (m)", value=1.2, step=0.1, key=f'gxj_{idx}_{j}')
                gy_j = ssc3.number_input("Grid Y (m)", value=1.2, step=0.1, key=f'gyj_{idx}_{j}')
                
                subtype_j, unb_j, ext_j = "", 1.5, 3.0
                if sys_j == "Cup-lock":
                    subtype_j = ssc1.selectbox("Grade", ["S355 (st.52)", "S235"], key=f'cj_{idx}_{j}')
                    unb_j = ssc2.number_input("Unbraced (m)", value=1.5, key=f'cuj_{idx}_{j}')
                elif sys_j == "Ring-lock":
                    subtype_j = ssc1.selectbox("Size", ["Ringlock 1.5\"", "Ringlock 2.0\""], key=f'rj_{idx}_{j}')
                    unb_j = ssc2.number_input("Unbraced (m)", value=1.5, key=f'ruj_{idx}_{j}')
                elif sys_j == "Acrow Prop":
                    try: 
                        from config import PROP_DB
                        subtype_j = ssc1.selectbox("Prop Type", list(PROP_DB.keys()), key=f'pj_{idx}_{j}')
                    except: subtype_j = "Prop No.2"
                    ext_j = ssc2.number_input("Extension (m)", value=3.0, key=f'pej_{idx}_{j}')
                
                cap_j = get_shoring_capacity(sys_j, subtype_j, unb_j, ext_j)
                level_j_shore = {'sys': sys_j, 'gx': gx_j, 'gy': gy_j, 'area': gx_j*gy_j, 'cap': cap_j}
                
                existing_slabs.append({
                    'll': ll_des, 'sidl': sidl_des, 'strength': strength, 'shore': level_j_shore
                })
                
            configs.append({
                'gamma_c': gamma_c, 'ts_fresh': ts_fresh, 'LL': LL_const, 'FW': FW_load, 'W_fresh': W_fresh,
                'level_1_shore': level_1_shore, 'existing_slabs': existing_slabs
            })
            
    st.markdown("---")
    if st.button("🚀 Calculate & Generate Detailed Left-Aligned Report", type="primary", use_container_width=True):
        docx_out = generate_backprop_report(configs, ref_code)
        st.success("✅ Multi-Zone Analysis Complete! Calculation Sheet generated successfully.")
        st.download_button("⬇️ Download Back-propping Calculation Sheet", 
                           data=docx_out.getvalue(), 
                           file_name="Back_Propping_Report.docx", 
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
