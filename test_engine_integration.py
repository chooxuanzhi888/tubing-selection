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


def test_api_5ct_columns_present(results):
    expected = {
        'p_test_psi', 'hydro_test_sf', 'hydro_design_factor', 'Hydro_Pass', 'Hydro_Reason',
        'min_elongation_pct', 'elongation_specimen', 'Elongation_Note',
        'cvn_body_trans_j', 'cvn_body_long_j', 'cvn_cplg_trans_j', 'cvn_cplg_long_j',
        'cvn_testing_waived', 'CVN_Note',
        'hrc_min_as_quenched', 'hrc_applicable', 'Hardenability_Note', 'API_5CT_Flags',
    }
    assert expected <= set(results.columns)


def test_every_candidate_gets_a_proof_test_pressure(results):
    """The hydro gate is a hard gate, so it must evaluate for every candidate."""
    assert results['p_test_psi'].notna().all()
    assert (results['p_test_psi'] > 0).all()
    assert results['hydro_design_factor'].isin([0.60, 0.80]).all()


def test_hydro_gate_genuinely_gates(results):
    """A candidate whose mill test pressure is below CITHP must fail and say so."""
    failed = results[~results['Hydro_Pass']]
    assert not failed.empty, "expected some low-grade candidates below shut-in CITHP"
    assert (failed['p_test_psi'] < failed['cithp_psi']).all()
    assert failed['Hydro_Reason'].str.startswith("Fail:").all()
    assert (~failed['Overall_Pass']).all()


def test_overall_pass_is_the_conjunction_of_the_hard_gates_only(results):
    """The three advisory 5CT checks must never affect Overall_Pass."""
    gates = [c for c in results.columns if c.endswith('_Pass') and c != 'Overall_Pass']
    assert 'Hydro_Pass' in gates
    assert (results['Overall_Pass'] == results[gates].all(axis=1)).all()


def test_advisory_checks_do_not_reject_candidates(results):
    """Waived CVN testing and non-applicable hardenability are notes, not failures."""
    waived = results[results['cvn_testing_waived']]
    assert not waived.empty
    # Some waived-CVN candidates must still pass overall, proving it is advisory.
    assert waived['Overall_Pass'].any()
    not_applicable = results[~results['hrc_applicable']]
    assert not not_applicable.empty
    assert not_applicable['Overall_Pass'].any()


def test_every_candidate_gets_an_elongation_requirement(results):
    assert results['min_elongation_pct'].notna().all()
    assert (results['min_elongation_pct'] > 0).all()
    assert set(results['elongation_specimen']) <= {
        "strip", "round_bar_8.9mm", "round_bar_12.7mm"
    }


def test_coupling_cvn_always_exceeds_pipe_body(results):
    """Couplings are rated on specified maximum yield, so they demand more."""
    assert (results['cvn_cplg_trans_j'] >= results['cvn_body_trans_j']).all()
    assert (results['cvn_cplg_long_j'] >= results['cvn_body_long_j']).all()


def test_cra_grades_report_hardenability_as_not_applicable(results):
    """CRA grades have no as-quenched martensite target -- reported, not raised."""
    cra = results[results['Grade'].str.contains("Cr", case=False, na=False)]
    assert not cra.empty
    assert (~cra['hrc_applicable']).all()
    assert cra['Hardenability_Note'].str.contains("corrosion-resistant").all()


def test_alternative_test_pressure_is_flagged(results):
    """Above the 10,000 psi cap the flag must fire without failing the gate."""
    flagged = results[results['API_5CT_Flags'].str.contains("Alternative Test Pressures")]
    assert not flagged.empty
    assert (flagged['p_test_psi'] > 10000.0).all()


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
