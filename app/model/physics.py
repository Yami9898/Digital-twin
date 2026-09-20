"""
app/model/physics.py
Équations différentielles du stérilisateur EtO.

Modèle recalibré :
  - TT112 redevient la température dynamique de paroi / double enveloppe.
  - La variable interne T_WALL est supprimée.
  - L'humidité possède une mémoire de charge P_H2O_LOAD afin d'éviter
    l'assèchement irréaliste des rinçages vers 0 %RH.
  - L'injection vapeur est maintenant pilotée vers HR300, sans affectation
    brutale, afin de conserver l'allure de la courbe.
  - Les phases de début cycle ont une calibration RH dédiée.
  - TT111 possède un profil thermique dédié au début du cycle afin d'éviter
    le refroidissement irréaliste pendant le vide initial.
  - Le comportement RH des rinçages est restauré à sa version du commit
    "Drive steam humidity to HR300 and reduce gas drying".
  - Une correction fine des cibles pression est appliquée aux zones où le
    rapport de référence montre un écart systématique : dilution azote et casse-vide
    finale. La stabilisation humidité n'est plus forcée en vide continu afin
    de conserver son profil RH calibré.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from app.model.signals import (
    WATER_VAPOR_KEY,
    WATER_LOAD_KEY,
    MIN_EFFECTIVE_PRESSURE,
    MIN_SATURATION_PRESSURE,
    TOTAL_ETO_MASS_KG,
    DELTA_PT111,
    DELTA_PT112,
    K112_TRACK,
    K112_PRESSURE,
    K191_PRECON_FROM_111,
    K191_PRECON_FROM_112,
    K191_PRECON_LOSS,
    PREEXPO_RH_EQ,
    PREEXPO_VAC_RH_EQ,
    GAS_INJECTION_RH_EQ,
    GAS_STAB_RH_EQ,
    VAPOR_RELAX_GAS_STAB,
    RINSE_DAMPING,
    RINSE_SMALL_NOISE,
    VAPOR_RELAX_RINSE,
    LOAD_DESORPTION_RATE,
    LOAD_ABSORPTION_RATE,
    LOAD_DEPLETION_FACTOR,
    RINSE_RH_FLOOR,
    STEAM_TARGET_RELAX,
    STEAM_LOAD_STORAGE,
    GAS_DRYING_DRIFT,
    effective_rate,
    compute_water_saturation_pressure_mbar,
    pressure_avg,
    saturation_pressure_of,
)
from app.model.constants import VARIABLES


def _cp(signals: Dict[str, float]) -> Dict[str, float]:
    return dict(signals)


_TT111_COEFFS: Dict[str, Dict[str, float]] = {
    "preconditioning": {"wall": 0.0008, "steam": 0.0,   "gas": 0.0,   "pressure": 0.0,   "loss": 0.0001},
    "vacuum":          {"wall": 0.020,  "steam": 0.0,   "gas": 0.0,   "pressure": 0.005, "loss": 0.001 },
    "steam_injection": {"wall": 0.015,  "steam": 0.015, "gas": 0.0,   "pressure": 0.002, "loss": 0.001 },
    "gas_injection":   {"wall": 0.020,  "steam": 0.0,   "gas": 0.003, "pressure": 0.002, "loss": 0.001 },
    "stabilisation":   {"wall": 0.025,  "steam": 0.0,   "gas": 0.0,   "pressure": 0.001, "loss": 0.001 },
    "exposure":        {"wall": 0.025,  "steam": 0.0,   "gas": 0.0,   "pressure": 0.0,   "loss": 0.001 },
    "rinse_vacuum":    {"wall": 0.020,  "steam": 0.0,   "gas": 0.0,   "pressure": 0.003, "loss": 0.001 },
    "rinse_break":     {"wall": 0.018,  "steam": 0.0,   "gas": 0.003, "pressure": 0.001, "loss": 0.001 },
    "default":         {"wall": 0.015,  "steam": 0.0,   "gas": 0.008, "pressure": 0.002, "loss": 0.001 },
}

_TT191_COEFFS: Dict[str, Dict[str, float]] = {
    "preconditioning": {"f111": K191_PRECON_FROM_111, "f112": K191_PRECON_FROM_112, "loss": K191_PRECON_LOSS},
    "vacuum":          {"f111": 0.015, "f112": 0.003, "loss": 0.0035},
    "rinse_vacuum":    {"f111": 0.015, "f112": 0.003, "loss": 0.0035},
    "steam_injection": {"f111": 0.020, "f112": 0.004, "loss": 0.0030},
    "gas_injection":   {"f111": 0.017, "f112": 0.003, "loss": 0.0035},
    "rinse_break":     {"f111": 0.017, "f112": 0.003, "loss": 0.0035},
    "stabilisation":   {"f111": 0.022, "f112": 0.004, "loss": 0.0030},
    "exposure":        {"f111": 0.018, "f112": 0.004, "loss": 0.0038},
    "default":         {"f111": 0.020, "f112": 0.004, "loss": 0.0032},
}


def classify_phase(phase_label: str) -> str:
    n = phase_label.lower()
    if "préconditionnement" in n or "preconditionnement" in n:
        return "preconditioning"
    is_rinse = "rinçage" in n or "rincage" in n or "rinse" in n
    if "exposition eto" in n:
        return "exposure"
    if is_rinse and ("vide" in n or "vacuum" in n):
        return "rinse_vacuum"
    if is_rinse and ("injection azote" in n or "casse vide" in n or "air vacuum break" in n):
        return "rinse_break"
    if "vide" in n or "vacuum" in n:
        return "vacuum"
    if "injection vapeur" in n or "steam injection" in n:
        return "steam_injection"
    if ("injection gaz" in n or "flush azote" in n or "injection azote" in n
            or "casse vide air" in n or "air vacuum break" in n):
        return "gas_injection"
    if "stabilisation" in n or "test de fuite" in n:
        return "stabilisation"
    return "default"


def _is_rinse_family(phase_label: str) -> bool:
    return classify_phase(phase_label) in {"rinse_vacuum", "rinse_break"}


def _is_steam_injection(phase_label: str) -> bool:
    return classify_phase(phase_label) == "steam_injection"


def _early_cycle_profile(phase_label: str) -> Optional[Tuple[float, float, float]]:
    """Cibles RH dédiées au début de cycle avant injection vapeur.

    Retourne (rh_cible, coefficient_relaxation, force_pompage_max).
    Ces profils évitent la chute irréaliste de RHT121 vers 0 %RH pendant
    les premiers vides, tout en gardant la chute réelle pendant la dilution.

    Important : le vide avant rinçage et les rinçages ne sont pas traités ici,
    afin de conserver la logique RH du commit f1c4c6d.
    """
    n = phase_label.lower()
    if "vide initial" in n:
        return 32.0, 0.18, 0.04
    if "test de fuite bas" in n or "low leak" in n:
        return 38.0, 0.12, 0.04
    if "dilution azote" in n and "injection" in n:
        return 39.0, 0.14, 0.04
    if "dilution azote" in n and ("vide" in n or "vacuum" in n):
        return 20.0, 0.16, 0.10
    return None


def _thermal_profile_for_phase(phase_label: str) -> Optional[Dict[str, float]]:
    """Coefficients TT111 spécifiques aux premières phases.

    Au début du cycle réel, TT111 monte avec la paroi malgré les phases de
    vide. Le modèle générique donnait trop de poids à dp_rate, ce qui créait
    une chute artificielle. Ces profils réduisent l'effet pression et donnent
    plus de poids à TT112 jusqu'à la stabilisation humidité.
    """
    n = phase_label.lower()
    if "vide initial" in n:
        return {"wall": 0.052, "steam": 0.0,   "gas": 0.0,    "pressure": 0.00035, "loss": 0.0002}
    if "test de fuite bas" in n or "low leak" in n:
        return {"wall": 0.055, "steam": 0.0,   "gas": 0.0,    "pressure": 0.0,     "loss": 0.0002}
    if "dilution azote" in n and "injection" in n:
        return {"wall": 0.046, "steam": 0.0,   "gas": 0.0007, "pressure": 0.0002,  "loss": 0.0003}
    if "dilution azote" in n and ("vide" in n or "vacuum" in n):
        return {"wall": 0.036, "steam": 0.0,   "gas": 0.0,    "pressure": 0.0008,  "loss": 0.0004}
    if "injection vapeur" in n or "steam injection" in n:
        return {"wall": 0.040, "steam": 0.010, "gas": 0.0,    "pressure": 0.0004,  "loss": 0.0003}
    if "stabilisation humidité" in n or "humidity stabilisation" in n or "humidity stabilization" in n:
        return {"wall": 0.045, "steam": 0.0,   "gas": 0.0,    "pressure": 0.0002,  "loss": 0.0002}
    if "injection gaz" in n:
        return {"wall": 0.034, "steam": 0.0,   "gas": 0.0012, "pressure": 0.0003,  "loss": 0.0004}
    return None


def _tt112_pressure_scale(phase_label: str) -> float:
    """Réduit l'effet pression sur TT112 dans les premières phases.

    TT112 représente la paroi / double enveloppe : elle ne doit pas chuter aussi
    vite que le gaz de chambre pendant le vide initial.
    """
    n = phase_label.lower()
    if "vide initial" in n:
        return 0.08
    if "test de fuite bas" in n or "low leak" in n:
        return 0.0
    if "dilution azote" in n and "injection" in n:
        return 0.20
    if "dilution azote" in n and ("vide" in n or "vacuum" in n):
        return 0.18
    if "injection vapeur" in n or "steam injection" in n:
        return 0.30
    if "stabilisation humidité" in n or "humidity stabilisation" in n or "humidity stabilization" in n:
        return 0.10
    return 1.0


def _pressure_target_correction(phase_label: str, target_p: float,
                                p_before: float, rate: float) -> Tuple[float, float]:
    """Correction fine des niveaux pression sans toucher aux rinçages.

    Cette fonction corrige seulement les niveaux où le rapport de référence montrait
    un écart systématique. Elle ne force plus le vide pendant toute la phase de
    stabilisation humidité, car cela déformait le profil RHT121 calibré.
    """
    n = phase_label.lower()
    corrected_target = float(target_p)
    corrected_rate = float(rate)

    if "dilution azote" in n and "injection" in n and 320.0 <= corrected_target < 365.0:
        corrected_target = 370.0
    elif "casse vide air finale" in n and 820.0 <= corrected_target < 870.0:
        corrected_target = 870.0

    if corrected_target != target_p:
        old_span = abs(float(target_p) - p_before)
        new_span = abs(corrected_target - p_before)
        if old_span > 1e-6 and new_span > old_span:
            corrected_rate *= new_span / old_span

    return corrected_target, corrected_rate


def advance_pressure(signals: Dict[str, float], target: float, rate: float,
                     fallback: float, dt: float,
                     d111: float = DELTA_PT111,
                     d112: float = DELTA_PT112) -> Dict[str, float]:
    s = _cp(signals)
    cur = pressure_avg(s)
    re = effective_rate(rate, fallback)
    delta = max(-re * dt, min(re * dt, target - cur))
    new_p = cur + delta
    s["PT111"] = new_p + d111
    s["PT112"] = new_p + d112
    return s


def hold_pressure(signals: Dict[str, float], target: float,
                  d111: float = DELTA_PT111,
                  d112: float = DELTA_PT112) -> Dict[str, float]:
    s = _cp(signals)
    s["PT111"] = target + d111
    s["PT112"] = target + d112
    return s


def apply_vapor_pumping(signals: Dict[str, float], p_before: float,
                        p_after: float, strength: float = 1.0) -> Dict[str, float]:
    s = _cp(signals)
    pb = max(MIN_EFFECTIVE_PRESSURE, p_before)
    pa = max(MIN_EFFECTIVE_PRESSURE, p_after)
    factor = (pa / pb) ** max(0.0, strength)
    s[WATER_VAPOR_KEY] *= factor
    if WATER_LOAD_KEY in s:
        s[WATER_LOAD_KEY] *= max(0.0, 1.0 - LOAD_DEPLETION_FACTOR * (1.0 - factor))
    return s


def apply_vapor_dilution(signals: Dict[str, float], p_before: float,
                         p_after: float, strength: float = 1.0) -> Dict[str, float]:
    s = _cp(signals)
    pb = max(MIN_EFFECTIVE_PRESSURE, p_before)
    pa = max(MIN_EFFECTIVE_PRESSURE, p_after)
    s[WATER_VAPOR_KEY] *= (pb / pa) ** max(0.0, strength)
    return s


def exchange_load_moisture(signals: Dict[str, float], dt: float,
                           phase_label: str = "") -> Dict[str, float]:
    s = _cp(signals)
    if WATER_LOAD_KEY not in s:
        s[WATER_LOAD_KEY] = s.get(WATER_VAPOR_KEY, 0.0)

    pv = max(0.0, s.get(WATER_VAPOR_KEY, 0.0))
    pload = max(0.0, s.get(WATER_LOAD_KEY, 0.0))
    delta = pload - pv
    if delta >= 0.0:
        transfer = LOAD_DESORPTION_RATE * delta * dt
    else:
        transfer = LOAD_ABSORPTION_RATE * delta * dt
    s[WATER_VAPOR_KEY] = max(0.0, pv + transfer)
    s[WATER_LOAD_KEY] = max(0.0, pload - transfer)

    if _is_rinse_family(phase_label):
        psat = saturation_pressure_of(s)
        s[WATER_VAPOR_KEY] = max(s[WATER_VAPOR_KEY], 0.01 * RINSE_RH_FLOOR * psat)

    return s


def relax_vapor(signals: Dict[str, float], target_rh: float, tau: float,
                dt: float, drift: float = 0.0) -> Dict[str, float]:
    s = _cp(signals)
    psat = max(MIN_SATURATION_PRESSURE,
               compute_water_saturation_pressure_mbar(s["TT111"]))
    pv_eq = max(0.0, 0.01 * max(0.0, target_rh) * psat)
    s[WATER_VAPOR_KEY] += tau * (pv_eq - s[WATER_VAPOR_KEY]) * dt - drift * dt
    s[WATER_VAPOR_KEY] = max(0.0, s[WATER_VAPOR_KEY])
    if WATER_LOAD_KEY in s:
        s[WATER_LOAD_KEY] += LOAD_ABSORPTION_RATE * (pv_eq - s[WATER_LOAD_KEY]) * dt
        s[WATER_LOAD_KEY] = max(0.0, s[WATER_LOAD_KEY])
    return s


def drive_vapor_to_rh(signals: Dict[str, float], target_rh: float,
                      dt: float, rate: float = STEAM_TARGET_RELAX,
                      load_storage: float = STEAM_LOAD_STORAGE) -> Dict[str, float]:
    """Pilote progressivement P_H2O vers une consigne %RH.

    Contrairement à une affectation directe de RHT121, cette fonction agit sur
    la pression de vapeur et sur l'humidité de charge. La courbe garde donc une
    montée progressive pendant l'injection vapeur et ne s'effondre pas pendant
    les phases suivantes.
    """
    s = _cp(signals)
    rh = max(0.0, min(100.0, float(target_rh)))
    psat = max(MIN_SATURATION_PRESSURE,
               compute_water_saturation_pressure_mbar(s["TT111"]))
    pv_target = 0.01 * rh * psat
    alpha = max(0.0, min(1.0, rate * dt))
    s[WATER_VAPOR_KEY] += alpha * (pv_target - s.get(WATER_VAPOR_KEY, 0.0))
    s[WATER_VAPOR_KEY] = max(0.0, s[WATER_VAPOR_KEY])
    s[WATER_LOAD_KEY] = max(s.get(WATER_LOAD_KEY, 0.0), load_storage * pv_target)
    return s


def inject_steam_vapor(signals: Dict[str, float], delta_p: float,
                       gain: float) -> Dict[str, float]:
    s = _cp(signals)
    added = max(0.0, delta_p) * max(0.0, gain)
    s[WATER_VAPOR_KEY] += added
    s[WATER_LOAD_KEY] = max(s.get(WATER_LOAD_KEY, 0.0), s[WATER_VAPOR_KEY] * 0.75)
    return s


def update_rh_from_vapor(signals: Dict[str, float]) -> Dict[str, float]:
    s = _cp(signals)
    psat = saturation_pressure_of(s)
    pvap = max(0.0, s.get(WATER_VAPOR_KEY, 0.0))
    s["RHT121"] = 100.0 * pvap / psat
    return s


def thermal(signals: Dict[str, float], phase_label: str, dt: float,
            p_before: float, steam_drive: float = 0.0,
            gas_drive: float = 0.0, jacket_sp: float = 49.0) -> Dict[str, float]:
    s = _cp(signals)
    fam = classify_phase(phase_label)
    p_after = pressure_avg(s)
    dp_rate = (p_after - p_before) / max(dt, 1e-6)

    # TT112 redevient la température dynamique de paroi / double enveloppe.
    # L'effet de pression est atténué au début du cycle : la paroi ne refroidit
    # pas aussi vite que le gaz lors du vide initial.
    wall_pressure_scale = _tt112_pressure_scale(phase_label)
    dT112 = (K112_TRACK * (jacket_sp - s["TT112"])
             + K112_PRESSURE * wall_pressure_scale * dp_rate)
    s["TT112"] += dT112 * dt

    co = _thermal_profile_for_phase(phase_label) or _TT111_COEFFS.get(fam, _TT111_COEFFS["default"])
    dT111 = (co["wall"] * (s["TT112"] - s["TT111"])
             + co["steam"] * max(0.0, steam_drive)
             - co["gas"] * max(0.0, gas_drive)
             + co["pressure"] * dp_rate
             - co["loss"] * (s["TT111"] - s["TT112"]))
    s["TT111"] += dT111 * dt

    co191 = _TT191_COEFFS.get(fam, _TT191_COEFFS["default"])
    dT191 = (co191["f111"] * (s["TT111"] - s["TT191"])
             + co191["f112"] * (s["TT112"] - s["TT191"])
             - co191["loss"] * (s["TT191"] - s["TT111"]))
    s["TT191"] += dT191 * dt
    return s


def finalize_state(signals: Dict[str, float]) -> Dict[str, float]:
    s = _cp(signals)
    for key in [*VARIABLES, WATER_VAPOR_KEY, WATER_LOAD_KEY]:
        v = s.get(key, 0.0)
        if not math.isfinite(v):
            s[key] = 0.0
    s[WATER_VAPOR_KEY] = max(0.0, s.get(WATER_VAPOR_KEY, 0.0))
    s[WATER_LOAD_KEY] = max(0.0, s.get(WATER_LOAD_KEY, s[WATER_VAPOR_KEY]))
    s["GT121"] = max(0.0, min(TOTAL_ETO_MASS_KG, s["GT121"]))
    s["TT112"] = max(0.0, min(80.0, s["TT112"]))
    s["TT111"] = max(0.0, min(80.0, s["TT111"]))
    s["TT191"] = max(0.0, min(80.0, s["TT191"]))
    s["PT111"] = max(0.0, s["PT111"])
    s["PT112"] = max(0.0, s["PT112"])
    psat = max(MIN_SATURATION_PRESSURE,
               compute_water_saturation_pressure_mbar(s["TT111"]))
    s[WATER_VAPOR_KEY] = min(s[WATER_VAPOR_KEY], 1.02 * psat)
    s[WATER_LOAD_KEY] = min(s[WATER_LOAD_KEY], 1.20 * psat)
    s["RHT121"] = 100.0 * s[WATER_VAPOR_KEY] / psat
    return s


def _micro_var(seed: float) -> float:
    return math.sin(seed) + 0.5 * math.sin(0.37 * seed + 1.2)


def preexpo_rh_eq(kind: str, signals: Dict[str, float], gf: float = 1.0,
                  prog: float = 0.0) -> float:
    tb = 0.05 * (signals["TT111"] - 30.0)
    if kind == "stabilisation":
        return PREEXPO_RH_EQ + tb
    if kind == "vacuum_after_stab":
        return PREEXPO_VAC_RH_EQ + 0.6 * tb
    if kind == "gas_injection":
        return GAS_INJECTION_RH_EQ - 1.2 * (gf - 1.0) - 1.4 * (1.0 - prog) + 0.5 * tb
    if kind == "gas_stabilisation":
        return GAS_STAB_RH_EQ - 0.8 * (gf - 1.0) + 0.5 * tb
    return signals["RHT121"]


def apply_gas_preexpo(signals: Dict[str, float], dt: float,
                      prog: float, gf: float) -> Dict[str, float]:
    rh_eq = preexpo_rh_eq("gas_injection", signals, gf, prog)
    tw = 1.0 + 0.45 * (1.0 - prog)
    return relax_vapor(signals, rh_eq, VAPOR_RELAX_GAS_STAB * tw, dt,
                       drift=GAS_DRYING_DRIFT * gf * tw)


def apply_rinse_effects(signals: Dict[str, float], dt: float, elapsed: float,
                        cycle_index: int, rh_tgt: float, pump_factor: float,
                        cool: float) -> Dict[str, float]:
    s = _cp(signals)
    noise = RINSE_SMALL_NOISE * _micro_var(
        (cycle_index + 1) * 7.0 + elapsed * 0.9 + pressure_avg(s) * 0.01
    )
    s[WATER_VAPOR_KEY] *= max(0.0, 1.0 - (pump_factor + RINSE_DAMPING * 0.25) * dt)
    s = exchange_load_moisture(s, dt, "rinse")
    return relax_vapor(s, max(RINSE_RH_FLOOR, rh_tgt + noise), VAPOR_RELAX_RINSE, dt)


def step_physics(signals: Dict[str, float], actuators, dt: float,
                 params: dict, phase_label: str = "") -> Dict[str, float]:
    s = dict(signals)
    p_before = pressure_avg(s)
    early_profile = _early_cycle_profile(phase_label)

    target_p = params.get("target_p", p_before)
    rate = params.get("rate", 999.0)
    fallback = params.get("fallback", 79.0)
    d111 = params.get("d111", DELTA_PT111)
    d112 = params.get("d112", DELTA_PT112)
    jacket_sp = params.get("jacket_sp", 49.0)

    target_p, rate = _pressure_target_correction(phase_label, target_p, p_before, rate)

    moving = (actuators.VP_vacuum and actuators.PV_vide) or actuators.PV_N2 \
             or actuators.PV_EtO or actuators.PV_steam or actuators.PV_air

    if moving:
        s = advance_pressure(s, target_p, rate, fallback, dt, d111, d112)
    else:
        s = hold_pressure(s, p_before, d111, d112)

    p_after = pressure_avg(s)

    s = thermal(s, phase_label, dt, p_before,
                steam_drive=params.get("steam_drive", 0.0),
                gas_drive=params.get("gas_drive", 0.0),
                jacket_sp=jacket_sp)

    strength = params.get("vapor_strength", 1.0)
    if early_profile is not None:
        # Les premiers vides ne doivent pas assécher comme un vide final :
        # la charge relargue encore beaucoup d'humidité.
        strength = min(strength, early_profile[2])

    if p_after < p_before - 1e-6:
        s = apply_vapor_pumping(s, p_before, p_after, strength)
    elif p_after > p_before + 1e-6:
        s = apply_vapor_dilution(s, p_before, p_after, strength)

    s = exchange_load_moisture(s, dt, phase_label)

    vapor_rh: Optional[float] = params.get("vapor_rh")
    if vapor_rh is not None:
        if _is_rinse_family(phase_label):
            vapor_rh = max(float(vapor_rh), RINSE_RH_FLOOR)
        if _is_steam_injection(phase_label):
            # HR300 est une consigne à atteindre pendant l'injection vapeur.
            s = drive_vapor_to_rh(s, vapor_rh, dt)
        else:
            s = relax_vapor(s, vapor_rh,
                            params.get("vapor_k", 0.05),
                            dt,
                            params.get("vapor_drift", 0.0))
    elif early_profile is not None:
        rh_target, tau, _ = early_profile
        s = relax_vapor(s, rh_target, tau, dt)

    s = update_rh_from_vapor(s)
    s = finalize_state(s)
    return s
