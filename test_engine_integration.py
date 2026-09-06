"""End-to-end check of the API 5C3 gates inside run_engineering_calculations."""

import pandas as pd
import pytest

import streamlit_app as app

BASE_INPUTS = {
    'well_type': 'Oil Well (Liquid Dominated)', 'lithology': 'Sandstone (C=120)',
    'tvd': 10000.0, 'md': 11500.0, 'dls': 2.0, 'casing_id': 8.681,
    'p_wh': 800.0, 'p_bhp': 4500.0, 't_wh': 150.0, 't_bht': 210.0, 't_ambient': 75.0,
    'annular_fluid': 'Water-Based Brine (α_v = 2.1e-4 /°C, κ_T = 3.0e-6 /psi)',
    'q_liquid': 5000.0, 'water_cut': 5.0, 'gor': 800.0,
    'q_gas_mmscfd': 15.0, 'cgr_stb_mmscf': 25.0, 'wgr_bbl_mmscf': 5.0,
    'api_gravity': 35.0, 'gas_sg': 0.65, 'water_sg': 1.05, 'oil_visc': 1.5,
    'co2_mole_pct': 2.5, 'h2s_ppm': 150.0, 'ph_val': 6.5, 'chlorides_ppm': 35000.0,
    'sand_rate_pptb': 0.0, 'sand_size_microns': 150.0, 'sand_sg': 2.65,
    'field_life_yrs': 20, 'decline_rate': 8.0, 'sf_triaxial': 1.25, 'apb_limit_psi': 1500.0,
}


@pytest.fixture(scope="module")
def results():
    db = pd.read_csv("tubing_database.csv")
    return app.run_engineering_calculations(dict(BASE_INPUTS), db)


def test_engine_runs_over_full_database(results):
    db = pd.read_csv("tubing_database.csv")
    assert len(results) == len(db)


def test_new_api_5c3_columns_present(results):
    expected = {
        'triaxial_sf', 'vme_governing_point', 'vme_n_points',
        'p_rupture_psi', 'rupture_sf', 'rupture_mode', 'Rupture_Pass', 'Rupture_Reason',
        'p_collapse_psi', 'collapse_sf', 'collapse_regime', 'y_pa_psi',
        'Collapse_Pass', 'Collapse_Reason',
    }
    assert expected <= set(results.columns)


def test_every_candidate_gets_a_rupture_capacity(results):
    """Clause 7 has no yield cutoff, so every candidate must get a real number."""
    assert (results['rupture_mode'] != 'not evaluated').all(), (
        results.loc[results['rupture_mode'] == 'not evaluated', ['Name', 'Rupture_Reason']].to_string()
    )
    assert results['p_rupture_psi'].notna().all()
    assert (results['p_rupture_psi'] > 0).all()


def test_collapse_yield_cutoff_only_bites_under_high_axial_stress(results):
    """Where Clause 8 declines to evaluate, it must be because axial stress has
    driven Y_pa below the curve-fit validity floor -- never for any other reason.

    Note this is a stricter condition than the app's own Axial_Pass gate: a
    candidate can satisfy |F_a| <= Y_p*A_n and still have enough axial stress to
    push Y_pa under the floor, because Y_pa collapses non-linearly as sigma_z
    approaches Y_p.
    """
    cutoff = results[results['collapse_regime'] == 'not evaluated']
    for _, row in cutoff.iterrows():
        assert "Y_pa" in row['Collapse_Reason'] or "axial" in row['Collapse_Reason'].lower(), (
            f"{row['Name']}: unexpected collapse failure -- {row['Collapse_Reason']}"
        )
    evaluated = results[results['collapse_regime'] != 'not evaluated']
    assert not evaluated.empty
    assert evaluated['p_collapse_psi'].notna().all()
    assert (evaluated['p_collapse_psi'] > 0).all()
    assert (evaluated['y_pa_psi'] >= 16000.0).all()


def test_yield_cutoff_is_reported_not_silently_passed(results):
    """Where the cutoff does bite, the gate fails with an explanatory reason."""
    cutoff = results[results['collapse_regime'] == 'not evaluated']
    if not cutoff.empty:
        assert (~cutoff['Collapse_Pass']).all()
        assert (~cutoff['Overall_Pass']).all()
        assert cutoff['Collapse_Reason'].str.startswith("Fail: Clause 8").all()


def test_vme_evaluates_multiple_coordinates_when_dogleg_present(results):
    """DLS = 2 deg/100ft means bending, so 4 coordinates must be checked."""
    assert (results['vme_n_points'] == 4).all()
    assert results['vme_governing_point'].str.contains("radius").all()


def test_collapse_regimes_are_recognised(results):
    assert set(results['collapse_regime']) <= {
        "Yield", "Plastic", "Transition", "Elastic", "not evaluated"
    }
    # At least some candidates must actually reach a real regime.
    assert (results['collapse_regime'] != 'not evaluated').any()


def test_rupture_modes_are_recognised(results):
    assert set(results['rupture_mode']) <= {"rupture", "necking"}


def test_overall_pass_respects_new_gates():
    """A candidate failing rupture or collapse cannot pass overall."""
    db = pd.read_csv("tubing_database.csv")
    severe = dict(BASE_INPUTS)
    severe.update({'p_bhp': 14000.0, 'p_wh': 9000.0, 'tvd': 18000.0, 'md': 19000.0})
    res = app.run_engineering_calculations(severe, db)
    assert (~res['Overall_Pass'] | (res['Rupture_Pass'] & res['Collapse_Pass'])).all()
    # Severe conditions must actually trip at least one of the new gates.
    assert (~res['Rupture_Pass']).any() or (~res['Collapse_Pass']).any()


def test_failed_gates_carry_a_reason():
    db = pd.read_csv("tubing_database.csv")
    severe = dict(BASE_INPUTS)
    severe.update({'p_bhp': 14000.0, 'p_wh': 9000.0, 'tvd': 18000.0, 'md': 19000.0})
    res = app.run_engineering_calculations(severe, db)
    for _, row in res.iterrows():
        if not row['Rupture_Pass']:
            assert row['Rupture_Reason'].startswith("Fail:")
        if not row['Collapse_Pass']:
            assert row['Collapse_Reason'].startswith("Fail:")


def test_tension_derates_collapse_capacity():
    """Deeper string -> more tension -> lower Y_pa -> lower collapse capacity.

    Uses the high-grade end of the database so the axial yield cutoff does not
    remove the candidates before the comparison can be made.
    """
    db = pd.read_csv("tubing_database.csv")
    db = db[db['Yield_psi'] >= 110000].head(6)
    shallow = app.run_engineering_calculations(dict(BASE_INPUTS, tvd=4000.0, md=4200.0), db)
    deep = app.run_engineering_calculations(dict(BASE_INPUTS, tvd=8000.0, md=8400.0), db)
    both = shallow['y_pa_psi'].notna() & deep['y_pa_psi'].notna()
    assert both.any(), "no candidate evaluated collapse at both depths"
    assert (deep.loc[both, 'y_pa_psi'] < shallow.loc[both, 'y_pa_psi']).all()
    assert (deep.loc[both, 'p_collapse_psi'] < shallow.loc[both, 'p_collapse_psi']).all()


def test_extreme_tension_reports_yield_cutoff_not_a_crash():
    """Y_pa below the API curve-fit validity floor must degrade to a failed gate
    with an explanatory reason, never an unhandled exception."""
    db = pd.read_csv("tubing_database.csv")
    extreme = dict(BASE_INPUTS)
    extreme.update({'p_bhp': 14000.0, 'p_wh': 9000.0, 'tvd': 18000.0, 'md': 19000.0})
    res = app.run_engineering_calculations(extreme, db)
    cutoff = res[res['collapse_regime'] == 'not evaluated']
    if not cutoff.empty:
        assert (~cutoff['Collapse_Pass']).all()
        assert cutoff['Collapse_Reason'].str.startswith("Fail: Clause 8").all()
        assert (~cutoff['Overall_Pass']).all()
