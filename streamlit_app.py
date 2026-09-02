import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import json
import urllib.request

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tubing Selection Tool",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for presentation-grade UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION & CSV LOADER
# -----------------------------------------------------------------------------
if 'inputs' not in st.session_state:
    st.session_state.inputs = {
        'well_type': 'Oil Well (Liquid Dominated)',
        'lithology': 'Sandstone (C=120)',
        'tvd': 10000.0,
        'md': 11500.0,
        'dls': 2.0,
        'casing_id': 8.681,
        'p_wh': 800.0,
        'p_bhp': 4500.0,
        'cithp': 3800.0,
        't_wh': 75.0,
        't_bht': 210.0,
        't_ambient': 75.0,
        'annular_fluid': 'Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)',
        # Oil Well Parameters
        'q_liquid': 5000.0,
        'water_cut': 5.0,
        'gor': 800.0,
        # Gas Well Parameters
        'q_gas_mmscfd': 15.0,
        'cgr_stb_mmscf': 25.0,
        'wgr_bbl_mmscf': 5.0,
        # Fluid & Chemical PVT
        'api_gravity': 35.0,
        'gas_sg': 0.65,
        'water_sg': 1.05,
        'oil_visc': 1.5,
        'co2_mole_pct': 2.5,
        'h2s_ppm': 150.0,
        'ph_val': 6.5,
        'chlorides_ppm': 35000.0,
        # Production Solids & Sand Specs
        'sand_rate_pptb': 0.0,
        'sand_size_microns': 150.0,
        'sand_sg': 2.65,
        'field_life_yrs': 20,
        'decline_rate': 8.0,
        'sf_triaxial': 1.25
    }

if 'tubing_db' not in st.session_state:
    if os.path.exists("tubing_database.csv"):
        st.session_state.tubing_db = pd.read_csv("tubing_database.csv")
    else:
        st.session_state.tubing_db = pd.DataFrame([
            {"Name": '2-3/8" L80-1 (4.6#)', "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.60, "Grade": "L80-1", "UNS_Code": "K08000", "Material": "NACE Carbon Steel", "Connection": "API EUE", "Yield_psi": 80000, "Burst_psi": 11200},
            {"Name": '2-7/8" L80-1 (6.5#)', "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "L80-1", "UNS_Code": "K08000", "Material": "NACE Carbon Steel", "Connection": "API EUE", "Yield_psi": 80000, "Burst_psi": 10570},
            {"Name": '3-1/2" L80-13Cr (9.2#)', "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.20, "Grade": "L80-13Cr", "UNS_Code": "S41000", "Material": "Martensitic Stainless", "Connection": "Premium (VAM Top)", "Yield_psi": 80000, "Burst_psi": 10160},
            {"Name": '3-1/2" P110 (9.2#)', "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.20, "Grade": "P110", "UNS_Code": "K01100", "Material": "High-Strength Alloy", "Connection": "Premium (TenarisHydril)", "Yield_psi": 110000, "Burst_psi": 13970},
            {"Name": '4-1/2" P110 (12.6#)', "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.60, "Grade": "P110", "UNS_Code": "K01100", "Material": "High-Strength Alloy", "Connection": "Premium (VAM Top)", "Yield_psi": 110000, "Burst_psi": 10690},
            {"Name": '9-5/8" P110 (53.5#)', "OD_in": 9.625, "ID_in": 8.535, "Weight_lbft": 53.50, "Grade": "P110", "UNS_Code": "K01100", "Material": "High-Strength Alloy", "Connection": "Premium (TenarisHydril)", "Yield_psi": 110000, "Burst_psi": 10860}
        ])

ANNULAR_FLUID_PROPS = {
    "Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)": {"alpha_v": 2.1e-4, "kappa_t": 3.0e-6},
    "Oil-Based Mud / Synthetic (α_v = 7.0e-4 /°C, κ_T = 5.0e-6 /psi)": {"alpha_v": 7.0e-4, "kappa_t": 5.0e-6},
    "Heavy Zinc/Calcium Brine (α_v = 3.5e-4 /°C, κ_T = 2.5e-6 /psi)": {"alpha_v": 3.5e-4, "kappa_t": 2.5e-6}
}

def compute_dynamic_z_factor(p_psi, t_deg_r, gas_sg):
    p_pc = 756.8 - 131.07 * gas_sg - 3.6 * (gas_sg ** 2)
    t_pc = 169.2 + 349.5 * gas_sg - 74.0 * (gas_sg ** 2)
    p_pr = p_psi / p_pc
    t_pr = t_deg_r / t_pc
    t_r = 1.0 / t_pr
    a = 0.06125 * t_r * np.exp(-1.2 * (1.0 - t_r)**2)
    y = 0.0125 * p_pr * t_r
    z = a * p_pr / y if y > 0 else 0.88
    return float(np.clip(z, 0.65, 1.25))

def run_engineering_calculations(inputs, candidate_df):
    results = []
    
    is_gas_well = "Gas Well" in inputs.get('well_type', 'Oil Well')
    p_wh_val = inputs.get('p_wh', 800.0)
    p_bhp_val = inputs.get('p_bhp', 4500.0)
    p_avg = (p_wh_val + p_bhp_val) / 2.0
    
    t_wh_val = inputs.get('t_wh', 75.0)
    t_bht_val = inputs.get('t_bht', 210.0)
    t_avg_f = (t_wh_val + t_bht_val) / 2.0
    t_avg_r = t_avg_f + 459.67
    t_bht_c = (t_bht_val - 32.0) * (5.0 / 9.0)
    
    casing_id_val = inputs.get('casing_id', 8.681)
    
    # -------------------------------------------------------------------------
    # FLUID & SLURRY PVT & VOLUMETRIC RATE ENGINE
    # -------------------------------------------------------------------------
    api_val = inputs.get('api_gravity', 35.0)
    gas_sg_val = inputs.get('gas_sg', 0.65)
    water_sg_val = inputs.get('water_sg', 1.05)
    
    gamma_o = 141.5 / (131.5 + api_val)
    
    if is_gas_well:
        q_g_scf_d = inputs.get('q_gas_mmscfd', 15.0) * 1e6
        q_cond_stbd = inputs.get('q_gas_mmscfd', 15.0) * inputs.get('cgr_stb_mmscf', 25.0)
        q_wat_stbd = inputs.get('q_gas_mmscfd', 15.0) * inputs.get('wgr_bbl_mmscf', 5.0)
        q_liq_stbd = q_cond_stbd + q_wat_stbd
        
        rs_scf_stb = 0.0
        bo_rb_stb = 1.05
        rho_o_live = 62.4 * gamma_o
        rho_w = water_sg_val * 62.4
        
        q_l_ft3s = (q_liq_stbd * 5.615) / 86400.0
        wc_frac = q_wat_stbd / q_liq_stbd if q_liq_stbd > 0 else 0.0
        rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w if q_liq_stbd > 0 else rho_o_live
    else:
        gor_val = inputs.get('gor', 800.0)
        q_liq_val = inputs.get('q_liquid', 5000.0)
        q_liq_stbd = q_liq_val
        wc_val = inputs.get('water_cut', 5.0)
        
        rs_scf_stb = gas_sg_val * (((p_avg / 18.2) + 1.4) * (10 ** (0.0125 * api_val - 0.00091 * t_avg_f))) ** 1.2048
        rs_scf_stb = min(rs_scf_stb, gor_val)
        
        bo_rb_stb = 0.9759 + 0.000120 * ((rs_scf_stb * ((gas_sg_val / gamma_o) ** 0.5) + 1.25 * t_avg_f) ** 1.2)
        rho_o_live = (62.4 * gamma_o + 0.0136 * rs_scf_stb * gas_sg_val) / bo_rb_stb
        rho_w = water_sg_val * 62.4
        
        wc_frac = wc_val / 100.0
        rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w
        
        q_l_ft3s = (q_liq_val * 5.615) / 86400.0
        q_o_stb = q_liq_val * (1.0 - wc_frac)
        free_gas_gor = max(gor_val - rs_scf_stb, 0.0)
        q_g_scf_d = q_o_stb * free_gas_gor

    z_factor = compute_dynamic_z_factor(p_avg, t_avg_r, gas_sg_val)
    rho_g = (2.7 * gas_sg_val * p_avg) / (z_factor * t_avg_r)
    rho_g = max(rho_g, 0.05)
    
    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg * 520.0 * 86400.0)
    q_m_ft3s = max(q_l_ft3s + q_g_ft3s, 1e-6)
    
    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g
    
    # Solid Particles Slurry Density Integration
    sand_pptb_val = inputs.get('sand_rate_pptb', 0.0)
    sand_d_um = inputs.get('sand_size_microns', 150.0)
    sand_sg_val = inputs.get('sand_sg', 2.65)
    rho_s_lbft3 = sand_sg_val * 62.4
    
    w_s_lb_day = (sand_pptb_val / 1000.0) * q_liq_stbd
    v_sand_ft3d = w_s_lb_day / rho_s_lbft3 if rho_s_lbft3 > 0 else 0.0
    v_liq_ft3d = q_liq_stbd * 5.615
    c_v_solids = v_sand_ft3d / (v_liq_ft3d + v_sand_ft3d) if (v_liq_ft3d + v_sand_ft3d) > 0 else 0.0
    rho_slurry = (1.0 - c_v_solids) * rho_m + c_v_solids * rho_s_lbft3
    
    mu_w_cp = 0.5
    mu_l_cp = (1.0 - wc_frac) * inputs.get('oil_visc', 1.5) + wc_frac * mu_w_cp
    mu_m_cp = lambda_l * mu_l_cp + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672
    
    # Particle Settling Velocity (Rubey Formula) & Oroskar-Turian Solid Transport Criteria
    d_p_ft = (sand_d_um * 1e-6) * 3.28084
    g_const = 32.174
    delta_rho = max(rho_s_lbft3 - rho_slurry, 0.1)
    nu_kinematic = (mu_m_lbfts / rho_slurry) if rho_slurry > 0 else 1e-5
    
    term1 = (2.0 / 3.0) * g_const * d_p_ft * (delta_rho / rho_slurry)
    term2 = (36.0 * (nu_kinematic ** 2)) / (d_p_ft ** 2) if d_p_ft > 0 else 0.0
    v_t_rubey = np.sqrt(term1 + term2) - (6.0 * nu_kinematic / d_p_ft) if d_p_ft > 0 else 0.0
    v_t_rubey = max(v_t_rubey, 0.0)
    
    # Corrosion & Environmental Limits
    h2s_ppm_val = inputs.get('h2s_ppm', 150.0)
    co2_pct_val = inputs.get('co2_mole_pct', 2.5)
    p_h2s_psia = p_bhp_val * (h2s_ppm_val / 1e6)
    p_co2_psia = p_bhp_val * (co2_pct_val / 100.0)
    is_sour_service = p_h2s_psia >= 0.05
    
    # Late Life Hydraulics
    decline_val = inputs.get('decline_rate', 8.0)
    field_life_val = inputs.get('field_life_yrs', 20)
    decline_factor = (1.0 - (decline_val / 100.0)) ** field_life_val
    q_m_late = q_m_ft3s * decline_factor
    
    # Dynamic APB Pressure Rise
    fluid_props = ANNULAR_FLUID_PROPS.get(inputs.get('annular_fluid', ''), ANNULAR_FLUID_PROPS["Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)"])
    alpha_v = fluid_props['alpha_v']
    kappa_t = fluid_props['kappa_t']
    
    t_ambient_val = inputs.get('t_ambient', 75.0)
    delta_t_annular = max(t_avg_f - t_ambient_val, 0.0)
    dp_apb_psi = (alpha_v / kappa_t) * delta_t_annular
    p_annular_total_wh = p_wh_val + dp_apb_psi

    # -------------------------------------------------------------------------
    # CANDIDATE EVALUATION LOOP
    # -------------------------------------------------------------------------
    for _, row in candidate_df.iterrows():
        id_ft = row['ID_in'] / 12.0
        od_ft = row['OD_in'] / 12.0
        area_id_ft2 = (np.pi / 4.0) * (id_ft ** 2)
        area_od_ft2 = (np.pi / 4.0) * (od_ft ** 2)
        area_steel_in2 = (np.pi / 4.0) * (row['OD_in']**2 - row['ID_in']**2)
        
        # Casing Clearance Gate
        casing_clearance_pass = row['OD_in'] < casing_id_val
        
        v_m = q_m_ft3s / area_id_ft2
        v_m_late = q_m_late / area_id_ft2
        
        reynolds = (rho_slurry * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])
        
        if reynolds > 2300:
            f = 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2
        else:
            f = 64.0 / reynolds if reynolds > 0 else 0.04
            
        tvd_val = inputs.get('tvd', 10000.0)
        md_val = inputs.get('md', 11500.0)
        dls_val = inputs.get('dls', 2.0)
        
        dp_hydro = (rho_slurry * tvd_val) / 144.0
        dp_fric = (f * md_val * rho_slurry * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0)
        dp_total = dp_hydro + dp_fric
        
        c_factor = 120.0 if "Sandstone" in inputs.get('lithology', 'Sandstone') else 150.0
        if is_gas_well:
            c_factor -= 20.0
            
        sigma_dynes = 20.0
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        v_carrying = max(v_critical_loading, 1.35 * v_t_rubey)
        
        # Sand Erosion Model (Salama 1983) vs Clean API 14E
        grade_str_upper = str(row['Grade']).upper()
        if w_s_lb_day > 0.1:
            c_salama = 450.0 if ("13CR" in grade_str_upper or "22CR" in grade_str_upper or "25CR" in grade_str_upper or "CRA" in str(row['Material']).upper()) else 200.0
            v_erosional = (c_salama / np.sqrt(rho_slurry)) * np.sqrt(row['ID_in'] / w_s_lb_day)
            v_erosional = min(v_erosional, c_factor / np.sqrt(rho_m))
        else:
            v_erosional = c_factor / np.sqrt(rho_m)
        
        dp_available = p_bhp_val - p_wh_val
        
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_carrying < v_m < v_erosional
        late_life_pass = v_m_late >= v_carrying
        
        # Lubinski Force Balance
        rho_buoy_factor = (1.0 - (rho_slurry / 490.0))
        f_gravity_lbs = row['Weight_lbft'] * md_val * rho_buoy_factor
        f_thermal_lbs = 30e6 * area_steel_in2 * 6.9e-6 * delta_t_annular
        f_piston_lbs = (p_bhp_val * area_id_ft2 * 144.0) - (p_annular_total_wh * (area_od_ft2 - area_id_ft2) * 144.0)
        f_ballooning_lbs = 2.0 * 0.3 * ((p_bhp_val * area_id_ft2 * 144.0) - (p_annular_total_wh * area_od_ft2 * 144.0))
        f_drag_lbs = (f * rho_slurry * (v_m ** 2) * np.pi * id_ft * md_val) / (2.0 * 32.174)
        sigma_bending_psi = 218.0 * row['OD_in'] * dls_val
        
        f_axial_total_lbs = f_gravity_lbs + f_thermal_lbs + f_piston_lbs + f_ballooning_lbs + f_drag_lbs
        f_axial_total_klbs = f_axial_total_lbs / 1000.0
        
        sigma_axial_psi = (f_axial_total_lbs / area_steel_in2) + sigma_bending_psi
        
        p_int = p_bhp_val
        p_ext = p_annular_total_wh
        r_i = row['ID_in'] / 2.0
        r_o = row['OD_in'] / 2.0
        
        sigma_hoop_psi = (p_int * (r_i**2) - p_ext * (r_o**2) + (r_i**2 * r_o**2 * (p_int - p_ext) / (r_i**2))) / (r_o**2 - r_i**2)
        sigma_radial_psi = -p_int
        
        vme_stress_psi = np.sqrt(0.5 * ((sigma_hoop_psi - sigma_radial_psi)**2 + (sigma_radial_psi - sigma_axial_psi)**2 + (sigma_axial_psi - sigma_hoop_psi)**2))
        triaxial_sf = row['Yield_psi'] / vme_stress_psi if vme_stress_psi > 0 else 99.0
        sf_triaxial_target = inputs.get('sf_triaxial', 1.25)
        stress_pass = triaxial_sf >= sf_triaxial_target
        
        # Static CITHP Surface Burst Screening
        cithp_val = inputs.get('cithp', p_wh_val)
        burst_sf = row['Burst_psi'] / cithp_val if cithp_val > 0 else 99.0
        burst_pass = burst_sf >= 1.10

        # Temperature Constraints
        temp_pass = True
        temp_reason = "Compatible"
        grade_str = str(row['Grade']).upper()
        
        if t_bht_c >= 107.0 and grade_str not in ["Q125"]:
            temp_pass = False
            temp_reason = f"Fail: BHT ({round(t_bht_c,1)}°C >= 107°C) requires Grade Q125"
        elif t_bht_c >= 80.0 and grade_str not in ["H40", "N80", "P105", "P110", "Q125"]:
            temp_pass = False
            temp_reason = f"Fail: BHT ({round(t_bht_c,1)}°C >= 80°C) requires H40, N80, P105, P110, or Q125"
        elif t_bht_c >= 65.0 and grade_str not in ["N80", "C95", "T95", "P105", "P110", "Q125"]:
            temp_pass = False
            temp_reason = f"Fail: BHT ({round(t_bht_c,1)}°C >= 65°C) requires N80, C95, T95, or higher"

        # NACE MR0175 / Sour Service Screening
        material_pass = True
        mat_reason = "Compatible"
        
        if is_sour_service:
            if grade_str in ["J-55", "J55", "N-80", "N80", "P-110", "P110"]:
                material_pass = False
                mat_reason = f"Fail: Sour Service (pH2S = {round(p_h2s_psia,3)} psia >= 0.05). Requires L80-1 (26 HRC Max) or CRA."

        # Connection Logic
        conn_reasons = []
        needs_premium = False
        
        if is_gas_well or inputs.get('gor', 0) > 2000 or inputs.get('q_gas_mmscfd', 0) > 10.0:
            needs_premium = True
            conn_reasons.append("High Gas Stream (Metal-to-Metal Seal Required)")
            
        if cithp_val > 3000:
            needs_premium = True
            conn_reasons.append(f"High Static CITHP ({round(cithp_val,0)} psi) - Thread Leak Risk")

        if dp_apb_psi > 1500:
            needs_premium = True
            conn_reasons.append(f"High APB ({round(dp_apb_psi,1)} psi) - Thread Dope Washout Risk")
            
        if "13CR" in grade_str or "22CR" in grade_str or "25CR" in grade_str:
            needs_premium = True
            conn_reasons.append("CRA Metallurgy (High Galling Risk on API Threads)")
            
        if tvd_val > 10000 or f_axial_total_klbs > 150.0:
            needs_premium = True
            conn_reasons.append("High Depth / Axial Load")

        connection_pass = True
        conn_status_msg = "Compatible API Thread"
        
        if needs_premium and row['Connection'] == 'API EUE':
            connection_pass = False
            conn_status_msg = "Premium Connection Required (" + "; ".join(conn_reasons) + ")"
        elif needs_premium and 'Premium' in row['Connection']:
            conn_status_msg = "Premium Connection Validated (" + "; ".join(conn_reasons) + ")"

        overall_pass = (casing_clearance_pass and hydraulics_pass and velocity_pass and late_life_pass and 
                        material_pass and stress_pass and connection_pass and temp_pass and burst_pass)
        
        results.append({
            "Name": row['Name'],
            "OD_in": row['OD_in'],
            "ID_in": row['ID_in'],
            "Grade": row['Grade'],
            "Material": row['Material'],
            "Connection": row['Connection'],
            "Velocity_fts": round(v_m, 2),
            "v_late_life_fts": round(v_m_late, 2),
            "v_erosional": round(v_erosional, 2),
            "v_critical": round(v_critical_loading, 2),
            "v_carrying": round(v_carrying, 2),
            "dp_hydro_psi": round(dp_hydro, 1),
            "dp_fric_psi": round(dp_fric, 1),
            "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(dp_available, 1),
            "dp_apb_psi": round(dp_apb_psi, 1),
            "cithp_psi": round(cithp_val, 1),
            "f_axial_klbs": round(f_axial_total_klbs, 1),
            "vme_stress_psi": round(vme_stress_psi, 0),
            "triaxial_sf": round(triaxial_sf, 2),
            "burst_sf": round(burst_sf, 2),
            "Z_Factor": round(z_factor, 3),
            "Bo_rb_stb": round(bo_rb_stb, 3),
            "Casing_Clearance_Pass": casing_clearance_pass,
            "Hydraulics_Pass": hydraulics_pass,
            "Velocity_Pass": velocity_pass,
            "Late_Life_Pass": late_life_pass,
            "Material_Pass": material_pass,
            "Stress_Pass": stress_pass,
            "Burst_Pass": burst_pass,
            "Temp_Pass": temp_pass,
            "Connection_Pass": connection_pass,
            "Connection_Reason": conn_status_msg,
            "Material_Reason": mat_reason,
            "Temp_Reason": temp_reason,
            "Overall_Pass": overall_pass
        })
        
    return pd.DataFrame(results)

# -----------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/000000/oil-rig.png", width=70)
st.sidebar.title("Tubing Selection Tool")
st.sidebar.caption("Upper-Completion Design Engine")

page = st.sidebar.radio(
    "Select Workflow Step:",
    [
        "1. Introduction & Overview",
        "2. Calculation Methodology",
        "3. Well & Fluid Inputs",
        "4. Candidate Tubing Specs",
        "5. Engineering Calculations",
        "6. Recommendation & Sensitivity"
    ]
)

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    st.markdown('<div class="main-header">Interactive Tubing Selection Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upper-Completion Optimization Engine for Varying Well Conditions</div>', unsafe_allow_html=True)
    
    if os.path.exists("cover.jpg"):
        st.image("cover.jpg", caption="Offshore Production Facility — Upper Completion Overview", use_container_width=True)
    
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A;">
        <h2 style="color: #1E3A8A; font-size: 1.6rem; margin-bottom: 0.8rem; font-weight: 700;">What is Upper Completion?</h2>
        <p style="font-size: 1.05rem; line-height: 1.6; color: #1E293B;">
            The <b>upper completion</b> is the portion of a well completion located <b>above the lower or reservoir completion</b>, extending to the <b>wellhead and surface facilities</b>. It provides the main pathway for <b>produced or injected fluids</b>. Depending on the well requirements, it may include <b>production tubing, packers, subsurface safety valves, artificial lift systems, and chemical-injection systems</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")

    with col1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #3B82F6;">
            <h3 style="color: #1E3A8A; font-size: 1.25rem; margin-bottom: 0.6rem; font-weight: 700;">Upper Completion Configurations</h3>
            <p style="font-size: 0.95rem; line-height: 1.5; color: #475569;">Common configurations include:</p>
            <ul style="font-size: 0.95rem; line-height: 1.7; color: #1E293B; margin-bottom: 0; padding-left: 1.2rem;">
                <li><b>Tubingless completion:</b> fluids flow through the casing.</li>
                <li><b>Tubing without packer:</b> tubing is installed without annular isolation.</li>
                <li><b>Tubing with packer:</b> the packer isolates the tubing–casing annulus.</li>
                <li><b>Dual tubing with packers:</b> provides separate flow paths for multiple zones or fluids.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        if os.path.exists("Figure 1.png"):
            st.image("Figure 1.png", caption="Figure 1: Upper-completion configurations", use_container_width=True)

        st.markdown("""
        <div class="card" style="margin-top: 1rem; border-top: 3px solid #3B82F6;">
            <h3 style="color: #1E3A8A; font-size: 1.25rem; margin-bottom: 0.6rem; font-weight: 700;">Major Design Decisions</h3>
            <p style="font-size: 0.95rem; line-height: 1.5; color: #475569;">Key decisions include:</p>
            <ul style="font-size: 0.95rem; line-height: 1.7; color: #1E293B; margin-bottom: 0; padding-left: 1.2rem;">
                <li><b>Artificial lift:</b> e.g., gas lift or ESP.</li>
                <li><b>Tubing size:</b> balances production capacity and pressure drop.</li>
                <li><b>Completion configuration:</b> single or dual completion.</li>
                <li><b>Tubing isolation:</b> using a <b>packer or equivalent</b> to control fluid communication.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #10B981;">
            <h3 style="color: #1E3A8A; font-size: 1.25rem; margin-bottom: 0.6rem; font-weight: 700;">Key Components</h3>
            <p style="font-size: 0.95rem; line-height: 1.6; color: #1E293B; margin-bottom: 0;">
                Typical components include <b>production tubing, packers, subsurface safety valves (SCSSVs), artificial-lift equipment, and chemical-injection systems</b>. Together, they enable <b>safe fluid transport, well control, well integrity, and future intervention</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if os.path.exists("Figure 2.jpg"):
            st.image("Figure 2.jpg", caption="Figure 2: Typical upper-completion components", use_container_width=True)

    st.markdown("---")
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #059669; margin-top: 1rem;">
        <h2 style="color: #065F46; font-size: 1.6rem; margin-bottom: 0.8rem; font-weight: 700;">Production Tubing: The Flow Path of the Well</h2>
        <p style="font-size: 1.05rem; line-height: 1.6; color: #1E293B;">
            <b>Production tubing</b> is the primary conduit that transports <b>oil, gas, or injected fluids</b> between the reservoir and surface facilities. Its design must balance <b>flow performance, mechanical integrity, and operational requirements</b>. Key considerations include <b>tubing size, wall thickness, steel grade, connection type, and mechanical strength</b>, ensuring the tubing can withstand the pressure, temperature, and loads encountered throughout the well's life.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if os.path.exists("Figure 3.jpg"):
        st.image("Figure 3.jpg", caption="Figure 3 — Production tubing in a completed well", use_container_width=True)

    st.markdown("""
    <div class="card" style="margin-top: 1rem; border-top: 3px solid #059669;">
        <h3 style="color: #065F46; font-size: 1.3rem; margin-bottom: 0.8rem; font-weight: 700;">Key Tubing Specifications</h3>
        <table style="width:100%; border-collapse: collapse; font-size: 0.95rem;">
            <thead>
                <tr style="background-color: #065F46; color: white; text-align: left;">
                    <th style="padding: 12px 16px; border-radius: 6px 0 0 0; width: 30%;">Specification</th>
                    <th style="padding: 12px 16px; border-radius: 0 6px 0 0; width: 70%;">Importance</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #FFFFFF;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Nominal size / OD</td>
                    <td style="padding: 12px 16px; color: #334155;">Determines the overall tubing size and compatibility with the casing.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Internal diameter (ID)</td>
                    <td style="padding: 12px 16px; color: #334155;">Influences <b>fluid velocity and pressure loss</b>.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #FFFFFF;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Drift diameter</td>
                    <td style="padding: 12px 16px; color: #334155;">Determines the maximum equipment diameter that can pass through the tubing.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Nominal weight</td>
                    <td style="padding: 12px 16px; color: #334155;">Indicates tubing weight and is related to <b>wall thickness</b>.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #FFFFFF;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Steel grade</td>
                    <td style="padding: 12px 16px; color: #334155;">Determines <b>strength and suitability for corrosive environments</b>.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Connection</td>
                    <td style="padding: 12px 16px; color: #334155;">Affects connection strength and tubing integrity.</td>
                </tr>
                <tr style="border-bottom: 1px solid #E2E8F0; background-color: #FFFFFF;">
                    <td style="padding: 12px 16px; font-weight: bold; color: #1E293B;">Joint length</td>
                    <td style="padding: 12px 16px; color: #334155;">Influences running and handling operations during completion and workover.</td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    if os.path.exists("Figure 4.png"):
        st.image("Figure 4.png", caption="Figure 4 — Tubing dimensions", use_container_width=True)

    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #DC2626; margin-top: 1.5rem;">
        <h2 style="color: #991B1B; font-size: 1.5rem; margin-bottom: 0.8rem; font-weight: 700;">Model Assumptions & Design Limitations</h2>
        <div style="display: flex; gap: 1rem;">
            <div style="flex: 1;">
                <h4 style="color: #991B1B; font-size: 1.1rem; margin-bottom: 0.4rem;">Key Assumptions</h4>
                <ul style="font-size: 0.95rem; line-height: 1.6; color: #1E293B; margin-bottom: 0; padding-left: 1.2rem;">
                    <li><b>Steady-State Flow:</b> Calculates single-phase gas or homogenized multiphase flow under steady operational conditions.</li>
                    <li><b>Linear Thermal Gradient:</b> Assumes a linear temperature distribution from surface wellhead to bottomhole.</li>
                    <li><b>Isothermal Annular APB:</b> Trapped annular fluid volume expansion relies on single-zone average thermal expansion (α<sub>v</sub>) and isothermal compressibility (κ<sub>T</sub>).</li>
                    <li><b>Uniform Pipe Geometry:</b> Tubing string is evaluated as a single nominal size and weight from surface to TD.</li>
                </ul>
            </div>
            <div style="flex: 1;">
                <h4 style="color: #991B1B; font-size: 1.1rem; margin-bottom: 0.4rem;">Engineering Limitations</h4>
                <ul style="font-size: 0.95rem; line-height: 1.6; color: #1E293B; margin-bottom: 0; padding-left: 1.2rem;">
                    <li><b>Transient Effects:</b> Does not account for dynamic shut-in surges, water hammer, or transient thermal warm-up/cool-down loops.</li>
                    <li><b>Multiphase Flow Regimes:</b> Uses a homogenous fluid mixture model; detailed flow pattern maps (slugging, mist, annular) are simplified.</li>
                    <li><b>Corrosion Kinetics:</b> NACE MR0175 screening is binary (pH<sub>2</sub>S threshold); it does not compute quantitative corrosion rates (mm/year).</li>
                    <li><b>Complex Completion Accessories:</b> Subsurface safety valves (SSSVs) and mandrels are modeled as equivalent hydraulic restrictions rather than detailed localized geometries.</li>
                </ul>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE 2: CALCULATION METHODOLOGY
# -----------------------------------------------------------------------------
elif page == "2. Calculation Methodology":
    st.markdown('<div class="main-header">Step 2: Comprehensive Calculation Methodology</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Step-by-step mathematical guide: mapping wellbore inputs through fluid PVT, sand transport, hydraulics, static CITHP burst, stress analysis, and dual-lifecycle screening.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A; margin-bottom: 1rem;">
        <h3 style="color: #1E3A8A; font-size: 1.2rem; margin-bottom: 0.4rem; font-weight: 700;">🔄 Dual-Lifecycle Candidate Screening Workflow</h3>
        <p style="font-size: 0.9rem; color: #334155; line-height: 1.4; margin-bottom: 0;">
            Tubing selection requires evaluating candidates against a <b>Dual Operational Envelope</b>: <i>Early-Life (Peak Production)</i> and <i>Late-Life (Depleted Reservoir / High Water Cut)</i>, alongside a static <i>Closed-In Tubing Head Pressure (CITHP)</i> surface burst check.
        </p>
    </div>
    """, unsafe_allow_html=True)

    diagram_html = """
<style>
    .funnel-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin: 1.2rem auto 2rem auto;
        max-width: 640px;
        width: 100%;
    }
    .funnel-card {
        width: 100%;
        padding: 10px 14px;
        border-radius: 8px;
        text-align: center;
        font-size: 0.88rem;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid rgba(0,0,0,0.08);
        box-sizing: border-box;
    }
    .funnel-connector {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 34px;
        position: relative;
        width: 100%;
    }
    .funnel-line {
        width: 2px;
        height: 100%;
        background-color: #64748B;
    }
    .funnel-head {
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #64748B;
        position: absolute;
        bottom: 0;
    }
    .funnel-text {
        position: absolute;
        left: calc(50% + 14px);
        font-size: 0.8rem;
        color: #475569;
        white-space: nowrap;
        font-weight: 500;
    }
</style>

<div class="funnel-wrapper">
    <div class="funnel-card" style="background-color: #E2E8F0; color: #0F172A; border-radius: 20px; font-weight: 600;">
        Candidate Database (All Sizes, Weights & Steel Grades)
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Early & Late Life PVT Inputs</div>
    </div>
    <div class="funnel-card" style="background-color: #DBEAFE; color: #1E3A8A; border-left: 4px solid #3B82F6;">
        <b>Step 1: Dynamic Slurry PVT & Density Engine</b><br/>
        <span style="font-size: 0.8rem;">Evaluates live oil/brine, gas/condensate & solid particles slurry density (&rho;<sub>slurry</sub>)</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Slurry Densities (&rho;<sub>slurry</sub>, &rho;<sub>g</sub>)</div>
    </div>
    <div class="funnel-card" style="background-color: #FEF3C7; color: #78350F; border-left: 4px solid #F59E0B;">
        <b>Step 2: Flow Dynamics, Sand Erosion & Carrying Velocity</b><br/>
        <span style="font-size: 0.8rem;">Salama Sand Erosion Limit vs. Rubey & Oroskar-Turian Solid Transport Carrying Velocity</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Hydraulically Compliant Sizes</div>
    </div>
    <div class="funnel-card" style="background-color: #D1FAE5; color: #065F46; border-left: 4px solid #10B981;">
        <b>Step 3: Lubinski Load Balance & Triaxial Yield Matrix</b><br/>
        <span style="font-size: 0.8rem;">Early: Thermal Expansion & APB &nbsp;|&nbsp; Late: Cooling Contraction & Differential Drawdown</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Structurally Sound Pipe</div>
    </div>
    <div class="funnel-card" style="background-color: #EDE9FE; color: #5B21B6; border-left: 4px solid #8B5CF6;">
        <b>Step 4: Shut-In CITHP Burst, Metallurgy & Connection Gate</b><br/>
        <span style="font-size: 0.8rem;">Filter: Static CITHP Surface Burst (SF &ge; 1.10), NACE Sour Service (p<sub>H2S</sub>) & Premium Threads</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Dual-Lifecycle Compliant Candidate</div>
    </div>
    <div class="funnel-card" style="background-color: #059669; color: #FFFFFF; font-weight: 700; font-size: 0.95rem;">
        Optimal Preferred Tubing Candidate (Passes All Hydraulics, Load & Environmental Screenings)
    </div>
</div>
"""
    st.markdown(diagram_html, unsafe_allow_html=True)
    st.markdown("---")

    # STEP 1: FLUID THERMODYNAMICS & IN-SITU DENSITY MODEL
    st.markdown("### Step 1: Dynamic Slurry PVT & In-Situ Density Engine")
    st.caption("Purpose: Determine real fluid and solid slurry properties at subsurface pressure and temperature across operational modes.")
    
    col1_1, col1_2 = st.columns(2)
    with col1_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #3B82F6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">1.1 Oil Well Mode (Standing's Correlations)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Estimates dissolved gas ($R_s$) and oil formation volume factor ($B_o$):</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"R_s = \gamma_g \left[ \left( \frac{P_{avg}}{18.2} + 1.4 \right) 10^{(0.0125 \cdot \text{API} - 0.00091 \cdot T_{avg})} \right]^{1.2048}")
        st.latex(r"B_o = 0.9759 + 0.000120 \left[ R_s \left( \frac{\gamma_g}{\gamma_o} \right)^{0.5} + 1.25 \cdot T_{avg} \right]^{1.2}")
        st.latex(r"\rho_{o,live} = \frac{62.4 \cdot \gamma_o + 0.0136 \cdot R_s \cdot \gamma_g}{B_o}, \quad \rho_l = (1-f_w)\rho_{o,live} + f_w \rho_w")

    with col1_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #3B82F6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">1.2 Gas Well Mode & Bulk Slurry Density ($\rho_{\text{slurry}}$)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Converts gas throughput, liquid ratios, and solid particle concentration ($C_v$) into slurry density:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"C_v = \frac{V_{sand}}{V_{liquid} + V_{sand}}, \quad \rho_{\text{slurry}} = (1 - C_v) \rho_m + C_v \rho_s")
        st.latex(r"\rho_g = \frac{2.7 \cdot \gamma_g \cdot P_{avg}}{Z \cdot T_{avg,R}}, \quad \lambda_l = \frac{q_l}{q_l + q_g}, \quad \rho_m = \lambda_l \rho_l + (1-\lambda_l)\rho_g")

    st.info("🎯 **Step 1 Candidate Gate:** Validates thermodynamic fluid and solid slurry density convergence.")
    st.markdown("---")

    # STEP 2: FLOW DYNAMICS & DUAL VELOCITY WINDOW WITH SAND
    st.markdown("### Step 2: Multiphase Hydraulics, Sand Erosion & Carrying Velocity")
    st.caption("Purpose: Screen mixture velocity ($v_m$) between minimum solid carrying velocity ($v_{\text{carrying}}$) and Salama sand erosion limit ($v_{\text{erosional}}$).")

    col2_1, col2_2 = st.columns(2)
    with col2_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #F59E0B;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">2.1 Total Slurry Pressure Loss (&Delta;P<sub>total</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Combines slurry hydrostatic head and turbulent pipe friction:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\Delta P_{total} = \underbrace{\frac{\rho_{\text{slurry}} \cdot TVD}{144}}_{\Delta P_{hydrostatic}} + \underbrace{\frac{f \cdot MD \cdot \rho_{\text{slurry}} \cdot v_m^2}{2 \cdot g_c \cdot d_i \cdot 144}}_{\Delta P_{friction}}")

    with col2_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #F59E0B;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">2.2 Salama Sand Erosion & Particle Settling Window</h4>
            <p style="font-size: 0.9rem; color: #475569;">Evaluates sand erosional velocity limit (Salama 1983) and Rubey terminal settling carrying velocity:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"v_{\text{erosional, sand}} = \frac{C_{\text{salama}}}{\sqrt{\rho_{\text{slurry}}}} \cdot \sqrt{\frac{d_i}{W_s}} \quad (C_{\text{salama, CRA}}=450, C_{\text{salama, CS}}=200)")
        st.latex(r"v_t = \sqrt{\frac{2}{3} g d_p \left(\frac{\rho_s - \rho_{\text{slurry}}}{\rho_{\text{slurry}}}\right) + 36 \nu^2} - \frac{6 \nu}{d_p}, \quad v_{\text{carrying}} = \max(v_{\text{critical}}, 1.35 v_t)")

    st.warning("🚫 **Step 2 Candidate Gate:** Rejects candidates if Early-Life rate causes pipe sand erosion ($v_m > v_{\text{erosional}}$) OR if Late-Life rate drops below solid transport velocity ($v_m < v_{\text{carrying}}$).")
    st.markdown("---")

    # STEP 3: STRUCTURAL LOAD BALANCE & TRIAXIAL STRESS MATRIX
    st.markdown("### Step 3: Lubinski Net Load Balance & von Mises Triaxial Stress")
    st.caption("Purpose: Verify structural integrity under peak Early-Life thermal expansion/APB and Late-Life cooling tension/differential collapse.")

    col3_1, col3_2 = st.columns(2)
    with col3_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #10B981;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">3.1 Lubinski Net Axial Force Balance (F<sub>axial</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Summates 5 discrete mechanical forces acting along the tubing string length:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}")
        st.latex(r"F_{gravity} = W_{lbft} \cdot MD \left(1 - \frac{\rho_{\text{slurry}}}{490}\right), \quad F_{thermal} = E \cdot A_{steel} \cdot \alpha \cdot \Delta T_{annular}")

    with col3_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #10B981;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">3.2 Lamé Thick-Wall & Triaxial Stress (&sigma;<sub>VME</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Calculates 3D principal stresses (Axial &sigma;<sub>z</sub>, Hoop &sigma;<sub>&theta;</sub>, Radial &sigma;<sub>r</sub>) including dogleg curvature bending:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\sigma_{axial} = \frac{F_{axial}}{A_{steel}} + \underbrace{218 \cdot OD \cdot DLS}_{\sigma_{bending}}")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]} \le \frac{Y_{yield}}{SF_{triaxial}}")

    st.success("🛡️ **Step 3 Candidate Gate:** Rejects candidates failing minimum safety factor limits ($SF_{triaxial} < 1.25$).")
    st.markdown("---")

    # STEP 4: ENVIRONMENTAL & SHUT-IN CITHP BURST SCREENING
    st.markdown("### Step 4: Dynamic APB, Static CITHP Surface Burst & Metallurgy Screening")
    st.caption("Purpose: Evaluate static CITHP surface burst margins, dynamic APB, NACE MR0175 sour service, and connection profile mandates.")

    col4_1, col4_2 = st.columns(2)
    with col4_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #8B5CF6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">4.1 Static CITHP Surface Burst Check & APB</h4>
            <p style="font-size: 0.9rem; color: #475569;">Evaluates surface burst load under static shut-in conditions and trapped annular pressure:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\text{CITHP} = P_{bhp} \cdot e^{-\left(\frac{M \cdot TVD}{Z \cdot R \cdot T_{avg}}\right)}, \quad SF_{burst} = \frac{\text{Candidate Burst Rating [psi]}}{\text{CITHP [psi]}} \ge 1.10")

    with col4_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #8B5CF6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">4.2 NACE MR0175 & Premium Connection Logic</h4>
            <p style="font-size: 0.9rem; color: #475569;">Screens material degradation and mandates gas-tight thread profiles:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"p_{H_2S} = P_{bhp} \times \left( \frac{\text{H}_2\text{S [PPM]}}{10^6} \right) \ge 0.05 \text{ psia}")
        st.markdown("* **Premium Connection Mandate:** Required if Gas Well, GOR $> 2000$, $Q_g > 10 \text{ MMscf/D}$, $\text{CITHP} > 3000\text{ psi}$, $\Delta P_{APB} > 1500\text{ psi}$, Depth $> 10,000\text{ ft}$, or CRA metallurgy.")

    st.error("☣️ **Step 4 Candidate Gate:** Eliminates non-NACE compliant metallurgy, flags static CITHP burst failures, and enforces Premium Connections when APB or gas leak risk is elevated.")

# ----------------------------------------------------------------------------- 
# PAGE 3: WELLBORE & DUAL-LIFECYCLE OPERATIONAL INPUTS
# ----------------------------------------------------------------------------- 
elif page == "3. Well & Fluid Inputs": 
    st.markdown('<div class="main-header">Step 3: Wellbore Geometry & Operational Inputs</div>', unsafe_allow_html=True) 
    st.markdown('<div class="sub-header">Specify wellbore profile, environmental chemistry, solid particles production, rate modes, and static CITHP pressure envelopes.</div>', unsafe_allow_html=True) 

    current_inputs = st.session_state.inputs
    well_type = current_inputs.get('well_type', 'Oil Well (Liquid Dominated)')
    is_gas_type = "Gas" in well_type

    tab_geo, tab_early, tab_late = st.tabs([ 
        "📐 1. Architecture, PVT & Shut-In CITHP",  
        "🚀 2. Early-Life (Initial Production)",  
        "📉 3. Late-Life (Depleted Envelopes)"
    ]) 

    # TAB 1: ARCHITECTURE & SHUT-IN
    with tab_geo: 
        st.markdown("#### 📐 Subsurface Geometry & Dynamic Well Mode") 
        col_g1, col_g2, col_g3 = st.columns(3) 
         
        with col_g1: 
            well_type = st.selectbox(
                "Well Type Category", 
                ["Oil Well (Liquid Dominated)", "Gas Well (Gas / Condensate)"],
                index=1 if is_gas_type else 0
            )
            tvd = st.number_input("True Vertical Depth - TVD (ft)", min_value=1000.0, max_value=30000.0, value=float(current_inputs.get('tvd', 10000.0)), step=100.0, format="%.3f") 
        
        with col_g2:
            md = st.number_input("Measured Depth - MD (ft)", min_value=1000.0, max_value=35000.0, value=float(current_inputs.get('md', 11500.0)), step=100.0, format="%.3f") 
            dls = st.number_input("Max Dogleg Severity - DLS (°/100ft)", min_value=0.0, max_value=15.0, value=float(current_inputs.get('dls', 2.0)), step=0.1, format="%.3f") 

        with col_g3:
            casing_id = st.number_input("Production Casing Inner Diameter - ID (in)", min_value=4.0, max_value=13.375, value=float(current_inputs.get('casing_id', 8.681)), step=0.001, format="%.3f")

        st.markdown("---")
        st.markdown("#### 🛡️ Shut-In Conditions & Static CITHP Pressure")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            calc_cithp = round(current_inputs.get('p_bhp', 4500.0) * np.exp(-0.000035 * tvd), 1)
            cithp_input = st.number_input("Closed-In Tubing Head Pressure - CITHP (psi)", min_value=0.0, max_value=25000.0, value=float(current_inputs.get('cithp', calc_cithp)), step=50.0, format="%.3f")

        with col_s2:
            sf_triaxial = st.number_input("Min Triaxial Safety Factor", min_value=1.0, max_value=2.0, value=float(current_inputs.get('sf_triaxial', 1.25)), step=0.05, format="%.3f")

        with col_s3:
            annular_options = list(ANNULAR_FLUID_PROPS.keys())
            curr_annular = current_inputs.get('annular_fluid', annular_options[0])
            annular_idx = annular_options.index(curr_annular) if curr_annular in annular_options else 0
            annular_fluid = st.selectbox(
                "Trapped Annular Packer Fluid Type", 
                annular_options,
                index=annular_idx
            )

        st.markdown("---")
        st.markdown("#### 🧪 Baseline Fluid PVT, Solids & Corrosivity")
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            api_gravity = st.number_input("Oil/Condensate Gravity (°API)", min_value=10.0, max_value=70.0, value=float(current_inputs.get('api_gravity', 35.0)), step=0.5, format="%.3f")
            gas_sg = st.number_input("Gas Specific Gravity (Air=1.00)", min_value=0.50, max_value=1.20, value=float(current_inputs.get('gas_sg', 0.65)), step=0.01, format="%.3f")
            water_sg = st.number_input("Formation Water SG", min_value=1.00, max_value=1.30, value=float(current_inputs.get('water_sg', 1.05)), step=0.01, format="%.3f")
            sand_rate_pptb = st.number_input("Sand Rate (PPTB - lbs/1000 bbl)", min_value=0.0, max_value=2000.0, value=float(current_inputs.get('sand_rate_pptb', 0.0)), step=5.0, format="%.3f")

        with col_c2:
            h2s_ppm = st.number_input("H₂S Concentration (PPM)", min_value=0.0, max_value=100000.0, value=float(current_inputs.get('h2s_ppm', 150.0)), step=10.0, format="%.3f")
            co2_pct = st.number_input("CO₂ Concentration (Mol %)", min_value=0.0, max_value=50.0, value=float(current_inputs.get('co2_mole_pct', 2.5)), step=0.1, format="%.3f")
            oil_visc = st.number_input("Oil Viscosity (cP)", min_value=0.1, max_value=100.0, value=float(current_inputs.get('oil_visc', 1.5)), step=0.1, format="%.3f")
            sand_size_microns = st.number_input("Average Grain Size (Microns - µm)", min_value=10.0, max_value=2000.0, value=float(current_inputs.get('sand_size_microns', 150.0)), step=10.0, format="%.3f")

        with col_c3:
            ph_val = st.number_input("Formation Water pH", min_value=2.0, max_value=10.0, value=float(current_inputs.get('ph_val', 6.5)), step=0.1, format="%.3f")
            chlorides_ppm = st.number_input("Chlorides (PPM Cl⁻)", min_value=0.0, max_value=250000.0, value=float(current_inputs.get('chlorides_ppm', 35000.0)), step=1000.0, format="%.3f")
            lithology = st.selectbox("Reservoir Lithology", ["Sandstone (C=120)", "Carbonate / Unconsolidated (C=150)"])
            sand_sg = st.number_input("Solid Particle Density (SG)", min_value=1.5, max_value=5.0, value=float(current_inputs.get('sand_sg', 2.65)), step=0.05, format="%.3f")

    # TAB 2: EARLY LIFE
    with tab_early: 
        st.markdown("#### Early-Life Operating Conditions (Peak Rates & Thermal Loads)") 
        col_e1, col_e2, col_e3 = st.columns(3) 

        with col_e1: 
            p_bhp_early = st.number_input("Early BHP (psi)", min_value=500.0, max_value=20000.0, value=float(current_inputs.get('p_bhp', 4500.0)), step=50.0, format="%.3f") 
            p_wh_early = st.number_input("Early Wellhead Pressure (psi)", min_value=50.0, max_value=5000.0, value=float(current_inputs.get('p_wh', 800.0)), step=20.0, format="%.3f") 

        with col_e2: 
            if "Gas" in well_type:
                q_gas_early = st.number_input("Early Gas Rate (MMscf/D)", min_value=0.1, max_value=200.0, value=float(current_inputs.get('q_gas_mmscfd', 15.0)), step=0.5, format="%.3f")
                cgr_early = st.number_input("Early Condensate-Gas Ratio - CGR (STB/MMscf)", min_value=0.0, max_value=500.0, value=float(current_inputs.get('cgr_stb_mmscf', 25.0)), step=1.0, format="%.3f")
                q_liq_early, wc_early, gor_early = 0.0, 0.0, 0.0
            else:
                q_liq_early = st.number_input("Early Liquid Rate (STB/D)", min_value=100.0, max_value=50000.0, value=float(current_inputs.get('q_liquid', 5000.0)), step=100.0, format="%.3f") 
                wc_early = st.number_input("Early Water Cut (%)", min_value=0.0, max_value=100.0, value=float(current_inputs.get('water_cut', 5.0)), step=0.5, format="%.3f") 
                q_gas_early, cgr_early, wgr_early = 0.0, 0.0, 0.0

        with col_e3: 
            if "Gas" in well_type:
                wgr_early = st.number_input("Early Water-Gas Ratio - WGR (bbl/MMscf)", min_value=0.0, max_value=200.0, value=float(current_inputs.get('wgr_bbl_mmscf', 5.0)), step=0.5, format="%.3f")
            else:
                gor_early = st.number_input("Early Producing GOR (scf/STB)", min_value=0.0, max_value=20000.0, value=float(current_inputs.get('gor', 800.0)), step=50.0, format="%.3f") 
            bht_early = st.number_input("Early Bottomhole Temp - BHT (°F)", min_value=80.0, max_value=400.0, value=float(current_inputs.get('t_bht', 210.0)), step=1.0, format="%.3f") 

    # TAB 3: LATE LIFE
    with tab_late: 
        st.markdown("#### Late-Life Operating Conditions (Depletion & High Water Cut)") 
        col_l1, col_l2, col_l3 = st.columns(3) 

        with col_l1: 
            decline_rate = st.number_input("Annual Field Decline Rate (%)", min_value=0.0, max_value=30.0, value=float(current_inputs.get('decline_rate', 8.0)), step=0.5, format="%.3f")
            field_life = st.number_input("Target Field Life (Years)", min_value=1, max_value=40, value=int(current_inputs.get('field_life_yrs', 20)), step=1)

        with col_l2:
            st.info("💡 Late-life flow rates are automatically estimated using annual reservoir decline multipliers.")

    st.markdown("---")
    
    # DUAL OPERATIONAL ENVELOPE SUMMARY MATRIX
    st.markdown("### 📊 Dual Operational Envelope Summary")
    
    if "Gas" in well_type:
        rate_summary_early = f"{q_gas_early:.2f} MMscf/D (CGR: {cgr_early:.1f} STB/MMscf)"
        rate_summary_late = f"{(q_gas_early * ((1 - decline_rate/100.0)**field_life)):.2f} MMscf/D"
        governing_msg = "Salama sand erosion v_m < v_eros (Early) vs. Solid transport v_m > v_carrying (Late)"
    else:
        rate_summary_early = f"{q_liq_early:.1f} STB/D ({wc_early:.1f}% WC)"
        rate_summary_late = f"{(q_liq_early * ((1 - decline_rate/100.0)**field_life)):.1f} STB/D"
        governing_msg = "Peak production velocity (Early) vs. Hydrostatic head drawdown (Late)"

    summary_html = f""" 
    <table style="width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 0.88rem;"> 
        <thead> 
            <tr style="background-color: #1E3A8A; color: white; text-align: left;"> 
                <th style="padding: 10px; border-radius: 4px 0 0 0;">Parameter</th> 
                <th style="padding: 10px;">🚀 Early-Life Baseline</th> 
                <th style="padding: 10px;">📉 Late-Life Baseline</th> 
                <th style="padding: 10px; border-radius: 0 4px 0 0;">Governing Design Challenge</th> 
            </tr> 
        </thead> 
        <tbody> 
            <tr style="border-bottom: 1px solid #E2E8F0;"> 
                <td style="padding: 10px; font-weight: 600;">Bottomhole Pressure (P<sub>bhp</sub>)</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{p_bhp_early:.1f} psi</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{(p_bhp_early * 0.5):.1f} psi</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Peak H₂S partial pressure (Early) vs. Drawdown head limit (Late)</td> 
            </tr> 
            <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;"> 
                <td style="padding: 10px; font-weight: 600;">Flow Rate & Sand PPTB</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{rate_summary_early} | Sand: {sand_rate_pptb} PPTB</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{rate_summary_late}</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">{governing_msg}</td> 
            </tr> 
            <tr style="border-bottom: 1px solid #E2E8F0;"> 
                <td style="padding: 10px; font-weight: 600;">Shut-In CITHP</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{cithp_input:.1f} psi</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{(cithp_input * 0.7):.1f} psi</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Static surface pipe burst safety factor (SF_burst >= 1.10)</td> 
            </tr> 
        </tbody> 
    </table> 
    """ 
    st.markdown(summary_html, unsafe_allow_html=True) 
    st.markdown("<br/>", unsafe_allow_html=True) 

    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1]) 
    with col_btn2: 
        if st.button("💾 Save Operational Baseline & Lifecycle State", type="primary", use_container_width=True): 
            st.session_state.inputs.update({ 
                "well_type": well_type,
                "tvd": tvd, "md": md, "dls": dls, "casing_id": casing_id,
                "cithp": cithp_input, "sf_triaxial": sf_triaxial, "annular_fluid": annular_fluid,
                "api_gravity": api_gravity, "gas_sg": gas_sg, "water_sg": water_sg, "oil_visc": oil_visc,
                "h2s_ppm": h2s_ppm, "co2_mole_pct": co2_pct, "ph_val": ph_val, "chlorides_ppm": chlorides_ppm,
                "sand_rate_pptb": sand_rate_pptb, "sand_size_microns": sand_size_microns, "sand_sg": sand_sg,
                "lithology": lithology, "p_bhp": p_bhp_early, "p_wh": p_wh_early, "t_bht": bht_early,
                "decline_rate": decline_rate, "field_life_yrs": field_life
            })
            if "Gas" in well_type:
                st.session_state.inputs.update({
                    "q_gas_mmscfd": q_gas_early, "cgr_stb_mmscf": cgr_early, "wgr_bbl_mmscf": wgr_early
                })
            else:
                st.session_state.inputs.update({
                    "q_liquid": q_liq_early, "water_cut": wc_early, "gor": gor_early
                })
            st.success("✅ Operational inputs saved! Proceed to Page 5 to view candidate screening calculations.")

# -----------------------------------------------------------------------------
# PAGE 4: CANDIDATE TUBING SPECS
# -----------------------------------------------------------------------------
elif page == "4. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 4: Candidate Tubing Database</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Manage standard API tubing & casing dimensions (up to 9.625" OD), steel grades, UNS designations, and mechanical limits.</div>', unsafe_allow_html=True)
    
    st.subheader("🔍 Database Filter Controls")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_sizes = st.multiselect(
            "Filter by Outer Diameter (OD):", 
            options=sorted(st.session_state.tubing_db['OD_in'].unique()),
            default=sorted(st.session_state.tubing_db['OD_in'].unique())
        )
    with col_f2:
        selected_grades = st.multiselect(
            "Filter by Steel Grade:", 
            options=sorted(st.session_state.tubing_db['Grade'].unique()),
            default=sorted(st.session_state.tubing_db['Grade'].unique())
        )

    filtered_db = st.session_state.tubing_db[
        (st.session_state.tubing_db['OD_in'].isin(selected_sizes)) & 
        (st.session_state.tubing_db['Grade'].isin(selected_grades))
    ]
    
    st.dataframe(filtered_db, use_container_width=True, height=450)
    
    with st.expander("➕ Add Custom Tubing Candidate"):
        with st.form("add_candidate_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                c_name = st.text_input("Candidate Name", value='3-1/2" P110 (9.2#)')
                c_od = st.number_input("Outer Diameter (OD) [in]", value=3.500, min_value=1.0, max_value=12.0)
                c_yield = st.number_input("Yield Strength [psi]", value=110000, min_value=30000, max_value=180000)
            with col2:
                c_id = st.number_input("Inner Diameter (ID) [in]", value=2.992, min_value=0.5, max_value=11.0)
                c_weight = st.number_input("Nominal Weight [lb/ft]", value=9.2, min_value=1.0, max_value=100.0)
                c_burst = st.number_input("Burst Pressure Rating [psi]", value=13970, min_value=1000, max_value=30000)
            with col3:
                c_grade = st.selectbox("Steel Grade", ["H40", "J-55", "K-55", "M65", "C75", "L80-1", "N80", "C95", "T95", "L80-13Cr", "S13Cr-110", "17Cr-110", "22Cr-110", "25Cr-125", "P110", "Q125"])
                c_mat = st.selectbox("Material Class", ["Carbon Steel", "NACE Carbon Steel", "Martensitic Stainless", "Super Martensitic CRA", "Enhanced Martensitic CRA", "Duplex Stainless", "Super Duplex CRA", "High-Strength Alloy"])
                c_conn = st.selectbox("Connection Profile", ["API EUE", "API NUE", "Premium (VAM Top)", "Premium (TenarisHydril)"])
                c_uns = st.text_input("UNS Designation Code", value="K01100")
                                
            add_sub = st.form_submit_button("Add Candidate to Database")
            if add_sub:
                if c_id >= c_od:
                    st.error("Validation Error: Inner Diameter (ID) must be strictly less than Outer Diameter (OD).")
                else:
                    new_row = pd.DataFrame([{
                        "Name": c_name, "OD_in": c_od, "ID_in": c_id, "Weight_lbft": c_weight,
                        "Grade": c_grade, "UNS_Code": c_uns, "Material": c_mat, "Connection": c_conn, 
                        "Yield_psi": c_yield, "Burst_psi": c_burst
                    }])
                    st.session_state.tubing_db = pd.concat([st.session_state.tubing_db, new_row], ignore_index=True)
                    st.success(f"Added {c_name} ({c_conn}) to active candidate database!")
                    st.rerun()

# -----------------------------------------------------------------------------
# PAGE 5: ENGINEERING CALCULATIONS
# -----------------------------------------------------------------------------
elif page == "5. Engineering Calculations":
    st.markdown('<div class="main-header">Step 5: Engineering Calculation Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluates dynamic PVT, pressure losses, velocity screening, APB, static CITHP burst, and Lubinski stress.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs.get('well_type', 'Oil Well')} Mode)")
    
    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts', 'v_carrying', 'v_erosional',
        'dp_total_psi', 'dp_apb_psi', 'cithp_psi', 'f_axial_klbs', 'vme_stress_psi', 'triaxial_sf', 'burst_sf', 'Material_Reason', 'Temp_Reason', 'Overall_Pass'
    ]].copy()
    
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)', 'Min Carrying Vel (ft/s)', 'Erosional Limit (ft/s)',
        'Total dP (psi)', 'APB Pressure (psi)', 'CITHP (psi)', 'Axial Load (klbs)', 'von Mises Stress (psi)', 'Triaxial SF', 'Burst SF', 'NACE Status', 'Temp Status', 'Overall Status'
    ]
    
    st.dataframe(display_df, use_container_width=True, height=450)
    
    with st.expander("📐 Show Governing Equations & Technical Correlations"):
        st.markdown("#### 1. Salama Sand Erosion Correlation (1983)")
        st.latex(r"v_{\text{erosional, sand}} = \frac{C_{\text{salama}}}{\sqrt{\rho_{\text{slurry}}}} \cdot \sqrt{\frac{d_i}{W_s}}")
        st.caption("Where $C_{\\text{salama}} = 450$ for 13Cr/CRA and $200$ for Carbon Steel; $W_s$ is sand rate in lb/day.")

        st.markdown("#### 2. Rubey Terminal Settling & Oroskar-Turian Transport Velocity")
        st.latex(r"v_t = \sqrt{\frac{2}{3} g d_p \left(\frac{\rho_s - \rho_{\text{slurry}}}{\rho_{\text{slurry}}}\right) + 36 \nu^2} - \frac{6 \nu}{d_p}, \quad v_{\text{carrying}} = \max(v_{\text{critical}}, 1.35 v_t)")
        st.caption("Calculates particle settling velocity to ensure minimum fluid velocity prevents sand deposition.")

        st.markdown("#### 3. Annular Pressure Build-up (APB)")
        st.latex(r"\Delta P_{APB} = \left( \frac{\alpha_v}{\kappa_T} \right) \Delta T_{annular}")
        st.caption("Where $\\alpha_v$ is thermal expansion coefficient and $\\kappa_T$ is fluid isothermal compressibility.")
        
        st.markdown("#### 4. Lubinski Total Net Axial Load Balance")
        st.latex(r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}")

        st.markdown("#### 5. von Mises Triaxial Equivalent Stress")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]} \le \frac{Y_{yield}}{SF_{triaxial}}")

# -----------------------------------------------------------------------------
# PAGE 6: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "6. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 6: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, structural/burst checks, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    passed_candidates = res_df[res_df['Overall_Pass'] == True]
    is_gas = "Gas" in st.session_state.inputs.get('well_type', 'Oil')
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            
            st.success("### Preferred Candidate")
            st.markdown(f"## **{preferred['Name']}**")
            st.metric("Total Pressure Drop", f"{preferred['dp_total_psi']} psi")
            st.metric("Flow Velocity", f"{preferred['Velocity_fts']} ft/s")
            st.metric("Material Grade", f"{preferred['Grade']}")
            st.metric("Connection Type", f"{preferred['Connection']}")
            st.metric("Triaxial Safety Factor", f"{preferred['triaxial_sf']} (SF >= 1.25)")
            st.metric("Surface Burst SF (CITHP)", f"{preferred['burst_sf']} (SF >= 1.10)")
            st.metric("APB Pressure Rise", f"{preferred['dp_apb_psi']} psi")
        else:
            st.error("### No Candidates Passed All Screenings!")
            st.warning("Consider increasing bottomhole pressure, selecting higher steel grades (e.g., P110/Q125 for CITHP burst), or upgrading to premium connections.")

    with col2:
        st.subheader("Engineering Justification Rationale")
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            
            rate_str = (
                f"**{st.session_state.inputs.get('q_gas_mmscfd', 15.0)} MMscf/D** gas with **{st.session_state.inputs.get('cgr_stb_mmscf', 25.0)} STB/MMscf** condensate"
                if is_gas else
                f"**{st.session_state.inputs.get('q_liquid', 5000.0)} STB/D** liquid with **{st.session_state.inputs.get('water_cut', 5.0)}%** water cut"
            )
            
            st.markdown(f"""
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**). Dynamic Z-factor (**{preferred['Z_Factor']}**) confirms live fluid conditions at rate of {rate_str}.
            * **Velocity Window:** Initial flow velocity (**{preferred['Velocity_fts']} ft/s**) and late-life velocity (**{preferred['v_late_life_fts']} ft/s**) remain safely above minimum sand carrying limit (**{preferred['v_carrying']} ft/s**) and below Salama sand erosion threshold (**{preferred['v_erosional']} ft/s**).
            * **Shut-In CITHP & Surface Integrity:** Closed-In Tubing Head Pressure of **{preferred['cithp_psi']} psi** yields a static burst safety factor of **{preferred['burst_sf']}** (exceeding $SF \ge 1.10$).
            * **NACE & Structural Safety:** Grade **{preferred['Grade']}** ({preferred['Material']}) provides a von Mises triaxial SF of **{preferred['triaxial_sf']}** under Lubinski axial tension (**{preferred['f_axial_klbs']} klbs**) and APB rise (**{preferred['dp_apb_psi']} psi**).
            * **Connection Validation:** {preferred['Connection_Reason']}
            """)
        else:
            st.write("Review the calculation matrix on Page 5 to identify specific failure flags (velocity, hydraulics, APB, CITHP burst, temperature, or NACE sour service).")

    # -------------------------------------------------------------------------
    # GEMINI AI EXECUTIVE SUMMARY ENGINE
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🤖 AI-Powered Executive Completion Memo")
    st.caption("Generates a dynamic technical narrative grounded strictly on Python calculation outputs.")

    if st.button("✨ Generate AI Executive Summary", type="primary"):
        raw_key = st.secrets.get("GEMINI_API_KEY", "")
        api_key = raw_key.strip().replace('"', '').replace("'", "")
        
        if not api_key:
            st.error("⚠️ GEMINI_API_KEY not found in Streamlit Secrets! Please add it in App Settings -> Secrets.")
        elif passed_candidates.empty:
            st.warning("Cannot generate executive report: No tubing candidates passed all technical screening thresholds.")
        else:
            with st.spinner("Analyzing hydraulics, CITHP burst loads, velocity windows, and NACE compliance via Gemini API..."):
                try:
                    pref = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
                    
                    if is_gas:
                        production_context = f"""
                        - Operating Mode: Gas / Condensate Well
                        - Gas Production Rate (Qg): {st.session_state.inputs.get('q_gas_mmscfd', 15.0)} MMscf/D
                        - Condensate-Gas Ratio (CGR): {st.session_state.inputs.get('cgr_stb_mmscf', 25.0)} STB/MMscf
                        - Water-Gas Ratio (WGR): {st.session_state.inputs.get('wgr_bbl_mmscf', 5.0)} bbl/MMscf
                        """
                    else:
                        production_context = f"""
                        - Operating Mode: Oil Well (Liquid Dominated)
                        - Liquid Production Rate (Qliq): {st.session_state.inputs.get('q_liquid', 5000.0)} STB/D
                        - Water Cut: {st.session_state.inputs.get('water_cut', 5.0)} %
                        - Producing GOR: {st.session_state.inputs.get('gor', 800.0)} scf/STB
                        """

                    prompt_text = f"""
                    You are a Senior Completion Engineer writing an executive technical recommendation memo for an asset manager.
                    Synthesize the following PRE-CALCULATED Python engineering data into a concise, professional technical assessment.
                    DO NOT re-calculate or alter any numerical values. Rely STRICTLY on these provided facts:

                    WELL & OPERATIONAL PARAMETERS:
                    - Well Type: {st.session_state.inputs.get('well_type', 'Oil Well')}
                    {production_context}
                    - Reservoir Lithology: {st.session_state.inputs.get('lithology', 'Sandstone')}
                    - Sand Production Specs: {st.session_state.inputs.get('sand_rate_pptb', 0.0)} PPTB, Grain Size {st.session_state.inputs.get('sand_size_microns', 150.0)} microns
                    - Measured Depth / TVD: {st.session_state.inputs.get('md', 11500.0)} ft / {st.session_state.inputs.get('tvd', 10000.0)} ft (Dogleg Severity: {st.session_state.inputs.get('dls', 2.0)} deg/100ft)
                    - Wellhead / Bottomhole Pressure: {st.session_state.inputs.get('p_wh', 800.0)} psi / {st.session_state.inputs.get('p_bhp', 4500.0)} psi (Available Drawdown: {pref['dp_avail_psi']} psi)
                    - Static Closed-In Tubing Head Pressure (CITHP): {pref['cithp_psi']} psi
                    - Annular Fluid & APB Pressure Rise: {st.session_state.inputs.get('annular_fluid', '')} (Calculated APB Rise: {pref['dp_apb_psi']} psi)
                    - Target Field Life: {st.session_state.inputs.get('field_life_yrs', 20)} Years at {st.session_state.inputs.get('decline_rate', 8.0)}% Annual Decline Rate
                    - CO2 / H2S Concentrations: {st.session_state.inputs.get('co2_mole_pct', 2.5)} mole% CO2, {st.session_state.inputs.get('h2s_ppm', 150.0)} PPM H2S

                    SELECTED PREFERRED TUBING CANDIDATE:
                    - Candidate Name: {pref['Name']}
                    - Steel Grade / Material: {pref['Grade']} ({pref['Material']})
                    - Thread / Connection Type: {pref['Connection']}
                    - Total Calculated Pressure Drop: {pref['dp_total_psi']} psi (Hydrostatic: {pref['dp_hydro_psi']} psi, Friction: {pref['dp_fric_psi']} psi)
                    - Net Lubinski Axial Force: {pref['f_axial_klbs']} klbs
                    - von Mises Triaxial Stress: {pref['vme_stress_psi']} psi (Triaxial Safety Factor: {pref['triaxial_sf']})
                    - Static Surface Burst Safety Factor (CITHP): {pref['burst_sf']} (Rating: {pref['cithp_psi']} psi CITHP vs Candidate Burst Limit)
                    - Initial Flow Velocity: {pref['Velocity_fts']} ft/s
                    - Year {st.session_state.inputs.get('field_life_yrs', 20)} Late-Life Velocity: {pref['v_late_life_fts']} ft/s
                    - Minimum Sand Carrying Limit: {pref['v_carrying']} ft/s
                    - Salama Max Sand Erosional Velocity Limit: {pref['v_erosional']} ft/s
                    - Connection Evaluation Rationale: {pref['Connection_Reason']}

                    INSTRUCTIONS:
                    1. Write an executive memo starting with TO, FROM, and SUBJECT lines.
                    2. Paragraph 1: Recommend the candidate size, grade, and connection type, justifying hydraulic performance against available drawdown drive under the given rate profile.
                    3. Paragraph 2: Analyze flow velocities (initial vs late-life) against Rubey sand carrying velocity and Salama sand erosion thresholds.
                    4. Paragraph 3: Detail static shut-in CITHP burst safety factor, Lubinski triaxial safety factor (SF_vme), thermal APB expansion, and justify connection selection (API EUE vs Premium metal seal) considering gas tightness and NACE MR0175 sour service requirements.
                    5. Use formal petroleum completion engineering phrasing and bold key numeric values.
                    """

                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                    payload = {
                        "contents": [{"parts": [{"text": prompt_text}]}],
                        "generationConfig": {"temperature": 0.2}
                    }
                    
                    headers = {
                        'Content-Type': 'application/json',
                        'x-goog-api-key': api_key
                    }
                    
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode('utf-8'),
                        headers=headers,
                        method='POST'
                    )

                    with urllib.request.urlopen(req) as response:
                        res_data = json.loads(response.read().decode('utf-8'))
                        ai_text = res_data['candidates'][0]['content']['parts'][0]['text']

                    st.markdown("""
                    <div style="background-color: #F0F9FF; border: 1px solid #BAE6FD; border-left: 5px solid #0284C7; border-radius: 8px; padding: 1.25rem; margin-top: 1rem;">
                    """, unsafe_allow_html=True)
                    st.markdown(ai_text)
                    st.markdown("</div>", unsafe_allow_html=True)

                except urllib.error.HTTPError as http_err:
                    error_body = http_err.read().decode('utf-8')
                    st.error(f"Gemini API HTTP Error {http_err.code}: {error_body}")
                except Exception as e:
                    st.error(f"Error calling Gemini API: {str(e)}")

    # -------------------------------------------------------------------------
    # INTERACTIVE SENSITIVITY PLOTS
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("Interactive Sensitivity Plots")
    
    tab1, tab2 = st.tabs(["Pressure Drop vs. Tubing ID", "Velocity Window vs. Tubing ID"])
    
    with tab1:
        fig_dp = px.line(
            res_df, x="ID_in", y="dp_total_psi", color="Grade", markers=True,
            title="Total Pressure Drop vs. Tubing Inner Diameter (ID)",
            labels={"ID_in": "Inner Diameter (inches)", "dp_total_psi": "Total Pressure Drop (psi)"},
            hover_data=["Name", "Velocity_fts", "Overall_Pass"]
        )
        fig_dp.update_traces(marker=dict(size=10))
        fig_dp.add_hline(
            y=res_df['dp_avail_psi'].iloc[0], 
            line_dash="dash", 
            line_color="red", 
            annotation_text="Available Drawdown Limit",
            annotation_position="bottom right"
        )
        
        max_dp = max(res_df['dp_total_psi'].max(), res_df['dp_avail_psi'].iloc[0])
        fig_dp.update_layout(yaxis=dict(range=[0, max_dp * 1.15]), margin=dict(t=50, b=40))
        
        st.plotly_chart(fig_dp, use_container_width=True)

    with tab2:
        fig_v = go.Figure()
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['Velocity_fts'], mode='lines+markers', name='Initial Flow Velocity'))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_late_life_fts'], mode='lines+markers', name='Late-Life Flow Velocity', line=dict(dash='dash', color='purple')))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_erosional'], mode='lines', name='Salama Sand Erosional Limit (Max)', line=dict(dash='dash', color='red')))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_carrying'], mode='lines', name='Min Sand Carrying Limit', line=dict(dash='dot', color='orange')))
        
        fig_v.update_layout(
            title="Flow Velocity Window vs. Tubing Inner Diameter",
            xaxis_title="Inner Diameter (inches)",
            yaxis_title="Velocity (ft/s)",
            margin=dict(t=50, b=40)
        )
        st.plotly_chart(fig_v, use_container_width=True)
        
        st.info(
            "**How to Interpret Graph 2:**\n\n"
            "* **Upper Red Limit (Salama Sand Erosional Velocity):** Operating above this threshold causes severe mechanical wall thinning due to high kinetic sand impact.\n"
            "* **Lower Orange Limit (Minimum Sand Carrying Velocity):** Operating below this threshold causes solid particle deposition, downhole sand plugging, and SCSSV malfunction.\n"
            "* **Purple Dashed Line (Late-Life Velocity):** Tubing must keep the purple line above the orange limit across the target field life."
        )