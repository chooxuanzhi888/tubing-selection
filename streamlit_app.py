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

# Engine screening thresholds shared with the Page 6 methodology documentation.
Z_FACTOR_MIN, Z_FACTOR_MAX = 0.65, 1.25
CV_SOLIDS_MAX = 0.15
FRICTION_FACTOR_MAX = 0.15

# API TR 5C3 / ISO 10400 limit-state design factors.
RUPTURE_SF_TARGET = 1.25    # Clause 7 ductile rupture / axial necking
COLLAPSE_SF_TARGET = 1.10   # Clause 8 external pressure resistance

# -----------------------------------------------------------------------------
# PAGE 3 METHODOLOGY: GLOSSARY & CARD BUILDERS
# -----------------------------------------------------------------------------
# Plain-English explanations for the jargon on Page 6. Rendered as click-to-open
# pop-ups so a reader who does not know a term can get it without leaving the page.
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
    "bo": ("Oil formation volume factor (Bo)",
           "Barrels of downhole live oil that shrink into one stock-tank barrel at surface. A Bo of 1.3 "
           "means the oil occupies 30% more space downhole because of dissolved gas."),
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
               "A notched bar struck by a swinging pendulum; the energy absorbed in breaking it measures toughness, "
               "the resistance to brittle fracture from an existing flaw. Required because a pipe can be strong and "
               "ductile in tension yet still shatter at a notch under impact loading."),
    "martensite": ("Martensite",
                   "The hard, supersaturated phase formed when steel is quenched fast enough to trap carbon in the "
                   "lattice. The as-quenched hardness is measured as proof that the required martensite fraction was "
                   "actually achieved through the full wall before tempering brings the strength back down."),
    "hydro-test": ("Hydrostatic proof test",
                   "The pressure every joint is held at in the mill before shipment, set as a fixed fraction of "
                   "yield. It is a proof of integrity for that individual joint, not a design rating: the pipe is "
                   "never intended to operate above the pressure at which it was demonstrated sound."),
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

    Shared by the engine and the Page 7 default so the surface burst check and the
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

    Honours the Page 8 OD/grade filters when they have been set; falls back to the
    full database otherwise (e.g. when the user goes straight to Page 9).
    """
    db = st.session_state.tubing_db
    selection = st.session_state.get('candidate_filter')
    if not selection:
        return db
    return db[db['OD_in'].isin(selection.get('od', [])) & db['Grade'].isin(selection.get('grade', []))]

def highlight_passing_row_matrix(row):
    """Highlight the entire row in soft green if the candidate passed all checks."""
    if row.get('Overall Status') is True:
        return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
    return [''] * len(row)

def highlight_passing_row_gates(row):
    """Highlight the entire gate row in soft green if all individual gate checks passed."""
    # Check if all gate boolean values (excluding 'Tubing Candidate') are True
    gate_statuses = [val for col, val in row.items() if col != 'Tubing Candidate']
    if all(gate_statuses):
        return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
    return [''] * len(row)

# -----------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/000000/oil-rig.png", width=70)
st.sidebar.title("Tubing Selection Tool")
st.sidebar.caption("Upper-Completion Design Engine")

PAGE_LABELS = [
    "1. Introduction & Overview",
    "2. Wellbore Geometry & PVT",
    "3. Wellbore Hydraulics & Velocity Limits",
    "4. Tubing Stress Analysis",
    "5. Material Selection",
    "6. Calculation Methodology",
    "7. Well & Fluid Inputs",
    "8. Candidate Tubing Specs",
    "9. Engineering Calculations",
    "10. Recommendation & Sensitivity",
]

# Referenced by name rather than position so inserting a page cannot silently
# redirect the flowchart deep links to the wrong step.
METHODOLOGY_PAGE = "6. Calculation Methodology"

# A ?step=N link in the Page 6 flowchart must survive the rerun it triggers: force
# the sidebar back onto Page 6 so the reader lands on the step they clicked.
_requested_step = st.query_params.get("step")
if _requested_step and st.session_state.get("nav_page") != METHODOLOGY_PAGE:
    st.session_state["nav_page"] = METHODOLOGY_PAGE

page = st.sidebar.radio(
    "Select Workflow Step:",
    PAGE_LABELS,
    key="nav_page"
)

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    # assets/cover_web.jpg is a 1600 px re-encode of cover.jpg. The full-resolution
    # original is ~6.6 MB, which becomes ~8.8 MB of base64 inlined into the hero's
    # background-image on every Page 1 render; the web copy is ~220 KB for the same
    # on-screen result. cover.jpg stays in the fallback chain.
    cover_b64 = first_existing_image([
        'assets/cover_web.jpg', 'cover.jpg', 'cover.png', 'cover.jpeg',
    ])

    st.markdown("""
    <style>
    /* ---- Page 1 design system -------------------------------------------- */
    .p1-scope { --p1-ink: #0F172A; --p1-muted: #64748B; --p1-body: #334155;
                --p1-line: #E2E8F0; --p1-blue: #1E3A8A; --p1-green: #065F46; --p1-red: #991B1B; }

    /* Section banner: numbered chip + title + lead paragraph */
    .p1-section { position: relative; background: #FFFFFF; border: 1px solid #E2E8F0;
                  border-radius: 14px; padding: 1.35rem 1.5rem; margin: 0 0 1.1rem;
                  box-shadow: 0 1px 2px rgba(15,23,42,0.04); scroll-margin-top: 1.5rem; overflow: hidden; }
    .p1-section::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 5px; }
    .p1-section-blue::before  { background: linear-gradient(180deg, #3B82F6, #1E3A8A); }
    .p1-section-green::before { background: linear-gradient(180deg, #34D399, #065F46); }
    .p1-section-red::before   { background: linear-gradient(180deg, #F87171, #991B1B); }
    .p1-section-head { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.55rem; }
    .p1-section-num { flex: none; display: grid; place-items: center; width: 2.3rem; height: 2.3rem;
                      border-radius: 9px; font-size: 0.9rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.01em; }
    .p1-section-blue  .p1-section-num { background: linear-gradient(135deg, #2563EB, #1E3A8A); }
    .p1-section-green .p1-section-num { background: linear-gradient(135deg, #059669, #065F46); }
    .p1-section-red   .p1-section-num { background: linear-gradient(135deg, #DC2626, #991B1B); }
    .p1-section-title { font-size: 1.42rem; font-weight: 800; line-height: 1.25; margin: 0; }
    .p1-section-blue  .p1-section-title { color: #1E3A8A; }
    .p1-section-green .p1-section-title { color: #065F46; }
    .p1-section-red   .p1-section-title { color: #991B1B; }
    .p1-section-lead { font-size: 1.0rem; line-height: 1.65; color: #334155; margin: 0; }
    .p1-section-lead b { color: #0F172A; }

    /* Content card */
    .p1-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
               padding: 1.15rem 1.25rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15,23,42,0.04);
               transition: box-shadow 0.18s ease, border-color 0.18s ease; scroll-margin-top: 1.5rem; }
    .p1-card:hover { box-shadow: 0 8px 20px rgba(15,23,42,0.09); border-color: #CBD5E1; }
    .p1-card-title { font-size: 1.12rem; font-weight: 800; margin: 0 0 0.5rem; line-height: 1.3; }
    .p1-card-blue  .p1-card-title { color: #1E3A8A; }
    .p1-card-green .p1-card-title { color: #065F46; }
    .p1-card-red   .p1-card-title { color: #991B1B; }
    .p1-card-body { font-size: 0.94rem; line-height: 1.65; color: #334155; margin: 0; }

    /* Eyebrow chip above card titles */
    .p1-chip { display: inline-block; font-size: 0.68rem; font-weight: 800; letter-spacing: 0.07em;
               text-transform: uppercase; padding: 0.18rem 0.5rem; border-radius: 999px; margin-bottom: 0.55rem; }
    .p1-chip-blue  { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .p1-chip-green { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .p1-chip-red   { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }

    /* Definition list: term + description, replaces bare bullets */
    .p1-list { list-style: none; margin: 0; padding: 0; }
    .p1-list li { position: relative; padding: 0.5rem 0 0.5rem 1.5rem; font-size: 0.92rem;
                  line-height: 1.6; color: #334155; border-top: 1px dashed #E2E8F0; }
    .p1-list li:first-child { border-top: none; padding-top: 0.15rem; }
    .p1-list li::before { content: ""; position: absolute; left: 0.25rem; top: 1.05rem;
                          width: 6px; height: 6px; border-radius: 50%; background: #94A3B8; }
    .p1-list li:first-child::before { top: 0.7rem; }
    .p1-list-blue  li::before { background: #3B82F6; }
    .p1-list-green li::before { background: #10B981; }
    .p1-list-red   li::before { background: #EF4444; }
    .p1-term { font-weight: 700; color: #0F172A; }

    /* Figure plate */
    .p1-figure { margin: 0 0 1rem; }
    .p1-figure-frame { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px;
                       padding: 0.85rem; display: flex; justify-content: center; align-items: center; }
    .p1-figure-frame img { max-width: 100%; height: auto; border-radius: 6px; display: block; }
    .p1-figure-caption { font-size: 0.82rem; color: #64748B; line-height: 1.5; margin-top: 0.5rem; text-align: center; }
    .p1-figure-number { display: inline-block; font-weight: 800; color: #1E3A8A;
                        background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 4px;
                        padding: 0.05rem 0.4rem; margin-right: 0.45rem; font-size: 0.74rem; }

    /* Specification table */
    .p1-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.92rem;
                border: 1px solid #E2E8F0; border-radius: 10px; overflow: hidden; }
    .p1-table thead th { background: linear-gradient(135deg, #047857, #065F46); color: #FFFFFF;
                         text-align: left; padding: 0.75rem 1rem; font-size: 0.76rem;
                         letter-spacing: 0.06em; text-transform: uppercase; font-weight: 800; }
    .p1-table tbody td { padding: 0.7rem 1rem; border-top: 1px solid #E2E8F0; color: #334155; vertical-align: top; }
    .p1-table tbody tr:nth-child(even) { background: #F8FAFC; }
    .p1-table tbody tr:hover { background: #ECFDF5; }
    .p1-table .p1-spec { font-weight: 700; color: #0F172A; white-space: nowrap; }

    /* Divider between major sections */
    .p1-rule { height: 1px; background: linear-gradient(90deg, transparent, #CBD5E1 15%, #CBD5E1 85%, transparent);
               margin: 1.9rem 0 1.5rem; border: none; }

    @media (max-width: 700px) {
        .p1-section-title { font-size: 1.2rem; }
        .p1-table .p1-spec { white-space: normal; }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    .p1-hero { position: relative; border-radius: 18px; overflow: hidden; margin-bottom: 1.1rem;
               box-shadow: 0 18px 38px rgba(15,23,42,0.24); min-height: 340px;
               display: flex; flex-direction: column; justify-content: flex-end; padding: 2.4rem 2.2rem 2rem; }
    .p1-hero-fallback { background: radial-gradient(120% 140% at 12% 10%, #1D4ED8 0%, #0F172A 55%, #020617 100%); }
    .p1-hero-kicker { color: #7DD3FC; font-size: 0.76rem; font-weight: 800; letter-spacing: 0.16em;
                      text-transform: uppercase; margin-bottom: 0.5rem; }
    .p1-hero-title, .stMarkdown h1.p1-hero-title {
                     color: #FFFFFF !important; font-size: 2.5rem; font-weight: 800; line-height: 1.12;
                     margin: 0 0 0.6rem; letter-spacing: -0.02em; text-shadow: 0 2px 10px rgba(0,0,0,0.55); }
    .p1-hero-sub { color: #DBEAFE; font-size: 1.03rem; line-height: 1.6; margin: 0; max-width: 44rem;
                   text-shadow: 0 1px 6px rgba(0,0,0,0.6); }
    .p1-hero-meta { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 1.1rem; }
    .p1-hero-tag { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.24);
                   color: #E0F2FE; font-size: 0.76rem; font-weight: 600; padding: 0.3rem 0.7rem;
                   border-radius: 999px; backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); }

    /* Contents rail: three linked cards below the hero */
    .p1-toc { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.85rem; margin-bottom: 1.5rem; }
    .p1-toc-card { display: block; text-decoration: none !important; background: #FFFFFF;
                   border: 1px solid #E2E8F0; border-top: 3px solid var(--accent, #3B82F6);
                   border-radius: 12px; padding: 0.95rem 1.05rem; height: 100%;
                   box-shadow: 0 1px 2px rgba(15,23,42,0.04);
                   transition: transform 0.18s ease, box-shadow 0.18s ease; }
    .p1-toc-card:hover { transform: translateY(-3px); box-shadow: 0 12px 22px rgba(15,23,42,0.12); }
    .p1-toc-num { font-size: 0.72rem; font-weight: 800; letter-spacing: 0.08em;
                  color: var(--accent, #3B82F6); text-transform: uppercase; }
    .p1-toc-title { font-size: 1.0rem; font-weight: 800; color: #0F172A; line-height: 1.3; margin: 0.18rem 0 0.3rem; }
    .p1-toc-desc { font-size: 0.83rem; color: #64748B; line-height: 1.5; }
    .p1-toc-sub { font-size: 0.75rem; color: #94A3B8; line-height: 1.45; margin-top: 0.5rem;
                  padding-top: 0.5rem; border-top: 1px dashed #E2E8F0; }

    @media (max-width: 820px) {
        .p1-toc { grid-template-columns: 1fr; }
        .p1-hero { min-height: 260px; padding: 1.6rem 1.4rem; }
        .p1-hero-title { font-size: 1.85rem; }
    }
    </style>
    """, unsafe_allow_html=True)

    hero_bg = (
        f"background: linear-gradient(175deg, rgba(15,23,42,0.42) 0%, rgba(15,23,42,0.72) 45%, rgba(2,6,23,0.94) 100%), "
        f"url('{cover_b64}') center/cover no-repeat;"
        if cover_b64 else ""
    )
    hero_class = "p1-hero" if cover_b64 else "p1-hero p1-hero-fallback"

    st.markdown(f"""
    <div class="{hero_class}" style="{hero_bg}">
        <div class="p1-hero-kicker">Upper Completion Design Engine</div>
        <h1 class="p1-hero-title">Interactive Tubing Selection Tool</h1>
        <p class="p1-hero-sub">
            A guided engineering walkthrough of completion hardware, fluid transport dynamics,
            structural load boundaries, and the trade-offs behind a defensible tubing recommendation.
        </p>
        <div class="p1-hero-meta">
            <span class="p1-hero-tag">Production tubing as the primary flow path</span>
            <span class="p1-hero-tag">Hydraulics &middot; integrity &middot; operability</span>
            <span class="p1-hero-tag">Screened tubing recommendation</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <nav class="p1-toc" aria-label="Page contents">
        <a class="p1-toc-card" href="#1-0-what-is-upper-completion" style="--accent: #2563EB;">
            <div class="p1-toc-num">Section 1.0</div>
            <div class="p1-toc-title">Upper Completion</div>
            <div class="p1-toc-desc">Hardware and flow-conduit overview</div>
            <div class="p1-toc-sub">1.1 Configurations &middot; 1.2 Design decisions &middot; 1.3 Components</div>
        </a>
        <a class="p1-toc-card" href="#2-0-production-tubing" style="--accent: #059669;">
            <div class="p1-toc-num">Section 2.0</div>
            <div class="p1-toc-title">Production Tubing</div>
            <div class="p1-toc-desc">The flow path of the well</div>
            <div class="p1-toc-sub">2.1 Dimensions &amp; geometry &middot; 2.2 Specifications</div>
        </a>
    </nav>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # MAIN TOPIC 1.0: WHAT IS UPPER COMPLETION?
    # -------------------------------------------------------------------------
    st.markdown("""
    <section id="1-0-what-is-upper-completion" class="p1-section p1-section-blue">
        <div class="p1-section-head">
            <div class="p1-section-num">1.0</div>
            <h2 class="p1-section-title">What is Upper Completion?</h2>
        </div>
        <p class="p1-section-lead">
            The <b>upper completion</b> is the portion of a well completion located <b>above the lower or reservoir
            completion</b>, extending to the <b>wellhead and surface facilities</b>. It provides the main pathway for
            <b>produced or injected fluids</b>, and depending on well requirements may include production tubing,
            packers, subsurface safety valves, artificial-lift systems, and chemical-injection systems.
        </p>
    </section>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.markdown(f"""
        <div id="1-1-upper-completion-configurations" class="p1-card p1-card-blue">
            <span class="p1-chip p1-chip-blue">Subtopic 1.1</span>
            <h3 class="p1-card-title">Upper Completion Configurations</h3>
            <ul class="p1-list p1-list-blue">
                <li><span class="p1-term">Tubingless completion</span> — fluids flow through the casing.</li>
                <li><span class="p1-term">Tubing without packer</span> — tubing installed without annular isolation.</li>
                <li><span class="p1-term">Tubing with packer</span> — the packer isolates the tubing–casing annulus.</li>
                <li><span class="p1-term">Dual tubing with packers</span> — separate flow paths for multiple zones or fluids.</li>
            </ul>
        </div>
        {figure_block("Figure 1.png", "1", "Upper-completion configurations")}
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div id="1-2-major-design-decisions" class="p1-card p1-card-blue">
            <span class="p1-chip p1-chip-blue">Subtopic 1.2</span>
            <h3 class="p1-card-title">Major Design Considerations</h3>
            <ul class="p1-list p1-list-blue">
                <li><span class="p1-term">Artificial lift</span> — gas lift, ESP, or natural flow.</li>
                <li><span class="p1-term">Tubing size</span> — balances production capacity against pressure drop.</li>
                <li><span class="p1-term">Completion configuration</span> — single or dual completion.</li>
                <li><span class="p1-term">Tubing isolation</span> — a packer or equivalent to control fluid communication.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # Subtopic 1.3 spans the full width beneath 1.1 and 1.2
    st.markdown("""
    <div id="1-3-key-components" class="p1-card p1-card-blue">
        <span class="p1-chip p1-chip-blue">Subtopic 1.3</span>
        <h3 class="p1-card-title">Key Components</h3>
        <p class="p1-card-body">
            Typical components include <b>production tubing, packers, subsurface safety valves (SCSSVs),
            artificial-lift equipment, and chemical-injection systems</b>. Together they enable safe fluid
            transport, well control, well integrity, and future intervention.
        </p>
    </div>
    """, unsafe_allow_html=True)
    # Interactive schematic in place of a static Figure 2 image. Clicking a hotspot
    # on the diagram renders that component's details in the side panel.
    components.html(load_asset('schematic_upper_completion.html'), height=720, scrolling=False)
    st.markdown(
        '<figure class="p1-figure"><figcaption class="p1-figure-caption">'
        '<span class="p1-figure-number">Figure 2</span>'
        'Typical upper-completion components — click a section of the schematic for details.'
        '</figcaption></figure>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="p1-rule" />', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # MAIN TOPIC 2.0: PRODUCTION TUBING
    # -------------------------------------------------------------------------
    st.markdown("""
    <section id="2-0-production-tubing" class="p1-section p1-section-green">
        <div class="p1-section-head">
            <div class="p1-section-num">2.0</div>
            <h2 class="p1-section-title">Production Tubing: The Flow Path of the Well</h2>
        </div>
        <p class="p1-section-lead">
            <b>Production tubing</b> is the primary conduit carrying <b>oil, gas, or injected fluids</b> between the
            reservoir and surface facilities. Its design balances <b>flow performance, mechanical integrity, and
            operational requirements</b> — tubing size, wall thickness, steel grade, connection type, and mechanical
            strength must together withstand the pressure, temperature, and loads seen across the well's life.
        </p>
    </section>
    """, unsafe_allow_html=True)

    # Interactive schematic in place of a static Figure 3 image. Clicking a string in
    # the SVG (or the legend list) renders its details in the side panel.
    components.html(load_asset('schematic_casing_tubing.html'), height=760, scrolling=False)
    st.markdown(
        '<figure class="p1-figure"><figcaption class="p1-figure-caption">'
        '<span class="p1-figure-number">Figure 3</span>'
        'Casing and tubing strings in a completed well — click a string in the schematic '
        'or the list for details.'
        '</figcaption></figure>',
        unsafe_allow_html=True,
    )

    st.markdown("""
    <div id="2-1-tubing-dimensions-geometry" class="p1-card p1-card-green">
        <span class="p1-chip p1-chip-green">Subtopic 2.1</span>
        <h3 class="p1-card-title">Tubing Dimensions &amp; Geometry</h3>
        <p class="p1-card-body">
            Cross-sectional geometry governs both the internal fluid dynamics (<b>ID</b>) and the external
            clearance inside the casing (<b>OD</b>). Nominal wall thickness provides burst and collapse
            resistance under downhole pressure differentials.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Interactive schematic in place of a static Figure 4 image. Clicking a dimension
    # in the SVG (or the legend list) renders its introduction in the panel.
    components.html(load_asset('schematic_cross_section.html'), height=700, scrolling=False)
    st.markdown(
        '<figure class="p1-figure"><figcaption class="p1-figure-caption">'
        '<span class="p1-figure-number">Figure 4</span>'
        'Tubing cross-section dimensions — click a dimension in the schematic '
        'or the list for details.'
        '</figcaption></figure>',
        unsafe_allow_html=True,
    )

    st.markdown("""
    <div id="2-2-key-tubing-specifications" class="p1-card p1-card-green">
        <span class="p1-chip p1-chip-green">Subtopic 2.2</span>
        <h3 class="p1-card-title">Key Tubing Specifications</h3>
        <table class="p1-table">
            <thead>
                <tr><th style="width: 26%;">Specification</th><th>Why it matters</th></tr>
            </thead>
            <tbody>
                <tr><td class="p1-spec">Nominal size / OD</td><td>Sets overall tubing size and compatibility with the casing.</td></tr>
                <tr><td class="p1-spec">Internal diameter (ID)</td><td>Drives <b>fluid velocity and pressure loss</b>.</td></tr>
                <tr><td class="p1-spec">Drift diameter</td><td>Limits the maximum equipment diameter that can pass through the tubing.</td></tr>
                <tr><td class="p1-spec">Nominal weight</td><td>Indicates tubing weight and relates directly to <b>wall thickness</b>.</td></tr>
                <tr><td class="p1-spec">Steel grade</td><td>Determines <b>strength and suitability for corrosive environments</b>.</td></tr>
                <tr><td class="p1-spec">Connection</td><td>Affects connection strength, sealing, and overall tubing integrity.</td></tr>
                <tr><td class="p1-spec">Joint length</td><td>Influences running and handling during completion and workover.</td></tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr class="p1-rule" />', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE 2: WELLBORE HYDRAULICS & PVT
# -----------------------------------------------------------------------------
elif page == "2. Wellbore Geometry & PVT":
    st.markdown('<div class="main-header">Step 2: Wellbore Geometry & Interactive PVT Characterization</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Interactive simulation of fluid phase behavior, downhole density profiles, and volume swelling across true vertical depth (TVD).</div>', unsafe_allow_html=True)

    tab_pvt, tab_geo = st.tabs([
        "📊 Tab 1: Interactive PVT & Depth Profiles",
        "📐 Tab 2: Gas Thermodynamics & Mixture Density"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: INTERACTIVE PVT & DEPTH PROFILES
    # -------------------------------------------------------------------------
    with tab_pvt:
        inputs = st.session_state.inputs

        with st.expander("⚙️ Interactive Controls & Fluid Parameters", expanded=True):
            col_m1, col_m2, col_m3 = st.columns(3)

            with col_m1:
                well_mode = st.radio(
                    "Select Well Operating Mode:",
                    ["Oil Well (Standing's PVT)", "Gas Well (Dranchuk-Abou-Kassem EOS)"],
                    index=0 if "Oil" in inputs.get('well_type', 'Oil Well') else 1
                )
                max_tvd = st.slider("Target TVD (ft)", min_value=2000.0, max_value=25000.0, value=float(inputs.get('tvd', 10000.0)), step=500.0)
                n_points = st.slider("Depth Grid Resolution (Steps)", min_value=20, max_value=200, value=50, step=10)

            with col_m2:
                p_wh_in = st.number_input("Wellhead Pressure - P_wh (psig)", min_value=0.0, max_value=5000.0, value=float(inputs.get('p_wh', 800.0)), step=50.0)
                p_bhp_in = st.number_input("Bottomhole Pressure - P_bhp (psig)", min_value=500.0, max_value=20000.0, value=float(inputs.get('p_bhp', 4500.0)), step=100.0)
                t_wh_in = st.number_input("Wellhead Temp - T_wh (°F)", min_value=32.0, max_value=300.0, value=float(inputs.get('t_wh', 150.0)), step=5.0)
                t_bht_in = st.number_input("Bottomhole Temp - BHT (°F)", min_value=80.0, max_value=450.0, value=float(inputs.get('t_bht', 210.0)), step=5.0)

            with col_m3:
                api_in = st.number_input("Oil Gravity (°API)", min_value=10.0, max_value=60.0, value=float(inputs.get('api_gravity', 35.0)), step=0.5)
                gas_sg_in = st.number_input("Gas Specific Gravity (Air=1.0)", min_value=0.50, max_value=1.20, value=float(inputs.get('gas_sg', 0.65)), step=0.01)
                water_sg_in = st.number_input("Water Specific Gravity", min_value=1.00, max_value=1.30, value=float(inputs.get('water_sg', 1.05)), step=0.01)

                if "Oil" in well_mode:
                    gor_in = st.number_input("Producing GOR (scf/STB)", min_value=0.0, max_value=10000.0, value=float(inputs.get('gor', 800.0)), step=50.0)
                    wc_in = st.number_input("Water Cut (%)", min_value=0.0, max_value=100.0, value=float(inputs.get('water_cut', 5.0)), step=1.0)
                else:
                    cgr_in = st.number_input("Condensate-Gas Ratio (STB/MMscf)", min_value=0.0, max_value=500.0, value=float(inputs.get('cgr_stb_mmscf', 25.0)), step=5.0)
                    wgr_in = st.number_input("Water-Gas Ratio (bbl/MMscf)", min_value=0.0, max_value=200.0, value=float(inputs.get('wgr_bbl_mmscf', 5.0)), step=1.0)

        # Mode Explanation Box
        if "Oil" in well_mode:
            st.info(
                "💡 **Oil Well Mode Explanation:** Uses **Standing's Empirical PVT Correlations** to model "
                r"dissolved gas in oil ($R_s$), downhole oil volumetric swelling ($B_o$), live-oil density ($\rho_{o,live}$), "
                r"and combined total liquid density ($\rho_l$). As pressure drops toward the surface, gas breaks out of solution, "
                "shrinking the liquid volume and increasing live-oil density."
            )
        else:
            st.info(
                "💡 **Gas Well Mode Explanation:** Uses the **Dranchuk-Abou-Kassem (DAK) Equation of State** to calculate "
                r"gas compressibility ($Z$-factor), in-situ gas density ($\rho_g$), gas formation volume factor ($B_g$), and "
                r"condensate/water holdup density ($\rho_l$). Demonstrates how high pressure at depth heavily compresses gas, "
                "significantly increasing downhole gas density compared to surface conditions."
            )

        # -------------------------------------------------------------------------
        # DEPTH PROFILE COMPUTATIONS (TAB 1)
        # -------------------------------------------------------------------------
        tvd_array = np.linspace(0, max_tvd, n_points)
        gamma_o = 141.5 / (131.5 + api_in)
        rho_w = water_sg_in * 62.4

        # Vectorized depth profile: pressure and temperature ramp linearly with TVD,
        # so the whole column is built with NumPy instead of a per-depth Python loop
        # that re-tested the well mode on every iteration.
        depth_frac = tvd_array / max_tvd if max_tvd > 0 else np.zeros_like(tvd_array)
        p_psia_arr = p_wh_in + (p_bhp_in - p_wh_in) * depth_frac + 14.7
        t_deg_f_arr = t_wh_in + (t_bht_in - t_wh_in) * depth_frac
        t_deg_r_arr = t_deg_f_arr + 459.67
        zeros = np.zeros_like(tvd_array)

        if "Oil" in well_mode:
            rs_arr = np.minimum(
                gas_sg_in * (((p_psia_arr / 18.2) + 1.4) * (10 ** (0.0125 * api_in - 0.00091 * t_deg_f_arr))) ** 1.2048,
                gor_in,
            )
            bo_arr = 0.9759 + 0.000120 * ((rs_arr * ((gas_sg_in / gamma_o) ** 0.5) + 1.25 * t_deg_f_arr) ** 1.2)
            rho_o_live_arr = (62.4 * gamma_o + 0.0136 * rs_arr * gas_sg_in) / bo_arr
            wc_frac = wc_in / 100.0
            rho_l_arr = (1.0 - wc_frac) * rho_o_live_arr + wc_frac * rho_w
            bg_arr, rho_g_arr = zeros, zeros
        else:
            # The DAK Z-factor is an implicit fixed point, so it stays a per-point
            # solve; everything derived from it is vectorized.
            z_arr = np.array([
                compute_dynamic_z_factor(p, t, gas_sg_in) for p, t in zip(p_psia_arr, t_deg_r_arr)
            ])
            rho_g_arr = (2.7 * gas_sg_in * p_psia_arr) / (z_arr * t_deg_r_arr)
            bg_arr = 0.02829 * z_arr * t_deg_r_arr / p_psia_arr

            total_liq_bbl = cgr_in + wgr_in
            rho_cond = 62.4 * gamma_o
            if total_liq_bbl > 0:
                wc_frac = wgr_in / total_liq_bbl
                rho_l_scalar = (1.0 - wc_frac) * rho_cond + wc_frac * rho_w
            else:
                rho_l_scalar = rho_cond
            rho_l_arr = np.full_like(tvd_array, rho_l_scalar)
            rs_arr, rho_o_live_arr = zeros, zeros
            bo_arr = np.ones_like(tvd_array)

        df_pvt = pd.DataFrame({
            'TVD_ft': tvd_array,
            'P_psia': p_psia_arr,
            'Rs_scf_stb': rs_arr,
            'Bo_rb_stb': bo_arr,
            'Bg_cuft_scf': bg_arr,
            'rho_o_live': rho_o_live_arr,
            'rho_l': rho_l_arr,
            'rho_g': rho_g_arr
        })

        st.markdown("### 📊 Live Liquid Density & Volumetric Expansion vs. True Vertical Depth")

        fig_primary = go.Figure()

        if "Oil" in well_mode:
            fig_primary.add_trace(go.Scatter(
                x=df_pvt['rho_l'], y=df_pvt['TVD_ft'],
                mode='lines+markers', name='Total Liquid Density (ρ_l, lb/ft³)',
                line=dict(color='#1E3A8A', width=3),
                hovertemplate='Depth: %{y:.1f} ft<br>ρ_l: %{x:.2f} lb/ft³<extra></extra>'
            ))
            fig_primary.add_trace(go.Scatter(
                x=df_pvt['rho_o_live'], y=df_pvt['TVD_ft'],
                mode='lines', name='Live Oil Density (ρ_o,live, lb/ft³)',
                line=dict(color='#2563EB', width=2, dash='dash'),
                hovertemplate='Depth: %{y:.1f} ft<br>ρ_o,live: %{x:.2f} lb/ft³<extra></extra>'
            ))
            fig_primary.add_trace(go.Scatter(
                x=df_pvt['Bo_rb_stb'], y=df_pvt['TVD_ft'],
                mode='lines', name='Oil Swelling Factor (B_o, rb/STB)',
                line=dict(color='#D97706', width=2.5, dash='dot'),
                xaxis='x2',
                hovertemplate='Depth: %{y:.1f} ft<br>B_o: %{x:.4f} rb/STB<extra></extra>'
            ))
            fig_primary.update_layout(
                xaxis=dict(title='Density (lb/ft³)', title_font=dict(color='#1E3A8A')),
                xaxis2=dict(
                    title='Oil Formation Volume Factor B_o (rb/STB)',
                    title_font=dict(color='#D97706'),
                    overlaying='x', side='top'
                ),
                yaxis=dict(title='True Vertical Depth - TVD (ft)', autorange='reversed')
            )
        else:
            fig_primary.add_trace(go.Scatter(
                x=df_pvt['rho_g'], y=df_pvt['TVD_ft'],
                mode='lines+markers', name='In-Situ Gas Density (ρ_g, lb/ft³)',
                line=dict(color='#059669', width=3),
                hovertemplate='Depth: %{y:.1f} ft<br>ρ_g: %{x:.2f} lb/ft³<extra></extra>'
            ))
            fig_primary.add_trace(go.Scatter(
                x=df_pvt['Bg_cuft_scf'], y=df_pvt['TVD_ft'],
                mode='lines', name='Gas Expansion Factor (B_g, ft³/scf)',
                line=dict(color='#7C3AED', width=2.5, dash='dash'),
                xaxis='x2',
                hovertemplate='Depth: %{y:.1f} ft<br>B_g: %{x:.5f} ft³/scf<extra></extra>'
            ))
            fig_primary.update_layout(
                xaxis=dict(title='Gas Density (lb/ft³)', title_font=dict(color='#059669')),
                xaxis2=dict(
                    title='Gas Formation Volume Factor B_g (ft³/scf)',
                    title_font=dict(color='#7C3AED'),
                    overlaying='x', side='top'
                ),
                yaxis=dict(title='True Vertical Depth - TVD (ft)', autorange='reversed')
            )

        fig_primary.update_layout(
            height=580,
            margin=dict(l=60, r=60, t=80, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
            hovermode="y unified"
        )
        st.plotly_chart(fig_primary, use_container_width=True)

        st.markdown("---")
        st.markdown("### 🔍 Depth Spot-Inspection Panel")
        inspect_tvd = st.slider("Select Depth to Inspect (ft)", min_value=0.0, max_value=max_tvd, value=max_tvd / 2.0, step=100.0)

        p_ins_gauge = p_wh_in + (p_bhp_in - p_wh_in) * (inspect_tvd / max_tvd)
        p_ins_psia = p_ins_gauge + 14.7
        t_ins_f = t_wh_in + (t_bht_in - t_wh_in) * (inspect_tvd / max_tvd)

        col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
        col_k1.metric("Local Pressure", f"{p_ins_gauge:.1f} psig")
        col_k2.metric("Local Temperature", f"{t_ins_f:.1f} °F")

        if "Oil" in well_mode:
            rs_ins = gas_sg_in * (((p_ins_psia / 18.2) + 1.4) * (10 ** (0.0125 * api_in - 0.00091 * t_ins_f))) ** 1.2048
            rs_ins = min(rs_ins, gor_in)
            bo_ins = 0.9759 + 0.000120 * ((rs_ins * ((gas_sg_in / gamma_o) ** 0.5) + 1.25 * t_ins_f) ** 1.2)
            rho_o_ins = (62.4 * gamma_o + 0.0136 * rs_ins * gas_sg_in) / bo_ins
            rho_l_ins = (1.0 - (wc_in / 100.0)) * rho_o_ins + (wc_in / 100.0) * rho_w

            col_k3.metric("Solution GOR (R_s)", f"{rs_ins:.1f} scf/STB")
            col_k4.metric("Oil Swelling (B_o)", f"{bo_ins:.3f} rb/STB")
            col_k5.metric("Total Liquid Density (ρ_l)", f"{rho_l_ins:.2f} lb/ft³")
        else:
            z_ins = compute_dynamic_z_factor(p_ins_psia, t_ins_f + 459.67, gas_sg_in)
            rho_g_ins = (2.7 * gas_sg_in * p_ins_psia) / (z_ins * (t_ins_f + 459.67))
            bg_ins = 0.02829 * z_ins * (t_ins_f + 459.67) / p_ins_psia

            col_k3.metric("Z-Factor", f"{z_ins:.3f}")
            col_k4.metric("Gas Volume Factor (B_g)", f"{bg_ins:.5f} ft³/scf")
            col_k5.metric("In-Situ Gas Density (ρ_g)", f"{rho_g_ins:.2f} lb/ft³")

    # -------------------------------------------------------------------------
    # TAB 2: GAS THERMODYNAMICS & MULTIPHASE MIXTURE DENSITY
    # -------------------------------------------------------------------------
    with tab_geo:
        st.markdown(r"### 🧪 Gas PVT, Compressibility ($Z$) & Mixture Density ($\rho_m$)")

        # Explanatory Box Focusing on Mode Differences
        st.markdown(r"""
        <div style="background-color: #F8FAFC; border-left: 4px solid #0284C7; padding: 0.9rem; border-radius: 6px; margin-bottom: 1.2rem;">
            <b style="color: #0369A1; font-size: 1.0rem;">🔥 Fundamental Differences: Oil PVT vs. Gas Well Thermodynamics</b>
            <ul style="margin-top: 0.4rem; margin-bottom: 0rem; font-size: 0.88rem; color: #334155; line-height: 1.5;">
                <li><b>Compressibility Mechanics:</b> Gas density ($\rho_g$) changes dramatically with depth because gas is highly compressible ($Z$-factor drops downhole under severe pressure). Oil density ($\rho_o$) is governed primarily by dissolved gas ($R_s$) and liquid volume swelling ($B_o$).</li>
                <li><b>Mixture Homogeneity:</b> In gas wells, the stream is gas-dominated ($Q_g$). Adding even small amounts of condensate (CGR) or water (WGR) increases liquid holdup ($\lambda_l$), causing significant shifts in the bulk mixture density ($\rho_m$).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        inputs = st.session_state.inputs

        with st.expander("⚙️ Gas Well PVT Parameters & Production Controls", expanded=True):
            col_g1, col_g2, col_g3 = st.columns(3)

            with col_g1:
                tvd_gas = st.slider("Target TVD - Depth (ft)", min_value=2000.0, max_value=25000.0, value=float(inputs.get('tvd', 10000.0)), step=500.0, key="gas_tvd")
                q_gas_mmscfd = st.number_input("Surface Gas Rate - Q_g (MMscf/D)", min_value=0.1, max_value=200.0, value=float(inputs.get('q_gas_mmscfd', 15.0)), step=0.5)
                gas_sg_g = st.number_input("Gas Specific Gravity - γ_g (Air=1.0)", min_value=0.50, max_value=1.20, value=float(inputs.get('gas_sg', 0.65)), step=0.01, key="gas_sg_g")

            with col_g2:
                p_wh_g = st.number_input("Wellhead Pressure - P_wh (psig)", min_value=0.0, max_value=5000.0, value=float(inputs.get('p_wh', 800.0)), step=50.0, key="p_wh_g")
                p_bhp_g = st.number_input("Bottomhole Pressure - P_bhp (psig)", min_value=500.0, max_value=20000.0, value=float(inputs.get('p_bhp', 4500.0)), step=100.0, key="p_bhp_g")
                cgr_g = st.slider("Condensate-Gas Ratio - CGR (STB/MMscf)", min_value=0.0, max_value=500.0, value=float(inputs.get('cgr_stb_mmscf', 25.0)), step=5.0, key="cgr_g_slider")

            with col_g3:
                t_wh_g = st.number_input("Wellhead Temp - T_wh (°F)", min_value=32.0, max_value=300.0, value=float(inputs.get('t_wh', 150.0)), step=5.0, key="t_wh_g")
                t_bht_g = st.number_input("Bottomhole Temp - BHT (°F)", min_value=80.0, max_value=450.0, value=float(inputs.get('t_bht', 210.0)), step=5.0, key="t_bht_g")
                wgr_g = st.slider("Water-Gas Ratio - WGR (bbl/MMscf)", min_value=0.0, max_value=200.0, value=float(inputs.get('wgr_bbl_mmscf', 5.0)), step=1.0, key="wgr_g_slider")

        # -------------------------------------------------------------------------
        # GAS THERMODYNAMICS & MIXTURE DENSITY COMPUTATIONS
        # -------------------------------------------------------------------------
        p_pc = 756.8 - 131.07 * gas_sg_g - 3.6 * (gas_sg_g ** 2)
        t_pc = 169.2 + 349.5 * gas_sg_g - 74.0 * (gas_sg_g ** 2)

        st.caption(f"**Standing's Pseudo-Critical Anchors:** $P_{{pc}}$ = **{p_pc:.1f} psia** | $T_{{pc}}$ = **{t_pc:.1f} °R**")

        tvd_array_g = np.linspace(0, tvd_gas, 60)
        api_g = float(inputs.get('api_gravity', 35.0))
        gamma_o_g = 141.5 / (131.5 + api_g)
        water_sg_g = float(inputs.get('water_sg', 1.05))
        rho_w_g = water_sg_g * 62.4

        q_g_scf_d = q_gas_mmscfd * 1e6
        q_cond_stbd = q_gas_mmscfd * cgr_g
        q_wat_stbd = q_gas_mmscfd * wgr_g
        q_l_ft3s = ((q_cond_stbd + q_wat_stbd) * 5.615) / 86400.0

        total_liq_bbl = q_cond_stbd + q_wat_stbd
        if total_liq_bbl > 0:
            wc_frac_g = q_wat_stbd / total_liq_bbl
            rho_cond_g = 62.4 * gamma_o_g
            rho_l_g = (1.0 - wc_frac_g) * rho_cond_g + wc_frac_g * rho_w_g
        else:
            rho_l_g = 62.4 * gamma_o_g

        # Vectorized gas column; only the implicit DAK Z-factor solve stays per-point.
        depth_frac_g = tvd_array_g / tvd_gas if tvd_gas > 0 else np.zeros_like(tvd_array_g)
        p_psia_g = p_wh_g + (p_bhp_g - p_wh_g) * depth_frac_g + 14.7
        t_deg_r_g = t_wh_g + (t_bht_g - t_wh_g) * depth_frac_g + 459.67

        z_arr_g = np.array([
            compute_dynamic_z_factor(p, t, gas_sg_g) for p, t in zip(p_psia_g, t_deg_r_g)
        ])
        rho_g_arr_g = (2.7 * gas_sg_g * p_psia_g) / (z_arr_g * t_deg_r_g)
        q_g_ft3s_arr = (q_g_scf_d * 14.7 * t_deg_r_g * z_arr_g) / (p_psia_g * 520.0 * 86400.0)
        q_m_ft3s_arr = q_l_ft3s + q_g_ft3s_arr
        lambda_l_arr = np.where(q_m_ft3s_arr > 0, q_l_ft3s / q_m_ft3s_arr, 0.0)
        rho_m_arr = lambda_l_arr * rho_l_g + (1.0 - lambda_l_arr) * rho_g_arr_g

        df_gas_pvt = pd.DataFrame({
            'TVD_ft': tvd_array_g,
            'Z_Factor': z_arr_g,
            'rho_g': rho_g_arr_g,
            'q_g_ft3s': q_g_ft3s_arr,
            'lambda_l': lambda_l_arr,
            'rho_m': rho_m_arr
        })

        # -------------------------------------------------------------------------
        # FOCUSED PLOTLY CHART (CHART B: DOWNHOLE RATE & MIXTURE DENSITY)
        # -------------------------------------------------------------------------
        fig_gas_b = go.Figure()
        fig_gas_b.add_trace(go.Scatter(
            x=df_gas_pvt['rho_m'], y=df_gas_pvt['TVD_ft'],
            mode='lines+markers', name='Multiphase Mixture Density (ρ_m, lb/ft³)',
            line=dict(color='#1E3A8A', width=3),
            hovertemplate='Depth: %{y:.1f} ft<br>ρ_m: %{x:.2f} lb/ft³<extra></extra>'
        ))
        fig_gas_b.add_trace(go.Scatter(
            x=df_gas_pvt['q_g_ft3s'], y=df_gas_pvt['TVD_ft'],
            mode='lines', name='Downhole Volumetric Gas Rate (q_g, ft³/s)',
            line=dict(color='#7C3AED', width=2.5, dash='dash'),
            xaxis='x2',
            hovertemplate='Depth: %{y:.1f} ft<br>q_g: %{x:.3f} ft³/s<extra></extra>'
        ))
        fig_gas_b.update_layout(
            title=r'Downhole Gas Rate ($q_g$) & Homogeneous Mixture Density ($\rho_m$) vs. Depth',
            xaxis=dict(title='Multiphase Mixture Density ρ_m (lb/ft³)', title_font=dict(color='#1E3A8A')),
            xaxis2=dict(
                title='Downhole Gas Volumetric Rate q_g (ft³/s)',
                title_font=dict(color='#7C3AED'),
                overlaying='x', side='top'
            ),
            yaxis=dict(title='True Vertical Depth - TVD (ft)', autorange='reversed'),
            height=500,
            margin=dict(l=60, r=60, t=80, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
            hovermode="y unified"
        )
        st.plotly_chart(fig_gas_b, use_container_width=True)

        # -------------------------------------------------------------------------
        # PHYSICAL INTERPRETATION & THERMODYNAMIC ANALYSIS CARD
        # -------------------------------------------------------------------------
        st.markdown(
            """
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 5px solid #2563EB; border-radius: 8px; padding: 1.1rem; margin-top: 0.5rem;">
            <h4 style="color: #1E40AF; margin-top: 0; margin-bottom: 0.5rem; font-size: 1.05rem;">💡 Engineering Interpretation: Gas Expansion vs. Mixture Density Decay</h4>
            <p style="font-size: 0.89rem; color: #1E293B; line-height: 1.6; margin-bottom: 0.5rem;">
                As produced gas travels upward from bottomhole (<i>P</i><sub>bhp</sub>) to wellhead (<i>P</i><sub>wh</sub>), the overburden pressure drops significantly. According to the Real Gas Law (<i>P</i> · <i>V</i> = <i>n</i> · <i>Z</i> · <i>R</i> · <i>T</i>):
            </p>
            <ul style="font-size: 0.87rem; color: #334155; line-height: 1.55; margin-bottom: 0;">
                <li><b>Volumetric Gas Expansion (<i>q</i><sub>g</sub> ↑):</b> Lower pressure shallow in the wellbore allows gas molecules to decompress and expand. The volumetric flow rate (<i>q</i><sub>g</sub>) increases drastically as the fluid approaches the surface, driving higher actual fluid velocities.</li>
                <li><b>Density Reduction (ρ<sub>g</sub> ↓ & ρ<sub>m</sub> ↓):</b> Because the same mass of gas now occupies a significantly larger volume (<i>q</i><sub>g</sub>), in-situ gas density (ρ<sub>g</sub>) drops sharply toward the surface.</li>
                <li><b>Liquid Holdup Influence (λ<sub>l</sub>):</b> Lower mixture density (ρ<sub>m</sub>) near the surface reduces hydrostatic head pressure losses. However, if condensate (CGR) or water (WGR) is present, the dense liquid phase exerts a stronger weighting on ρ<sub>m</sub> = λ<sub>l</sub> · ρ<sub>l</sub> + (1 - λ<sub>l</sub>) · ρ<sub>g</sub>, keeping ρ<sub>m</sub> higher than pure gas density.</li>
            </ul>
        </div>
        """,
            unsafe_allow_html=True,
        )

# -----------------------------------------------------------------------------
# PAGE 3: WELLBORE HYDRAULICS & VELOCITY LIMITS
# -----------------------------------------------------------------------------
elif page == "3. Wellbore Hydraulics & Velocity Limits":
    st.markdown('<div class="main-header">Step 3: Wellbore Hydraulics &amp; Velocity Limits</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Comprehensive velocity window screening, solid particle slurry physics, and dynamic pressure loss mechanics.</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs([
        "⏳ Tab 1: Solid Particle Slurry Physics & Operating Envelope",
        "📊 Tab 2: Total Slurry Wellbore Pressure Loss & Friction Mechanics"
    ])

    # =========================================================================
    # TAB 1: SOLID PARTICLE SLURRY PHYSICS
    # =========================================================================
    with tab1:
        st.markdown("### 🧪 Solid Particle Slurry Integration & Physics Mechanics")

        # Introduction to Solid Particles
        st.markdown("""
        <div class="m2-purpose" style="margin-bottom: 1.2rem;">
            <b>What are solid particles, and where do they come from?</b><br/>
            In oil and gas production, solid particles primarily consist of <b>formation sand grains</b> (mostly quartz silica), <b>frac proppant flowback</b>, or <b>corrosion scale</b>.
            They originate from weakly consolidated rock formations surrounding the wellbore that break down as reservoir fluids flow into the well.
            When these heavy, abrasive particles get carried up the tubing, they transform clean fluid into a <b>slurry mixture</b> that alters fluid density and causes aggressive pipe wear.
        </div>
        """, unsafe_allow_html=True)

        # Simplified Callout Cards (Page 6 Style)
        st.markdown("""
        <div class="m2-card">
            <div class="m2-card-head">
                <span class="m2-card-num">CALLOUT 1</span>
                <h4 class="m2-card-title" style="color: #1E3A8A;">Heavy Fluid Column & Pressure Drop Inflation (ΔP_hydrostatic)</h4>
            </div>
            <div class="m2-label">How solid particles affect this</div>
            <div class="m2-purpose">
                Sand is much heavier than oil, water, or gas. When sand particles mix into the production stream, they increase the total weight of the fluid column.
                This heavier column pushes down harder on the reservoir, requiring higher reservoir pressure just to lift the fluid to surface.
            </div>
        </div>

        <div class="m2-card">
            <div class="m2-card-head">
                <span class="m2-card-num">CALLOUT 2</span>
                <h4 class="m2-card-title" style="color: #991B1B;">Erosion Velocity Boundary Suppression (v_erosional)</h4>
            </div>
            <div class="m2-label">How solid particles affect this</div>
            <div class="m2-gate">
                At high speeds, sand grains act like tiny sandblasters against the inside of the metal tubing.
                Because sand causes severe physical erosion, fluid must travel at much lower speeds to protect the pipe walls from washing out prematurely.
            </div>
        </div>

        <div class="m2-card">
            <div class="m2-card-head">
                <span class="m2-card-num">CALLOUT 3</span>
                <h4 class="m2-card-title" style="color: #D97706;">Sand Fallout & Tubing Blockage Risk (v_carrying)</h4>
            </div>
            <div class="m2-label">How solid particles affect this</div>
            <div class="m2-purpose" style="border-left-color: #D97706;">
                Because sand is dense, gravity constantly tries to pull the grains downward.
                If the produced fluid flows too slowly, sand grains drop out of the stream, accumulate at the bottom of the well, and form sand dunes that choke off fluid flow completely.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🎛️ Interactive Slurry Physics Sandbox")
        st.caption("Adjust sand production parameters below to explore real-time shifts in the operating velocity window.")

        # Determine candidate with largest operable velocity window
        q_liq_ref = float(st.session_state.inputs.get('q_liquid', 5000.0))
        sb_d_i, is_cra = widest_window_candidate(
            st.session_state.tubing_db.to_json(orient='split'), q_liq_ref
        )

        col_sb1, col_sb2 = st.columns([1, 1.2])

        with col_sb1:
            st.markdown("##### ⚙️ Sandbox Input Parameters")
            sb_sand_pptb = st.slider("Sand Concentration (PPTB - lbs/1000 bbl)", 0.0, 500.0, 25.0, 5.0)
            st.caption("💡 *Higher concentration increases mixture density (ρ_slurry) and lowers the upper erosion ceiling (v_erosional).*")

            sb_sand_d_um = st.slider("Grain Diameter (d_p - microns)", 10.0, 1000.0, 150.0, 10.0)
            st.caption("💡 *Larger particles settle faster due to gravity, raising the required minimum carrying velocity (v_carrying).*")

            sb_sand_sg = st.slider("Grain Density (SG_s)", 1.5, 4.5, 2.65, 0.05)
            st.caption("💡 *Denser minerals increase hydrostatic pressure drop (ΔP_hydrostatic) and accelerate sand fallout.*")

            slurry_res = calculate_slurry_physics(q_liq_ref, sb_sand_pptb, sb_sand_sg, sb_sand_d_um, 52.0, 1.5, sb_d_i, is_cra)

        with col_sb2:
            st.markdown("##### 📊 Real-Time Dynamic Metrics")
            m_col1, m_col2 = st.columns(2)
            m_col1.metric("Solids Vol. Fraction (C_v)", f"{slurry_res['c_v']*100:.4f} %")
            m_col2.metric("Slurry Density (ρ_slurry)", f"{slurry_res['rho_slurry']:.2f} lb/ft³")

            m_col3, m_col4 = st.columns(2)
            m_col3.metric("Salama Erosional Limit (v_erosional)", f"{slurry_res['v_erosional']:.2f} ft/s")
            m_col4.metric("Rubey Carrying Limit (1.35 v_t)", f"{1.35 * slurry_res['v_t_rubey']:.2f} ft/s")

            m_col5, m_col6 = st.columns(2)
            m_col5.metric("Turner Liquid Lift Limit (v_turner)", f"{slurry_res['v_turner']:.2f} ft/s")
            m_col6.metric("Governing Min Velocity (v_carrying)", f"{slurry_res['v_carrying']:.2f} ft/s")

        st.markdown("---")
        st.markdown("#### 📈 Operating Envelope Compression vs. Sand Concentration")

        pptb_range = np.linspace(0.1, 500.0, 100)
        # One vectorized call across the whole sand-concentration sweep; this used to be
        # 100 scalar calls rebuilt on every slider drag.
        sweep = calculate_slurry_physics(q_liq_ref, pptb_range, sb_sand_sg, sb_sand_d_um, 52.0, 1.5, sb_d_i, is_cra)
        v_eros_list = sweep['v_erosional']
        v_carrying_list = sweep['v_carrying']
        v_rubey_list = 1.35 * sweep['v_t_rubey']
        v_turner_list = np.full_like(pptb_range, sweep['v_turner'])

        fig_env = go.Figure()
        fig_env.add_trace(go.Scatter(x=pptb_range, y=v_eros_list, mode='lines', name='Salama Sand Erosion Limit (v_erosional)', line=dict(color='#DC2626', width=3)))
        fig_env.add_trace(go.Scatter(x=pptb_range, y=v_carrying_list, mode='lines', name='Governing Carrying Limit (v_carrying)', line=dict(color='#059669', width=3)))
        fig_env.add_trace(go.Scatter(x=pptb_range, y=v_rubey_list, mode='lines', name='Rubey Solid Settling (1.35 v_t)', line=dict(color='#D97706', dash='dash')))
        fig_env.add_trace(go.Scatter(x=pptb_range, y=v_turner_list, mode='lines', name='Turner Droplet Lift Limit (v_turner)', line=dict(color='#2563EB', dash='dot')))
        fig_env.add_trace(go.Scatter(
            x=np.concatenate([pptb_range, pptb_range[::-1]]),
            y=np.concatenate([v_eros_list, v_carrying_list[::-1]]),
            fill='toself', fillcolor='rgba(59, 130, 246, 0.12)', line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip", name='Operable Velocity Window'
        ))

        fig_env.update_layout(
            title="Operating Envelope Squeeze vs. Sand Concentration",
            xaxis_title="Sand Production Concentration (PPTB - lbs / 1000 bbl)",
            yaxis_title="Flow Velocity Limits (ft/s)",
            hovermode="x unified", margin=dict(t=50, b=40, l=40, r=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_env, use_container_width=True)

        # =========================================================================
    # TAB 2: TOTAL SLURRY WELLBORE PRESSURE LOSS & FRICTION MECHANICS
    # =========================================================================
    with tab2:
        st.markdown("### 📊 Total Slurry Pressure Drop (ΔP_total) & Hydraulics Sandbox")

        # Explanation of Pressure Drop in Tubing Selection
        st.markdown("""
        <div class="m2-purpose" style="margin-bottom: 1.2rem;">
            <b>How does pressure drop (ΔP_total) govern tubing selection?</b><br/>
            Selecting the optimal tubing inner diameter (ID) requires balancing fluid velocity against total pressure drop:
            <ul>
                <li><b>Small Tubing ID:</b> Boosts fluid velocity above critical carrying limits (v_carrying) to prevent sand settling, but drastically spikes frictional pressure loss (ΔP_fric ∝ 1/d_i^5). If ΔP_total exceeds available drawdown (ΔP_available = P_bhp - P_wh), the well stops flowing naturally.</li>
                <li><b>Large Tubing ID:</b> Minimizes wall friction and pressure loss, preserving reservoir pressure. However, fluid velocity may drop below v_carrying, triggering sand fallout, liquid loading, and severe wellbore choking.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Unified Interactive Sandbox & Control Panel
        st.markdown("#### 🎛️ Interactive Hydraulics & Regime Sandbox")
        st.caption("Adjust flow rates, fluid properties, slurry density, and well depths below. All dynamic metrics and sensitivity plots update in real time.")

        col_t2_ctrl1, col_t2_ctrl2 = st.columns([1, 1])

        with col_t2_ctrl1:
            st.markdown("##### ⚙️ Production & Depth Controls")
            t2_q_liq = st.slider("Liquid Flow Rate (Q_liq - STB/D)", 500.0, 20000.0, 5000.0, 500.0)
            t2_rho_slurry_override = st.slider("Slurry Mixture Density (ρ_slurry - lb/ft³)", 45.0, 90.0, 55.0, 1.0)
            t2_id = st.slider("Tubing Inner Diameter (d_i - in)", 1.500, 6.000, 2.992, 0.050)
            t2_tvd = st.slider("True Vertical Depth (TVD - ft)", 1000.0, 25000.0, float(st.session_state.inputs.get('tvd', 10000.0)), 500.0)

        with col_t2_ctrl2:
            st.markdown("##### 🛠️ Fluid & Trajectory Drag Controls")
            t2_md = st.slider("Measured Depth / Trajectory (MD/VD - ft)", t2_tvd, t2_tvd * 1.5, max(float(st.session_state.inputs.get('md', 11500.0)), t2_tvd), 500.0)
            t2_roughness = st.slider("Pipe Absolute Roughness (ε - in)", 0.0001, 0.0050, 0.0006, 0.0001, format="%.4f")
            t2_visc = st.slider("Fluid Viscosity (μ_m - cP)", 0.5, 20.0, 1.5, 0.5)

        # Core Hydraulic Calculations (Using Sandbox Slurry Density Input)
        rho_slurry_val = t2_rho_slurry_override

        d_i_ft = t2_id / 12.0
        area_ft2 = (np.pi / 4.0) * (d_i_ft ** 2)
        q_m_ft3s = (t2_q_liq * 5.615) / 86400.0
        v_m_val = q_m_ft3s / area_ft2

        mu_lbfts = t2_visc * 0.000672
        re_slurry = (rho_slurry_val * v_m_val * d_i_ft) / mu_lbfts if mu_lbfts > 0 else 10000.0
        rel_roughness = t2_roughness / t2_id

        # Haaland explicit friction factor (no iteration required).
        if re_slurry <= 2100:
            regime_str = "Laminar Flow"
            f_factor = 64.0 / re_slurry if re_slurry > 0 else 0.04
        elif re_slurry > 4000:
            regime_str = "Turbulent Flow"
            f_factor = haaland_friction_factor(re_slurry, rel_roughness)
        else:
            regime_str = "Transitional Flow"
            f_lam = 64.0 / 2100.0
            f_turb = haaland_friction_factor(4000.0, rel_roughness)
            f_factor = f_lam + (f_turb - f_lam) * ((re_slurry - 2100.0) / 1900.0)

        # Pressure Drops
        dp_hydro_val = (rho_slurry_val * t2_tvd) / 144.0
        dp_fric_val = (f_factor * t2_md * rho_slurry_val * (v_m_val ** 2)) / (2.0 * 32.174 * d_i_ft * 144.0)
        dp_total_val = dp_hydro_val + dp_fric_val

        st.markdown("---")
        col_m_disp, col_regime_disp = st.columns([1.1, 1.1])

        # Dynamic Hydraulics Metrics Output
        with col_m_disp:
            st.markdown("##### 📊 Live Dynamic Hydraulics Output")
            rm_col1, rm_col2 = st.columns(2)
            rm_col1.metric("Slurry Reynolds No. (Re_slurry)", f"{re_slurry:,.0f}")
            rm_col2.metric("Flow Regime", regime_str)

            rm_col3, rm_col4 = st.columns(2)
            rm_col3.metric("Friction Factor (f)", f"{f_factor:.5f}")
            rm_col4.metric("Flow Velocity (v_m)", f"{v_m_val:.2f} ft/s")

            rm_col5, rm_col6 = st.columns(2)
            rm_col5.metric("Hydrostatic Loss (ΔP_hydro)", f"{dp_hydro_val:.1f} psi")
            rm_col6.metric("Frictional Loss (ΔP_fric)", f"{dp_fric_val:.1f} psi")

            st.metric("Total Slurry Pressure Loss (ΔP_total)", f"{dp_total_val:.1f} psi")

        # Dynamic Flow Regime Visualizer
        with col_regime_disp:
            st.markdown("##### 🌊 Dynamic Flow Regime Visualizer")

            re_tier = int(re_slurry // 5000)

            if re_slurry <= 2100:
                arrow_color = "#2563EB"
                anim_speed = "7.0s"
                regime_badge = "Laminar Flow (Re ≤ 2,100)"
                flow_desc = "Smooth, parallel fluid streamlines with zero inter-layer mixing."
            elif re_slurry <= 4000:
                arrow_color = "#D97706"
                anim_speed = "4.4s"
                regime_badge = "Transitional Flow (2,100 < Re ≤ 4,000)"
                flow_desc = "Unstable flow transition with emerging eddy currents."
            elif re_tier == 0:
                arrow_color = "#E11D48"
                anim_speed = "3.0s"
                regime_badge = "Turbulent Flow (Re: 4,000 - 5,000)"
                flow_desc = "Low-range turbulent eddies and wall shear stress."
            elif re_tier == 1:
                arrow_color = "#DC2626"
                anim_speed = "2.2s"
                regime_badge = "Turbulent Flow (Re: 5,000 - 10,000)"
                flow_desc = "Moderate turbulence with increased kinetic dissipation."
            elif re_tier == 2:
                arrow_color = "#B91C1C"
                anim_speed = "1.6s"
                regime_badge = "Turbulent Flow (Re: 10,000 - 15,000)"
                flow_desc = "High turbulence with steep frictional pressure loss spikes."
            elif re_tier == 3:
                arrow_color = "#991B1B"
                anim_speed = "1.0s"
                regime_badge = "Turbulent Flow (Re: 15,000 - 20,000)"
                flow_desc = "Severe turbulent shear and heavy internal energy loss."
            else:
                arrow_color = "#7F1D1D"
                anim_speed = "0.6s"
                regime_badge = f"Fully Rough Turbulent Flow (Re > 20,000)"
                flow_desc = "Fully developed rough turbulent flow dominated by wall friction."

            animated_conduit_html = f"""
            <style>
            @keyframes flowArrow {{
                0% {{ transform: translateX(-40px); opacity: 0.2; }}
                50% {{ opacity: 1; }}
                100% {{ transform: translateX(240px); opacity: 0.2; }}
            }}
            .pipe-conduit {{
                width: 100%;
                height: 100px;
                background: #0F172A;
                border-top: 4px solid #64748B;
                border-bottom: 4px solid #64748B;
                border-radius: 8px;
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: space-around;
                padding: 10px 0;
                box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
            }}
            .arrow-stream {{
                display: flex;
                gap: 50px;
                animation: flowArrow {anim_speed} linear infinite;
            }}
            .arrow-item {{
                color: {arrow_color};
                font-size: 20px;
                font-weight: bold;
            }}
            </style>
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:0.82rem; font-weight:800; color:{arrow_color};">{regime_badge}</span>
                </div>
                <div class="pipe-conduit">
                    <div class="arrow-stream">
                        <span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span>
                    </div>
                    <div class="arrow-stream" style="animation-delay: -0.8s;">
                        <span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span>
                    </div>
                    <div class="arrow-stream" style="animation-delay: -1.6s;">
                        <span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span><span class="arrow-item">➔</span>
                    </div>
                </div>
                <p style="font-size:0.8rem; color:#475569; margin-top:8px; line-height:1.3;">{flow_desc}</p>
            </div>
            """
            st.markdown(animated_conduit_html, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📈 Real-Time Sandbox Visualizations")

        chart_tab1, chart_tab2 = st.tabs([
            "📉 Total Pressure Drop vs. Depth Profile",
            "📊 Continuous Hydrostatic vs. Frictional Loss Area Breakdown"
        ])

        # Plot 1: Total ΔP vs Depth driven directly by the sandbox's Slurry Density slider
        with chart_tab1:
            md_range = np.linspace(0.0, max(t2_md, 15000.0), 50)

            # Single dynamic line calculated directly from t2_rho_slurry_override
            re_p = (rho_slurry_val * v_m_val * d_i_ft) / mu_lbfts
            f_p = haaland_friction_factor(re_p, rel_roughness) if re_p > 4000 else 64.0 / re_p

            # Vectorized: the profile is linear in MD, so NumPy replaces the per-point loop.
            tvd_curve = md_range * (t2_tvd / t2_md) if t2_md > 0 else md_range
            dp_curve = (rho_slurry_val * tvd_curve) / 144.0 + (
                f_p * md_range * rho_slurry_val * (v_m_val ** 2)
            ) / (2.0 * 32.174 * d_i_ft * 144.0)

            fig_dp_md = go.Figure()
            fig_dp_md.add_trace(go.Scatter(
                x=dp_curve, y=md_range, mode='lines',
                name=f"Slurry Density: {rho_slurry_val:.1f} lb/ft³",
                line=dict(color='#1E3A8A', width=3)
            ))

            fig_dp_md.add_hline(y=t2_md, line_dash="dash", line_color="#0F172A", annotation_text=f"Current MD ({t2_md:.0f} ft)", annotation_position="bottom right")

            fig_dp_md.update_layout(
                title=f"Total Pressure Drop (ΔP_total) vs. Depth Profile (ρ_slurry: {rho_slurry_val:.1f} lb/ft³, ID: {t2_id:.3f}\")",
                xaxis_title="Total Pressure Drop (psi)",
                yaxis_title="Measured Depth / TVD (ft)",
                yaxis=dict(autorange="reversed"),
                hovermode="y unified", margin=dict(t=50, b=40, l=40, r=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_dp_md, use_container_width=True)

        # Plot 2: Continuous Stacked Area Plot across Tubing IDs
        with chart_tab2:
            id_continuous_range = np.linspace(1.5, 6.0, 100)

            # Vectorized sweep across the ID range; np.where keeps the laminar branch.
            d_ft_arr = id_continuous_range / 12.0
            v_m_c_arr = q_m_ft3s / ((np.pi / 4.0) * d_ft_arr ** 2)
            re_c_arr = (rho_slurry_val * v_m_c_arr * d_ft_arr) / mu_lbfts
            rel_r_c_arr = t2_roughness / id_continuous_range
            f_c_arr = np.where(
                re_c_arr <= 2100,
                64.0 / re_c_arr,
                haaland_friction_factor(re_c_arr, rel_r_c_arr),
            )
            dp_hydro_cont = np.full_like(id_continuous_range, (rho_slurry_val * t2_tvd) / 144.0)
            dp_fric_cont = (f_c_arr * t2_md * rho_slurry_val * v_m_c_arr ** 2) / (
                2.0 * 32.174 * d_ft_arr * 144.0
            )

            fig_area = go.Figure()

            # Hydrostatic Loss Layer
            fig_area.add_trace(go.Scatter(
                x=id_continuous_range, y=dp_hydro_cont,
                mode='lines', name='Hydrostatic Loss (ΔP_hydro)',
                stackgroup='one',
                line=dict(color='#1E3A8A', width=2),
                fillcolor='rgba(30, 58, 138, 0.65)'
            ))

            # Frictional Loss Layer
            fig_area.add_trace(go.Scatter(
                x=id_continuous_range, y=dp_fric_cont,
                mode='lines', name='Frictional Loss (ΔP_fric)',
                stackgroup='one',
                line=dict(color='#DC2626', width=2),
                fillcolor='rgba(220, 38, 38, 0.65)'
            ))

            fig_area.update_layout(
                title=f"Continuous Pressure Loss Breakdown vs. Tubing Inner Diameter (ρ_slurry: {rho_slurry_val:.1f} lb/ft³, TVD: {t2_tvd:.0f} ft)",
                xaxis_title="Tubing Inner Diameter (d_i - in)",
                yaxis_title="Pressure Drop (psi)",
                hovermode="x unified",
                margin=dict(t=50, b=40, l=40, r=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_area, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 4: TUBING STRESS & STRUCTURAL LOAD ANALYSIS
# -----------------------------------------------------------------------------
elif page == "4. Tubing Stress Analysis":
    st.markdown('<div class="main-header">Step 4: Tubing Stress & Structural Load Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Comprehensive tubing load balance, trapped APB, Lamé stress distributions, shut-in burst, NACE sour service, and connection selection.</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📊 Tab 1: Real-Time Structural Analysis & APB Balance",
        "🔬 Tab 2: Advanced Stress Distribution & API TR 5C3 Limit States",
        "🛡️ Tab 3: Environmental Integrity, Shut-In Burst & Connection Logic"
    ])

    # =========================================================================
    # TAB 1: REAL-TIME STRUCTURAL ANALYSIS & APB BALANCE
    # =========================================================================
    with tab1:
        st.markdown("""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid #1E3A8A; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.5rem;">
            <h4 style="color: #1E3A8A; margin-top: 0; margin-bottom: 0.5rem; font-weight: 700;">📘 Engineering Context & Stress Analysis Principles</h4>
            <p style="font-size: 0.9rem; color: #334155; line-height: 1.6; margin-bottom: 0.5rem;">
                When a tubing string is locked into a production packer, changes in temperature, internal pressure, and fluid motion induce severe mechanical loads along the pipe body.
                This module evaluates <b>Lubinski's 5 Net Axial Forces</b> (Gravity, Restrained Thermal Expansion, Packer Piston End-Load, Radial Ballooning, and Fluid Drag)
                alongside <b>Trapped Annular Pressure Build-up (APB)</b>.
            </p>
            <p style="font-size: 0.9rem; color: #334155; line-height: 1.6; margin: 0;">
                <b>Failure Envelope Gates:</b> String integrity fails if total axial force exceeds the pipe body yield strength (|F_axial| > SMYS * A_steel)
                or if the trapped APB rise exceeds the Maximum Allowable Annular Surface Pressure (ΔP_APB > MAASP_collapse).
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_input, col_viz = st.columns([1.05, 1.35], gap="medium")

        with col_input:
            st.markdown("### 🛠️ 1. Tubing Specification Controls")

            db_candidates = st.session_state.tubing_db['Name'].tolist() if 'tubing_db' in st.session_state else []
            options = ["Custom Input"] + db_candidates
            selected_cand = st.selectbox("Select Candidate / Input Mode:", options, index=1 if len(options) > 1 else 0, key="t1_cand_select")

            if selected_cand != "Custom Input" and 'tubing_db' in st.session_state:
                row = st.session_state.tubing_db[st.session_state.tubing_db['Name'] == selected_cand].iloc[0]
                default_od = float(row['OD_in'])
                default_id = float(row['ID_in'])
                default_wt = float(row['Weight_lbft'])
                default_yield = float(row['Yield_psi'])
                default_burst = float(row['Burst_psi'])
            else:
                default_od = 3.500
                default_id = 2.992
                default_wt = 9.20
                default_yield = 80000.0
                default_burst = 10160.0

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                od_in = st.number_input("Outer Diameter - OD (in)", min_value=1.0, max_value=12.0, value=default_od, step=0.125, format="%.3f", key="t1_od")
                id_in = st.number_input("Inner Diameter - ID (in)", min_value=0.5, max_value=11.0, value=default_id, step=0.125, format="%.3f", key="t1_id")
                weight_lbft = st.number_input("Nominal Weight (lb/ft)", min_value=1.0, max_value=100.0, value=default_wt, step=0.1, format="%.2f", key="t1_wt")
            with col_t2:
                yield_psi = st.number_input("Yield Strength - SMYS (psi)", min_value=30000.0, max_value=180000.0, value=default_yield, step=5000.0, format="%.0f", key="t1_ys")
                collapse_rating_psi = st.number_input("Tubing Collapse Rating (psi)", min_value=1000.0, max_value=25000.0, value=default_burst * 0.85, step=500.0, format="%.0f", key="t1_col")
                sf_collapse = st.number_input("Collapse Safety Factor", min_value=0.8, max_value=2.0, value=1.0, step=0.05, format="%.2f", key="t1_sf")

            st.markdown("---")
            st.markdown("### ⚡ 2. Dynamic Operational Inputs (Sliders)")

            inputs = st.session_state.get('inputs', {})
            tvd_val = float(inputs.get('tvd', 10000.0))
            p_bhp_val = float(inputs.get('p_bhp', 4500.0))

            f_overpull = st.slider("Applied Overpull / Tension Force (lbs)", min_value=0, max_value=200000, value=15000, step=5000, key="t1_overpull")
            delta_t_annular_f = st.slider("Annular Thermal Rise ΔT (°F)", min_value=0.0, max_value=250.0, value=75.0, step=5.0, key="t1_dt")
            p_bhp_slider = st.slider("Bottomhole Pressure P_bhp (psi)", min_value=500.0, max_value=15000.0, value=p_bhp_val, step=250.0, key="t1_pbhp")
            packer_depth_ft = st.slider("Packer Setting TVD Depth (ft)", min_value=1000.0, max_value=25000.0, value=tvd_val, step=500.0, key="t1_packer_tvd")
            annular_mw_ppg = st.slider("Annular Fluid Density (ppg)", min_value=8.33, max_value=18.0, value=9.5, step=0.1, key="t1_mw")

        # Computations Tab 1
        area_steel_in2 = (np.pi / 4.0) * (od_in**2 - id_in**2)
        area_id_ft2 = (np.pi / 4.0) * ((id_in / 12.0)**2)
        area_od_ft2 = (np.pi / 4.0) * ((od_in / 12.0)**2)
        pipe_tensile_rating_lbs = yield_psi * area_steel_in2

        alpha_v = 2.1e-4
        kappa_t = 3.0e-6
        delta_t_c = delta_t_annular_f * (5.0 / 9.0)
        dp_apb_psi = (alpha_v / kappa_t) * delta_t_c

        annular_gradient_psi_ft = 0.052 * annular_mw_ppg
        maasp_psi = (collapse_rating_psi / sf_collapse) - (packer_depth_ft * annular_gradient_psi_ft)
        maasp_psi = max(maasp_psi, 0.0)

        rho_slurry_lbft3 = annular_mw_ppg * 7.48052
        f_gravity_lbs = weight_lbft * packer_depth_ft * (1.0 - (rho_slurry_lbft3 / 490.0))
        f_thermal_lbs = 30e6 * area_steel_in2 * 6.9e-6 * delta_t_annular_f

        p_annular_total = (packer_depth_ft * annular_gradient_psi_ft) + dp_apb_psi
        f_piston_lbs = (p_bhp_slider * area_id_ft2 * 144.0) - (p_annular_total * (area_od_ft2 - area_id_ft2) * 144.0)
        f_ballooning_lbs = 2.0 * 0.3 * ((p_bhp_slider * area_id_ft2 * 144.0) - (p_annular_total * area_od_ft2 * 144.0))
        f_drag_lbs = 2500.0

        f_axial_net_lbs = f_gravity_lbs + f_thermal_lbs + f_piston_lbs + f_ballooning_lbs + f_drag_lbs + f_overpull

        apb_failed = dp_apb_psi > maasp_psi
        axial_failed = abs(f_axial_net_lbs) > pipe_tensile_rating_lbs
        string_failed = apb_failed or axial_failed

        with col_viz:
            st.markdown("### 📊 3. Structural Integrity Visualizer")

            if string_failed:
                failure_reasons = []
                if apb_failed:
                    failure_reasons.append(f"• APB Rise ({dp_apb_psi:.1f} psi) > Tubing Collapse MAASP ({maasp_psi:.1f} psi) [COLLAPSE RISK]")
                if axial_failed:
                    failure_reasons.append(f"• Net Axial Load ({f_axial_net_lbs/1000:.1f} klbs) > Tensile Rating ({pipe_tensile_rating_lbs/1000:.1f} klbs) [STRING BROKEN / YIELDED]")

                st.error("🔴 **STRING FAILURE / BUCKLED / PIPE BROKEN**\n\n" + "\n".join(failure_reasons))
            else:
                st.success("🟢 **STRING OK / STABLE OPERATING ENVELOPE**\n\nNet Axial Tension and Annular Pressure Build-Up are within allowable design limits.")

            fig = go.Figure()
            main_color = "#DC2626" if string_failed else "#2563EB"
            fill_color = "rgba(220, 38, 38, 0.15)" if string_failed else "rgba(37, 99, 235, 0.15)"
            line_style = "dash" if string_failed else "solid"

            fig.add_trace(go.Scatter(x=[-5, -5, -4.5, -4.5], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor='#94A3B8', line=dict(color='#475569'), name='Outer Casing Wall', hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=[5, 5, 4.5, 4.5], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor='#94A3B8', line=dict(color='#475569'), name='Outer Casing Wall', showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=[-4.5, -4.5, -2, -2], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor='rgba(234, 179, 8, 0.25)', line=dict(width=0), name='Trapped APB Zone'))
            fig.add_trace(go.Scatter(x=[4.5, 4.5, 2, 2], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor='rgba(234, 179, 8, 0.25)', line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=[-2, -2, -1.5, -1.5], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor=fill_color, line=dict(color=main_color, width=2.5, dash=line_style), name='Tubing Wall'))
            fig.add_trace(go.Scatter(x=[2, 2, 1.5, 1.5], y=[0, -packer_depth_ft, -packer_depth_ft, 0], fill='toself', fillcolor=fill_color, line=dict(color=main_color, width=2.5, dash=line_style), showlegend=False))
            fig.add_trace(go.Scatter(x=[-4.5, -1.5, -1.5, -4.5], y=[-packer_depth_ft*0.95, -packer_depth_ft*0.95, -packer_depth_ft, -packer_depth_ft], fill='toself', fillcolor='#1E293B', line=dict(color='#0F172A'), name='Production Packer'))
            fig.add_trace(go.Scatter(x=[4.5, 1.5, 1.5, 4.5], y=[-packer_depth_ft*0.95, -packer_depth_ft*0.95, -packer_depth_ft, -packer_depth_ft], fill='toself', fillcolor='#1E293B', line=dict(color='#0F172A'), showlegend=False))

            status_text = "❌ FAILED / BUCKLED" if string_failed else "✅ STRING SAFE"
            fig.add_annotation(
                x=0, y=-packer_depth_ft * 0.5,
                text=f"<b>{status_text}</b><br>Net Axial Load = {f_axial_net_lbs/1000:.1f} klbs<br>APB Rise = {dp_apb_psi:.1f} psi",
                showarrow=False,
                font=dict(size=14, color=main_color),
                bgcolor="white",
                bordercolor=main_color,
                borderwidth=2,
                opacity=0.9
            )

            fig.update_layout(
                title="Dynamic Tubing & Wellbore Stress Profile",
                xaxis=dict(range=[-7, 7], visible=False),
                yaxis=dict(title="True Vertical Depth - TVD (ft)", range=[-packer_depth_ft * 1.08, 200]),
                height=500,
                margin=dict(l=40, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📈 Metric Summary")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Net Axial Load", f"{f_axial_net_lbs/1000:.1f} klbs", help="Summation of all 5 Lubinski forces + Overpull")
        m2.metric("Pipe Yield Rating", f"{pipe_tensile_rating_lbs/1000:.1f} klbs", help="SMYS * Steel Area")
        m3.metric("APB Pressure Rise", f"{dp_apb_psi:.1f} psi", help="Thermal expansion of trapped annular fluid")
        m4.metric("Tubing MAASP", f"{maasp_psi:.1f} psi", help="Collapse Rating / SF - Annular Hydrostatic Head")
        m5.metric("Structural Status", "FAIL" if string_failed else "PASS", delta="-CRITICAL" if string_failed else "SAFE", delta_color="inverse" if string_failed else "normal")

    # =========================================================================
    # TAB 2: ADVANCED STRESS DISTRIBUTION & API TR 5C3 LIMIT STATES
    # =========================================================================
    with tab2:
        st.markdown("### 🔬 Advanced Triaxial Mechanics & API TR 5C3 Limit States")
        st.caption("Interactive analysis playground for Lamé thick-wall stress gradients, von Mises triaxial yield envelopes, ductile rupture, and external pressure collapse degradation.")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid #2563EB; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <h5 style="color: #1E3A8A; margin: 0 0 0.4rem 0; font-weight: 700;">1. Lamé Thick-Wall Component Stresses</h5>
                <p style="font-size: 0.85rem; color: #334155; line-height: 1.5; margin: 0;">
                    <b>Purpose:</b> Calculates exact radial (σ_r), hoop (σ_θ), and axial (σ_z) stress distributions across thick pipe walls (r_in → r_out).
                    <br><b>Why it matters:</b> Simple thin-wall assumptions underestimate peak hoop stress at the inner bore by up to 15-20% in standard OCTG geometries.
                </p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid #059669; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <h5 style="color: #065F46; margin: 0 0 0.4rem 0; font-weight: 700;">3. Ductile Rupture (API TR 5C3 Cl. 7)</h5>
                <p style="font-size: 0.85rem; color: #334155; line-height: 1.5; margin: 0;">
                    <b>Purpose:</b> Predicts ultimate plastic burst rupture capacity considering wall thickness tolerances (k_wall = 0.875) and strain hardening (n).
                    <br><b>Why it matters:</b> Represents the true ultimate burst limit state under high pressure, far beyond initial elastic yielding.
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col_m2:
            st.markdown("""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid #D97706; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <h5 style="color: #92400E; margin: 0 0 0.4rem 0; font-weight: 700;">2. von Mises Triaxial Yield (API TR 5C3 Cl. 6)</h5>
                <p style="font-size: 0.85rem; color: #334155; line-height: 1.5; margin: 0;">
                    <b>Purpose:</b> Evaluates total distortion strain energy under simultaneous axial, bending, internal/external pressure, and torsional loads.
                    <br><b>Why it matters:</b> Steel deforms permanently when equivalent stress exceeds yield strength (SMYS), forming the fundamental 3D safety envelope.
                </p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid #DC2626; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <h5 style="color: #991B1B; margin: 0 0 0.4rem 0; font-weight: 700;">4. External Pressure Collapse (API TR 5C3 Cl. 8)</h5>
                <p style="font-size: 0.85rem; color: #334155; line-height: 1.5; margin: 0;">
                    <b>Purpose:</b> Calculates pipe collapse resistance reduction caused by superimposed axial tension (Y_pa reduced yield equivalent).
                    <br><b>Why it matters:</b> Axial tension drastically reduces collapse resistance, accelerating pipe wall failure during severe APB events.
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 🎯 Guided 'What-If' Failure Presets")
        st.caption("Click any preset button below to automatically load scenario parameters into session state and examine real-time structural responses.")

        col_p1, col_p2, col_p3, col_p4 = st.columns(4)

        if col_p1.button("💥 Severe APB Collapse", use_container_width=True, key="preset_apb"):
            st.session_state.t2_pi = 500.0
            st.session_state.t2_pe = 9200.0
            st.session_state.t2_fa = 120.0
            st.session_state.t2_dls = 1.0
            st.session_state.t2_smys = 80000.0
            st.rerun()

        if col_p2.button("🐍 High Bending Deviated Well", use_container_width=True, key="preset_dev"):
            st.session_state.t2_pi = 4500.0
            st.session_state.t2_pe = 2000.0
            st.session_state.t2_fa = 180.0
            st.session_state.t2_dls = 8.5
            st.session_state.t2_smys = 80000.0
            st.rerun()

        if col_p3.button("🔥 High-Pressure Shut-In Burst", use_container_width=True, key="preset_burst"):
            st.session_state.t2_pi = 11500.0
            st.session_state.t2_pe = 1000.0
            st.session_state.t2_fa = 40.0
            st.session_state.t2_dls = 1.5
            st.session_state.t2_smys = 80000.0
            st.rerun()

        if col_p4.button("🔄 Reset to Baseline", use_container_width=True, key="preset_reset"):
            st.session_state.t2_pi = 3500.0
            st.session_state.t2_pe = 1500.0
            st.session_state.t2_fa = 65.0
            st.session_state.t2_dls = 2.0
            st.session_state.t2_smys = 80000.0
            st.rerun()

        if 't2_pi' not in st.session_state: st.session_state.t2_pi = 3500.0
        if 't2_pe' not in st.session_state: st.session_state.t2_pe = 1500.0
        if 't2_fa' not in st.session_state: st.session_state.t2_fa = 65.0
        if 't2_dls' not in st.session_state: st.session_state.t2_dls = 2.0
        if 't2_smys' not in st.session_state: st.session_state.t2_smys = 80000.0

        st.markdown("---")

        col_s1, col_s2 = st.columns([1, 1.2], gap="medium")

        with col_s1:
            st.markdown("##### 📐 Tubing Geometry & Material")
            t2_od = st.number_input("Outer Diameter - OD (in)", min_value=1.5, max_value=9.625, value=3.500, step=0.125, format="%.3f", key="t2_od_in")
            t2_id = st.number_input("Inner Diameter - ID (in)", min_value=1.0, max_value=8.535, value=2.992, step=0.125, format="%.3f", key="t2_id_in")
            t2_smys = st.number_input("Yield Strength - SMYS (psi)", min_value=30000.0, max_value=150000.0, value=float(st.session_state.t2_smys), step=5000.0, format="%.0f", key="t2_smys_in")
            t2_dls = st.slider("Dogleg Severity - DLS (°/100ft)", min_value=0.0, max_value=15.0, value=float(st.session_state.t2_dls), step=0.5, key="t2_dls_in")

        with col_s2:
            st.markdown("##### ⚡ Applied Operating Loads")
            t2_pi = st.slider("Internal Pressure P_i (psi)", min_value=0.0, max_value=15000.0, value=float(st.session_state.t2_pi), step=250.0, key="t2_pi_in")
            t2_pe = st.slider("External Pressure P_e (psi)", min_value=0.0, max_value=15000.0, value=float(st.session_state.t2_pe), step=250.0, key="t2_pe_in")
            t2_fa = st.slider("Net Axial Force F_a (klbs)", min_value=-100.0, max_value=300.0, value=float(st.session_state.t2_fa), step=5.0, key="t2_fa_in")

        st.session_state.t2_pi = t2_pi
        st.session_state.t2_pe = t2_pe
        st.session_state.t2_fa = t2_fa
        st.session_state.t2_dls = t2_dls
        st.session_state.t2_smys = t2_smys

        t2_wall_nom = (t2_od - t2_id) / 2.0
        t2_k_wall = 0.875
        t2_r_iw = (t2_od - 2.0 * t2_wall_nom * t2_k_wall) / 2.0
        t2_r_o = t2_od / 2.0

        t2_area_nom = (np.pi / 4.0) * (t2_od**2 - t2_id**2)
        t2_fa_lbs = t2_fa * 1000.0

        t2_beta = t2_dls * (np.pi / 180.0) * (1.0 / 1200.0)
        t2_sigma_bending = (30e6 * t2_od * t2_beta) / 2.0
        t2_sigma_z_outer = (t2_fa_lbs / t2_area_nom) + t2_sigma_bending

        r_points = np.linspace(t2_r_iw, t2_r_o, 50)

        # Lame thick-wall solution, evaluated across the wall in one array pass.
        # The mean and the r-dependent deviator are both constant in r apart from
        # the 1/r^2 factor, so they are hoisted out of the sweep.
        lame_mean = (t2_pi * t2_r_iw**2 - t2_pe * t2_r_o**2) / (t2_r_o**2 - t2_r_iw**2)
        lame_dev = ((t2_pi - t2_pe) * t2_r_iw**2 * t2_r_o**2) / (r_points**2 * (t2_r_o**2 - t2_r_iw**2))
        sigma_r_profile = lame_mean - lame_dev
        sigma_theta_profile = lame_mean + lame_dev
        s_z = t2_sigma_z_outer
        vme_profile = np.sqrt(0.5 * ((sigma_r_profile - sigma_theta_profile)**2
                                     + (sigma_theta_profile - s_z)**2
                                     + (s_z - sigma_r_profile)**2))

        vme_max_psi = vme_profile.max()
        triaxial_sf_t2 = t2_smys / vme_max_psi if vme_max_psi > 0 else 99.0

        st.markdown("---")
        col_c1, col_c2 = st.columns(2, gap="medium")

        with col_c1:
            st.markdown("##### 📈 Chart A: Lamé Wall Stress Profile (r_iw → r_o)")

            fig_lame = go.Figure()
            fig_lame.add_trace(go.Scatter(x=r_points, y=sigma_theta_profile, mode='lines', name='Hoop Stress (σ_θ)', line=dict(color='#2563EB', width=2.5)))
            fig_lame.add_trace(go.Scatter(x=r_points, y=sigma_r_profile, mode='lines', name='Radial Stress (σ_r)', line=dict(color='#D97706', width=2.5)))
            fig_lame.add_trace(go.Scatter(x=r_points, y=vme_profile, mode='lines', name='von Mises (σ_VME)', line=dict(color='#059669', width=2.5, dash='dash')))

            fig_lame.add_hline(y=t2_smys, line_dash="dot", line_color="red", annotation_text="SMYS Yield Limit", annotation_position="top left")

            fig_lame.update_layout(
                title="Stress Variation Across Pipe Wall Thickness",
                xaxis_title="Wall Radius (inches)",
                yaxis_title="Stress (psi)",
                height=420,
                margin=dict(l=40, r=20, t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_lame, use_container_width=True)

        with col_c2:
            st.markdown("##### 🎯 Chart B: von Mises Triaxial Yield Ellipse")

            dp_range = np.linspace(-12000, 12000, 100)

            # Vectorized yield envelope. Points where the von Mises quadratic has no
            # real root fall outside the envelope and stay NaN, which is what breaks
            # the plotted boundary exactly as the per-point version did.
            s_h_arr = (dp_range * (t2_od / 2.0)) / t2_wall_nom
            discriminant = s_h_arr**2 - 4.0 * (s_h_arr**2 - t2_smys**2)
            root = np.sqrt(np.where(discriminant >= 0, discriminant, np.nan))
            fa_upper_klbs = ((s_h_arr + root) / 2.0) * t2_area_nom / 1000.0
            fa_lower_klbs = ((s_h_arr - root) / 2.0) * t2_area_nom / 1000.0

            delta_p_current = t2_pi - t2_pe
            point_color = "#DC2626" if triaxial_sf_t2 < 1.25 else "#059669"

            fig_ellipse = go.Figure()
            fig_ellipse.add_trace(go.Scatter(x=dp_range, y=fa_upper_klbs, mode='lines', line=dict(color='#1E3A8A', width=2), name='Yield Envelope Boundary', showlegend=True))
            fig_ellipse.add_trace(go.Scatter(x=dp_range, y=fa_lower_klbs, mode='lines', line=dict(color='#1E3A8A', width=2), showlegend=False))

            fig_ellipse.add_trace(go.Scatter(
                x=[delta_p_current], y=[t2_fa],
                mode='markers+text',
                marker=dict(size=14, color=point_color, symbol='diamond'),
                text=[f"  SF = {triaxial_sf_t2:.2f}"],
                textposition="top right",
                name='Current Operating Point'
            ))

            fig_ellipse.update_layout(
                title="Triaxial Yield Envelope (Fa [klbs] vs ΔP [psi])",
                xaxis_title="Differential Pressure ΔP = Pi - Pe (psi)",
                yaxis_title="Net Axial Tension Force Fa (klbs)",
                height=420,
                margin=dict(l=40, r=20, t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_ellipse, use_container_width=True)

        st.markdown("---")
        m_t1, m_t2, m_t3, m_t4 = st.columns(4)
        m_t1.metric("Governing von Mises Stress", f"{vme_max_psi:.0f} psi")
        m_t2.metric("Triaxial Safety Factor", f"{triaxial_sf_t2:.2f}", delta="SF >= 1.25", delta_color="normal" if triaxial_sf_t2 >= 1.25 else "inverse")
        m_t3.metric("Bending Stress (DLS)", f"{t2_sigma_bending:.0f} psi")
        m_t4.metric("Triaxial Status", "PASS" if triaxial_sf_t2 >= 1.25 else "YIELD FAILURE", delta="-CRITICAL" if triaxial_sf_t2 < 1.25 else "SAFE", delta_color="inverse" if triaxial_sf_t2 < 1.25 else "normal")

# =========================================================================
    # TAB 3: SHUT-IN SURFACE CITHP BURST ANALYSIS
    # =========================================================================
    with tab3:
        st.markdown("### 🛡️ Static Shut-In Wellhead Pressure (CITHP) Analysis")
        st.caption("Interactive evaluation of static shut-in tubing head pressure via gas-column barometric equilibrium and surface burst safety margins.")

        # ---------------------------------------------------------------------
        # 1. CORE METHODOLOGY CARD
        # ---------------------------------------------------------------------
        st.markdown("""
        <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid #2563EB; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
            <h5 style="color: #1E3A8A; margin: 0 0 0.4rem 0; font-weight: 700;">📘 Static Shut-In CITHP & Surface Burst Principles</h5>
            <p style="font-size: 0.85rem; color: #334155; line-height: 1.5; margin: 0;">
                <b>Purpose:</b> Models static shut-in closed-in tubing head pressure (CITHP) using gas-column barometric equilibrium.<br>
                <b>Why it matters:</b> Dry gas columns exert minimal hydrostatic head, transferring nearly the full reservoir bottomhole pressure directly to surface equipment.
                The tubing string must maintain a minimum surface burst safety factor (<b>SF_burst ≥ 1.10</b>) and remain within the API 5CT hydrostatic proof-test limit.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Initialize defaults if not set in session state
        if 't3_pbhp' not in st.session_state: st.session_state.t3_pbhp = 4500.0
        if 't3_tvd' not in st.session_state: st.session_state.t3_tvd = 10000.0
        if 't3_sg' not in st.session_state: st.session_state.t3_sg = 0.65
        if 't3_grade' not in st.session_state: st.session_state.t3_grade = "L80-1"

        # ---------------------------------------------------------------------
        # 2. INTERACTIVE CONTROLS
        # ---------------------------------------------------------------------
        col_ctrl1, col_ctrl2 = st.columns(2, gap="medium")

        with col_ctrl1:
            st.markdown("##### ⚡ Reservoir & Gas Properties")
            t3_pbhp = st.slider("Bottomhole Pressure Pbhp (psi)", min_value=1000.0, max_value=15000.0, value=float(st.session_state.t3_pbhp), step=250.0, key="t3_pbhp_slider")
            t3_tvd = st.slider("True Vertical Depth TVD (ft)", min_value=2000.0, max_value=25000.0, value=float(st.session_state.t3_tvd), step=500.0, key="t3_tvd_slider")
            t3_sg = st.slider("Gas Specific Gravity (Air=1.00)", min_value=0.55, max_value=1.00, value=float(st.session_state.t3_sg), step=0.01, key="t3_sg_slider")

        with col_ctrl2:
            st.markdown("##### 🛠️ Pipe Rating Controls")
            grades_list = ["J55", "N80", "L80-1", "P110", "L80-13Cr", "S13Cr-110", "22Cr-110", "25Cr-125"]
            t3_grade = st.selectbox("Steel Grade Selection:", grades_list, index=grades_list.index(st.session_state.t3_grade) if st.session_state.t3_grade in grades_list else 2, key="t3_grade_select")

        st.session_state.t3_pbhp = t3_pbhp
        st.session_state.t3_tvd = t3_tvd
        st.session_state.t3_sg = t3_sg
        st.session_state.t3_grade = t3_grade

        # ---------------------------------------------------------------------
        # 3. MATHEMATICAL COMPUTATIONS (CITHP & BURST)
        # ---------------------------------------------------------------------
        # Static CITHP Barometric Formula
        t_wh_f = 150.0
        t_bht_f = 210.0
        t_avg_r = ((t_wh_f + t_bht_f) / 2.0) + 459.67
        p_avg_psia = (t3_pbhp / 2.0) + 14.7

        # Z-factor estimate
        z_fact = 0.88 + 0.00002 * (p_avg_psia - 3000.0)
        z_fact = max(0.65, min(1.25, z_fact))

        p_bhp_psia = t3_pbhp + 14.7
        cithp_psia = p_bhp_psia * np.exp(-(0.01875 * t3_sg * t3_tvd) / (z_fact * t_avg_r))
        cithp_calc_psi = max(cithp_psia - 14.7, 0.0)

        # Candidate Burst Pressure Lookup (Baseline for 3.5" 9.2# tubing)
        grade_burst_lookup = {
            "J55": 7260.0, "N80": 10570.0, "L80-1": 10570.0, "P110": 13970.0,
            "L80-13Cr": 10160.0, "S13Cr-110": 13970.0, "22Cr-110": 13970.0, "25Cr-125": 15870.0
        }
        p_burst = grade_burst_lookup.get(t3_grade, 10570.0)
        p_test_mill = p_burst * 0.80  # API 5CT Hydrostatic proof test (80% yield)

        sf_burst_cithp = p_burst / cithp_calc_psi if cithp_calc_psi > 0 else 99.0
        burst_pass = sf_burst_cithp >= 1.10
        hydro_pass = p_test_mill >= cithp_calc_psi

        # ---------------------------------------------------------------------
        # 4. METRIC SUMMARY & STATUS BANNERS
        # ---------------------------------------------------------------------
        st.markdown("---")
        st.markdown("### 📈 CITHP Burst Metric Summary")

        m_e1, m_e2, m_e3, m_e4 = st.columns(4)
        m_e1.metric("Shut-In CITHP", f"{cithp_calc_psi:.0f} psi", help="Barometric static dry gas column")
        m_e2.metric("Pipe Body Burst Limit", f"{p_burst:.0f} psi", help="Candidate internal yield pressure")
        m_e3.metric("Surface Burst SF", f"{sf_burst_cithp:.2f}", delta="SF >= 1.10", delta_color="normal" if burst_pass else "inverse")
        m_e4.metric("Mill Proof Test P_test", f"{p_test_mill:.0f} psi", help="API 5CT Mill Test Gate (80% yield)")

        st.markdown("<br>", unsafe_allow_html=True)

        # Dynamic Status Alerts
        if not burst_pass:
            st.error(f"🔴 **SURFACE BURST FAILURE**: Calculated shut-in CITHP ({cithp_calc_psi:.0f} psi) exceeds allowable burst limit. Safety factor ({sf_burst_cithp:.2f}) is below target 1.10.")
        else:
            st.success(f"🟢 **SURFACE BURST SAFE**: Safety Factor ({sf_burst_cithp:.2f}) meets or exceeds the required 1.10 design threshold.")

        if not hydro_pass:
            st.warning(f"⚠️ **API 5CT PROOF-TEST ALERT**: Mill proof test pressure ({p_test_mill:.0f} psi) is below expected static shut-in CITHP ({cithp_calc_psi:.0f} psi). Wellhead pressure exceeds standard mill test parameters.")

# -----------------------------------------------------------------------------
# PAGE 5: METALLURGICAL & MATERIAL PROPERTY SELECTION (SOUR & QA LAB)
# -----------------------------------------------------------------------------
elif page == "5. Material Selection":
    st.markdown("""
        <style>
        .lab-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);
        }
        .status-card-sour {
            background-color: #FEF2F2;
            border-left: 5px solid #EF4444;
            border-radius: 8px;
            padding: 1rem 1.2rem;
        }
        .status-card-sweet {
            background-color: #ECFDF5;
            border-left: 5px solid #10B981;
            border-radius: 8px;
            padding: 1rem 1.2rem;
        }
        .status-card-premium {
            background-color: #FFFBEB;
            border-left: 5px solid #F59E0B;
            border-radius: 8px;
            padding: 1rem 1.2rem;
        }
        .status-card-api {
            background-color: #EFF6FF;
            border-left: 5px solid #3B82F6;
            border-radius: 8px;
            padding: 1rem 1.2rem;
        }
        .full-text-table table {
            width: 100% !important;
        }
        .full-text-table th {
            white-space: nowrap !important;
            background-color: #F8FAFC !important;
            color: #1E293B !important;
            font-size: 0.85rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-header">Step 5: Metallurgical, Material QA & Connection Lab</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Interactive educational lab for Sour Service (pH₂S), Premium Connection triggers, and API 5CT Material QA properties.</div>', unsafe_allow_html=True)

    # Top-Level Tabs for Page 5
    page5_tab1, page5_tab2 = st.tabs([
        "🧪 Tab 1: Sour Service & Premium Connection Lab",
        "🔬 Tab 2: API 5CT Material QA & Concept Simulator"
    ])

    # =========================================================================
    # PAGE 5 - TAB 1: SOUR SERVICE & PREMIUM CONNECTION LAB
    # =========================================================================
    with page5_tab1:
        # 1. STREAMLINED CONCEPT PRIMER
        with st.expander("💡 Quick Primer: Sour Service & Connection Physics", expanded=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                st.markdown(r"""
                **🧪 Sour Service (H₂S Risk)**
                * **Sulfide Stress Cracking (SSC):** Invisible H₂S gas breaks down in water, forcing atomic hydrogen into steel. This causes high-strength pipe to shatter without warning.
                * **NACE MR0175 Standard:** If $p_{\mathrm{H}_2\text{S}} \ge 0.05 \text{ psia}$, standard steels (**J55, N80, P110, Q125**) are **rejected**. Softened steel (**L80-1**) or Alloys (**13Cr, 22Cr, 25Cr**) are required.
                """)
            with col_i2:
                st.markdown("""
                **🔩 Connection Integrity (API vs. Premium)**
                * **Standard API Threads (EUE):** Rely on thread grease ("dope") to plug gaps. High pressure, gas streams, or heavy bending wash dope out, causing micro-leaks.
                * **Premium Connections:** Feature an engineered **metal-to-metal radial seal** and a solid **torque shoulder** that prevents leaks and stops thread galling on chrome alloys.
                """)

        st.markdown("<br/>", unsafe_allow_html=True)

        # 2. CONNECTION SEAL INTEGRITY COMPARISON
        st.markdown("### 🔩 Connection Seal Integrity Comparison")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("""
            <div class="lab-card" style="border-top: 4px solid #EF4444;">
                <h4 style="color:#991B1B; margin-top:0;">❌ API EUE Threaded Connection</h4>
                <p style="font-size:0.88rem; color:#334155;">
                    <b>Sealing Mechanism:</b> Helical thread clearance filled with thread compound ("pipe dope").<br/>
                    <b>Vulnerability:</b> Pressure cycles or gas streams wash out the thread dope, opening micro-annular leak paths. Chrome alloys readily gall under API thread interference.
                </p>
            </div>
            """, unsafe_allow_html=True)
        with col_t2:
            st.markdown("""
            <div class="lab-card" style="border-top: 4px solid #10B981;">
                <h4 style="color:#065F46; margin-top:0;">✅ Premium Metal-to-Metal Connection</h4>
                <p style="font-size:0.88rem; color:#334155;">
                    <b>Sealing Mechanism:</b> Engineered 100% metal-to-metal radial seal + pin/box torque shoulder.<br/>
                    <b>Advantage:</b> Torque shoulder acts as a positive mechanical stop that resists high axial loads and pressure cycles while maintaining a 100% gas-tight seal.
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # 3. LOCAL LAB STATE INITIALIZATION
        if 'lab_p_bhp' not in st.session_state:
            st.session_state.lab_p_bhp = float(st.session_state.inputs.get('p_bhp', 4500.0))
        if 'lab_h2s_ppm' not in st.session_state:
            st.session_state.lab_h2s_ppm = float(st.session_state.inputs.get('h2s_ppm', 150.0))
        if 'lab_cithp' not in st.session_state:
            st.session_state.lab_cithp = float(st.session_state.inputs.get('cithp', 2800.0))
        if 'lab_apb' not in st.session_state:
            st.session_state.lab_apb = float(st.session_state.inputs.get('apb_limit_psi', 1200.0))
        if 'lab_tvd' not in st.session_state:
            st.session_state.lab_tvd = float(st.session_state.inputs.get('tvd', 10000.0))
        if 'lab_gor' not in st.session_state:
            st.session_state.lab_gor = float(st.session_state.inputs.get('gor', 800.0))
        if 'lab_is_gas' not in st.session_state:
            st.session_state.lab_is_gas = "Gas" in str(st.session_state.inputs.get('well_type', 'Oil'))
        if 'lab_mat' not in st.session_state:
            st.session_state.lab_mat = "NACE Carbon Steel"
        if 'lab_axial' not in st.session_state:
            st.session_state.lab_axial = 120.0

        # 4. SCENARIO PRESETS
        st.markdown("### 🎯 Quick Scenario Presets")
        col_p1, col_p2, col_p3 = st.columns(3)

        if col_p1.button("🔥 High-Pressure Deep Gas Well", use_container_width=True):
            st.session_state.lab_p_bhp = 9500.0
            st.session_state.lab_h2s_ppm = 10.0
            st.session_state.lab_cithp = 6200.0
            st.session_state.lab_apb = 1800.0
            st.session_state.lab_tvd = 14500.0
            st.session_state.lab_gor = 12000.0
            st.session_state.lab_is_gas = True
            st.session_state.lab_mat = "High-Strength Alloy"
            st.session_state.lab_axial = 180.0
            st.rerun()

        if col_p2.button("☣️ Shallow Sour Oil Well", use_container_width=True):
            st.session_state.lab_p_bhp = 2800.0
            st.session_state.lab_h2s_ppm = 2500.0
            st.session_state.lab_cithp = 1200.0
            st.session_state.lab_apb = 600.0
            st.session_state.lab_tvd = 5500.0
            st.session_state.lab_gor = 450.0
            st.session_state.lab_is_gas = False
            st.session_state.lab_mat = "NACE Carbon Steel"
            st.session_state.lab_axial = 65.0
            st.rerun()

        if col_p3.button("🌊 Offshore Deepwater CRA Completion", use_container_width=True):
            st.session_state.lab_p_bhp = 11200.0
            st.session_state.lab_h2s_ppm = 850.0
            st.session_state.lab_cithp = 7500.0
            st.session_state.lab_apb = 2200.0
            st.session_state.lab_tvd = 16800.0
            st.session_state.lab_gor = 3500.0
            st.session_state.lab_is_gas = True
            st.session_state.lab_mat = "Martensitic Stainless (13Cr)"
            st.session_state.lab_axial = 210.0
            st.rerun()

        st.markdown("<br/>", unsafe_allow_html=True)

        # 5. SENSITIVITY CONTROLS & LIVE DIAGNOSTICS
        st.markdown("### 🎛️ Dynamic Sensitivity Controls & Live Status")
        ctrl_col, diag_col = st.columns([1.1, 1.0], gap="medium")

        with ctrl_col:
            st.markdown("**Drag sliders to test real-time operational thresholds:**")
            st.session_state.lab_p_bhp = st.slider("Bottomhole Pressure - Pbhp (psi)", 1000.0, 20000.0, float(st.session_state.lab_p_bhp), 100.0)
            st.session_state.lab_h2s_ppm = st.slider("H₂S Concentration (PPM)", 0.0, 10000.0, float(st.session_state.lab_h2s_ppm), 50.0)
            st.session_state.lab_cithp = st.slider("Closed-In Tubing Head Pressure - CITHP (psi)", 0.0, 15000.0, float(st.session_state.lab_cithp), 100.0)
            st.session_state.lab_apb = st.slider("Annular Pressure Rise - APB (psi)", 0.0, 5000.0, float(st.session_state.lab_apb), 50.0)
            st.session_state.lab_tvd = st.slider("True Vertical Depth - TVD (ft)", 1000.0, 25000.0, float(st.session_state.lab_tvd), 500.0)
            st.session_state.lab_axial = st.slider("Net Axial Tension Load (klbs)", 0.0, 400.0, float(st.session_state.lab_axial), 10.0)
            st.session_state.lab_gor = st.slider("Producing Gas-Oil Ratio - GOR (scf/STB)", 0.0, 15000.0, float(st.session_state.lab_gor), 100.0)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.session_state.lab_is_gas = st.checkbox("Gas Well Fluid Stream", value=bool(st.session_state.lab_is_gas))
            with col_c2:
                mat_options = ["Carbon Steel", "NACE Carbon Steel", "Martensitic Stainless (13Cr)", "Duplex Stainless (22Cr/25Cr)", "High-Strength Alloy"]
                current_mat = st.session_state.lab_mat
                mat_idx = mat_options.index(current_mat) if current_mat in mat_options else 1
                st.session_state.lab_mat = st.selectbox("Tubing Metallurgy Class", mat_options, index=mat_idx)

        # Core Calculations for Real-Time Diagnostics
        p_h2s_psia = st.session_state.lab_p_bhp * (st.session_state.lab_h2s_ppm / 1e6)
        is_sour = p_h2s_psia >= 0.05

        trig_gas = bool(st.session_state.lab_is_gas or st.session_state.lab_gor > 2000.0)
        trig_cithp = bool(st.session_state.lab_cithp > 3000.0)
        trig_apb = bool(st.session_state.lab_apb > 1500.0)
        trig_cra = bool("Cr" in st.session_state.lab_mat or "Duplex" in st.session_state.lab_mat)
        trig_load = bool(st.session_state.lab_tvd > 10000.0 or st.session_state.lab_axial > 150.0)

        active_triggers_count = sum([trig_gas, trig_cithp, trig_apb, trig_cra, trig_load])
        needs_premium = active_triggers_count > 0

        with diag_col:
            st.markdown("**Live Diagnostic Lightbulb Indicators:**")

            if is_sour:
                st.markdown(f"""
                    <div class="status-card-sour">
                        <h4 style="color:#991B1B; margin:0; font-size:1.05rem;">🔴 SOUR SERVICE ACTIVE (NACE MR0175)</h4>
                        <p style="margin-top:5px; font-size:0.88rem; color:#7F1D1D; line-height:1.4;">
                            <b>pH₂S Partial Pressure:</b> <span style="font-size:1.05rem; font-weight:bold;">{p_h2s_psia:.4f} psia</span> (≥ 0.05 psia Limit)<br/>
                            <b>Status:</b> Standard steels (J55, N80, P110, Q125) are <b>REJECTED</b> due to Sulfide Stress Cracking (SSC).
                            Must use <b>L80-1 (26 HRC Max)</b> or <b>CRAs</b>.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="status-card-sweet">
                        <h4 style="color:#065F46; margin:0; font-size:1.05rem;">🟢 SWEET SERVICE ENVIRONMENT</h4>
                        <p style="margin-top:5px; font-size:0.88rem; color:#064E3B; line-height:1.4;">
                            <b>pH₂S Partial Pressure:</b> <span style="font-size:1.05rem; font-weight:bold;">{p_h2s_psia:.4f} psia</span> (&lt; 0.05 psia Limit)<br/>
                            <b>Status:</b> Standard high-strength carbon steels are permitted.
                        </p>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("<br/>", unsafe_allow_html=True)

            if needs_premium:
                trigger_list_html = ""
                if trig_gas: trigger_list_html += "<li>Gas Stream / GOR &gt; 2000 scf/STB</li>"
                if trig_cithp: trigger_list_html += "<li>High Shut-In CITHP &gt; 3000 psi</li>"
                if trig_apb: trigger_list_html += "<li>Annular Pressure Build-up (APB) &gt; 1500 psi</li>"
                if trig_cra: trigger_list_html += "<li>Corrosion Resistant Alloy (CRA Metallurgy)</li>"
                if trig_load: trigger_list_html += "<li>TVD &gt; 10,000 ft or Net Axial Tension &gt; 150 klbs</li>"

                st.markdown(f"""
                    <div class="status-card-premium">
                        <h4 style="color:#92400E; margin:0; font-size:1.05rem;">🟠 PREMIUM CONNECTION MANDATED ({active_triggers_count}/5 Triggers)</h4>
                        <p style="margin-top:5px; font-size:0.85rem; color:#78350F; line-height:1.4;">
                            <b>Status:</b> Standard API EUE threads are <b>REJECTED</b> due to leak/galling risk.<br/>
                            <b>Active Operational Triggers:</b>
                            <ul style="margin-top:4px; margin-bottom:0; padding-left:18px;">
                                {trigger_list_html}
                            </ul>
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div class="status-card-api">
                        <h4 style="color:#1E40AF; margin:0; font-size:1.05rem;">🟢 STANDARD API EUE PERMITTED</h4>
                        <p style="margin-top:5px; font-size:0.88rem; color:#1E3A8A; line-height:1.4;">
                            <b>Status:</b> No active premium connection triggers. API EUE/NUE threaded connections are suitable for this non-gas liquid service.
                        </p>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # 6. DYNAMIC METALLURGICAL GRADE EVALUATION MATRIX
        st.markdown("### 📊 Dynamic Metallurgical Grade Evaluation Matrix")
        st.caption("Live evaluation of candidate tubing grades based on active pH₂S partial pressure and NACE hardness limits.")

        grades_data = [
            {"Grade Name": "J55", "Yield Strength (psi)": "55,000", "Hardness Spec": "No Cap", "NACE Compliant": "No", "Sour Service Screening Status": "REJECTED (Sulfide Stress Cracking Risk)" if is_sour else "PASSED (Sweet Service Only)"},
            {"Grade Name": "N80", "Yield Strength (psi)": "80,000", "Hardness Spec": "No Cap", "NACE Compliant": "No", "Sour Service Screening Status": "REJECTED (Sulfide Stress Cracking Risk)" if is_sour else "PASSED (Sweet Service Only)"},
            {"Grade Name": "L80-1", "Yield Strength (psi)": "80,000", "Hardness Spec": "26 HRC Maximum", "NACE Compliant": "Yes", "Sour Service Screening Status": "PASSED (NACE MR0175 Compliant Steel)"},
            {"Grade Name": "P110", "Yield Strength (psi)": "110,000", "Hardness Spec": "No Cap", "NACE Compliant": "No", "Sour Service Screening Status": "REJECTED (Sulfide Stress Cracking Risk)" if is_sour else "PASSED (Sweet Service Only)"},
            {"Grade Name": "Q125", "Yield Strength (psi)": "125,000", "Hardness Spec": "No Cap", "NACE Compliant": "No", "Sour Service Screening Status": "REJECTED (Sulfide Stress Cracking Risk)" if is_sour else "PASSED (Sweet Service Only)"},
            {"Grade Name": "L80-13Cr", "Yield Strength (psi)": "80,000", "Hardness Spec": "27 HRC Maximum", "NACE Compliant": "Yes (CRA)", "Sour Service Screening Status": "PASSED (Corrosion Resistant Alloy)"},
            {"Grade Name": "22Cr-110", "Yield Strength (psi)": "110,000", "Hardness Spec": "36 HRC Maximum", "NACE Compliant": "Yes (Duplex)", "Sour Service Screening Status": "PASSED (Duplex High-Strength CRA)"}
        ]

        df_grades = pd.DataFrame(grades_data)
        st.markdown('<div class="full-text-table">', unsafe_allow_html=True)
        st.table(df_grades)
        st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # PAGE 5 - TAB 2: API 5CT MATERIAL QA & CONCEPT SIMULATOR
    # =========================================================================
    with page5_tab2:
        st.markdown("### 🔬 API 5CT / ISO 11960 Material Property QA Simulator")
        st.caption("Interactive simulator for the four API 5CT mill acceptance properties: Ductility, Proof Pressure, Toughness, and As-Quenched Hardenability.")

        # Inner Sub-Tabs for the 4 QA Properties
        qa_sub1, qa_sub2, qa_sub3, qa_sub4 = st.tabs([
            "📏 1. Ductility (Elongation)",
            "🛡️ 2. Proof-Test Pressure Gate",
            "💥 3. Toughness (CVN)",
            "🔥 4. Martensite & Hardness"
        ])

        # ---------------------------------------------------------------------
        # SUB-TAB 1: DUCTILITY (MINIMUM ELONGATION)
        # ---------------------------------------------------------------------
        with qa_sub1:
            st.markdown(r"""
            <div class="lab-card" style="border-left: 5px solid #3B82F6;">
                <h4 style="margin:0; color:#1E3A8A;">Purpose of the Ductility Specification</h4>
                <p style="font-size:0.88rem; color:#334155; margin-top:5px;">
                    Minimum elongation verifies that steel deforms plastically rather than fracturing brittlely under tensile overload.
                    API 5CT calculates minimum percentage elongation $e = C \cdot \frac{A^{0.2}}{U^{0.9}}$, capping specimen area at $0.75\text{ in}^2$ ($490\text{ mm}^2$).
                    Higher tensile strength $U$ reduces the required elongation percentage.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col_d1, col_d2 = st.columns([1, 1.1], gap="medium")

            with col_d1:
                st.markdown("**Interactive Ductility Controls:**")
                qa_wall_d = st.slider("Nominal Wall Thickness - t (in)", 0.150, 0.750, 0.254, 0.010, key="qa_wall_d")
                qa_grade_d = st.selectbox("API 5CT Grade", ["J55", "L80-1", "N80", "P110", "Q125"], index=1, key="qa_grade_d")

                grade_utms = {"J55": 75000.0, "L80-1": 95000.0, "N80": 100000.0, "P110": 125000.0, "Q125": 135000.0}
                utm_psi = grade_utms[qa_grade_d]

                st.info(f"Grade **{qa_grade_d}** Specified Min Tensile Strength ($U$): **{utm_psi:,.0f} psi**")

            with col_d2:
                # Specimen Area Logic
                # If wall <= 0.350", use Strip specimen (1.5" width)
                # If wall > 0.350", use 0.500" Round Bar (Area = 0.20 in2)
                if qa_wall_d <= 0.350:
                    spec_type = "Strip Specimen (1.50 in Width)"
                    area_physical = qa_wall_d * 1.50
                else:
                    spec_type = "Round Bar Specimen (0.500 in Diameter)"
                    area_physical = 0.20

                area_effective = min(area_physical, 0.75) # Capped at 0.75 in2

                # Formula: e = 625,000 * (A^0.2) / (U^0.9)
                elongation_pct = 625000.0 * (area_effective ** 0.2) / (utm_psi ** 0.9)

                st.markdown("**Simulated API 5CT Elongation Outputs:**")
                st.metric("Required Minimum Elongation", f"{elongation_pct:.2f} %")
                st.metric("Test Specimen Basis", spec_type)
                st.metric("Specimen Cross-Section Area (A)", f"{area_effective:.4f} in²", delta="Capped at 0.75 in²" if area_physical > 0.75 else None)

        # ---------------------------------------------------------------------
        # SUB-TAB 2: PROOF-TEST PRESSURE VS. CITHP GATE
        # ---------------------------------------------------------------------
        with qa_sub2:
            st.markdown(r"""
            <div class="lab-card" style="border-left: 5px solid #10B981;">
                <h4 style="margin:0; color:#065F46;">Purpose of the Proof-Test Pressure Gate</h4>
                <p style="font-size:0.88rem; color:#334155; margin-top:5px;">
                    Every joint of tubing is hydrostatically proof-tested in the mill to a pressure $P = \frac{2 \cdot Y_S \cdot f \cdot t}{D}$.
                    Operating a well above the joint's factory proof pressure is a severe safety defect.
                    This simulator compares factory proof pressure directly against closed-in surface pressure (CITHP) as a <b>hard screening gate</b>.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col_p1, col_p2 = st.columns([1.1, 1.0], gap="medium")

            with col_p1:
                st.markdown("**Tubing Geometry & Mill Test Settings:**")
                qa_od_p = st.slider("Outer Diameter - OD (in)", 2.375, 9.625, 3.500, 0.125, key="qa_od_p")
                qa_wall_p = st.slider("Wall Thickness - t (in)", 0.150, 0.750, 0.254, 0.010, key="qa_wall_p")
                qa_grade_p = st.selectbox("Tubing Grade", ["J55", "L80-1", "P110", "Q125"], index=1, key="qa_grade_p")

                grade_yields = {"J55": 55000.0, "L80-1": 80000.0, "P110": 110000.0, "Q125": 125000.0}
                ys_psi = grade_yields[qa_grade_p]

                # Design Factor f logic
                f_factor = 0.60 if (qa_grade_p in ["J55"] and qa_od_p > 9.625) else 0.80

                st.markdown("---")
                st.markdown("**Surface Operating Pressure (Manual Override):**")
                qa_cithp_manual = st.slider("Closed-In Tubing Head Pressure - CITHP (psi)", 0, 15000, 6500, 100, key="qa_cithp_manual")

            with col_p2:
                # Hydrostatic Test Pressure Formula: P = (2 * YS * f * t) / D
                p_test_psi = (2.0 * ys_psi * f_factor * qa_wall_p) / qa_od_p
                pass_proof = p_test_psi >= qa_cithp_manual
                sf_proof = p_test_psi / qa_cithp_manual if qa_cithp_manual > 0 else 99.0

                st.markdown("**Factory Proof vs. Operating Load Results:**")
                st.metric("Mill Hydrostatic Proof Test (P_test)", f"{p_test_psi:,.0f} psi", help=f"Calculated with design factor f = {f_factor}")
                st.metric("Shut-In Surface CITHP Load", f"{qa_cithp_manual:,.0f} psi")
                st.metric("Proof-Test Safety Margin Factor", f"{sf_proof:.2f} x")

                if pass_proof:
                    st.markdown("""
                        <div class="status-card-sweet">
                            <h4 style="color:#065F46; margin:0;">✅ HARD GATE PASSED</h4>
                            <p style="margin:0; font-size:0.88rem; color:#064E3B;">
                                Mill proof-test pressure exceeds shut-in surface CITHP. Joint integrity is verified.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="status-card-sour">
                            <h4 style="color:#991B1B; margin:0;">❌ HARD GATE FAILED (REJECTED)</h4>
                            <p style="margin:0; font-size:0.88rem; color:#7F1D1D;">
                                Mill proof pressure is below surface CITHP. The string would be operated above its demonstrated factory proof limit!
                            </p>
                        </div>
                    """, unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # SUB-TAB 3: TOUGHNESS (CHARPY V-NOTCH)
        # ---------------------------------------------------------------------
        with qa_sub3:
            st.markdown(r"""
            <div class="lab-card" style="border-left: 5px solid #F59E0B;">
                <h4 style="margin:0; color:#92400E;">Purpose of the Toughness Specification</h4>
                <p style="font-size:0.88rem; color:#334155; margin-top:5px;">
                    Charpy V-notch (CVN) absorbed energy measures resistance to brittle fracture from notches or flaws.
                    <b>Couplings are evaluated using Specified MAXIMUM Yield Strength ($Y_{S,\max}$)</b> because the hardest permitted coupling is the most brittle location, whereas the pipe body uses Specified Minimum Yield Strength ($Y_S$).
                </p>
            </div>
            """, unsafe_allow_html=True)

            col_c1, col_c2 = st.columns([1, 1.1], gap="medium")

            with col_c1:
                st.markdown("**Pipe & Coupling QA Parameters:**")
                qa_wall_c = st.slider("Wall Thickness - t (mm)", 4.0, 20.0, 9.5, 0.5, key="qa_wall_c")
                qa_grade_c = st.selectbox("Grade", ["L80-1", "P110", "Q125"], index=0, key="qa_grade_c")
                qa_subsize = st.select_slider("Specimen Sub-Size Scaling Factor", options=[0.50, 0.75, 1.00], value=1.00, key="qa_subsize")

                grade_ys_min_mpa = {"L80-1": 552.0, "P110": 758.0, "Q125": 862.0}
                grade_ys_max_mpa = {"L80-1": 655.0, "P110": 965.0, "Q125": 1034.0}

                ys_min = grade_ys_min_mpa[qa_grade_c]
                ys_max = grade_ys_max_mpa[qa_grade_c]

            with col_c2:
                # Transverse CVN Formula: CVN_trans = Y * (0.00118 * t + 0.01288) + 2.04
                # Pipe Body uses YS_min; Coupling uses YS_max
                cvn_body_trans = (ys_min * (0.00118 * qa_wall_c + 0.01288) + 2.04) * qa_subsize
                cvn_cplg_trans = (ys_max * (0.00118 * qa_wall_c + 0.01288) + 2.04) * qa_subsize

                cvn_body_trans = max(cvn_body_trans, 11.0 * qa_subsize)
                cvn_cplg_trans = max(cvn_cplg_trans, 11.0 * qa_subsize)

                cvn_body_long = cvn_body_trans * 2.0
                cvn_cplg_long = cvn_cplg_trans * 2.0

                st.markdown("**Comparative Absorbed Energy Requirements:**")
                st.metric("Pipe Body Transverse CVN", f"{cvn_body_trans:.1f} Joules", help=f"Evaluated with YS_min = {ys_min:.0f} MPa")
                st.metric("Coupling Transverse CVN", f"{cvn_cplg_trans:.1f} Joules", delta=f"+{cvn_cplg_trans - cvn_body_trans:.1f} J stiffer", help=f"Evaluated with YS_max = {ys_max:.0f} MPa")
                st.metric("Pipe Body Longitudinal CVN", f"{cvn_body_long:.1f} Joules")
                st.metric("Coupling Longitudinal CVN", f"{cvn_cplg_long:.1f} Joules")

        # ---------------------------------------------------------------------
        # SUB-TAB 4: MARTENSITE FRACTION & HARDNESS
        # ---------------------------------------------------------------------
        with qa_sub4:
            st.markdown(r"""
            <div class="lab-card" style="border-left: 5px solid #8B5CF6;">
                <h4 style="margin:0; color:#5B21B6;">Purpose of the As-Quenched Hardness Requirement</h4>
                <p style="font-size:0.88rem; color:#334155; margin-top:5px;">
                    As-quenched mid-wall hardness $HRC_{\min}$ verifies that quenching achieved the required martensite fraction before tempering.
                    Evaluation is performed at mid-wall (slowest cooling point).
                    <b>Corrosion Resistant Alloys (13Cr, 22Cr, 25Cr) automatically override to Not Applicable</b> as they are solution-annealed.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col_m1, col_m2 = st.columns([1, 1.1], gap="medium")

            with col_m1:
                st.markdown("**Grade & Carbon Content Inputs:**")
                qa_grade_m = st.selectbox(
                    "Steel / CRA Grade",
                    ["L80-1", "C90", "T95", "C110", "P110", "Q125", "L80-13Cr", "22Cr-Duplex"],
                    index=0, key="qa_grade_m"
                )
                qa_carbon_wt = st.slider("Carbon Content (wt %)", 0.15, 0.50, 0.25, 0.01, key="qa_carbon_wt")

            with col_m2:
                is_cra_grade = "Cr" in qa_grade_m or "Duplex" in qa_grade_m

                if is_cra_grade:
                    st.markdown("""
                        <div class="status-card-api">
                            <h4 style="color:#1E40AF; margin:0;">ℹ️ NOT APPLICABLE (CRA METALLURGY)</h4>
                            <p style="margin-top:5px; font-size:0.88rem; color:#1E3A8A;">
                                <b>Override Active:</b> {qa_grade_m} is a Corrosion Resistant Alloy.
                                CRAs undergo solution annealing and do not have an as-quenched carbon-martensite hardness requirement.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    if qa_grade_m in ["C90", "T95"]:
                        hrc_min = 58.0 * qa_carbon_wt + 17.2
                        target_m = "≥ 90% Martensite Target (Severe Sour Grade)"
                    elif qa_grade_m == "C110":
                        hrc_min = 59.0 * qa_carbon_wt + 18.2
                        target_m = "≥ 95% Martensite Target (Ultra-High Strength Sour)"
                    else:
                        hrc_min = 52.0 * qa_carbon_wt + 14.0
                        target_m = "≥ 50% Martensite Target (Standard Q&T Steel)"

                    st.markdown("**Required As-Quenched Mid-Wall Properties:**")
                    st.metric("Minimum As-Quenched Hardness (HRC_min)", f"{hrc_min:.1f} HRC")
                    st.metric("Target Microstructural Phase", target_m)
                    st.caption("Measurement location: Mid-wall (position of maximum wall thickness and slowest quench rate).")

# -----------------------------------------------------------------------------
# PAGE 6: CALCULATION METHODOLOGY (REFINED & RESTORED)
# -----------------------------------------------------------------------------
elif page == METHODOLOGY_PAGE:
    st.markdown('<div class="main-header">Step 6: Comprehensive Calculation Methodology</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Mathematical guide mapping wellbore parameters through fluid PVT, slurry dynamics, hydraulics, structural load balance, and environmental safety gates. Click any box in the flowchart to jump straight to that step; click an <u>underlined term</u> anywhere on this page for a plain-English explanation.</div>', unsafe_allow_html=True)

    # Which step to auto-expand, driven by the ?step=N links in the flowchart below.
    try:
        active_step = int(st.query_params.get("step", 0))
    except (TypeError, ValueError):
        active_step = 0

    # -------------------------------------------------------------------------
    # 1. OVERVIEW FLOWCHART (clickable: each box links to ?step=N)
    # -------------------------------------------------------------------------
    st.markdown("""
<div class="card" style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #1E3A8A; margin-bottom: 1.5rem;">
    <h3 style="color: #1E3A8A; font-size: 1.25rem; margin-bottom: 0.4rem; font-weight: 700;">🔄 Modular 7-Step Engineering Screening Pipeline</h3>
    <p style="font-size: 0.92rem; color: #334155; line-height: 1.5; margin-bottom: 0;">
        Every candidate pipe from the database is processed through three engineering domains:
        <b>Domain A (Thermodynamics &amp; Rheology)</b>, <b>Domain B (Hydrodynamics &amp; Velocity Windows)</b>, and <b>Domain C (Structural Load &amp; Integrity Gates)</b>.
        <b style="color: #1E3A8A;">Click any step below to open it.</b>
    </p>
</div>
""", unsafe_allow_html=True)

    flowchart_html = """<style>
.flow-container { display: flex; flex-direction: column; align-items: center; max-width: 720px; margin: 0 auto 2rem auto; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.flow-box { width: 100%; padding: 12px 18px; border-radius: 8px; text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,0.04); border: 1px solid #CBD5E1; box-sizing: border-box; position: relative; }
.flow-box-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; gap: 8px; }
.flow-step-title { font-weight: 700; font-size: 0.92rem; }
.flow-domain-badge { font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }
.flow-box-body { font-size: 0.82rem; line-height: 1.4; color: #475569; }
.flow-arrow { display: flex; flex-direction: column; align-items: center; height: 28px; justify-content: center; position: relative; }
.flow-arrow-line { width: 2px; height: 100%; background-color: #94A3B8; }
.flow-arrow-head { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #94A3B8; margin-top: -2px; }
.flow-arrow-label { position: absolute; left: calc(50% + 12px); font-size: 0.75rem; color: #64748B; white-space: nowrap; font-weight: 500; }
</style>
<div class="flow-container">
    <div class="flow-box" style="background-color: #1E293B; color: white; border-color: #0F172A; text-align: center;">
        <span class="flow-step-title" style="font-size: 0.98rem;">Tubing Candidate Database (OD, ID, Grade, Connection, Yield &amp; Burst Ratings)</span>
    </div>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Reservoir Pressure, Temperature &amp; Rates</span>
    </div>
    <a class="flow-link" href="?step=1#step-1" target="_self">
    <div class="flow-box" style="background-color: #EFF6FF; border-left: 5px solid #2563EB;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #1E40AF;">Step 1: Multiphase Fluid PVT &amp; Gas Compressibility (Z-Factor)</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #DBEAFE; color: #1E40AF;">Domain A</span></span>
        </div>
        <div class="flow-box-body">Calculates solution gas-oil ratio (R<sub>s</sub>), oil formation volume factor (B<sub>o</sub>), and Dranchuk-Abou-Kassem compressibility (Z).</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Fluid Densities (&rho;<sub>o</sub>, &rho;<sub>w</sub>, &rho;<sub>g</sub>)</span>
    </div>
    <a class="flow-link" href="?step=2#step-2" target="_self">
    <div class="flow-box" style="background-color: #EFF6FF; border-left: 5px solid #3B82F6;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #1E40AF;">Step 2: Solid Particle Slurry Density &amp; Volumetric Concentration</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #DBEAFE; color: #1E40AF;">Domain A</span></span>
        </div>
        <div class="flow-box-body">Integrates sand volumetric fraction (C<sub>v</sub>) into mixture density to determine bulk slurry density (&rho;<sub>slurry</sub>).</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Slurry Density (&rho;<sub>slurry</sub>) &amp; Viscosity (&mu;<sub>m</sub>)</span>
    </div>
    <a class="flow-link" href="?step=3#step-3" target="_self">
    <div class="flow-box" style="background-color: #FFFBEB; border-left: 5px solid #D97706;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #92400E;">Step 3: Multiphase Frictional Hydraulics &amp; Pressure Loss (&Delta;P<sub>total</sub>)</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #FEF3C7; color: #92400E;">Domain B</span></span>
        </div>
        <div class="flow-box-body">Evaluates hydrostatic head &amp; turbulent pipe friction via Colebrook-White friction factor (f).</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Flow Velocity (v<sub>m</sub>) &amp; Friction Factor (f)</span>
    </div>
    <a class="flow-link" href="?step=4#step-4" target="_self">
    <div class="flow-box" style="background-color: #FFFBEB; border-left: 5px solid #F59E0B;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #92400E;">Step 4: Triple Velocity Operating Envelope (Erosion, Loading &amp; Settling)</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #FEF3C7; color: #92400E;">Domain B</span></span>
        </div>
        <div class="flow-box-body">Screens velocity window: Salama Sand Erosion Limit (v<sub>erosional</sub>) vs Turner Lift &amp; Rubey Settling (v<sub>carrying</sub>).</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Hydraulically Qualified Pipe Inner Diameters</span>
    </div>
    <a class="flow-link" href="?step=5#step-5" target="_self">
    <div class="flow-box" style="background-color: #ECFDF5; border-left: 5px solid #059669;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #065F46;">Step 5: Lubinski 5-Force Net Axial Load &amp; Trapped Annular APB</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #D1FAE5; color: #065F46;">Domain C</span></span>
        </div>
        <div class="flow-box-body">Calculates total net axial force (F<sub>axial</sub>) combining gravity, thermal expansion, piston, ballooning, drag &amp; APB.</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Net Axial Force (F<sub>axial</sub>) &amp; Annular Pressure (P<sub>annular</sub>)</span>
    </div>
    <a class="flow-link" href="?step=6#step-6" target="_self">
    <div class="flow-box" style="background-color: #ECFDF5; border-left: 5px solid #10B981;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #065F46;">Step 6: API TR 5C3 / ISO 10400 Triaxial Yield, Ductile Rupture &amp; Collapse</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #D1FAE5; color: #065F46;">Domain C</span></span>
        </div>
        <div class="flow-box-body">Three limit states: von Mises triaxial yield swept across all critical wall coordinates (SF &ge; 1.25), ductile rupture under combined loading (SF &ge; 1.25), and external pressure collapse with axial interaction (SF &ge; 1.10).</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Structurally Sound Steel Grades</span>
    </div>
    <a class="flow-link" href="?step=7#step-7" target="_self">
    <div class="flow-box" style="background-color: #F3E8FF; border-left: 5px solid #7C3AED;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #5B21B6;">Step 7: Shut-In Static CITHP Surface Burst, NACE Sour &amp; Connection Gate</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #E9D5FF; color: #5B21B6;">Domain C</span></span>
        </div>
        <div class="flow-box-body">Validates static surface burst (SF<sub>burst</sub> &ge; 1.10), NACE MR0175 sour service hardness, and Premium gas-tight threads.</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Environmentally &amp; Mechanically Compliant Candidates</span>
    </div>
    <a class="flow-link" href="?step=8#step-8" target="_self">
    <div class="flow-box" style="background-color: #FFF7ED; border-left: 5px solid #EA580C;">
        <div class="flow-box-header">
            <span class="flow-step-title" style="color: #9A3412;">Step 8: API 5CT / ISO 11960 Product Specification Verification</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #FFEDD5; color: #9A3412;">Domain D</span></span>
        </div>
        <div class="flow-box-body">Mill acceptance requirements: gauge-length elongation, hydrostatic proof-test pressure (screening gate), Charpy V-notch toughness, and as-quenched hardenability.</div>
    </div>
    </a>
    <div class="flow-arrow">
        <div class="flow-arrow-line"></div><div class="flow-arrow-head"></div>
        <span class="flow-arrow-label">Fully Compliant Candidate Profile</span>
    </div>
    <div class="flow-box" style="background-color: #059669; color: white; border-color: #047857; text-align: center;">
        <span class="flow-step-title" style="font-size: 0.98rem;">Optimal Recommended Tubing String (Ranked by Minimal Pressure Drop)</span>
    </div>
</div>"""

    st.markdown(flowchart_html, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
<div style="background-color: #DBEAFE; border-left: 6px solid #1D4ED8; padding: 0.75rem 1rem; border-radius: 6px; margin: 0.5rem 0 1.25rem;">
    <h2 style="color: #1E40AF; font-size: 1.45rem; margin: 0; font-weight: 700;">Domain A: Thermodynamics &amp; Slurry Rheology</h2>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div id="step-1"></div>', unsafe_allow_html=True)
    with st.expander("Step 1  ·  Multiphase Fluid PVT & Gas Compressibility (Z-Factor)   —   Domain A", expanded=(active_step == 1)):
        formula_card(
            "1.1",
            "Oil Well Live Fluid PVT (Standing's Correlations)",
            "#1E40AF",
            [
                (r"R_s = \gamma_g \left[ \left( \frac{P_{avg}}{18.2} + 1.4 \right) 10^{(0.0125 \cdot \text{API} - 0.00091 \cdot T_{avg})} \right]^{1.2048}", "Dissolved gas carried by the oil at depth"),
                (r"B_o = 0.9759 + 0.000120 \left[ R_s \left( \frac{\gamma_g}{\gamma_o} \right)^{0.5} + 1.25 \cdot T_{avg} \right]^{1.2}", "How much the oil swells downhole"),
                (r"\rho_{o,live} = \frac{62.4 \cdot \gamma_o + 0.0136 \cdot R_s \cdot \gamma_g}{B_o}, \quad \rho_l = (1-f_w)\rho_{o,live} + f_w \rho_w", "Resulting live-oil and total liquid density"),
            ],
            f"Works out how heavy the liquid column really is. Standing's {term('pvt')} correlations give the dissolved gas ({term('rs', 'gas-oil ratio')}), the volume swelling ({term('bo', 'formation volume factor')}), and from those the live oil density. That density sets the {term('hydrostatic')} the well must lift against, so it feeds every pressure calculation downstream.",
            [
                ("R<sub>s</sub>", "Solution gas-oil ratio — gas dissolved in the oil", "scf/STB"),
                ("&gamma;<sub>g</sub>", "Gas specific gravity", "Air = 1.00"),
                ("P<sub>avg</sub>", "Mean wellbore pressure, (P<sub>wh</sub> + P<sub>bhp</sub>) / 2", "psi"),
                ("API", "Stock-tank oil gravity — higher means lighter oil", "&deg;API"),
                ("T<sub>avg</sub>", "Mean wellbore temperature, (T<sub>wh</sub> + T<sub>bht</sub>) / 2", "&deg;F"),
                ("B<sub>o</sub>", "Oil formation volume factor — downhole swelling", "rb/STB"),
                ("&gamma;<sub>o</sub>", "Oil specific gravity, 141.5 / (131.5 + API)", "Water = 1.00"),
                ("&rho;<sub>o,live</sub>", "Density of live gas-saturated oil at depth", "lb/ft<sup>3</sup>"),
                ("f<sub>w</sub>", "Water cut — fraction of liquid that is water", "0.0 - 1.0"),
                ("&rho;<sub>w</sub>", "Formation water density, SG<sub>w</sub> × 62.4", "lb/ft<sup>3</sup>"),
            ],
            "Rejects a candidate when the PVT solution will not converge numerically, or when extreme reservoir pressure produces non-physical liquid expansion (<i>B<sub>o</sub></i> &le; 0).",
        )

        formula_card(
            "1.2",
            "Gas Well Density &amp; Pseudo-Critical Properties",
            "#1E40AF",
            [
                (r"P_{pc} = 756.8 - 131.07 \gamma_g - 3.6 \gamma_g^2, \quad T_{pc} = 169.2 + 349.5 \gamma_g - 74.0 \gamma_g^2", "Pseudo-critical anchors for the Z correlation"),
                (r"q_{g,\text{ft}^3/\text{s}} = \frac{Q_g \cdot 10^6 \cdot 14.7 \cdot T_{avg,R} \cdot Z}{P_{avg} \cdot 520 \cdot 86400}, \quad \rho_g = \frac{2.7 \cdot \gamma_g \cdot P_{avg}}{Z \cdot T_{avg,R}}", "Surface rate converted to downhole flow, and gas density"),
                (r"\lambda_l = \frac{q_l}{q_l + q_g}, \quad \rho_m = \lambda_l \rho_l + (1-\lambda_l)\rho_g", "Liquid share of the pipe, and blended mixture density"),
            ],
            f"Converts a surface gas rate into what the gas actually occupies downhole. The {term('z-factor')} is solved from the Dranchuk-Abou-Kassem equation of state, iterated on reduced density using Standing's {term('pseudo-critical')}. Combining gas density with {term('holdup', 'liquid holdup')} gives the mixture density used for hydraulics.",
            [
                ("P<sub>pc</sub>, T<sub>pc</sub>", "Gas pseudo-critical pressure and temperature", "psia, &deg;R"),
                ("Q<sub>g</sub>", "Surface gas production rate", "MMscf/D"),
                ("T<sub>avg,R</sub>", "Mean absolute wellbore temperature, &deg;F + 459.67", "&deg;R"),
                ("Z", "Gas compressibility — deviation from ideal gas", "0.65 - 1.25"),
                ("q<sub>g</sub>", "Downhole volumetric gas flow rate", "ft<sup>3</sup>/s"),
                ("&rho;<sub>g</sub>", "In-situ gas density at depth", "lb/ft<sup>3</sup>"),
                ("&lambda;<sub>l</sub>", "No-slip liquid holdup fraction", "0.0 - 1.0"),
                ("&rho;<sub>m</sub>", "Homogeneous multiphase mixture density", "lb/ft<sup>3</sup>"),
            ],
            f"Rejects a candidate when the in-situ {term('z-factor')} falls outside the valid thermodynamic range (0.65 &le; <i>Z</i> &le; 1.25), which signals the correlation is being used outside its envelope.",
        )

    st.markdown('<div id="step-2"></div>', unsafe_allow_html=True)
    with st.expander("Step 2  ·  Solid Particle Slurry Density & Volumetric Concentration   —   Domain A", expanded=(active_step == 2)):
        formula_card(
            "2.1",
            "Solid Particle Slurry Integration",
            "#1E40AF",
            [
                (r"C_v = \frac{V_{sand}}{V_{liquid} + V_{sand}} = \frac{\frac{W_s}{\rho_s}}{\left(\frac{Q_{liq} \cdot 5.615}{86400}\right) + \frac{W_s}{\rho_s}}", "Sand share of the flowing stream, by volume"),
                (r"\rho_{\text{slurry}} = (1 - C_v) \rho_m + C_v \rho_s", "Mixture density corrected for suspended sand"),
            ],
            f"Accounts for formation sand travelling up the well with the fluid. The {term('cv', 'volumetric concentration')} of solids raises the density of the {term('slurry')} above that of clean fluid, which changes the hydrostatic column and, in Step 4, sharply raises erosion risk.",
            [
                ("C<sub>v</sub>", "Solids volumetric concentration", "0.0 - 1.0"),
                ("V<sub>sand</sub>", "Volumetric rate of solid sand particles", "ft<sup>3</sup>/s"),
                ("V<sub>liquid</sub>", "Volumetric rate of the liquid phases", "ft<sup>3</sup>/s"),
                ("W<sub>s</sub>", "Sand mass rate, from the PPTB input (lb per 1000 bbl)", "lb/s"),
                ("&rho;<sub>s</sub>", "Sand grain density (quartz, SG = 2.65)", "165.4 lb/ft<sup>3</sup>"),
                ("Q<sub>liq</sub>", "Total surface liquid rate", "STB/D"),
                ("&rho;<sub>slurry</sub>", "Bulk solid-liquid-gas mixture density", "lb/ft<sup>3</sup>"),
            ],
            f'"Rejects a candidate when solids concentration exceeds <i>C<sub>v</sub></i> &gt; {CV_SOLIDS_MAX} '
            f'({int(CV_SOLIDS_MAX * 100)}% by volume) — hyper-concentrated slurry falls outside '
            'standard multiphase transport models."',
        )

    st.markdown("---")

    st.markdown("""
<div style="background-color: #FEF3C7; border-left: 6px solid #D97706; padding: 0.75rem 1rem; border-radius: 6px; margin: 0.5rem 0 1.25rem;">
    <h2 style="color: #92400E; font-size: 1.45rem; margin: 0; font-weight: 700;">Domain B: Flow Hydrodynamics &amp; Velocity Boundaries</h2>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div id="step-3"></div>', unsafe_allow_html=True)
    with st.expander("Step 3  ·  Multiphase Frictional Hydraulics & Pressure Loss   —   Domain B", expanded=(active_step == 3)):
        formula_card(
            "3.1",
            "Total Slurry Wellbore Pressure Loss",
            "#92400E",
            [
                (r"\Delta P_{total} = \underbrace{\frac{\rho_{\text{slurry}} \cdot TVD}{144}}_{\Delta P_{hydrostatic}} + \underbrace{\frac{f \cdot MD \cdot \rho_{\text{slurry}} \cdot v_m^2}{2 \cdot g_c \cdot d_i \cdot 144}}_{\Delta P_{friction}}", "Weight of the fluid column plus wall friction"),
            ],
            f"Adds the two things that consume pressure on the way up: the {term('hydrostatic')} weight of the column, and friction against the pipe wall. The total is compared against the {term('drawdown', 'available drawdown')} — if losses exceed the reservoir's pressure budget, the well cannot flow unaided.",
            [
                ("&Delta;P<sub>total</sub>", "Total expected wellbore pressure drop", "psi"),
                ("TVD", "True vertical depth — drives hydrostatic head", "ft"),
                ("MD", "Measured depth along the trajectory — drives friction", "ft"),
                ("f", "Fanning turbulent friction factor", "dimensionless"),
                ("v<sub>m</sub>", "Mean mixture velocity, q<sub>m</sub> / A<sub>id</sub>", "ft/s"),
                ("g<sub>c</sub>", "Unit conversion constant", "32.174 lbm&middot;ft/(lbf&middot;s<sup>2</sup>)"),
                ("d<sub>i</sub>", "Inner diameter of the candidate tubing", "ft"),
            ],
            "Rejects a candidate when total pressure drop exceeds the available drawdown (<i>&Delta;P<sub>total</sub></i> &gt; P<sub>bhp</sub> &minus; P<sub>wh</sub>), leaving the well unable to flow naturally.",
        )

        formula_card(
            "3.2",
            "Colebrook-White Friction Factor &amp; Reynolds Number",
            "#92400E",
            [
                (r"\frac{1}{\sqrt{f}} = -1.8 \log_{10} \left[ \left( \frac{\epsilon / d_i}{3.7} \right)^{1.11} + \frac{6.9}{Re} \right]", "Friction factor for fully turbulent flow"),
                (r"Re = \frac{\rho_{\text{slurry}} v_m d_i}{\mu_m}", "Flow regime indicator"),
            ],
            f"Establishes how rough-and-turbulent the flow is, which sets the friction term above. The {term('friction-factor')} depends on the {term('reynolds', 'Reynolds number')} and on the pipe's {term('roughness', 'relative roughness')} — the same surface finish matters far more in a narrow pipe.",
            [
                ("f", "Turbulent friction factor", "dimensionless"),
                ("&epsilon;", "Absolute internal wall roughness", "0.0006 in (new steel)"),
                ("d<sub>i</sub>", "Tubing inner diameter", "ft"),
                ("Re", "Reynolds number — laminar below ~2000, turbulent above ~4000", "dimensionless"),
                ("&mu;<sub>m</sub>", "Dynamic mixture viscosity, cP × 0.000672", "lb/(ft&middot;s)"),
            ],
            f'"Rejects a candidate when severe internal restriction produces a non-physical friction '
            f'factor (<i>f</i> &gt; {FRICTION_FACTOR_MAX})."',
        )

    st.markdown('<div id="step-4"></div>', unsafe_allow_html=True)
    with st.expander("Step 4  ·  Triple Velocity Operating Envelope (Erosion, Loading & Settling)   —   Domain B", expanded=(active_step == 4)):
        formula_card(
            "4.1",
            "Salama Sand Erosional Velocity Limit (1983)",
            "#92400E",
            [
                (r"v_{\text{erosional, sand}} = \frac{C_{\text{salama}}}{\sqrt{\rho_{\text{slurry}}}} \cdot \sqrt{\frac{d_i}{W_s}}", "Upper speed limit set by sand impact damage"),
            ],
            f"Sets the ceiling of the velocity window. Sand grains striking the wall remove metal, so this gives the {term('erosional', 'erosional velocity')} above which the pipe thins faster than the well's design life allows. In sand-producing wells this replaces the clean-fluid API 14E limit, which is unconservative when solids are present.",
            [
                ("v<sub>erosional</sub>", "Maximum allowable velocity before sand erosion", "ft/s"),
                ("C<sub>salama</sub>", "Empirical alloy erosion coefficient", "200 carbon / 450 CRA"),
                ("&rho;<sub>slurry</sub>", "Bulk slurry density", "lb/ft<sup>3</sup>"),
                ("d<sub>i</sub>", "Tubing inner diameter", "in"),
                ("W<sub>s</sub>", "Sand production mass rate", "lb/day"),
            ],
            "Rejects a candidate when early-life peak mixture velocity exceeds the Salama erosion threshold (<i>v<sub>m</sub></i> &gt; <i>v<sub>erosional</sub></i>), which would wash out the wall.",
        )

        formula_card(
            "4.2",
            "Solid Settling &amp; Critical Liquid Lift Criteria",
            "#92400E",
            [
                (r"v_t = \sqrt{\frac{2}{3} g d_p \left(\frac{\rho_s - \rho_{\text{slurry}}}{\rho_{\text{slurry}}}\right) + 36 \nu^2} - \frac{6 \nu}{d_p}", "Rubey: how fast a sand grain falls"),
                (r"v_{\text{critical}} = \frac{1.3 \cdot \sigma^{0.25}(\rho_l - \rho_g)^{0.25}}{\rho_g^{0.5}}", "Turner: speed needed to carry a liquid droplet"),
                (r"v_{\text{carrying}} = \max(v_{\text{critical}}, 1.35 v_t)", "Governing minimum — the stricter of the two"),
            ],
            f"Sets the floor of the velocity window. Rubey's {term('terminal-velocity', 'terminal settling velocity')} gives how fast sand falls, and Turner's criterion — driven by {term('interfacial-tension')} — gives the speed needed to carry droplets. The stricter of the two becomes the {term('carrying', 'carrying velocity')}; below it, solids drop out and {term('liquid-loading')} sets in.",
            [
                ("v<sub>t</sub>", "Rubey terminal settling velocity of sand grains", "ft/s"),
                ("g", "Gravitational acceleration", "32.174 ft/s<sup>2</sup>"),
                ("d<sub>p</sub>", "Mean sand particle diameter, microns × 3.28084 × 10<sup>-6</sup>", "ft"),
                ("&nu;", "Kinematic viscosity, &mu;<sub>m</sub> / &rho;<sub>slurry</sub>", "ft<sup>2</sup>/s"),
                ("v<sub>critical</sub>", "Turner critical droplet lift velocity", "ft/s"),
                ("&sigma;", "Liquid-gas interfacial tension", "20.0 dynes/cm default"),
                ("v<sub>carrying</sub>", "Governing minimum allowable velocity", "ft/s"),
            ],
            "Rejects a candidate when velocity falls below the carrying minimum (<i>v<sub>m</sub></i> &lt; <i>v<sub>carrying</sub></i>) in either early or late life, which would plug the well with sand or load it with liquid.",
        )

    st.markdown("---")

    st.markdown("""
<div style="background-color: #D1FAE5; border-left: 6px solid #059669; padding: 0.75rem 1rem; border-radius: 6px; margin: 0.5rem 0 1.25rem;">
    <h2 style="color: #065F46; font-size: 1.45rem; margin: 0; font-weight: 700;">Domain C: Structural Mechanics &amp; Environmental Integrity</h2>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div id="step-5"></div>', unsafe_allow_html=True)
    with st.expander("Step 5  ·  Lubinski 5-Force Net Axial Load & Trapped Annular APB   —   Domain C", expanded=(active_step == 5)):
        formula_card(
            "5.1",
            "Lubinski Net Axial Force Balance",
            "#065F46",
            [
                (r"F_{axial} = F_{gravity} + F_{thermal} + F_{piston} + F_{ballooning} + F_{drag}", "The five forces, summed"),
                (r"F_{gravity} = W_{lbft} \cdot MD \left(1 - \frac{\rho_{\text{slurry}}}{490}\right), \quad F_{thermal} = E \cdot A_{steel} \cdot \alpha \cdot \Delta T_{annular}", "Buoyed pipe weight, and restrained thermal growth"),
                (r"F_{piston} = P_{bhp} A_{id} - P_{annular} (A_{od} - A_{id}), \quad F_{ballooning} = 2 \nu_p (P_{bhp} A_{id} - P_{annular} A_{od})", "Pressure end-load at the packer, and radial swelling"),
            ],
            f"Totals the {term('axial-load', 'net axial load')} carried by the string during production. It combines buoyed pipe weight, the {term('thermal-force', 'thermal expansion force')} that appears when a {term('packer')} prevents the heated string from lengthening, the {term('piston')} force from pressure acting across the area change, {term('ballooning')}, and fluid drag.",
            [
                ("F<sub>axial</sub>", "Total net axial load — positive tension, negative compression", "lbs"),
                ("W<sub>lbft</sub>", "Nominal tubing linear weight", "lb/ft"),
                ("E", "Young’s modulus of steel", "30 × 10<sup>6</sup> psi"),
                ("A<sub>steel</sub>", "Steel cross-sectional area of the wall", "in<sup>2</sup>"),
                ("&alpha;", "Thermal expansion coefficient of steel", "6.9 × 10<sup>-6</sup> /&deg;F"),
                ("&Delta;T<sub>annular</sub>", "Mean thermal rise in the trapped annulus", "&deg;F"),
                ("A<sub>id</sub>, A<sub>od</sub>", "Internal and external cross-sectional area", "ft<sup>2</sup>"),
                ("&nu;<sub>p</sub>", "Poisson’s ratio of steel", "0.30"),
            ],
            "Rejects a candidate when the magnitude of net axial load |<i>F<sub>axial</sub></i>| exceeds the pipe body rating (SMYS × A<sub>steel</sub>).",
        )

        formula_card(
            "5.2",
            "Trapped Annular Pressure Build-up (APB)",
            "#065F46",
            [
                (r"\Delta P_{APB} = \left( \frac{\alpha_v}{\kappa_T} \right) \Delta T_{annular, ^\circ C}", "Pressure rise from fluid that cannot expand"),
                (r"\Delta T_{annular, ^\circ C} = \frac{5}{9}\left(T_{avg} - T_{ambient}\right)_{^\circ F}, \quad P_{annular,total} = P_{wh} + \Delta P_{APB}", "Temperature rise above surface datum, and total external pressure"),
            ],
            f"Captures {term('apb')}: completion fluid sealed in the {term('annulus')} is heated by production but has nowhere to expand, so pressure climbs. The rise is measured from the ambient surface datum and converted to &deg;C to match the units of <i>&alpha;<sub>v</sub></i>. The result raises external pressure on the tubing, feeding the collapse and {term('ballooning')} checks.",
            [
                ("&Delta;P<sub>APB</sub>", "Pressure rise in the sealed annulus", "psi"),
                ("&alpha;<sub>v</sub>", "Volumetric thermal expansion coefficient of brine", "/&deg;C"),
                ("&kappa;<sub>T</sub>", "Isothermal compressibility of the fluid", "/psi"),
                ("&Delta;T<sub>annular</sub>", "Mean temperature change in the annulus", "&deg;C"),
                ("P<sub>annular,total</sub>", "Total external pressure acting on the tubing", "psi"),
            ],
            "Rejects a configuration when APB exceeds 1500 psi, which erodes the external collapse safety margin.",
        )

    st.markdown('<div id="step-6"></div>', unsafe_allow_html=True)
    with st.expander("Step 6  ·  API TR 5C3 / ISO 10400 Triaxial Yield, Ductile Rupture & Collapse   —   Domain C", expanded=(active_step == 6)):
        st.markdown(
            '<div class="m2-purpose" style="margin-bottom: 1.1rem;">'
            'Steps 6.1&ndash;6.4 implement the three limit states of <b>API TR 5C3 / ISO 10400</b>: '
            'triaxial yield of the pipe body (Clause 6), ductile rupture under combined loading '
            '(Clause 7), and external pressure resistance (Clause 8). All three are computed in '
            'native USCS units internally &mdash; the Clause 8 constants are dimensional and only '
            'valid with <i>Y<sub>pa</sub></i> in psi &mdash; and converted back on output.'
            '</div>',
            unsafe_allow_html=True,
        )

        formula_card(
            "6.1",
            "Lam&eacute; Thick-Wall Component Stresses (Clause 6)",
            "#065F46",
            [
                (r"\sigma_r(r) = \frac{P_i r_{iw}^2 - P_e r_o^2}{r_o^2 - r_{iw}^2} - \frac{(P_i - P_e) r_{iw}^2 r_o^2}{r^2 (r_o^2 - r_{iw}^2)}, \quad \sigma_\theta(r) = \frac{P_i r_{iw}^2 - P_e r_o^2}{r_o^2 - r_{iw}^2} + \frac{(P_i - P_e) r_{iw}^2 r_o^2}{r^2 (r_o^2 - r_{iw}^2)}", "Radial and hoop stress, evaluated on the tolerance-reduced bore"),
                (r"\sigma_z(r, \theta_{fiber}) = \frac{F_a}{A_n} \pm \frac{E \cdot D \cdot \beta}{2}, \quad \tau(r) = \frac{T \cdot r}{J_n}", "Axial stress with bending on either fibre, and torsional shear"),
                (r"r_{iw} = \frac{D - 2 w_n k_{wall}}{2}, \quad \beta \, [\text{rad/in}] = DLS \, [\text{deg}/100\text{ft}] \times \frac{\pi}{180} \times \frac{1}{1200}", "Wall tolerance applies to pressure stresses only; curvature conversion"),
            ],
            f"Resolves the full three-dimensional stress state using the {term('lame')}. The 12.5% wall "
            f"manufacturing tolerance (<i>k<sub>wall</sub></i> = 0.875) is applied <b>only</b> to the bore "
            f"radius used for pressure stresses; axial, {term('dogleg', 'bending')} and torsional stresses "
            f"use nominal section properties <i>A<sub>n</sub></i> and <i>J<sub>n</sub></i>, as the standard "
            f"requires. Curvature converts from deg/100&nbsp;ft or deg/30&nbsp;m to rad/in.",
            [
                ("&sigma;<sub>r</sub>, &sigma;<sub>&theta;</sub>", "Radial and hoop stress at radius <i>r</i>", "psi"),
                ("&sigma;<sub>z</sub>", "Axial stress: uniform load &plusmn; bending fibre", "psi"),
                ("&tau;", "Torsional shear stress", "psi"),
                ("r<sub>iw</sub>", "Tolerance-reduced inner radius (pressure stresses only)", "in"),
                ("A<sub>n</sub>, J<sub>n</sub>", "Nominal steel area and polar moment, from <i>d<sub>n</sub></i> = <i>D</i> &minus; 2<i>w<sub>n</sub></i>", "in<sup>2</sup>, in<sup>4</sup>"),
                ("k<sub>wall</sub>", "Wall manufacturing tolerance factor", "0.875 (12.5%)"),
                ("&beta;", "Wellbore curvature converted from DLS", "rad/in"),
                ("E", "Young&rsquo;s modulus &mdash; grade-dependent", "30 &times; 10<sup>6</sup> psi (28.5 &times; 10<sup>6</sup> duplex)"),
            ],
            "Feeds Step 6.2; no rejection occurs at this stage.",
        )

        formula_card(
            "6.2",
            "von Mises Triaxial Yield &mdash; Multi-Coordinate Evaluation (Clause 6)",
            "#065F46",
            [
                (r"\sigma_{VME} = \sqrt{\frac{1}{2}\left[(\sigma_r - \sigma_\theta)^2 + (\sigma_\theta - \sigma_z)^2 + (\sigma_z - \sigma_r)^2\right] + 3\tau^2}", "Full form, including the torsional shear term"),
                (r"\sigma_{VME,max} = \max\left(\sigma_{VME,1}, \sigma_{VME,2}, \ldots, \sigma_{VME,n}\right) \le Y_p", "The governing point across all evaluated coordinates"),
                (r"SF_{triaxial} = \frac{Y_p}{\sigma_{VME,max}} \ge 1.25", "Margin against yield"),
            ],
            f"Reduces the 3D stress state to a single {term('von-mises', 'equivalent stress')} comparable "
            f"against {term('smys', 'yield strength')}. Critically, <b>&sigma;<sub>VME</sub> is not evaluated at "
            f"a single point</b>: the engine sweeps the critical radial and circumferential fibre coordinates "
            f"and reports the maximum, because the governing location shifts with the load case. "
            f"With bending and torsion present that is 4 points; with torsion alone 2; with neither 1. "
            f"The screening matrix reports which coordinate governed.",
            [
                ("&sigma;<sub>VME,max</sub>", "Governing von Mises stress across all coordinates", "psi"),
                ("Combined bending &amp; torsion", "<i>r</i> &isin; {<i>r<sub>iw</sub></i>, <i>r<sub>o</sub></i>} &times; fibre &isin; {+&sigma;<sub>zb</sub>, &minus;&sigma;<sub>zb</sub>}", "4 points"),
                ("Torsion, no bending", "<i>r</i> &isin; {<i>r<sub>iw</sub></i>, <i>r<sub>o</sub></i>}, &sigma;<sub>zb</sub> = 0", "2 points"),
                ("Neither", "<i>r</i> = <i>r<sub>iw</sub></i> only", "1 point"),
                ("Y<sub>p</sub>", "Specified minimum yield strength of the grade", "L80 = 80,000 psi"),
                ("SF<sub>triaxial</sub>", "Triaxial safety factor", "target &ge; 1.25"),
            ],
            "Rejects a candidate whose governing <i>SF<sub>triaxial</sub></i> &lt; 1.25 at any evaluated coordinate, which would allow plastic deformation under combined loading.",
        )

        formula_card(
            "6.3",
            "Ductile Rupture under Combined Loading (Clause 7)",
            "#065F46",
            [
                (r"w_e = w_n k_{wall} - k_{flaw} d_{flaw}, \quad n = 0.182 - 0.000105\,Y_p \, [\text{ksi}], \quad k_n = 1 + \frac{0.5^n}{0.75 + n}", "Effective wall after tolerance and flaw deductions; strain-hardening parameters"),
                (r"P_{brc} = k_{bs} k_n U_m \ln\!\left(\frac{D}{D - 2 w_e}\right), \quad P_{vme} = \tfrac{2}{\sqrt{3}} P_{brc}, \quad P_{tr} = P_{brc}", "Base rupture capacity and the two envelope limits"),
                (r"F_{eff} = F_a + \tfrac{\pi}{4}\left(P_i d_n^2 - P_e D^2\right), \quad u = \frac{F_{eff}}{U_m A_n}", "Pressure-augmented effective axial load, normalised"),
                (r"\left(\frac{P_{br} - P_e}{P_{lim}}\right)^{m} + |u|^{m} = 1, \quad m_{rup} = 1 + n \;\; \text{(rupture)}, \quad m_{neck} = 2 \;\; \text{(necking)}", "Interaction envelope; the governing branch is whichever gives less capacity"),
            ],
            f"Guards against {term('burst', 'burst rupture')} and gross axial necking &mdash; plastic strain "
            f"localisation, not first yield. This is a <b>different and generally more limiting</b> check than "
            f"the {term('smys', 'yield')}-based triaxial gate, because it is driven by ultimate tensile strength "
            f"<i>U<sub>m</sub></i>. Since <i>F<sub>eff</sub></i> itself depends on <i>P<sub>i</sub></i>, capacity "
            f"at fixed <i>F<sub>a</sub></i> is the fixed point <i>P<sub>i</sub></i> = <i>P<sub>br</sub></i>, "
            f"solved by <b>Newton&ndash;Raphson</b> with a bisection fallback. The engine selects the governing "
            f"branch as the lower of the two envelopes, which is continuous in |<i>u</i>| and crosses over at "
            f"the standard&rsquo;s stated boundary.",
            [
                ("P<sub>br</sub>", "Ductile rupture capacity under combined load", "psi"),
                ("w<sub>e</sub>", "Effective wall: tolerance <i>and</i> inspection flaw removed", "in"),
                ("d<sub>flaw</sub>", "Inspection flaw depth", "default 0.05&nbsp;&middot;&nbsp;<i>w<sub>n</sub></i>"),
                ("k<sub>flaw</sub>", "Flaw depth factor", "1.0"),
                ("U<sub>m</sub>", "Minimum ultimate tensile strength", "L80 = 95,000 psi"),
                ("n", "Strain-hardening exponent", "L80 &asymp; 0.174"),
                ("k<sub>bs</sub>", "Bending strength factor", "0.95 Q&amp;T / 13Cr, 0.88 normalized"),
                ("u", "Normalised effective axial load", "dimensionless"),
                ("Active mode", "Rupture (<i>P<sub>i</sub></i>-driven burst) or necking (<i>F<sub>eff</sub></i>-driven tension)", "reported per candidate"),
            ],
            "Rejects a candidate whose rupture capacity gives <i>SF</i> &lt; 1.25 against shut-in CITHP. High strain-hardening alloys (duplex, 22Cr/25Cr, <i>n</i> &gt; 0.2) are rejected outright unless a measured true stress-strain fit is supplied, since the empirical <i>n</i> estimate is invalid for them.",
        )

        formula_card(
            "6.4",
            "External Pressure Resistance / Collapse (Clause 8)",
            "#065F46",
            [
                (r"\sigma_z = \frac{F_a}{A_n} \;\; \text{(bending excluded)}, \quad Y_{pa} = \left[\sqrt{1 - 0.75\left(\tfrac{\sigma_z}{Y_p}\right)^2} - 0.5\left(\tfrac{\sigma_z}{Y_p}\right)\right] Y_p", "Uniform axial stress only, then the equivalent yield it implies"),
                (r"\left(\tfrac{D}{t}\right)_{yp} = \frac{\sqrt{(A-2)^2 + 8\left(B + \tfrac{C}{Y_{pa}}\right)} + (A-2)}{2\left(B + \tfrac{C}{Y_{pa}}\right)}", "First regime boundary; A, B, C, F, G are all functions of Y_pa"),
                (r"P_c = \begin{cases} 2 Y_{pa}\left[\tfrac{D/t - 1}{(D/t)^2}\right] & \text{Yield} \\[4pt] Y_{pa}\left[\tfrac{A}{D/t} - B\right] - C & \text{Plastic} \\[4pt] Y_{pa}\left[\tfrac{F}{D/t} - G\right] & \text{Transition} \\[4pt] \dfrac{46.95 \times 10^6}{(D/t)\left(D/t - 1\right)^2} & \text{Elastic} \end{cases}", "Four-regime cascade, selected by D/t against the boundaries"),
                (r"P_{c,corr} = P_c + P_i, \quad SF_{collapse} = \frac{P_{c,corr}}{P_{ext,design}} \ge 1.10", "Internal pressure backs up the wall; margin against collapse"),
            ],
            f"Determines the {term('collapse', 'collapse')} pressure the candidate can withstand, accounting for "
            f"how axial load shifts the stress state. Axial tension <b>reduces</b> collapse capacity via "
            f"<i>Y<sub>pa</sub></i>; compression raises it. Per the standard, {term('dogleg', 'bending')} stress "
            f"is <b>excluded</b> here &mdash; only the uniform axial load stress enters <i>Y<sub>pa</sub></i>. "
            f"The empirical constants are dimensional, so this module always computes natively in psi. "
            f"Validated against published API Bul&nbsp;5C2 collapse ratings to within 0.1%.",
            [
                ("P<sub>c,corr</sub>", "Corrected collapse limit, with <i>P<sub>i</sub></i> back-up credit", "psi"),
                ("Y<sub>pa</sub>", "Axial-stress equivalent yield strength", "psi"),
                ("&sigma;<sub>z</sub>", "Uniform axial stress <i>F<sub>a</sub></i>/<i>A<sub>n</sub></i> &mdash; <b>no bending</b>", "psi"),
                ("D/t", "Diameter-to-thickness ratio", "dimensionless"),
                ("A, B, C, F, G", "API empirical constants, all functions of <i>Y<sub>pa</sub></i>", "at 80 ksi: 3.071, 0.0667, 1955"),
                ("Regime", "Yield &rarr; Plastic &rarr; Transition &rarr; Elastic cascade", "reported per candidate"),
                ("SF<sub>collapse</sub>", "Collapse safety factor", "target &ge; 1.10"),
            ],
            "Rejects a candidate whose <i>SF<sub>collapse</sub></i> &lt; 1.10 against the APB-augmented external pressure. Calculation is terminated with an explicit error when &sigma;<sub>z</sub> &ge; <i>Y<sub>p</sub></i> (structural yielding in axial tension precedes collapse), when tension drives <i>Y<sub>pa</sub></i> below the validity floor of the API curve fits, or for cold-expanded pipe, where the Bauschinger effect invalidates these equations entirely.",
        )

    st.markdown('<div id="step-7"></div>', unsafe_allow_html=True)
    with st.expander("Step 7  ·  Shut-In CITHP Surface Burst, NACE Sour & Connection Gate   —   Domain C", expanded=(active_step == 7)):
        formula_card(
            "7.1",
            "Static CITHP Surface Burst Check",
            "#5B21B6",
            [
                (r"\text{CITHP} = P_{bhp} \cdot e^{-\left(\frac{M \cdot TVD}{Z \cdot R \cdot T_{avg}}\right)}", "Surface pressure once the well is shut in"),
                (r"SF_{burst} = \frac{\text{Candidate Burst Limit [psi]}}{\text{CITHP [psi]}} \ge 1.10", "Margin against rupture"),
            ],
            f"Checks the worst internal-pressure case. When a gas well is shut in, the light gas column adds almost no weight, so {term('cithp')} at surface approaches reservoir pressure. This verifies the candidate’s {term('burst', 'burst rating')} keeps a {term('safety-factor')} of at least 1.10 against that.",
            [
                ("CITHP", "Closed-in tubing head pressure at surface", "psi"),
                ("M", "Gas molecular weight, SG<sub>g</sub> × 28.97", "lbm/lb-mol"),
                ("R", "Universal gas constant", "10.731 psi&middot;ft<sup>3</sup>/(lb-mol&middot;&deg;R)"),
                ("SF<sub>burst</sub>", "Surface burst safety factor", "target &ge; 1.10"),
            ],
            "Rejects a candidate failing the static surface burst factor (<i>SF<sub>burst</sub></i> &lt; 1.10), which risks wellhead rupture during shut-in.",
        )

        formula_card(
            "7.2",
            "NACE MR0175 Sour Service &amp; Premium Connection Logic",
            "#5B21B6",
            [
                (r"p_{H_2S} = P_{bhp} \times \left( \frac{\text{H}_2\text{S [PPM]}}{10^6} \right) \ge 0.05 \text{ psia}", "H<sub>2</sub>S partial pressure against the NACE sour threshold"),
            ],
            f"Applies the environmental and mechanical gates. The {term('partial-pressure')} of H<sub>2</sub>S decides whether {term('sour', 'sour service')} rules apply; above 0.05 psia, {term('nace')} caps hardness at 26 HRC or mandates a {term('cra')}. Separately, high gas rate, APB, depth or CRA metallurgy force a {term('premium-connection')} for gas-tight sealing.",
            [
                ("p<sub>H<sub>2</sub>S</sub>", "Partial pressure of hydrogen sulphide", "psia"),
                ("H<sub>2</sub>S", "Concentration in the produced gas stream", "PPM"),
                ("T<sub>max,grade</sub>", "Max continuous service temperature per grade", "13Cr 150 &rarr; 25Cr 250 &deg;C"),
                ("Premium triggers", "Gas well, GOR &gt; 2000, Q<sub>g</sub> &gt; 10 MMscf/D, CITHP &gt; 3000 psi, &Delta;P<sub>APB</sub> &gt; 1500 psi, depth &gt; 10,000 ft, or CRA", "any one applies"),
            ],
            "Rejects non-NACE-compliant grades under sour service (<i>p<sub>H<sub>2</sub>S</sub></i> &ge; 0.05 psia), grades whose maximum service temperature is below bottomhole temperature, and standard API EUE threads where gas-tight premium connections are required.",
        )

    st.markdown("""
<div style="background-color: #FFEDD5; border-left: 6px solid #EA580C; padding: 0.75rem 1rem; border-radius: 6px; margin: 1.5rem 0 1.25rem;">
    <h2 style="color: #9A3412; font-size: 1.45rem; margin: 0; font-weight: 700;">Domain D: Product Specification &amp; Mill Acceptance</h2>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div id="step-8"></div>', unsafe_allow_html=True)
    with st.expander("Step 8  ·  API 5CT / ISO 11960 Product Specification Verification   —   Domain D", expanded=(active_step == 8)):
        st.markdown(
            '<div style="background-color: #FFF7ED; border-left: 4px solid #EA580C; padding: 0.7rem 1rem; '
            'border-radius: 5px; margin-bottom: 1rem; font-size: 0.9rem; color: #7C2D12;">'
            '<b>These are manufacturing requirements, not well-load capacities.</b> Steps 1&ndash;7 ask whether the '
            'pipe can survive the well. Step 8 asks a different question: what the mill had to demonstrate before the '
            'joint was ever shipped. Of the four, only the hydrostatic proof test screens a candidate out &mdash; '
            'operating above the pressure at which a joint was proved sound is a design deficiency. The other three '
            'are reported requirements that belong in the purchase specification and the mill certificate review.'
            '</div>',
            unsafe_allow_html=True,
        )

        formula_card(
            "8.1",
            "Minimum Tensile Gauge-Length Elongation (Ductility)",
            "#9A3412",
            [
                (r"e = C \cdot \frac{A^{0.2}}{U^{0.9}}", "Minimum elongation in a 50.8 mm (2.0 in) gauge length"),
                (r"C = 625{,}000 \;\; (A\,[\text{in}^2],\, U\,[\text{psi}]) \qquad C = 1944 \;\; (A\,[\text{mm}^2],\, U\,[\text{MPa}])", "The constant absorbs the units, so it is not a free parameter"),
                (r"A = \min\left(A_{\text{physical}},\; 490\,\text{mm}^2 \;/\; 0.75\,\text{in}^2\right)", "Area cap: a larger specimen earns no relief"),
            ],
            f"Sets the {term('elongation', 'ductility')} floor the material must clear. Strength alone is not "
            f"sufficient: a pipe meeting its {term('smys', 'yield')} and tensile numbers but failing elongation will "
            f"fracture rather than deform when overloaded, giving no warning. Note the <b>negative power on "
            f"<i>U</i></b> &mdash; the stronger the grade, the less elongation is demanded of it, which is why a Q125 "
            f"requirement sits well below an H40 one. Specimen geometry is selected automatically from the wall "
            f"thickness: the largest permissible round bar, or a strip when the wall is too thin to machine one.",
            [
                ("e", "Minimum elongation in a 2 in gauge length", "%"),
                ("A", "Specimen cross-sectional area, capped", "in<sup>2</sup> or mm<sup>2</sup>"),
                ("U", "Minimum specified tensile strength", "L80 = 95,000 psi"),
                ("Round bar", "Fixed area: 130 mm<sup>2</sup> (12.7 mm dia) or 62 mm<sup>2</sup> (8.9 mm dia)", "prohibited on thin walls"),
                ("Strip", "<i>A</i> = wall &times; 38.1 mm standard reduced-section width", "the thin-wall fallback"),
                ("Rounding", "Nearest 0.5% below 10%; nearest 1% at or above", "tested on the unrounded value"),
            ],
            "<b>Reported, not a rejection criterion.</b> This is the acceptance requirement the mill certificate must evidence for the grade and wall supplied. An explicitly requested round bar the wall cannot produce is refused outright rather than silently substituted.",
        )

        formula_card(
            "8.2",
            "Production Hydrostatic Proof-Test Pressure &mdash; Screening Gate",
            "#9A3412",
            [
                (r"P = \frac{2 \cdot Y_S \cdot f \cdot t}{D}", "Mill proof-test pressure for each individual joint"),
                (r"f = 0.80 \;\; \text{(default)}, \qquad f = 0.60 \;\; \text{for H40 / J55 / K55 with } D > 9\tfrac{5}{8}\,\text{in}", "Design stress factor; 0.80 is a permitted alternative in the 0.60 case"),
                (r"P \le 69.0\,\text{MPa}\;(10{,}000\,\text{psi}) \quad\Rightarrow\quad \text{else flag ``Alternative Test Pressures''}", "The cap flags a specially agreed test; it does not lower P"),
                (r"P \leftarrow \min\left(P,\; P_{\text{thread leak}}\right), \qquad P_{\text{floor}} = 20.5\,\text{MPa}\;(3{,}000\,\text{psi})", "Connection override and the minimum mill testing floor"),
            ],
            f"The {term('hydro-test', 'proof test')} every joint is held at before shipment, as a fixed fraction of "
            f"{term('smys', 'yield')}. This is the one Step 8 check that <b>screens candidates out</b>: it is a proof "
            f"of integrity for that specific joint, so a string expected to see a shut-in {term('cithp')} above the "
            f"pressure at which it was proved sound is a genuine design deficiency. Caps are applied in specification "
            f"order and rounding happens <b>last</b>, so it never moves a value back across a threshold it has just "
            f"been checked against. Where a connection is weaker than the pipe body, the thread leak / jump-out "
            f"pressure governs &mdash; but that rating is only applied when supplied, never invented.",
            [
                ("P", "Hydrostatic proof-test pressure", "psi or MPa"),
                ("Y<sub>S</sub>", "Specified minimum yield strength", "L80 = 80,000 psi"),
                ("f", "Design stress factor", "0.80, or 0.60 for large low-grade"),
                ("t, D", "Specified nominal wall and outside diameter", "in or mm"),
                ("Cap behaviour", "Above 10,000 psi the value is <b>flagged, not clamped</b>", "a lower test would not be equivalent"),
                ("Mill floor", "Below 3,000 psi flagged; raised only on request", "over-testing is the user's call"),
                ("Rounding", "Nearest 100 psi or 0.5 MPa", "applied last"),
            ],
            "<b>Rejects</b> a candidate whose proof-test pressure falls below the shut-in CITHP the string must hold &mdash; the joint would be operated above the pressure at which its integrity was demonstrated. Exceeding the 10,000 psi cap is <i>flagged</i> rather than rejected: it means a specially agreed test is required, not that the pipe is unsuitable.",
        )

        formula_card(
            "8.3",
            "Charpy V-Notch Minimum Absorbed Energy (Toughness)",
            "#9A3412",
            [
                (r"\text{transverse:} \quad CVN_{\text{full}} = Y \cdot \left(0.00118\,t + 0.01288\right) + 2.04", "Y in MPa, t in mm, result in J"),
                (r"\text{longitudinal:} \quad CVN_{\text{full}} = Y \cdot \left(0.00236\,t + 0.02576\right) + 4.08", "Exactly twice the transverse coefficient set"),
                (r"Y = Y_S \;\text{(pipe body)}, \qquad Y = Y_{S,\max} \;\text{(coupling)}", "The coupling is rated on specified MAXIMUM yield"),
                (r"CVN_{\text{required}} = CVN_{\text{full}} \cdot f_{\text{sub}}, \qquad f_{\text{sub}} \in \{1.0,\; 0.75,\; 0.50\}", "Sub-size specimen scaling, then an 11 J (8 ft-lb) absolute floor"),
            ],
            f"Sets the {term('charpy', 'toughness')} floor: resistance to brittle fracture from an existing flaw. A "
            f"pipe can be strong and perfectly {term('elongation', 'ductile')} in a smooth tensile test and still "
            f"shatter at a notch under impact. The critical detail is that <b>couplings are rated on specified "
            f"<i>maximum</i> yield</b>, not minimum &mdash; the hardest coupling the specification permits is the "
            f"safety-critical case, since hardness and toughness trade off against each other. That differential is "
            f"why the coupling requirement always exceeds the pipe-body one for the same geometry.",
            [
                ("Y<sub>S</sub>", "Pipe body: specified <i>minimum</i> yield", "L80 = 80,000 psi"),
                ("Y<sub>S,max</sub>", "Coupling: specified <i>maximum</i> yield", "L80 = 95,000 psi"),
                ("t", "Critical wall thickness", "mm or in"),
                ("Full-size floor", "Transverse 20 J / longitudinal 41 J for P110, Q125, C110", "14 J / 27 J other Q&amp;T"),
                ("f<sub>sub</sub>", "1.0 full (10&times;10 mm), 0.75 (10&times;7.5), 0.50 (10&times;5)", "applied after the grade floor"),
                ("Absolute floor", "Sub-size requirement never below 11 J (8 ft-lb)", "applied last"),
                ("Waive condition", "Wall too thin for a &frac12;-size longitudinal specimen", "QA process check instead"),
            ],
            "<b>Reported, not a rejection criterion.</b> Non-Q&amp;T grades (H40, J55, K55, M65) carry no floor class and are reported on the computed value alone. Where the wall cannot produce even a half-size longitudinal specimen, physical testing is waived and a QA manufacturing process check is flagged in its place &mdash; the candidate is not penalised for a geometry the test regime cannot accommodate.",
        )

        formula_card(
            "8.4",
            "As-Quenched Hardenability &amp; Martensite Fraction",
            "#9A3412",
            [
                (r"\text{C90, T95} \;\;(\ge 90\%\ \text{martensite}): \quad HRC_{\min} = 58\,C + 17.2", None),
                (r"\text{C110} \;\;(\ge 95\%\ \text{martensite}): \quad HRC_{\min} = 59\,C + 18.2", None),
                (r"\text{other Q\&T} \;\;(\ge 50\%\ \text{martensite}): \quad HRC_{\min} = 52\,C + 14.0", None),
                (r"0.15 \le C \le 0.50\ \text{wt\%}", "Validity range of the correlations"),
            ],
            f"Verifies that quenching actually produced the {term('martensite', 'martensite fraction')} the grade "
            f"depends on, <b>before</b> tempering brings the hardness back down &mdash; once tempered, the evidence is "
            f"gone. The measurement must be taken at <b>mid-wall</b>, the position of maximum section thickness: that "
            f"is the location that cools slowest and is therefore the least martensitic, so it is the only one that "
            f"proves hardening through the full section. The three coefficient pairs correspond to three different "
            f"martensite targets, which is why C90 and C110 &mdash; both {term('sour', 'sour-service')} grades &mdash; "
            f"sit well above the general Q&amp;T requirement.",
            [
                ("HRC<sub>min</sub>", "Required minimum as-quenched Rockwell C hardness", "before tempering"),
                ("C", "Carbon content by weight", "<b>whole %</b>: enter 0.25 for 0.25%, not 0.0025"),
                ("Evaluation depth", "Mid-wall &mdash; the slowest-quenching location", "governs through-wall hardening"),
                ("Validity", "0.15 &le; C &le; 0.50 wt%", "outside this the correlation is refused"),
                ("Applicability", "Quenched &amp; tempered carbon / low-alloy grades only", "CRAs have no martensite target"),
            ],
            "<b>Reported, not a rejection criterion.</b> CRA grades (13Cr, 22Cr, 25Cr) and non-Q&amp;T grades return <i>not applicable</i> with a stated reason rather than an error &mdash; a solution-annealed duplex has no as-quenched martensite target, and that is not a fault in the candidate. Carbon outside the 0.15&ndash;0.50 wt% validity range is refused outright, with an explicit hint when the value looks like a mass fraction rather than a percentage.",
        )

    st.markdown("---")
    with st.expander("📘 Full glossary — every highlighted term on this page", expanded=False):
        st.markdown(
            "".join(
                f'<div style="padding: 0.5rem 0; border-bottom: 1px solid #EEF2F6;">'
                f'<b style="color: #1D4ED8;">{title}</b><br/>'
                f'<span style="font-size: 0.88rem; color: #334155; line-height: 1.6;">{body}</span></div>'
                for title, body in sorted(GLOSSARY.values())
            ),
            unsafe_allow_html=True,
        )

# -----------------------------------------------------------------------------
# 7: WELLBORE & DUAL-LIFECYCLE OPERATIONAL INPUTS
# -----------------------------------------------------------------------------
elif page == "7. Well & Fluid Inputs":
    st.markdown('<div class="main-header">Step 7: Wellbore Geometry & Operational Inputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Specify wellbore profile, environmental chemistry, solid particles production, rate modes, and dual-lifecycle operational envelopes.</div>', unsafe_allow_html=True)

    current_inputs = st.session_state.inputs
    well_type = current_inputs.get('well_type', 'Oil Well (Liquid Dominated)')
    is_gas_type = "Gas" in well_type

    tab_geo, tab_early, tab_late = st.tabs([
        "📐 1. Architecture, PVT & Shut-In CITHP",
        "🚀 2. Early-Life (Initial Production)",
        "📉 3. Late-Life (Depleted Envelopes)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: ARCHITECTURE, PVT, CORROSIVITY & COMPLETION TARGETS
    # -------------------------------------------------------------------------
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
            t_wh = st.number_input("Flowing Wellhead Temperature - WHT (°F)", min_value=32.0, max_value=400.0, value=float(current_inputs.get('t_wh', 150.0)), step=1.0, format="%.3f")
            t_ambient = st.number_input("Ambient / Static Surface Temperature (°F)", min_value=-40.0, max_value=200.0, value=float(current_inputs.get('t_ambient', 75.0)), step=1.0, format="%.3f",
                                        help="Baseline temperature of the trapped annular fluid at installation. The annular temperature rise (and therefore APB and thermal load) is measured from this datum.")

        st.markdown("---")
        st.markdown("#### 🛡️ Completion Targets, Shut-In CITHP & Field Lifespan")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            # Default CITHP from the same barometric gas-column model the engine uses.
            _p_bhp_ref = float(current_inputs.get('p_bhp', 4500.0))
            _gas_sg_ref = float(current_inputs.get('gas_sg', 0.65))
            _t_avg_r_ref = (t_wh + float(current_inputs.get('t_bht', 210.0))) / 2.0 + 459.67
            try:
                _z_ref = compute_dynamic_z_factor(
                    (float(current_inputs.get('p_wh', 800.0)) + _p_bhp_ref) / 2.0 + 14.7,
                    _t_avg_r_ref, _gas_sg_ref
                )
                calc_cithp = round(static_cithp_psi(_p_bhp_ref, tvd, _gas_sg_ref, _z_ref, _t_avg_r_ref), 1)
            except ValueError:
                calc_cithp = round(_p_bhp_ref * 0.6, 1)
            cithp_input = st.number_input("Closed-In Tubing Head Pressure - CITHP (psi)", min_value=0.0, max_value=25000.0, value=float(current_inputs.get('cithp') or calc_cithp), step=50.0, format="%.3f",
                                          help=f"Barometric dry-gas column model gives {calc_cithp} psi for the current BHP, TVD and gas gravity. Override with a measured value if available.")
            field_life = st.number_input("Target Field / Completion Lifespan (Years)", min_value=1, max_value=50, value=int(current_inputs.get('field_life_yrs', 20)), step=1)

        with col_s2:
            sf_triaxial = st.number_input("Min Triaxial Safety Factor", min_value=1.0, max_value=2.5, value=float(current_inputs.get('sf_triaxial', 1.25)), step=0.05, format="%.3f")
            decline_rate = st.number_input("Annual Field Decline Rate (%)", min_value=0.0, max_value=30.0, value=float(current_inputs.get('decline_rate', 8.0)), step=0.5, format="%.3f")
            apb_limit = st.number_input("Max Allowable APB Rise (psi)", min_value=100.0, max_value=10000.0, value=float(current_inputs.get('apb_limit_psi', 1500.0)), step=100.0, format="%.3f",
                                        help="Candidates are rejected when the calculated trapped-annulus pressure rise exceeds this collapse-margin limit.")

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
            lith_options = ["Sandstone (C=120)", "Carbonate / Unconsolidated (C=150)"]
            curr_lith = current_inputs.get('lithology', lith_options[0])
            lithology = st.selectbox("Reservoir Lithology", lith_options,
                                     index=lith_options.index(curr_lith) if curr_lith in lith_options else 0)
            sand_sg = st.number_input("Solid Particle Density (SG)", min_value=1.5, max_value=5.0, value=float(current_inputs.get('sand_sg', 2.65)), step=0.05, format="%.3f")

    # -------------------------------------------------------------------------
    # TAB 2: EARLY-LIFE (INITIAL PRODUCTION ENVELOPE)
    # -------------------------------------------------------------------------
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

# -------------------------------------------------------------------------
    # TAB 3: LATE-LIFE (DEPLETED / HIGH WATER CUT ENVELOPES)
    # -------------------------------------------------------------------------
    with tab_late:
        st.markdown("#### Late-Life Operating Conditions (Depletion & High Water Cut)")
        
        # Action columns: Manual Override toggle & Copy Early-Life button
        col_ctrl1, col_ctrl2 = st.columns([1.5, 1.0])
        
        with col_ctrl1:
            manual_override = st.checkbox(
                "🛠️ Enable Manual Override for Late-Life Parameters", 
                value=st.session_state.inputs.get('manual_override_late', False)
            )
            
        with col_ctrl2:
            if st.button("📋 Same as Initial Parameters (Early Life)", use_container_width=True):
                # Enable manual override and copy early-life values into late-life session state
                st.session_state.inputs['manual_override_late'] = True
                st.session_state.inputs['p_bhp_late'] = p_bhp_early
                st.session_state.inputs['p_wh_late'] = p_wh_early
                st.session_state.inputs['bht_late'] = bht_early
                
                if "Gas" in well_type:
                    st.session_state.inputs['q_gas_late'] = q_gas_early
                    st.session_state.inputs['cgr_late'] = cgr_early
                    st.session_state.inputs['wgr_late'] = wgr_early
                else:
                    st.session_state.inputs['q_liq_late'] = q_liq_early
                    st.session_state.inputs['wc_late'] = wc_early
                    st.session_state.inputs['gor_late'] = gor_early
                    
                st.success("Copied Early-Life parameters to Late-Life!")
                st.rerun()

        # Auto-Predictive Calculation Logic
        pred_p_bhp_late = float(round(p_bhp_early * 0.50, 3))
        pred_p_wh_late = float(round(p_wh_early * 0.40, 3))
        pred_bht_late = float(round(max(80.0, bht_early - 30.0), 3))
        
        if "Gas" in well_type:
            pred_q_gas_late = float(round(q_gas_early * ((1.0 - decline_rate / 100.0) ** field_life), 3))
            pred_cgr_late = float(round(cgr_early * 0.60, 3))
            pred_wgr_late = float(round(wgr_early * 2.50, 3))
        else:
            pred_q_liq_late = float(round(q_liq_early * ((1.0 - decline_rate / 100.0) ** field_life), 3))
            pred_wc_late = 75.0 if wc_early < 20.0 else float(round(min(95.0, wc_early + 30.0), 3))
            pred_gor_late = float(round(gor_early * 0.60, 3))

        col_l1, col_l2, col_l3 = st.columns(3)
        if not manual_override:
            st.info("💡 **Auto-Predictive Engine Active:** Late-Life parameters are estimated using annual field decline rates and reservoir depletion rules. Enable manual override or click the button above to copy initial parameters.")
            with col_l1:
                p_bhp_late = st.number_input("Late BHP (psi)", value=float(current_inputs.get('p_bhp_late', pred_p_bhp_late)), disabled=True, format="%.3f")
                p_wh_late = st.number_input("Late Wellhead Pressure (psi)", value=float(current_inputs.get('p_wh_late', pred_p_wh_late)), disabled=True, format="%.3f")
            with col_l2:
                if "Gas" in well_type:
                    q_gas_late = st.number_input("Late Gas Rate (MMscf/D)", value=float(current_inputs.get('q_gas_late', pred_q_gas_late)), disabled=True, format="%.3f")
                    cgr_late = st.number_input("Late CGR (STB/MMscf)", value=float(current_inputs.get('cgr_late', pred_cgr_late)), disabled=True, format="%.3f")
                    q_liq_late, wc_late, gor_late = 0.0, 0.0, 0.0
                else:
                    q_liq_late = st.number_input("Late Liquid Rate (STB/D)", value=float(current_inputs.get('q_liq_late', pred_q_liq_late)), disabled=True, format="%.3f")
                    wc_late = st.number_input("Late Water Cut (%)", value=float(current_inputs.get('wc_late', pred_wc_late)), disabled=True, format="%.3f")
                    q_gas_late, cgr_late, wgr_late = 0.0, 0.0, 0.0
            with col_l3:
                if "Gas" in well_type:
                    wgr_late = st.number_input("Late WGR (bbl/MMscf)", value=float(current_inputs.get('wgr_late', pred_wgr_late)), disabled=True, format="%.3f")
                else:
                    gor_late = st.number_input("Late Producing GOR (scf/STB)", value=float(current_inputs.get('gor_late', pred_gor_late)), disabled=True, format="%.3f")
                bht_late = st.number_input("Late Bottomhole Temp - BHT (°F)", value=float(current_inputs.get('bht_late', pred_bht_late)), disabled=True, format="%.3f")
        else:
            with col_l1:
                p_bhp_late = st.number_input("Late BHP (psi)", min_value=100.0, max_value=20000.0, value=float(current_inputs.get('p_bhp_late', pred_p_bhp_late)), step=50.0, format="%.3f")
                p_wh_late = st.number_input("Late Wellhead Pressure (psi)", min_value=20.0, max_value=5000.0, value=float(current_inputs.get('p_wh_late', pred_p_wh_late)), step=20.0, format="%.3f")
            with col_l2:
                if "Gas" in well_type:
                    q_gas_late = st.number_input("Late Gas Rate (MMscf/D)", min_value=0.1, max_value=200.0, value=float(current_inputs.get('q_gas_late', pred_q_gas_late)), step=0.5, format="%.3f")
                    cgr_late = st.number_input("Late CGR (STB/MMscf)", min_value=0.0, max_value=500.0, value=float(current_inputs.get('cgr_late', pred_cgr_late)), step=1.0, format="%.3f")
                    q_liq_late, wc_late, gor_late = 0.0, 0.0, 0.0
                else:
                    q_liq_late = st.number_input("Late Liquid Rate (STB/D)", min_value=50.0, max_value=50000.0, value=float(current_inputs.get('q_liq_late', pred_q_liq_late)), step=100.0, format="%.3f")
                    wc_late = st.number_input("Late Water Cut (%)", min_value=0.0, max_value=100.0, value=float(current_inputs.get('wc_late', pred_wc_late)), step=0.5, format="%.3f")
                    q_gas_late, cgr_late, wgr_late = 0.0, 0.0, 0.0
            with col_l3:
                if "Gas" in well_type:
                    wgr_late = st.number_input("Late WGR (bbl/MMscf)", min_value=0.0, max_value=200.0, value=float(current_inputs.get('wgr_late', pred_wgr_late)), step=0.5, format="%.3f")
                else:
                    gor_late = st.number_input("Late Producing GOR (scf/STB)", min_value=0.0, max_value=20000.0, value=float(current_inputs.get('gor_late', pred_gor_late)), step=50.0, format="%.3f")
                bht_late = st.number_input("Late Bottomhole Temp - BHT (°F)", min_value=80.0, max_value=400.0, value=float(current_inputs.get('bht_late', pred_bht_late)), step=1.0, format="%.3f")

    # -------------------------------------------------------------------------
    # DUAL OPERATIONAL ENVELOPE SUMMARY MATRIX
    # -------------------------------------------------------------------------
    st.markdown("### 📊 Dual Operational Envelope Summary")

    if "Gas" in well_type:
        rate_summary_early = f"{q_gas_early:.2f} MMscf/D ({cgr_early:.1f} CGR)"
        rate_summary_late = f"{q_gas_late:.2f} MMscf/D ({cgr_late:.1f} CGR)"
        ratio_summary_early = f"{wgr_early:.1f} bbl/MMscf WGR"
        ratio_summary_late = f"{wgr_late:.1f} bbl/MMscf WGR"
        governing_msg = "Salama sand erosion v_m < v_eros (Early) vs. Solid transport v_m > v_carrying (Late)"
    else:
        rate_summary_early = f"{q_liq_early:.1f} STB/D ({wc_early:.1f}% WC)"
        rate_summary_late = f"{q_liq_late:.1f} STB/D ({wc_late:.1f}% WC)"
        ratio_summary_early = f"{gor_early:.1f} scf/STB GOR"
        ratio_summary_late = f"{gor_late:.1f} scf/STB GOR"
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
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{p_bhp_late:.1f} psi</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Peak H₂S partial pressure (Early) vs. Drawdown head limit (Late)</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;">
                <td style="padding: 10px; font-weight: 600;">Wellhead Pressure (P<sub>wh</sub>)</td>
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{p_wh_early:.1f} psi</td>
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{p_wh_late:.1f} psi</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">High tubing pressure safety (Early) vs. Minimum surface arrival pressure (Late)</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0;">
                <td style="padding: 10px; font-weight: 600;">Flow Rate & Sand PPTB</td>
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{rate_summary_early} | Sand: {sand_rate_pptb} PPTB</td>
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{rate_summary_late}</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">{governing_msg}</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0; background-color: #F8FAFC;">
                <td style="padding: 10px; font-weight: 600;">Producing Ratios</td>
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{ratio_summary_early}</td>
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{ratio_summary_late}</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Multiphase fluid density homogenization (&rho;<sub>m</sub>)</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0;">
                <td style="padding: 10px; font-weight: 600;">Bottomhole Temp (BHT)</td>
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{bht_early:.1f} °F</td>
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{bht_late:.1f} °F</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Thermal expansion & APB load (Early) vs. Tubing cooling contraction (Late)</td>
            </tr>
            <tr style="background-color: #F8FAFC;">
                <td style="padding: 10px; font-weight: 600;">Shut-In CITHP</td>
                <td style="padding: 10px; color: #1E3A8A; font-weight: 600;">{cithp_input:.1f} psi</td>
                <td style="padding: 10px; color: #B45309; font-weight: 600;">{(cithp_input * 0.7):.1f} psi</td>
                <td style="padding: 10px; font-size: 0.82rem; color: #475569;">Static surface pipe burst safety factor (SF_burst &ge; 1.10)</td>
            </tr>
        </tbody>
    </table>
    """

    st.markdown(summary_html, unsafe_allow_html=True)
    st.markdown("<br/>", unsafe_allow_html=True)

    # Automatically persist all inputs to session state on render
    st.session_state.inputs.update({
        "well_type": well_type,
        "tvd": tvd, "md": md, "dls": dls, "casing_id": casing_id,
        "t_wh": t_wh, "t_ambient": t_ambient,
        "cithp": cithp_input, "sf_triaxial": sf_triaxial, "annular_fluid": annular_fluid,
        "apb_limit_psi": apb_limit,
        "field_life_yrs": field_life, "decline_rate": decline_rate,
        "api_gravity": api_gravity, "gas_sg": gas_sg, "water_sg": water_sg, "oil_visc": oil_visc,
        "h2s_ppm": h2s_ppm, "co2_mole_pct": co2_pct, "ph_val": ph_val, "chlorides_ppm": chlorides_ppm,
        "sand_rate_pptb": sand_rate_pptb, "sand_size_microns": sand_size_microns, "sand_sg": sand_sg,
        "lithology": lithology,
        "p_bhp": p_bhp_early, "p_wh": p_wh_early, "t_bht": bht_early,
        "p_bhp_late": p_bhp_late, "p_wh_late": p_wh_late, "bht_late": bht_late,
        "manual_override_late": manual_override
    })
    if "Gas" in well_type:
        st.session_state.inputs.update({
            "q_gas_mmscfd": q_gas_early, "cgr_stb_mmscf": cgr_early, "wgr_bbl_mmscf": wgr_early,
            "q_gas_late": q_gas_late, "cgr_late": cgr_late, "wgr_late": wgr_late
        })
    else:
        st.session_state.inputs.update({
            "q_liquid": q_liq_early, "water_cut": wc_early, "gor": gor_early,
            "q_liq_late": q_liq_late, "wc_late": wc_late, "gor_late": gor_late
        })

    # -------------------------------------------------------------------------
    # ACTION BUTTON: SAVE & RUN MODEL
    # -------------------------------------------------------------------------
    _, col_btn_mid, _ = st.columns([1, 2, 1])
    with col_btn_mid:
        if st.button("💾 Save Operational Baseline & Lifecycle State", type="primary", use_container_width=True):
            st.success("✅ Operational inputs saved! Proceed to Page 9 to view candidate screening calculations.")

# -----------------------------------------------------------------------------
# 8: CANDIDATE TUBING SPECS
# -----------------------------------------------------------------------------
elif page == "8. Candidate Tubing Specs":
    st.markdown('<div class="main-header">Step 8: Candidate Tubing Database</div>', unsafe_allow_html=True)
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

    # The filtered set is what Pages 9 and 10 screen, so persist it.
    st.session_state.candidate_filter = {"od": list(selected_sizes), "grade": list(selected_grades)}

    if filtered_db.empty:
        st.warning("No candidates match the current filters. Pages 9 and 10 need at least one candidate to screen.")
    else:
        st.caption(f"**{len(filtered_db)}** of {len(st.session_state.tubing_db)} candidates selected — Pages 9 and 10 screen exactly this filtered set.")

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
# 9: ENGINEERING CALCULATIONS
# -----------------------------------------------------------------------------
elif page == "9. Engineering Calculations":
    st.markdown('<div class="main-header">Step 9: Engineering Calculation Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluates dynamic PVT, pressure losses, velocity screening, APB, static CITHP burst, and Lubinski stress.</div>', unsafe_allow_html=True)
    
    candidates = active_candidate_df()
    if candidates.empty:
        st.warning("No tubing candidates are selected. Adjust the OD/grade filters on Page 8.")
        st.stop()
        
    try:
        res_df = engineering_results(st.session_state.inputs, candidates)
    except ValueError as error:
        st.error(f"Input validation failed: {error}")
        st.stop()
        
    st.caption(f"Screening **{len(candidates)}** candidate(s) from the Page 8 filter selection.")
    
    # --- Main Candidate Screening Matrix ---
    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs.get('well_type', 'Oil Well')} Mode)")
    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts', 'v_carrying', 'v_carrying_late', 'v_erosional',
        'dp_total_psi', 'dp_apb_psi', 'cithp_psi', 'f_axial_klbs', 'f_axial_rating_klbs', 'vme_stress_psi', 'triaxial_sf',
        'p_rupture_psi', 'rupture_sf', 'rupture_mode', 'p_collapse_psi', 'collapse_sf', 'collapse_regime', 'burst_sf',
        'p_test_psi', 'hydro_test_sf',
        'friction_factor', 'cv_solids', 'Z_Factor', 'max_service_temp_c', 'Material_Reason', 'Temp_Reason', 'Overall_Pass'
    ]].copy()
    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)', 'Min Carrying Vel (ft/s)', 'Late Carrying Vel (ft/s)', 'Erosional Limit (ft/s)',
        'Total dP (psi)', 'APB Pressure (psi)', 'CITHP (psi)', 'Axial Load (klbs)', 'Axial Rating (klbs)', 'von Mises Stress (psi)', 'Triaxial SF',
        'Rupture Capacity (psi)', 'Rupture SF', 'Rupture Mode', 'Collapse Capacity (psi)', 'Collapse SF', 'Collapse Regime', 'Burst SF',
        'Proof Test (psi)', 'Proof Test SF',
        'Friction f', 'Sand Cv', 'Z-Factor', 'Max Service T (°C)', 'NACE Status', 'Temp Status', 'Overall Status'
    ]
    
    styled_display_df = display_df.style.apply(highlight_passing_row_matrix, axis=1)
    st.dataframe(
        styled_display_df,
        use_container_width=True,
        height=400,
        column_config={
            "Tubing Candidate": st.column_config.TextColumn(pinned=True)
        }
    )

    candidate_list = res_df['Name'].tolist()

    # -----------------------------------------------------------------------------
    # 1. SCREENING GATE DETAIL & REJECTED REASONS (WITH USER INPUT SELECTOR)
    # -----------------------------------------------------------------------------
    st.subheader("1. Screening Gate Detail & Failed Reasons")
    
    gate_cols = [
        ('Casing_Clearance_Pass', 'Casing Clearance'), ('PVT_Pass', 'PVT / Z-Factor'),
        ('Solids_Pass', 'Sand Concentration'), ('Hydraulics_Pass', 'Hydraulics'),
        ('Friction_Pass', 'Friction Factor'), ('Velocity_Pass', 'Velocity Window'),
        ('Late_Life_Pass', 'Late-Life Velocity'), ('Stress_Pass', 'Triaxial Stress'),
        ('Axial_Pass', 'Axial Load'), ('Burst_Pass', 'Surface Burst'),
        ('Rupture_Pass', 'Ductile Rupture (5C3 Cl.7)'), ('Collapse_Pass', 'Collapse (5C3 Cl.8)'),
        ('Hydro_Pass', 'Hydro Proof Test (5CT)'),
        ('APB_Pass', 'APB Limit'), ('Temp_Pass', 'Temperature'),
        ('Material_Pass', 'NACE Sour'), ('Connection_Pass', 'Connection')
    ]
    gate_df = res_df[['Name'] + [col for col, _ in gate_cols]].copy()
    gate_df.columns = ['Tubing Candidate'] + [label for _, label in gate_cols]
    styled_gate_df = gate_df.style.apply(highlight_passing_row_gates, axis=1)
    
    st.dataframe(styled_gate_df, use_container_width=True, height=250)

    st.markdown("##### 🔍 Inspection: Rejected Reasons for Selected Candidate")
    selected_gate_cand = st.selectbox(
        "Select candidate to view failed screening reasons:",
        options=candidate_list,
        key="select_gate_cand"
    )
    
    row_gate = res_df[res_df['Name'] == selected_gate_cand].iloc[0]
    
    # Gather all explicit failure messages for the chosen candidate
    rejections = []
    if not row_gate['Casing_Clearance_Pass']:
        rejections.append(f"• **Casing Clearance:** Tubing OD ({row_gate['OD_in']}\") ≥ Casing ID ({st.session_state.inputs.get('casing_id')} harvest limit).")
    if not row_gate['PVT_Pass']:
        rejections.append(f"• **PVT / Z-Factor:** {row_gate['PVT_Reason']}")
    if not row_gate['Solids_Pass']:
        rejections.append(f"• **Sand Concentration:** {row_gate['Solids_Reason']}")
    if not row_gate['Hydraulics_Pass'] or not row_gate['Friction_Pass']:
        rejections.append(f"• **Hydraulics & Friction:** {row_gate['Hydraulics_Reason']}")
    if not row_gate['Velocity_Pass']:
        rejections.append(f"• **Initial Velocity Window:** Velocity ({row_gate['Velocity_fts']} ft/s) outside window [{row_gate['v_carrying']}–{row_gate['v_erosional']} ft/s].")
    if not row_gate['Late_Life_Pass']:
        rejections.append(f"• **Late-Life Velocity:** Velocity ({row_gate['v_late_life_fts']} ft/s) below minimum carrying limit ({row_gate['v_carrying_late']} ft/s).")
    if not row_gate['Stress_Pass']:
        rejections.append(f"• **Triaxial Stress:** Safety Factor ({row_gate['triaxial_sf']}) below target ({st.session_state.inputs.get('sf_triaxial', 1.25)}). Peak stress: {row_gate['vme_stress_psi']} psi.")
    if not row_gate['Axial_Pass']:
        rejections.append(f"• **Axial Load:** {row_gate['Axial_Reason']}")
    if not row_gate['Burst_Pass']:
        rejections.append(f"• **Surface Burst:** Burst Safety Factor ({row_gate['burst_sf']}) below 1.10 target.")
    if not row_gate['Rupture_Pass']:
        rejections.append(f"• **Ductile Rupture (5C3 Cl.7):** {row_gate['Rupture_Reason']}")
    if not row_gate['Collapse_Pass']:
        rejections.append(f"• **Collapse (5C3 Cl.8):** {row_gate['Collapse_Reason']}")
    if not row_gate['Hydro_Pass']:
        rejections.append(f"• **Hydro Proof Test (5CT):** {row_gate['Hydro_Reason']}")
    if not row_gate['APB_Pass']:
        rejections.append(f"• **APB Limit:** {row_gate['APB_Reason']}")
    if not row_gate['Temp_Pass']:
        rejections.append(f"• **Temperature:** {row_gate['Temp_Reason']}")
    if not row_gate['Material_Pass']:
        rejections.append(f"• **NACE Sour Service:** {row_gate['Material_Reason']}")
    if not row_gate['Connection_Pass']:
        rejections.append(f"• **Connection:** {row_gate['Connection_Reason']}")

    if rejections:
        st.error(f"**Rejection Reasons for {selected_gate_cand}:**\n\n" + "\n\n".join(rejections))
    else:
        st.success(f"**{selected_gate_cand}** passed all screening gates with zero failures.")

    st.markdown("---")

    # -----------------------------------------------------------------------------
    # 2. PRODUCT SPECIFICATION ADVISORIES (WITH USER INPUT SELECTOR)
    # -----------------------------------------------------------------------------
    st.subheader("2. Product Specification Advisories (API 5CT / ISO 11960)")
    st.caption("Mill acceptance requirements evaluated per API 5CT. These report factory testing parameters and notes.")

    st.markdown("##### 🔍 Inspection: Product Specification Advisories for Selected Candidate")
    selected_advisory_cand = st.selectbox(
        "Select candidate to view product specification advisories:",
        options=candidate_list,
        key="select_advisory_cand"
    )
    
    row_adv = res_df[res_df['Name'] == selected_advisory_cand].iloc[0]

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown(f"**Candidate:** `{row_adv['Name']}` | **Grade:** `{row_adv['Grade']}`")
        st.markdown(f"• **Minimum Elongation:** {row_adv['Elongation_Note']}")
        st.markdown(f"• **Charpy V-Notch (CVN) Toughness:** {row_adv['CVN_Note']}")
    with col_a2:
        st.markdown(f"• **As-Quenched Hardenability:** {row_adv['Hardenability_Note']}")
        if row_adv['API_5CT_Flags']:
            st.warning(f"**API 5CT Specification Flags:** {row_adv['API_5CT_Flags']}")
        else:
            st.info("**API 5CT Specification Flags:** None")

    st.markdown("---")

    # -----------------------------------------------------------------------------
    # 3. PER-CANDIDATE SPECIFICATION DETAIL (WITH USER INPUT SELECTOR)
    # -----------------------------------------------------------------------------
    st.subheader("3. Per-Candidate Specification Detail")
    st.caption("Detailed mechanical, hydrodynamic, and limit-state parameters for individual string evaluation.")

    st.markdown("##### 🔍 Inspection: Specification Detail for Selected Candidate")
    selected_detail_cand = st.selectbox(
        "Select candidate to view detailed engineering parameters:",
        options=candidate_list,
        key="select_detail_cand"
    )

    row_det = res_df[res_df['Name'] == selected_detail_cand].iloc[0]

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.markdown("**Mechanical & Hydrodynamic Metrics**")
        st.markdown(f"• **Candidate Name:** {row_det['Name']}")
        st.markdown(f"• **Outer Diameter (OD):** {row_det['OD_in']}\"")
        st.markdown(f"• **Inner Diameter (ID):** {row_det['ID_in']}\"")
        st.markdown(f"• **Grade / Material:** {row_det['Grade']} ({row_det['Material']})")
        st.markdown(f"• **Connection:** {row_det['Connection']}")
        st.markdown(f"• **Flow Velocity (Initial / Late):** {row_det['Velocity_fts']} / {row_det['v_late_life_fts']} ft/s")
        st.markdown(f"• **Erosional Limit (Salama):** {row_det['v_erosional']} ft/s")
        st.markdown(f"• **Carrying Velocity (Initial / Late):** {row_det['v_carrying']} / {row_det['v_carrying_late']} ft/s")
        st.markdown(f"• **Friction Factor (f):** {row_det['friction_factor']}")
        st.markdown(f"• **Total Pressure Drop:** {row_det['dp_total_psi']} psi")

    with col_d2:
        st.markdown("**Structural & Limit State Performance**")
        st.markdown(f"• **Net Axial Load:** {row_det['f_axial_klbs']} klbs (Rating: {row_det['f_axial_rating_klbs']} klbs)")
        st.markdown(f"• **von Mises Stress:** {row_det['vme_stress_psi']} psi (SF: {row_det['triaxial_sf']})")
        st.markdown(f"• **vME Governing Point:** {row_det['vme_governing_point']}")
        st.markdown(f"• **Ductile Rupture Capacity:** {row_det['p_rupture_psi']} psi (SF: {row_det['rupture_sf']})")
        st.markdown(f"• **Active Rupture Mode:** {row_det['rupture_mode']}")
        st.markdown(f"• **Collapse Capacity:** {row_det['p_collapse_psi']} psi (SF: {row_det['collapse_sf']})")
        st.markdown(f"• **Collapse Regime:** {row_det['collapse_regime']}")
        st.markdown(f"• **Axial Equivalent Yield (Y_pa):** {row_det['y_pa_psi']} psi")

    with col_d3:
        st.markdown("**Environmental, APB & Factory Gates**")
        st.markdown(f"• **Shut-In CITHP Load:** {row_det['cithp_psi']} psi")
        st.markdown(f"• **Surface Burst Safety Factor:** {row_det['burst_sf']}")
        st.markdown(f"• **Annular Pressure Build-Up (APB):** {row_det['dp_apb_psi']} psi")
        st.markdown(f"• **Mill Hydrostatic Proof Test:** {row_det['p_test_psi']} psi (SF: {row_det['hydro_test_sf']})")
        st.markdown(f"• **Hydro Design Factor (f):** {row_det['hydro_design_factor']}")
        st.markdown(f"• **Max Service Temp Limit:** {row_det['max_service_temp_c']} °C")
        st.markdown(f"• **NACE Sour Status:** {row_det['Material_Reason']}")
        st.markdown(f"• **Connection Status:** {row_det['Connection_Reason']}")
        st.markdown(f"• **Overall Compliance Status:** {'PASS' if row_det['Overall_Pass'] else 'FAIL'}")

# -----------------------------------------------------------------------------
# PAGE 10: RECOMMENDATION & LIFECYCLE SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "10. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 10: Recommendations & Lifecycle Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluate qualified tubing options, dynamic pressure drop evolution over well field life, and drawdown limit thresholds.</div>', unsafe_allow_html=True)
    
    candidates = active_candidate_df()
    if candidates.empty:
        st.warning("No tubing candidates are selected. Adjust the OD/grade filters on Page 8.")
        st.stop()
        
    try:
        res_df = engineering_results(st.session_state.inputs, candidates)
    except ValueError as error:
        st.error(f"Input validation failed: {error}")
        st.stop()
        
    # Create Main Tabs for Page 10
    page10_tab1, page10_tab2 = st.tabs([
        "🏆 Tab 1: Qualified Recommendations & Sensitivity",
        "📈 Tab 2: Tubing Selection & Pressure Drop Along Well Life"
    ])

    # =========================================================================
    # TAB 1: QUALIFIED RECOMMENDATIONS & SENSITIVITY (CURRENT WORKFLOW)
    # =========================================================================
    with page10_tab1:
        passed_candidates = res_df[res_df['Overall_Pass'] == True].copy()
        is_gas = "Gas" in st.session_state.inputs.get('well_type', 'Oil')
        
        # Sort all passed candidates primarily by minimal total pressure drop
        if not passed_candidates.empty:
            sorted_passed = passed_candidates.sort_values(
                by=['dp_total_psi', 'Velocity_fts', 'triaxial_sf'], 
                ascending=[True, True, False]
            ).reset_index(drop=True)
        else:
            sorted_passed = pd.DataFrame()
            
        col1, col2 = st.columns([1.2, 1.8], gap="medium")
        
        with col1:
            st.subheader("Qualified Candidate Ranking")
            if not sorted_passed.empty:
                st.markdown(f"**Total Candidates Passed Screening:** `{len(sorted_passed)}` of `{len(res_df)}`")
                
                # Top 3 Candidates displayed as Feature Cards
                top_3 = sorted_passed.head(3)
                for idx, candidate in top_3.iterrows():
                    rank = idx + 1
                    if rank == 1:
                        border_color, bg_color, badge = "#10B981", "#ECFDF5", "🏆 Rank 1 (Top Preferred)"
                    elif rank == 2:
                        border_color, bg_color, badge = "#3B82F6", "#EFF6FF", "🥈 Rank 2"
                    else:
                        border_color, bg_color, badge = "#F59E0B", "#FFFBEB", "🥉 Rank 3"
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-weight: 800; font-size: 1.05rem; color: #0F172A;">#{rank}. {candidate['Name']}</span>
                            <span style="font-size: 0.78rem; font-weight: 700; color: {border_color}; text-transform: uppercase;">{badge}</span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; font-size: 0.88rem; color: #334155;">
                            <div><b>Total ΔP:</b> {candidate['dp_total_psi']} psi</div>
                            <div><b>Flow Velocity:</b> {candidate['Velocity_fts']} ft/s</div>
                            <div><b>Grade / Mat:</b> {candidate['Grade']}</div>
                            <div><b>Connection:</b> {candidate['Connection']}</div>
                            <div><b>Triaxial SF:</b> {candidate['triaxial_sf']}</div>
                            <div><b>Surface Burst SF:</b> {candidate['burst_sf']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                # Remaining Passing Candidates
                remaining_passed = sorted_passed.iloc[3:]
                if not remaining_passed.empty:
                    st.markdown("##### Other Qualified Candidates")
                    table_df = remaining_passed.copy()
                    table_df['Rank'] = [f"#{i}" for i in range(4, len(sorted_passed) + 1)]
                    table_df = table_df[[
                        'Rank', 'Name', 'Grade', 'dp_total_psi', 'Velocity_fts', 'triaxial_sf', 'burst_sf'
                    ]].rename(columns={
                        'Name': 'Tubing', 'dp_total_psi': 'ΔP (psi)', 'Velocity_fts': 'Vel (ft/s)',
                        'triaxial_sf': 'Triaxial SF', 'burst_sf': 'Burst SF'
                    })
                    st.dataframe(table_df, use_container_width=True, hide_index=True)
            else:
                st.error("### No Candidates Passed All Screenings!")
                st.warning("Consider increasing bottomhole pressure, selecting higher steel grades, or upgrading to premium connections.")

        with col2:
            st.subheader("Engineering Justification Rationale")
            if not sorted_passed.empty:
                top_1 = sorted_passed.iloc[0]
                rate_str = (
                    f"**{st.session_state.inputs.get('q_gas_mmscfd', 15.0)} MMscf/D** gas with **{st.session_state.inputs.get('cgr_stb_mmscf', 25.0)} STB/MMscf** condensate"
                    if is_gas else
                    f"**{st.session_state.inputs.get('q_liquid', 5000.0)} STB/D** liquid with **{st.session_state.inputs.get('water_cut', 5.0)}%** water cut"
                )
                
                st.markdown(f"""
                <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-left: 5px solid #16A34A; border-radius: 8px; padding: 1rem; margin-bottom: 1.25rem;">
                    <h4 style="color: #15803D; margin-top: 0; margin-bottom: 0.4rem; font-size: 1.05rem;">🎯 Why {top_1['Name']} is Ranked #1</h4>
                    <p style="font-size: 0.89rem; color: #166534; line-height: 1.5; margin: 0;">
                        <b>{top_1['Name']}</b> achieves the lowest total pressure drop (<b>{top_1['dp_total_psi']} psi</b>) among all qualified candidates while operating safely within the velocity window (<b>{top_1['Velocity_fts']} ft/s</b>). 
                        It maintains robust structural margins under Lubinski axial load (Triaxial SF = <b>{top_1['triaxial_sf']}</b> ≥ 1.25) and static closed-in surface burst (Burst SF = <b>{top_1['burst_sf']}</b> ≥ 1.10).
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(rf"""
                ##### General Compliance Rationale (All Qualified Candidates)
                * **Hydraulic Validation:** All qualified candidates operate with total pressure drop ($\Delta P_{{\text{{total}}}}$) fully within the available drawdown drive (**{top_1['dp_avail_psi']} psi**). Dynamic Z-factor (**{top_1['Z_Factor']}**) confirms live fluid conditions at a rate of {rate_str}.
                * **Velocity Window:** Initial flow velocities sit safely between the minimum sand carrying limit (**{top_1['v_carrying']} ft/s**) and the Salama sand erosion threshold (**{top_1['v_erosional']} ft/s**).
                * **Shut-In CITHP & Surface Integrity:** Static Closed-In Tubing Head Pressure of **{top_1['cithp_psi']} psi** yields static surface burst safety factors meeting or exceeding $SF \ge 1.10$.
                * **NACE & Structural Safety:** All passed candidates provide a von Mises triaxial SF $\ge 1.25$ under Lubinski net axial tension and APB rise (**{top_1['dp_apb_psi']} psi**).
                """)

        # General Interactive Sensitivity Charts (Current Page 10 Tab 1 Plots)
        st.markdown("---")
        st.subheader("General Tubing Diameter Sensitivity Charts")
        sens_tab1, sens_tab2 = st.tabs(["Pressure Drop vs. Tubing ID", "Velocity Window vs. Tubing ID"])
        with sens_tab1:
            fig_dp = px.line(
                res_df, x="ID_in", y="dp_total_psi", color="Grade", markers=True,
                title="Total Pressure Drop vs. Tubing Inner Diameter (ID)",
                labels={"ID_in": "Inner Diameter (inches)", "dp_total_psi": "Total Pressure Drop (psi)"},
                hover_data=["Name", "Velocity_fts", "Overall_Pass"]
            )
            fig_dp.update_traces(marker=dict(size=10))
            fig_dp.add_hline(
                y=res_df['dp_avail_psi'].iloc[0], line_dash="dash", line_color="red",
                annotation_text="Available Drawdown Limit", annotation_position="bottom right"
            )
            st.plotly_chart(fig_dp, use_container_width=True)

        with sens_tab2:
            fig_v = go.Figure()
            fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['Velocity_fts'], mode='lines+markers', name='Initial Flow Velocity'))
            fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_late_life_fts'], mode='lines+markers', name='Late-Life Flow Velocity', line=dict(dash='dash', color='purple')))
            fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_erosional'], mode='lines', name='Salama Sand Erosional Limit (Max)', line=dict(dash='dash', color='red')))
            fig_v.add_trace(go.Scatter(x=res_df['ID_in'], y=res_df['v_carrying'], mode='lines', name='Min Sand Carrying Limit', line=dict(dash='dot', color='orange')))
            fig_v.update_layout(
                title="Flow Velocity Window vs. Tubing Inner Diameter",
                xaxis_title="Inner Diameter (inches)", yaxis_title="Velocity (ft/s)", margin=dict(t=50, b=40)
            )
            st.plotly_chart(fig_v, use_container_width=True)

    # =========================================================================
    # TAB 2: TUBING SELECTION ALONG WELL LIFE (NEW FEATURE)
    # =========================================================================
    with page10_tab2:
        st.subheader("📈 Tubing Selection & Pressure Drop Trajectory Along Well Life")
        st.caption("Simulate pressure drop evolution from Year 0 to Target Well Field Life under exponential reservoir pressure depletion and rate decline.")

        # Inputs for well life simulation
        field_life_yrs = int(st.session_state.inputs.get('field_life_yrs', 20))
        decline_rate_pct = float(st.session_state.inputs.get('decline_rate', 8.0))
        
        # Interactive Controls
        col_lc1, col_lc2 = st.columns([1.2, 1.0], gap="medium")
        with col_lc1:
            st.markdown("##### ⚙️ Tubing Specification Input & Life Controls")
            cand_names = res_df['Name'].tolist()
            selected_life_tubing = st.selectbox(
                "Select Tubing Candidate to Analyze Across Well Life:",
                options=cand_names,
                index=0,
                key="life_tubing_selector"
            )
            
            # Custom Overrides for Field Life parameters
            life_yrs_sim = st.slider("Target Well Field Life (Years)", min_value=5, max_value=40, value=field_life_yrs, step=1, key="life_yrs_sim")
            decline_sim = st.slider("Annual Production & Pressure Decline Rate (%)", min_value=0.0, max_value=25.0, value=decline_rate_pct, step=0.5, key="decline_sim")
            
        # Get baseline parameters for chosen candidate
        selected_row = res_df[res_df['Name'] == selected_life_tubing].iloc[0]
        id_in_sim = float(selected_row['ID_in'])
        od_in_sim = float(selected_row['OD_in'])
        grade_sim = selected_row['Grade']
        
        p_bhp_0 = float(st.session_state.inputs.get('p_bhp', 4500.0))
        p_wh_0 = float(st.session_state.inputs.get('p_wh', 800.0))
        dp_available_0 = p_bhp_0 - p_wh_0
        
        # Calculate year-by-year lifecycle trajectory
        years_arr = np.arange(0, life_yrs_sim + 1)
        
        # Depletion model over time
        decline_factor = (1.0 - decline_sim / 100.0) ** years_arr
        p_bhp_t = p_bhp_0 * decline_factor
        p_wh_t = np.maximum(p_wh_0 * decline_factor, 50.0)  # Minimum wellhead arrival pressure constraint
        dp_available_t = p_bhp_t - p_wh_t
        
        # Recalculate Total Pressure Drop along field life
        # Rates decline with reservoir energy; hydrostatic drops slightly while friction drops significantly with lower rate
        dp_hydro_0 = float(selected_row['dp_hydro_psi'])
        dp_fric_0 = float(selected_row['dp_fric_psi'])
        
        # Frictional pressure loss scales quadratically with rate ~ Q^1.8
        dp_fric_t = dp_fric_0 * (decline_factor ** 1.8)
        # Hydrostatic pressure loss scales with live density shifts
        dp_hydro_t = dp_hydro_0 * (0.92 + 0.08 * decline_factor)
        dp_total_t = dp_hydro_t + dp_fric_t
        
        # Determine drawdown breach year
        drawdown_breached = dp_total_t > dp_available_t
        breach_years = years_arr[drawdown_breached]
        
        if len(breach_years) > 0:
            first_breach_year = int(breach_years[0])
            breach_status_str = f"⚠️ **Year {first_breach_year}**"
            breach_alert = f"Drawdown limit reached at **Year {first_breach_year}**. Natural flow ceases as total pressure drop ({dp_total_t[first_breach_year]:.1f} psi) exceeds available drawdown ({dp_available_t[first_breach_year]:.1f} psi)."
            breach_pass = False
        else:
            first_breach_year = None
            breach_status_str = "🟢 **Not Breached (Sustained Natural Flow)**"
            breach_alert = f"Natural flow is successfully sustained across the full **{life_yrs_sim}-year** target well life!"
            breach_pass = True

        with col_lc2:
            st.markdown("##### 📌 Lifecycle Key Performance Indicators")
            m1, m2 = st.columns(2)
            m1.metric("Selected Tubing", selected_life_tubing)
            m2.metric("Target Field Life", f"{life_yrs_sim} Years")
            
            m3, m4 = st.columns(2)
            m3.metric("Initial ΔP (Year 0)", f"{dp_total_t[0]:.1f} psi")
            m4.metric("Drawdown Limit Breach", breach_status_str)
            
            if breach_pass:
                st.success(f"✅ **Target Well Life Met:** {breach_alert}")
            else:
                st.error(f"❌ **Drawdown Limit Reached:** {breach_alert}")

        st.markdown("---")
        st.markdown(f"#### 📊 Lifecycle Pressure Drop & Available Drawdown Trajectory ({selected_life_tubing})")
        
        # Plot Lifecycle Pressure Drop Trajectory Graph
        fig_life = go.Figure()
        
        # Total Pressure Drop curve
        fig_life.add_trace(go.Scatter(
            x=years_arr, y=dp_total_t, mode='lines+markers',
            name=f'Total Tubing Pressure Drop ΔP_total ({selected_life_tubing})',
            line=dict(color='#1E3A8A', width=3),
            hovertemplate='Year %{x}: ΔP_total = %{y:.1f} psi<extra></extra>'
        ))
        
        # Available Drawdown Limit curve
        fig_life.add_trace(go.Scatter(
            x=years_arr, y=dp_available_t, mode='lines',
            name='Available Reservoir Drawdown Limit (P_bhp - P_wh)',
            line=dict(color='#DC2626', width=2.5, dash='dash'),
            hovertemplate='Year %{x}: Available Drawdown = %{y:.1f} psi<extra></extra>'
        ))
        
        # Hydrostatic Component
        fig_life.add_trace(go.Scatter(
            x=years_arr, y=dp_hydro_t, mode='lines',
            name='Hydrostatic Head Component (ΔP_hydro)',
            line=dict(color='#2563EB', width=1.5, dash='dot'),
            visible='legendonly'
        ))
        
        # Frictional Component
        fig_life.add_trace(go.Scatter(
            x=years_arr, y=dp_fric_t, mode='lines',
            name='Frictional Component (ΔP_fric)',
            line=dict(color='#D97706', width=1.5, dash='dot'),
            visible='legendonly'
        ))
        
        # Add Vertical Marker for Drawdown Limit Breach Year
        if first_breach_year is not None:
            fig_life.add_vline(
                x=first_breach_year, line_dash="solid", line_color="#DC2626",
                annotation_text=f"Drawdown Limit Reached: Year {first_breach_year}",
                annotation_position="top left", annotation_font_color="#DC2626"
            )
            fig_life.add_trace(go.Scatter(
                x=[first_breach_year], y=[dp_total_t[first_breach_year]],
                mode='markers', marker=dict(size=14, color='#DC2626', symbol='x'),
                name='Drawdown Limit Breach Point'
            ))

        fig_life.update_layout(
            title=f"Tubing Pressure Drop Trajectory vs. Target Well Life ({life_yrs_sim} Years)",
            xaxis_title="Well Life Time (Years)",
            yaxis_title="Pressure (psi)",
            hovermode="x unified",
            height=500,
            margin=dict(t=50, b=40, l=40, r=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig_life, use_container_width=True)
        
        # Explanatory Callout Card
        st.markdown(f"""
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 5px solid #2563EB; border-radius: 8px; padding: 1rem; margin-top: 0.5rem;">
            <h5 style="color: #1E40AF; margin-top: 0; margin-bottom: 0.4rem; font-weight: 700;">💡 Well Life Lifecycle Analysis Findings</h5>
            <ul style="margin: 0; font-size: 0.88rem; color: #1E293B; line-height: 1.6;">
                <li><b>Target Field Life:</b> <b>{life_yrs_sim} Years</b> (Annual production decline rate: <b>{decline_sim}%</b>).</li>
                <li><b>Selected Tubing Candidate:</b> <b>{selected_life_tubing}</b> (ID: <b>{id_in_sim}"</b>, OD: <b>{od_in_sim}"</b>, Grade: <b>{grade_sim}</b>).</li>
                <li><b>Drawdown Status:</b> {breach_alert}</li>
                <li><b>Engineering Recommendation:</b> {"If drawdown limit is breached prior to target well life, artificial lift (e.g., gas lift or ESP) or a velocity string retrofit must be scheduled prior to the breach year." if not breach_pass else "This candidate provides sufficient hydraulic diameter to sustain natural flow throughout the full target well life."}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)