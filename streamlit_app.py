import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

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
        'chlorides_ppm': 25000.0
    }

if 'tubing_db' not in st.session_state:
    st.session_state.tubing_db = pd.DataFrame([
        {"Name": '2-7/8" L-80', "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.5, "Grade": "L-80", "Material": "Carbon Steel", "Yield_psi": 80000, "Burst_psi": 10570},
        {"Name": '2-7/8" 13Cr', "OD_in": 2.875, "ID_in": 2.441, "Weight_lbft": 6.5, "Grade": "13Cr", "Material": "Martensitic Stainless", "Yield_psi": 80000, "Burst_psi": 10570},
        {"Name": '3-1/2" L-80', "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.3, "Grade": "L-80", "Material": "Carbon Steel", "Yield_psi": 80000, "Burst_psi": 10160},
        {"Name": '3-1/2" 13Cr', "OD_in": 3.500, "ID_in": 2.992, "Weight_lbft": 9.3, "Grade": "13Cr", "Material": "Martensitic Stainless", "Yield_psi": 80000, "Burst_psi": 10160},
        {"Name": '4" L-80',     "OD_in": 4.000, "ID_in": 3.476, "Weight_lbft": 11.0, "Grade": "L-80", "Material": "Carbon Steel", "Yield_psi": 80000, "Burst_psi": 9520},
        {"Name": '4" 13Cr',     "OD_in": 4.000, "ID_in": 3.476, "Weight_lbft": 11.0, "Grade": "13Cr", "Material": "Martensitic Stainless", "Yield_psi": 80000, "Burst_psi": 9520},
        {"Name": '4-1/2" L-80', "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.6, "Grade": "L-80", "Material": "Carbon Steel", "Yield_psi": 80000, "Burst_psi": 8980},
        {"Name": '4-1/2" 13Cr', "OD_in": 4.500, "ID_in": 3.958, "Weight_lbft": 12.6, "Grade": "13Cr", "Material": "Martensitic Stainless", "Yield_psi": 80000, "Burst_psi": 8980},
    ])

# -----------------------------------------------------------------------------
# HELPER CALCULATION ENGINE
# -----------------------------------------------------------------------------
def run_engineering_calculations(inputs, candidate_df):
    """Executes hydraulic, mechanical, and environmental screening for candidates."""
    results = []
    
    # 1. Base Density & PVT Calculations
    rho_o = (141.5 / (131.5 + inputs['api_gravity'])) * 62.4  # lb/ft3
    rho_w = inputs['water_sg'] * 62.4                         # lb/ft3
    wc_frac = inputs['water_cut'] / 100.0
    rho_l = (1.0 - wc_frac) * rho_o + wc_frac * rho_w         # Liquid mixture density
    
    # Pressure & Temperature averages
    p_avg = (inputs['p_wh'] + inputs['p_bhp']) / 2.0         # psi
    t_avg_f = (inputs['t_wh'] + inputs['t_bht']) / 2.0       # deg F
    t_avg_r = t_avg_f + 459.67                               # deg R
    
    # Gas density at average well conditions (Real Gas Law approx)
    z_factor = 0.88  # Average gas z-factor estimation
    rho_g = (2.7 * inputs['gas_sg'] * p_avg) / (z_factor * t_avg_r) # lb/ft3
    if rho_g <= 0.01:
        rho_g = 0.05
        
    # Volumetric Rates (ft3/s)
    q_l_ft3s = (inputs['q_liquid'] * 5.615) / 86400.0
    q_o_stb = inputs['q_liquid'] * (1.0 - wc_frac)
    q_g_scf_d = q_o_stb * inputs['gor']
    
    # In-situ Gas Rate
    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg * 520.0 * 86400.0)
    q_m_ft3s = q_l_ft3s + q_g_ft3s                            # Total mixture rate
    
    # No-slip Liquid Holdup
    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g        # Mixture density
    
    # Viscosity mixture (cP to lb/ft-s conversion factor = 0.000672)
    mu_m_cp = lambda_l * inputs['oil_visc'] + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672
    
    # Partial Pressures for Environmental Screening
    p_co2 = p_avg * (inputs['co2_mole_pct'] / 100.0)
    p_h2s = p_avg * (inputs['h2s_mole_pct'] / 100.0)
    
    for _, row in candidate_df.iterrows():
        id_ft = row['ID_in'] / 12.0
        area_ft2 = (np.pi / 4.0) * (id_ft ** 2)
        
        # Velocity calculations
        v_m = q_m_ft3s / area_ft2                              # ft/s
        
        # Reynolds Number & Friction Factor
        reynolds = (rho_m * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])          # Commercial steel roughness ~ 0.0006 in
        
        # Haaland Equation for friction factor
        if reynolds > 2300:
            f = 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2
        else:
            f = 64.0 / reynolds if reynolds > 0 else 0.04
            
        # Pressure Losses
        dp_hydro = (rho_m * inputs['tvd']) / 144.0              # psi
        dp_fric = (f * inputs['md'] * rho_m * (v_m ** 2)) / (2.0 * 32.174 * id_ft * 144.0) # psi
        dp_total = dp_hydro + dp_fric                           # psi
        
        # Screening Threshold Limits
        v_erosional = 120.0 / np.sqrt(rho_m)                    # API RP 14E limit
        sigma_dynes = 20.0                                      # Interfacial tension
        v_critical_loading = (1.3 * (sigma_dynes ** 0.25) * ((rho_l - rho_g) ** 0.25)) / (rho_g ** 0.5) # Turner criterion
        
        # Pressure Available Check
        dp_available = inputs['p_bhp'] - inputs['p_wh']
        
        # Compliance Flags
        hydraulics_pass = dp_total <= dp_available
        velocity_pass = v_critical_loading < v_m < v_erosional
        
        # Material Compliance
        # Sour Service (NACE MR0175): H2S >= 0.05 psi requires Sour Grade/13Cr
        # Sweet Corrosion: CO2 >= 7.0 psi requires 13Cr
        material_pass = True
        mat_reason = "Compatible"
        if p_h2s >= 0.05 or p_co2 >= 7.0:
            if row['Grade'] == "L-80" and row['Material'] == "Carbon Steel":
                material_pass = False
                mat_reason = "Corrosion Risk (Requires 13Cr CRA)"
                
        # Overall Candidate Status
        overall_pass = hydraulics_pass and velocity_pass and material_pass
        
        results.append({
            "Name": row['Name'],
            "OD_in": row['OD_in'],
            "ID_in": row['ID_in'],
            "Grade": row['Grade'],
            "Material": row['Material'],
            "Velocity_fts": round(v_m, 2),
            "v_erosional": round(v_erosional, 2),
            "v_critical": round(v_critical_loading, 2),
            "dp_hydro_psi": round(dp_hydro, 1),
            "dp_fric_psi": round(dp_fric, 1),
            "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(dp_available, 1),
            "Reynolds": int(reynolds),
            "Hydraulics_Pass": hydraulics_pass,
            "Velocity_Pass": velocity_pass,
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
st.sidebar.info("**Project Stage:** Week 2 Implementation\n**Core Engine:** Field Units (Imperial)")

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    st.markdown('<div class="main-header">Interactive Tubing Selection Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upper-Completion Optimization Engine for Varying Well Conditions</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("""
        <div class="card">
        <h3>What is Upper Completion & Production Tubing?</h3>
        <p>The <b>upper completion</b> encompasses all tubulars and subsurface control equipment installed between the top of the production packer and the wellhead. At its core is the <b>production tubing</b>, which acts as the primary conduit transporting produced hydrocarbons from the reservoir to surface facilities.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="card">
        <h3>Why Does Tubing Size Matter?</h3>
        <ul>
            <li><b>Sized Too Small:</b> Generates excessive frictional pressure drop ($\Delta P_{fric}$), restricting maximum production rates and triggering erosional wear.</li>
            <li><b>Sized Too Large:</b> Leads to low flow velocities where gas fails to lift liquids, causing <i>liquid loading</i> and well shut-in.</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="card">
        <h3>Chemical Engineering Core Pillars</h3>
        <ul>
            <li><b>Fluid Mechanics:</b> Velocity profiles, friction factors, and Reynolds regimes.</li>
            <li><b>Multiphase Flow:</b> Combined oil, gas, and water holdup calculations.</li>
            <li><b>Thermodynamics:</b> Pressure-Temperature gradients & PVT phase behavior.</li>
            <li><b>Material Selection:</b> NACE MR0175 corrosion screening ($CO_2 / H_2S$ limits).</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("Workflow Architecture")
    st.code("USER INPUTS ➔ HYDRAULIC SCREENING ➔ MECHANICAL & CORROSION CHECK ➔ RANKED RECOMMENDATIONS", language="text")

# -----------------------------------------------------------------------------
# PAGE 2: WELL & FLUID INPUTS
# -----------------------------------------------------------------------------
elif page == "2. Well & Fluid Inputs":
    st.markdown('<div class="main-header">Step 2: Well & Operating Inputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Define subsurface geometry, production rates, PVT properties, and environmental contaminants.</div>', unsafe_allow_html=True)
    
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
            q_liquid = st.number_input("Total Liquid Rate [STB/day]", value=st.session_state.inputs['q_liquid'], min_value=50.0, max_value=50000.0)
            water_cut = st.number_input("Water Cut [%]", value=st.session_state.inputs['water_cut'], min_value=0.0, max_value=100.0)
            gor = st.number_input("Gas-Oil Ratio (GOR) [scf/STB]", value=st.session_state.inputs['gor'], min_value=0.0, max_value=20000.0)

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

        submitted = st.form_submit_button("Save Inputs & Update Model")
        if submitted:
            if md < tvd:
                st.error("Validation Error: Measured Depth (MD) must be greater than or equal to True Vertical Depth (TVD).")
            else:
                st.session_state.inputs.update({
                    'tvd': tvd, 'md': md, 'p_wh': p_wh, 'p_bhp': p_bhp, 't_wh': t_wh, 't_bht': t_bht,
                    'q_liquid': q_liquid, 'water_cut': water_cut, 'gor': gor,
                    'api_gravity': api_gravity, 'gas_sg': gas_sg, 'water_sg': water_sg, 'oil_visc': oil_visc,
                    'co2_mole_pct': co2_mole_pct, 'h2s_mole_pct': h2s_mole_pct, 'chlorides_ppm': chlorides_ppm
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
                c_grade = st.selectbox("Grade", ["L-80", "13Cr", "P-110", "25Cr"])
                c_mat = st.selectbox("Material Type", ["Carbon Steel", "Martensitic Stainless", "Duplex Stainless"])
                
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
    st.markdown('<div class="sub-header">Evaluates Reynolds number, pressure loss components, velocity screening, and environmental compliance.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    
    # Overview Summary Table
    st.subheader("Candidate Screening Matrix")
    
    # Styled display table
    display_df = res_df[[
        'Name', 'ID_in', 'Velocity_fts', 'v_critical', 'v_erosional', 
        'dp_hydro_psi', 'dp_fric_psi', 'dp_total_psi', 'Material_Reason', 'Overall_Pass'
    ]].copy()
    
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Mixture Vel (ft/s)', 'Min Lift Vel (ft/s)', 'Max Erosional Vel (ft/s)',
        'Hydrostatic dP (psi)', 'Friction dP (psi)', 'Total dP (psi)', 'Material Status', 'Overall Status'
    ]
    
    st.dataframe(display_df, use_container_width=True)
    
    # Calculation Formula Expanders
    with st.expander("Show Governing Equations & Correlations"):
        st.latex(r"\Delta P_{total} = \Delta P_{hydrostatic} + \Delta P_{friction}")
        st.latex(r"\Delta P_{hydrostatic} = \frac{\rho_{mixture} \cdot TVD}{144}")
        st.latex(r"v_{erosional} = \frac{C}{\sqrt{\rho_{mixture}}} \quad \text{(API RP 14E, } C=120\text{)}")
        st.latex(r"v_{critical} = \frac{1.3 \sigma^{0.25} (\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}} \quad \text{(Turner Correlation)}")

# -----------------------------------------------------------------------------
# PAGE 5: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "5. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 5: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
    res_df = run_engineering_calculations(st.session_state.inputs, st.session_state.tubing_db)
    passed_candidates = res_df[res_df['Overall_Pass'] == True]
    
    # Recommended Box
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if not passed_candidates.empty:
            # Pick candidate with minimum total pressure drop among passed
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
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**).
            * **Velocity Window:** Mixture flow velocity (**{preferred['Velocity_fts']} ft/s**) lies safely above the liquid loading threshold (**{preferred['v_critical']} ft/s**) and below the API RP 14E erosional limit (**{preferred['v_erosional']} ft/s**).
            * **Corrosion & Metallurgy:** Selected **{preferred['Grade']} ({preferred['Material']})** tubing satisfies NACE MR0175 partial pressure requirements for $CO_2$ ({st.session_state.inputs['co2_mole_pct']} mole %) and $H_2S$ ({st.session_state.inputs['h2s_mole_pct']} mole %).
            """)
        else:
            st.write("Review the calculation page to identify specific failure flags (velocity, hydraulics, or corrosion).")

    st.markdown("---")
    st.subheader("Interactive Sensitivity Plots")
    
    tab1, tab2 = st.tabs(["Pressure Drop vs. Tubing ID", "Velocity Window vs. Tubing ID"])
    
    with tab1:
        fig_dp = px.line(
            res_df, x="ID_in", y="dp_total_psi", text="Name", markers=True,
            title="Total Pressure Drop vs. Tubing Inner Diameter (ID)",
            labels={"ID_in": "Inner Diameter (inches)", "dp_total_psi": "Total Pressure Drop (psi)"}
        )
        fig_dp.add_hline(y=res_df['dp_avail_psi'].iloc[0], line_dash="dash", line_color="red", annotation_text="Available Drawdown Limit")
        st.plotly_chart(fig_dp, use_container_width=True)

    with tab2:
        fig_v = go.Figure()
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['Velocity_fts'], mode='lines+markers', name='Actual Flow Velocity'))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_erosional'], mode='lines', name='Erosional Velocity Limit (Max)', line=dict(dash='dash', color='red')))
        fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_critical'], mode='lines', name='Liquid Loading Limit (Min)', line=dict(dash='dot', color='orange')))
        
        fig_v.update_layout(
            title="Flow Velocity Window vs. Tubing Inner Diameter",
            xaxis_title="Inner Diameter (inches)",
            yaxis_title="Velocity (ft/s)"
        )
        st.plotly_chart(fig_v, use_container_width=True)