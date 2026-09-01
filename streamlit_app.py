import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

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
        'well_type': 'Oil Well',
        'lithology': 'Sandstone',
        'tvd': 8000.0,
        'md': 9500.0,
        'dls': 1.5,
        'p_wh': 500.0,
        'p_bhp': 3200.0,
        't_wh': 80.0,
        't_bht': 180.0,
        't_ambient': 60.0,
        'annular_fluid': 'Fresh Water / Light Brine',
        'q_liquid': 3500.0,
        'water_cut': 25.0,
        'gor': 600.0,
        'api_gravity': 35.0,
        'gas_sg': 0.65,
        'water_sg': 1.02,
        'oil_visc': 1.5,
        'co2_mole_pct': 3.5,
        'h2s_ppm': 50.0,
        'ph_val': 5.5,
        'chlorides_ppm': 25000.0,
        'field_life_yrs': 15,
        'decline_rate': 8.0
    }

if 'tubing_db' not in st.session_state:
    if os.path.exists("tubing_database.csv"):
        st.session_state.tubing_db = pd.read_csv("tubing_database.csv")
    else:
        st.session_state.tubing_db = pd.DataFrame([
            {"Name": '2-3/8" L80-1 (4.6#)', "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.60, "Grade": "L80-1", "UNS_Code": "K08000", "Material": "NACE Carbon Steel", "Connection": "API EUE", "Yield_psi": 80000, "Burst_psi": 11200},
            {"Name": '3-1/2" L80-13Cr (9.2#)', "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.20, "Grade": "L80-13Cr", "UNS_Code": "S41000", "Material": "Martensitic Stainless", "Connection": "Premium (VAM Top)", "Yield_psi": 80000, "Burst_psi": 10160},
            {"Name": '9-5/8" P110 (53.5#)', "OD_in": 9.625, "ID_in": 8.535, "Weight_lbft": 53.50, "Grade": "P110", "UNS_Code": "K01100", "Material": "High-Strength Alloy", "Connection": "Premium (TenarisHydril)", "Yield_psi": 110000, "Burst_psi": 10860}
        ])

ANNULAR_FLUID_PROPS = {
    "Fresh Water / Light Brine": {"alpha_v": 2.1e-4, "kappa_t": 3.0e-6},
    "Heavy Brine (CaCl2/ZnBr2)": {"alpha_v": 3.0e-4, "kappa_t": 3.2e-6},
    "Oil-Based Packer Fluid (OBM)": {"alpha_v": 4.5e-4, "kappa_t": 5.5e-6}
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
    
    p_avg = (inputs['p_wh'] + inputs['p_bhp']) / 2.0
    t_avg_f = (inputs['t_wh'] + inputs['t_bht']) / 2.0
    t_avg_r = t_avg_f + 459.67
    t_bht_c = (inputs['t_bht'] - 32.0) * (5.0 / 9.0)
    
    gamma_o = 141.5 / (131.5 + inputs['api_gravity'])
    rs_scf_stb = inputs['gas_sg'] * (((p_avg / 18.2) + 1.4) * (10 ** (0.0125 * inputs['api_gravity'] - 0.00091 * t_avg_f))) ** 1.2048
    rs_scf_stb = min(rs_scf_stb, inputs['gor'])
    
    bo_rb_stb = 0.9759 + 0.000120 * ((rs_scf_stb * ((inputs['gas_sg'] / gamma_o) ** 0.5) + 1.25 * t_avg_f) ** 1.2)
    rho_o_live = (62.4 * gamma_o + 0.0136 * rs_scf_stb * inputs['gas_sg']) / bo_rb_stb
    rho_w = inputs['water_sg'] * 62.4
    
    wc_frac = inputs['water_cut'] / 100.0
    rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w
    
    z_factor = compute_dynamic_z_factor(p_avg, t_avg_r, inputs['gas_sg'])
    rho_g = (2.7 * inputs['gas_sg'] * p_avg) / (z_factor * t_avg_r)
    rho_g = max(rho_g, 0.05)
        
    q_l_ft3s = (inputs['q_liquid'] * 5.615) / 86400.0
    q_o_stb = inputs['q_liquid'] * (1.0 - wc_frac)
    free_gas_gor = max(inputs['gor'] - rs_scf_stb, 0.0)
    q_g_scf_d = q_o_stb * free_gas_gor
    
    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg * 520.0 * 86400.0)
    q_m_ft3s = max(q_l_ft3s + q_g_ft3s, 1e-6)
    
    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g
    
    mu_w_cp = 0.5
    mu_l_cp = (1.0 - wc_frac) * inputs['oil_visc'] + wc_frac * mu_w_cp
    mu_m_cp = lambda_l * mu_l_cp + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672
    
    # Partial Pressures for NACE Screening
    p_h2s_psia = inputs['p_bhp'] * (inputs['h2s_ppm'] / 1e6)
    p_co2_psia = inputs['p_bhp'] * (inputs['co2_mole_pct'] / 100.0)
    is_sour_service = p_h2s_psia >= 0.05
    
    late_life_q = inputs['q_liquid'] * ((1.0 - (inputs['decline_rate'] / 100.0)) ** inputs['field_life_yrs'])
    q_m_late = (late_life_q * 5.615 / 86400.0) + q_g_ft3s
    
    fluid_props = ANNULAR_FLUID_PROPS.get(inputs['annular_fluid'], ANNULAR_FLUID_PROPS["Fresh Water / Light Brine"])
    alpha_v = fluid_props['alpha_v']
    kappa_t = fluid_props['kappa_t']
    
    delta_t_annular = max(t_avg_f - inputs['t_ambient'], 0.0)
    dp_apb_psi = (alpha_v / kappa_t) * delta_t_annular
    p_annular_total_wh = inputs['p_wh'] + dp_apb_psi
    
    for _, row in candidate_df.iterrows():
        id_ft = row['ID_in'] / 12.0
        od_ft = row['OD_in'] / 12.0
        area_id_ft2 = (np.pi / 4.0) * (id_ft ** 2)
        area_od_ft2 = (np.pi / 4.0) * (od_ft ** 2)
        area_steel_in2 = (np.pi / 4.0) * (row['OD_in']**2 - row['ID_in']**2)
        
        v_m = q_m_ft3s / area_id_ft2
        v_m_late = q_m_late / area_id_ft2
        
        reynolds = (rho_m * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])
        
        if reynolds > 2300:
            f = 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2
        else:
            f = 64.0 / reynolds if reynolds > 0 else 0.04
            
        dp_hydro = (rho_m * inputs['tvd']) / 144.0
        dp_fric = (f * inputs['md'] * rho_m * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0)
        dp_total = dp_hydro + dp_fric
        
        if inputs.get('lithology', 'Sandstone') == 'Sandstone':
            c_factor = 100.0 if inputs['well_type'] == 'Gas Well' else 120.0
        else:
            c_factor = 125.0 if inputs['well_type'] == 'Gas Well' else 150.0 
        v_erosional = c_factor / np.sqrt(rho_m)
        sigma_dynes = 20.0
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        
        dp_available = inputs['p_bhp'] - inputs['p_wh']
        
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_critical_loading < v_m < v_erosional
        late_life_pass = v_m_late >= v_critical_loading
        
        # Lubinski Force Balance
        rho_buoy_factor = (1.0 - (rho_m / 490.0))
        f_gravity_lbs = row['Weight_lbft'] * inputs['md'] * rho_buoy_factor
        f_thermal_lbs = 30e6 * area_steel_in2 * 6.9e-6 * delta_t_annular
        f_piston_lbs = (inputs['p_bhp'] * area_id_ft2 * 144.0) - (p_annular_total_wh * (area_od_ft2 - area_id_ft2) * 144.0)
        f_ballooning_lbs = 2.0 * 0.3 * ((inputs['p_bhp'] * area_id_ft2 * 144.0) - (p_annular_total_wh * area_od_ft2 * 144.0))
        f_drag_lbs = (f * rho_m * (v_m ** 2) * np.pi * id_ft * inputs['md']) / (2.0 * 32.174)
        sigma_bending_psi = 218.0 * row['OD_in'] * inputs['dls']
        
        f_axial_total_lbs = f_gravity_lbs + f_thermal_lbs + f_piston_lbs + f_ballooning_lbs + f_drag_lbs
        f_axial_total_klbs = f_axial_total_lbs / 1000.0
        
        sigma_axial_psi = (f_axial_total_lbs / area_steel_in2) + sigma_bending_psi
        
        p_int = inputs['p_bhp']
        p_ext = p_annular_total_wh
        r_i = row['ID_in'] / 2.0
        r_o = row['OD_in'] / 2.0
        
        sigma_hoop_psi = (p_int * (r_i**2) - p_ext * (r_o**2) + (r_i**2 * r_o**2 * (p_int - p_ext) / (r_i**2))) / (r_o**2 - r_i**2)
        sigma_radial_psi = -p_int
        
        vme_stress_psi = np.sqrt(0.5 * ((sigma_hoop_psi - sigma_radial_psi)**2 + (sigma_radial_psi - sigma_axial_psi)**2 + (sigma_axial_psi - sigma_hoop_psi)**2))
        triaxial_sf = row['Yield_psi'] / vme_stress_psi if vme_stress_psi > 0 else 99.0
        stress_pass = triaxial_sf >= 1.25
        
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
        
        if inputs['well_type'] == 'Gas Well' or inputs['gor'] > 2000:
            needs_premium = True
            conn_reasons.append("High Gas Ratio (Gas-Tight Metal Seal Required)")
            
        if dp_apb_psi > 1500:
            needs_premium = True
            conn_reasons.append(f"High APB ({round(dp_apb_psi,1)} psi) - Thread Dope Washout Risk")
            
        if "13CR" in grade_str or "22CR" in grade_str or "25CR" in grade_str:
            needs_premium = True
            conn_reasons.append("CRA Metallurgy (High Galling Risk on API Threads)")
            
        if inputs['tvd'] > 10000 or f_axial_total_klbs > 150.0:
            needs_premium = True
            conn_reasons.append("High Depth / Axial Load")

        connection_pass = True
        conn_status_msg = "Compatible API Thread"
        
        if needs_premium and row['Connection'] == 'API EUE':
            connection_pass = False
            conn_status_msg = "Premium Connection Required (" + "; ".join(conn_reasons) + ")"
        elif needs_premium and 'Premium' in row['Connection']:
            conn_status_msg = "Premium Connection Validated (" + "; ".join(conn_reasons) + ")"

        overall_pass = (hydraulics_pass and velocity_pass and late_life_pass and 
                        material_pass and stress_pass and connection_pass and temp_pass)
        
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
            "dp_hydro_psi": round(dp_hydro, 1),
            "dp_fric_psi": round(dp_fric, 1),
            "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(dp_available, 1),
            "dp_apb_psi": round(dp_apb_psi, 1),
            "f_axial_klbs": round(f_axial_total_klbs, 1),
            "vme_stress_psi": round(vme_stress_psi, 0),
            "triaxial_sf": round(triaxial_sf, 2),
            "Z_Factor": round(z_factor, 3),
            "Bo_rb_stb": round(bo_rb_stb, 3),
            "Hydraulics_Pass": hydraulics_pass,
            "Velocity_Pass": velocity_pass,
            "Late_Life_Pass": late_life_pass,
            "Material_Pass": material_pass,
            "Stress_Pass": stress_pass,
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

    # --- ASSUMPTIONS & LIMITATIONS SECTION ---
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
    st.markdown('<div class="sub-header">Step-by-step mathematical guide: mapping wellbore inputs through fluid PVT, hydraulics, stress analysis, and dual-lifecycle screening.</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # WORKFLOW OVERVIEW CARD
    # -------------------------------------------------------------------------
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A; margin-bottom: 1rem;">
        <h3 style="color: #1E3A8A; font-size: 1.2rem; margin-bottom: 0.4rem; font-weight: 700;">🔄 Dual-Lifecycle Candidate Screening Workflow</h3>
        <p style="font-size: 0.9rem; color: #334155; line-height: 1.4; margin-bottom: 0;">
            Tubing selection requires evaluating candidates against a <b>Dual Operational Envelope</b>: <i>Early-Life (Peak Production)</i> and <i>Late-Life (Depleted Reservoir / High Water Cut)</i>. Candidates pass sequentially through thermodynamic fluid models, hydraulic velocity envelopes, Lubinski load balances, and environmental gates. A tubing string achieves a final status of <b>PASS</b> only if it satisfies all engineering criteria across <b>BOTH</b> lifecycle phases.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # WORKFLOW OVERVIEW & SEQUENTIAL CANDIDATE SCREENING FUNNEL (HTML/CSS)
    # -------------------------------------------------------------------------
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
        <b>Step 1: In-Situ Fluid PVT & Density Engine</b><br/>
        <span style="font-size: 0.8rem;">Evaluates live oil & brine mixture density (&rho;<sub>m</sub>) across both lifecycle phases</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Phase Densities (&rho;<sub>m</sub>, &rho;<sub>g</sub>)</div>
    </div>
    <div class="funnel-card" style="background-color: #FEF3C7; color: #78350F; border-left: 4px solid #F59E0B;">
        <b>Step 2: Flow Dynamics & Dual Velocity Operating Envelope</b><br/>
        <span style="font-size: 0.8rem;">Early: v<sub>m</sub> < v<sub>erosional</sub> &nbsp;|&nbsp; Late: v<sub>m</sub> > v<sub>critical</sub> (Droplet Lift)</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Hydraulically Compliant Sizes</div>
    </div>
    <div class="funnel-card" style="background-color: #D1FAE5; color: #065F46; border-left: 4px solid #10B981;">
        <b>Step 3: Lubinski Net Load Balance & Triaxial Yield Matrix</b><br/>
        <span style="font-size: 0.8rem;">Early: Thermal Expansion & APB &nbsp;|&nbsp; Late: Cooling Contraction & Differential Drawdown</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Structurally Sound Pipe</div>
    </div>
    <div class="funnel-card" style="background-color: #EDE9FE; color: #5B21B6; border-left: 4px solid #8B5CF6;">
        <b>Step 4: Environmental Integrity, APB & Metallurgy Gate</b><br/>
        <span style="font-size: 0.8rem;">Filter: NACE Sour Service (p<sub>H2S</sub>), BHT Yield Derating & Connection Profile</span>
    </div>
    <div class="funnel-connector">
        <div class="funnel-line"></div>
        <div class="funnel-head"></div>
        <div class="funnel-text">Dual-Lifecycle Compliant Candidate</div>
    </div>
    <div class="funnel-card" style="background-color: #059669; color: #FFFFFF; font-weight: 700; font-size: 0.95rem;">
        Optimal Preferred Tubing Candidate (Passes Early & Late Life)
    </div>
</div>
"""
    st.markdown(diagram_html, unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # SECTION A: INPUT-TO-CALCULATION MAPPING MATRIX
    # -------------------------------------------------------------------------
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A; margin-bottom: 1.5rem;">
        <h3 style="color: #1E3A8A; font-size: 1.2rem; margin-bottom: 0.4rem; font-weight: 700;">🔗 Dual Lifecycle Parameter Mapping</h3>
        <p style="font-size: 0.9rem; color: #334155; line-height: 1.4; margin-bottom: 0;">
            Operational parameters evolve over well life. Here is how early-life inputs and predicted late-life degradation drive the engineering engines:
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.info("**1. PVT & Density**\n\n* **Early:** High $P_{bhp}$, live oil expansion ($B_o$).\n* **Late:** Lower $P_{bhp}$, high water cut ($f_w$), heavy mixture density ($\\rho_m$).")
    with col_m2:
        st.info("**2. Flow & Hydraulics**\n\n* **Early:** Peak rates risk pipe wall erosion ($v_m > v_{eros}$).\n* **Late:** Low gas rates risk liquid loading ($v_m < v_{crit}$).")
    with col_m3:
        st.info("**3. Loads & Stress**\n\n* **Early:** High BHT causes thermal expansion ($F_{thermal}$) & APB.\n* **Late:** Well cooling causes tubing tension & differential collapse.")
    with col_m4:
        st.info("**4. Environmental**\n\n* **Early:** Peak $P_{bhp}$ maximizes $H_2S$ partial pressure ($p_{H_2S}$).\n* **Late:** High water production increases scaling/corrosion risk.")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # STEP 1: FLUID THERMODYNAMICS & IN-SITU DENSITY MODEL
    # -------------------------------------------------------------------------
    st.markdown("### Step 1: Fluid Thermodynamics & In-Situ Density Model")
    st.caption("Purpose: Determine real fluid properties at subsurface pressure and temperature across both Early-Life and Late-Life operational states.")
    
    col1_1, col1_2 = st.columns(2)
    with col1_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #3B82F6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">1.1 Live Oil Solution GOR (R<sub>s</sub>) & FVF (B<sub>o</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Standing's empirical correlations estimate dissolved gas and oil volume expansion at average wellbore conditions:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"R_s = \gamma_g \left[ \left( \frac{P_{avg}}{18.2} + 1.4 \right) 10^{(0.0125 \cdot \text{API} - 0.00091 \cdot T_{avg})} \right]^{1.2048}")
        st.latex(r"B_o = 0.9759 + 0.000120 \left[ R_s \left( \frac{\gamma_g}{\gamma_o} \right)^{0.5} + 1.25 \cdot T_{avg} \right]^{1.2}")

    with col1_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #3B82F6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">1.2 Gas Z-Factor & Homogenized Mixture Density (&rho;<sub>m</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Standing-Katz pseudocritical methods compute gas compressibility Z-factor and multiphase density:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\rho_g = \frac{2.7 \cdot \gamma_g \cdot P_{avg}}{Z \cdot T_{avg, R}}, \quad \rho_l = (1-f_w)\rho_{o,live} + f_w \rho_w")
        st.latex(r"\rho_m = \lambda_l \rho_l + (1 - \lambda_l) \rho_g \quad \text{where } \lambda_l = \frac{q_l}{q_l + q_g}")

    st.info("🎯 **Step 1 Candidate Gate:** Validates thermodynamic fluid state convergence for both Early-Life and Late-Life reservoir conditions.")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # STEP 2: FLOW DYNAMICS & DUAL VELOCITY WINDOW
    # -------------------------------------------------------------------------
    st.markdown("### Step 2: Multiphase Hydraulics & Dual-Velocity Operating Window")
    st.caption("Purpose: Ensure the tubing ID allows fluids to flow within safe velocity boundaries in Early-Life while avoiding liquid loading in Late-Life.")

    col2_1, col2_2 = st.columns(2)
    with col2_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #F59E0B;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">2.1 Total Pressure Loss (&Delta;P<sub>total</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Combines hydrostatic head and turbulent pipe friction via Colebrook-White friction factor (f):</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\Delta P_{total} = \underbrace{\frac{\rho_m \cdot TVD}{144}}_{\Delta P_{hydrostatic}} + \underbrace{\frac{f \cdot MD \cdot \rho_m \cdot v_m^2}{2 \cdot g_c \cdot d_i \cdot 144}}_{\Delta P_{friction}}")
        st.latex(r"\frac{1}{\sqrt{f}} = -1.8 \log_{10} \left[ \left( \frac{\epsilon / d_i}{3.7} \right)^{1.11} + \frac{6.9}{Re} \right]")

    with col2_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #F59E0B;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">2.2 Operating Velocity Envelope Window</h4>
            <p style="font-size: 0.9rem; color: #475569;">Screens mixture velocity (v<sub>m</sub>) between Turner droplet lift minimums and lithology-adjusted erosion limits:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"v_{critical} = \frac{1.3 \cdot \sigma^{0.25}(\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}} \quad \text{(Turner Droplet Lift)}")
        st.latex(r"v_{erosional} = \frac{C}{\sqrt{\rho_m}} \quad \text{(API RP 14E: } C_{sandstone}=120, C_{carbonate}=150\text{)}")

    st.warning("🚫 **Step 2 Candidate Gate:** Rejects candidates if Early-Life rate causes pipe erosion ($v_m > v_{erosional}$) OR if Late-Life rate drops below liquid lift velocity ($v_m < v_{critical}$).")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # STEP 3: STRUCTURAL LOAD BALANCE & TRIAXIAL STRESS MATRIX
    # -------------------------------------------------------------------------
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
        st.latex(r"F_{thermal} = E \cdot A_{steel} \cdot \alpha \cdot \Delta T_{annular}")
        st.markdown("* **Gravity ($F_g$):** Buoyed pipe weight $W_{lbft} \cdot MD \cdot (1 - \\rho_m / 490)$.")
        st.markdown("* **Piston ($F_p$):** Pressure area imbalance across packers/seals.")
        st.markdown("* **Ballooning ($F_b$):** Radial pressure expansion shortening via Poisson's ratio ($\nu = 0.3$).")

    with col3_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #10B981;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">3.2 Lamé Thick-Wall & Triaxial Stress (&sigma;<sub>VME</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Calculates 3D principal stresses (Axial &sigma;<sub>z</sub>, Hoop &sigma;<sub>&theta;</sub>, Radial &sigma;<sub>r</sub>) including dogleg curvature bending:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\sigma_{axial} = \frac{F_{axial}}{A_{steel}} + \underbrace{218 \cdot OD \cdot DLS}_{\sigma_{bending}}")
        st.latex(r"\sigma_\theta = \frac{P_{int} r_i^2 - P_{ext} r_o^2 + \frac{r_i^2 r_o^2 (P_{int} - P_{ext})}{r^2}}{r_o^2 - r_i^2}, \quad \sigma_r = -P_{int}")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]}")

    st.success("🛡️ **Step 3 Candidate Gate:** Rejects candidates failing minimum safety factor limits ($SF_{triaxial} < 1.25$) in either Early-Life expansion or Late-Life contraction.")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # STEP 4: ENVIRONMENTAL INTEGRITY & MATERIAL SCREENING
    # -------------------------------------------------------------------------
    st.markdown("### Step 4: Dynamic APB, Metallurgy & Connection Screening")
    st.caption("Purpose: Model thermal annular pressure build-up, prevent NACE corrosion cracking, and enforce gas-tight thread profiles.")

    col4_1, col4_2 = st.columns(2)
    with col4_1:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #8B5CF6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">4.1 Dynamic Annular Pressure Build-up (&Delta;P<sub>APB</sub>)</h4>
            <p style="font-size: 0.9rem; color: #475569;">Calculates thermal fluid expansion pressure rise in unvented annuli during Early-Life production:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"\Delta P_{APB} = \left( \frac{\alpha_v}{\kappa_T} \right) \cdot \Delta T_{annular}")
        st.latex(r"\Delta T_{annular} = T_{producing\_avg} - T_{geothermal\_avg}")
        st.caption("• **Fluid Parameters:** Uses thermal expansion ($\\alpha_v$) and isothermal compressibility ($\\kappa_T$) for trapped annular brine/OBM.")

    with col4_2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #8B5CF6;">
            <h4 style="color: #1E3A8A; font-size: 1.1rem; font-weight: 700;">4.2 NACE MR0175 & Premium Connection Logic</h4>
            <p style="font-size: 0.9rem; color: #475569;">Screens material degradation and mandates gas-tight thread profiles:</p>
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"p_{H_2S} = P_{bhp, early} \times \left( \frac{\text{H}_2\text{S [PPM]}}{10^6} \right) \ge 0.05 \text{ psia}")
        st.markdown("* **Sour Service Screening:** Flags sour service if $p_{H_2S} \ge 0.05\\text{ psia}$. Standard carbon steels fail; L80-1 or CRA materials are enforced.")
        st.markdown("* **Premium Connection Enforcer:** Mandates gas-tight metal-to-metal seals if Gas Well, GOR $> 2000$, $\\Delta P_{APB} > 1500\\text{ psi}$, Depth $> 10,000\\text{ ft}$, or CRA metallurgy.")

    st.error("☣️ **Step 4 Candidate Gate:** Eliminates non-NACE compliant metallurgy under peak Early-Life $p_{H_2S}$, flags thermal yield derating, and enforces Premium Connections when APB or gas risk is elevated.")

# ----------------------------------------------------------------------------- 
# PAGE 3: INPUTS & CANDIDATE SELECTION
# ----------------------------------------------------------------------------- 
elif "3." in page: 
    st.markdown('<div class="main-header">Step 3: Wellbore Geometry & Operational Inputs</div>', unsafe_allow_html=True) 
    st.markdown('<div class="sub-header">Specify wellbore geometry, environmental baseline, dual-lifecycle parameters, and manage candidate tubing specs.</div>', unsafe_allow_html=True) 

    # ------------------------------------------------------------------------- 
    # TABBED INPUT STRUCTURE 
    # ------------------------------------------------------------------------- 
    tab_geo, tab_early, tab_late, tab_db = st.tabs([ 
        "📐 1. Geometry, Fluids & Targets",  
        "🚀 2. Early-Life (Initial Production)",  
        "📉 3. Late-Life (Depleted / High Water Cut)",
        "📦 4. Candidate Tubing Database"
    ]) 

    # ------------------------------------------------------------------------- 
    # TAB 1: WELLBORE GEOMETRY, ENVIRONMENTAL BASELINE & TARGETS
    # ------------------------------------------------------------------------- 
    with tab_geo: 
        st.markdown("#### 📐 Wellbore Architecture & Fluid PVT Baseline") 
        col_g1, col_g2, col_g3 = st.columns(3) 
         
        with col_g1: 
            tvd = st.number_input("True Vertical Depth - TVD (ft)", min_value=1000.000, max_value=30000.000, value=10000.000, step=100.000, format="%.3f") 
            md = st.number_input("Measured Depth - MD (ft)", min_value=1000.000, max_value=35000.000, value=11500.000, step=100.000, format="%.3f") 
            dls = st.number_input("Max Dogleg Severity - DLS (°/100ft)", min_value=0.000, max_value=15.000, value=2.000, step=0.100, format="%.3f") 

        with col_g2: 
            oil_api = st.number_input("Oil Gravity (°API)", min_value=10.000, max_value=60.000, value=35.000, step=0.100, format="%.3f") 
            gas_sg = st.number_input("Gas Specific Gravity (Air=1.000)", min_value=0.550, max_value=1.200, value=0.650, step=0.001, format="%.3f") 
            water_sg = st.number_input("Formation Water SG (Fresh=1.000)", min_value=1.000, max_value=1.250, value=1.050, step=0.001, format="%.3f") 

        with col_g3: 
            h2s_ppm = st.number_input("H₂S Concentration (PPM)", min_value=0.000, max_value=100000.000, value=150.000, step=1.000, format="%.3f") 
            co2_pct = st.number_input("CO₂ Concentration (Mol %)", min_value=0.000, max_value=50.000, value=2.500, step=0.100, format="%.3f") 
            lithology = st.selectbox("Reservoir Lithology (Erosion C-Factor)", ["Sandstone (C=120)", "Carbonate / Unconsolidated (C=150)"]) 

        st.markdown("---")
        st.markdown("#### 🛡️ Environmental Water Chemistry, Targets & Safety Limits")
        col_e1, col_e2, col_e3 = st.columns(3)

        with col_e1:
            water_chlorides = st.number_input("Water Chlorides Concentration (PPM)", min_value=0.000, max_value=250000.000, value=35000.000, step=1000.000, format="%.3f")
            water_ph = st.number_input("Formation Water pH", min_value=2.000, max_value=10.000, value=6.500, step=0.100, format="%.3f")

        with col_e2:
            target_life = st.number_input("Target Completion Lifespan (Years)", min_value=1.000, max_value=50.000, value=20.000, step=1.000, format="%.3f")
            target_capacity = st.number_input("Design Production Capacity (STB/D)", min_value=500.000, max_value=50000.000, value=10000.000, step=500.000, format="%.3f")

        with col_e3:
            sf_triaxial = st.number_input("Min Triaxial Safety Factor (SF_vme)", min_value=1.000, max_value=2.500, value=1.250, step=0.050, format="%.3f")
            surf_temp = st.number_input("Surface Ambient Temperature (°F)", min_value=30.000, max_value=130.000, value=75.000, step=1.000, format="%.3f")

        st.markdown("---")
        st.markdown("#### 🌡️ Annular Packer Fluid & Casing Geometry")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            casing_id = st.number_input("Production Casing Inner Diameter - ID (in)", min_value=4.000, max_value=13.375, value=8.681, step=0.001, format="%.3f")
        with col_a2:
            annular_fluid = st.selectbox("Trapped Annular Packer Fluid Type", [
                "Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)", 
                "Oil-Based Mud / Synthetic (α_v = 7.0e-4 /°C, κ_T = 5.0e-6 /psi)",
                "Heavy Zinc/Calcium Brine (α_v = 3.5e-4 /°C, κ_T = 2.5e-6 /psi)"
            ])

    # ------------------------------------------------------------------------- 
    # TAB 2: EARLY-LIFE (INITIAL PRODUCTION ENVELOPE) 
    # ------------------------------------------------------------------------- 
    with tab_early: 
        st.markdown("#### Early-Life Operating Conditions (Peak Rates & Pressure)") 
        col_e1, col_e2, col_e3 = st.columns(3) 

        with col_e1: 
            p_bhp_early = st.number_input("Early BHP (psi)", min_value=500.000, max_value=20000.000, value=4500.000, step=10.000, format="%.3f") 
            p_wh_early = st.number_input("Early Wellhead Pressure (psi)", min_value=50.000, max_value=5000.000, value=800.000, step=10.000, format="%.3f") 

        with col_e2: 
            q_liq_early = st.number_input("Early Liquid Production Rate (STB/D)", min_value=100.000, max_value=30000.000, value=5000.000, step=50.000, format="%.3f") 
            wc_early = st.number_input("Early Water Cut (%)", min_value=0.000, max_value=100.000, value=5.000, step=0.100, format="%.3f") 

        with col_e3: 
            gor_early = st.number_input("Early Producing GOR (scf/STB)", min_value=0.000, max_value=20000.000, value=800.000, step=10.000, format="%.3f") 
            bht_early = st.number_input("Early Bottomhole Temp - BHT (°F)", min_value=80.000, max_value=400.000, value=210.000, step=0.500, format="%.3f") 

    # ------------------------------------------------------------------------- 
    # TAB 3: LATE-LIFE (PREDICTIVE ENGINE WITH MANUAL OVERRIDE) 
    # ------------------------------------------------------------------------- 
    with tab_late: 
        st.markdown("#### Late-Life Operating Conditions (Depletion & High Water Cut)") 
         
        # Predictive Defaults Calculation Logic 
        pred_p_bhp_late = float(round(p_bhp_early * 0.50, 3)) 
        pred_p_wh_late = float(round(p_wh_early * 0.40, 3)) 
        pred_q_liq_late = float(round(q_liq_early * 0.40, 3)) 
        pred_wc_late = 75.000 if wc_early < 20.0 else float(round(min(95.0, wc_early + 30.0), 3)) 
        pred_gor_late = float(round(gor_early * 0.60, 3)) 
        pred_bht_late = float(round(bht_early - 30.0, 3)) 

        manual_override = st.toggle("🛠️ Enable Manual Override for Late-Life Parameters", value=False) 

        col_l1, col_l2, col_l3 = st.columns(3) 

        if not manual_override: 
            st.info("💡 **Auto-Predictive Engine Active:** Late-Life parameters are estimated using standard reservoir depletion multipliers. Toggle above to adjust manually.") 
             
            with col_l1: 
                p_bhp_late = st.number_input("Late BHP (psi)", value=pred_p_bhp_late, disabled=True, format="%.3f") 
                p_wh_late = st.number_input("Late Wellhead Pressure (psi)", value=pred_p_wh_late, disabled=True, format="%.3f") 

            with col_l2: 
                q_liq_late = st.number_input("Late Liquid Rate (STB/D)", value=pred_q_liq_late, disabled=True, format="%.3f") 
                wc_late = st.number_input("Late Water Cut (%)", value=pred_wc_late, disabled=True, format="%.3f") 

            with col_l3: 
                gor_late = st.number_input("Late Producing GOR (scf/STB)", value=pred_gor_late, disabled=True, format="%.3f") 
                bht_late = st.number_input("Late BHT (°F)", value=pred_bht_late, disabled=True, format="%.3f") 

        else: 
            with col_l1: 
                p_bhp_late = st.number_input("Late BHP (psi)", min_value=100.000, max_value=20000.000, value=pred_p_bhp_late, step=10.000, format="%.3f") 
                p_wh_late = st.number_input("Late Wellhead Pressure (psi)", min_value=20.000, max_value=5000.000, value=pred_p_wh_late, step=10.000, format="%.3f") 

            with col_l2: 
                q_liq_late = st.number_input("Late Liquid Rate (STB/D)", min_value=50.000, max_value=30000.000, value=pred_q_liq_late, step=50.000, format="%.3f") 
                wc_late = st.number_input("Late Water Cut (%)", min_value=0.000, max_value=100.000, value=pred_wc_late, step=0.100, format="%.3f") 

            with col_l3: 
                gor_late = st.number_input("Late Producing GOR (scf/STB)", min_value=0.000, max_value=20000.000, value=pred_gor_late, step=10.000, format="%.3f") 
                bht_late = st.number_input("Late BHT (°F)", min_value=80.000, max_value=400.000, value=pred_bht_late, step=0.500, format="%.3f") 

    # ------------------------------------------------------------------------- 
    # TAB 4: CANDIDATE TUBING DATABASE & CUSTOM INPUT FORM (RESTORED)
    # ------------------------------------------------------------------------- 
    with tab_db:
        st.markdown("#### 📦 Candidate Tubing Specifications Database")
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
        st.dataframe(filtered_db, use_container_width=True, height=400) 

        # --- CUSTOM TUBING INPUT FORM --- 
        with st.expander("➕ Add Custom Tubing Candidate"): 
            with st.form("add_candidate_form"): 
                col1, col2, col3 = st.columns(3) 
                with col1: 
                    c_name = st.text_input("Candidate Name", value='3-1/2" P110 (9.2#)') 
                    c_od = st.number_input("Outer Diameter (OD) [in]", value=3.500, min_value=1.000, max_value=12.000, step=0.001, format="%.3f") 
                    c_yield = st.number_input("Yield Strength [psi]", value=110000, min_value=30000, max_value=180000, step=1000) 
                    c_collapse = st.number_input("Collapse Pressure Rating [psi]", value=12200, min_value=1000, max_value=30000, step=100)
                with col2: 
                    c_id = st.number_input("Inner Diameter (ID) [in]", value=2.992, min_value=0.500, max_value=11.000, step=0.001, format="%.3f") 
                    c_weight = st.number_input("Nominal Weight [lb/ft]", value=9.200, min_value=1.000, max_value=100.000, step=0.100, format="%.3f") 
                    c_burst = st.number_input("Burst Pressure Rating [psi]", value=13970, min_value=1000, max_value=30000, step=100) 
                    c_tensile = st.number_input("Joint Tensile Strength [lbs]", value=214000, min_value=10000, max_value=1000000, step=1000)
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
                            "Yield_psi": c_yield, "Burst_psi": c_burst, "Collapse_psi": c_collapse, "Tensile_lb": c_tensile
                        }]) 
                        st.session_state.tubing_db = pd.concat([st.session_state.tubing_db, new_row], ignore_index=True) 
                        st.success(f"Added {c_name} ({c_conn}) to active candidate database!") 
                        st.rerun()

    st.markdown("---") 

    # ------------------------------------------------------------------------- 
    # DUAL OPERATIONAL ENVELOPE SUMMARY MATRIX 
    # ------------------------------------------------------------------------- 
    st.markdown("### 📊 Dual Operational Envelope Summary") 
     
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
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{p_bhp_early:.3f} psi</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{p_bhp_late:.3f} psi</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Peak H₂S partial pressure (Early) vs. Hydrostatic head drawdown (Late)</td> 
            </tr> 
            <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;"> 
                <td style="padding: 10px; font-weight: 600;">Liquid Rate & Water Cut</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{q_liq_early:.3f} STB/D ({wc_early:.3f}% WC)</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{q_liq_late:.3f} STB/D ({wc_late:.3f}% WC)</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Erosion limits v<sub>m</sub> &lt; v<sub>eros</sub> (Early) vs. Liquid loading v<sub>m</sub> &gt; v<sub>crit</sub> (Late)</td> 
            </tr> 
            <tr style="border-bottom: 1px solid #E2E8F0;"> 
                <td style="padding: 10px; font-weight: 600;">Producing GOR</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{gor_early:.3f} scf/STB</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{gor_late:.3f} scf/STB</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Multiphase fluid density homogenization (&rho;<sub>m</sub>)</td> 
            </tr> 
            <tr style="background-color: #F8FAFC;"> 
                <td style="padding: 10px; font-weight: 600;">Bottomhole Temp & APB</td> 
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{bht_early:.3f} °F</td> 
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{bht_late:.3f} °F</td> 
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Thermal expansion & APB load (Early) vs. Tubing cooling contraction (Late)</td> 
            </tr> 
        </tbody> 
    </table> 
    """ 
    st.markdown(summary_html, unsafe_allow_html=True) 
    st.markdown("<br/>", unsafe_allow_html=True) 

    # ------------------------------------------------------------------------- 
    # ACTION BUTTON: SAVE & RUN MODEL 
    # ------------------------------------------------------------------------- 
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1]) 
    with col_btn2: 
        if st.button("💾 Save & Run Screening Model", type="primary", use_container_width=True): 
            st.session_state["well_inputs"] = { 
                "tvd": tvd, "md": md, "dls": dls, 
                "oil_api": oil_api, "gas_sg": gas_sg, "water_sg": water_sg, 
                "h2s_ppm": h2s_ppm, "co2_pct": co2_pct, "lithology": lithology, 
                "water_chlorides": water_chlorides, "water_ph": water_ph,
                "target_life": target_life, "target_capacity": target_capacity,
                "sf_triaxial": sf_triaxial, "surf_temp": surf_temp,
                "annular_fluid": annular_fluid, "casing_id": casing_id,
                "early": { 
                    "p_bhp": p_bhp_early, "p_wh": p_wh_early, 
                    "q_liq": q_liq_early, "wc": wc_early, 
                    "gor": gor_early, "bht": bht_early 
                }, 
                "late": { 
                    "p_bhp": p_bhp_late, "p_wh": p_wh_late, 
                    "q_liq": q_liq_late, "wc": wc_late, 
                    "gor": gor_late, "bht": bht_late 
                } 
            } 
            st.success("✅ Complete operational inputs & candidate database saved! Ready to run screening.")

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
    st.markdown('<div class="sub-header">Evaluates dynamic PVT, pressure losses, velocity screening, APB, NACE MR0175 sour service, and Lubinski stress.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs['well_type']} Mode)")
    
    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts',
        'dp_total_psi', 'dp_apb_psi', 'f_axial_klbs', 'vme_stress_psi', 'triaxial_sf', 'Material_Reason', 'Temp_Reason', 'Overall_Pass'
    ]].copy()
    
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)',
        'Total dP (psi)', 'APB Pressure (psi)', 'Axial Load (klbs)', 'von Mises Stress (psi)', 'Triaxial SF', 'NACE Status', 'Temp Status', 'Overall Status'
    ]
    
    st.dataframe(display_df, use_container_width=True, height=450)
    
    with st.expander("📐 Show Governing Equations & Technical Correlations"):
        st.markdown("#### 1. Annular Pressure Build-up (APB)")
        st.latex(r"\Delta P_{APB} = \left( \frac{\alpha_v}{\kappa_T} \right) \Delta T_{annular}")
        st.caption("Where $\\alpha_v$ is thermal expansion coefficient and $\\kappa_T$ is fluid isothermal compressibility.")
        
        st.markdown("#### 2. Lubinski Total Net Axial Load Balance")
        st.latex(r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}")
        st.caption("Includes buoyed pipe weight, constrained thermal expansion, pressure area changes across seals, radial expansion shortening, and fluid skin friction.")

        st.markdown("#### 3. von Mises Triaxial Equivalent Stress")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]} \le \frac{Y_{yield}}{SF_{triaxial}}")
        st.caption("Requires a minimum triaxial safety factor $SF_{triaxial} \\ge 1.25$ per completion design standards.")

        st.markdown("#### 4. Turner Critical Liquid Loading Velocity")
        st.latex(r"v_{critical} = \frac{1.3 \cdot \sigma^{0.25} (\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}} \quad \text{(Turner Correlation, } C=1.3\text{)}")
        st.caption("Calculates minimum gas mixture velocity required to continuously transport liquid droplets to surface.")

# -----------------------------------------------------------------------------
# PAGE 6: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "6. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 6: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, structural checks, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    passed_candidates = res_df[res_df['Overall_Pass'] == True]
    
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
            st.metric("APB Pressure Rise", f"{preferred['dp_apb_psi']} psi")
        else:
            st.error("### No Candidates Passed All Screenings!")
            st.warning("Consider increasing bottomhole pressure, selecting NACE-compliant grades, or upgrading to premium connections.")

    with col2:
        st.subheader("Engineering Justification Rationale")
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            st.markdown(f"""
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**). Dynamic Z-factor (**{preferred['Z_Factor']}**) and Bo (**{preferred['Bo_rb_stb']} rb/STB**) confirm live-fluid flow.
            * **Velocity Window:** Initial mixture flow velocity (**{preferred['Velocity_fts']} ft/s**) and Year {st.session_state.inputs['field_life_yrs']} late-life velocity (**{preferred['v_late_life_fts']} ft/s**) remain safely above liquid loading limits (**{preferred['v_critical']} ft/s**).
            * **NACE & Thermal Compliance:** Grade **{preferred['Grade']}** ({preferred['Material']}) is compliant for operating BHT ({st.session_state.inputs['t_bht']}°F) and sour service limits ($p_{{H_2S}} = {round(st.session_state.inputs['p_bhp'] * (st.session_state.inputs['h2s_ppm']/1e6), 3)}$ psia).
            * **Structural & APB Integrity:** Total axial tension (**{preferred['f_axial_klbs']} klbs**) and APB pressure (**{preferred['dp_apb_psi']} psi**) yield a von Mises stress of **{preferred['vme_stress_psi']} psi** (Triaxial SF = **{preferred['triaxial_sf']}**).
            """)
        else:
            st.write("Review the calculation page to identify specific failure flags (velocity, hydraulics, APB, temperature rating, or NACE limits).")

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
            with st.spinner("Analyzing hydraulics, velocity limits, APB, and NACE compliance via Gemini API..."):
                try:
                    import json
                    import urllib.request

                    pref = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
                    
                    prompt_text = f"""
                    You are a Senior Completion Engineer writing an executive technical recommendation memo for an asset manager.
                    Synthesize the following PRE-CALCULATED Python engineering data into a concise, professional technical assessment.
                    DO NOT re-calculate or alter any numerical values. Rely STRICTLY on these provided facts:

                    WELL & OPERATIONAL PARAMETERS:
                    - Well Type: {st.session_state.inputs['well_type']}
                    - Reservoir Lithology: {st.session_state.inputs.get('lithology', 'Sandstone')}
                    - Measured Depth / TVD: {st.session_state.inputs['md']} ft / {st.session_state.inputs['tvd']} ft (Dogleg Severity: {st.session_state.inputs['dls']} deg/100ft)
                    - Wellhead / Bottomhole Pressure: {st.session_state.inputs['p_wh']} psi / {st.session_state.inputs['p_bhp']} psi (Available Drawdown: {pref['dp_avail_psi']} psi)
                    - Annular Fluid & APB Pressure Build-up: {st.session_state.inputs['annular_fluid']} (Calculated APB Rise: {pref['dp_apb_psi']} psi)
                    - Target Field Life: {st.session_state.inputs['field_life_yrs']} Years at {st.session_state.inputs['decline_rate']}% Annual Decline Rate
                    - CO2 / H2S Concentrations: {st.session_state.inputs['co2_mole_pct']} mole% CO2, {st.session_state.inputs['h2s_ppm']} PPM H2S (pH: {st.session_state.inputs['ph_val']})

                    SELECTED PREFERRED TUBING CANDIDATE:
                    - Candidate Name: {pref['Name']}
                    - Steel Grade / Material: {pref['Grade']} ({pref['Material']})
                    - Thread / Connection Type: {pref['Connection']}
                    - Total Calculated Pressure Drop: {pref['dp_total_psi']} psi (Hydrostatic: {pref['dp_hydro_psi']} psi, Friction: {pref['dp_fric_psi']} psi)
                    - Net Lubinski Axial Force: {pref['f_axial_klbs']} klbs
                    - von Mises Triaxial Stress: {pref['vme_stress_psi']} psi (Triaxial Safety Factor: {pref['triaxial_sf']})
                    - Initial Flow Velocity: {pref['Velocity_fts']} ft/s
                    - Year {st.session_state.inputs['field_life_yrs']} Late-Life Velocity: {pref['v_late_life_fts']} ft/s
                    - Turner Critical Liquid Loading Limit: {pref['v_critical']} ft/s
                    - API RP 14E Max Erosional Velocity Limit: {pref['v_erosional']} ft/s
                    - Connection Evaluation Rationale: {pref['Connection_Reason']}

                    INSTRUCTIONS:
                    1. Write an executive memo starting with TO, FROM, and SUBJECT lines.
                    2. Paragraph 1: Recommend the candidate size, grade, and connection type, justifying hydraulics vs available drawdown.
                    3. Paragraph 2: Analyze initial vs Year 15 late-life velocities against Turner loading and API RP 14E limits.
                    4. Paragraph 3: Detail structural safety factor (Triaxial SF), Annular Pressure Build-up (APB), and explain connection choice (API EUE vs Premium metal seal) under NACE MR0175 limits.
                    5. Use formal engineering phrasing and bold key numeric values.
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
        
        st.info("""
        **How to Interpret Graph 1:**
        * **Red Dashed Line (Drawdown Limit):** Represents maximum available reservoir pressure drive (P_bhp - P_wh). Candidates operating above this line cannot flow naturally to the surface.
        * **Pressure Curve Trend:** Frictional pressure drop decreases sharply as tubing inner diameter increases. The optimal candidate balances low pressure drop while remaining comfortably below the drawdown ceiling.
        """)

    with tab2:
        fig_v = go.Figure()
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['Velocity_fts'], mode='lines+markers', name='Initial Flow Velocity'))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_late_life_fts'], mode='lines+markers', name='Late-Life Flow Velocity', line=dict(dash='dash', color='purple')))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_erosional'], mode='lines', name='Erosional Limit (Max)', line=dict(dash='dash', color='red')))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_critical'], mode='lines', name='Turner Liquid Loading Limit (Min)', line=dict(dash='dot', color='orange')))
        
        fig_v.update_layout(
            title="Flow Velocity Window vs. Tubing Inner Diameter",
            xaxis_title="Inner Diameter (inches)",
            yaxis_title="Velocity (ft/s)",
            margin=dict(t=50, b=40)
        )
        st.plotly_chart(fig_v, use_container_width=True)
        
        st.info(
            "**How to Interpret Graph 2:**\n\n"
            "* **Upper Red Limit (API RP 14E Erosional Velocity):** Operating above this line causes severe structural pipe wear and wall thinning due to high fluid kinetic energy.\n"
            "* **Lower Orange Limit (Turner Liquid Loading Velocity):** Operating below this line results in insufficient gas velocity to lift liquid droplets, causing liquid accumulation downhole and shutting in the well.\n"
            "* **Purple Dashed Line (Late-Life Velocity):** Demonstrates velocity reduction after reservoir decline. Tubing must keep the purple line above the orange limit to ensure long-term well performance."
        )