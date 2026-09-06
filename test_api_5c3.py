"""Verification tests for the API TR 5C3 / ISO 10400 engine."""

import math

import pytest

from api_5c3 import (
    ColdExpandedPipeError,
    GeometryError,
    MaterialSpecificationError,
    UnitSystemError,
    YieldCutoffExceededError,
    calculate_collapse,
    calculate_ductile_rupture,
    calculate_vme,
    collapse_boundaries,
    collapse_constants,
    dls_to_beta_rad_per_in,
    psi_to_mpa,
)

# 3-1/2" 9.2# L80: OD 3.500, wall 0.254, ID 2.992
OD, WALL, YP = 3.500, 0.254, 80000.0


# --- Module 1: triaxial -------------------------------------------------------

def test_vme_point_counts():
    """1 point with neither bending nor torsion, 2 with torsion, 4 with both."""
    plain = calculate_vme(OD, WALL, YP, 8000.0, 2000.0, 50000.0)
    assert plain["n_points"] == 1
    assert plain["governing_point"]["radius"] == "inner"

    torsion = calculate_vme(OD, WALL, YP, 8000.0, 2000.0, 50000.0, torque=3000.0)
    assert torsion["n_points"] == 2

    both = calculate_vme(OD, WALL, YP, 8000.0, 2000.0, 50000.0, dls=8.0, torque=3000.0)
    assert both["n_points"] == 4
    assert {p["fibre"] for p in both["evaluation_points"]} == {"tensile", "compressive"}
    assert {p["radius"] for p in both["evaluation_points"]} == {"inner", "outer"}


def test_vme_thin_wall_hoop_sanity():
    """Pure internal pressure, no axial: hoop at the bore should track Lame."""
    res = calculate_vme(OD, WALL, YP, 10000.0, 0.0, 0.0, k_wall=1.0)
    pt = res["governing_point"]
    r_i, r_o = res["r_iw_in"], res["r_o_in"]
    expected_hoop = 10000.0 * (r_i ** 2 + r_o ** 2) / (r_o ** 2 - r_i ** 2)
    assert pt["sigma_theta_psi"] == pytest.approx(expected_hoop, rel=1e-9)
    assert pt["sigma_r_psi"] == pytest.approx(-10000.0, rel=1e-9)


def test_vme_wall_tolerance_reduces_bore_radius():
    """k_wall = 0.875 must shrink the wall used for pressure stresses only."""
    default = calculate_vme(OD, WALL, YP, 10000.0, 0.0, 0.0)
    full = calculate_vme(OD, WALL, YP, 10000.0, 0.0, 0.0, k_wall=1.0)
    assert default["r_iw_in"] > full["r_iw_in"]
    assert default["sigma_vme_max_psi"] > full["sigma_vme_max_psi"]
    # Axial/torsional properties stay nominal regardless of k_wall.
    assert default["area_n_in2"] == pytest.approx(full["area_n_in2"])
    assert default["polar_j_n_in4"] == pytest.approx(full["polar_j_n_in4"])


def test_dls_conversion_both_systems():
    """10 deg/100ft and its SI near-equivalent 3 deg/30m."""
    assert dls_to_beta_rad_per_in(10.0, "USCS") == pytest.approx(10.0 * math.pi / 180.0 / 1200.0)
    si = dls_to_beta_rad_per_in(3.0, "SI")
    assert si == pytest.approx(3.0 * math.pi / 180.0 / 30.0 * 0.0254)
    # 3 deg/30m ~= 3.05 deg/100ft, so beta should be close but not equal.
    assert si == pytest.approx(dls_to_beta_rad_per_in(3.048, "USCS"), rel=1e-3)


def test_vme_bending_stress_magnitude():
    """sigma_zb = E*D*beta/2 for a 10 deg/100ft dogleg on 3-1/2" pipe."""
    res = calculate_vme(OD, WALL, YP, 5000.0, 1000.0, 0.0, dls=10.0)
    beta = 10.0 * math.pi / 180.0 / 1200.0
    assert res["sigma_bending_psi"] == pytest.approx(30.0e6 * OD * beta / 2.0, rel=1e-9)
    # ~7630 psi at 10 deg/100ft, the classic order of magnitude.
    assert 7000.0 < res["sigma_bending_psi"] < 8300.0


def test_vme_si_round_trip():
    """SI inputs must reproduce the USCS answer after conversion."""
    uscs = calculate_vme(OD, WALL, YP, 8000.0, 2000.0, 50000.0, dls=10.0, torque=3000.0)
    si = calculate_vme(
        OD * 25.4, WALL * 25.4, psi_to_mpa(YP), psi_to_mpa(8000.0), psi_to_mpa(2000.0),
        50000.0 / 224.80894309971047, dls=10.0 / 1.0160, torque=3000.0 / 0.7375621492772654,
        unit_system="SI",
    )
    assert si["sigma_vme_max_psi"] == pytest.approx(uscs["sigma_vme_max_psi"], rel=2e-3)
    assert si["sigma_vme_max_mpa"] == pytest.approx(psi_to_mpa(si["sigma_vme_max_psi"]), rel=1e-12)


def test_vme_rejects_bad_geometry_and_units():
    with pytest.raises(GeometryError):
        calculate_vme(3.5, 1.8, YP, 0.0, 0.0, 0.0)
    with pytest.raises(GeometryError):
        calculate_vme(3.5, -0.2, YP, 0.0, 0.0, 0.0)
    with pytest.raises(MaterialSpecificationError):
        calculate_vme(OD, WALL, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(UnitSystemError):
        calculate_vme(OD, WALL, YP, 0.0, 0.0, 0.0, unit_system="imperial")


# --- Module 2: ductile rupture ----------------------------------------------

def test_rupture_zero_axial_governs_on_rupture():
    """With F_a = 0 and P_e = 0 the pressure end-load alone drives |u| to ~0.47,
    where the rupture envelope is the lower of the two and governs."""
    res = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1")
    assert res["converged"]
    assert res["active_mode"] == "rupture"
    assert 0.0 < res["p_rupture_psi"] < res["p_vme_psi"]
    assert res["p_vme_psi"] == pytest.approx(2.0 / math.sqrt(3.0) * res["p_brc_psi"])
    assert res["p_tr_psi"] == pytest.approx(res["p_brc_psi"])


def test_rupture_governing_branch_is_the_lower_envelope():
    """The active mode must always be whichever envelope gives less capacity."""
    for fa in (0.0, 50000.0, 120000.0, 200000.0):
        res = calculate_ductile_rupture(OD, WALL, YP, 500.0, fa, grade="L80-1")
        u, pe = abs(res["u"]), 500.0
        m_rup = 1.0 + res["hardening_exponent"]
        rupture = pe + res["p_vme_psi"] * max(1.0 - u ** m_rup, 0.0) ** (1.0 / m_rup)
        necking = pe + res["p_tr_psi"] * max(1.0 - u ** 2.0, 0.0) ** 0.5
        assert res["p_rupture_psi"] == pytest.approx(min(rupture, necking), rel=1e-6)
        assert res["active_mode"] == ("rupture" if rupture <= necking else "necking")


def test_rupture_necking_governs_at_low_u():
    """Compression can pull |u| below the crossover, where necking governs.

    The minimum-envelope rule crosses over at exactly the spec's u_boundary, so
    this doubles as a check that the two formulations agree on the boundary.
    """
    probe = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1")
    # Offset the pressure end-load with compression to land near u ~ 0.
    fa = -0.60 * probe["f_u_lbf"]
    res = calculate_ductile_rupture(OD, WALL, YP, 0.0, fa, grade="L80-1")
    assert abs(res["u"]) < res["u_boundary"]
    assert res["active_mode"] == "necking"
    assert res["m_exponent"] == pytest.approx(2.0)


def test_rupture_fixed_point_is_self_consistent():
    """The root must satisfy the interaction envelope at P_i = P_br."""
    res = calculate_ductile_rupture(OD, WALL, YP, 1500.0, 60000.0, grade="L80-1")
    p, pe = res["p_rupture_psi"], 1500.0
    u, m = abs(res["u"]), res["m_exponent"]
    p_lim = res["p_limit_active_psi"]
    lhs = ((p - pe) / p_lim) ** m + u ** m
    assert lhs == pytest.approx(1.0, rel=1e-6)


def test_rupture_effective_wall_deductions():
    """w_e = w_n*k_wall - k_flaw*d_flaw, default d_flaw = 0.05*w_n."""
    res = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1")
    assert res["flaw_depth_in"] == pytest.approx(0.05 * WALL)
    assert res["effective_wall_in"] == pytest.approx(WALL * 0.875 - 0.05 * WALL)

    absolute = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1", flaw_depth=0.030)
    assert absolute["effective_wall_in"] == pytest.approx(WALL * 0.875 - 0.030)
    assert absolute["p_rupture_psi"] < res["p_rupture_psi"]

    with pytest.raises(GeometryError):
        calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1", flaw_depth=0.30)


def test_rupture_material_parameters():
    """n, k_n, k_bs against hand calculation for L80 (Y_p = 80 ksi)."""
    res = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, grade="L80-1")
    n = 0.182 - 0.000105 * 80.0
    assert res["hardening_exponent"] == pytest.approx(n)
    assert res["k_n"] == pytest.approx(1.0 + 0.5 ** n / (0.75 + n))
    assert res["k_bs"] == pytest.approx(0.95)          # L80 is quenched & tempered

    normalized = calculate_ductile_rupture(OD, WALL, 55000.0, 0.0, 0.0, grade="J-55")
    assert normalized["k_bs"] == pytest.approx(0.88)


def test_rupture_high_axial_derates_capacity():
    """Large tension raises |u| and cuts the pressure capacity."""
    low = calculate_ductile_rupture(OD, WALL, YP, 0.0, 10000.0, grade="L80-1")
    f_u = low["f_u_lbf"]
    high = calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.85 * f_u, grade="L80-1")
    assert abs(high["u"]) > abs(low["u"])
    assert high["p_rupture_psi"] < low["p_rupture_psi"]


def test_rupture_capacity_decreases_monotonically_with_tension():
    caps = [
        calculate_ductile_rupture(OD, WALL, YP, 0.0, fa, grade="L80-1")["p_rupture_psi"]
        for fa in (0.0, 50000.0, 100000.0, 150000.0, 200000.0)
    ]
    assert caps == sorted(caps, reverse=True)


def test_rupture_high_strain_hardening_requires_measured_fit():
    """22Cr/25Cr duplex must not fall back on the empirical n."""
    duplex = calculate_ductile_rupture(OD, WALL, 110000.0, 0.0, 0.0, grade="22Cr-110")
    assert duplex["hardening_exponent_source"] == "measured true stress-strain fit"
    assert duplex["hardening_exponent"] > 0.2

    with pytest.raises(MaterialSpecificationError):
        calculate_ductile_rupture(OD, WALL, 110000.0, 0.0, 0.0, grade="35Cr-Unobtainium")
    override = calculate_ductile_rupture(
        OD, WALL, 110000.0, 0.0, 0.0, grade="35Cr-Unobtainium",
        ultimate_strength=140000.0, hardening_exponent=0.25,
    )
    assert override["hardening_exponent"] == pytest.approx(0.25)


def test_rupture_requires_um_above_yield():
    with pytest.raises(MaterialSpecificationError):
        calculate_ductile_rupture(OD, WALL, YP, 0.0, 0.0, ultimate_strength=70000.0)


def test_rupture_si_round_trip():
    uscs = calculate_ductile_rupture(OD, WALL, YP, 1500.0, 60000.0, grade="L80-1")
    si = calculate_ductile_rupture(
        OD * 25.4, WALL * 25.4, psi_to_mpa(YP), psi_to_mpa(1500.0),
        60000.0 / 224.80894309971047, grade="L80-1", unit_system="SI",
    )
    assert si["p_rupture_psi"] == pytest.approx(uscs["p_rupture_psi"], rel=1e-9)
    assert si["p_rupture_mpa"] == pytest.approx(psi_to_mpa(uscs["p_rupture_psi"]), rel=1e-9)


# --- Module 3: collapse ------------------------------------------------------

def test_collapse_api_5c3_published_ratings():
    """Compare against API Bul 5C2 published *collapse* ratings (+/-3%)."""
    cases = [
        # (OD, wall, Yp, published collapse psi)
        (2.875, 0.217, 80000.0, 11160.0),   # 2-7/8" 6.5# L80
        (3.500, 0.254, 80000.0, 10530.0),   # 3-1/2" 9.2# L80
        (7.000, 0.317, 55000.0, 3270.0),    # 7" 23# J55
        (9.625, 0.545, 110000.0, 7950.0),   # 9-5/8" 53.5# P110
    ]
    for od, wall, yp, published in cases:
        res = calculate_collapse(od, wall, yp, 0.0)
        assert res["p_collapse_psi"] == pytest.approx(published, rel=0.03), (
            f"{od}\" x {wall}\" {yp/1000:.0f}ksi -> {res['p_collapse_psi']:.0f} psi "
            f"({res['regime']}) vs published {published:.0f} psi"
        )


def test_collapse_regimes_are_reachable():
    """The cascade must select all four regimes across the D/t range."""
    seen = {}
    for od, wall in ((4.5, 0.900), (4.5, 0.337), (7.0, 0.317), (9.625, 0.312),
                     (13.375, 0.330), (20.0, 0.250)):
        res = calculate_collapse(od, wall, 55000.0, 0.0)
        seen.setdefault(res["regime"], res["d_over_t"])
    assert {"Yield", "Plastic", "Transition", "Elastic"} <= set(seen), seen


def test_collapse_boundaries_are_ordered():
    constants = collapse_constants(80000.0)
    bounds = collapse_boundaries(80000.0, constants)
    assert bounds["dt_yp"] < bounds["dt_pt"] < bounds["dt_te"]


def test_collapse_curves_are_continuous_at_boundaries():
    """Adjacent regime formulas must agree where the cascade switches between
    them -- the check that caught the bad constants in the first place."""
    y_pa = 80000.0
    k = collapse_constants(y_pa)
    b = collapse_boundaries(y_pa, k)
    a, bb, c, f, g = k["A"], k["B"], k["C"], k["F"], k["G"]

    dt = b["dt_yp"]
    assert 2.0 * y_pa * ((dt - 1.0) / dt ** 2) == pytest.approx(y_pa * (a / dt - bb) - c, rel=1e-9)

    dt = b["dt_pt"]
    assert y_pa * (a / dt - bb) - c == pytest.approx(y_pa * (f / dt - g), rel=1e-9)

    dt = b["dt_te"]
    assert y_pa * (f / dt - g) == pytest.approx(46.95e6 / (dt * (dt - 1.0) ** 2), rel=1e-6)


def test_collapse_constants_against_api_table():
    """A, B, C for Y_pa = 80,000 psi against the API 5C3 tabulated values."""
    constants = collapse_constants(80000.0)
    assert constants["A"] == pytest.approx(3.071, abs=0.002)
    assert constants["B"] == pytest.approx(0.0667, abs=0.0005)
    assert constants["C"] == pytest.approx(1955.0, rel=0.01)


def test_collapse_tension_reduces_capacity_compression_raises_it():
    """Y_pa interaction: tension derates collapse, compression uprates it."""
    neutral = calculate_collapse(OD, WALL, YP, 0.0)
    tension = calculate_collapse(OD, WALL, YP, 150000.0)
    compression = calculate_collapse(OD, WALL, YP, -150000.0)
    assert tension["y_pa_psi"] < neutral["y_pa_psi"] < compression["y_pa_psi"]
    assert tension["p_collapse_psi"] < neutral["p_collapse_psi"] < compression["p_collapse_psi"]


def test_collapse_y_pa_formula():
    res = calculate_collapse(OD, WALL, YP, 120000.0)
    ratio = res["sigma_axial_psi"] / YP
    expected = (math.sqrt(1.0 - 0.75 * ratio ** 2) - 0.5 * ratio) * YP
    assert res["y_pa_psi"] == pytest.approx(expected, rel=1e-12)


def test_collapse_excludes_bending():
    """calculate_collapse takes no DLS: bending must not enter sigma_z. The axial
    stress it reports is exactly F_a / A_n."""
    res = calculate_collapse(OD, WALL, YP, 100000.0)
    assert res["sigma_axial_psi"] == pytest.approx(100000.0 / res["area_n_in2"], rel=1e-12)
    assert "beta_rad_per_in" not in res


def test_collapse_internal_pressure_credit():
    base = calculate_collapse(OD, WALL, YP, 0.0, p_internal=0.0)
    backed = calculate_collapse(OD, WALL, YP, 0.0, p_internal=2500.0)
    assert backed["p_collapse_psi"] == pytest.approx(base["p_collapse_psi"])
    assert backed["p_collapse_corrected_psi"] == pytest.approx(base["p_collapse_psi"] + 2500.0)


def test_collapse_yield_cutoff():
    """sigma_z >= Y_p terminates the calculation."""
    area = math.pi / 4.0 * (OD ** 2 - (OD - 2 * WALL) ** 2)
    with pytest.raises(YieldCutoffExceededError):
        calculate_collapse(OD, WALL, YP, YP * area * 1.01)
    with pytest.raises(YieldCutoffExceededError):
        calculate_collapse(OD, WALL, YP, -YP * area * 1.01)


def test_collapse_blocks_cold_expanded_pipe():
    with pytest.raises(ColdExpandedPipeError):
        calculate_collapse(OD, WALL, YP, 0.0, cold_expanded=True)


def test_collapse_si_round_trip():
    uscs = calculate_collapse(OD, WALL, YP, 80000.0, p_internal=2000.0)
    si = calculate_collapse(
        OD * 25.4, WALL * 25.4, psi_to_mpa(YP), 80000.0 / 224.80894309971047,
        p_internal=psi_to_mpa(2000.0), unit_system="SI",
    )
    assert si["p_collapse_psi"] == pytest.approx(uscs["p_collapse_psi"], rel=1e-9)
    assert si["p_collapse_corrected_mpa"] == pytest.approx(
        psi_to_mpa(uscs["p_collapse_corrected_psi"]), rel=1e-9
    )
