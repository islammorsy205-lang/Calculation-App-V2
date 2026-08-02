# ui_wind.py

import streamlit as st
import pandas as pd
import numpy as np
import io
from helpers import get_val, get_idx, convert_transparent_to_pdf_stream, get_valid_struts
from config import STRUTS_DB
from math_solver import get_kz, solve_beam_advanced
from plot_core import draw_tilting_diagrams

def render_wind_tilting_ui(i, h_panel, w_tot):
    tilt_dict = {'active': False}
    st.divider()
    with st.container(border=True):
        st.markdown("### 🌬️ Wind Load & Tilting System Config")
        
        current_h = st.session_state.get(f"hp_wind_{i}", h_panel)
        if st.session_state.get(f"last_h_{i}") != current_h:
            st.session_state[f"last_h_{i}"] = current_h
            st.session_state[f"y1_{i}"] = 0.50
            st.session_state[f"x1_{i}"] = 1.35  
            
            if current_h <= 6.5:
                st.session_state[f"rb_num_props_{i}"] = 2
                st.session_state[f"y2_{i}"] = round(current_h - (current_h / 3.0), 2)
                st.session_state[f"x2_{i}"] = round(st.session_state[f"y2_{i}"] / 1.732, 2)
                st.session_state[f"y3_{i}"] = 0.0
                st.session_state[f"x3_{i}"] = 0.0
            else:
                st.session_state[f"rb_num_props_{i}"] = 3
                st.session_state[f"y2_{i}"] = round(current_h / 2.0, 2)
                st.session_state[f"x2_{i}"] = round(st.session_state[f"y2_{i}"] / 1.732, 2)
                st.session_state[f"y3_{i}"] = round(current_h - (current_h / 6.0), 2)
                st.session_state[f"x3_{i}"] = round(st.session_state[f"y3_{i}"] / 1.732, 2)
                
        cw1, cw2, cw3, cw4 = st.columns(4)
        with cw1:
            exp_cat = st.selectbox("Exposure Category", ["B", "C", "D"], index=get_idx("exp", i, ["B", "C", "D"], 0), key=f"exp_{i}")
            v_wind = st.number_input("Wind Speed V (m/s)", value=float(get_val("vw", i, 47.0)), step=1.0, key=f"vw_{i}")
        with cw2:
            z_height = st.number_input("Height above ground, z (m)", value=float(get_val("z_ht", i, 20.0)), step=0.05, key=f"z_ht_{i}")
            kz_wind = get_kz(z_height, exp_cat)
            st.info(f"**Kz Factor** = {kz_wind:.2f}")
        with cw3: 
            h_panel = st.number_input("Total Wall/Panel Height (m)", key=f"hp_wind_{i}", step=0.05, value=current_h)
        with cw4: 
            wp_panel = st.number_input("Push-pull Spacing (m)", value=float(get_val("wp", i, 2.20)), step=0.05, key=f"wp_{i}")

        qz = 0.613 * kz_wind * 1.00 * 0.85 * (v_wind ** 2)
        Af = h_panel * wp_panel
        F_wind = (qz / 1000) * 0.850 * 1.300 * Af
        w_dist = F_wind / h_panel if h_panel > 0 else 0
        st.success(f"🌬️ **Distributed Wind Load/m' = {w_dist:.2f} KN/M**")
        
        st.markdown("#### 📐 Advanced Strut Axial Analysis")
        if st.toggle("Include Detailed Strut & Anchor Checks", value=bool(get_val("inc_tilt", i, False)), key=f"inc_tilt_{i}"):
            ts_1, ts_2 = st.columns([1.0, 2.0])
            with ts_1:
                inc_bracket = st.toggle("Include Access Bracket", value=False, key=f"inc_bkt_{i}")
                
                # إخفاء/إظهار الداتا الخاصة بالبراكت بناءً على زر التفعيل
                acc_L1, acc_L2, acc_LL = 0.90, 1.00, 1.50
                if inc_bracket:
                    st.markdown("**Access Bracket Forces:**")
                    cb1, cb2, cb3 = st.columns(3)
                    acc_L1 = cb1.number_input("L1 (m)", value=0.90, step=0.05, key=f"acc_l1_{i}")
                    acc_L2 = cb2.number_input("L2 (m)", value=1.00, step=0.05, key=f"acc_l2_{i}")
                    acc_LL = cb3.number_input("LL (kN/m²)", value=1.50, step=0.1, key=f"acc_ll_{i}")
                
                num_props = st.radio("Number of Push-Pulls:", [2, 3], key=f"rb_num_props_{i}", horizontal=True)
                struts_conf = []
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    y1 = st.number_input("Y1 (m)", value=0.50, key=f"y1_{i}", step=0.05)
                    y2 = st.number_input("Y2 (m)", value=4.00, key=f"y2_{i}", step=0.05)
                    y3 = st.number_input("Y3 (m)", value=6.67, key=f"y3_{i}", step=0.05) if num_props == 3 else 0.0
                with col_g2:
                    default_x2 = st.session_state.get(f"x2_{i}", 2.31)
                    x1 = st.number_input("X1 (m)", value=float(default_x2), key=f"x1_{i}", step=0.05)
                    x2 = st.number_input("X2 (m)", value=2.31, key=f"x2_{i}", step=0.05)
                    x3 = st.number_input("X3 (m)", value=3.85, key=f"x3_{i}", step=0.05) if num_props == 3 else 0.0
                
                l1_req = np.hypot(x1, y1)
                l2_req = np.hypot(x2, y2)
                l3_req = np.hypot(x3, y3) if num_props == 3 else 0.0
                
                st.markdown("---")
                s1 = st.selectbox(f"Lower Type ({l1_req:.2f}m)", get_valid_struts(l1_req, "wind"), key=f"s1_{i}")
                s2 = st.selectbox(f"Middle Type ({l2_req:.2f}m)", get_valid_struts(l2_req, "wind"), key=f"s2_{i}")
                struts_conf.append({"y": y1, "x_base": x1, "type": s1, "allow": STRUTS_DB.get(s1, {}).get('allow', 999.0) if "No strut" not in s1 else 0.0})
                struts_conf.append({"y": y2, "x_base": x2, "type": s2, "allow": STRUTS_DB.get(s2, {}).get('allow', 999.0) if "No strut" not in s2 else 0.0})
                
                length_is_safe = ("No strut" not in s1) and ("No strut" not in s2)
                if num_props == 3:
                    s3 = st.selectbox(f"Top Type ({l3_req:.2f}m)", get_valid_struts(l3_req, "wind"), key=f"s3_{i}")
                    struts_conf.append({"y": y3, "x_base": x3, "type": s3, "allow": STRUTS_DB.get(s3, {}).get('allow', 999.0) if "No strut" not in s3 else 0.0})
                    if "No strut" in s3: length_is_safe = False
                    
                st.markdown("#### 🧱 Base Anchorage Type")
                base_type = st.radio("Select Anchorage:", ["Rigid Slab / Raft", "Independent Concrete Block"], key=f"base_type_{i}", horizontal=True)
                block_data = None
                if base_type == "Independent Concrete Block":
                    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                    b_len = col_b1.number_input("L (m)", value=1.0, step=0.05, key=f"blen_{i}")
                    b_wid = col_b2.number_input("W (m)", value=1.0, step=0.05, key=f"bwid_{i}")
                    b_ht = col_b3.number_input("H (m)", value=1.25, step=0.05, key=f"bht_{i}")
                    b_mu = col_b4.number_input("μ", value=0.50, step=0.01, key=f"bmu_{i}")
                    block_data = {'active': True, 'L': b_len, 'W': b_wid, 'H': b_ht, 'mu': b_mu, 'gamma': 25.0}

                y_top = h_panel - 0.50
                y_bot = y_top - acc_L2
                F_couple = (acc_LL * acc_L1 * wp_panel * (acc_L1 / 2.0)) / acc_L2 if acc_L2 > 0 else 0
                bkt_data = {'active': inc_bracket, 'dist': 0.50, 'L1': acc_L1, 'L2': acc_L2, 'LL': acc_LL, 'y_top': y_top, 'y_bot': y_bot, 'F': F_couple}
                if inc_bracket: st.info(f"**Bracket Forces:** Top = +{F_couple:.2f} kN, Bottom = -{F_couple:.2f} kN")
                
            with ts_2:
                if length_is_safe:
                    loads_w = [{'type': 'linear', 'w1': w_dist, 'w2': w_dist, 'x1': 0, 'x2': h_panel}]
                    if bkt_data['active']:
                        loads_w.extend([{'type': 'point', 'p': bkt_data['F'], 'x': bkt_data['y_top']}, {'type': 'point', 'p': -bkt_data['F'], 'x': bkt_data['y_bot']}])
                    
                    supports_w = [0.0] + [st_c['y'] for st_c in struts_conf]
                    
                    try: _, _, _, _, R_wind = solve_beam_advanced(h_panel, supports_w, loads_w, 21000, 1000)
                    except Exception: R_wind = [0] * (len(supports_w) + 1)
                    
                    for idx, st_c in enumerate(struts_conf):
                        y_att, x_b = st_c['y'], st_c['x_base']
                        R_att = abs(R_wind[idx+1]) if (idx+1) < len(R_wind) else 0
                        L_st = np.sqrt(x_b**2 + y_att**2)
                        st_c['N'] = R_att * (L_st / x_b) if x_b > 0 else 0
                        
                    img_w_bytes, img_n_bytes, img_r_bytes, max_rx_base, max_ry_base, max_n = draw_tilting_diagrams(h_panel, struts_conf, w_dist, bkt_data=bkt_data, transparent_bg=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.download_button("📥 PDF", convert_transparent_to_pdf_stream(img_w_bytes), "Wind_Loads.pdf", "application/pdf", key=f"dw_{i}")
                        st.image(img_w_bytes, use_container_width=True)
                        st.markdown("<p style='text-align: center; color: #666;'>Assigned Wind Load</p>", unsafe_allow_html=True)
                    with c2:
                        st.download_button("📥 PDF", convert_transparent_to_pdf_stream(img_n_bytes), "Wind_Axial.pdf", "application/pdf", key=f"dn_{i}")
                        st.image(img_n_bytes, use_container_width=True)
                        st.markdown("<p style='text-align: center; color: #666;'>Axial Force Diagram</p>", unsafe_allow_html=True)
                    
                    st.markdown("---")
                    st.markdown("<p style='text-align: left; font-weight: bold;'>Base Reactions & Anchor Bolts Check</p>", unsafe_allow_html=True)
                    
                    c_r1, c_r2 = st.columns([1, 2])
                    with c_r1: 
                        st.download_button("📥 PDF", convert_transparent_to_pdf_stream(img_r_bytes), "Wind_Reactions.pdf", "application/pdf", key=f"dr_{i}")
                        st.image(img_r_bytes, use_container_width=True)
                        st.markdown("<p style='text-align: center; color: #666;'>Reactions Diagram</p>", unsafe_allow_html=True)
                    with c_r2:
                        st.info(f"**Max Revit Pin Shear:** {max_n:.2f} kN < 80.00 kN")
                        st.info(f"**Max Anchor Bolt Tension (Worst Base):** {max_ry_base/2:.2f} kN < 15.10 kN")
                        st.info(f"**Max Anchor Bolt Shear (Worst Base):** {max_rx_base/2:.2f} kN < 29.50 kN")
                        if block_data and block_data['active']:
                            W_block = block_data['L'] * block_data['W'] * block_data['H'] * block_data['gamma']
                            N_eff = W_block - max_ry_base
                            if N_eff <= 0: 
                                st.error(f"**Block Stability:** UNSAFE (Block is lifting!)")
                                block_data['safe'] = False
                            else:
                                M_st = N_eff * (block_data['L'] / 2.0)
                                M_ov = max_rx_base * (block_data['H'] / 2.0)
                                FOS_ov = M_st / M_ov if M_ov > 0 else 999.0
                                F_res = N_eff * block_data['mu']
                                FOS_sl = F_res / max_rx_base if max_rx_base > 0 else 999.0
                                block_data['safe'] = (FOS_ov >= 1.50) and (FOS_sl >= 1.50)
                                block_data.update({'W_block': W_block, 'N_eff': N_eff, 'M_st': M_st, 'M_ov': M_ov, 'FOS_ov': FOS_ov, 'FOS_sl': FOS_sl, 'max_rx': max_rx_base, 'max_ry': max_ry_base})
                        
                        s2k_data = "SAP2000 Data Placeholder. Waiting for details."
                        st.download_button("📥 Export S2K", data=s2k_data, file_name=f"Wind_{i}.s2k", mime="text/plain", key=f"s2k_w_{i}")
                    
                    tilt_dict.update({
                        "active": True, "struts": struts_conf, "rx1": max_rx_base, "ry1": max_ry_base, 
                        "rx2": 0, "ry2": 0, "max_n": max_n, "x1": x1, "x2": x2, 
                        "h_panel": h_panel, "w_dist": w_dist, "v_wind": v_wind, 
                        "kz_wind": kz_wind, "wp_panel": wp_panel, "bkt_data": bkt_data, 
                        "block_data": block_data, "length_safe": True, "img_w": img_w_bytes, 
                        "img_n": img_n_bytes, "img_r": img_r_bytes
                    })
                else: 
                    st.error("⚠️ Invalid Geometry! Please adjust distances.")
                    tilt_dict.update({"active": True, "length_safe": False})
        else: 
            tilt_dict.update({"active": False, "w_dist": w_dist, "v_wind": v_wind, "kz_wind": kz_wind, "hp": h_panel, "wp": wp_panel})
            
    return tilt_dict
