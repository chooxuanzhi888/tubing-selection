import os
import json
import urllib.request
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# PAGE CONFIG & REUSABLE STYLES
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tubing Selection Tool",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.3rem; }
    .sub-header { font-size: 1.05rem; color: #475569; margin-bottom: 1.2rem; }
    .card { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; margin-bottom: 1rem; }
    .card-blue { border-left: 5px solid #1E3A8A; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .card-green { border-left: 5px solid #059669; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .card-red { border-left: 5px solid #DC2626; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .table-styled { width:100%; border-collapse: collapse; font-size: 0.9rem; }
    .table-styled th { background-color: #1E3A8A; color: white; padding: 10px; text-align: left; }
    .table-styled td { padding: 10px; border-bottom: 1px solid #E2E8F0; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE & CONSTANTS
# -----------------------------------------------------------------------------
DEFAULT_INPUTS = {
    'well_type': 'Oil Well (Liquid Dominated)', 'lithology': 'Sandstone (C=120)',
    'tvd': 10000.0, 'md': 11500.0, 'dls': 2.0, 'casing_id': 8.681, 'p_wh': 800.0,
    'p_bhp': 4500.0, 'cithp': 3800.0, 't_wh': 75.0, 't_bht': 210.0, 't_ambient': 75.0,
    'annular_fluid': 'Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)',
    'q_liquid': 5000.0, 'water_cut': 5.0, 'gor': 800.0, 'q_gas_mmscfd': 15.0,
    'cgr_stb_mmscf': 25.0, 'wgr_bbl_mmscf': 5.0, 'api_gravity': 35.0, 'gas_sg': 0.65,
    'water_sg': 1.05, 'oil_visc': 1.5, 'co2_mole_pct': 2.5, 'h2s_ppm': 150.0,
    'ph_val': 6.5, 'chlorides_ppm': 35000.0, 'field_life_yrs': 20, 'decline_rate': 8.0, 'sf_triaxial': 1.25
}

if 'inputs' not in st.session_state:
    st.session_state.inputs = DEFAULT_INPUTS.copy()

def cfg(key, fallback=None):
    """Retrieve state input value safely with fallback."""
    return st.session_state.inputs.get(key, DEFAULT_INPUTS.get(key, fallback))

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

# -----------------------------------------------------------------------------
# CORE ENGINEERING CALCULATION ENGINE
# -----------------------------------------------------------------------------
def compute_dynamic_z_factor(p_psi, t_deg_r, gas_sg):
    p_pc = 756.8 - 131.07 * gas_sg - 3.6 * (gas_sg ** 2)
    t_pc = 169.2 + 349.5 * gas_sg - 74.0 * (gas_sg ** 2)
    p_pr, t_pr = p_psi / p_pc, t_deg_r / t_pc
    t_r = 1.0 / t_pr
    a = 0.06125 * t_r * np.exp(-1.2 * (1.0 - t_r)**2)
    y = 0.0125 * p_pr * t_r
    return float(np.clip(a * p_pr / y if y > 0 else 0.88, 0.65, 1.25))

def run_engineering_calculations(inputs, candidate_df):
    results = []
    is_gas_well = "Gas Well" in inputs.get('well_type', 'Oil Well')
    p_wh, p_bhp = inputs.get('p_wh', 800.0), inputs.get('p_bhp', 4500.0)
    p_avg = (p_wh + p_bhp) / 2.0
    
    t_wh, t_bht = inputs.get('t_wh', 75.0), inputs.get('t_bht', 210.0)
    t_avg_f = (t_wh + t_bht) / 2.0
    t_avg_r = t_avg_f + 459.67
    t_bht_c = (t_bht - 32.0) * (5.0 / 9.0)
    casing_id_val = inputs.get('casing_id', 8.681)
    
    api_val, gas_sg_val, water_sg_val = inputs.get('api_gravity', 35.0), inputs.get('gas_sg', 0.65), inputs.get('water_sg', 1.05)
    gamma_o = 141.5 / (131.5 + api_val)
    
    if is_gas_well:
        q_g_scf_d = inputs.get('q_gas_mmscfd', 15.0) * 1e6
        q_cond_stbd = inputs.get('q_gas_mmscfd', 15.0) * inputs.get('cgr_stb_mmscf', 25.0)
        q_wat_stbd = inputs.get('q_gas_mmscfd', 15.0) * inputs.get('wgr_bbl_mmscf', 5.0)
        bo_rb_stb, rho_o_live, rho_w = 1.05, 62.4 * gamma_o, water_sg_val * 62.4
        q_l_ft3s = ((q_cond_stbd + q_wat_stbd) * 5.615) / 86400.0
        wc_frac = q_wat_stbd / (q_cond_stbd + q_wat_stbd) if (q_cond_stbd + q_wat_stbd) > 0 else 0.0
        rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w if (q_cond_stbd + q_wat_stbd) > 0 else rho_o_live
    else:
        gor_val, q_liq_val, wc_val = inputs.get('gor', 800.0), inputs.get('q_liquid', 5000.0), inputs.get('water_cut', 5.0)
        rs_scf_stb = min(gas_sg_val * (((p_avg / 18.2) + 1.4) * (10 ** (0.0125 * api_val - 0.00091 * t_avg_f))) ** 1.2048, gor_val)
        bo_rb_stb = 0.9759 + 0.000120 * ((rs_scf_stb * ((gas_sg_val / gamma_o) ** 0.5) + 1.25 * t_avg_f) ** 1.2)
        rho_o_live, rho_w = (62.4 * gamma_o + 0.0136 * rs_scf_stb * gas_sg_val) / bo_rb_stb, water_sg_val * 62.4
        wc_frac = wc_val / 100.0
        rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w
        q_l_ft3s = (q_liq_val * 5.615) / 86400.0
        q_g_scf_d = q_liq_val * (1.0 - wc_frac) * max(gor_val - rs_scf_stb, 0.0)

    z_factor = compute_dynamic_z_factor(p_avg, t_avg_r, gas_sg_val)
    rho_g = max((2.7 * gas_sg_val * p_avg) / (z_factor * t_avg_r), 0.05)
    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg * 520.0 * 86400.0)
    q_m_ft3s = max(q_l_ft3s + q_g_ft3s, 1e-6)
    
    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g
    mu_m_lbfts = (lambda_l * ((1.0 - wc_frac) * inputs.get('oil_visc', 1.5) + wc_frac * 0.5) + (1.0 - lambda_l) * 0.018) * 0.000672
    
    is_sour_service = (p_bhp * (inputs.get('h2s_ppm', 150.0) / 1e6)) >= 0.05
    decline_factor = (1.0 - (inputs.get('decline_rate', 8.0) / 100.0)) ** inputs.get('field_life_yrs', 20)
    q_m_late = q_m_ft3s * decline_factor
    
    fluid_props = ANNULAR_FLUID_PROPS.get(inputs.get('annular_fluid', ''), ANNULAR_FLUID_PROPS["Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)"])
    delta_t_annular = max(t_avg_f - inputs.get('t_ambient', 75.0), 0.0)
    dp_apb_psi = (fluid_props['alpha_v'] / fluid_props['kappa_t']) * delta_t_annular
    p_annular_wh = p_wh + dp_apb_psi

    for _, row in candidate_df.iterrows():
        id_ft, od_ft = row['ID_in'] / 12.0, row['OD_in'] / 12.0
        area_id, area_od = (np.pi / 4.0) * (id_ft ** 2), (np.pi / 4.0) * (od_ft ** 2)
        area_steel = (np.pi / 4.0) * (row['OD_in']**2 - row['ID_in']**2)
        
        casing_clearance_pass = row['OD_in'] < casing_id_val
        v_m, v_m_late = q_m_ft3s / area_id, q_m_late / area_id
        reynolds = (rho_m * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        rel_rough = 0.0006 / row['ID_in']
        
        f = (1.0 / (-1.8 * np.log10((rel_rough / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2) if reynolds > 2300 else (64.0 / reynolds if reynolds > 0 else 0.04)
        tvd_val, md_val, dls_val = inputs.get('tvd', 10000.0), inputs.get('md', 11500.0), inputs.get('dls', 2.0)
        
        dp_hydro = (rho_m * tvd_val) / 144.0
        dp_fric = (f * md_val * rho_m * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0)
        dp_total = dp_hydro + dp_fric
        
        c_factor = (100.0 if is_gas_well else 120.0) if "Sandstone" in inputs.get('lithology', 'Sandstone') else (130.0 if is_gas_well else 150.0)
        v_erosional = c_factor / np.sqrt(rho_m)
        v_critical = (1.3 * (20.0 ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        
        hydraulics_pass = dp_total <= (p_bhp - p_wh)
        velocity_pass = v_critical < v_m < v_erosional
        late_life_pass = v_m_late >= v_critical
        
        # Lubinski Mechanics
        f_grav = row['Weight_lbft'] * md_val * (1.0 - (rho_m / 490.0))
        f_therm = 30e6 * area_steel * 6.9e-6 * delta_t_annular
        f_pist = (p_bhp * area_id * 144.0) - (p_annular_wh * (area_od - area_id) * 144.0)
        f_ball = 0.6 * ((p_bhp * area_id * 144.0) - (p_annular_wh * area_od * 144.0))
        f_drag = (f * rho_m * (v_m ** 2) * np.pi * id_ft * md_val) / (2.0 * 32.174)
        f_axial_klbs = (f_grav + f_therm + f_pist + f_ball + f_drag) / 1000.0
        
        sigma_axial = ((f_axial_klbs * 1000.0) / area_steel) + (218.0 * row['OD_in'] * dls_val)
        r_i, r_o = row['ID_in'] / 2.0, row['OD_in'] / 2.0
        sigma_hoop = (p_bhp * (r_i**2) - p_annular_wh * (r_o**2) + (r_i**2 * r_o**2 * (p_bhp - p_annular_wh) / (r_i**2))) / (r_o**2 - r_i**2)
        sigma_radial = -p_bhp
        
        vme_stress = np.sqrt(0.5 * ((sigma_hoop - sigma_radial)**2 + (sigma_radial - sigma_axial)**2 + (sigma_axial - sigma_hoop)**2))
        triaxial_sf = row['Yield_psi'] / vme_stress if vme_stress > 0 else 99.0
        stress_pass = triaxial_sf >= inputs.get('sf_triaxial', 1.25)
        
        cithp_val = inputs.get('cithp', p_wh)
        burst_sf = row['Burst_psi'] / cithp_val if cithp_val > 0 else 99.0
        burst_pass = burst_sf >= 1.10

        # Temperature & Metallurgy Gates
        grade_str = str(row['Grade']).upper()
        temp_pass, temp_reason = True, "Compatible"
        if t_bht_c >= 107.0 and grade_str not in ["Q125"]:
            temp_pass, temp_reason = False, f"Fail: BHT ({round(t_bht_c,1)}°C >= 107°C) requires Grade Q125"
        elif t_bht_c >= 80.0 and grade_str not in ["H40", "N80", "P105", "P110", "Q125"]:
            temp_pass, temp_reason = False, f"Fail: BHT ({round(t_bht_c,1)}°C >= 80°C) requires H40, N80, P105, P110, Q125"

        material_pass, mat_reason = True, "Compatible"
        if is_sour_service and grade_str in ["J-55", "J55", "N-80", "N80", "P-110", "P110"]:
            material_pass, mat_reason = False, "Fail: Sour Service requires L80-1 (26 HRC Max) or CRA."

        # Connection Logic
        needs_premium = (is_gas_well or inputs.get('gor', 0) > 2000 or inputs.get('q_gas_mmscfd', 0) > 10.0 or
                         cithp_val > 3000 or dp_apb_psi > 1500 or any(c in grade_str for c in ["13CR", "22CR", "25CR"]) or tvd_val > 10000)
        
        connection_pass = not (needs_premium and row['Connection'] == 'API EUE')
        conn_status_msg = ("Premium Connection Required" if not connection_pass else ("Premium Validated" if needs_premium else "API Thread Valid"))

        overall_pass = (casing_clearance_pass and hydraulics_pass and velocity_pass and late_life_pass and 
                        material_pass and stress_pass and connection_pass and temp_pass and burst_pass)
        
        results.append({
            "Name": row['Name'], "OD_in": row['OD_in'], "ID_in": row['ID_in'], "Grade": row['Grade'],
            "Material": row['Material'], "Connection": row['Connection'], "Velocity_fts": round(v_m, 2),
            "v_late_life_fts": round(v_m_late, 2), "v_erosional": round(v_erosional, 2), "v_critical": round(v_critical, 2),
            "dp_hydro_psi": round(dp_hydro, 1), "dp_fric_psi": round(dp_fric, 1), "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(p_bhp - p_wh, 1), "dp_apb_psi": round(dp_apb_psi, 1), "cithp_psi": round(cithp_val, 1),
            "f_axial_klbs": round(f_axial_klbs, 1), "vme_stress_psi": round(vme_stress, 0), "triaxial_sf": round(triaxial_sf, 2),
            "burst_sf": round(burst_sf, 2), "Z_Factor": round(z_factor, 3), "Bo_rb_stb": round(bo_rb_stb, 3),
            "Casing_Clearance_Pass": casing_clearance_pass, "Hydraulics_Pass": hydraulics_pass, "Velocity_Pass": velocity_pass,
            "Late_Life_Pass": late_life_pass, "Material_Pass": material_pass, "Stress_Pass": stress_pass,
            "Burst_Pass": burst_pass, "Temp_Pass": temp_pass, "Connection_Pass": connection_pass,
            "Connection_Reason": conn_status_msg, "Material_Reason": mat_reason, "Temp_Reason": temp_reason, "Overall_Pass": overall_pass
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
    ["1. Introduction & Overview", "2. Calculation Methodology", "3. Well & Fluid Inputs", 
     "4. Candidate Tubing Specs", "5. Engineering Calculations", "6. Recommendation & Sensitivity"]
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
    <div class="card card-blue">
        <h2 style="color: #1E3A8A; font-size: 1.5rem; margin-bottom: 0.6rem;">What is Upper Completion?</h2>
        <p style="font-size: 1rem; line-height: 1.5; color: #1E293B;">
            The <b>upper completion</b> is the portion of a well completion located <b>above the lower reservoir completion</b>, extending to the <b>wellhead and surface facilities</b>. It provides the main conduit for produced or injected fluids via production tubing, packers, subsurface safety valves (SCSSVs), and artificial lift systems.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="card">
            <h3 style="color: #1E3A8A; font-size: 1.2rem;">Upper Completion Configurations</h3>
            <ul>
                <li><b>Tubingless completion:</b> direct flow through casing.</li>
                <li><b>Tubing without packer:</b> open annular communication.</li>
                <li><b>Tubing with packer:</b> full annular isolation.</li>
                <li><b>Dual tubing string:</b> multi-zone isolation.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if os.path.exists("Figure 1.png"):
            st.image("Figure 1.png", caption="Figure 1: Upper-completion configurations", use_container_width=True)

    with col2:
        st.markdown("""
        <div class="card">
            <h3 style="color: #1E3A8A; font-size: 1.2rem;">Major Components</h3>
            <p>Includes production tubing, SCSSVs, packers, gas-lift mandrels, and chemical injection subs ensuring well control and structural integrity.</p>
        </div>
        """, unsafe_allow_html=True)
        if os.path.exists("Figure 2.jpg"):
            st.image("Figure 2.jpg", caption="Figure 2: Typical upper-completion components", use_container_width=True)

    st.markdown("---")
    st.markdown("""
    <div class="card card-green">
        <h2 style="color: #065F46; font-size: 1.5rem; margin-bottom: 0.6rem;">Production Tubing Specifications</h2>
        <table class="table-styled">
            <tr style="background:#065F46; color:white;"><th>Specification</th><th>Engineering Importance</th></tr>
            <tr><td><b>Nominal Size / OD</b></td><td>Casing clearance & mechanical geometry.</td></tr>
            <tr><td><b>Internal Diameter (ID)</b></td><td>Governs fluid velocity & pressure drop.</td></tr>
            <tr><td><b>Steel Grade & Material</b></td><td>Determines yield strength & NACE H2S resistance.</td></tr>
            <tr><td><b>Connection Profile</b></td><td>Ensures gas-tight metal sealing under high pressure/CITHP.</td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    if os.path.exists("Figure 3.jpg"):
        st.image("Figure 3.jpg", caption="Figure 3 — Production tubing in wellbore", use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: CALCULATION METHODOLOGY
# -----------------------------------------------------------------------------
elif page == "2. Calculation Methodology":
    st.markdown('<div class="main-header">Step 2: Comprehensive Calculation Methodology</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Step-by-step mathematical guide for fluid PVT, hydraulics, CITHP burst, and Lubinski stress.</div>', unsafe_allow_html=True)

    st.markdown("### Step 1: Dynamic Fluid PVT & In-Situ Density Engine")
    col1_1, col1_2 = st.columns(2)
    with col1_1:
        st.markdown("**1.1 Oil Well Mode (Standing's Correlations)**")
        st.latex(r"R_s = \gamma_g \left[ \left( \frac{P_{avg}}{18.2} + 1.4 \right) 10^{(0.0125 \cdot \text{API} - 0.00091 \cdot T_{avg})} \right]^{1.2048}")
        st.latex(r"B_o = 0.9759 + 0.000120 \left[ R_s \left( \frac{\gamma_g}{\gamma_o} \right)^{0.5} + 1.25 \cdot T_{avg} \right]^{1.2}")
    with col1_2:
        st.markdown("**1.2 Gas Well Mode (Standing-Katz Z-Factor)**")
        st.latex(r"P_{pc} = 756.8 - 131.07 \gamma_g - 3.6 \gamma_g^2, \quad T_{pc} = 169.2 + 349.5 \gamma_g - 74.0 \gamma_g^2")
        st.latex(r"\rho_g = \frac{2.7 \cdot \gamma_g \cdot P_{avg}}{Z \cdot T_{avg,R}}, \quad \rho_m = \lambda_l \rho_l + (1-\lambda_l)\rho_g")

    st.markdown("---")
    st.markdown("### Step 2: Multiphase Hydraulics & Velocity Envelope")
    col2_1, col2_2 = st.columns(2)
    with col2_1:
        st.markdown("**2.1 Total Pressure Loss (&Delta;P<sub>total</sub>)**")
        st.latex(r"\Delta P_{total} = \frac{\rho_m \cdot TVD}{144} + \frac{f \cdot MD \cdot \rho_m \cdot v_m^2}{2 \cdot g_c \cdot d_i \cdot 144}")
    with col2_2:
        st.markdown("**2.2 Operating Velocity Limits**")
        st.latex(r"v_{critical} = \frac{1.3 \cdot \sigma^{0.25}(\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}}, \quad v_{erosional} = \frac{C}{\sqrt{\rho_m}}")

    st.markdown("---")
    st.markdown("### Step 3 & 4: Structural Stress & Shut-In Burst")
    col3_1, col3_2 = st.columns(2)
    with col3_1:
        st.markdown("**3.1 Lubinski Net Axial Force & von Mises Stress**")
        st.latex(r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]} \le \frac{Y_{yield}}{SF_{triaxial}}")
    with col3_2:
        st.markdown("**4.1 Shut-In Static CITHP Surface Burst**")
        st.latex(r"\text{CITHP} = P_{bhp} \cdot e^{-\left(\frac{M \cdot TVD}{Z \cdot R \cdot T_{avg}}\right)}, \quad SF_{burst} = \frac{\text{Burst Limit}}{\text{CITHP}} \ge 1.10")

# ----------------------------------------------------------------------------- 
# PAGE 3: WELL & FLUID INPUTS
# ----------------------------------------------------------------------------- 
elif page == "3. Well & Fluid Inputs": 
    st.markdown('<div class="main-header">Step 3: Wellbore Geometry & Operational Inputs</div>', unsafe_allow_html=True) 

    well_type_curr = cfg('well_type', 'Oil Well (Liquid Dominated)')
    is_gas = "Gas" in well_type_curr

    tab_geo, tab_early, tab_late = st.tabs(["📐 Architecture & CITHP", "🚀 Early-Life Baseline", "📉 Late-Life Envelope"]) 

    with tab_geo: 
        c1, c2, c3 = st.columns(3) 
        well_type = c1.selectbox("Well Type Category", ["Oil Well (Liquid Dominated)", "Gas Well (Gas / Condensate)"], index=1 if is_gas else 0)
        tvd = c1.number_input("True Vertical Depth - TVD (ft)", value=float(cfg('tvd', 10000.0)), step=100.0) 
        md = c2.number_input("Measured Depth - MD (ft)", value=float(cfg('md', 11500.0)), step=100.0) 
        dls = c2.number_input("Max DLS (°/100ft)", value=float(cfg('dls', 2.0)), step=0.1) 
        casing_id = c3.number_input("Casing ID (in)", value=float(cfg('casing_id', 8.681)), step=0.001)

        st.markdown("---")
        cithp_calc = round(cfg('p_bhp', 4500.0) * np.exp(-0.000035 * tvd), 1)
        cithp_input = c1.number_input("Static CITHP (psi)", value=float(cfg('cithp', cithp_calc)), step=50.0)
        sf_triaxial = c2.number_input("Min Triaxial Safety Factor", value=float(cfg('sf_triaxial', 1.25)), step=0.05)
        
        ann_opts = list(ANNULAR_FLUID_PROPS.keys())
        annular_fluid = c3.selectbox("Annular Fluid", ann_opts, index=0)

        st.markdown("---")
        api_gravity = c1.number_input("Oil/Condensate (°API)", value=float(cfg('api_gravity', 35.0)))
        gas_sg = c1.number_input("Gas SG", value=float(cfg('gas_sg', 0.65)))
        h2s_ppm = c2.number_input("H₂S (PPM)", value=float(cfg('h2s_ppm', 150.0)))
        co2_pct = c2.number_input("CO₂ (Mol %)", value=float(cfg('co2_mole_pct', 2.5)))
        oil_visc = c3.number_input("Oil Viscosity (cP)", value=float(cfg('oil_visc', 1.5)))
        lithology = c3.selectbox("Lithology", ["Sandstone (C=120)", "Carbonate / Unconsolidated (C=150)"])

    with tab_early: 
        c1, c2, c3 = st.columns(3) 
        p_bhp_early = c1.number_input("Early BHP (psi)", value=float(cfg('p_bhp', 4500.0))) 
        p_wh_early = c1.number_input("Early Wellhead P (psi)", value=float(cfg('p_wh', 800.0))) 
        if "Gas" in well_type:
            q_gas_early = c2.number_input("Early Gas Rate (MMscf/D)", value=float(cfg('q_gas_mmscfd', 15.0)))
            cgr_early = c2.number_input("Early CGR (STB/MMscf)", value=float(cfg('cgr_stb_mmscf', 25.0)))
            wgr_early = c3.number_input("Early WGR (bbl/MMscf)", value=float(cfg('wgr_bbl_mmscf', 5.0)))
            q_liq_early, wc_early, gor_early = 0.0, 0.0, 0.0
        else:
            q_liq_early = c2.number_input("Early Liquid Rate (STB/D)", value=float(cfg('q_liquid', 5000.0))) 
            wc_early = c2.number_input("Early Water Cut (%)", value=float(cfg('water_cut', 5.0))) 
            gor_early = c3.number_input("Early GOR (scf/STB)", value=float(cfg('gor', 800.0)))
            q_gas_early, cgr_early, wgr_early = 0.0, 0.0, 0.0
        bht_early = c3.number_input("Early BHT (°F)", value=float(cfg('t_bht', 210.0)))

    with tab_late: 
        c1, c2 = st.columns(2) 
        decline_rate = c1.number_input("Annual Field Decline (%)", value=float(cfg('decline_rate', 8.0)))
        field_life = c1.number_input("Field Life (Years)", value=int(cfg('field_life_yrs', 20)))

    st.markdown("---")
    if st.button("💾 Save Inputs & Operational State", type="primary"): 
        st.session_state.inputs.update({ 
            "well_type": well_type, "tvd": tvd, "md": md, "dls": dls, "casing_id": casing_id,
            "cithp": cithp_input, "sf_triaxial": sf_triaxial, "annular_fluid": annular_fluid,
            "api_gravity": api_gravity, "gas_sg": gas_sg, "oil_visc": oil_visc, "h2s_ppm": h2s_ppm,
            "co2_mole_pct": co2_pct, "lithology": lithology, "p_bhp": p_bhp_early, "p_wh": p_wh_early,
            "t_bht": bht_early, "decline_rate": decline_rate, "field_life_yrs": field_life
        })
        if "Gas" in well_type:
            st.session_state.inputs.update({"q_gas_mmscfd": q_gas_early, "cgr_stb_mmscf": cgr_early, "wgr_bbl_mmscf": wgr_early})
        else:
            st.session_state.inputs.update({"q_liquid": q_liq_early, "water_cut": wc_early, "gor": gor_early})
        st.success("✅ Inputs saved successfully!")

# -----------------------------------------------------------------------------
# PAGE 4: CANDIDATE TUBING SPECS
# -----------------------------------------------------------------------------
elif page == "4. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 4: Candidate Tubing Database</div>', unsafe_allow_html=True)
    
    col_f1, col_f2 = st.columns(2)
    selected_sizes = col_f1.multiselect("Filter OD:", options=sorted(st.session_state.tubing_db['OD_in'].unique()), default=sorted(st.session_state.tubing_db['OD_in'].unique()))
    selected_grades = col_f2.multiselect("Filter Steel Grade:", options=sorted(st.session_state.tubing_db['Grade'].unique()), default=sorted(st.session_state.tubing_db['Grade'].unique()))

    filtered_db = st.session_state.tubing_db[(st.session_state.tubing_db['OD_in'].isin(selected_sizes)) & (st.session_state.tubing_db['Grade'].isin(selected_grades))]
    st.dataframe(filtered_db, use_container_width=True, height=400)

# -----------------------------------------------------------------------------
# PAGE 5: ENGINEERING CALCULATIONS
# -----------------------------------------------------------------------------
elif page == "5. Engineering Calculations":
    st.markdown('<div class="main-header">Step 5: Engineering Calculation Engine</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts',
        'dp_total_psi', 'dp_apb_psi', 'cithp_psi', 'f_axial_klbs', 'vme_stress_psi', 'triaxial_sf', 'burst_sf', 'Material_Reason', 'Temp_Reason', 'Overall_Pass'
    ]].copy()
    display_df.columns = ['Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel', 'Late Vel', 'Total dP', 'APB (psi)', 'CITHP', 'Axial (klbs)', 'vME Stress', 'Triaxial SF', 'Burst SF', 'NACE', 'Temp', 'Status']
    
    st.dataframe(display_df, use_container_width=True, height=450)

# -----------------------------------------------------------------------------
# PAGE 6: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "6. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 6: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    passed = res_df[res_df['Overall_Pass'] == True]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if not passed.empty:
            pref = passed.sort_values(by='dp_total_psi').iloc[0]
            st.success("### Recommended Candidate")
            st.markdown(f"## **{pref['Name']}**")
            st.metric("Total Pressure Drop", f"{pref['dp_total_psi']} psi")
            st.metric("Flow Velocity", f"{pref['Velocity_fts']} ft/s")
            st.metric("Triaxial Safety Factor", f"{pref['triaxial_sf']}")
            st.metric("Surface Burst SF (CITHP)", f"{pref['burst_sf']}")
        else:
            st.error("No Candidates Passed All Screenings!")

    with col2:
        st.subheader("Engineering Rationale")
        if not passed.empty:
            pref = passed.sort_values(by='dp_total_psi').iloc[0]
            st.markdown(f"""
            * **Hydraulics:** Pressure drop (**{pref['dp_total_psi']} psi**) fits drawdown drive (**{pref['dp_avail_psi']} psi**).
            * **Velocity Window:** Initial velocity (**{pref['Velocity_fts']} ft/s**) remains inside Turner (**{pref['v_critical']} ft/s**) and Erosion (**{pref['v_erosional']} ft/s**) limits.
            * **Burst & Stress:** CITHP burst safety factor of **{pref['burst_sf']}** ($SF \ge 1.10$) and von Mises SF of **{pref['triaxial_sf']}**.
            * **Connection Profile:** {pref['Connection_Reason']}
            """)

    # GEMINI AI SUMMARY ENGINE
    st.markdown("---")
    if st.button("✨ Generate AI Executive Summary", type="primary"):
        api_key = st.secrets.get("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
        if not api_key:
            st.error("⚠️ GEMINI_API_KEY missing from Streamlit Secrets.")
        elif passed.empty:
            st.warning("Cannot generate report: No passed candidates.")
        else:
            with st.spinner("Generating memo via Gemini API..."):
                try:
                    pref = passed.sort_values(by='dp_total_psi').iloc[0]
                    prompt = f"Write executive completion memo for asset manager. Rec Candidate: {pref['Name']}, Grade: {pref['Grade']}, dP: {pref['dp_total_psi']} psi, Burst SF: {pref['burst_sf']}, Triaxial SF: {pref['triaxial_sf']}, Connection: {pref['Connection_Reason']}."
                    
                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                    req = urllib.request.Request(
                        url, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8'),
                        headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key}, method='POST'
                    )
                    with urllib.request.urlopen(req) as resp:
                        res = json.loads(resp.read().decode('utf-8'))
                        st.info(res['candidates'][0]['content']['parts'][0]['text'])
                except Exception as e:
                    st.error(f"Gemini API Error: {str(e)}")

    # SENSITIVITY PLOTS
    st.markdown("---")
    t1, t2 = st.tabs(["Pressure Drop vs. ID", "Velocity Window vs. ID"])
    with t1:
        fig1 = px.line(res_df, x="ID_in", y="dp_total_psi", color="Grade", markers=True, title="Pressure Drop vs. Tubing ID")
        st.plotly_chart(fig1, use_container_width=True)
    with t2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['Velocity_fts'], name='Initial Velocity'))
        fig2.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_erosional'], name='Max Erosional Limit', line=dict(dash='dash', color='red')))
        fig2.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_critical'], name='Min Liquid Loading Limit', line=dict(dash='dot', color='orange')))
        st.plotly_chart(fig2, use_container_width=True)