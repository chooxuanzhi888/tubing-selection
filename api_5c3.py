"""API TR 5C3 / ISO 10400 tubing limit-state engine.

Three design checks, each callable on its own:

* ``calculate_vme``              -- Clause 6, triaxial (von Mises) yield of the pipe body.
* ``calculate_ductile_rupture``  -- Clause 7, ductile rupture / axial necking under combined load.
* ``calculate_collapse``         -- Clause 8, external pressure resistance.

Unit policy
-----------
Every solver computes in **USCS** internally (psi, in, lbf, lbf-ft) because the
Clause 8 empirical constants are dimensional and only valid with ``Y_pa`` in psi.
Callers may pass ``unit_system="SI"``; inputs are then converted on entry and the
pressure/stress results are converted back to MPa on exit. The USCS values are
always retained in the result dictionary under their ``*_psi`` keys so a caller
can audit the native computation.

SI input convention: D and w_n in mm, pressures/strengths in MPa, axial force in
kN, torque in N-m, DLS in deg/30m.
USCS input convention: D and w_n in in, pressures/strengths in psi, axial force
in lbf, torque in lbf-ft, DLS in deg/100ft.
"""

import math

# -----------------------------------------------------------------------------
# EXCEPTIONS
# -----------------------------------------------------------------------------


class APIDesignError(Exception):
    """Base class for every API 5C3 / ISO 10400 limit-state failure."""


class UnitSystemError(APIDesignError):
    """An unrecognised unit system was requested."""


class GeometryError(APIDesignError):
    """Pipe geometry is non-physical (non-positive wall, wall >= radius, ...)."""


class MaterialSpecificationError(APIDesignError):
    """A required material property is missing or outside the model's validity.

    Raised for high strain-hardening alloys (duplex / super-duplex, n > 0.2)
    where the empirical ``n = 0.182 - 0.000105*Y_p`` estimate is not applicable
    and no measured true stress-strain fit has been supplied.
    """


class YieldCutoffExceededError(APIDesignError):
    """|sigma_z| >= Y_p: the pipe yields axially before collapse can be evaluated."""


class ColdExpandedPipeError(APIDesignError):
    """Cold-expanded / cold-worked line pipe: the Bauschinger effect invalidates
    the API collapse equations, so Clause 8 must not be run."""


class ConvergenceError(APIDesignError):
    """A non-linear solver failed to converge."""


# -----------------------------------------------------------------------------
# UNIT CONVERSION
# -----------------------------------------------------------------------------

MM_PER_IN = 25.4
PSI_PER_MPA = 145.03773800721814
LBF_PER_KN = 224.80894309971047
LBF_FT_PER_N_M = 0.7375621492772654

USCS = "USCS"
SI = "SI"


def _check_unit_system(unit_system):
    system = str(unit_system).upper()
    if system not in (USCS, SI):
        raise UnitSystemError(
            f"Unknown unit system '{unit_system}'. Use 'USCS' (psi, in, lbf, lbf-ft) or 'SI' (MPa, mm, kN, N-m)."
        )
    return system


def to_uscs(unit_system, length_mm_or_in=None, pressure=None, force=None, torque=None):
    """Convert a bundle of optional inputs into USCS. ``None`` passes through."""
    system = _check_unit_system(unit_system)
    if system == USCS:
        return length_mm_or_in, pressure, force, torque
    return (
        None if length_mm_or_in is None else length_mm_or_in / MM_PER_IN,
        None if pressure is None else pressure * PSI_PER_MPA,
        None if force is None else force * LBF_PER_KN,
        None if torque is None else torque * LBF_FT_PER_N_M,
    )


def psi_to_mpa(value):
    return value / PSI_PER_MPA


def dls_to_beta_rad_per_in(dls, unit_system=USCS):
    """Convert dogleg severity to curvature in rad/in (the internal USCS unit).

    USCS input is deg/100ft: beta = DLS * (pi/180) / 1200.
    SI input is deg/30m: beta[rad/m] = DLS * (pi/180) / 30, then rad/m -> rad/in.
    """
    system = _check_unit_system(unit_system)
    if dls is None:
        return 0.0
    if system == USCS:
        return float(dls) * (math.pi / 180.0) / 1200.0
    beta_rad_per_m = float(dls) * (math.pi / 180.0) / 30.0
    return beta_rad_per_m * 0.0254


# -----------------------------------------------------------------------------
# MATERIAL LIBRARY
# -----------------------------------------------------------------------------


def normalize_grade_key(grade):
    """Collapse a grade label to a lookup key: uppercase, no spaces/hyphens."""
    return str(grade).upper().replace(" ", "").replace("-", "").replace("_", "")


# Minimum ultimate tensile strength U_m [psi] per API 5CT / manufacturer data.
ULTIMATE_TENSILE_PSI = {
    "H40": 60000.0, "J55": 75000.0, "K55": 95000.0, "M65": 85000.0,
    "C75": 95000.0, "N80": 100000.0, "L80": 95000.0, "L801": 95000.0,
    "L8013CR": 95000.0, "C90": 100000.0, "C95": 105000.0, "T95": 105000.0,
    "P105": 120000.0, "P110": 125000.0, "Q125": 135000.0,
    "S13CR110": 125000.0, "17CR110": 125000.0,
    "22CR110": 125000.0, "25CR125": 135000.0,
}

# k_bs: 0.95 quenched & tempered / 13Cr, 0.88 normalized or as-rolled (default).
QUENCHED_AND_TEMPERED = {
    "C75", "L80", "L801", "L8013CR", "C90", "C95", "T95", "P105", "P110",
    "Q125", "S13CR110", "17CR110", "22CR110", "25CR125",
}
K_BS_QT = 0.95
K_BS_NORMALIZED = 0.88

# Young's modulus [psi]. Duplex / super-duplex run softer than carbon steel.
YOUNGS_MODULUS_PSI = {
    "22CR110": 28.5e6, "25CR125": 28.5e6,
    "S13CR110": 29.0e6, "17CR110": 29.0e6, "L8013CR": 29.0e6,
}
DEFAULT_YOUNGS_MODULUS_PSI = 30.0e6

# Grades whose measured strain-hardening exponent exceeds the 0.2 validity limit
# of the empirical n-estimate. Clause 7 requires a measured true stress-strain
# fit for these; a grade listed here without an entry raises
# MaterialSpecificationError.
HIGH_STRAIN_HARDENING_GRADES = {"22CR110", "25CR125"}
MEASURED_HARDENING_EXPONENT = {
    "22CR110": 0.220,   # 22Cr duplex, solution-annealed
    "25CR125": 0.240,   # 25Cr super-duplex, solution-annealed
}

# Cold-expanded (cold-worked) line pipe blocks Clause 8 entirely.
COLD_EXPANDED_GRADES = set()

STRAIN_HARDENING_VALIDITY_LIMIT = 0.2


def ultimate_tensile_psi(grade, override=None):
    """U_m [psi] for a grade. ``override`` wins; unknown grades raise."""
    if override is not None:
        return float(override)
    key = normalize_grade_key(grade)
    if key not in ULTIMATE_TENSILE_PSI:
        raise MaterialSpecificationError(
            f"No ultimate tensile strength on file for grade '{grade}'. "
            "Supply U_m explicitly (mill certificate) before running the Clause 7 rupture check."
        )
    return ULTIMATE_TENSILE_PSI[key]


def bending_strength_factor(grade, override=None):
    """k_bs: 0.95 for quenched & tempered / 13Cr, 0.88 otherwise."""
    if override is not None:
        return float(override)
    return K_BS_QT if normalize_grade_key(grade) in QUENCHED_AND_TEMPERED else K_BS_NORMALIZED


def youngs_modulus_psi(grade, override=None):
    if override is not None:
        return float(override)
    return YOUNGS_MODULUS_PSI.get(normalize_grade_key(grade), DEFAULT_YOUNGS_MODULUS_PSI)


def strain_hardening_exponent(yield_psi, grade=None, override=None):
    """Strain-hardening exponent n.

    Empirical estimate n = 0.182 - 0.000105*Y_p with Y_p in ksi. For grades whose
    measured n exceeds the 0.2 validity limit (duplex / super-duplex) the
    empirical estimate is overridden by a measured fit, and its absence is a hard
    error rather than a silent fallback.
    """
    if override is not None:
        n = float(override)
        if not math.isfinite(n) or n <= 0.0:
            raise MaterialSpecificationError("Strain-hardening exponent override must be finite and positive.")
        return n, "user-specified"

    key = normalize_grade_key(grade) if grade is not None else None
    if key in MEASURED_HARDENING_EXPONENT:
        return MEASURED_HARDENING_EXPONENT[key], "measured true stress-strain fit"
    if key in HIGH_STRAIN_HARDENING_GRADES:
        raise MaterialSpecificationError(
            f"Grade '{grade}' is a high strain-hardening alloy (n > {STRAIN_HARDENING_VALIDITY_LIMIT}). "
            "The empirical n = 0.182 - 0.000105*Y_p estimate is invalid; supply a measured "
            "true stress-strain fit via hardening_exponent."
        )

    n = 0.182 - 0.000105 * (float(yield_psi) / 1000.0)
    if n <= 0.0:
        raise MaterialSpecificationError(
            f"Empirical strain-hardening exponent is non-positive (n = {n:.4f}) for Y_p = {yield_psi:.0f} psi. "
            "Supply a measured value."
        )
    if n > STRAIN_HARDENING_VALIDITY_LIMIT:
        raise MaterialSpecificationError(
            f"Empirical n = {n:.4f} exceeds the {STRAIN_HARDENING_VALIDITY_LIMIT} validity limit. "
            "Supply a measured true stress-strain fit via hardening_exponent."
        )
    return n, "empirical (0.182 - 0.000105*Y_p)"


# -----------------------------------------------------------------------------
# SHARED GEOMETRY
# -----------------------------------------------------------------------------


def _section_properties(od_in, wall_in, k_wall):
    """Nominal and wall-tolerance-reduced section properties, all USCS."""
    for name, value in (("outside diameter", od_in), ("wall thickness", wall_in)):
        if not math.isfinite(value) or value <= 0.0:
            raise GeometryError(f"Pipe {name} must be finite and positive (got {value}).")
    if not 0.0 < k_wall <= 1.0:
        raise GeometryError(f"Wall tolerance factor k_wall must be in (0, 1] (got {k_wall}).")
    if 2.0 * wall_in >= od_in:
        raise GeometryError(f"Wall thickness {wall_in} in leaves no bore in a {od_in} in OD pipe.")

    r_o = od_in / 2.0
    d_n = od_in - 2.0 * wall_in                       # nominal ID
    r_iw = (od_in - 2.0 * wall_in * k_wall) / 2.0     # tolerance-reduced bore radius
    a_n = (math.pi / 4.0) * (od_in ** 2 - d_n ** 2)   # nominal steel area
    j_n = (math.pi / 32.0) * (od_in ** 4 - d_n ** 4)  # nominal polar moment
    return {
        "r_o_in": r_o, "r_iw_in": r_iw, "d_n_in": d_n,
        "area_n_in2": a_n, "polar_j_n_in4": j_n,
    }


# -----------------------------------------------------------------------------
# MODULE 1 -- CLAUSE 6: TRIAXIAL YIELD OF THE PIPE BODY
# -----------------------------------------------------------------------------


def calculate_vme(od, wall, yield_strength, p_internal, p_external, axial_force,
                  dls=0.0, torque=0.0, youngs_modulus=None, grade=None,
                  k_wall=0.875, unit_system=USCS):
    """Clause 6 triaxial check: sigma_VME,max <= Y_p.

    Evaluates sigma_VME across the critical radial and circumferential fibre
    coordinates: inner (r_iw) and outer (r_o) radii crossed with the maximum
    tensile and compressive bending fibres. Point count follows the standard --
    4 with bending and torsion, 2 with torsion alone, 1 with neither.

    Returns a dict of results (USCS keys always present; SI keys added when
    ``unit_system='SI'``).
    """
    system = _check_unit_system(unit_system)
    if system == SI:
        od_in = od / MM_PER_IN
        wall_in = wall / MM_PER_IN
        yp_psi = yield_strength * PSI_PER_MPA
        pi_psi = p_internal * PSI_PER_MPA
        pe_psi = p_external * PSI_PER_MPA
        fa_lbf = axial_force * LBF_PER_KN
        torque_lbf_ft = torque * LBF_FT_PER_N_M
    else:
        od_in, wall_in = float(od), float(wall)
        yp_psi = float(yield_strength)
        pi_psi, pe_psi = float(p_internal), float(p_external)
        fa_lbf = float(axial_force)
        torque_lbf_ft = float(torque)

    if not math.isfinite(yp_psi) or yp_psi <= 0.0:
        raise MaterialSpecificationError(f"Yield strength must be finite and positive (got {yield_strength}).")

    geom = _section_properties(od_in, wall_in, k_wall)
    r_o, r_iw = geom["r_o_in"], geom["r_iw_in"]
    a_n, j_n = geom["area_n_in2"], geom["polar_j_n_in4"]

    e_psi = youngs_modulus_psi(grade, youngs_modulus)
    beta = dls_to_beta_rad_per_in(dls, system)
    torque_lbf_in = torque_lbf_ft * 12.0

    # Uniform axial stress and the bending stress amplitude at the outer fibre.
    sigma_za = fa_lbf / a_n
    sigma_zb = e_psi * od_in * beta / 2.0

    has_bending = abs(sigma_zb) > 1e-9
    has_torsion = abs(torque_lbf_in) > 1e-9

    # Lame thick-cylinder constants evaluated on the tolerance-reduced bore.
    denom = r_o ** 2 - r_iw ** 2
    if denom <= 0.0:
        raise GeometryError("Tolerance-reduced bore radius is not smaller than the outer radius.")
    lame_mean = (pi_psi * r_iw ** 2 - pe_psi * r_o ** 2) / denom
    lame_amp = (pi_psi - pe_psi) * r_iw ** 2 * r_o ** 2 / denom

    radii = [("inner", r_iw), ("outer", r_o)] if (has_bending or has_torsion) else [("inner", r_iw)]
    fibres = [("tensile", 1.0), ("compressive", -1.0)] if has_bending else [("neutral", 0.0)]

    points = []
    for radius_label, r in radii:
        sigma_r = lame_mean - lame_amp / (r ** 2)
        sigma_theta = lame_mean + lame_amp / (r ** 2)
        tau = torque_lbf_in * r / j_n if has_torsion else 0.0
        for fibre_label, sign in fibres:
            sigma_z = sigma_za + sign * sigma_zb
            vme = math.sqrt(
                0.5 * ((sigma_r - sigma_theta) ** 2
                       + (sigma_theta - sigma_z) ** 2
                       + (sigma_z - sigma_r) ** 2)
                + 3.0 * tau ** 2
            )
            points.append({
                "radius": radius_label, "r_in": r, "fibre": fibre_label,
                "sigma_r_psi": sigma_r, "sigma_theta_psi": sigma_theta,
                "sigma_z_psi": sigma_z, "tau_psi": tau, "sigma_vme_psi": vme,
            })

    governing = max(points, key=lambda p: p["sigma_vme_psi"])
    vme_max = governing["sigma_vme_psi"]

    result = {
        "sigma_vme_max_psi": vme_max,
        "yield_psi": yp_psi,
        "safety_factor": (yp_psi / vme_max) if vme_max > 0.0 else float("inf"),
        "passes": vme_max <= yp_psi,
        "governing_point": governing,
        "evaluation_points": points,
        "n_points": len(points),
        "sigma_axial_uniform_psi": sigma_za,
        "sigma_bending_psi": sigma_zb,
        "beta_rad_per_in": beta,
        "youngs_modulus_psi": e_psi,
        "unit_system": system,
        **geom,
    }
    if system == SI:
        result["sigma_vme_max_mpa"] = psi_to_mpa(vme_max)
        result["yield_mpa"] = psi_to_mpa(yp_psi)
    return result


# -----------------------------------------------------------------------------
# MODULE 2 -- CLAUSE 7: DUCTILE RUPTURE UNDER COMBINED LOADING
# -----------------------------------------------------------------------------

M_NECK = 2.0
_NR_MAX_ITER = 100
_NR_TOL_PSI = 1e-6


def calculate_ductile_rupture(od, wall, yield_strength, p_external, axial_force,
                              ultimate_strength=None, grade=None, k_wall=0.875,
                              k_flaw=1.0, flaw_depth=None, flaw_depth_fraction=0.05,
                              bending_strength_factor_override=None,
                              hardening_exponent=None, unit_system=USCS):
    """Clause 7 combined-load rupture capacity P_br.

    F_eff depends on P_i, so with F_a held fixed the capacity is the fixed point
    P_i = P_br. Solved by Newton-Raphson with a bisection fallback. The active
    limit state (rupture vs axial necking) is re-selected from |u| on every
    iteration so the returned root sits on the correct branch.
    """
    system = _check_unit_system(unit_system)
    if system == SI:
        od_in = od / MM_PER_IN
        wall_in = wall / MM_PER_IN
        yp_psi = yield_strength * PSI_PER_MPA
        pe_psi = p_external * PSI_PER_MPA
        fa_lbf = axial_force * LBF_PER_KN
        um_psi = None if ultimate_strength is None else ultimate_strength * PSI_PER_MPA
        flaw_in = None if flaw_depth is None else flaw_depth / MM_PER_IN
    else:
        od_in, wall_in = float(od), float(wall)
        yp_psi = float(yield_strength)
        pe_psi = float(p_external)
        fa_lbf = float(axial_force)
        um_psi = None if ultimate_strength is None else float(ultimate_strength)
        flaw_in = None if flaw_depth is None else float(flaw_depth)

    if not math.isfinite(yp_psi) or yp_psi <= 0.0:
        raise MaterialSpecificationError(f"Yield strength must be finite and positive (got {yield_strength}).")

    geom = _section_properties(od_in, wall_in, k_wall)
    d_n, a_n = geom["d_n_in"], geom["area_n_in2"]

    um_psi = ultimate_tensile_psi(grade, um_psi)
    if um_psi <= yp_psi:
        raise MaterialSpecificationError(
            f"Ultimate tensile strength ({um_psi:.0f} psi) must exceed yield ({yp_psi:.0f} psi)."
        )

    # Effective wall: tolerance reduction, then the inspection flaw deduction.
    d_flaw = flaw_depth_fraction * wall_in if flaw_in is None else flaw_in
    w_e = wall_in * k_wall - k_flaw * d_flaw
    if w_e <= 0.0:
        raise GeometryError(
            f"Effective wall thickness is non-positive (w_e = {w_e:.4f} in) after the "
            f"{k_wall:.3f} tolerance factor and a {d_flaw:.4f} in flaw deduction."
        )
    if 2.0 * w_e >= od_in:
        raise GeometryError("Effective wall thickness leaves no bore.")

    n, n_source = strain_hardening_exponent(yp_psi, grade, hardening_exponent)
    k_n = 1.0 + (0.5 ** n) / (0.75 + n)
    k_bs = bending_strength_factor(grade, bending_strength_factor_override)

    p_brc = k_bs * k_n * um_psi * math.log(od_in / (od_in - 2.0 * w_e))
    p_vme = (2.0 / math.sqrt(3.0)) * p_brc
    p_tr = p_brc
    f_u = um_psi * a_n

    m_rup = 1.0 + n
    # Spec's stated crossover, reported for traceability. It is NOT used to pick
    # the branch: applying it literally makes the capacity jump discontinuously
    # (and selects the *higher* of the two limit states below the boundary). The
    # governing capacity is the lower of the two envelopes, which is continuous
    # in |u| and conservative -- whichever limit state is reached first governs.
    u_boundary = ((p_vme - p_tr) / p_vme) ** (1.0 / m_rup)

    def _u_of(p_i):
        f_eff = fa_lbf + (math.pi / 4.0) * (p_i * d_n ** 2 - pe_psi * od_in ** 2)
        return f_eff / f_u, f_eff

    def _envelope(p_lim, m, u_abs):
        if u_abs >= 1.0:
            return pe_psi  # axial load alone consumes the section: no pressure capacity
        return pe_psi + p_lim * (1.0 - u_abs ** m) ** (1.0 / m)

    def _branch(u_abs):
        """Return (mode, m, p_limit) for the governing limit state at this |u|."""
        rupture = _envelope(p_vme, m_rup, u_abs)
        necking = _envelope(p_tr, M_NECK, u_abs)
        if rupture <= necking:
            return "rupture", m_rup, p_vme, rupture
        return "necking", M_NECK, p_tr, necking

    def _capacity(p_i):
        """Right-hand side: the P_br the interaction envelope allows at this P_i."""
        u, _ = _u_of(p_i)
        return _branch(abs(u))[3]

    def _residual(p_i):
        return p_i - _capacity(p_i)

    # Newton-Raphson on g(P) = P - capacity(P). The capacity term is piecewise in
    # |u|, so the derivative is taken numerically.
    p = pe_psi + p_brc
    converged = False
    iterations = 0
    for iterations in range(1, _NR_MAX_ITER + 1):
        g = _residual(p)
        if abs(g) < _NR_TOL_PSI:
            converged = True
            break
        h = max(1.0, abs(p) * 1e-6)
        slope = (_residual(p + h) - _residual(p - h)) / (2.0 * h)
        if not math.isfinite(slope) or abs(slope) < 1e-12:
            break
        step = g / slope
        p_next = p - step
        if not math.isfinite(p_next):
            break
        # Keep the iterate physical: capacity can never fall below P_e.
        p = max(p_next, pe_psi)

    if not converged:
        # Bisection fallback over [P_e, P_e + 2*P_vme]; g is continuous and
        # g(P_e) <= 0 <= g(P_e + 2*P_vme) whenever a root exists.
        lo, hi = pe_psi, pe_psi + 2.0 * p_vme + 1.0
        g_lo, g_hi = _residual(lo), _residual(hi)
        if g_lo > 0.0 or g_hi < 0.0:
            raise ConvergenceError(
                "Ductile rupture solver could not bracket a root; check the axial load and external pressure."
            )
        for iterations in range(1, 201):
            mid = 0.5 * (lo + hi)
            g_mid = _residual(mid)
            if abs(g_mid) < _NR_TOL_PSI or (hi - lo) < _NR_TOL_PSI:
                p = mid
                converged = True
                break
            if g_mid < 0.0:
                lo = mid
            else:
                hi = mid
        else:
            raise ConvergenceError("Ductile rupture solver failed to converge in 200 bisection steps.")
        p = 0.5 * (lo + hi) if not converged else p

    u_final, f_eff_final = _u_of(p)
    mode, m_active, p_lim_active, _ = _branch(abs(u_final))

    result = {
        "p_rupture_psi": p,
        "p_brc_psi": p_brc,
        "p_vme_psi": p_vme,
        "p_tr_psi": p_tr,
        "effective_wall_in": w_e,
        "flaw_depth_in": d_flaw,
        "hardening_exponent": n,
        "hardening_exponent_source": n_source,
        "k_n": k_n,
        "k_bs": k_bs,
        "ultimate_psi": um_psi,
        "f_u_lbf": f_u,
        "f_eff_lbf": f_eff_final,
        "u": u_final,
        "u_boundary": u_boundary,
        "active_mode": mode,
        "m_exponent": m_active,
        "p_limit_active_psi": p_lim_active,
        "iterations": iterations,
        "converged": converged,
        "unit_system": system,
        **geom,
    }
    if system == SI:
        result["p_rupture_mpa"] = psi_to_mpa(p)
        result["p_brc_mpa"] = psi_to_mpa(p_brc)
    return result


# -----------------------------------------------------------------------------
# MODULE 3 -- CLAUSE 8: EXTERNAL PRESSURE RESISTANCE / COLLAPSE
# -----------------------------------------------------------------------------


ELASTIC_COLLAPSE_COEFF = 46.95e6

# The API curve-fit constants are regressed over the API 5CT grade range. Below
# Y_pa ~= 15.1 ksi the C constant turns negative (and below ~3 ksi the (D/t)_yp
# radicand does too), so the fit is extrapolated nonsense rather than a collapse
# rating. Y_pa can fall into that range when the axial stress approaches yield;
# 16,000 psi is the first round value at which C > 0 with margin.
COLLAPSE_YIELD_VALIDITY_MIN_PSI = 16000.0


def collapse_constants(y_pa_psi):
    """Empirical constants A, B, C, F, G. Y_pa must be in psi (native USCS).

    These are the API TR 5C3 / Bul 5C3 curve-fit constants. Reproduces the
    tabulated A = 3.071, B = 0.0667, C = 1955 at Y_pa = 80,000 psi.
    """
    if not math.isfinite(y_pa_psi) or y_pa_psi < COLLAPSE_YIELD_VALIDITY_MIN_PSI:
        raise MaterialSpecificationError(
            f"Y_pa = {y_pa_psi} psi is outside the validity range of the API collapse curve fits "
            f"(minimum {COLLAPSE_YIELD_VALIDITY_MIN_PSI:.0f} psi)."
        )
    a = (2.8762
         + 0.10679e-5 * y_pa_psi
         + 0.21301e-10 * y_pa_psi ** 2
         - 0.53132e-16 * y_pa_psi ** 3)
    b = 0.026233 + 0.50609e-6 * y_pa_psi
    c = (-465.93
         + 0.030867 * y_pa_psi
         - 0.10483e-7 * y_pa_psi ** 2
         + 0.36989e-13 * y_pa_psi ** 3)

    # F and G are fixed by the requirement that the transition and elastic
    # curves meet tangentially; they do not depend on the pipe's own D/t.
    ba = b / a
    t = 3.0 * ba / (2.0 + ba)
    f_denom = y_pa_psi * (t - ba) * (1.0 - t) ** 2
    if abs(f_denom) < 1e-12:
        raise MaterialSpecificationError(
            f"Degenerate transition-collapse constant F at Y_pa = {y_pa_psi:.0f} psi."
        )
    f = ELASTIC_COLLAPSE_COEFF * t ** 3 / f_denom
    g = f * ba
    return {"A": a, "B": b, "C": c, "F": f, "G": g}


def collapse_boundaries(y_pa_psi, constants):
    """Regime D/t boundaries: (D/t)_yp, (D/t)_pt, (D/t)_te."""
    a, b, c = constants["A"], constants["B"], constants["C"]
    f, g = constants["F"], constants["G"]

    bc = b + c / y_pa_psi
    dt_yp = (math.sqrt((a - 2.0) ** 2 + 8.0 * bc) + (a - 2.0)) / (2.0 * bc)

    pt_denom = c + y_pa_psi * (b - g)
    dt_pt = (y_pa_psi * (a - f) / pt_denom) if abs(pt_denom) > 1e-12 else float("inf")

    ba = b / a
    dt_te = (2.0 + ba) / (3.0 * ba)

    return {"dt_yp": dt_yp, "dt_pt": dt_pt, "dt_te": dt_te}


def calculate_collapse(od, wall, yield_strength, axial_force, p_internal=0.0,
                       grade=None, k_wall=0.875, cold_expanded=False,
                       unit_system=USCS):
    """Clause 8 collapse resistance with axial-load interaction.

    Bending stress is deliberately excluded: only the uniform axial stress
    sigma_z = F_a / A_n enters Y_pa. The returned ``p_collapse_corrected_psi`` is
    the limiting *external* pressure, already carrying the +P_i back-up credit.
    """
    system = _check_unit_system(unit_system)
    if system == SI:
        od_in = od / MM_PER_IN
        wall_in = wall / MM_PER_IN
        yp_psi = yield_strength * PSI_PER_MPA
        fa_lbf = axial_force * LBF_PER_KN
        pi_psi = p_internal * PSI_PER_MPA
    else:
        od_in, wall_in = float(od), float(wall)
        yp_psi = float(yield_strength)
        fa_lbf = float(axial_force)
        pi_psi = float(p_internal)

    if cold_expanded or normalize_grade_key(grade) in COLD_EXPANDED_GRADES:
        raise ColdExpandedPipeError(
            f"Grade '{grade}' is cold-expanded / cold-worked line pipe. The Bauschinger effect "
            "invalidates the API 5C3 collapse equations; use a measured collapse rating instead."
        )
    if not math.isfinite(yp_psi) or yp_psi <= 0.0:
        raise MaterialSpecificationError(f"Yield strength must be finite and positive (got {yield_strength}).")

    geom = _section_properties(od_in, wall_in, k_wall)
    a_n = geom["area_n_in2"]

    # Step 1: uniform axial stress, bending excluded.
    sigma_z = fa_lbf / a_n
    ratio = sigma_z / yp_psi
    if abs(ratio) >= 1.0:
        raise YieldCutoffExceededError(
            f"Uniform axial stress ({sigma_z:.0f} psi) reaches or exceeds yield ({yp_psi:.0f} psi). "
            "The pipe yields axially before collapse can be evaluated."
        )

    # Step 2: axial-stress equivalent yield.
    y_pa = (math.sqrt(1.0 - 0.75 * ratio ** 2) - 0.5 * ratio) * yp_psi
    if y_pa <= 0.0:
        raise YieldCutoffExceededError(
            f"Axial-stress equivalent yield is non-positive (Y_pa = {y_pa:.0f} psi)."
        )
    if y_pa < COLLAPSE_YIELD_VALIDITY_MIN_PSI:
        raise YieldCutoffExceededError(
            f"Axial tension has driven the equivalent yield to Y_pa = {y_pa:.0f} psi, below the "
            f"{COLLAPSE_YIELD_VALIDITY_MIN_PSI:.0f} psi validity floor of the API collapse curve fits "
            f"(sigma_z = {sigma_z:.0f} psi against Y_p = {yp_psi:.0f} psi). The axial load is the "
            "governing limit state here, not collapse."
        )

    # Step 3-4: regime constants and D/t boundaries, both from Y_pa.
    d_over_t = od_in / wall_in
    constants = collapse_constants(y_pa)
    bounds = collapse_boundaries(y_pa, constants)

    # Step 5: regime cascade.
    a, b, c = constants["A"], constants["B"], constants["C"]
    f, g = constants["F"], constants["G"]
    if d_over_t <= bounds["dt_yp"]:
        regime = "Yield"
        p_c = 2.0 * y_pa * ((d_over_t - 1.0) / d_over_t ** 2)
    elif d_over_t <= bounds["dt_pt"]:
        regime = "Plastic"
        p_c = y_pa * (a / d_over_t - b) - c
    elif d_over_t <= bounds["dt_te"]:
        regime = "Transition"
        p_c = y_pa * (f / d_over_t - g)
    else:
        regime = "Elastic"
        p_c = ELASTIC_COLLAPSE_COEFF / (d_over_t * (d_over_t - 1.0) ** 2)

    p_c = max(p_c, 0.0)
    # Step 6: internal pressure backs up the wall against external collapse.
    p_c_corr = p_c + pi_psi

    result = {
        "p_collapse_psi": p_c,
        "p_collapse_corrected_psi": p_c_corr,
        "regime": regime,
        "d_over_t": d_over_t,
        "sigma_axial_psi": sigma_z,
        "y_pa_psi": y_pa,
        "yield_psi": yp_psi,
        "constants": constants,
        "boundaries": bounds,
        "p_internal_psi": pi_psi,
        "unit_system": system,
        **geom,
    }
    if system == SI:
        result["p_collapse_mpa"] = psi_to_mpa(p_c)
        result["p_collapse_corrected_mpa"] = psi_to_mpa(p_c_corr)
    return result
