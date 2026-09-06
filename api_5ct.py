"""API Spec 5CT / ISO 11960 product-specification verification.

Four mill acceptance requirements, each callable on its own:

* ``calculate_min_elongation``            -- minimum gauge-length elongation.
* ``calculate_hydrostatic_test_pressure`` -- production hydrostatic proof test.
* ``calculate_min_cvn``                   -- Charpy V-notch absorbed energy.
* ``calculate_as_quenched_hardness``      -- as-quenched hardenability target.

These are *product specification* checks -- what the pipe must have satisfied at
the mill -- not well-load capacities. Only the hydrostatic proof-test pressure
is a design gate in the screening engine: operating above the pressure at which
a joint's integrity was demonstrated is a genuine deficiency. The other three
are reported acceptance requirements.

Unit policy
-----------
Follows ``api_5c3``: each solver computes natively in one system and converts at
the boundary. Elongation and the proof test are native **USCS** (psi, in). The
Charpy expressions are native **SI** (MPa, mm, J) -- see below -- and convert to
ft-lb on exit. Hardenability is dimensionless. USCS keys are always present in
the result; SI keys are added when ``unit_system='SI'``.

Charpy coefficient set
----------------------
The four CVN expressions in API 5CT are frequently transcribed as though the
transverse/longitudinal split were an SI/USCS split, with the same coefficients
(0.00118, 0.01288) quoted for both. That cannot be dimensionally correct. The
additive terms and every floor are exact unit conversions of one another
(2.04 J = 1.50 ft-lb, 4.08 J = 3.01 ft-lb, 20 J = 14.8 ft-lb, 41 J = 30.2 ft-lb,
11 J = 8.1 ft-lb), so the real distinction is the *component*, not the unit
system: the pipe body is rated on specified minimum yield Y_S, the coupling on
specified **maximum** yield Y_S,max, because a harder coupling is the
safety-critical case for toughness.

This module therefore carries one native-SI coefficient set, applied with
whichever yield the component calls for. For audit, the equivalent USCS-native
transverse form is

    CVN [ft-lb] = Y_S [ksi] * (0.1524 * t [in] + 0.0655) + 1.5

which reproduces the SI expression to within rounding.
"""

import math

from api_5c3 import (
    MM_PER_IN,
    PSI_PER_MPA,
    QUENCHED_AND_TEMPERED,
    SI,
    USCS,
    _check_unit_system,
    normalize_grade_key,
    psi_to_mpa,
    ultimate_tensile_psi,
)

# -----------------------------------------------------------------------------
# EXCEPTIONS
# -----------------------------------------------------------------------------


class APIProductSpecError(Exception):
    """Base class for every API 5CT / ISO 11960 verification failure."""


class SpecimenGeometryError(APIProductSpecError):
    """Pipe geometry admits no permissible test specimen."""


class CarbonContentRangeError(APIProductSpecError):
    """Carbon content is outside the 0.15-0.50 wt% validity range of the
    hardenability correlations."""


class GradeDataUnavailableError(APIProductSpecError):
    """A required per-grade property (specified maximum yield, carbon content)
    is not on file and was not supplied explicitly."""


# -----------------------------------------------------------------------------
# CONVERSIONS AND ROUNDING
# -----------------------------------------------------------------------------

J_PER_FT_LB = 1.3558179483314004
IN2_PER_MM2 = 1.0 / (MM_PER_IN ** 2)


def joules_to_ft_lb(value):
    return value / J_PER_FT_LB


def _round_to(value, step):
    """Round to the nearest multiple of ``step``."""
    return round(value / step) * step


def round_elongation_pct(e):
    """5CT rounding: nearest 0.5% below 10%, nearest 1% at or above.

    The threshold is tested on the *unrounded* value, so 9.9% rounds to 10.0 via
    the 0.5% rule rather than being promoted into the integer rule first.
    """
    return _round_to(e, 0.5) if e < 10.0 else float(round(e))


def round_test_pressure(pressure, unit_system=USCS):
    """Nearest 100 psi (USCS) or 0.5 MPa (SI)."""
    return _round_to(pressure, 100.0) if _check_unit_system(unit_system) == USCS else _round_to(pressure, 0.5)


# -----------------------------------------------------------------------------
# GRADE LIBRARY
# -----------------------------------------------------------------------------

# API 5CT specified MAXIMUM yield strength [psi]. Couplings are rated on the
# maximum rather than the minimum: the hardest coupling the specification allows
# is the safety-critical case for toughness, so the coupling CVN requirement is
# driven by this value.
SPECIFIED_MAX_YIELD_PSI = {
    "H40": 80000.0, "J55": 80000.0, "K55": 80000.0, "M65": 85000.0,
    "N80": 110000.0, "C75": 90000.0, "L80": 95000.0, "L801": 95000.0,
    "L8013CR": 95000.0, "C90": 105000.0, "C95": 110000.0, "T95": 110000.0,
    "C110": 120000.0, "P105": 135000.0, "P110": 140000.0, "Q125": 150000.0,
    "S13CR110": 140000.0, "17CR110": 140000.0,
    "22CR110": 140000.0, "25CR125": 150000.0,
}

# Specified maximum carbon content [wt %] from the API 5CT chemical
# requirements. Representative values -- for a real order these are superseded
# by the mill certificate, which is what the ``carbon_pct`` override is for.
SPECIFIED_CARBON_MAX_PCT = {
    "H40": 0.50, "J55": 0.50, "K55": 0.50, "M65": 0.50, "N80": 0.50,
    "C75": 0.50, "L80": 0.43, "L801": 0.43,
    "C90": 0.35, "C95": 0.45, "T95": 0.35, "C110": 0.35,
    "P105": 0.30, "P110": 0.30, "Q125": 0.35,
}

# Raised CVN floor class: the high-strength Q&T grades.
CVN_HIGH_FLOOR_GRADES = {"P110", "Q125", "C110"}

CVN_FLOOR_J = {
    # (transverse, longitudinal) full-size absorbed energy floors [J]
    "high": (20.0, 41.0),      # P110, Q125, C110
    "standard": (14.0, 27.0),  # other Q&T grades
}
CVN_SUBSIZE_ABSOLUTE_FLOOR_J = 11.0

CVN_SUBSIZE_FACTOR = {"full": 1.0, "three_quarter": 0.75, "half": 0.50}

# Hardenability targets a martensite fraction produced by quenching a carbon or
# low-alloy steel. The CRA grades are solution-annealed or cold-worked
# austenitic / duplex / martensitic-stainless products with no such target, so
# the correlation does not apply to them at all.
HARDENABILITY_NOT_APPLICABLE = {
    "L8013CR", "S13CR110", "17CR110", "22CR110", "25CR125",
}

CARBON_MIN_PCT = 0.15
CARBON_MAX_PCT = 0.50

# HRC_min = slope * C + intercept, with the martensite fraction each pair proves.
HARDENABILITY_HIGH_MARTENSITE = {"C90", "T95"}
_HRC_COEFFS = {
    "c90_t95": (58.0, 17.2, 90.0),
    "c110": (59.0, 18.2, 95.0),
    "other_qt": (52.0, 14.0, 50.0),
}


def specified_max_yield_psi(grade, override=None):
    """Y_S,max [psi] for a grade. ``override`` wins; unknown grades raise."""
    if override is not None:
        return float(override)
    key = normalize_grade_key(grade)
    if key not in SPECIFIED_MAX_YIELD_PSI:
        raise GradeDataUnavailableError(
            f"No specified maximum yield strength on file for grade '{grade}'. "
            "Supply yield_max explicitly (mill certificate) before rating a coupling."
        )
    return SPECIFIED_MAX_YIELD_PSI[key]


def specified_carbon_pct(grade, override=None):
    """Carbon content [wt %] for a grade. ``override`` wins; unknown grades raise."""
    if override is not None:
        return float(override)
    key = normalize_grade_key(grade)
    if key not in SPECIFIED_CARBON_MAX_PCT:
        raise GradeDataUnavailableError(
            f"No carbon content on file for grade '{grade}'. Supply carbon_pct "
            "explicitly (mill certificate) before running the hardenability check."
        )
    return SPECIFIED_CARBON_MAX_PCT[key]


# -----------------------------------------------------------------------------
# MODULE 1 -- MINIMUM ELONGATION
# -----------------------------------------------------------------------------

# e = C * A^0.2 / U^0.9. The constant absorbs the units of A and U, so it is not
# a free parameter: 625000 pairs with in^2 and psi, 1944 with mm^2 and MPa.
ELONGATION_C_USCS = 625000.0
ELONGATION_C_SI = 1944.0
ELONGATION_C_ISO_11960 = 1942.57

# Maximum effective specimen area. A larger physical specimen does not earn a
# lower elongation requirement -- the area is capped before it enters the
# correlation.
AREA_CAP_IN2 = 0.75
AREA_CAP_MM2 = 490.0

# Fixed round-bar areas: 12.7 mm and 8.9 mm diameter reduced sections.
ROUND_BAR_AREA_MM2 = {"round_bar_12.7mm": 130.0, "round_bar_8.9mm": 62.0}

# A round bar must be machined entirely from within the wall, so the wall has to
# exceed the bar diameter by a machining allowance. Below these thicknesses the
# specimen is prohibited and a strip must be used instead.
ROUND_BAR_127_MIN_WALL_MM = 19.05   # 0.750 in
ROUND_BAR_89_MIN_WALL_MM = 12.70    # 0.500 in

# Standard rectangular (strip) reduced-section width.
STRIP_WIDTH_MM = 38.1               # 1.5 in


def _select_specimen(wall_mm):
    """Pick the largest permissible specimen. Returns (basis, area_mm2, reason).

    ``reason`` explains why a round bar was prohibited, or None when one was
    selected.
    """
    if wall_mm >= ROUND_BAR_127_MIN_WALL_MM:
        return "round_bar_12.7mm", ROUND_BAR_AREA_MM2["round_bar_12.7mm"], None
    if wall_mm >= ROUND_BAR_89_MIN_WALL_MM:
        return (
            "round_bar_8.9mm",
            ROUND_BAR_AREA_MM2["round_bar_8.9mm"],
            f"12.7 mm round bar prohibited: wall {wall_mm:.2f} mm is below the "
            f"{ROUND_BAR_127_MIN_WALL_MM:.2f} mm required to machine one.",
        )
    return (
        "strip",
        wall_mm * STRIP_WIDTH_MM,
        f"Round bars prohibited: wall {wall_mm:.2f} mm is below the "
        f"{ROUND_BAR_89_MIN_WALL_MM:.2f} mm needed for the smallest (8.9 mm) bar.",
    )


def calculate_min_elongation(wall, ultimate_strength=None, grade=None, specimen=None,
                             iso_11960=False, unit_system=USCS):
    """Minimum elongation in a 50.8 mm (2.0 in) gauge length [%].

        e = C * A^0.2 / U^0.9

    The specimen is auto-selected from the wall thickness unless ``specimen`` is
    given ('round_bar_12.7mm', 'round_bar_8.9mm' or 'strip'); an explicitly
    requested round bar the wall cannot produce raises SpecimenGeometryError.
    """
    system = _check_unit_system(unit_system)
    wall_in = float(wall) / MM_PER_IN if system == SI else float(wall)
    um_psi = ultimate_strength
    if um_psi is not None and system == SI:
        um_psi = float(um_psi) * PSI_PER_MPA
    um_psi = ultimate_tensile_psi(grade, um_psi)

    if not math.isfinite(wall_in) or wall_in <= 0.0:
        raise SpecimenGeometryError(f"Wall thickness must be finite and positive (got {wall}).")
    if not math.isfinite(um_psi) or um_psi <= 0.0:
        raise GradeDataUnavailableError(f"Ultimate tensile strength must be finite and positive (got {um_psi}).")

    wall_mm = wall_in * MM_PER_IN
    auto_basis, auto_area_mm2, prohibited_reason = _select_specimen(wall_mm)

    if specimen is None:
        basis, area_mm2 = auto_basis, auto_area_mm2
    elif specimen == "strip":
        basis, area_mm2 = "strip", wall_mm * STRIP_WIDTH_MM
        prohibited_reason = None
    elif specimen in ROUND_BAR_AREA_MM2:
        minimum = ROUND_BAR_127_MIN_WALL_MM if specimen == "round_bar_12.7mm" else ROUND_BAR_89_MIN_WALL_MM
        if wall_mm < minimum:
            raise SpecimenGeometryError(
                f"A {specimen} specimen cannot be machined from a {wall_mm:.2f} mm wall "
                f"(needs {minimum:.2f} mm). Use a strip specimen."
            )
        basis, area_mm2 = specimen, ROUND_BAR_AREA_MM2[specimen]
        prohibited_reason = None
    else:
        raise SpecimenGeometryError(
            f"Unknown specimen '{specimen}'. Use 'round_bar_12.7mm', 'round_bar_8.9mm', 'strip', or None to auto-select."
        )

    # Cap before the correlation: extra area earns no relief.
    area_capped = area_mm2 > AREA_CAP_MM2
    if area_capped:
        area_mm2 = AREA_CAP_MM2
    area_in2 = area_mm2 * IN2_PER_MM2

    if system == SI:
        c = ELONGATION_C_ISO_11960 if iso_11960 else ELONGATION_C_SI
        e_raw = c * (area_mm2 ** 0.2) / (psi_to_mpa(um_psi) ** 0.9)
    else:
        c = ELONGATION_C_USCS
        e_raw = c * (area_in2 ** 0.2) / (um_psi ** 0.9)

    result = {
        "min_elongation_pct": round_elongation_pct(e_raw),
        "min_elongation_pct_unrounded": e_raw,
        "specimen_basis": basis,
        "specimen_area_in2": area_in2,
        "specimen_area_mm2": area_mm2,
        "area_capped": area_capped,
        "round_bar_prohibited_reason": prohibited_reason,
        "constant_c": c,
        "ultimate_psi": um_psi,
        "gauge_length_in": 2.0,
        "unit_system": system,
    }
    if system == SI:
        result["ultimate_mpa"] = psi_to_mpa(um_psi)
    return result


# -----------------------------------------------------------------------------
# MODULE 2 -- HYDROSTATIC PROOF-TEST PRESSURE
# -----------------------------------------------------------------------------

DESIGN_FACTOR_DEFAULT = 0.80
DESIGN_FACTOR_LARGE_LOW_GRADE = 0.60
LARGE_OD_THRESHOLD_IN = 9.625            # 9-5/8 in = 244.48 mm
LOW_GRADE_LARGE_OD = {"H40", "J55", "K55"}

STANDARD_TEST_PRESSURE_CAP_PSI = 10000.0  # 69.0 MPa
MILL_FLOOR_PSI = 3000.0                   # 20.5 MPa


def hydrostatic_design_factor(od_in, grade, override=None):
    """Design stress factor f, with the basis for the choice.

    Grades H40/J55/K55 above 9-5/8 in OD test at 0.60 as standard; f = 0.80 is a
    permitted alternative for them, which is why the basis string says so.
    """
    if override is not None:
        return float(override), "user-specified"
    if normalize_grade_key(grade) in LOW_GRADE_LARGE_OD and od_in > LARGE_OD_THRESHOLD_IN:
        return (
            DESIGN_FACTOR_LARGE_LOW_GRADE,
            f"0.60 standard for {grade} above {LARGE_OD_THRESHOLD_IN} in OD "
            "(f = 0.80 is a permitted alternative)",
        )
    return DESIGN_FACTOR_DEFAULT, "0.80 default (80% of specified minimum yield)"


def calculate_hydrostatic_test_pressure(od, wall, yield_strength, grade=None,
                                        design_factor=None, p_thread_leak=None,
                                        apply_mill_floor=False, unit_system=USCS):
    """Production hydrostatic proof-test pressure.

        P = 2 * Y_S * f * t / D

    Caps are applied in specification order and the result is rounded last, so
    the rounding never moves a value back across a threshold it has just been
    checked against.

    The 10,000 psi cap does **not** clamp P: exceeding it means the joint needs a
    specially agreed test, so the result is flagged
    ``alternative_test_pressure_required`` and the computed pressure retained.
    The 3,000 psi mill floor is likewise only flagged unless ``apply_mill_floor``
    is set, since over-testing pipe is the user's decision to make.
    """
    system = _check_unit_system(unit_system)
    if system == SI:
        od_in = float(od) / MM_PER_IN
        wall_in = float(wall) / MM_PER_IN
        ys_psi = float(yield_strength) * PSI_PER_MPA
        leak_psi = None if p_thread_leak is None else float(p_thread_leak) * PSI_PER_MPA
    else:
        od_in, wall_in = float(od), float(wall)
        ys_psi = float(yield_strength)
        leak_psi = None if p_thread_leak is None else float(p_thread_leak)

    for name, value in (("outside diameter", od_in), ("wall thickness", wall_in), ("yield strength", ys_psi)):
        if not math.isfinite(value) or value <= 0.0:
            raise APIProductSpecError(f"Pipe {name} must be finite and positive (got {value}).")
    if 2.0 * wall_in >= od_in:
        raise APIProductSpecError(f"Wall thickness {wall_in} in leaves no bore in a {od_in} in OD pipe.")

    f, f_basis = hydrostatic_design_factor(od_in, grade, design_factor)
    p_psi = 2.0 * ys_psi * f * wall_in / od_in
    p_body_psi = p_psi
    flags = []

    # Cap: flag, never clamp.
    alternative_required = p_psi > STANDARD_TEST_PRESSURE_CAP_PSI
    if alternative_required:
        flags.append(
            f"Alternative Test Pressures: computed {p_psi:.0f} psi exceeds the "
            f"{STANDARD_TEST_PRESSURE_CAP_PSI:.0f} psi standard cap; a specially agreed test is required."
        )

    # Thread leak governs when the connection is weaker than the pipe body.
    thread_leak_governs = False
    if leak_psi is None:
        thread_leak_basis = "no thread-leak rating supplied — pipe body governs"
    elif leak_psi < p_psi:
        thread_leak_governs = True
        p_psi = leak_psi
        thread_leak_basis = f"thread leak / jump-out at {leak_psi:.0f} psi governs over the pipe body"
        flags.append(
            f"Thread-leak override: test pressure limited to {leak_psi:.0f} psi by the connection, "
            f"below the {p_body_psi:.0f} psi pipe-body value."
        )
    else:
        thread_leak_basis = f"thread-leak rating {leak_psi:.0f} psi is above the pipe-body value — no override"

    below_floor = p_psi < MILL_FLOOR_PSI
    if below_floor:
        if apply_mill_floor:
            p_psi = MILL_FLOOR_PSI
            flags.append(f"Raised to the {MILL_FLOOR_PSI:.0f} psi minimum mill testing floor.")
        else:
            flags.append(
                f"Computed test pressure {p_psi:.0f} psi is below the {MILL_FLOOR_PSI:.0f} psi "
                "minimum mill testing floor; pass apply_mill_floor=True to raise it."
            )

    p_rounded_psi = round_test_pressure(p_psi, USCS)

    result = {
        "p_test_psi": p_rounded_psi,
        "p_test_unrounded_psi": p_psi,
        "p_body_psi": p_body_psi,
        "design_factor": f,
        "design_factor_basis": f_basis,
        "alternative_test_pressure_required": alternative_required,
        "thread_leak_governs": thread_leak_governs,
        "thread_leak_basis": thread_leak_basis,
        "below_mill_floor": below_floor,
        "mill_floor_applied": below_floor and apply_mill_floor,
        "flags": flags,
        "yield_psi": ys_psi,
        "unit_system": system,
    }
    if system == SI:
        result["p_test_mpa"] = round_test_pressure(psi_to_mpa(p_psi), SI)
        result["p_test_unrounded_mpa"] = psi_to_mpa(p_psi)
        result["yield_mpa"] = psi_to_mpa(ys_psi)
    return result


# -----------------------------------------------------------------------------
# MODULE 3 -- CHARPY V-NOTCH ABSORBED ENERGY
# -----------------------------------------------------------------------------

# Native-SI coefficients: Y [MPa], t [mm] -> CVN [J]. See the module docstring
# for why the longitudinal set is exactly double the transverse one, and why the
# split is by component rather than by unit system.
CVN_COEFFS_SI = {
    "transverse": (0.00118, 0.01288, 2.04),
    "longitudinal": (0.00236, 0.02576, 4.08),
}

# A half-size (10 x 5 mm) specimen is the smallest the standard recognises. Below
# the wall that can produce one, physical testing is waived in favour of a QA
# manufacturing process check.
HALF_SIZE_MIN_WALL_MM = 6.35   # 0.250 in


def calculate_min_cvn(wall, yield_strength, grade=None, component="pipe_body",
                      orientation="transverse", specimen_size="full",
                      yield_max=None, unit_system=USCS):
    """Minimum Charpy V-notch absorbed energy.

        transverse:   CVN_full = Y * (0.00118*t + 0.01288) + 2.04
        longitudinal: CVN_full = Y * (0.00236*t + 0.02576) + 4.08

    with Y = Y_S for the pipe body and Y = Y_S,max for a coupling. The grade
    floor is applied to the full-size value *before* sub-size scaling, then the
    11 J absolute floor is applied after it.
    """
    system = _check_unit_system(unit_system)
    if component not in ("pipe_body", "coupling"):
        raise APIProductSpecError(f"Unknown component '{component}'. Use 'pipe_body' or 'coupling'.")
    if orientation not in CVN_COEFFS_SI:
        raise APIProductSpecError(f"Unknown orientation '{orientation}'. Use 'transverse' or 'longitudinal'.")
    if specimen_size not in CVN_SUBSIZE_FACTOR:
        raise APIProductSpecError(
            f"Unknown specimen size '{specimen_size}'. Use 'full', 'three_quarter' or 'half'."
        )

    if system == SI:
        wall_mm = float(wall)
        ys_psi = float(yield_strength) * PSI_PER_MPA
    else:
        wall_mm = float(wall) * MM_PER_IN
        ys_psi = float(yield_strength)

    if not math.isfinite(wall_mm) or wall_mm <= 0.0:
        raise SpecimenGeometryError(f"Wall thickness must be finite and positive (got {wall}).")
    if not math.isfinite(ys_psi) or ys_psi <= 0.0:
        raise GradeDataUnavailableError(f"Yield strength must be finite and positive (got {yield_strength}).")

    if component == "coupling":
        y_psi = specified_max_yield_psi(grade, yield_max)
        y_basis = "specified maximum yield (Y_S,max)"
    else:
        y_psi = ys_psi
        y_basis = "specified minimum yield (Y_S)"
    y_mpa = psi_to_mpa(y_psi)

    slope, intercept, constant = CVN_COEFFS_SI[orientation]
    cvn_full_j = y_mpa * (slope * wall_mm + intercept) + constant

    # Grade floor on the full-size value. Non-Q&T grades carry no floor class.
    key = normalize_grade_key(grade) if grade is not None else None
    floor_applicable = key in QUENCHED_AND_TEMPERED
    governing_floor_j = None
    floor_applied = False
    if floor_applicable:
        floor_class = "high" if key in CVN_HIGH_FLOOR_GRADES else "standard"
        transverse_floor, longitudinal_floor = CVN_FLOOR_J[floor_class]
        governing_floor_j = transverse_floor if orientation == "transverse" else longitudinal_floor
        if cvn_full_j < governing_floor_j:
            cvn_full_j = governing_floor_j
            floor_applied = True

    f_sub = CVN_SUBSIZE_FACTOR[specimen_size]
    cvn_required_j = cvn_full_j * f_sub

    subsize_floor_applied = f_sub < 1.0 and cvn_required_j < CVN_SUBSIZE_ABSOLUTE_FLOOR_J
    if subsize_floor_applied:
        cvn_required_j = CVN_SUBSIZE_ABSOLUTE_FLOOR_J

    testing_waived = wall_mm < HALF_SIZE_MIN_WALL_MM

    result = {
        "cvn_required_j": cvn_required_j,
        "cvn_required_ftlb": joules_to_ft_lb(cvn_required_j),
        "cvn_full_size_j": cvn_full_j,
        "cvn_full_size_ftlb": joules_to_ft_lb(cvn_full_j),
        "f_sub": f_sub,
        "specimen_size": specimen_size,
        "component": component,
        "orientation": orientation,
        "yield_basis": y_basis,
        "yield_used_psi": y_psi,
        "yield_used_mpa": y_mpa,
        "floor_applicable": floor_applicable,
        "floor_applied": floor_applied,
        "governing_floor_j": governing_floor_j,
        "subsize_floor_applied": subsize_floor_applied,
        "testing_waived": testing_waived,
        "qa_process_check_required": testing_waived,
        "wall_mm": wall_mm,
        "unit_system": system,
    }
    if testing_waived:
        result["waive_reason"] = (
            f"Wall {wall_mm:.2f} mm cannot produce a half-size (10 x 5 mm) longitudinal specimen "
            f"(needs {HALF_SIZE_MIN_WALL_MM:.2f} mm). Physical testing is waived; a QA "
            "manufacturing process check is required instead."
        )
    return result


# -----------------------------------------------------------------------------
# MODULE 4 -- AS-QUENCHED HARDENABILITY
# -----------------------------------------------------------------------------


def calculate_as_quenched_hardness(grade, carbon_pct=None, unit_system=USCS):
    """Minimum as-quenched Rockwell C hardness proving the required martensite
    fraction.

        C90, T95  (>=90% martensite):  HRC_min = 58*C + 17.2
        C110      (>=95% martensite):  HRC_min = 59*C + 18.2
        other Q&T (>=50% martensite):  HRC_min = 52*C + 14.0

    C is a whole weight percentage: 0.25 means 0.25%, not 0.0025. The hardness
    must be verified at mid-wall -- the position of maximum section thickness,
    which quenches slowest and is therefore the least martensitic.

    Grades outside the quenched-and-tempered carbon/low-alloy family return
    ``applicable = False`` rather than raising: the correlation has no meaning
    for a solution-annealed CRA, but that is not a caller error.
    """
    system = _check_unit_system(unit_system)
    key = normalize_grade_key(grade)

    if key in HARDENABILITY_NOT_APPLICABLE:
        return {
            "applicable": False,
            "reason": (
                f"Grade '{grade}' is a corrosion-resistant alloy supplied solution-annealed or "
                "cold-worked. It has no as-quenched martensite target, so the hardenability "
                "correlation does not apply."
            ),
            "hrc_min": None, "carbon_pct": None,
            "martensite_fraction_min_pct": None,
            "grade": grade, "unit_system": system,
        }
    if key not in QUENCHED_AND_TEMPERED:
        return {
            "applicable": False,
            "reason": (
                f"Grade '{grade}' is not quenched and tempered (normalized or as-rolled). "
                "The as-quenched hardenability requirement applies only to Q&T products."
            ),
            "hrc_min": None, "carbon_pct": None,
            "martensite_fraction_min_pct": None,
            "grade": grade, "unit_system": system,
        }

    c = specified_carbon_pct(grade, carbon_pct)
    if not math.isfinite(c):
        raise CarbonContentRangeError(f"Carbon content must be finite (got {c}).")
    if c < CARBON_MIN_PCT:
        # The classic input error is passing a mass fraction instead of a
        # percentage, which lands two orders of magnitude low.
        hint = (
            f" Carbon is entered as a whole percentage: use {c * 100.0:.2f} for {c * 100.0:.2f}%, not {c}."
            if c < CARBON_MIN_PCT / 10.0 else ""
        )
        raise CarbonContentRangeError(
            f"Carbon content {c} wt% is below the {CARBON_MIN_PCT} wt% validity limit of the "
            f"hardenability correlation.{hint}"
        )
    if c > CARBON_MAX_PCT:
        raise CarbonContentRangeError(
            f"Carbon content {c} wt% exceeds the {CARBON_MAX_PCT} wt% validity limit of the "
            "hardenability correlation."
        )

    if key in HARDENABILITY_HIGH_MARTENSITE:
        slope, intercept, martensite = _HRC_COEFFS["c90_t95"]
    elif key == "C110":
        slope, intercept, martensite = _HRC_COEFFS["c110"]
    else:
        slope, intercept, martensite = _HRC_COEFFS["other_qt"]

    return {
        "applicable": True,
        "reason": None,
        "hrc_min": slope * c + intercept,
        "carbon_pct": c,
        "martensite_fraction_min_pct": martensite,
        "slope": slope,
        "intercept": intercept,
        "evaluation_position": "mid-wall (position of maximum section thickness)",
        "grade": grade,
        "unit_system": system,
    }
