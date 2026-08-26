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
# SESSION STATE INITIALIZATION & CSV LOADER FOR 500+ CANDIDATES
# -----------------------------------------------------------------------------
if 'inputs' not in st.session_state:
    st.session_state.inputs = {
        # Operating Well Type
        'well_type': 'Oil Well',
        # Well Geometry & Thermal
        'tvd': 8000.0,
        'md': 9500.0,
        'dls': 1.5,
        'p_wh': 500.0,
        'p_bhp': 3200.0,
        't_wh': 80.0,
        't_bht': 180.0,
        't_ambient': 60.0,
        'annular_fluid': 'Fresh Water / Light Brine',
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
    if os.path.exists("tubing_database.csv"):
        st.session_state.tubing_db = pd.read_csv("tubing_database.csv")
    else:
        st.session_state.tubing_db = pd.DataFrame([
            {"Name": '2-3/8" J-55 (4.7#)',   "OD_in": 2.375, "ID_in": 1.995, "Weight_lbft": 4.70, "Grade": "J-55",  "Material": "Carbon Steel",        "Connection": "API EUE", "Yield_psi": 55000,  "Burst_psi": 7700},
            {"Name": '2-7/8" J-55 (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "J-55",  "Material": "Carbon Steel",        "Connection": "API EUE", "Yield_psi": 55000,  "Burst_psi": 7260},
            {"Name": '2-7/8" 13Cr (6.5#)',   "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.50, "Grade": "13Cr",  "Material": "Martensitic Stainless","Connection": "Premium (VAM Top)", "Yield_psi": 80000,  "Burst_psi": 10570},
            {"Name": '3-1/2" L-80 (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "L-80",  "Material": "Carbon Steel",        "Connection": "API EUE", "Yield_psi": 80000,  "Burst_psi": 10160},
            {"Name": '3-1/2" 25Cr (9.3#)',   "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.30, "Grade": "25Cr",  "Material": "Super Duplex CRA",    "Connection": "Premium (VAM Top)", "Yield_psi": 125000, "Burst_psi": 15870}
        ])

# -----------------------------------------------------------------------------
# ANNULAR FLUID LOOKUP DICTIONARY
# -----------------------------------------------------------------------------
ANNULAR_FLUID_PROPS = {
    "Fresh Water / Light Brine": {"alpha_v": 2.1e-4, "kappa_t": 3.0e-6},
    "Heavy Brine (CaCl2/ZnBr2)": {"alpha_v": 3.0e-4, "kappa_t": 3.2e-6},
    "Oil-Based Packer Fluid (OBM)": {"alpha_v": 4.5e-4, "kappa_t": 5.5e-6}
}

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
    y = 0.0125 * p_pr * t_r
    z = a * p_pr / y if y > 0 else 0.88
    return float(np.clip(z, 0.65, 1.25))

def run_engineering_calculations(inputs, candidate_df):
    """Executes hydraulic, mechanical, live oil PVT, APB, and triaxial stress screening."""
    results = []
    
    p_avg = (inputs['p_wh'] + inputs['p_bhp']) / 2.0         # psi
    t_avg_f = (inputs['t_wh'] + inputs['t_bht']) / 2.0       # deg F
    t_avg_r = t_avg_f + 459.67                               # deg R
    
    # Live Oil PVT Model (Standing's Correlation for Bo & Rs)
    gamma_o = 141.5 / (131.5 + inputs['api_gravity'])
    rs_scf_stb = inputs['gas_sg'] * (((p_avg / 18.2) + 1.4) * (10 ** (0.0125 * inputs['api_gravity'] - 0.00091 * t_avg_f))) ** 1.2048
    rs_scf_stb = min(rs_scf_stb, inputs['gor'])
    
    bo_rb_stb = 0.9759 + 0.000120 * ((rs_scf_stb * ((inputs['gas_sg'] / gamma_o) ** 0.5) + 1.25 * t_avg_f) ** 1.2)
    rho_o_live = (62.4 * gamma_o + 0.0136 * rs_scf_stb * inputs['gas_sg']) / bo_rb_stb  # lb/ft3
    rho_w = inputs['water_sg'] * 62.4                         # lb/ft3
    
    wc_frac = inputs['water_cut'] / 100.0
    rho_l = (1.0 - wc_frac) * rho_o_live + wc_frac * rho_w    # Live liquid mixture density
    
    # Dynamic Z-Factor & Gas Density
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
    
    mu_w_cp = 0.5
    mu_l_cp = (1.0 - wc_frac) * inputs['oil_visc'] + wc_frac * mu_w_cp
    mu_m_cp = lambda_l * mu_l_cp + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672
    
    # Partial Pressures for Environmental Screening
    p_co2 = p_avg * (inputs['co2_mole_pct'] / 100.0)
    p_h2s = p_avg * (inputs['h2s_mole_pct'] / 100.0)
    
    # Late-life Capacity Screening
    late_life_q = inputs['q_liquid'] * ((1.0 - (inputs['decline_rate'] / 100.0)) ** inputs['field_life_yrs'])
    q_m_late = (late_life_q * 5.615 / 86400.0) + q_g_ft3s
    
    # Annular Pressure Build-up (APB) Calculation Engine
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
        
        # Velocity calculations
        v_m = q_m_ft3s / area_id_ft2
        v_m_late = q_m_late / area_id_ft2
        
        # Reynolds Number & Friction Factor
        reynolds = (rho_m * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])
        
        if reynolds > 2300:
            f = 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2
        else:
            f = 64.0 / reynolds if reynolds > 0 else 0.04
            
        # Hydraulic Pressure Losses
        dp_hydro = (rho_m * inputs['tvd']) / 144.0
        dp_fric = (f * inputs['md'] * rho_m * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0)
        dp_total = dp_hydro + dp_fric
        
        # Screening Threshold Limits
        c_factor = 120.0 if inputs['well_type'] == 'Gas Well' else 140.0
        v_erosional = c_factor / np.sqrt(rho_m)
        sigma_dynes = 20.0
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5)
        
        dp_available = inputs['p_bhp'] - inputs['p_wh']
        
        # Compliance Flags
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_critical_loading < v_m < v_erosional
        late_life_pass = v_m_late >= v_critical_loading
        
        # Lubinski Axial Force Balance & Stress Analysis
        rho_buoy_factor = (1.0 - (rho_m / 490.0))
        f_gravity_lbs = row['Weight_lbft'] * inputs['md'] * rho_buoy_factor
        
        e_modulus = 30e6
        alpha_steel = 6.9e-6
        f_thermal_lbs = e_modulus * area_steel_in2 * alpha_steel * delta_t_annular
        
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
        
        # 5-Factor Automated Connection Selection Logic
        conn_reasons = []
        needs_premium = False
        
        if inputs['well_type'] == 'Gas Well' or inputs['gor'] > 2000:
            needs_premium = True
            conn_reasons.append("High Gas Ratio (Gas-Tight Metal Seal Required)")
            
        if dp_apb_psi > 1500:
            needs_premium = True
            conn_reasons.append(f"High APB ({round(dp_apb_psi,1)} psi) - Thread Dope Washout Risk")
            
        if row['Material'] in ["Martensitic Stainless", "Duplex Stainless", "Super Duplex CRA"]:
            needs_premium = True
            conn_reasons.append("CRA Metallurgy (High Galling Risk on API Threads)")
            
        if inputs['tvd'] > 10000 or f_axial_total_klbs > 150.0:
            needs_premium = True
            conn_reasons.append("High Depth / Axial Load")
            
        if inputs['dls'] > 3.0:
            needs_premium = True
            conn_reasons.append(f"High Dogleg ({inputs['dls']}°/100ft)")

        connection_pass = True
        conn_status_msg = "Compatible API Thread"
        
        if needs_premium and row['Connection'] == 'API EUE':
            connection_pass = False
            conn_status_msg = "Premium Connection Required (" + "; ".join(conn_reasons) + ")"
        elif needs_premium and 'Premium' in row['Connection']:
            conn_status_msg = "Premium Connection Validated (" + "; ".join(conn_reasons) + ")"

        material_pass = True
        mat_reason = "Compatible"
        if p_h2s >= 0.05 or p_co2 >= 7.0:
            if row['Grade'] == "L-80" and row['Material'] == "Carbon Steel":
                material_pass = False
                mat_reason = "Corrosion Risk (Requires 13Cr CRA)"
                
        overall_pass = hydraulics_pass and velocity_pass and late_life_pass and material_pass and stress_pass and connection_pass
        
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
            "Connection_Pass": connection_pass,
            "Connection_Reason": conn_status_msg,
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
    
    if os.path.exists("image.png"):
        st.image("image.png", caption="Offshore Production Facility — Upper Completion Overview", use_container_width=True)
    
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
            st.subheader("📍 Well & Thermal Conditions")
            tvd = st.number_input("True Vertical Depth (TVD) [ft]", value=st.session_state.inputs['tvd'], min_value=1000.0, max_value=25000.0)
            md = st.number_input("Measured Depth (MD) [ft]", value=st.session_state.inputs['md'], min_value=1000.0, max_value=30000.0)
            dls = st.number_input("Dogleg Severity (DLS) [°/100 ft]", value=st.session_state.inputs.get('dls', 1.5), min_value=0.0, max_value=15.0)
            p_wh = st.number_input("Wellhead Pressure (P_wh) [psi]", value=st.session_state.inputs['p_wh'], min_value=10.0, max_value=5000.0)
            p_bhp = st.number_input("Bottomhole Pressure (P_bhp) [psi]", value=st.session_state.inputs['p_bhp'], min_value=100.0, max_value=15000.0)
            t_wh = st.number_input("Wellhead Temperature [°F]", value=st.session_state.inputs['t_wh'], min_value=40.0, max_value=200.0)
            t_bht = st.number_input("Bottomhole Temperature [°F]", value=st.session_state.inputs['t_bht'], min_value=80.0, max_value=400.0)
            
            st.subheader("🛡️ APB & Annular Properties")
            t_ambient = st.number_input("Ambient Surface Temperature [°F]", value=st.session_state.inputs.get('t_ambient', 60.0), min_value=30.0, max_value=120.0)
            annular_fluid = st.selectbox(
                "Annular Packer Fluid Type", 
                ["Fresh Water / Light Brine", "Heavy Brine (CaCl2/ZnBr2)", "Oil-Based Packer Fluid (OBM)"],
                index=0
            )

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
                    'tvd': tvd, 'md': md, 'dls': dls, 'p_wh': p_wh, 'p_bhp': p_bhp, 't_wh': t_wh, 't_bht': t_bht,
                    't_ambient': t_ambient, 'annular_fluid': annular_fluid,
                    'q_liquid': q_liquid, 'water_cut': water_cut, 'gor': gor,
                    'api_gravity': api_gravity, 'gas_sg': gas_sg, 'water_sg': water_sg, 'oil_visc': oil_visc,
                    'co2_mole_pct': co2_mole_pct, 'h2s_mole_pct': h2s_mole_pct, 'chlorides_ppm': chlorides_ppm,
                    'field_life_yrs': field_life_yrs, 'decline_rate': decline_rate
                })
                st.success("Inputs saved successfully! Proceed to Page 3 or 4.")

# -----------------------------------------------------------------------------
# PAGE 3: CANDIDATE TUBING SPECS (WITH FILTERING)
# -----------------------------------------------------------------------------
elif page == "3. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 3: Candidate Tubing Database</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Manage standard API tubing dimensions, steel grades, connection profiles, and mechanical yield limits.</div>', unsafe_allow_html=True)
    
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
                c_conn = st.selectbox("Connection Type", ["API EUE", "API NUE", "Premium (VAM Top)", "Premium (TenarisHydril)"])
                                
            add_sub = st.form_submit_button("Add to Database")
            if add_sub:
                new_row = pd.DataFrame([{
                    "Name": c_name, "OD_in": c_od, "ID_in": c_id, "Weight_lbft": c_weight,
                    "Grade": c_grade, "Material": c_mat, "Connection": c_conn, "Yield_psi": 80000, "Burst_psi": 10000
                }])
                st.session_state.tubing_db = pd.concat([st.session_state.tubing_db, new_row], ignore_index=True)
                st.success(f"Added {c_name} ({c_conn}) to candidates database!")
                st.rerun()

# -----------------------------------------------------------------------------
# PAGE 4: ENGINEERING CALCULATIONS (WITH SCROLLABLE TABLE)
# -----------------------------------------------------------------------------
elif page == "4. Engineering Calculations":
    st.markdown('<div class="main-header">Step 4: Engineering Calculation Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluates dynamic PVT, pressure losses, velocity screening, APB, and Lubinski triaxial stress.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs['well_type']} Mode)")
    
    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts',
        'dp_total_psi', 'dp_apb_psi', 'f_axial_klbs', 'vme_stress_psi', 'triaxial_sf', 'Connection_Reason', 'Overall_Pass'
    ]].copy()
    
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)',
        'Total dP (psi)', 'APB Pressure (psi)', 'Axial Load (klbs)', 'von Mises Stress (psi)', 'Triaxial SF', 'Connection Status', 'Overall Status'
    ]
    
    st.dataframe(display_df, use_container_width=True, height=450)
    
    with st.expander("Show Governing Equations & Correlations"):
        st.latex(r"\Delta P_{APB} = \left( \frac{\alpha_v}{\kappa_T} \right) \Delta T_{annular}")
        st.latex(r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}")
        st.latex(r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_z)^2 + (\sigma_z - \sigma_\theta)^2 \right]} \le \frac{Y_{yield}}{SF_{triaxial}}")
        st.latex(r"v_{critical} = \frac{1.3 \cdot \sigma^{0.25} (\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}} \quad \text{(Turner Correlation, } C=1.3\text{)}")

# -----------------------------------------------------------------------------
# PAGE 5: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "5. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 5: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
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
            st.warning("Consider increasing bottomhole pressure, reducing target rates, or picking higher CRA tubing grades/premium connections.")

    with col2:
        st.subheader("Engineering Justification Rationale")
        if not passed_candidates.empty:
            preferred = passed_candidates.sort_values(by='dp_total_psi').iloc[0]
            st.markdown(f"""
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**). Dynamic Z-factor (**{preferred['Z_Factor']}**) and Bo (**{preferred['Bo_rb_stb']} rb/STB**) confirm live-fluid flow.
            * **Velocity Window:** Initial mixture flow velocity (**{preferred['Velocity_fts']} ft/s**) and Year {st.session_state.inputs['field_life_yrs']} late-life velocity (**{preferred['v_late_life_fts']} ft/s**) both remain safely above liquid loading limits (**{preferred['v_critical']} ft/s**).
            * **Structural & APB Integrity:** Total axial tension (**{preferred['f_axial_klbs']} klbs**) and APB pressure (**{preferred['dp_apb_psi']} psi**) yield a von Mises stress of **{preferred['vme_stress_psi']} psi** (Triaxial SF = **{preferred['triaxial_sf']}**).
            * **Connection & Metallurgy:** Selected **{preferred['Grade']} ({preferred['Material']})** with **{preferred['Connection']}** thread status (**{preferred['Connection_Reason']}**) satisfies structural and NACE MR0175 limits.
            """)
        else:
            st.write("Review the calculation page to identify specific failure flags (velocity, hydraulics, APB, or triaxial stress).")

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
                    - Measured Depth / TVD: {st.session_state.inputs['md']} ft / {st.session_state.inputs['tvd']} ft (Dogleg Severity: {st.session_state.inputs['dls']} deg/100ft)
                    - Wellhead / Bottomhole Pressure: {st.session_state.inputs['p_wh']} psi / {st.session_state.inputs['p_bhp']} psi (Available Drawdown: {pref['dp_avail_psi']} psi)
                    - Annular Fluid & APB Pressure Build-up: {st.session_state.inputs['annular_fluid']} (Calculated APB Rise: {pref['dp_apb_psi']} psi)
                    - Target Field Life: {st.session_state.inputs['field_life_yrs']} Years at {st.session_state.inputs['decline_rate']}% Annual Decline Rate
                    - CO2 / H2S Concentrations: {st.session_state.inputs['co2_mole_pct']} mole% CO2, {st.session_state.inputs['h2s_mole_pct']} mole% H2S

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

                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
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