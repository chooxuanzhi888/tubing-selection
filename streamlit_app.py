import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import json
import urllib.request
import textwrap
import base64
import itertools

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
    .formula-card {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    .purpose-box {
        background-color: #F1F5F9;
        border-left: 4px solid #3B82F6;
        padding: 0.65rem 0.85rem;
        border-radius: 4px;
        font-size: 0.88rem;
        color: #1E293B;
        margin-top: 0.6rem;
        margin-bottom: 0.6rem;
    }
    .param-key {
        font-size: 0.84rem;
        color: #334155;
        line-height: 1.6;
        background-color: #FAFAFA;
        padding: 0.65rem 0.85rem;
        border-radius: 6px;
        border: 1px dashed #CBD5E1;
        margin-bottom: 0.6rem;
    }
    .filter-box {
        background-color: #FEF2F2;
        border-left: 4px solid #EF4444;
        padding: 0.6rem 0.85rem;
        border-radius: 4px;
        font-size: 0.84rem;
        color: #991B1B;
        margin-top: 0.5rem;
    }

    /* ---- Page 2 methodology layout ------------------------------------- */
    /* Full-width formula card: heading, then formula, then labelled blocks. */
    .m2-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
               padding: 1.15rem 1.35rem 1.25rem; margin: 0 0 1.4rem;
               box-shadow: 0 1px 3px rgba(15,23,42,0.05); }
    .m2-card-head { display: flex; align-items: baseline; gap: 0.6rem;
                    padding-bottom: 0.6rem; margin-bottom: 0.9rem;
                    border-bottom: 1px solid #E2E8F0; }
    .m2-card-num { flex: none; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.06em;
                   padding: 0.16rem 0.5rem; border-radius: 5px; background: #F1F5F9; color: #475569; }
    .m2-card-title { font-size: 1.06rem; font-weight: 700; margin: 0; line-height: 1.3; }
    /* Small uppercase label that introduces each block inside a card. */
    .m2-label { font-size: 0.7rem; font-weight: 800; letter-spacing: 0.09em;
                text-transform: uppercase; color: #64748B; margin: 1.1rem 0 0.4rem; }
    .m2-label:first-child { margin-top: 0; }
    /* Left-aligned on purpose: these paragraphs embed inline glossary terms whose
       pop-up panels cannot be broken across lines, so justification would stretch
       the spaces around each term into visible gaps. */
    .m2-purpose { font-size: 0.9rem; line-height: 1.65; color: #1E293B;
                  background: #F8FAFC; border-left: 3px solid #3B82F6;
                  padding: 0.7rem 0.9rem; border-radius: 0 5px 5px 0;
                  text-align: left; }
    .m2-gate { font-size: 0.86rem; line-height: 1.6; color: #991B1B;
               background: #FEF2F2; border-left: 3px solid #EF4444;
               padding: 0.7rem 0.9rem; border-radius: 0 5px 5px 0;
               text-align: left; }
    /* Parameter definition table: symbol | meaning | units. */
    .m2-param-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .m2-param-table th { text-align: left; font-size: 0.68rem; font-weight: 800;
                         letter-spacing: 0.07em; text-transform: uppercase; color: #64748B;
                         padding: 0.4rem 0.6rem; border-bottom: 1.5px solid #CBD5E1;
                         background: #F8FAFC; }
    .m2-param-table td { padding: 0.45rem 0.6rem; border-bottom: 1px solid #EEF2F6;
                         color: #334155; line-height: 1.5; vertical-align: top;
                         text-align: left; }
    .m2-param-table tr:last-child td { border-bottom: none; }
    .m2-param-table td.m2-sym { white-space: nowrap; font-weight: 700; color: #0F172A;
                                width: 16%; font-family: "SFMono-Regular", Consolas, monospace; }
    .m2-param-table td.m2-unit { white-space: nowrap; color: #64748B; width: 24%; font-size: 0.8rem; }
    /* Caption naming the quantity each formula solves for. */
    .m2-fx-caption { font-size: 0.82rem; color: #475569; font-weight: 600; margin: 0.55rem 0 -0.35rem; }

    /* ---- Glossary pop-up ------------------------------------------------ */
    /* Built from inline <span>/<label> only. An earlier <details>-based version
       broke the line: <details> is block-level, so the markdown renderer split
       the paragraph around every term. A hidden checkbox driven by <label>
       gives click-to-toggle with no block element in the text flow. */
    .m2-term { position: relative; display: inline; }
    .m2-term > input.m2-term-cb { position: absolute; opacity: 0; width: 0; height: 0;
                                  pointer-events: none; }
    .m2-term > label.m2-term-label { display: inline; cursor: help;
                                     border-bottom: 1.5px dotted #2563EB; color: #1D4ED8;
                                     font-weight: 600; }
    .m2-term > label.m2-term-label:hover { background: #EFF6FF; }
    .m2-term > input.m2-term-cb:checked ~ label.m2-term-label { background: #DBEAFE; }
    .m2-term .m2-term-pop { display: none; position: absolute; z-index: 40; left: 0; top: 1.7em;
                            width: min(21rem, 78vw); background: #0F172A; color: #E2E8F0;
                            border-radius: 8px; padding: 0.7rem 0.85rem;
                            font-size: 0.82rem; line-height: 1.55; font-weight: 400;
                            font-style: normal; text-transform: none; letter-spacing: normal;
                            text-align: left; white-space: normal;
                            box-shadow: 0 10px 24px rgba(15,23,42,0.28); }
    .m2-term > input.m2-term-cb:checked ~ .m2-term-pop { display: block; }
    .m2-term .m2-term-pop b { color: #7DD3FC; display: block; margin-bottom: 0.2rem; }

    /* ---- Clickable flowchart ------------------------------------------- */
    a.flow-link { text-decoration: none; display: block; color: inherit; }
    a.flow-link:hover .flow-box { border-color: #2563EB;
                                  box-shadow: 0 4px 10px rgba(37,99,235,0.18);
                                  transform: translateY(-1px); }
    .flow-box { transition: box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease; }
    .flow-jump { font-size: 0.7rem; font-weight: 700; color: #2563EB; opacity: 0; transition: opacity 0.15s ease; }
    a.flow-link:hover .flow-jump { opacity: 1; }
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

# Engine screening thresholds shared with the Page 2 methodology documentation.
Z_FACTOR_MIN, Z_FACTOR_MAX = 0.65, 1.25
CV_SOLIDS_MAX = 0.15
FRICTION_FACTOR_MAX = 0.15

# -----------------------------------------------------------------------------
# PAGE 2 METHODOLOGY: GLOSSARY & CARD BUILDERS
# -----------------------------------------------------------------------------
# Plain-English explanations for the jargon on Page 2. Rendered as click-to-open
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


# Interactive upper-completion schematic used in place of a static Figure 2 image.
# Clicking a hotspot on the diagram renders that component's details in the side panel.
UPPER_COMPLETION_SCHEMATIC_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Accurate Upper Completion Schematic - Light Theme</title>
<style>
  * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
  body { margin: 0; padding: 20px; background-color: #f8fafc; color: #0f172a; }
  .container { display: flex; flex-direction: row; gap: 24px; max-width: 1200px; height: 780px; margin: 0 auto; }
  
  /* Schematic Viewer Card */
  .diagram-card {
    flex: 1.1;
    background: #ffffff;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 12px;
    overflow: hidden;
  }
  svg { width: 100%; height: 100%; max-width: 420px; }

  /* Interactive Hotspot Styles */
  .hotspot { cursor: pointer; }
  .hotspot .selection-box {
    fill: transparent;
    stroke: transparent;
    stroke-width: 1.5;
    transition: all 0.2s ease;
  }
  .hotspot:hover .selection-box, .hotspot.active .selection-box {
    fill: rgba(2, 132, 199, 0.08);
    stroke: #0284c7;
    stroke-dasharray: 4 4;
  }
  .hotspot:hover .comp-body, .hotspot.active .comp-body {
    filter: drop-shadow(0 0 6px rgba(2, 132, 199, 0.4));
  }
  .pointer-line { stroke: #94a3b8; stroke-width: 1; stroke-dasharray: 2 2; }
  .label-text { font-size: 11px; font-weight: 600; fill: #475569; pointer-events: none; }
  .hotspot:hover .label-text, .hotspot.active .label-text { fill: #0284c7; font-weight: 700; }

  /* Info Card */
  .info-card {
    flex: 0.9;
    background: #ffffff;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    padding: 32px;
    display: flex;
    flex-direction: column;
  }
  .badge {
    align-self: flex-start;
    padding: 4px 12px;
    border-radius: 16px;
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 16px;
  }
  .title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 16px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid #e2e8f0;
  }
  .description { font-size: 0.95rem; line-height: 1.7; color: #334155; }
  .placeholder { color: #94a3b8; font-style: italic; }
</style>
</head>
<body>

<div class="container">
  <div class="diagram-card">
    <svg viewBox="0 0 340 740">
      <defs>
        <linearGradient id="tubingMetal" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#94a3b8"/>
          <stop offset="30%" stop-color="#f1f5f9"/>
          <stop offset="70%" stop-color="#cbd5e1"/>
          <stop offset="100%" stop-color="#64748b"/>
        </linearGradient>

        <linearGradient id="steelDark" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#334155"/>
          <stop offset="50%" stop-color="#64748b"/>
          <stop offset="100%" stop-color="#1e293b"/>
        </linearGradient>

        <linearGradient id="brassValve" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#d97706"/>
          <stop offset="50%" stop-color="#fde047"/>
          <stop offset="100%" stop-color="#b45309"/>
        </linearGradient>

        <pattern id="cementPattern" width="8" height="8" patternUnits="userSpaceOnUse">
          <path d="M 0 8 L 8 0 M 0 0 L 8 8" stroke="#cbd5e1" stroke-width="0.8"/>
        </pattern>
        
        <pattern id="packerRubber" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#1e293b"/>
          <circle cx="3" cy="3" r="1" fill="#ef4444"/>
        </pattern>
      </defs>

      <rect x="20" y="10" width="220" height="720" fill="url(#cementPattern)"/>

      <rect x="40" y="10" width="180" height="720" fill="#0284c7" fill-opacity="0.05" stroke="#cbd5e1" stroke-width="2"/>
      <line x1="40" y1="10" x2="40" y2="730" stroke="#475569" stroke-width="4"/>
      <line x1="220" y1="10" x2="220" y2="730" stroke="#475569" stroke-width="4"/>

      <rect x="120" y="10" width="20" height="720" fill="url(#tubingMetal)" stroke="#475569" stroke-width="1"/>

      <g class="hotspot" id="th" onclick="selectComponent('th')">
        <rect class="selection-box" x="25" y="15" width="280" height="45"/>
        <g class="comp-body">
          <path d="M 35 15 L 225 15 L 200 55 L 60 55 Z" fill="url(#steelDark)" stroke="#1e293b" stroke-width="1.5"/>
          <circle cx="75" cy="30" r="3" fill="#ef4444"/>
          <circle cx="185" cy="30" r="3" fill="#ef4444"/>
          <line x1="85" y1="15" x2="85" y2="55" stroke="#0284c7" stroke-width="1.5"/>
        </g>
        <line class="pointer-line" x1="160" y1="35" x2="240" y2="35"/>
        <text class="label-text" x="245" y="38">Tubing Hanger</text>
      </g>

      <g class="hotspot" id="fc1" onclick="selectComponent('fc1')">
        <rect class="selection-box" x="105" y="80" width="200" height="40"/>
        <rect class="comp-body" x="114" y="82" width="32" height="36" rx="2" fill="url(#steelDark)" stroke="#1e293b" stroke-width="1.5"/>
        <line class="pointer-line" x1="146" y1="100" x2="240" y2="100"/>
        <text class="label-text" x="245" y="103">Flow Coupling</text>
      </g>

      <g class="hotspot" id="trsv" onclick="selectComponent('trsv')">
        <rect class="selection-box" x="75" y="135" width="230" height="65"/>
        <g class="comp-body">
          <rect x="108" y="140" width="44" height="55" rx="3" fill="url(#brassValve)" stroke="#b45309" stroke-width="1.5"/>
          <path d="M 85 15 L 85 155 L 108 155" fill="none" stroke="#0284c7" stroke-width="2"/>
          <line x1="122" y1="172" x2="134" y2="162" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/>
        </g>
        <line class="pointer-line" x1="152" y1="168" x2="240" y2="168"/>
        <text class="label-text" x="245" y="171">TRSSV</text>
      </g>

      <g class="hotspot" id="fc2" onclick="selectComponent('fc2')">
        <rect class="selection-box" x="105" y="215" width="200" height="40"/>
        <rect class="comp-body" x="114" y="217" width="32" height="36" rx="2" fill="url(#steelDark)" stroke="#1e293b" stroke-width="1.5"/>
        <line class="pointer-line" x1="146" y1="235" x2="240" y2="235"/>
        <text class="label-text" x="245" y="238">Flow Coupling</text>
      </g>

      <g class="hotspot" id="spm" onclick="selectComponent('spm')">
        <rect class="selection-box" x="80" y="270" width="225" height="75"/>
        <g class="comp-body">
          <path d="M 120 275 L 162 275 L 168 290 L 168 325 L 162 335 L 120 335 Z" fill="url(#steelDark)" stroke="#65a30d" stroke-width="1.5"/>
          <rect x="144" y="290" width="16" height="32" rx="2" fill="#eab308" stroke="#ca8a04" stroke-width="1"/>
          <line x1="152" y1="322" x2="152" y2="338" stroke="#dc2626" stroke-width="1.5"/>
        </g>
        <line class="pointer-line" x1="168" y1="308" x2="240" y2="308"/>
        <text class="label-text" x="245" y="311">Mandrel & Gauge</text>
      </g>

      <g class="hotspot" id="lp" onclick="selectComponent('lp')">
        <rect class="selection-box" x="100" y="360" width="205" height="40"/>
        <g class="comp-body">
          <rect x="116" y="362" width="28" height="36" fill="url(#steelDark)" stroke="#1e293b" stroke-width="1.5"/>
          <path d="M 120 370 L 124 370 L 124 378 L 120 378 Z" fill="#0284c7"/>
          <path d="M 140 370 L 136 370 L 136 378 L 140 378 Z" fill="#0284c7"/>
        </g>
        <line class="pointer-line" x1="144" y1="380" x2="240" y2="380"/>
        <text class="label-text" x="245" y="383">Landing Profile</text>
      </g>

      <g class="hotspot" id="packer" onclick="selectComponent('packer')">
        <rect class="selection-box" x="35" y="415" width="270" height="85"/>
        <g class="comp-body">
          <rect x="42" y="435" width="76" height="30" fill="url(#packerRubber)" stroke="#dc2626" stroke-width="1.5"/>
          <rect x="142" y="435" width="76" height="30" fill="url(#packerRubber)" stroke="#dc2626" stroke-width="1.5"/>
          
          <path d="M 42 420 L 118 420 L 110 432 L 50 432 Z" fill="#94a3b8" stroke="#475569"/>
          <path d="M 142 420 L 218 420 L 210 432 L 150 432 Z" fill="#94a3b8" stroke="#475569"/>
          
          <path d="M 50 468 L 110 468 L 118 480 L 42 480 Z" fill="#94a3b8" stroke="#475569"/>
          <path d="M 150 468 L 210 468 L 218 480 L 142 480 Z" fill="#94a3b8" stroke="#475569"/>
        </g>
        <line class="pointer-line" x1="218" y1="450" x2="240" y2="450"/>
        <text class="label-text" x="245" y="453">Production Packer</text>
      </g>

      <g class="hotspot" id="irsv" onclick="selectComponent('irsv')">
        <rect class="selection-box" x="90" y="515" width="215" height="55"/>
        <g class="comp-body">
          <rect x="112" y="520" width="36" height="45" rx="2" fill="url(#steelDark)" stroke="#9333ea" stroke-width="1.5"/>
          <circle cx="130" cy="542" r="5" fill="#a855f7"/>
          <polygon points="130,532 125,538 135,538" fill="#c084fc"/>
        </g>
        <line class="pointer-line" x1="148" y1="542" x2="240" y2="542"/>
        <text class="label-text" x="245" y="545">IRSV Barrier</text>
      </g>

      <g class="hotspot" id="shoe" onclick="selectComponent('shoe')">
        <rect class="selection-box" x="90" y="585" width="215" height="65"/>
        <g class="comp-body">
          <path d="M 118 590 L 142 590 L 142 630 L 118 610 Z" fill="url(#steelDark)" stroke="#d97706" stroke-width="1.5"/>
        </g>
        <line class="pointer-line" x1="142" y1="605" x2="240" y2="605"/>
        <text class="label-text" x="245" y="608">Guide Shoe</text>
      </g>

      <text x="48" y="715" fill="#94a3b8" font-size="10" font-weight="700">CASING</text>
      <text x="122" y="715" fill="#64748b" font-size="10" font-weight="700">TUBING</text>
    </svg>
  </div>

  <div class="info-card">
    <div id="badge-slot"></div>
    <h2 class="title" id="title-slot">Upper Completion Assembly</h2>
    <div class="description" id="desc-slot">
      <p class="placeholder">Click any component or label on the completion schematic to review its mechanical construction, API specifications, and operational function.</p>
    </div>
  </div>
</div>

<script>
const data = {
  th: {
    title: "Tubing Hanger",
    category: "Wellhead Component",
    desc: "Landed inside the wellhead housing bowl, the tubing hanger supports the entire weight of the production tubing string. It utilizes dynamic elastomer seal rings to seal off the casing annulus and provides high-pressure feedthrough ports for hydraulic control lines and downhole gauge cables."
  },
  fc1: {
    title: "Flow Coupling (Upper)",
    category: "Tubular Protection",
    desc: "A thick-walled joint of heavy-duty tubing installed directly above dynamic flow-constricting safety valves. It is engineered to absorb erosive fluid jetting caused by turbulent flow and localized high velocity."
  },
  trsv: {
    title: "Tubing-Retrievable Safety Valve (TRSSV)",
    category: "Primary Barrier",
    desc: "A surface-controlled fail-safe valve held in the open position by hydraulic pressure applied through a control line. Loss of surface pressure allows internal springs to actuate the flapper mechanism shut, isolating reservoir pressure downhole."
  },
  fc2: {
    title: "Flow Coupling (Lower)",
    category: "Tubular Protection",
    desc: "Positioned directly beneath flow restrictions to protect the primary production string from wall thinning and washouts caused by turbulent fluid entry."
  },
  spm: {
    title: "Side Pocket Mandrel & Gauge",
    category: "Monitoring & Artificial Lift",
    desc: "Features an offset external pocket that houses downhole memory/permanent pressure-temperature gauges. The internal profile allows kick-off, gas-lift, or chemical-injection valves to be set and retrieved via slickline."
  },
  lp: {
    title: "Landing Profile (Nipple)",
    category: "Flow Control",
    desc: "A heavy-walled tubular section featuring precision internal locking grooves and polished seal bores. Serves as a landing platform for wireline tools, standing valves, or isolation plugs."
  },
  packer: {
    title: "Production Packer",
    category: "Zonal Isolation",
    desc: "Utilizes expandable elastomer elements and opposing bi-directional mechanical slip wickers to anchor inside the casing. Isolates the annular space above the reservoir, containing formation pressure inside the tubing."
  },
  irsv: {
    title: "Injection-Retrievable Safety Valve (IRSV)",
    category: "Secondary Barrier",
    desc: "A specialized downhole safety sub designed with an internal check-valve mechanism. Allows controlled fluid injection while preventing uncontained backflow toward upper completion zones."
  },
  shoe: {
    title: "Self-Aligning Guide Shoe",
    category: "Completion Bottom-Hole Assembly",
    desc: "Featuring a tapered mule-shoe profile at the base of the tubing string, this component guides wireline or coiled tubing tools smoothly back into the tubing bore during reentry interventions."
  }
};

function selectComponent(id) {
  document.querySelectorAll('.hotspot').forEach(el => el.classList.remove('active'));
  
  const target = document.getElementById(id);
  if (target) target.classList.add('active');

  const comp = data[id];
  if (comp) {
    document.getElementById('badge-slot').innerHTML = `<span class="badge">${comp.category}</span>`;
    document.getElementById('title-slot').innerText = comp.title;
    document.getElementById('desc-slot').innerHTML = `<p>${comp.desc}</p>`;
  }
}
</script>

</body>
</html>
"""


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

    Shared by the engine and the Page 3 default so the surface burst check and the
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
    p_co2_psia = p_bhp_val * (co2_pct_val / 100.0)
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
        sigma_bending_psi = 218.0 * row['OD_in'] * dls_val

        f_axial_total_lbs = f_gravity_lbs + f_thermal_lbs + f_piston_lbs + f_ballooning_lbs + f_drag_lbs
        f_axial_total_klbs = f_axial_total_lbs / 1000.0

        # Pipe body tensile rating: SMYS across the steel cross-section.
        tensile_rating_lbs = row['Yield_psi'] * area_steel_in2
        axial_pass = abs(f_axial_total_lbs) <= tensile_rating_lbs

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
                        temp_pass and burst_pass and apb_pass and pvt_pass and cv_in_range)

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

def active_candidate_df():
    """Return the candidate set the screening pages should evaluate.

    Honours the Page 4 OD/grade filters when they have been set; falls back to the
    full database otherwise (e.g. when the user goes straight to Page 5).
    """
    db = st.session_state.tubing_db
    selection = st.session_state.get('candidate_filter')
    if not selection:
        return db
    return db[db['OD_in'].isin(selection.get('od', [])) & db['Grade'].isin(selection.get('grade', []))]


# -----------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/000000/oil-rig.png", width=70)
st.sidebar.title("Tubing Selection Tool")
st.sidebar.caption("Upper-Completion Design Engine")

PAGE_LABELS = [
    "1. Introduction & Overview",
    "2. Calculation Methodology",
    "3. Well & Fluid Inputs",
    "4. Candidate Tubing Specs",
    "5. Engineering Calculations",
    "6. Recommendation & Sensitivity"
]

# A ?step=N link in the Page 2 flowchart must survive the rerun it triggers: force
# the sidebar back onto Page 2 so the reader lands on the step they clicked.
_requested_step = st.query_params.get("step")
if _requested_step and st.session_state.get("nav_page") != PAGE_LABELS[1]:
    st.session_state["nav_page"] = PAGE_LABELS[1]

page = st.sidebar.radio(
    "Select Workflow Step:",
    PAGE_LABELS,
    key="nav_page"
)

# -----------------------------------------------------------------------------
# PAGE 1: INTRODUCTION & OVERVIEW
# -----------------------------------------------------------------------------
if page == "1. Introduction & Overview":
    @st.cache_data(show_spinner=False)
    def encode_image_b64(path):
        """Return an inline data URI for `path`, or None when it is unavailable.

        Cached because cover.jpg is several megabytes; re-encoding it on every
        rerun would add that much base64 to each page render.
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

    cover_b64 = first_existing_image(['cover.jpg', 'cover.png', 'cover.jpeg'])

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
        <a class="p1-toc-card" href="#3-0-model-assumptions-limitations" style="--accent: #DC2626;">
            <div class="p1-toc-num">Section 3.0</div>
            <div class="p1-toc-title">Assumptions &amp; Limits</div>
            <div class="p1-toc-desc">Model scope and operational bounds</div>
            <div class="p1-toc-sub">3.1 Key assumptions &middot; 3.2 Engineering limits</div>
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
        <div id="1-2-major-design-decisions" class="p1-card p1-card-blue">
            <span class="p1-chip p1-chip-blue">Subtopic 1.2</span>
            <h3 class="p1-card-title">Major Design Decisions</h3>
            <ul class="p1-list p1-list-blue">
                <li><span class="p1-term">Artificial lift</span> — gas lift, ESP, or natural flow.</li>
                <li><span class="p1-term">Tubing size</span> — balances production capacity against pressure drop.</li>
                <li><span class="p1-term">Completion configuration</span> — single or dual completion.</li>
                <li><span class="p1-term">Tubing isolation</span> — a packer or equivalent to control fluid communication.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col2:
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
        components.html(UPPER_COMPLETION_SCHEMATIC_HTML, height=830, scrolling=False)
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

    col_t1, col_t2 = st.columns([1, 1], gap="medium")

    with col_t1:
        st.markdown(figure_block("Figure 3.jpg", "3", "Production tubing in a completed well"), unsafe_allow_html=True)

    with col_t2:
        st.markdown(f"""
        <div id="2-1-tubing-dimensions-geometry" class="p1-card p1-card-green">
            <span class="p1-chip p1-chip-green">Subtopic 2.1</span>
            <h3 class="p1-card-title">Tubing Dimensions &amp; Geometry</h3>
            <p class="p1-card-body">
                Cross-sectional geometry governs both the internal fluid dynamics (<b>ID</b>) and the external
                clearance inside the casing (<b>OD</b>). Nominal wall thickness provides burst and collapse
                resistance under downhole pressure differentials.
            </p>
        </div>
        {figure_block("Figure 4.jpg", "4", "Tubing dimensions and wall thickness")}
        """, unsafe_allow_html=True)

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

    # -------------------------------------------------------------------------
    # MAIN TOPIC 3.0: MODEL ASSUMPTIONS & DESIGN LIMITATIONS
    # -------------------------------------------------------------------------
    st.markdown("""
    <section id="3-0-model-assumptions-limitations" class="p1-section p1-section-red">
        <div class="p1-section-head">
            <div class="p1-section-num">3.0</div>
            <h2 class="p1-section-title">Model Assumptions &amp; Design Limitations</h2>
        </div>
        <p class="p1-section-lead">
            To deliver rapid, robust screening, this engine applies standardized physical models and fluid-dynamics
            principles. Knowing where those models hold — and where they stop — is essential to interpreting the
            recommendations correctly.
        </p>
    </section>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
        <div id="3-1-key-assumptions" class="p1-card p1-card-red" style="margin-bottom: 0;">
            <span class="p1-chip p1-chip-red">Subtopic 3.1</span>
            <h3 class="p1-card-title">Key Assumptions</h3>
            <ul class="p1-list p1-list-red">
                <li><span class="p1-term">Steady-state flow</span> — single-phase gas or homogenized multiphase flow under steady operating conditions.</li>
                <li><span class="p1-term">Linear thermal gradient</span> — temperature varies linearly from wellhead to bottomhole.</li>
                <li><span class="p1-term">Isothermal annular APB</span> — trapped-fluid expansion uses single-zone average thermal expansion (&alpha;<sub>v</sub>) and isothermal compressibility (&kappa;<sub>T</sub>).</li>
                <li><span class="p1-term">Uniform pipe geometry</span> — the string is evaluated as one nominal size and weight from surface to TD.</li>
            </ul>
        </div>
        <div id="3-2-engineering-limitations" class="p1-card p1-card-red" style="margin-bottom: 0;">
            <span class="p1-chip p1-chip-red">Subtopic 3.2</span>
            <h3 class="p1-card-title">Engineering Limitations</h3>
            <ul class="p1-list p1-list-red">
                <li><span class="p1-term">Transient effects</span> — shut-in surges, water hammer, and thermal warm-up/cool-down cycles are not modeled.</li>
                <li><span class="p1-term">Multiphase flow regimes</span> — a homogeneous mixture model is used; slug, mist, and annular flow maps are simplified.</li>
                <li><span class="p1-term">Corrosion kinetics</span> — NACE MR0175 screening is binary (pH<sub>2</sub>S threshold); no quantitative corrosion rate (mm/year) is computed.</li>
                <li><span class="p1-term">Completion accessories</span> — SSSVs and mandrels are treated as equivalent hydraulic restrictions, not detailed local geometries.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE 2: CALCULATION METHODOLOGY (REFINED & RESTORED)
# -----------------------------------------------------------------------------
elif page == "2. Calculation Methodology":
    st.markdown('<div class="main-header">Step 2: Comprehensive Calculation Methodology</div>', unsafe_allow_html=True)
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
            <span class="flow-step-title" style="color: #065F46;">Step 6: Lam&eacute; 3D Principal Stresses &amp; von Mises Triaxial Yield (&sigma;<sub>VME</sub>)</span>
            <span><span class="flow-jump">open &rsaquo;</span> <span class="flow-domain-badge" style="background-color: #D1FAE5; color: #065F46;">Domain C</span></span>
        </div>
        <div class="flow-box-body">Evaluates 3D axial, hoop, radial, and dogleg bending stresses against yield strength (SF<sub>triaxial</sub> &ge; 1.25).</div>
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
    with st.expander("Step 6  ·  Lamé 3D Principal Stresses & von Mises Triaxial Yield   —   Domain C", expanded=(active_step == 6)):
        formula_card(
            "6.1",
            "Lam&eacute; Thick-Wall Principal &amp; Bending Stresses",
            "#065F46",
            [
                (r"\sigma_{axial} = \frac{F_{axial}}{A_{steel}} + \underbrace{218 \cdot OD \cdot DLS}_{\sigma_{bending}}", "Axial stress, including bending through doglegs"),
                (r"\sigma_\theta = \frac{P_{int} r_i^2 - P_{ext} r_o^2 + \frac{r_i^2 r_o^2 (P_{int} - P_{ext})}{r^2}}{r_o^2 - r_i^2}, \quad \sigma_r = -P_{int}", "Hoop and radial stress at the inner wall"),
            ],
            f"Resolves the three-dimensional stress state in the pipe wall using the {term('lame')}. It produces axial stress including {term('dogleg', 'dogleg')} bending, {term('hoop', 'hoop stress')} acting circumferentially, and {term('radial-stress', 'radial stress')} through the wall — the three inputs the von Mises check needs.",
            [
                ("&sigma;<sub>axial</sub>", "Total axial stress including dogleg bending", "psi"),
                ("OD", "Tubing outer diameter", "in"),
                ("DLS", "Maximum dogleg severity", "deg/100 ft"),
                ("&sigma;<sub>&theta;</sub>", "Hoop stress at the inner wall", "psi"),
                ("&sigma;<sub>r</sub>", "Radial stress at the inner wall", "psi"),
                ("P<sub>int</sub>, P<sub>ext</sub>", "Internal (P<sub>bhp</sub>) and external (P<sub>annular</sub>) pressure", "psi"),
                ("r<sub>i</sub>, r<sub>o</sub>", "Inner and outer pipe radii", "in"),
            ],
            "Rejects a candidate when dogleg bending stress combined with axial tension exceeds structural yield.",
        )

        formula_card(
            "6.2",
            "von Mises Triaxial Equivalent Yield Stress",
            "#065F46",
            [
                (r"\sigma_{VME} = \sqrt{\frac{1}{2} \left[ (\sigma_\theta - \sigma_r)^2 + (\sigma_r - \sigma_{axial})^2 + (\sigma_{axial} - \sigma_\theta)^2 \right]}", "Three stresses collapsed into one comparable number"),
                (r"SF_{triaxial} = \frac{Y_{yield}}{\sigma_{VME}} \ge 1.25", "Margin against yield"),
            ],
            f"Reduces the 3D stress state to a single {term('von-mises', 'equivalent stress')} that can be compared directly against the steel’s {term('smys', 'yield strength')}. The ratio of the two is the {term('safety-factor')}, and 1.25 is the threshold this engine enforces.",
            [
                ("&sigma;<sub>VME</sub>", "von Mises equivalent triaxial stress", "psi"),
                ("Y<sub>yield</sub>", "Specified minimum yield strength of the grade", "L80 = 80,000 psi"),
                ("SF<sub>triaxial</sub>", "Triaxial safety factor", "target &ge; 1.25"),
            ],
            "Rejects a candidate failing the triaxial safety factor (<i>SF<sub>triaxial</sub></i> &lt; 1.25), which would allow plastic deformation under combined loading.",
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
# PAGE 3: WELLBORE & DUAL-LIFECYCLE OPERATIONAL INPUTS
# ----------------------------------------------------------------------------- 
elif page == "3. Well & Fluid Inputs": 
    st.markdown('<div class="main-header">Step 3: Wellbore Geometry & Operational Inputs</div>', unsafe_allow_html=True) 
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

        manual_override = st.checkbox("🛠️ Enable Manual Override for Late-Life Parameters", value=False) 

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
            st.info("💡 **Auto-Predictive Engine Active:** Late-Life parameters are estimated using annual field decline rates and reservoir depletion rules. Check above to adjust manually.") 

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

    st.markdown("---")
    
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
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1]) 
    with col_btn2: 
        if st.button("💾 Save Operational Baseline & Lifecycle State", type="primary", use_container_width=True): 
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

    # The filtered set is what Pages 5 and 6 screen, so persist it.
    st.session_state.candidate_filter = {"od": list(selected_sizes), "grade": list(selected_grades)}

    if filtered_db.empty:
        st.warning("No candidates match the current filters. Pages 5 and 6 need at least one candidate to screen.")
    else:
        st.caption(f"**{len(filtered_db)}** of {len(st.session_state.tubing_db)} candidates selected — Pages 5 and 6 screen exactly this filtered set.")

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
    
    candidates = active_candidate_df()
    if candidates.empty:
        st.warning("No tubing candidates are selected. Adjust the OD/grade filters on Page 4.")
        st.stop()

    try:
        res_df = run_engineering_calculations(st.session_state.inputs, candidates)
    except ValueError as error:
        st.error(f"Input validation failed: {error}")
        st.stop()

    st.caption(f"Screening **{len(candidates)}** candidate(s) from the Page 4 filter selection.")

    st.subheader(f"Candidate Screening Matrix ({st.session_state.inputs.get('well_type', 'Oil Well')} Mode)")

    display_df = res_df[[
        'Name', 'ID_in', 'Grade', 'Material', 'Connection', 'Velocity_fts', 'v_late_life_fts', 'v_carrying', 'v_carrying_late', 'v_erosional',
        'dp_total_psi', 'dp_apb_psi', 'cithp_psi', 'f_axial_klbs', 'f_axial_rating_klbs', 'vme_stress_psi', 'triaxial_sf', 'burst_sf',
        'friction_factor', 'cv_solids', 'Z_Factor', 'max_service_temp_c', 'Material_Reason', 'Temp_Reason', 'Overall_Pass'
    ]].copy()

    display_df.columns = [
        'Tubing Candidate', 'ID (in)', 'Grade', 'Material', 'Connection', 'Initial Vel (ft/s)', 'Late-Life Vel (ft/s)', 'Min Carrying Vel (ft/s)', 'Late Carrying Vel (ft/s)', 'Erosional Limit (ft/s)',
        'Total dP (psi)', 'APB Pressure (psi)', 'CITHP (psi)', 'Axial Load (klbs)', 'Axial Rating (klbs)', 'von Mises Stress (psi)', 'Triaxial SF', 'Burst SF',
        'Friction f', 'Sand Cv', 'Z-Factor', 'Max Service T (°C)', 'NACE Status', 'Temp Status', 'Overall Status'
    ]

    st.dataframe(display_df, use_container_width=True, height=450)

    # Per-gate failure detail so a rejection can be traced to a specific check.
    st.subheader("Screening Gate Detail")
    gate_cols = [
        ('Casing_Clearance_Pass', 'Casing Clearance'), ('PVT_Pass', 'PVT / Z-Factor'),
        ('Solids_Pass', 'Sand Concentration'), ('Hydraulics_Pass', 'Hydraulics'),
        ('Friction_Pass', 'Friction Factor'), ('Velocity_Pass', 'Velocity Window'),
        ('Late_Life_Pass', 'Late-Life Velocity'), ('Stress_Pass', 'Triaxial Stress'),
        ('Axial_Pass', 'Axial Load'), ('Burst_Pass', 'Surface Burst'),
        ('APB_Pass', 'APB Limit'), ('Temp_Pass', 'Temperature'),
        ('Material_Pass', 'NACE Sour'), ('Connection_Pass', 'Connection')
    ]
    gate_df = res_df[['Name'] + [col for col, _ in gate_cols]].copy()
    gate_df.columns = ['Tubing Candidate'] + [label for _, label in gate_cols]
    st.dataframe(gate_df, use_container_width=True, height=350)

    failed = res_df[~res_df['Overall_Pass']]
    if not failed.empty:
        with st.expander(f"⚠️ Rejection reasons ({len(failed)} candidate(s) failed)"):
            for _, r in failed.iterrows():
                reasons = []
                if not r['Casing_Clearance_Pass']:
                    reasons.append(f"OD {r['OD_in']}\" does not clear the {st.session_state.inputs.get('casing_id', 8.681)}\" casing ID")
                if not r['PVT_Pass']:
                    reasons.append(r['PVT_Reason'])
                if not r['Solids_Pass']:
                    reasons.append(r['Solids_Reason'])
                if not (r['Hydraulics_Pass'] and r['Friction_Pass']):
                    reasons.append(r['Hydraulics_Reason'])
                if not r['Velocity_Pass']:
                    reasons.append(f"Initial velocity {r['Velocity_fts']} ft/s outside window {r['v_carrying']}–{r['v_erosional']} ft/s")
                if not r['Late_Life_Pass']:
                    reasons.append(f"Late-life velocity {r['v_late_life_fts']} ft/s below late carrying limit {r['v_carrying_late']} ft/s")
                if not r['Stress_Pass']:
                    reasons.append(f"Triaxial SF {r['triaxial_sf']} below target {st.session_state.inputs.get('sf_triaxial', 1.25)}")
                if not r['Axial_Pass']:
                    reasons.append(r['Axial_Reason'])
                if not r['Burst_Pass']:
                    reasons.append(f"Surface burst SF {r['burst_sf']} below 1.10")
                if not r['APB_Pass']:
                    reasons.append(r['APB_Reason'])
                if not r['Temp_Pass']:
                    reasons.append(r['Temp_Reason'])
                if not r['Material_Pass']:
                    reasons.append(r['Material_Reason'])
                if not r['Connection_Pass']:
                    reasons.append(r['Connection_Reason'])
                st.markdown(f"**{r['Name']}** — " + "; ".join(str(x) for x in reasons))

# -----------------------------------------------------------------------------
# PAGE 6: RECOMMENDATION & SENSITIVITY
# -----------------------------------------------------------------------------
elif page == "6. Recommendation & Sensitivity":
    st.markdown('<div class="main-header">Step 6: Recommendations & Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Final candidate ranking, automated engineering rationale, structural/burst checks, and interactive comparative charts.</div>', unsafe_allow_html=True)
    
    candidates = active_candidate_df()
    if candidates.empty:
        st.warning("No tubing candidates are selected. Adjust the OD/grade filters on Page 4.")
        st.stop()

    try:
        res_df = run_engineering_calculations(st.session_state.inputs, candidates)
    except ValueError as error:
        st.error(f"Input validation failed: {error}")
        st.stop()
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
            
            st.markdown(rf"""
            * **Hydraulic Validation:** Total pressure drop (**{preferred['dp_total_psi']} psi**) is fully within available drawdown drive (**{preferred['dp_avail_psi']} psi**). Dynamic Z-factor (**{preferred['Z_Factor']}**) confirms live fluid conditions at rate of {rate_str}.
            * **Velocity Window:** Initial flow velocity (**{preferred['Velocity_fts']} ft/s**) sits between the minimum sand carrying limit (**{preferred['v_carrying']} ft/s**) and the Salama sand erosion threshold (**{preferred['v_erosional']} ft/s**). Late-life velocity (**{preferred['v_late_life_fts']} ft/s**) remains above the depleted-condition carrying limit (**{preferred['v_carrying_late']} ft/s**).
            * **Shut-In CITHP & Surface Integrity:** Closed-In Tubing Head Pressure of **{preferred['cithp_psi']} psi** yields a static burst safety factor of **{preferred['burst_sf']}** (exceeding $SF \ge 1.10$).
            * **NACE & Structural Safety:** Grade **{preferred['Grade']}** ({preferred['Material']}) provides a von Mises triaxial SF of **{preferred['triaxial_sf']}** under Lubinski axial tension (**{preferred['f_axial_klbs']} klbs** against a **{preferred['f_axial_rating_klbs']} klbs** pipe body rating) and APB rise (**{preferred['dp_apb_psi']} psi**). Maximum service temperature for this grade is **{preferred['max_service_temp_c']}°C**.
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