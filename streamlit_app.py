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

# Responsive, theme-aware CSS (Supports Light & Dark mode seamlessly)
st.markdown("""
    <style>
    /* Global Typography & Variable Overrides */
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: var(--text-color);
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: var(--text-color);
        opacity: 0.75;
        margin-bottom: 1.5rem;
    }

    /* Helper Card Component */
    .custom-card {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    /* Custom Metric Display Cards */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
        margin-bottom: 1.25rem;
    }
    .metric-card-box {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF !important;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .metric-card-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.9;
        margin-bottom: 0.25rem;
    }
    .metric-card-value {
        font-size: 1.35rem;
        font-weight: 700;
    }

    /* Clean Table Formatting */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        font-size: 0.95rem;
    }
    .styled-table th {
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        font-weight: 600;
        padding: 10px 14px;
        text-align: left;
        border-bottom: 2px solid rgba(128, 128, 128, 0.3);
    }
    .styled-table td {
        padding: 10px 14px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.15);
        color: var(--text-color);
    }
    </style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# UI HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def render_card(title: str, content_html: str, accent_color: str = "#2563EB"):
    """Renders a theme-aware styled card with an accent left border."""
    st.markdown(
        f"""
        <div class="custom-card" style="border-left: 4px solid {accent_color};">
            <h3 style="margin-top:0; margin-bottom:0.6rem; font-size:1.25rem; font-weight:700;">{title}</h3>
            {content_html}
        </div>
        """,
        unsafe_allow_html=True
    )


# Inline fallback SVG icon for offline / corporate network safety
SIDEBAR_ICON_SVG = """
<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
  <path d="M5 22h14"/>
</svg>
"""

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION & CSV LOADER
# -----------------------------------------------------------------------------
if 'inputs' not in st.session_state:
    st.session_state.inputs = {
        'well_type': 'Oil Well',
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
    p_pc = 677.0 + 15.0 * gas_sg - 37.5 * (gas_sg**2)
    t_pc = 168.0 + 325.0 * gas_sg - 12.5 * (gas_sg**2)
    p_pr = p_psi / p_pc
    t_pr = t_deg_r / t_pc

    A = 1.39 * (t_pr - 0.92) ** 0.5 - 0.36 * t_pr - 0.101
    E = 9.0 * (t_pr - 1.0)
    F = 0.310 - 0.49 * t_pr + 0.1 * (t_pr**2)
    Y = 0.27 * p_pr / t_pr

    z = A + (1.0 - A) / np.exp(E) + F * (Y**D if 'D' in locals() else Y**1.2)
    # Standard Papay Explicit Formulation:
    z = 1.0 - (3.52 * p_pr / (10 ** (0.9813 * t_pr))) + (
        0.274 * (p_pr**2) / (10 ** (0.8157 * t_pr))
    )
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
    
    p_h2s_psia = inputs['p_bhp'] * (inputs['h2s_ppm'] / 1e6)
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
        
        c_factor = 120.0 if inputs['well_type'] == 'Gas Well' else 140.0
        v_erosional = c_factor / np.sqrt(rho_m)
        sigma_dynes = 20.0
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        
        dp_available = inputs['p_bhp'] - inputs['p_wh']
        
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_critical_loading < v_m < v_erosional
        late_life_pass = v_m_late >= v_critical_loading
        
        rho_annulus = fluid_props.get(
            'density_lbft3', 62.4
        )  # e.g., 62.4 lb/ft3 for light brine
        rho_buoy_factor = 1.0 - (rho_annulus / 490.0)
        f_gravity_lbs = row['Weight_lbft'] * inputs['md'] * rho_buoy_factor
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

        material_pass = True
        mat_reason = "Compatible"
        
    # Explicit NACE MR0175 Qualified List for Sour Service (P_H2S >= 0.05 psia)
    NACE_APPROVED_GRADES = {
        "L80-1",
        "L80-13CR",
        "S13CR-110",
        "17CR-110",
        "22CR-110",
        "25CR-125",
        "C95",
        "T95",
}

    if is_sour_service:
        if grade_str not in NACE_APPROVED_GRADES:
            material_pass = False
            mat_reason = (
                f"Fail: NACE MR0175 violation (pH2S = {round(p_h2s_psia, 3)} psia >="
                f" 0.05). Grade {grade_str} is not SSC resistant."
            )

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
st.sidebar.markdown(SIDEBAR_ICON_SVG, unsafe_allow_html=True)
st.sidebar.title("Tubing Selection Tool")
st.sidebar.caption("Upper-Completion Optimization Engine")

page = st.sidebar.radio(
    "Select Workflow Step:",
    [
        "1. Introduction & Overview",
        "2. Well & Fluid Inputs",
        "3. Candidate Tubing Specs",
        "4. Engineering Calculations",
        "5. Recommendation & Sensitivity"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("**Project Stage:** Upper Completion Optimization\n\n**Core Engine:** Field Units (Imperial)")

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    st.markdown('<div class="main-header">Interactive Tubing Selection Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upper-Completion Optimization Engine for Varying Well Conditions</div>', unsafe_allow_html=True)
    
    if os.path.exists("image.png"):
        st.image("image.png", caption="Offshore Production Facility — Upper Completion Overview", use_container_width=True)
    
    render_card(
        "What is Upper Completion?",
        """<p style="font-size: 1.05rem; line-height: 1.6; margin-bottom: 0;">
        The <b>upper completion</b> is the portion of a well completion located <b>above the lower or reservoir completion</b>, extending to the <b>wellhead and surface facilities</b>. It provides the main pathway for <b>produced or injected fluids</b>. Depending on the well requirements, it may include <b>production tubing, packers, subsurface safety valves, artificial lift systems, and chemical-injection systems</b>.
        </p>""",
        accent_color="#1E3A8A"
    )

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        render_card(
            "Upper Completion Configurations",
            """<p style="font-size: 0.95rem; line-height: 1.5;">Common configurations include:</p>
            <ul style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 0; padding-left: 1.2rem;">
                <li><b>Tubingless completion:</b> fluids flow through the casing.</li>
                <li><b>Tubing without packer:</b> tubing is installed without annular isolation.</li>
                <li><b>Tubing with packer:</b> the packer isolates the tubing–casing annulus.</li>
                <li><b>Dual tubing with packers:</b> provides separate flow paths for multiple zones or fluids.</li>
            </ul>""",
            accent_color="#2563EB"
        )

        if os.path.exists("Figure 1.png"):
            st.image("Figure 1.png", caption="Figure 1: Upper-completion configurations", use_container_width=True)

        render_card(
            "Major Design Decisions",
            """<p style="font-size: 0.95rem; line-height: 1.5;">Key decisions include:</p>
            <ul style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 0; padding-left: 1.2rem;">
                <li><b>Artificial lift:</b> e.g., gas lift or ESP.</li>
                <li><b>Tubing size:</b> balances production capacity and pressure drop.</li>
                <li><b>Completion configuration:</b> single or dual completion.</li>
                <li><b>Tubing isolation:</b> using a <b>packer or equivalent</b> to control fluid communication.</li>
            </ul>""",
            accent_color="#2563EB"
        )

    with col2:
        render_card(
            "Key Components",
            """<p style="font-size: 0.95rem; line-height: 1.6; margin-bottom: 0;">
            Typical components include <b>production tubing, packers, subsurface safety valves (SCSSVs), artificial-lift equipment, and chemical-injection systems</b>. Together, they enable <b>safe fluid transport, well control, well integrity, and future intervention</b>.
            </p>""",
            accent_color="#10B981"
        )

        if os.path.exists("Figure 2.jpg"):
            st.image("Figure 2.jpg", caption="Figure 2: Typical upper-completion components", use_container_width=True)

    st.markdown("---")
    
    render_card(
        "Production Tubing: The Flow Path of the Well",
        """<p style="font-size: 1.05rem; line-height: 1.6; margin-bottom: 0;">
        <b>Production tubing</b> is the primary conduit that transports <b>oil, gas, or injected fluids</b> between the reservoir and surface facilities. Its design must balance <b>flow performance, mechanical integrity, and operational requirements</b>. Key considerations include <b>tubing size, wall thickness, steel grade, connection type, and mechanical strength</b>, ensuring the tubing can withstand the pressure, temperature, and loads encountered throughout the well's life.
        </p>""",
        accent_color="#059669"
    )

    if os.path.exists("Figure 3.jpg"):
        st.image("Figure 3.jpg", caption="Figure 3 — Production tubing in a completed well", use_container_width=True)

    with st.container():
        st.subheader("Key Tubing Specifications")
        st.markdown("""
        <table class="styled-table">
            <thead>
                <tr>
                    <th style="width: 30%;">Specification</th>
                    <th style="width: 70%;">Importance</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b>Nominal size / OD</b></td>
                    <td>Determines the overall tubing size and compatibility with the casing.</td>
                </tr>
                <tr>
                    <td><b>Internal diameter (ID)</b></td>
                    <td>Influences <b>fluid velocity and pressure loss</b>.</td>
                </tr>
                <tr>
                    <td><b>Drift diameter</b></td>
                    <td>Determines the maximum equipment diameter that can pass through the tubing.</td>
                </tr>
                <tr>
                    <td><b>Nominal weight</b></td>
                    <td>Indicates tubing weight and is related to <b>wall thickness</b>.</td>
                </tr>
                <tr>
                    <td><b>Steel grade</b></td>
                    <td>Determines <b>strength and suitability for corrosive environments</b>.</td>
                </tr>
                <tr>
                    <td><b>Connection</b></td>
                    <td>Affects connection strength and tubing integrity.</td>
                </tr>
                <tr>
                    <td><b>Joint length</b></td>
                    <td>Influences running and handling operations during completion and workover.</td>
                </tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)

    if os.path.exists("Figure 4.png"):
        st.image("Figure 4.png", caption="Figure 4 — Tubing dimensions", use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: WELL & FLUID INPUTS
# -----------------------------------------------------------------------------
elif page == "2. Well & Fluid Inputs":
    st.markdown('<div class="main-header">Step 2: Well & Operating Inputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Define subsurface geometry, production rates, PVT properties, APB factors, and lifecycle targets.</div>', unsafe_allow_html=True)
    
    well_type = st.radio("Select Operating Well Type:", ["Oil Well", "Gas Well"], horizontal=True, index=0 if st.session_state.inputs['well_type'] == 'Oil Well' else 1)

    with st.form("inputs_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Well Geometry & Thermal Conditions")
            tvd = st.number_input("True Vertical Depth (TVD) [ft]", value=st.session_state.inputs['tvd'], min_value=1000.0, max_value=25000.0)
            md = st.number_input("Measured Depth (MD) [ft]", value=st.session_state.inputs['md'], min_value=1000.0, max_value=30000.0)
            dls = st.number_input("Dogleg Severity (DLS) [°/100 ft]", value=st.session_state.inputs.get('dls', 1.5), min_value=0.0, max_value=15.0)
            p_wh = st.number_input("Wellhead Pressure (P_wh) [psi]", value=st.session_state.inputs['p_wh'], min_value=10.0, max_value=5000.0)
            p_bhp = st.number_input("Bottomhole Pressure (P_bhp) [psi]", value=st.session_state.inputs['p_bhp'], min_value=100.0, max_value=15000.0)
            t_wh = st.number_input("Wellhead Temperature [°F]", value=st.session_state.inputs['t_wh'], min_value=40.0, max_value=200.0)
            t_bht = st.number_input("Bottomhole Temperature [°F]", value=st.session_state.inputs['t_bht'], min_value=80.0, max_value=450.0)
            
            st.subheader("APB & Annular Properties")
            t_ambient = st.number_input("Ambient Surface Temperature [°F]", value=st.session_state.inputs.get('t_ambient', 60.0), min_value=30.0, max_value=120.0)
            annular_fluid = st.selectbox(
                "Annular Packer Fluid Type", 
                ["Fresh Water / Light Brine", "Heavy Brine (CaCl2/ZnBr2)", "Oil-Based Packer Fluid (OBM)"],
                index=0
            )

            st.subheader("Production Rates")
            q_liquid = st.number_input("Target Production Rate [STB/day or Mscf/d]", value=st.session_state.inputs['q_liquid'], min_value=50.0, max_value=100000.0)
            water_cut = st.number_input("Water Cut [%]", value=st.session_state.inputs['water_cut'], min_value=0.0, max_value=100.0)
            gor = st.number_input("Gas-Oil Ratio (GOR) [scf/STB]", value=st.session_state.inputs['gor'], min_value=0.0, max_value=50000.0)

        with col2:
            st.subheader("Fluid PVT Properties")
            api_gravity = st.number_input("Oil Gravity [°API]", value=st.session_state.inputs['api_gravity'], min_value=10.0, max_value=60.0)
            gas_sg = st.number_input("Gas Specific Gravity [Air = 1.0]", value=st.session_state.inputs['gas_sg'], min_value=0.55, max_value=0.95)
            water_sg = st.number_input("Water Specific Gravity [Fresh = 1.0]", value=st.session_state.inputs['water_sg'], min_value=1.00, max_value=1.25)
            oil_visc = st.number_input("Oil Viscosity [cP]", value=st.session_state.inputs['oil_visc'], min_value=0.1, max_value=200.0)

            st.subheader("Environmental & Corrosion Factors")
            co2_mole_pct = st.number_input("CO₂ Concentration [mole %]", value=st.session_state.inputs['co2_mole_pct'], min_value=0.0, max_value=50.0)
            h2s_ppm = st.number_input("H₂S Concentration [PPM]", value=st.session_state.inputs.get('h2s_ppm', 50.0), min_value=0.0, max_value=100000.0)
            ph_val = st.number_input("In-Situ Fluid pH", value=st.session_state.inputs.get('ph_val', 5.5), min_value=2.0, max_value=9.0)
            chlorides_ppm = st.number_input("Water Chloride Content [PPM]", value=st.session_state.inputs['chlorides_ppm'], min_value=0.0, max_value=250000.0)

            st.subheader("Field Life & Lifecycle Capacity")
            field_life_yrs = st.number_input("Target Field Life [Years]", value=st.session_state.inputs['field_life_yrs'], min_value=1, max_value=40)
            decline_rate = st.number_input("Annual Reservoir Decline Rate [%/year]", value=st.session_state.inputs['decline_rate'], min_value=0.0, max_value=30.0)

        submitted = st.form_submit_button("Save Inputs & Update Model")
        if submitted:
            if md < tvd:
                st.error("Validation Error: Measured Depth (MD) must be greater than or equal to True Vertical Depth (TVD).")
            else:
                st.session_state.inputs.update({
                    'well_type': well_type,
                    'tvd': tvd, 'md': md, 'dls': dls, 'p_wh': p_wh, 'p_bhp': p_bhp, 't_wh': t_wh, 't_bht': t_bht,
                    't_ambient': t_ambient, 'annular_fluid': annular_fluid,
                    'q_liquid': q_liquid, 'water_cut': water_cut, 'gor': gor,
                    'api_gravity': api_gravity, 'gas_sg': gas_sg, 'water_sg': water_sg, 'oil_visc': oil_visc,
                    'co2_mole_pct': co2_mole_pct, 'h2s_ppm': h2s_ppm, 'ph_val': ph_val, 'chlorides_ppm': chlorides_ppm,
                    'field_life_yrs': field_life_yrs, 'decline_rate': decline_rate
                })
                st.success("Inputs saved successfully! Proceed to Page 3 or 4.")

# -----------------------------------------------------------------------------
# PAGE 3: CANDIDATE TUBING SPECS
# -----------------------------------------------------------------------------
elif page == "3. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 3: Candidate Tubing Database</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Manage standard API tubing & casing dimensions (up to 9.625" OD), steel grades, UNS designations, and mechanical limits.</div>', unsafe_allow_html=True)
    
    st.subheader("Database Filter Controls")
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
    
    with st.expander("Add Custom Tubing Candidate"):
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
# PAGE 4: ENGINEERING CALCULATIONS
# -----------------------------------------------------------------------------
elif page == "4. Engineering Calculations":
    st.markdown('<div class="main-header">Step 4: Engineering Calculation Engine</div>', unsafe_allow_html=True)
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
    
    with st.expander("Show Governing Equations & Technical Correlations"):
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
# PAGE 5: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "5. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 5: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, structural checks, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    passed_candidates = res_df[res_df['Overall_Pass'] == True]
    
    col1, col2 = st.columns([1.1, 1.9], gap="medium")
    
    with col1:
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            
            st.success(f"### Preferred Candidate\n## **{preferred['Name']}**")
            
            # Styled Custom Metric Grid
            st.markdown(f"""
            <div class="metric-grid">
                <div class="metric-card-box">
                    <div class="metric-card-title">Total Pressure Drop</div>
                    <div class="metric-card-value">{preferred['dp_total_psi']} psi</div>
                </div>
                <div class="metric-card-box">
                    <div class="metric-card-title">Flow Velocity</div>
                    <div class="metric-card-value">{preferred['Velocity_fts']} ft/s</div>
                </div>
                <div class="metric-card-box">
                    <div class="metric-card-title">Material Grade</div>
                    <div class="metric-card-value">{preferred['Grade']}</div>
                </div>
                <div class="metric-card-box">
                    <div class="metric-card-title">Connection Type</div>
                    <div class="metric-card-value">{preferred['Connection']}</div>
                </div>
                <div class="metric-card-box">
                    <div class="metric-card-title">Triaxial SF</div>
                    <div class="metric-card-value">{preferred['triaxial_sf']}</div>
                </div>
                <div class="metric-card-box">
                    <div class="metric-card-title">APB Rise</div>
                    <div class="metric-card-value">{preferred['dp_apb_psi']} psi</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
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
    st.subheader("AI-Powered Executive Completion Memo")
    st.caption("Generates a dynamic technical narrative grounded strictly on Python calculation outputs.")

    if st.button("Generate AI Executive Summary", type="primary"):
        raw_key = st.secrets.get("GEMINI_API_KEY", "")
        api_key = raw_key.strip().replace('"', '').replace("'", "")
        
        if not api_key:
            st.error("GEMINI_API_KEY not found in Streamlit Secrets! Please add it in App Settings -> Secrets.")
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

                    render_card(
                        "AI Executive Memorandum",
                        ai_text,
                        accent_color="#0284C7"
                    )

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