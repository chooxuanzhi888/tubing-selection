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
    .status-pass {
        color: #16A34A;
        font-weight: bold;
    }
    .status-fail {
        color: #DC2626;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if 'inputs' not in st.session_state:
    st.session_state.inputs = {
        # Operating Well Type
        'well_type': 'Oil Well',
        # Well Conditions
        'tvd': 8000.0,
        'md': 9500.0,
        'p_wh': 500.0,
        'p_bhp': 3200.0,
        't_wh': 80.0,
        't_bht': 180.0,
        # Production Rates
        'q_liquid': 3500.0,
        'water_cut': 25.0,
        'gor': 600.0,
        # Fluid PVT
        'api_gravity': 35.0,
        'gas_sg': 0.65,
        'water_sg': 1.02,
        'oil_visc': 1.5,
        # Environmental Contaminants
        'co2_mole_pct': 3.5,
        'h2s_mole_pct': 0.02,
        'chlorides_ppm': 25000.0,
        # Field Life & Lifecycle
        'field_life_yrs': 15,
        'decline_rate': 8.0
    }

if 'tubing_db' not in st.session_state:
    st.session_state.tubing_db = pd.DataFrame([
        # 2-3/8" Candidates
        {"Name": '2-3/8" J-55 (4.7#)',   "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.70, "Grade": "J-55",  "Material": "Carbon Steel",        "Yield_psi": 55000,  "Burst_psi": 7700},
        {"Name": '2-3/8" L-80 (4.7#)',   "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.70, "Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 11200},
        {"Name": '2-3/8" 13Cr (4.7#)',   "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.70, "Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 11200},
        
        # 2-7/8" Candidates
        {"Name": '2-7/8" J-55 (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "J-55",  "Material": "Carbon Steel",        "Yield_psi": 55000,  "Burst_psi": 7260},
        {"Name": '2-7/8" L-80 (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 10570},
        {"Name": '2-7/8" N-80 (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "N-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 10570},
        {"Name": '2-7/8" 13Cr (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 10570},
        {"Name": '2-7/8" P-110 (6.5#)',  "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "P-110", "Material": "High-Strength Alloy", "Yield_psi": 110000, "Burst_psi": 14530},
        {"Name": '2-7/8" 22Cr (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "22Cr",  "Material": "Duplex Stainless",    "Yield_psi": 110000, "Burst_psi": 14530},

        # 3-1/2" Candidates
        {"Name": '3-1/2" L-80 (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 10160},
        {"Name": '3-1/2" N-80 (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "N-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 10160},
        {"Name": '3-1/2" 13Cr (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 10160},
        {"Name": '3-1/2" P-110 (9.3#)',  "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "P-110", "Material": "High-Strength Alloy", "Yield_psi": 110000, "Burst_psi": 13970},
        {"Name": '3-1/2" 22Cr (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "22Cr",  "Material": "Duplex Stainless",    "Yield_psi": 110000, "Burst_psi": 13970},
        {"Name": '3-1/2" 25Cr (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "25Cr",  "Material": "Super Duplex CRA",    "Yield_psi": 125000, "Burst_psi": 15870},

        # 4" Candidates
        {"Name": '4" L-80 (11.0#)',      "OD_in": 4.000, "ID_in": 3.476, "Weight_lbft": 11.00,"Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 9520},
        {"Name": '4" 13Cr (11.0#)',      "OD_in": 4.000, "ID_in": 3.476, "Weight_lbft": 11.00,"Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 9520},
        {"Name": '4" P-110 (11.0#)',     "OD_in": 4.000, "ID_in": 3.476, "Weight_lbft": 11.00,"Grade": "P-110", "Material": "High-Strength Alloy", "Yield_psi": 110000, "Burst_psi": 13090},

        # 4-1/2" Candidates
        {"Name": '4-1/2" L-80 (12.6#)',  "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.60,"Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 8980},
        {"Name": '4-1/2" 13Cr (12.6#)',  "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.60,"Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 8980},
        {"Name": '4-1/2" P-110 (12.6#)', "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.60,"Grade": "P-110", "Material": "High-Strength Alloy", "Yield_psi": 110000, "Burst_psi": 12340},
        {"Name": '4-1/2" 25Cr (12.6#)',  "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.60,"Grade": "25Cr",  "Material": "Super Duplex CRA",    "Yield_psi": 125000, "Burst_psi": 14020},

        # 5-1/2" Candidates
        {"Name": '5-1/2" L-80 (17.0#)',  "OD_in": 5.500, "ID_in": 4.892, "Weight_lbft": 17.00,"Grade": "L-80",  "Material": "Carbon Steel",        "Yield_psi": 80000,  "Burst_psi": 7740},
        {"Name": '5-1/2" 13Cr (17.0#)',  "OD_in": 5.500, "ID_in": 4.892, "Weight_lbft": 17.00,"Grade": "13Cr",  "Material": "Martensitic Stainless","Yield_psi": 80000,  "Burst_psi": 7740},
        {"Name": '5-1/2" P-110 (17.0#)', "OD_in": 5.500, "ID_in": 4.892, "Weight_lbft": 17.00,"Grade": "P-110", "Material": "High-Strength Alloy", "Yield_psi": 110000, "Burst_psi": 10640},
    ])

# -----------------------------------------------------------------------------
# HELPER DYNAMIC PVT & CALCULATIONS ENGINE
# -----------------------------------------------------------------------------
def compute_dynamic_z_factor(p_psi, t_deg_r, gas_sg):
    """Calculates gas Z-factor dynamically via Sutton & Hall-Yarborough correlation."""
    p_pc = 756.8 - 131.07 * gas_sg - 3.6 * (gas_sg ** 2)
    t_pc = 169.2 + 349.5 * gas_sg - 74.0 * (gas_sg ** 2)
    p_pr = p_psi / p_pc
    t_pr = t_deg_r / t_pc
    
    t_r = 1.0 / t_pr
    a = 0.06125 * t_r * np.exp(-1.2 * (1.0 - t_r)**2)
    # Hall-Yarborough explicit approximation for Z
    y = 0.0125 * p_pr * t_r
    z = a * p_pr / y if y > 0 else 0.88
    return float(np.clip(z, 0.65, 1.25))

def run_engineering_calculations(inputs, candidate_df):
    """Executes hydraulic, mechanical, live oil PVT, and lifecycle screening."""
    results = []
    
    # Pressure & Temperature averages
    p_avg = (inputs['p_wh'] + inputs['p_bhp']) / 2.0         # psi
    t_avg_f = (inputs['t_wh'] + inputs['t_bht']) / 2.0       # deg F
    t_avg_r = t_avg_f + 459.67                               # deg R
    
    # 1. Live Oil PVT Model (Standing's Correlation for Bo & Rs)
    gamma_o = 141.5 / (131.5 + inputs['api_gravity'])
    rs_scf_stb = inputs['gas_sg'] * (((p_avg / 18.2) + 1.4) * (10 ** (0.0125 * inputs['api_gravity'] - 0.00091 * t_avg_f))) ** 1.2048
    rs_scf_stb = min(rs_scf_stb, inputs['gor'])              # Cap solution GOR at total GOR
    
    bo_rb_stb = 0.9759 + 0.000120 * ((rs_scf_stb * ((inputs['gas_sg'] / gamma_o) ** 0.5) + 1.25 * t_avg_f) ** 1.2)
    rho_o_live = (62.4 * gamma_o + 0.0136 * rs_scf_stb * inputs['gas_sg']) / bo_rb_stb  # lb/ft3
    rho_w = inputs['water_sg'] * 62.4                         # lb/ft3
    
    wc_frac = inputs['water_cut'] / 100.0
    rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w    # Live liquid mixture density
    
    # 2. Dynamic Z-Factor & Gas Density
    z_factor = compute_dynamic_z_factor(p_avg, t_avg_r, inputs['gas_sg'])
    rho_g = (2.7 * inputs['gas_sg'] * p_avg) / (z_factor * t_avg_r) # lb/ft3
    rho_g = max(rho_g, 0.05)
        
    # Volumetric Rates (ft3/s)
    q_l_ft3s = (inputs['q_liquid'] * 5.615) / 86400.0
    q_o_stb = inputs['q_liquid'] * (1.0 - wc_frac)
    free_gas_gor = max(inputs['gor'] - rs_scf_stb, 0.0)
    q_g_scf_d = q_o_stb * free_gas_gor
    
    # In-situ Gas Rate
    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg * 520.0 * 86400.0)
    q_m_ft3s = max(q_l_ft3s + q_g_ft3s, 1e-6)                 # Total mixture rate
    
    # No-slip Liquid Holdup & Viscosity Mixture
    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g        # Mixture density
    
    mu_w_cp = 0.5                                             # Water viscosity downhole approx
    mu_l_cp = (1.0 - wc_frac) * inputs['oil_visc'] + wc_frac * mu_w_cp
    mu_m_cp = lambda_l * mu_l_cp + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672
    
    # Partial Pressures for Environmental Screening
    p_co2 = p_avg * (inputs['co2_mole_pct'] / 100.0)
    p_h2s = p_avg * (inputs['h2s_mole_pct'] / 100.0)
    
    # Late-life Capacity Screening (End of Field Life Flow Rate)
    late_life_q = inputs['q_liquid'] * ((1.0 - (inputs['decline_rate'] / 100.0)) ** inputs['field_life_yrs'])
    q_m_late = (late_life_q * 5.615 / 86400.0) + q_g_ft3s
    
    for _, row in candidate_df.iterrows():
        id_ft = row['ID_in'] / 12.0
        area_ft2 = (np.pi / 4.0) * (id_ft ** 2)
        
        # Velocity calculations
        v_m = q_m_ft3s / area_ft2                              # ft/s
        v_m_late = q_m_late / area_ft2                         # Late-life velocity
        
        # Reynolds Number & Friction Factor
        reynolds = (rho_m * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])
        
        # Haaland Equation
        if reynolds > 2300:
            f = 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2
        else:
            f = 64.0 / reynolds if reynolds > 0 else 0.04
            
        # Pressure Losses
        dp_hydro = (rho_m * inputs['tvd']) / 144.0              # psi
        dp_fric = (f * inputs['md'] * rho_m * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0) # psi
        dp_total = dp_hydro + dp_fric                           # psi
        
        # Screening Threshold Limits
        c_factor = 120.0 if inputs['well_type'] == 'Gas Well' else 140.0
        v_erosional = c_factor / np.sqrt(rho_m)                 # API RP 14E limit
        sigma_dynes = 20.0
        
        # Turner Liquid Loading Limit (Fixed Constant C = 1.3)
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        
        # Pressure Available Check
        dp_available = inputs['p_bhp'] - inputs['p_wh']
        
        # Compliance Flags
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_critical_loading < v_m < v_erosional
        late_life_pass = v_m_late >= v_critical_loading        # Lifecycle liquid loading check
        
        # Material Compliance (NACE MR0175)
        material_pass = True
        mat_reason = "Compatible"
        if p_h2s >= 0.05 or p_co2 >= 7.0:
            if row['Grade'] == "L-80" and row['Material'] == "Carbon Steel":
                material_pass = False
                mat_reason = "Corrosion Risk (Requires 13Cr CRA)"
                
        # Overall Candidate Status
        overall_pass = hydraulics_pass and velocity_pass and late_life_pass and material_pass
        
        results.append({
            "Name": row['Name'],
            "OD_in": row['OD_in'],
            "ID_in": row['ID_in'],
            "Grade": row['Grade'],
            "Material": row['Material'],
            "Velocity_fts": round(v_m, 2),
            "v_late_life_fts": round(v_m_late, 2),
            "v_erosional": round(v_erosional, 2),
            "v_critical": round(v_critical_loading, 2),
            "dp_hydro_psi": round(dp_hydro, 1),
            "dp_fric_psi": round(dp_fric, 1),
            "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(dp_available, 1),
            "Z_Factor": round(z_factor, 3),
            "Bo_rb_stb": round(bo_rb_stb, 3),
            "Hydraulics_Pass": hydraulics_pass,
            "Velocity_Pass": velocity_pass,
            "Late_Life_Pass": late_life_pass,
            "Material_Pass": material_pass,
            "Material_Reason": mat_reason,
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
        "2. Well & Fluid Inputs",
        "3. Candidate Tubing Specs",
        "4. Engineering Calculations",
        "5. Recommendation & Sensitivity"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("**Project Stage:** Upper Completion Optimization\n**Core Engine:** Field Units (Imperial)")

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    st.markdown('<div class="main-header">Interactive Tubing Selection Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upper-Completion Optimization Engine for Varying Well Conditions</div>', unsafe_allow_html=True)
    
    # 1. Hero Offshore Rig Banner
    if os.path.exists("image.png"):
        st.image("image.png", caption="Offshore Production Facility — Upper Completion Overview", use_container_width=True)
    
    # 2. Section: What is Upper Completion?
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A;">
        <h2 style="color: #1E3A8A; font-size: 1.6rem; margin-bottom: 0.8rem; font-weight: 700;">What is Upper Completion?</h2>
        <p style="font-size: 1.05rem; line-height: 1.6; color: #1E293B;">
            The <b>upper completion</b> is the portion of a well completion located <b>above the lower or reservoir completion</b>, extending to the <b>wellhead and surface facilities</b>. It provides the main pathway for <b>produced or injected fluids</b>. Depending on the well requirements, it may include <b>production tubing, packers, subsurface safety valves, artificial lift systems, and chemical-injection systems</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")

    # -------------------------------------------------------------------------
    # LEFT COLUMN: Configurations -> Figure 1 -> Major Decisions
    # -------------------------------------------------------------------------
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

        # FIGURE 1
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

    # -------------------------------------------------------------------------
    # RIGHT COLUMN: Key Components -> Figure 2
    # -------------------------------------------------------------------------
    with col2:
        st.markdown("""
        <div class="card" style="border-top: 3px solid #10B981;">
            <h3 style="color: #1E3A8A; font-size: 1.25rem; margin-bottom: 0.6rem; font-weight: 700;">Key Components</h3>
            <p style="font-size: 0.95rem; line-height: 1.6; color: #1E293B; margin-bottom: 0;">
                Typical components include <b>production tubing, packers, subsurface safety valves (SCSSVs), artificial-lift equipment, and chemical-injection systems</b>. Together, they enable <b>safe fluid transport, well control, well integrity, and future intervention</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # FIGURE 2
        if os.path.exists("Figure 2.jpg"):
            st.image("Figure 2.jpg", caption="Figure 2: Typical upper-completion components", use_container_width=True)

    # -------------------------------------------------------------------------
    # SECTION 2: PRODUCTION TUBING: THE FLOW PATH OF THE WELL
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("""
    <div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #059669; margin-top: 1rem;">
        <h2 style="color: #065F46; font-size: 1.6rem; margin-bottom: 0.8rem; font-weight: 700;">Production Tubing: The Flow Path of the Well</h2>
        <p style="font-size: 1.05rem; line-height: 1.6; color: #1E293B;">
            <b>Production tubing</b> is the primary conduit that transports <b>oil, gas, or injected fluids</b> between the reservoir and surface facilities. Its design must balance <b>flow performance, mechanical integrity, and operational requirements</b>. Key considerations include <b>tubing size, wall thickness, steel grade, connection type, and mechanical strength</b>, ensuring the tubing can withstand the pressure, temperature, and loads encountered throughout the well's life.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Figure 3 displayed full-width above the specifications table
    if os.path.exists("Figure 3.jpg"):
        st.image("Figure 3.jpg", caption="Figure 3 — Production tubing in a completed well", use_container_width=True)

    # Key Tubing Specifications Table
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

    # Figure 4 positioned directly below the specifications table
    if os.path.exists("Figure 4.png"):
        st.image("Figure 4.png", caption="Figure 4 — Tubing dimensions", use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: WELL & FLUID INPUTS
# -----------------------------------------------------------------------------
elif page == "2. Well & Fluid Inputs":
    st.markdown('<div class="main-header">Step 2: Well & Operating Inputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Define subsurface geometry, production rates, PVT properties, and lifecycle targets.</div>', unsafe_allow_html=True)
    
    # Operating Well Type Selector
    well_type = st.radio("Select Operating Well Type:", ["Oil Well", "Gas Well"], horizontal=True, index=0 if st.session_state.inputs['well_type'] == 'Oil Well' else 1)

    with st.form("inputs_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📍 Well & Thermal Conditions")
            tvd = st.number_input("True Vertical Depth (TVD) [ft]", value=st.session_state.inputs['tvd'], min_value=1000.0, max_value=25000.0)
            md = st.number_input("Measured Depth (MD) [ft]", value=st.session_state.inputs['md'], min_value=1000.0, max_value=30000.0)
            p_wh = st.number_input("Wellhead Pressure (P_wh) [psi]", value=st.session_state.inputs['p_wh'], min_value=10.0, max_value=5000.0)
            p_bhp = st.number_input("Bottomhole Pressure (P_bhp) [psi]", value=st.session_state.inputs['p_bhp'], min_value=100.0, max_value=15000.0)
            t_wh = st.number_input("Wellhead Temperature [°F]", value=st.session_state.inputs['t_wh'], min_value=40.0, max_value=200.0)
            t_bht = st.number_input("Bottomhole Temperature [°F]", value=st.session_state.inputs['t_bht'], min_value=80.0, max_value=400.0)

            st.subheader("🛢️ Production Rates")
            q_liquid = st.number_input("Target Production Rate [STB/day or Mscf/d]", value=st.session_state.inputs['q_liquid'], min_value=50.0, max_value=100000.0)
            water_cut = st.number_input("Water Cut [%]", value=st.session_state.inputs['water_cut'], min_value=0.0, max_value=100.0)
            gor = st.number_input("Gas-Oil Ratio (GOR) [scf/STB]", value=st.session_state.inputs['gor'], min_value=0.0, max_value=50000.0)

        with col2:
            st.subheader("🧪 Fluid PVT Properties")
            api_gravity = st.number_input("Oil Gravity [°API]", value=st.session_state.inputs['api_gravity'], min_value=10.0, max_value=60.0)
            gas_sg = st.number_input("Gas Specific Gravity [Air = 1.0]", value=st.session_state.inputs['gas_sg'], min_value=0.55, max_value=0.95)
            water_sg = st.number_input("Water Specific Gravity [Fresh = 1.0]", value=st.session_state.inputs['water_sg'], min_value=1.00, max_value=1.25)
            oil_visc = st.number_input("Oil Viscosity [cP]", value=st.session_state.inputs['oil_visc'], min_value=0.1, max_value=200.0)

            st.subheader("☣️ Environmental & Corrosion Factors")
            co2_mole_pct = st.number_input("CO₂ Concentration [mole %]", value=st.session_state.inputs['co2_mole_pct'], min_value=0.0, max_value=50.0)
            h2s_mole_pct = st.number_input("H₂S Concentration [mole %]", value=st.session_state.inputs['h2s_mole_pct'], min_value=0.0, max_value=10.0)
            chlorides_ppm = st.number_input("Water Chloride Content [ppm]", value=st.session_state.inputs['chlorides_ppm'], min_value=0.0, max_value=200000.0)

            st.subheader("📅 Field Life & Lifecycle Capacity")
            field_life_yrs = st.number_input("Target Field Life [Years]", value=st.session_state.inputs['field_life_yrs'], min_value=1, max_value=40)
            decline_rate = st.number_input("Annual Reservoir Decline Rate [%/year]", value=st.session_state.inputs['decline_rate'], min_value=0.0, max_value=30.0)

        submitted = st.form_submit_button("Save Inputs & Update Model")
        if submitted:
            if md < tvd:
                st.error("Validation Error: Measured Depth (MD) must be greater than or equal to True Vertical Depth (TVD).")
            else:
                st.session_state.inputs.update({
                    'well_type': well_type,
                    'tvd': tvd, 'md': md, 'p_wh': p_wh, 'p_bhp': p_bhp, 't_wh': t_wh, 't_bht': t_bht,
                    'q_liquid': q_liquid, 'water_cut': water_cut, 'gor': gor,
                    'api_gravity': api_gravity, 'gas_sg': gas_sg, 'water_sg': water_sg, 'oil_visc': oil_visc,
                    'co2_mole_pct': co2_mole_pct, 'h2s_mole_pct': h2s_mole_pct, 'chlorides_ppm': chlorides_ppm,
                    'field_life_yrs': field_life_yrs, 'decline_rate': decline_rate
                })
                st.success("Inputs saved successfully! Proceed to Page 3 or 4.")

# -----------------------------------------------------------------------------
# PAGE 3: CANDIDATE TUBING SPECS
# -----------------------------------------------------------------------------
elif page == "3. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 3: Candidate Tubing Database</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Manage standard API tubing dimensions, steel grades, and mechanical yield limits.</div>', unsafe_allow_html=True)
    
    st.dataframe(st.session_state.tubing_db, use_container_width=True)
    
    with st.expander("Add Custom Tubing Candidate"):
        with st.form("add_candidate_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                c_name = st.text_input("Name", value='3-1/2" P-110')
                c_od = st.number_input("Outer Diameter (OD) [in]", value=3.500)
            with col2:
                c_id = st.number_input("Inner Diameter (ID) [in]", value=2.992)
                c_weight = st.number_input("Weight [lb/ft]", value=9.3)
            with col3:
                c_grade = st.selectbox("Grade", ["J-55", "L-80", "N-80", "13Cr", "P-110", "22Cr", "25Cr"])
                c_mat = st.selectbox("Material Type", ["Carbon Steel", "Martensitic Stainless", "High-Strength Alloy", "Duplex Stainless", "Super Duplex CRA"])
                                
            add_sub = st.form_submit_button("Add to Database")
            if add_sub:
                new_row = pd.DataFrame([{
                    "Name": c_name, "OD_in": c_od, "ID_in": c_id, "Weight_lbft": c_weight,
                    "Grade": c_grade, "Material": c_mat, "Yield_psi": 80000, "Burst_psi": 10000
                }])
                st.session_state.tubing_db = pd.concat([st.session_state.tubing_db, new_row], ignore_index=True)
                st.success(f"Added {c_name} to candidates database!")
                st.rerun()

# -----------------------------------------------------------------------------
# PAGE 4: ENGINEERING CALCULATIONS
# -----------------------------------------------------------------------------
elif page == "4. Engineering Calculations":
    st.markdown('<div class="main-header">Step 4: Engineering Calculation Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluates dynamic PVT, pressure losses, velocity screening, and late-life liquid loading.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    # Overview Summary Table
    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs['well_type']} Mode)")
    
    display_df = res_df[[
        'Name', 'ID_in', 'Velocity_fts', 'v_late_life_fts', 'v_critical', 'v_erosional', 
        'dp_hydro_psi', 'dp_fric_psi', 'dp_total_psi', 'Z_Factor', 'Bo_rb_stb', 'Material_Reason', 'Overall_Pass'
    ]].copy()
    
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)', 'Min Lift Vel (ft/s)', 'Max Erosional Vel (ft/s)',
        'Hydrostatic dP (psi)', 'Friction dP (psi)', 'Total dP (psi)', 'Dynamic Z', 'Bo (rb/STB)', 'Material Status', 'Overall Status'
    ]
    
    st.dataframe(display_df, use_container_width=True)
    
    # Calculation Formula Expanders
    with st.expander("Show Governing Equations & Correlations"):
        st.latex(r"Z = f(P_{pr}, T_{pr}) \quad \text{(Hall-Yarborough Correlation)}")
        st.latex(r"B_o = 0.9759 + 0.000120 \left[ R_s \left(\frac{\gamma_g}{\gamma_o}\right)^{0.5} + 1.25 T \right]^{1.2} \quad \text{(Standing Correlation)}")
        st.latex(r"\Delta P_{total} = \Delta P_{hydrostatic} + \Delta P_{friction}")
        st.latex(r"v_{critical} = \frac{1.3 \cdot \sigma^{0.25} (\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}} \quad \text{(Turner Correlation, } C=1.3\text{)}")

# -----------------------------------------------------------------------------
# PAGE 5: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "5. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 5: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
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
        else:
            st.error("### No Candidates Passed All Screenings!")
            st.warning("Consider increasing bottomhole pressure, reducing target rates, or picking higher CRA tubing grades.")

    with col2:
        st.subheader("Engineering Justification Rationale")
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            st.markdown(f"""
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**). Dynamic Z-factor (**{preferred['Z_Factor']}**) and Bo (**{preferred['Bo_rb_stb']} rb/STB**) confirm live-fluid flow.
            * **Velocity Window:** Initial mixture flow velocity (**{preferred['Velocity_fts']} ft/s**) and Year {st.session_state.inputs['field_life_yrs']} late-life velocity (**{preferred['v_late_life_fts']} ft/s**) both remain safely above liquid loading limits (**{preferred['v_critical']} ft/s**).
            * **Corrosion & Metallurgy:** Selected **{preferred['Grade']} ({preferred['Material']})** tubing satisfies NACE MR0175 requirements for $CO_2$ ({st.session_state.inputs['co2_mole_pct']} mole %) and $H_2S$ ({st.session_state.inputs['h2s_mole_pct']} mole %).
            """)
        else:
            st.write("Review the calculation page to identify specific failure flags (velocity, hydraulics, or corrosion).")

    # -------------------------------------------------------------------------
        # GEMINI AI EXECUTIVE SUMMARY ENGINE
        # -------------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🤖 AI-Powered Executive Completion Memo")
        st.caption("Generates a dynamic technical narrative grounded strictly on Python calculation outputs.")

        if st.button("✨ Generate AI Executive Summary", type="primary"):
            # Check for Gemini API key in Streamlit Secrets
            api_key = st.secrets.get("GEMINI_API_KEY", None)
            
            if not api_key:
                st.error("⚠️ GEMINI_API_KEY not found in Streamlit Secrets! Please add it in App Settings -> Secrets.")
            elif passed_candidates.empty:
                st.warning("Cannot generate executive report: No tubing candidates passed all technical screening thresholds.")
            else:
                with st.spinner("Analyzing hydraulics, velocity limits, and NACE compliance via Gemini AI..."):
                    try:
                        import google.generativeai as genai

                        # Configure Gemini with the API Key
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        # Construct strict raw numerical data payload
                        pref = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
                        
                        prompt_data = f"""
                        You are a Senior Completion Engineer writing an executive technical recommendation memo for an asset manager.
                        Synthesize the following PRE-CALCULATED Python engineering data into a concise, professional technical assessment.
                        DO NOT re-calculate or alter any numerical values. Rely STRICTLY on these provided facts:

                        WELL & OPERATIONAL PARAMETERS:
                        - Well Type: {st.session_state.inputs['well_type']}
                        - Measured Depth / TVD: {st.session_state.inputs['md']} ft / {st.session_state.inputs['tvd']} ft
                        - Wellhead / Bottomhole Pressure: {st.session_state.inputs['p_wh']} psi / {st.session_state.inputs['p_bhp']} psi (Available Drawdown: {pref['dp_avail_psi']} psi)
                        - Target Field Life: {st.session_state.inputs['field_life_yrs']} Years at {st.session_state.inputs['decline_rate']}% Annual Decline Rate
                        - CO2 / H2S Concentrations: {st.session_state.inputs['co2_mole_pct']} mole% CO2, {st.session_state.inputs['h2s_mole_pct']} mole% H2S

                        SELECTED PREFERRED TUBING CANDIDATE:
                        - Candidate Name: {pref['Name']}
                        - Steel Grade / Material: {pref['Grade']} ({pref['Material']})
                        - Total Calculated Pressure Drop: {pref['dp_total_psi']} psi (Hydrostatic: {pref['dp_hydro_psi']} psi, Friction: {pref['dp_fric_psi']} psi)
                        - Initial Flow Velocity: {pref['Velocity_fts']} ft/s
                        - Year {st.session_state.inputs['field_life_yrs']} Late-Life Velocity: {pref['v_late_life_fts']} ft/s
                        - Turner Critical Liquid Loading Limit: {pref['v_critical']} ft/s
                        - API RP 14E Max Erosional Velocity Limit: {pref['v_erosional']} ft/s
                        - Fluid PVT Outputs: Gas Z-Factor = {pref['Z_Factor']}, Bo = {pref['Bo_rb_stb']} rb/STB

                        INSTRUCTIONS:
                        1. Write a 3-paragraph executive technical memo.
                        2. Paragraph 1: State the recommended tubing size and grade, confirming drawdown hydraulic drive acceptability.
                        3. Paragraph 2: Discuss velocity window stability (initial vs late-life Turner liquid loading and erosional limits).
                        4. Paragraph 3: Explain the metallurgy selection under NACE MR0175 CO2/H2S partial pressure limits.
                        5. Keep tone formal, concise, and professional. Use markdown formatting with bold metrics.
                        """

                        response = model.generate_content(
                            prompt_data,
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.2
                            )
                        )

                        st.markdown("""
                        <div style="background-color: #F0F9FF; border: 1px solid #BAE6FD; border-left: 5px solid #0284C7; border-radius: 8px; padding: 1.25rem; margin-top: 1rem;">
                        """, unsafe_allow_html=True)
                        st.markdown(response.text)
                        st.markdown("</div>", unsafe_allow_html=True)

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
        **💡 How to Interpret Graph 1:**
        * **Red Dashed Line (Drawdown Limit):** Represents maximum available reservoir pressure drive ($P_{bhp} - P_{wh}$). Candidates operating **above** this line cannot flow naturally to the surface.
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
        
        st.info("""
        **💡 How to Interpret Graph 2:**
        * **Upper Red Limit (API RP 14E Erosional Velocity):** Operating above this line causes severe structural pipe wear and wall thinning due to high fluid kinetic energy.
        * **Lower Orange Limit (Turner Liquid Loading Velocity):** Operating below this line results in insufficient gas velocity to lift liquid droplets, causing liquid accumulation downhole and shutting in the well.
        * **Purple Dashed Line (Late-Life Velocity):** Demonstrates velocity reduction after reservoir decline. Tubing must keep the purple line **above** the orange limit to ensure long-term well performance.
        """)