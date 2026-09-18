import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import io
import json
import urllib.request
import base64
import itertools
from pathlib import Path

from api_5c3 import (
    APIDesignError,
    calculate_collapse,
    calculate_ductile_rupture,
    calculate_vme,
)
from api_5ct import (
    APIProductSpecError,
    calculate_as_quenched_hardness,
    calculate_hydrostatic_test_pressure,
    calculate_min_cvn,
    calculate_min_elongation,
)

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tubing Selection Tool",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# STATIC ASSET LOADER
# -----------------------------------------------------------------------------
_ASSET_DIR = Path(__file__).resolve().parent / "assets"


@st.cache_data(show_spinner=False)
def load_asset(name):
    """Return the text of `assets/<name>`, read once per session.

    The stylesheet and the three interactive schematics are static text with no
    Python interpolation. Holding them as module-level string literals put ~60 KB
    of inert markup in the source and re-materialized it on every rerun; reading
    them from disk through cache_data does the I/O once and hands back the same
    cached string thereafter.
    """
    return (_ASSET_DIR / name).read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def encode_image_b64(path):
    """Return an inline data URI for `path`, or None when it is unavailable.

    Cached because the hero image is hundreds of kilobytes; re-encoding it on every
    rerun would add that much base64 work to each page render.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as handle:
            encoded = base64.b64encode(handle.read()).decode('utf-8')
    except OSError:
        return None
    lowered = path.lower()
    if lowered.endswith('.png'):
        mime = 'image/png'
    elif lowered.endswith('.svg'):
        mime = 'image/svg+xml'
    else:
        mime = 'image/jpeg'
    return f'data:{mime};base64,{encoded}'


def first_existing_image(names):
    """Return the data URI of the first readable path in `names`."""
    for name in names:
        data_uri = encode_image_b64(name)
        if data_uri:
            return data_uri
    return None


def figure_block(path, number, caption):
    """Render a figure inside a framed, captioned plate. Skips missing files."""
    data_uri = encode_image_b64(path)
    if not data_uri:
        return ""
    return f"""
    <figure class="p1-figure">
        <div class="p1-figure-frame"><img src="{data_uri}" alt="{caption}" loading="lazy" /></div>
        <figcaption class="p1-figure-caption"><span class="p1-figure-number">Figure {number}</span>{caption}</figcaption>
    </figure>
    """


# Custom CSS styling for presentation-grade UI
st.markdown(f"<style>{load_asset('app.css')}</style>", unsafe_allow_html=True)

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
        't_wh': 150.0,
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
        'sf_triaxial': 1.25,
        'apb_limit_psi': 1500.0
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

# -----------------------------------------------------------------------------
# HELPER FORMULA FUNCTIONS FOR SLURRY PHYSICS
# -----------------------------------------------------------------------------
def calculate_slurry_physics(q_liq_stbd, sand_pptb, sand_sg, sand_d_um, rho_m, mu_m_cp, d_i_in, is_cra=False):
    """Salama erosional ceiling, Rubey settling and Turner lift for a sand slurry.

    `sand_pptb` may be a scalar or a NumPy array; every branch is expressed with
    np.where/np.maximum so a whole sand-concentration sweep resolves in one call
    instead of one Python-level call per point. Scalar inputs return Python floats
    so callers can still `round()` the results.
    """
    rho_s = sand_sg * 62.4
    w_s_lb_day = (sand_pptb / 1000.0) * q_liq_stbd
    w_s_lb_s = w_s_lb_day / 86400.0
    v_sand_ft3s = w_s_lb_s / rho_s if rho_s > 0 else np.zeros_like(np.asarray(w_s_lb_day, dtype=float))
    v_liq_ft3s = (q_liq_stbd * 5.615) / 86400.0

    v_total_ft3s = v_liq_ft3s + v_sand_ft3s
    c_v = np.where(v_total_ft3s > 0, v_sand_ft3s / np.where(v_total_ft3s > 0, v_total_ft3s, 1.0), 0.0)
    rho_slurry = (1.0 - c_v) * rho_m + c_v * rho_s

    # Salama's erosional limit needs a positive solids rate; below the 0.1 lb/day
    # floor the sand-free API 14E form governs instead.
    c_salama = 450.0 if is_cra else 200.0
    has_solids = w_s_lb_day > 0.1
    v_erosional = np.where(
        has_solids,
        (c_salama / np.sqrt(rho_slurry)) * np.sqrt(d_i_in / np.where(has_solids, w_s_lb_day, 1.0)),
        120.0 / np.sqrt(rho_m),
    )

    mu_m_lbfts = mu_m_cp * 0.000672
    d_p_ft = (sand_d_um * 1e-6) * 3.28084
    g_const = 32.174
    delta_rho = np.maximum(rho_s - rho_slurry, 0.1)
    nu_kinematic = np.where(rho_slurry > 0, mu_m_lbfts / np.where(rho_slurry > 0, rho_slurry, 1.0), 1e-5)

    term1 = (2.0 / 3.0) * g_const * d_p_ft * (delta_rho / rho_slurry)
    if d_p_ft > 0:
        term2 = (36.0 * (nu_kinematic ** 2)) / (d_p_ft ** 2)
        v_t_rubey = np.maximum(np.sqrt(term1 + term2) - (6.0 * nu_kinematic / d_p_ft), 0.0)
    else:
        v_t_rubey = np.zeros_like(np.asarray(term1, dtype=float))

    sigma_dynes = 20.0
    rho_g = 1.5
    v_turner = (1.3 * (sigma_dynes ** 0.25) * ((62.4 - rho_g) ** 0.25)) / (rho_g ** 0.5)
    v_carrying = np.maximum(v_turner, 1.35 * v_t_rubey)

    scalar = np.isscalar(sand_pptb) or np.ndim(sand_pptb) == 0
    cast = float if scalar else np.asarray
    return {
        "c_v": cast(c_v),
        "rho_slurry": cast(rho_slurry),
        "v_erosional": cast(v_erosional),
        "v_t_rubey": cast(v_t_rubey),
        "v_turner": v_turner,
        "v_carrying": cast(v_carrying),
        "w_s_lb_day": cast(w_s_lb_day)
    }

# Indicative maximum continuous service temperature per steel grade [°C]. These are
# screening values for grade-vs-BHT compatibility only; a project-specific design
# must use the mill's published derating curves.
MAX_SERVICE_TEMP_C = {
    "H40": 150.0, "J55": 150.0, "K55": 150.0, "M65": 150.0, "C75": 150.0,
    "N80": 150.0, "C95": 150.0, "T95": 150.0, "L80": 150.0, "L801": 150.0,
    "P105": 150.0, "P110": 150.0, "Q125": 150.0,
    "L8013CR": 150.0, "S13CR110": 175.0, "17CR110": 180.0,
    "22CR110": 232.0, "25CR125": 250.0
}
DEFAULT_MAX_SERVICE_TEMP_C = 150.0

# Engine screening thresholds shared with the Page 5 methodology documentation.
Z_FACTOR_MIN, Z_FACTOR_MAX = 0.65, 1.25
CV_SOLIDS_MAX = 0.15
FRICTION_FACTOR_MAX = 0.15

# API TR 5C3 / ISO 10400 limit-state design factors.
RUPTURE_SF_TARGET = 1.25    # Clause 7 ductile rupture / axial necking
COLLAPSE_SF_TARGET = 1.10   # Clause 8 external pressure resistance

# -----------------------------------------------------------------------------
# PAGE 3 METHODOLOGY: GLOSSARY & CARD BUILDERS
# -----------------------------------------------------------------------------
# Plain-English explanations for the jargon on Page 5. Rendered as click-to-open
# pop-ups so a reader who does not know a term can get it without leaving the page.
# Expanded GLOSSARY dictionary with the requested Page 2 terms
GLOSSARY = {
    "z-factor": ("Z-factor (gas compressibility)",
                 "How far a real gas strays from ideal-gas behaviour. Z = 1 is ideal; hot deep gas "
                 "typically runs 0.8-1.2. It scales how much a given surface gas rate shrinks when "
                 "compressed downhole, so it drives gas density and true flow velocity."),
    "pvt": ("PVT (pressure-volume-temperature)",
            "Lab-derived relationships describing how a reservoir fluid changes volume, density and "
            "dissolved-gas content as pressure and temperature change between reservoir and surface."),
    "rs": ("Solution gas-oil ratio (Rs)",
           "How much gas is dissolved in the oil at downhole conditions. As pressure drops on the way "
           "up, this gas comes out of solution, lightening the fluid column and adding gas volume."),
    "bo": ("Downhole oil volumetric swelling (Bo)",
           "Barrels of downhole live oil that shrink into one stock-tank barrel at surface. A Bo of 1.3 "
           "means the oil occupies 30% more space downhole because of dissolved gas."),
    "rho-o-live": ("Live-oil density (rho_o,live)",
                   "The downhole density of oil containing dissolved solution gas. As pressure decreases toward surface "
                   "and gas breaks out of solution, live-oil density increases."),
    "rho-g": ("In-situ gas density (rho_g)",
              "The actual mass per unit volume of real gas under downhole temperature and pressure conditions, "
              "governed by the real-gas equation of state."),
    "bg": ("Gas formation volume factor (Bg)",
           "The ratio of the volume of gas downhole at pressure and temperature to the volume of the same gas at standard surface conditions."),
    "rho-l-gas": ("Condensate/water holdup density (rho_l)",
                  "The weighted density of liquid phases (condensate and formation water) present in the gas stream, setting the overall liquid holdup column weight."),
    "holdup": ("Liquid holdup",
               "The fraction of the pipe cross-section occupied by liquid rather than gas. It sets the "
               "weight of the fluid column, and therefore how much hydrostatic pressure the well must lift against."),
    "pseudo-critical": ("Pseudo-critical properties",
                        "A gas mixture has no single critical point, so correlations use averaged "
                        "'pseudo' critical pressure and temperature. Dividing actual conditions by these "
                        "gives the reduced values that Z-factor correlations need."),
    "cv": ("Solids volumetric concentration (Cv)",
           "The share of the flowing stream made up of solid sand grains, by volume. Even a few percent "
           "raises mixture density and sharply accelerates erosion of the pipe wall."),
    "slurry": ("Slurry",
               "A flowing mixture of liquid, gas and suspended solid particles. It is heavier and more "
               "erosive than clean fluid, so it is modelled separately from single-phase flow."),
    "reynolds": ("Reynolds number (Re)",
                 "A dimensionless ratio of inertial to viscous forces that tells you whether flow is "
                 "smooth (laminar, below ~2,000) or chaotic (turbulent, above ~4,000). Production tubing "
                 "flow is almost always turbulent."),
    "friction-factor": ("Friction factor (f)",
                        "A dimensionless number capturing how much pressure the fluid loses rubbing "
                        "against the pipe wall. It depends on the Reynolds number and on how rough the wall is."),
    "roughness": ("Relative roughness",
                  "Pipe wall bumpiness divided by pipe diameter. The same absolute roughness matters much "
                  "more in a narrow pipe than a wide one, which is why the ratio is used."),
    "hydrostatic": ("Hydrostatic pressure",
                    "The pressure from the sheer weight of the fluid column standing in the well. It depends "
                    "on fluid density and vertical depth only, not on flow rate."),
    "drawdown": ("Available drawdown",
                 "The pressure difference between the reservoir at the bottom and the wellhead at surface. "
                 "This is the total budget available to lift fluid up the well; if losses exceed it, the well dies."),
    "erosional": ("Erosional velocity",
                  "The speed above which flowing fluid, especially when carrying sand, strips metal from the "
                  "pipe wall fast enough to shorten well life. It sets the upper bound on flow velocity."),
    "carrying": ("Carrying (critical) velocity",
                 "The minimum speed needed to keep sand and liquid droplets moving upward. Flow slower than "
                 "this lets solids settle out and liquid accumulate, eventually killing the well."),
    "liquid-loading": ("Liquid loading",
                       "When gas flows too slowly to carry liquid to surface, liquid falls back and collects "
                       "at the bottom of the well. The accumulating column adds back-pressure and can stop flow entirely."),
    "terminal-velocity": ("Terminal settling velocity",
                          "The steady falling speed a sand grain reaches in still fluid, where drag balances "
                          "its weight. Upward flow must beat this to carry the grain out of the well."),
    "interfacial-tension": ("Interfacial tension",
                            "The surface force holding a liquid droplet together against the gas around it. "
                            "It sets the largest droplet the gas stream can carry before it breaks up or falls back."),
    "frac-proppant-flowback": ("Frac proppant flowback",
                               "Ceramic or coated sand grains injected during hydraulic fracturing. They flow back into the wellbore with produced fluids."),
    "corrosion-scale": ("Corrosion scale",
                        "Solid mineral scale deposits detached from the casing/tubing inner walls that enter the flow stream."),
    "sand-fallout": ("Sand fallout",
                     "The physical settling of suspended sand grains down the wellbore column when fluid velocity drops below terminal settling velocity, forming bottomhole sand bridges."),
    "wellbore-choking": ("Wellbore choking",
                         "Severe restriction or total blockage of the production conduit caused by accumulated sand dunes, liquid loading columns, or heavy scale bridges."),
    "axial-load": ("Net axial load",
                   "The total up-or-down force acting along the tubing's length, summing pipe weight, thermal "
                   "effects, pressure end-loads and drag. Too much tension parts the string; too much compression buckles it."),
    "thermal-force": ("Thermal expansion force",
                      "Hot produced fluid heats the steel, which wants to lengthen. When a packer anchors the "
                      "string and prevents that movement, the restrained expansion converts into large compressive force instead."),
    "piston": ("Piston force",
               "Pressure acting on the exposed change in cross-sectional area at the packer, pushing the tubing "
               "like fluid pushing a piston in a cylinder."),
    "ballooning": ("Ballooning",
                   "Internal pressure swells the pipe radially outward. Because the steel volume is fixed, that "
                   "radial swelling makes the string shorten axially, adding force when it is anchored."),
    "apb": ("APB (annular pressure build-up)",
            "In a sealed annulus, completion fluid heated by production has nowhere to expand, so pressure climbs. "
            "Severe APB can collapse the tubing or burst the casing, and is a known cause of deepwater well failures."),
    "annulus": ("Annulus",
                "The ring-shaped space between the outside of the tubing and the inside of the casing."),
    "packer": ("Packer",
               "A downhole seal that grips the casing and blocks the annulus, forcing produced fluid to travel "
               "up the tubing and isolating the annulus above it."),
    "lame": ("Lamé thick-wall equations",
             "Classical elasticity solution for the stresses in a thick-walled cylinder under internal and external "
             "pressure. Tubing is too thick-walled for simple thin-wall formulas to be accurate."),
    "hoop": ("Hoop stress",
             "Circumferential stress that tries to split the pipe lengthwise, like the tension in a barrel band. "
             "Internal pressure is what mainly drives it."),
    "radial-stress": ("Radial stress",
                      "Stress acting through the pipe wall thickness, inward or outward. At the inner wall it equals "
                      "the internal pressure pressing on it."),
    "von-mises": ("von Mises equivalent stress",
                  "A way to collapse three-dimensional stress into one number comparable against the steel's yield "
                  "strength. It predicts yielding from distortion, which is how ductile steel actually fails."),
    "dogleg": ("Dogleg severity (DLS)",
               "How sharply the wellbore changes direction, in degrees per 100 ft. Forcing straight pipe through a "
               "sharp bend adds bending stress on top of the axial load."),
    "smys": ("SMYS / yield strength",
             "Specified Minimum Yield Strength: the stress at which the steel grade begins to deform permanently. "
             "L80 means 80,000 psi, P110 means 110,000 psi."),
    "tubing-collapse-rating": ("Tubing Collapse Rating",
                                "The external pressure limit at which the tubing pipe body undergoes structural buckling or collapse."),
    "collapse-safety-factor": ("Collapse Safety Factor",
                                "The ratio of the pipe's internal/external collapse rating over the net external differential pressure applied."),
    "distortion-strain-energy": ("Distortion Strain Energy",
                                 "The portion of strain energy associated with shape deformation (shear) rather than volume change, governing von Mises yield theory."),
    "ultimate-plastic-burst": ("Ultimate plastic burst rupture capacity",
                               "The maximum internal pressure capacity a pipe body can withstand prior to plastic rupture, evaluated per API TR 5C3 Clause 7."),
    "safety-factor": ("Safety factor (SF)",
                      "Capacity divided by applied load. An SF of 1.25 means 25% margin remains before the limit is "
                      "reached; anything at or below 1.0 means failure is predicted."),
    "cithp": ("CITHP",
              "Closed-In Tubing Head Pressure: the surface pressure once the well is shut in and flow stops. With a gas "
              "column weighing little, surface pressure approaches reservoir pressure, which is the worst case for burst."),
    "burst": ("Burst rating",
              "The internal pressure at which the pipe body ruptures outward. Checked against shut-in surface pressure, "
              "the harshest internal-pressure case the tubing sees."),
    "nace": ("NACE MR0175",
             "The industry standard governing materials for sour (H2S-bearing) service. It caps steel hardness and "
             "restricts grades, because hard high-strength steels crack in the presence of H2S."),
    "sour": ("Sour service",
             "Wells producing hydrogen sulphide (H2S). H2S drives sulphide stress cracking, in which susceptible steel "
             "fails suddenly and brittlely at stresses well below its rating."),
    "partial-pressure": ("Partial pressure",
                         "The share of total pressure contributed by one gas component: total pressure times its mole "
                         "fraction. Corrosion severity tracks partial pressure, not raw concentration."),
    "cra": ("CRA (corrosion-resistant alloy)",
            "High-chromium and nickel alloys such as 13Cr or 25Cr, used when carbon steel would corrode too fast. They "
            "cost considerably more but survive sour and CO2-rich environments."),
    "premium-connection": ("Premium connection",
                           "A thread with engineered metal-to-metal sealing surfaces, as opposed to a standard API "
                           "thread sealing on thread compound. Required for gas-tight integrity at high pressure."),
    "drift": ("Drift diameter",
              "The largest diameter guaranteed to pass all the way through the string. It, rather than nominal ID, "
              "governs which intervention tools will physically fit."),
    "collapse": ("Collapse",
                 "Inward buckling of the pipe wall when external pressure exceeds internal by enough to make the "
                 "cross-section unstable. Unlike burst, it is a stability failure as much as a strength one, so it "
                 "depends strongly on the diameter-to-thickness ratio D/t and is made worse by axial tension."),
    "elongation": ("Elongation",
                   "How far a tensile specimen stretches before it breaks, as a percentage of a fixed 50.8 mm (2 in) "
                   "gauge length. It is the practical measure of ductility: a pipe that meets its strength numbers but "
                   "not its elongation will fracture rather than deform when overloaded, giving no warning."),
    "charpy": ("Charpy V-notch (CVN)",
               "A standardized impact test that measures how much energy steel can absorb when struck by a "
               "heavy swinging pendulum before it breaks. "),
    "martensite": ("Martensite",
                   "The hard, supersaturated phase formed when steel is quenched fast enough to trap carbon in the "
                   "lattice. The as-quenched hardness is measured as proof that the required martensite fraction was "
                   "actually achieved through the full wall before tempering brings the strength back down."),
    "hydro-test": ("Hydrostatic proof test",
                   "The pressure every joint is held at in the mill before shipment, set as a fixed fraction of "
                   "yield. It is a proof of integrity for that individual joint, not a design rating: the pipe is "
                   "never intended to operate above the pressure at which it was demonstrated sound."),
    "torque-shoulder": (
        "Torque Shoulder",
        "A positive mechanical stop engineered into premium pipe connections. "
        "It controls makeup torque, absorbs extreme axial compressive loads, "
        "and locks the radial metal-to-metal seal in place under high pressure."),
    "martensite-fraction": (
        "Martensite Fraction",
        "The volumetric percentage of hard martensitic microstructural phase formed "
        "during initial quenching. Higher martensite fractions (e.g., ≥90% for sour service) "
        "ensure uniform strength and toughness through the full pipe wall before tempering."),
}

_TERM_SEQ = itertools.count()


def term(key, text=None):
    """Render `text` as a clickable glossary term that reveals a pop-up definition.

    Emits only inline elements. A hidden checkbox plus its <label> gives
    click-to-toggle in pure CSS, which matters because st.markdown strips custom
    JavaScript. Do not switch this back to <details>: that element is block-level,
    so the markdown renderer breaks the paragraph at every term.
    """
    title, body = GLOSSARY[key]
    label = text if text is not None else title
    cb_id = f"gt{next(_TERM_SEQ)}"
    return (f'<span class="m2-term">'
            f'<input class="m2-term-cb" type="checkbox" id="{cb_id}" />'
            f'<label class="m2-term-label" for="{cb_id}">{label}</label>'
            f'<span class="m2-term-pop"><b>{title}</b>{body}</span></span>')


def param_table(rows):
    """Build the symbol / meaning / units definition table for a formula card."""
    body = "".join(
        f'<tr><td class="m2-sym">{sym}</td><td>{meaning}</td><td class="m2-unit">{units}</td></tr>'
        for sym, meaning, units in rows
    )
    return (
        '<table class="m2-param-table">'
        '<thead><tr><th>Symbol</th><th>Meaning</th><th>Units / typical value</th></tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def formula_card(num, title, colour, formulas, purpose, params, gate):
    """Render one full-width methodology card in a fixed block order.

    Streamlit cannot nest st.latex inside an HTML string, so the card is emitted
    in three passes: header + purpose, then the LaTeX formulas, then the
    parameter table and screening gate. `formulas` is a list of (latex, caption)
    pairs; a caption of None omits the caption line.
    """
    st.markdown(
        f'<div class="m2-card">'
        f'<div class="m2-card-head"><span class="m2-card-num">{num}</span>'
        f'<h4 class="m2-card-title" style="color: {colour};">{title}</h4></div>'
        f'<div class="m2-label">What it does</div>'
        f'<div class="m2-purpose">{purpose}</div>'
        f'<div class="m2-label">Formula</div>',
        unsafe_allow_html=True,
    )
    for latex, caption in formulas:
        if caption:
            st.markdown(f'<p class="m2-fx-caption">{caption}</p>', unsafe_allow_html=True)
        st.latex(latex)
    st.markdown(
        f'<div class="m2-label">Parameters</div>{param_table(params)}'
        f'<div class="m2-label">Screening gate — what gets rejected</div>'
        f'<div class="m2-gate">{gate}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def haaland_friction_factor(reynolds, relative_roughness):
    """Darcy friction factor from the Haaland explicit approximation.

    Haaland is a closed-form approximation to Colebrook-White, so it needs no
    iteration; an earlier fixed-point loop around this expression recomputed an
    identical value up to 20 times per call. Accepts scalars or arrays.
    """
    return 1.0 / (-1.8 * np.log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds)) ** 2


def normalize_grade(grade):
    """Collapse a grade label to a lookup key: uppercase, no spaces or hyphens."""
    return str(grade).upper().replace(" ", "").replace("-", "").replace("_", "")


def max_service_temp_c(grade):
    """Return the indicative max service temperature [°C] for a steel grade."""
    return MAX_SERVICE_TEMP_C.get(normalize_grade(grade), DEFAULT_MAX_SERVICE_TEMP_C)


def compute_dynamic_z_factor(p_psia, t_deg_r, gas_sg):
    """Return gas compressibility using the Dranchuk-Abou-Kassem correlation.

    Parameters must be absolute pressure (psia), absolute temperature (°R), and
    gas specific gravity relative to air. The iterative reduced-density solution
    avoids the previous algebraic cancellation that made Z independent of pressure.
    """
    values = (p_psia, t_deg_r, gas_sg)
    if not all(np.isfinite(value) for value in values) or p_psia <= 0 or t_deg_r <= 0 or gas_sg <= 0:
        raise ValueError("Gas Z-factor requires finite, positive pressure (psia), temperature (°R), and gas specific gravity.")

    p_pc = 756.8 - 131.07 * gas_sg - 3.6 * gas_sg ** 2
    t_pc = 169.2 + 349.5 * gas_sg - 74.0 * gas_sg ** 2
    p_pr = p_psia / p_pc
    t_pr = t_deg_r / t_pc
    if p_pr <= 0 or t_pr <= 0:
        raise ValueError("Reduced pressure and temperature must be positive for the Z-factor calculation.")

    a1, a2, a3, a4, a5 = 0.3265, -1.0700, -0.5339, 0.01569, -0.05165
    a6, a7, a8, a9, a10, a11 = 0.5475, -0.7361, 0.1844, 0.1056, 0.6134, 0.7210
    reduced_density = 0.27 * p_pr / t_pr

    for _ in range(100):
        density_sq = reduced_density ** 2
        z_factor = (
            1.0
            + (a1 + a2 / t_pr + a3 / t_pr ** 3 + a4 / t_pr ** 4 + a5 / t_pr ** 5) * reduced_density
            + (a6 + a7 / t_pr + a8 / t_pr ** 2) * density_sq
            - a9 * (a7 / t_pr + a8 / t_pr ** 2) * reduced_density ** 5
            + a10 * (1.0 + a11 * density_sq) * density_sq * np.exp(-a11 * density_sq) / t_pr ** 3
        )
        if not np.isfinite(z_factor) or z_factor <= 0:
            raise ValueError("Z-factor calculation became non-physical; check the pressure, temperature, and gas gravity.")

        updated_density = 0.27 * p_pr / (z_factor * t_pr)
        if abs(updated_density - reduced_density) < 1e-8:
            return float(z_factor)
        reduced_density = 0.5 * (reduced_density + updated_density)

    raise ValueError("Z-factor calculation did not converge; check the gas-property inputs.")


def static_cithp_psi(p_bhp, tvd, gas_sg, z_factor, t_avg_r):
    """Static shut-in CITHP [psig] from a barometric dry-gas column.

    Uses the standard gas-gradient exponent 0.01875·γ_g·TVD/(Z·T_avg,R), which is
    M/R with R = 1545 ft·lbf/(lb-mol·°R): 28.97/1545 = 0.01875. Pressures are
    converted to absolute for the exponential and returned as gauge, matching the
    convention used everywhere else in the app.

    Shared by the engine and the Page 6 default so the surface burst check and the
    value shown in the input form always come from the same model.
    """
    p_bhp_psia = p_bhp + 14.7
    p_wh_psia = p_bhp_psia * np.exp(-(0.01875 * gas_sg * tvd) / (z_factor * t_avg_r))
    return max(p_wh_psia - 14.7, 0.0)


def validate_engineering_inputs(inputs, candidate_df):
    """Raise ValueError before invalid user/session data can enter the model."""
    numeric_fields = {
        "wellhead pressure": "p_wh", "bottomhole pressure": "p_bhp", "wellhead temperature": "t_wh",
        "bottomhole temperature": "t_bht", "TVD": "tvd", "MD": "md", "casing ID": "casing_id",
        "API gravity": "api_gravity", "gas specific gravity": "gas_sg", "water specific gravity": "water_sg",
        "oil viscosity": "oil_visc", "sand size": "sand_size_microns", "sand specific gravity": "sand_sg",
        "field life": "field_life_yrs", "decline rate": "decline_rate", "water cut": "water_cut",
        "ambient surface temperature": "t_ambient",
    }
    values = {}
    for label, key in numeric_fields.items():
        try:
            values[key] = float(inputs[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{label.capitalize()} must be a finite numeric value.") from None
        if not np.isfinite(values[key]):
            raise ValueError(f"{label.capitalize()} must be finite.")

    if values["p_wh"] < 0 or values["p_bhp"] <= values["p_wh"]:
        raise ValueError("Bottomhole pressure must be greater than or equal to zero and greater than wellhead pressure.")
    if values["t_wh"] <= -459.67 or values["t_bht"] <= -459.67 or values["t_ambient"] <= -459.67:
        raise ValueError("Temperatures must be above absolute zero.")
    if values["tvd"] <= 0 or values["md"] < values["tvd"]:
        raise ValueError("Measured depth must be greater than or equal to positive TVD.")
    if values["casing_id"] <= 0 or values["api_gravity"] <= -131.5 or values["gas_sg"] <= 0:
        raise ValueError("Casing ID, API gravity, and gas specific gravity are outside valid physical bounds.")
    if values["water_sg"] <= 0 or values["oil_visc"] <= 0 or values["sand_size_microns"] <= 0 or values["sand_sg"] <= 0:
        raise ValueError("Fluid and sand properties must be positive.")
    if not 0 <= values["water_cut"] <= 100 or values["field_life_yrs"] <= 0 or not 0 <= values["decline_rate"] < 100:
        raise ValueError("Water cut must be 0–100%, field life positive, and annual decline 0–<100%.")

    is_gas_well = "Gas Well" in str(inputs.get("well_type", ""))
    rate_key = "q_gas_mmscfd" if is_gas_well else "q_liquid"
    try:
        rate = float(inputs[rate_key])
    except (KeyError, TypeError, ValueError):
        raise ValueError("A valid production rate is required.") from None
    if not np.isfinite(rate) or rate < 0:
        raise ValueError("Production rate must be finite and non-negative.")

    required_columns = {"OD_in", "ID_in", "Weight_lbft", "Yield_psi", "Burst_psi"}
    missing_columns = required_columns - set(candidate_df.columns)
    if candidate_df.empty or missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Candidate database is empty or missing required columns: {missing}.")
    dimensions = candidate_df[["OD_in", "ID_in", "Weight_lbft", "Yield_psi", "Burst_psi"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(dimensions.to_numpy()).all() or (dimensions <= 0).any().any() or (dimensions["ID_in"] >= dimensions["OD_in"]).any():
        raise ValueError("Every tubing candidate needs finite positive ratings and an ID strictly smaller than its OD.")


def run_engineering_calculations(inputs, candidate_df):
    validate_engineering_inputs(inputs, candidate_df)
    results = []

    is_gas_well = "Gas Well" in inputs.get('well_type', 'Oil Well')
    p_wh_val = inputs.get('p_wh', 800.0)
    p_bhp_val = inputs.get('p_bhp', 4500.0)
    # UI pressures are gauge pressures; PVT correlations require absolute pressure.
    p_avg_psia = (p_wh_val + p_bhp_val) / 2.0 + 14.7

    t_wh_val = inputs.get('t_wh', 150.0)
    t_bht_val = inputs.get('t_bht', 210.0)
    t_avg_f = (t_wh_val + t_bht_val) / 2.0
    t_avg_r = t_avg_f + 459.67
    t_bht_c = (t_bht_val - 32.0) * (5.0 / 9.0)

    casing_id_val = inputs.get('casing_id', 8.681)

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

        rs_scf_stb = gas_sg_val * (((p_avg_psia / 18.2) + 1.4) * (10 ** (0.0125 * api_val - 0.00091 * t_avg_f))) ** 1.2048
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

    z_factor = compute_dynamic_z_factor(p_avg_psia, t_avg_r, gas_sg_val)
    z_in_range = Z_FACTOR_MIN <= z_factor <= Z_FACTOR_MAX
    bo_valid = bo_rb_stb > 0.0
    rho_g = (2.7 * gas_sg_val * p_avg_psia) / (z_factor * t_avg_r)
    rho_g = max(rho_g, 0.05)

    q_g_ft3s = (q_g_scf_d * 14.7 * t_avg_r * z_factor) / (p_avg_psia * 520.0 * 86400.0)
    q_m_ft3s = max(q_l_ft3s + q_g_ft3s, 1e-6)

    lambda_l = q_l_ft3s / q_m_ft3s if q_m_ft3s > 0 else 1.0
    rho_m = lambda_l * rho_l + (1.0 - lambda_l) * rho_g

    sand_pptb_val = inputs.get('sand_rate_pptb', 0.0)
    sand_d_um = inputs.get('sand_size_microns', 150.0)
    sand_sg_val = inputs.get('sand_sg', 2.65)
    rho_s_lbft3 = sand_sg_val * 62.4

    w_s_lb_day = (sand_pptb_val / 1000.0) * q_liq_stbd
    v_sand_ft3d = w_s_lb_day / rho_s_lbft3 if rho_s_lbft3 > 0 else 0.0
    v_liq_ft3d = q_liq_stbd * 5.615
    c_v_solids = v_sand_ft3d / (v_liq_ft3d + v_sand_ft3d) if (v_liq_ft3d + v_sand_ft3d) > 0 else 0.0
    cv_in_range = c_v_solids <= CV_SOLIDS_MAX
    rho_slurry = (1.0 - c_v_solids) * rho_m + c_v_solids * rho_s_lbft3

    mu_w_cp = 0.5
    mu_l_cp = (1.0 - wc_frac) * inputs.get('oil_visc', 1.5) + wc_frac * mu_w_cp
    mu_m_cp = lambda_l * mu_l_cp + (1.0 - lambda_l) * 0.018
    mu_m_lbfts = mu_m_cp * 0.000672

    d_p_ft = (sand_d_um * 1e-6) * 3.28084
    g_const = 32.174
    delta_rho = max(rho_s_lbft3 - rho_slurry, 0.1)
    nu_kinematic = (mu_m_lbfts / rho_slurry) if rho_slurry > 0 else 1e-5

    term1 = (2.0 / 3.0) * g_const * d_p_ft * (delta_rho / rho_slurry)
    term2 = (36.0 * (nu_kinematic ** 2)) / (d_p_ft ** 2) if d_p_ft > 0 else 0.0
    v_t_rubey = np.sqrt(term1 + term2) - (6.0 * nu_kinematic / d_p_ft) if d_p_ft > 0 else 0.0
    v_t_rubey = max(v_t_rubey, 0.0)

    h2s_ppm_val = inputs.get('h2s_ppm', 150.0)
    co2_pct_val = inputs.get('co2_mole_pct', 2.5)
    p_h2s_psia = p_bhp_val * (h2s_ppm_val / 1e6)
    is_sour_service = p_h2s_psia >= 0.05

    # Calculate Late-Life volumetric rate using stored Late-Life parameters
    p_bhp_late = inputs.get('p_bhp_late', p_bhp_val * 0.5)
    p_wh_late = inputs.get('p_wh_late', p_wh_val * 0.4)
    p_avg_late_psia = (p_wh_late + p_bhp_late) / 2.0 + 14.7
    t_bht_late = inputs.get('bht_late', t_bht_val)
    t_avg_late_r = (t_wh_val + t_bht_late) / 2.0 + 459.67
    z_late = compute_dynamic_z_factor(p_avg_late_psia, t_avg_late_r, gas_sg_val)

    if is_gas_well:
        q_g_scf_d_late = inputs.get('q_gas_late', inputs.get('q_gas_mmscfd', 15.0) * 0.5) * 1e6
        q_cond_late = inputs.get('q_gas_late', 15.0) * inputs.get('cgr_late', inputs.get('cgr_stb_mmscf', 25.0))
        q_wat_late = inputs.get('q_gas_late', 15.0) * inputs.get('wgr_late', inputs.get('wgr_bbl_mmscf', 5.0))
        q_l_ft3s_late = ((q_cond_late + q_wat_late) * 5.615) / 86400.0
        q_g_ft3s_late = (q_g_scf_d_late * 14.7 * t_avg_late_r * z_late) / (p_avg_late_psia * 520.0 * 86400.0)
    else:
        q_liq_late_val = inputs.get('q_liq_late', q_liq_stbd * 0.5)
        wc_late_frac = inputs.get('wc_late', inputs.get('water_cut', 5.0)) / 100.0
        gor_late_val = inputs.get('gor_late', inputs.get('gor', 800.0))
        rs_late = min(gas_sg_val * (((p_avg_late_psia / 18.2) + 1.4) * (10 ** (0.0125 * api_val - 0.00091 * (t_avg_late_r - 459.67)))) ** 1.2048, gor_late_val)
        q_l_ft3s_late = (q_liq_late_val * 5.615) / 86400.0
        free_gas_late = max(gor_late_val - rs_late, 0.0)
        q_g_scf_d_late = q_liq_late_val * (1.0 - wc_late_frac) * free_gas_late
        q_g_ft3s_late = (q_g_scf_d_late * 14.7 * t_avg_late_r * z_late) / (p_avg_late_psia * 520.0 * 86400.0)

    q_m_late = max(q_l_ft3s_late + q_g_ft3s_late, 1e-6)

    # Late-life in-situ densities: the minimum-carrying-velocity check has to be
    # evaluated against depleted conditions, not early-life gas density.
    rho_g_late = max((2.7 * gas_sg_val * p_avg_late_psia) / (z_late * t_avg_late_r), 0.05)
    if is_gas_well:
        q_liq_late_total = q_cond_late + q_wat_late
        wc_late_frac_eff = q_wat_late / q_liq_late_total if q_liq_late_total > 0 else 0.0
        rho_o_late = 62.4 * gamma_o
    else:
        wc_late_frac_eff = wc_late_frac
        bo_late = 0.9759 + 0.000120 * ((rs_late * ((gas_sg_val / gamma_o) ** 0.5) + 1.25 * (t_avg_late_r - 459.67)) ** 1.2)
        rho_o_late = (62.4 * gamma_o + 0.0136 * rs_late * gas_sg_val) / bo_late
    rho_l_late = (1.0 - wc_late_frac_eff) * rho_o_late + wc_late_frac_eff * rho_w

    # Static shut-in CITHP via barometric gas column; a user-entered value overrides it.
    tvd_val = inputs.get('tvd', 10000.0)
    cithp_calc = static_cithp_psi(p_bhp_val, tvd_val, gas_sg_val, z_factor, t_avg_r)
    cithp_val = float(inputs.get('cithp') or cithp_calc)

    fluid_props = ANNULAR_FLUID_PROPS.get(inputs.get('annular_fluid', ''), ANNULAR_FLUID_PROPS["Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)"])
    alpha_v = fluid_props['alpha_v']
    kappa_t = fluid_props['kappa_t']

    t_ambient_val = inputs.get('t_ambient', 75.0)
    # Annular temperature rise is the *change* from the sealed-in static condition to
    # flowing conditions, not the difference from surface ambient. Bottomhole stays at
    # reservoir temperature, so the mean static profile is (T_ambient + T_bht)/2 and the
    # mean flowing profile is (T_wh + T_bht)/2 — the rise reduces to half the wellhead
    # heat-up. alpha_v is per °C, so convert from °F.
    t_static_avg_f = (t_ambient_val + t_bht_val) / 2.0
    delta_t_annular_f = max(t_avg_f - t_static_avg_f, 0.0)
    delta_t_annular_c = delta_t_annular_f * (5.0 / 9.0)
    dp_apb_psi = (alpha_v / kappa_t) * delta_t_annular_c
    apb_limit_psi = float(inputs.get('apb_limit_psi', 1500.0))
    apb_pass = dp_apb_psi <= apb_limit_psi
    p_annular_total_wh = p_wh_val + dp_apb_psi

    for _, row in candidate_df.iterrows():
        id_ft = row['ID_in'] / 12.0
        od_ft = row['OD_in'] / 12.0
        area_id_ft2 = (np.pi / 4.0) * (id_ft ** 2)
        area_od_ft2 = (np.pi / 4.0) * (od_ft ** 2)
        area_steel_in2 = (np.pi / 4.0) * (row['OD_in']**2 - row['ID_in']**2)

        casing_clearance_pass = row['OD_in'] < casing_id_val
        v_m = q_m_ft3s / area_id_ft2
        v_m_late = q_m_late / area_id_ft2

        reynolds = (rho_slurry * v_m * id_ft) / mu_m_lbfts if mu_m_lbfts > 0 else 10000
        relative_roughness = (0.0006 / row['ID_in'])

        if reynolds > 2300:
            f = haaland_friction_factor(reynolds, relative_roughness)
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

        # Late-life carrying limit uses depleted densities: lower gas density raises
        # the Turner droplet-lift threshold, which is the binding late-life risk.
        v_critical_late = (1.3 * (sigma_dynes ** 0.25) * (max(rho_l_late - rho_g_late, 0.01) ** 0.25)) / (rho_g_late ** 0.5)
        v_carrying_late = max(v_critical_late, 1.35 * v_t_rubey)

        grade_str_upper = str(row['Grade']).upper()
        if w_s_lb_day > 0.1:
            c_salama = 450.0 if ("13CR" in grade_str_upper or "22CR" in grade_str_upper or "25CR" in grade_str_upper or "CRA" in str(row['Material']).upper()) else 200.0
            v_erosional = (c_salama / np.sqrt(rho_slurry)) * np.sqrt(row['ID_in'] / w_s_lb_day)
            v_erosional = min(v_erosional, c_factor / np.sqrt(rho_m))
        else:
            v_erosional = c_factor / np.sqrt(rho_m)

        dp_available = p_bhp_val - p_wh_val

        hydraulics_pass = dp_total <= dp_available
        friction_pass = f <= FRICTION_FACTOR_MAX
        velocity_pass = v_carrying < v_m < v_erosional
        late_life_pass = v_m_late >= v_carrying_late

        rho_buoy_factor = (1.0 - (rho_slurry / 490.0))
        f_gravity_lbs = row['Weight_lbft'] * md_val * rho_buoy_factor
        f_thermal_lbs = 30e6 * area_steel_in2 * 6.9e-6 * delta_t_annular_f
        f_piston_lbs = (p_bhp_val * area_id_ft2 * 144.0) - (p_annular_total_wh * (area_od_ft2 - area_id_ft2) * 144.0)
        f_ballooning_lbs = 2.0 * 0.3 * ((p_bhp_val * area_id_ft2 * 144.0) - (p_annular_total_wh * area_od_ft2 * 144.0))
        f_drag_lbs = (f * rho_slurry * (v_m ** 2) * np.pi * id_ft * md_val) / (2.0 * 32.174)

        f_axial_total_lbs = f_gravity_lbs + f_thermal_lbs + f_piston_lbs + f_ballooning_lbs + f_drag_lbs
        f_axial_total_klbs = f_axial_total_lbs / 1000.0

        p_int = p_bhp_val
        p_ext = p_annular_total_wh
        wall_in = (row['OD_in'] - row['ID_in']) / 2.0

        # --- API TR 5C3 / ISO 10400 limit states -----------------------------
        # Module 1 (Clause 6): triaxial yield across all critical radial and
        # circumferential fibre coordinates, replacing the previous single-point
        # bore evaluation. Torque is zero for a static completion string.
        vme = calculate_vme(
            od=row['OD_in'], wall=wall_in, yield_strength=row['Yield_psi'],
            p_internal=p_int, p_external=p_ext, axial_force=f_axial_total_lbs,
            dls=dls_val, torque=0.0, grade=row['Grade'],
        )
        vme_stress_psi = vme["sigma_vme_max_psi"]
        triaxial_sf = vme["safety_factor"]
        sf_triaxial_target = inputs.get('sf_triaxial', 1.25)
        stress_pass = triaxial_sf >= sf_triaxial_target
        vme_governing = f"{vme['governing_point']['radius']} radius / {vme['governing_point']['fibre']} fibre"

        # Module 2 (Clause 7): ductile rupture capacity under the same axial
        # load, solved for the fixed point P_i = P_br. Checked against the static
        # shut-in surface load (CITHP), which is the governing burst case.
        try:
            rupture = calculate_ductile_rupture(
                od=row['OD_in'], wall=wall_in, yield_strength=row['Yield_psi'],
                p_external=p_wh_val, axial_force=f_axial_total_lbs, grade=row['Grade'],
            )
            p_rupture_psi = rupture["p_rupture_psi"]
            rupture_mode = rupture["active_mode"]
            rupture_sf = (p_rupture_psi / cithp_val) if cithp_val > 0 else float('inf')
            rupture_pass = rupture_sf >= RUPTURE_SF_TARGET
            rupture_reason = (
                "Compatible" if rupture_pass else
                f"Fail: ductile rupture SF {round(rupture_sf, 2)} below {RUPTURE_SF_TARGET} "
                f"({rupture_mode} mode, capacity {round(p_rupture_psi, 0)} psi vs CITHP {round(cithp_val, 0)} psi)"
            )
        except (APIDesignError, ValueError) as error:
            p_rupture_psi, rupture_sf = float('nan'), float('nan')
            rupture_mode, rupture_pass = "not evaluated", False
            rupture_reason = f"Fail: Clause 7 rupture check unavailable — {error}"

        # Module 3 (Clause 8): collapse under APB-augmented external pressure.
        # Bending is excluded from the axial stress by construction.
        try:
            collapse = calculate_collapse(
                od=row['OD_in'], wall=wall_in, yield_strength=row['Yield_psi'],
                axial_force=f_axial_total_lbs, p_internal=p_int, grade=row['Grade'],
            )
            p_collapse_psi = collapse["p_collapse_corrected_psi"]
            collapse_regime = collapse["regime"]
            y_pa_psi = collapse["y_pa_psi"]
            p_ext_design = p_ext + dp_hydro  # annulus fluid column plus APB
            collapse_sf = (p_collapse_psi / p_ext_design) if p_ext_design > 0 else float('inf')
            collapse_pass = collapse_sf >= COLLAPSE_SF_TARGET
            collapse_reason = (
                "Compatible" if collapse_pass else
                f"Fail: collapse SF {round(collapse_sf, 2)} below {COLLAPSE_SF_TARGET} "
                f"({collapse_regime} regime, {round(p_collapse_psi, 0)} psi capacity vs "
                f"{round(p_ext_design, 0)} psi external)"
            )
        except (APIDesignError, ValueError) as error:
            p_collapse_psi, collapse_sf, y_pa_psi = float('nan'), float('nan'), float('nan')
            collapse_regime, collapse_pass = "not evaluated", False
            collapse_reason = f"Fail: Clause 8 collapse check unavailable — {error}"

        # --- API 5CT / ISO 11960 product specification verification ----------
        # Mill acceptance requirements, not well-load capacities. Only the
        # hydrostatic proof test is a hard gate: operating above the pressure at
        # which the joint's integrity was demonstrated is a design deficiency,
        # not a QA note. The other three are reported requirements, so their
        # notes never touch overall_pass.
        api_5ct_flags = []
        try:
            hydro = calculate_hydrostatic_test_pressure(
                od=row['OD_in'], wall=wall_in, yield_strength=row['Yield_psi'], grade=row['Grade'],
            )
            p_test_psi = hydro['p_test_psi']
            hydro_design_factor = hydro['design_factor']
            hydro_sf = (p_test_psi / cithp_val) if cithp_val > 0 else float('inf')
            hydro_pass = p_test_psi >= cithp_val
            hydro_reason = (
                "Compatible" if hydro_pass else
                f"Fail: mill proof-test pressure {round(p_test_psi, 0)} psi (f = {hydro_design_factor}) "
                f"is below the shut-in CITHP {round(cithp_val, 0)} psi the string must hold"
            )
            api_5ct_flags.extend(hydro['flags'])
        except (APIProductSpecError, ValueError) as error:
            p_test_psi, hydro_sf = float('nan'), float('nan')
            hydro_design_factor, hydro_pass = float('nan'), False
            hydro_reason = f"Fail: 5CT hydrostatic proof-test check unavailable — {error}"

        try:
            elong = calculate_min_elongation(wall=wall_in, grade=row['Grade'])
            min_elongation_pct = elong['min_elongation_pct']
            elongation_specimen = elong['specimen_basis']
            elongation_note = (
                f"Requires {min_elongation_pct}% elongation in a 2 in gauge length "
                f"({elongation_specimen.replace('_', ' ')} specimen)"
            )
            if elong['area_capped']:
                api_5ct_flags.append("Elongation specimen area capped at the 490 mm² maximum")
        except (APIProductSpecError, ValueError) as error:
            min_elongation_pct = float('nan')
            elongation_specimen = "not evaluated"
            elongation_note = f"Not evaluated — {error}"

        # Four CVN requirements: pipe body and coupling, each transverse and
        # longitudinal. The coupling runs on specified MAXIMUM yield, so it is
        # always the more demanding of the pair.
        try:
            cvn_values = {}
            cvn_waived = False
            for comp, orient, key in (
                ("pipe_body", "transverse", "body_trans"), ("pipe_body", "longitudinal", "body_long"),
                ("coupling", "transverse", "cplg_trans"), ("coupling", "longitudinal", "cplg_long"),
            ):
                cvn = calculate_min_cvn(
                    wall=wall_in, yield_strength=row['Yield_psi'], grade=row['Grade'],
                    component=comp, orientation=orient,
                )
                cvn_values[key] = cvn['cvn_required_j']
                cvn_waived = cvn_waived or cvn['testing_waived']
            cvn_note = (
                f"Pipe body {round(cvn_values['body_trans'], 1)} J transverse / "
                f"{round(cvn_values['body_long'], 1)} J longitudinal; coupling "
                f"{round(cvn_values['cplg_trans'], 1)} J / {round(cvn_values['cplg_long'], 1)} J"
            )
            if cvn_waived:
                api_5ct_flags.append(
                    "CVN testing waived (wall too thin for a half-size specimen) — QA process check required"
                )
        except (APIProductSpecError, ValueError) as error:
            cvn_values = {k: float('nan') for k in ("body_trans", "body_long", "cplg_trans", "cplg_long")}
            cvn_waived = False
            cvn_note = f"Not evaluated — {error}"

        try:
            hardness = calculate_as_quenched_hardness(grade=row['Grade'])
            hrc_applicable = hardness['applicable']
            hrc_min_as_quenched = hardness['hrc_min'] if hrc_applicable else float('nan')
            hardenability_note = (
                f"{round(hrc_min_as_quenched, 1)} HRC minimum at mid-wall "
                f"({round(hardness['martensite_fraction_min_pct'], 0)}% martensite, "
                f"C = {hardness['carbon_pct']} wt%)"
                if hrc_applicable else hardness['reason']
            )
        except (APIProductSpecError, ValueError) as error:
            hrc_min_as_quenched, hrc_applicable = float('nan'), False
            hardenability_note = f"Not evaluated — {error}"

        # Pipe body tensile rating: SMYS across the steel cross-section.
        tensile_rating_lbs = row['Yield_psi'] * area_steel_in2
        axial_pass = abs(f_axial_total_lbs) <= tensile_rating_lbs

        burst_sf = row['Burst_psi'] / cithp_val if cithp_val > 0 else 99.0
        burst_pass = burst_sf >= 1.10

        grade_str = str(row['Grade']).upper()
        grade_temp_limit_c = max_service_temp_c(row['Grade'])
        temp_pass = t_bht_c <= grade_temp_limit_c
        temp_reason = (
            f"Compatible (BHT {round(t_bht_c, 1)}°C ≤ {round(grade_temp_limit_c, 0)}°C limit)"
            if temp_pass else
            f"Fail: BHT ({round(t_bht_c, 1)}°C) exceeds {row['Grade']} max service temperature ({round(grade_temp_limit_c, 0)}°C)"
        )

        material_pass = True
        mat_reason = "Compatible"

        if is_sour_service:
            if grade_str in ["J-55", "J55", "N-80", "N80", "P-110", "P110", "K-55", "K55", "C95", "M65", "Q125"]:
                material_pass = False
                mat_reason = f"Fail: Sour Service (pH2S = {round(p_h2s_psia,3)} psia >= 0.05). Requires L80-1 (26 HRC Max), C75, T95, or CRA."

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

        # Well-level PVT / rheology gates: identical for every candidate, but reported
        # per row so a failure is visible in the screening matrix.
        pvt_pass = z_in_range and bo_valid
        if pvt_pass:
            pvt_reason = "Compatible"
        elif not z_in_range:
            pvt_reason = f"Fail: Z-factor ({round(z_factor, 3)}) outside valid range {Z_FACTOR_MIN}–{Z_FACTOR_MAX}"
        else:
            pvt_reason = f"Fail: non-physical oil formation volume factor (Bo = {round(bo_rb_stb, 3)} ≤ 0)"

        if cv_in_range:
            solids_reason = "Compatible"
        else:
            solids_reason = f"Fail: sand concentration Cv ({round(c_v_solids, 4)}) exceeds {CV_SOLIDS_MAX} transport-model limit"

        if not friction_pass:
            hydraulics_reason = f"Fail: non-physical friction factor (f = {round(f, 4)} > {FRICTION_FACTOR_MAX})"
        elif not hydraulics_pass:
            hydraulics_reason = f"Fail: dP total ({round(dp_total, 1)} psi) exceeds available drawdown ({round(dp_available, 1)} psi)"
        else:
            hydraulics_reason = "Compatible"

        if not apb_pass:
            apb_reason = f"Fail: APB rise ({round(dp_apb_psi, 1)} psi) exceeds {round(apb_limit_psi, 0)} psi collapse-margin limit"
        else:
            apb_reason = "Compatible"

        if not axial_pass:
            axial_reason = f"Fail: net axial load ({round(f_axial_total_klbs, 1)} klbs) exceeds pipe body rating ({round(tensile_rating_lbs / 1000.0, 1)} klbs)"
        else:
            axial_reason = "Compatible"

        overall_pass = (casing_clearance_pass and hydraulics_pass and friction_pass and velocity_pass and
                        late_life_pass and material_pass and stress_pass and axial_pass and connection_pass and
                        temp_pass and burst_pass and apb_pass and pvt_pass and cv_in_range and
                        rupture_pass and collapse_pass and hydro_pass)

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
            "v_carrying_late": round(v_carrying_late, 2),
            "dp_hydro_psi": round(dp_hydro, 1),
            "dp_fric_psi": round(dp_fric, 1),
            "dp_total_psi": round(dp_total, 1),
            "dp_avail_psi": round(dp_available, 1),
            "dp_apb_psi": round(dp_apb_psi, 1),
            "cithp_psi": round(cithp_val, 1),
            "f_axial_klbs": round(f_axial_total_klbs, 1),
            "f_axial_rating_klbs": round(tensile_rating_lbs / 1000.0, 1),
            "friction_factor": round(f, 4),
            "cv_solids": round(c_v_solids, 5),
            "vme_stress_psi": round(vme_stress_psi, 0),
            "triaxial_sf": round(triaxial_sf, 2),
            "vme_governing_point": vme_governing,
            "vme_n_points": vme["n_points"],
            "p_rupture_psi": round(p_rupture_psi, 0),
            "rupture_sf": round(rupture_sf, 2),
            "rupture_mode": rupture_mode,
            "p_collapse_psi": round(p_collapse_psi, 0),
            "collapse_sf": round(collapse_sf, 2),
            "collapse_regime": collapse_regime,
            "y_pa_psi": round(y_pa_psi, 0),
            "p_test_psi": round(p_test_psi, 0),
            "hydro_test_sf": round(hydro_sf, 2),
            "hydro_design_factor": hydro_design_factor,
            "min_elongation_pct": min_elongation_pct,
            "elongation_specimen": elongation_specimen,
            "cvn_body_trans_j": round(cvn_values['body_trans'], 1),
            "cvn_body_long_j": round(cvn_values['body_long'], 1),
            "cvn_cplg_trans_j": round(cvn_values['cplg_trans'], 1),
            "cvn_cplg_long_j": round(cvn_values['cplg_long'], 1),
            "cvn_testing_waived": cvn_waived,
            "hrc_min_as_quenched": round(hrc_min_as_quenched, 1),
            "hrc_applicable": hrc_applicable,
            "burst_sf": round(burst_sf, 2),
            "Z_Factor": round(z_factor, 3),
            "Bo_rb_stb": round(bo_rb_stb, 3),
            "max_service_temp_c": round(grade_temp_limit_c, 0),
            "Casing_Clearance_Pass": casing_clearance_pass,
            "Hydraulics_Pass": hydraulics_pass,
            "Friction_Pass": friction_pass,
            "Velocity_Pass": velocity_pass,
            "Late_Life_Pass": late_life_pass,
            "Material_Pass": material_pass,
            "Stress_Pass": stress_pass,
            "Axial_Pass": axial_pass,
            "Burst_Pass": burst_pass,
            "Rupture_Pass": rupture_pass,
            "Collapse_Pass": collapse_pass,
            "Hydro_Pass": hydro_pass,
            "Rupture_Reason": rupture_reason,
            "Collapse_Reason": collapse_reason,
            "Hydro_Reason": hydro_reason,
            "Elongation_Note": elongation_note,
            "CVN_Note": cvn_note,
            "Hardenability_Note": hardenability_note,
            "API_5CT_Flags": "; ".join(api_5ct_flags),
            "Temp_Pass": temp_pass,
            "APB_Pass": apb_pass,
            "PVT_Pass": pvt_pass,
            "Solids_Pass": cv_in_range,
            "Connection_Pass": connection_pass,
            "Connection_Reason": conn_status_msg,
            "Material_Reason": mat_reason,
            "Temp_Reason": temp_reason,
            "Hydraulics_Reason": hydraulics_reason,
            "APB_Reason": apb_reason,
            "Axial_Reason": axial_reason,
            "PVT_Reason": pvt_reason,
            "Solids_Reason": solids_reason,
            "Overall_Pass": overall_pass
        })

    return pd.DataFrame(results)


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_engineering_calculations(inputs_key, candidates_json):
    """Memoized engine call keyed on immutable snapshots of its two inputs.

    Pages 9 and 10 both need the same result set, and Streamlit reruns the whole
    script on every widget interaction — without this, each rerun re-solved the
    DAK Z-factor iteration and the full 5C3/5CT limit-state suite for every
    candidate, which is what made the pages stutter. `inputs_key` is a sorted
    tuple of (key, value) pairs and `candidates_json` is the candidate frame
    serialized to JSON, so both hash cheaply and cannot carry stale mutable
    state. max_entries bounds the cache so long sessions cannot grow it without
    limit.
    """
    return run_engineering_calculations(dict(inputs_key), pd.read_json(io.StringIO(candidates_json), orient='split'))


def engineering_results(inputs, candidate_df):
    """Return the screening result frame, reusing the cached value when possible."""
    # Every value must be hashable and part of the key: silently dropping an
    # unhashable one would return a result cached under different inputs.
    unhashable = sorted(k for k, v in inputs.items() if isinstance(v, (list, dict, set)))
    if unhashable:
        raise ValueError(
            "Engine inputs must be scalars so they can key the result cache; "
            f"got container value(s) for: {', '.join(unhashable)}"
        )
    inputs_key = tuple(sorted(inputs.items()))
    return _cached_engineering_calculations(inputs_key, candidate_df.to_json(orient='split'))


@st.cache_data(show_spinner=False, max_entries=8)
def widest_window_candidate(tubing_db_json, q_liq_ref):
    """Return (ID_in, is_cra) for the candidate with the widest velocity window.

    The reference slurry conditions are fixed, so this depends only on the tubing
    database and the liquid rate. It previously re-scanned every row on each Page 3
    rerun — i.e. on every slider drag — for a result that could not change.
    """
    db = pd.read_json(io.StringIO(tubing_db_json), orient='split')
    grade_up = db['Grade'].astype(str).str.upper()
    material_up = db['Material'].astype(str).str.upper()
    cra_flags = grade_up.str.contains("13CR") | material_up.str.contains("CRA")
    best_id, best_cra, max_window = None, False, -np.inf
    for cand_id, cand_cra in zip(db['ID_in'], cra_flags):
        res = calculate_slurry_physics(q_liq_ref, 25.0, 2.65, 150.0, 52.0, 1.5, cand_id, bool(cand_cra))
        window = res['v_erosional'] - res['v_carrying']
        if window > max_window:
            max_window, best_id, best_cra = window, cand_id, bool(cand_cra)
    return best_id, best_cra


def active_candidate_df():
    """Return the candidate set the screening pages should evaluate.