"""Verification tests for the API 5CT / ISO 11960 product-specification engine."""

import math

import pytest

from api_5ct import (
    AREA_CAP_MM2,
    CVN_SUBSIZE_ABSOLUTE_FLOOR_J,
    MILL_FLOOR_PSI,
    STANDARD_TEST_PRESSURE_CAP_PSI,
    CarbonContentRangeError,
    GradeDataUnavailableError,
    SpecimenGeometryError,
    calculate_as_quenched_hardness,
    calculate_hydrostatic_test_pressure,
    calculate_min_cvn,
    calculate_min_elongation,
    joules_to_ft_lb,
    round_elongation_pct,
    round_test_pressure,
)

# 3-1/2" 9.2# L80: OD 3.500, wall 0.254, Y_S 80 ksi, U_m 95 ksi
OD, WALL, YS = 3.500, 0.254, 80000.0

# --- Module 1: elongation -----------------------------------------------------

def test_elongation_si_round_trip():
    """The same physical pipe must give the same requirement in either system."""
    uscs = calculate_min_elongation(WALL, grade="L80")
    si = calculate_min_elongation(WALL * 25.4, grade="L80", unit_system="SI")
    assert si["min_elongation_pct_unrounded"] == pytest.approx(
        uscs["min_elongation_pct_unrounded"], rel=2e-3
    )
    assert si["min_elongation_pct"] == uscs["min_elongation_pct"]


def test_elongation_hand_calculation():
    """3-1/2" 9.2# L80 on a strip specimen requires 17% elongation."""
    result = calculate_min_elongation(WALL, grade="L80")
    assert result["min_elongation_pct_unrounded"] == pytest.approx(17.07, abs=0.05)
    assert result["min_elongation_pct"] == 17.0
    assert result["specimen_basis"] == "strip"


def test_elongation_requirement_falls_as_strength_rises():
    """U enters at a negative power, so a stronger grade must elongate less."""
    soft = calculate_min_elongation(WALL, grade="J-55")["min_elongation_pct_unrounded"]
    hard = calculate_min_elongation(WALL, grade="Q125")["min_elongation_pct_unrounded"]
    assert hard < soft


def test_elongation_area_cap_binds_on_a_thick_strip():
    """A strip wide enough to exceed 490 mm2 earns no further relief.

    Only reachable on an explicitly requested strip: a wall this thick would
    otherwise auto-select a round bar, whose area is fixed well under the cap.
    """
    thick = calculate_min_elongation(0.60, grade="L80", specimen="strip")
    assert thick["area_capped"] is True
    assert thick["specimen_area_mm2"] == pytest.approx(AREA_CAP_MM2)
    # Capped, so a still-thicker strip gives an identical requirement.
    thicker = calculate_min_elongation(0.70, grade="L80", specimen="strip")
    assert thicker["min_elongation_pct_unrounded"] == pytest.approx(
        thick["min_elongation_pct_unrounded"]
    )


def test_thin_wall_selects_strip_and_says_why_round_bars_are_out():
    result = calculate_min_elongation(WALL, grade="L80")
    assert result["specimen_basis"] == "strip"
    assert "Round bars prohibited" in result["round_bar_prohibited_reason"]


def test_specimen_auto_selection_climbs_with_wall_thickness():
    """Largest permissible specimen wins: 12.7 mm bar, then 8.9 mm, then strip."""
    assert calculate_min_elongation(0.20, grade="L80")["specimen_basis"] == "strip"
    assert calculate_min_elongation(0.55, grade="L80")["specimen_basis"] == "round_bar_8.9mm"
    assert calculate_min_elongation(0.80, grade="L80")["specimen_basis"] == "round_bar_12.7mm"


def test_round_bar_areas_are_fixed_not_derived():
    """Round bars carry a fixed area regardless of the wall they came from."""
    a = calculate_min_elongation(0.80, grade="L80")
    b = calculate_min_elongation(1.20, grade="L80")
    assert a["specimen_area_mm2"] == pytest.approx(130.0)
    assert b["specimen_area_mm2"] == pytest.approx(130.0)


def test_explicit_round_bar_on_too_thin_a_wall_is_prohibited():
    with pytest.raises(SpecimenGeometryError, match="cannot be machined"):
        calculate_min_elongation(WALL, grade="L80", specimen="round_bar_12.7mm")


def test_elongation_rounding_rule():
    """Below 10% to the nearest 0.5%, at or above to the nearest whole percent."""
    assert round_elongation_pct(9.7) == 9.5
    assert round_elongation_pct(9.9) == 10.0
    assert round_elongation_pct(9.4) == 9.5
    assert round_elongation_pct(17.1) == 17.0
    assert round_elongation_pct(17.6) == 18.0


def test_iso_11960_constant_shifts_the_result():
    """C = 1942.57 rather than 1944 gives a slightly lower requirement."""
    api = calculate_min_elongation(WALL * 25.4, grade="L80", unit_system="SI")
    iso = calculate_min_elongation(WALL * 25.4, grade="L80", unit_system="SI", iso_11960=True)
    assert iso["constant_c"] == 1942.57
    assert iso["min_elongation_pct_unrounded"] < api["min_elongation_pct_unrounded"]
    assert iso["min_elongation_pct_unrounded"] == pytest.approx(
        api["min_elongation_pct_unrounded"], rel=1e-3
    )


# --- Module 2: hydrostatic proof test -----------------------------------------

def test_hydrostatic_hand_calculation():
    """2*80000*0.80*0.254/3.5 = 9289 psi, rounding to 9300."""
    result = calculate_hydrostatic_test_pressure(OD, WALL, YS, grade="L80")
    assert result["p_test_unrounded_psi"] == pytest.approx(9289.1, abs=1.0)
    assert result["p_test_psi"] == 9300.0
    assert result["design_factor"] == 0.80
    assert result["flags"] == []


def test_hydrostatic_si_round_trip():
    uscs = calculate_hydrostatic_test_pressure(OD, WALL, YS, grade="L80")
    si = calculate_hydrostatic_test_pressure(
        OD * 25.4, WALL * 25.4, YS / 145.03773800721814, grade="L80", unit_system="SI"
    )
    assert si["p_test_unrounded_psi"] == pytest.approx(uscs["p_test_unrounded_psi"], rel=1e-9)
    assert si["p_test_mpa"] == pytest.approx(round_test_pressure(uscs["p_test_unrounded_psi"] / 145.03773800721814, "SI"))


def test_design_factor_drops_for_large_low_grade_pipe():
    """H40/J55/K55 above 9-5/8 in test at 0.60; the same grade below it at 0.80."""
    large = calculate_hydrostatic_test_pressure(10.75, 0.400, 55000.0, grade="J-55")
    small = calculate_hydrostatic_test_pressure(7.000, 0.400, 55000.0, grade="J-55")
    assert large["design_factor"] == 0.60
    assert "permitted alternative" in large["design_factor_basis"]
    assert small["design_factor"] == 0.80


def test_design_factor_stays_high_for_strong_large_pipe():
    """The 0.60 rule is grade-specific: a large P110 still tests at 0.80."""
    result = calculate_hydrostatic_test_pressure(10.75, 0.400, 110000.0, grade="P110")
    assert result["design_factor"] == 0.80


def test_pressure_cap_flags_but_never_clamps():
    """Above 10,000 psi the joint needs a specially agreed test, not a lower one."""
    result = calculate_hydrostatic_test_pressure(5.500, 0.500, 125000.0, grade="Q125")
    assert result["p_test_unrounded_psi"] > STANDARD_TEST_PRESSURE_CAP_PSI
    assert result["alternative_test_pressure_required"] is True
    assert any("Alternative Test Pressures" in f for f in result["flags"])
    # Retained, not clamped down to the cap.
    assert result["p_test_psi"] > STANDARD_TEST_PRESSURE_CAP_PSI


def test_thread_leak_below_pipe_body_governs():
    result = calculate_hydrostatic_test_pressure(OD, WALL, YS, grade="L80", p_thread_leak=6000.0)
    assert result["thread_leak_governs"] is True
    assert result["p_test_psi"] == 6000.0
    assert result["p_body_psi"] == pytest.approx(9289.1, abs=1.0)
    assert any("Thread-leak override" in f for f in result["flags"])


def test_thread_leak_above_pipe_body_does_not_override():
    result = calculate_hydrostatic_test_pressure(OD, WALL, YS, grade="L80", p_thread_leak=12000.0)
    assert result["thread_leak_governs"] is False
    assert result["p_test_psi"] == 9300.0


def test_absent_thread_leak_is_reported_not_invented():
    """No rating supplied must leave P untouched and say so explicitly."""
    result = calculate_hydrostatic_test_pressure(OD, WALL, YS, grade="L80")
    assert result["thread_leak_governs"] is False
    assert "no thread-leak rating supplied" in result["thread_leak_basis"]
    assert result["p_test_psi"] == 9300.0


def test_mill_floor_is_flagged_but_only_applied_on_request():
    thin = dict(od=4.500, wall=0.100, yield_strength=40000.0, grade="H40")
    flagged = calculate_hydrostatic_test_pressure(**thin)
    assert flagged["below_mill_floor"] is True
    assert flagged["mill_floor_applied"] is False
    assert flagged["p_test_psi"] < MILL_FLOOR_PSI

    raised = calculate_hydrostatic_test_pressure(**thin, apply_mill_floor=True)
    assert raised["mill_floor_applied"] is True
    assert raised["p_test_psi"] == MILL_FLOOR_PSI


def test_test_pressure_rounding_grid():
    assert round_test_pressure(9289.1, "USCS") == 9300.0
    assert round_test_pressure(9240.0, "USCS") == 9200.0
    assert round_test_pressure(64.03, "SI") == 64.0
    assert round_test_pressure(64.3, "SI") == 64.5


# --- Module 3: Charpy V-notch -------------------------------------------------

def test_longitudinal_is_double_transverse_before_the_floors():
    """The longitudinal coefficient set is exactly 2x the transverse one."""
    # A high-strength thick wall clears both floors, so the raw ratio shows.
    trans = calculate_min_cvn(0.60, 125000.0, grade="Q125", orientation="transverse")
    longi = calculate_min_cvn(0.60, 125000.0, grade="Q125", orientation="longitudinal")
    assert trans["floor_applied"] is False and longi["floor_applied"] is False
    assert longi["cvn_full_size_j"] == pytest.approx(2.0 * trans["cvn_full_size_j"], rel=1e-12)


def test_coupling_requirement_exceeds_pipe_body():
    """Couplings are rated on specified MAXIMUM yield, so they demand more."""
    body = calculate_min_cvn(0.60, 110000.0, grade="P110", component="pipe_body")
    cplg = calculate_min_cvn(0.60, 110000.0, grade="P110", component="coupling")
    assert cplg["yield_used_psi"] > body["yield_used_psi"]
    assert cplg["cvn_required_j"] > body["cvn_required_j"]
    assert "maximum" in cplg["yield_basis"] and "minimum" in body["yield_basis"]


def test_high_floor_binds_for_p110_and_standard_floor_for_l80():
    p110 = calculate_min_cvn(0.20, 110000.0, grade="P110")
    l80 = calculate_min_cvn(0.20, YS, grade="L80")
    assert p110["governing_floor_j"] == 20.0
    assert l80["governing_floor_j"] == 14.0
    assert p110["cvn_required_j"] >= 20.0
    assert l80["cvn_required_j"] >= 14.0


def test_longitudinal_floors_are_the_raised_pair():
    p110 = calculate_min_cvn(0.20, 110000.0, grade="P110", orientation="longitudinal")
    l80 = calculate_min_cvn(0.20, YS, grade="L80", orientation="longitudinal")
    assert p110["governing_floor_j"] == 41.0
    assert l80["governing_floor_j"] == 27.0


def test_non_qt_grades_carry_no_floor_class():
    """H40/J55/K55 are not quenched and tempered, so no floor applies."""
    result = calculate_min_cvn(0.30, 55000.0, grade="J-55")
    assert result["floor_applicable"] is False
    assert result["governing_floor_j"] is None
    assert result["floor_applied"] is False


def test_subsize_factors_scale_the_requirement():
    kwargs = dict(wall=0.60, yield_strength=125000.0, grade="Q125")
    full = calculate_min_cvn(**kwargs, specimen_size="full")
    three_q = calculate_min_cvn(**kwargs, specimen_size="three_quarter")
    half = calculate_min_cvn(**kwargs, specimen_size="half")
    assert three_q["cvn_required_j"] == pytest.approx(0.75 * full["cvn_required_j"])
    assert half["cvn_required_j"] == pytest.approx(0.50 * full["cvn_required_j"])


def test_subsize_absolute_floor_binds_where_scaling_would_go_below_it():
    """Half of the 14 J standard floor is 7 J, which the 11 J minimum lifts."""
    result = calculate_min_cvn(0.20, YS, grade="L80", specimen_size="half")
    assert result["cvn_full_size_j"] == pytest.approx(14.0)
    assert result["subsize_floor_applied"] is True
    assert result["cvn_required_j"] == CVN_SUBSIZE_ABSOLUTE_FLOOR_J


def test_thin_wall_waives_testing_and_triggers_qa_check():
    result = calculate_min_cvn(0.20, YS, grade="L80")
    assert result["testing_waived"] is True
    assert result["qa_process_check_required"] is True
    assert "QA" in result["waive_reason"]

    thick = calculate_min_cvn(0.40, YS, grade="L80")
    assert thick["testing_waived"] is False


def test_joule_and_ft_lb_outputs_agree():
    result = calculate_min_cvn(0.60, 125000.0, grade="Q125")
    assert result["cvn_required_ftlb"] == pytest.approx(joules_to_ft_lb(result["cvn_required_j"]))
    # The published floor pairs are unit conversions of one another.
    assert joules_to_ft_lb(20.0) == pytest.approx(14.8, abs=0.1)
    assert joules_to_ft_lb(41.0) == pytest.approx(30.2, abs=0.1)
    assert joules_to_ft_lb(11.0) == pytest.approx(8.1, abs=0.1)


def test_cvn_si_round_trip():
    uscs = calculate_min_cvn(0.60, 125000.0, grade="Q125")
    si = calculate_min_cvn(0.60 * 25.4, 125000.0 / 145.03773800721814, grade="Q125", unit_system="SI")
    assert si["cvn_required_j"] == pytest.approx(uscs["cvn_required_j"], rel=1e-9)


def test_unknown_cvn_arguments_are_rejected():
    for bad in (dict(component="flange"), dict(orientation="radial"), dict(specimen_size="quarter")):
        with pytest.raises(Exception):
            calculate_min_cvn(0.30, YS, grade="L80", **bad)


def test_coupling_without_max_yield_on_file_raises():
    with pytest.raises(GradeDataUnavailableError, match="maximum yield"):
        calculate_min_cvn(0.30, YS, grade="X-Unobtainium", component="coupling")


# --- Module 4: as-quenched hardenability --------------------------------------

def test_c90_hardenability_hand_calculation():
    """58*0.35 + 17.2 = 37.5 HRC at 90% martensite."""
    result = calculate_as_quenched_hardness("C90", 0.35)
    assert result["applicable"] is True
    assert result["hrc_min"] == pytest.approx(37.5, abs=0.01)
    assert result["martensite_fraction_min_pct"] == 90.0


def test_t95_shares_the_c90_correlation():
    assert calculate_as_quenched_hardness("T95", 0.35)["hrc_min"] == pytest.approx(
        calculate_as_quenched_hardness("C90", 0.35)["hrc_min"]
    )


def test_c110_uses_its_own_pair_at_95_percent_martensite():
    result = calculate_as_quenched_hardness("C110", 0.35)
    assert result["hrc_min"] == pytest.approx(59.0 * 0.35 + 18.2, abs=0.01)
    assert result["martensite_fraction_min_pct"] == 95.0


def test_other_qt_grades_use_the_50_percent_correlation():
    result = calculate_as_quenched_hardness("L80-1", 0.43)
    assert result["hrc_min"] == pytest.approx(52.0 * 0.43 + 14.0, abs=0.01)
    assert result["martensite_fraction_min_pct"] == 50.0


def test_hardness_target_is_verified_at_mid_wall():
    """The slowest-quenching location governs, so the result must say where."""
    result = calculate_as_quenched_hardness("C90", 0.35)
    assert "mid-wall" in result["evaluation_position"]


def test_carbon_outside_the_validity_range_raises():
    with pytest.raises(CarbonContentRangeError, match="below"):
        calculate_as_quenched_hardness("C90", 0.10)
    with pytest.raises(CarbonContentRangeError, match="exceeds"):
        calculate_as_quenched_hardness("C90", 0.60)


def test_mass_fraction_input_error_gets_an_explicit_hint():
    """0.0025 is the classic 'entered a fraction' slip; say so in the message."""
    with pytest.raises(CarbonContentRangeError, match="whole percentage"):
        calculate_as_quenched_hardness("C90", 0.0025)


def test_cra_grades_are_not_applicable_rather_than_an_error():
    for grade in ("25Cr-125", "22Cr-110", "S13Cr-110", "L80-13Cr"):
        result = calculate_as_quenched_hardness(grade)
        assert result["applicable"] is False
        assert result["hrc_min"] is None
        assert "corrosion-resistant" in result["reason"]


def test_non_qt_grades_are_not_applicable():
    result = calculate_as_quenched_hardness("J-55")
    assert result["applicable"] is False
    assert "not quenched and tempered" in result["reason"]


def test_carbon_falls_back_to_the_grade_table():
    assert calculate_as_quenched_hardness("C90")["carbon_pct"] == pytest.approx(0.35)


def test_hardness_rises_with_carbon():
    low = calculate_as_quenched_hardness("C90", 0.20)["hrc_min"]
    high = calculate_as_quenched_hardness("C90", 0.45)["hrc_min"]
    assert high > low
