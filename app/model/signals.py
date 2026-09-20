"""
app/model/signals.py
Constantes physiques calibrées + utilitaires sur l'état capteurs.

Toutes les constantes numériques (K111_*, K191_*, RATE_*, VAPOR_*, etc.)
vivent ici. Les autres couches (physics, grafcet) les importent depuis
ce module pour éviter la duplication.
"""

from __future__ import annotations

import math
from typing import Dict

# ── Clés internes ────────────────────────────────────────────────────
# P_H2O représente la vapeur instantanée dans l'atmosphère de la cuve.
# P_H2O_LOAD représente l'humidité stockée dans la charge/emballages,
# relarguée progressivement pendant les phases de vide/rinçage.
# TT112 redevient la température dynamique de paroi / double enveloppe.
WATER_VAPOR_KEY = "P_H2O"
WATER_LOAD_KEY = "P_H2O_LOAD"

# ── Constantes physiques machine ──────────────────────────────────────
R_UNIV               = 8.314    # J/(mol·K)
M_ETO                = 0.04405  # kg/mol
V_CUVE               = 16.9     # m³
T_AMBIENT            = 20.0     # °C
TOTAL_ETO_MASS_KG    = 12.1
MIN_EFFECTIVE_PRESSURE  = 1e-3
MIN_SATURATION_PRESSURE = 0.5

# ── Double enveloppe / paroi dynamique (TT112) ────────────────────────
K112_TRACK    = 0.045
K112_PRESSURE = 0.0043

# ── Chambre (TT111) ──────────────────────────────────────────────────
K111_WALL     = 0.0055
K111_STEAM    = 0.0100
K111_GAS      = 0.0250
K111_PRESSURE = 0.0035
K111_LOSS     = 0.0045

# ── Sonde charge (TT191) ─────────────────────────────────────────────
K191_FROM_111 = 0.032
K191_FROM_112 = 0.012
K191_LOSS     = 0.0022

# ── Vapeur / humidité relative ────────────────────────────────────────
# STEAM_TO_VAPOR_GAIN est volontairement réduit : l'injection vapeur est
# maintenant pilotée vers HR300 par drive_vapor_to_rh(), et non plus
# uniquement par un gain pression -> vapeur.
STEAM_TO_VAPOR_GAIN     = 0.15
DEC_STEAM_TO_VAPOR_GAIN = 0.62
VAPOR_RELAX_DEC_STAB    = 0.12
VAPOR_RELAX_DEC_POSTVAC = 0.10
VAPOR_RELAX_STAB        = 0.10
VAPOR_RELAX_GAS_STAB    = 0.06
VAPOR_RELAX_EXPO        = 0.05
VAPOR_RELAX_RINSE       = 0.06
PREEXPO_RH_EQ           = 54.0
PREEXPO_VAC_RH_EQ       = 28.0
GAS_INJECTION_RH_EQ     = 35.0
GAS_STAB_RH_EQ          = 34.0
EXPO_RH_EQ              = 51.4
EXPO_DRY_RH_EQ          = 49.6
RINSE_BREAK_RH_EQ       = 26.0
RINSE_VAC_RH_EQ         = 24.0
RINSE_DAMPING           = 0.10
RINSE_BREAK_PUMP_FACTOR = 0.12
RINSE_VAC_PUMP_FACTOR   = 0.30
FINAL_VAC_PUMP_FACTOR   = 0.25
GAS_CUMULATIVE_FACTOR   = 0.10
RINSE_SMALL_NOISE       = 0.35

# Pilotage vapeur : permet d'atteindre HR300 sans casser l'allure de la courbe.
STEAM_TARGET_RELAX      = 0.42
STEAM_LOAD_STORAGE      = 0.85

# Séchage gaz pré-exposition : réduit pour garder ~35-40 %RH avant exposition.
GAS_DRYING_DRIFT        = 0.030

# Mémoire d'humidité de la charge : évite l'assèchement irréaliste à 0 %RH.
LOAD_DESORPTION_RATE    = 0.075  # charge -> atmosphère cuve
LOAD_ABSORPTION_RATE    = 0.018  # atmosphère cuve -> charge
LOAD_DEPLETION_FACTOR   = 0.18   # la charge se vide plus lentement que le gaz
RINSE_RH_FLOOR          = 22.0   # %RH plancher empirique pendant les rinçages

# ── Préconditionnement ────────────────────────────────────────────────
K111_PRECON_WALL      = 0.0035
K111_PRECON_LOSS      = 0.0020
K191_PRECON_FROM_111  = 0.018
K191_PRECON_FROM_112  = 0.006
K191_PRECON_LOSS      = 0.0018
PRECON_RH_EQ          = 38.0
PRECON_VAPOR_RELAX    = 0.008
PRECON_VAPOR_DRIFT    = 0.005

# ── Vitesses machine réelles (fallback quand recette = 999) ──────────
RATE_VACUUM_FROM_ATM = 69.0   # pompe à vide depuis ~1000 mbar
RATE_VACUUM_MID      = 55.0   # pompe à vide depuis ~400 mbar
RATE_VACUUM_LOW      = 24.0   # pompe à vide depuis ~100 mbar
RATE_N2_BREAK_SLOW   = 52.0   # injection azote casse-vide lente
RATE_N2_RINSE        = 45.0   # injection azote rinçage
RATE_AIR_BREAK       = 99.0   # injection air casse-vide
RATE_ETO_INJECTION   = 113.0  # injection EtO
RATE_N2_GAS          = 55.0   # injection azote phase gaz
RATE_STEAM           = 16.0   # vaporiseur vapeur

# ── Offsets intercapteurs (défauts de zéro PT111/PT112) ──────────────
DELTA_PT111 = -1.0
DELTA_PT112 =  1.0


# ── Utilitaires ───────────────────────────────────────────────────────

def compute_water_saturation_pressure_mbar(temp_c: float) -> float:
    """Pression de saturation de la vapeur d'eau (formule de Magnus, mbar)."""
    exponent = (7.5 * float(temp_c)) / (237.3 + float(temp_c))
    return 6.1078 * (10.0 ** exponent)


def pressure_avg(signals: Dict[str, float]) -> float:
    """Pression moyenne chambre (mbar)."""
    return 0.5 * (signals["PT111"] + signals["PT112"])


def saturation_pressure_of(signals: Dict[str, float]) -> float:
    """Pression de saturation à la température TT111 actuelle (mbar)."""
    return max(MIN_SATURATION_PRESSURE,
               compute_water_saturation_pressure_mbar(signals["TT111"]))


def effective_rate(rate_value: float, fallback_rate: float) -> float:
    """Vitesse effective : utilise le fallback si la recette indique 999 (max machine)."""
    if rate_value >= 900:
        return fallback_rate
    return max(rate_value, 1e-6)


def eto_p_from_mass(mass_kg: float, temperature_c: float) -> float:
    """Pression partielle EtO selon loi des gaz parfaits (mbar)."""
    mass_kg = max(0.0, mass_kg)
    tk = max(273.15, temperature_c + 273.15)
    return (mass_kg / M_ETO * R_UNIV * tk / V_CUVE) / 100.0


def make_initial_state(recipe: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Construit l'état capteurs initial à partir de la recette.

    TT111 démarre à T_INIT, TT112 redevient la température dynamique de paroi
    utilisée par le modèle thermique, et l'humidité initiale est paramétrable
    via RH_INIT. Une humidité de charge interne est initialisée pour reproduire
    le relargage d'humidité pendant les rinçages.
    """
    from app.model.constants import VARIABLES  # import local évite les cycles

    general = recipe.get("Général", {})
    t_init = float(general.get("T_INIT - Température initiale chambre", T_AMBIENT))
    rh_init = float(general.get("RH_INIT - Humidité initiale chambre", 30.0))
    rh_init = max(0.0, min(100.0, rh_init))

    psat_init = compute_water_saturation_pressure_mbar(t_init)
    p_h2o_init = 0.01 * rh_init * psat_init

    state: Dict[str, float] = {k: 0.0 for k in VARIABLES}
    state.update(
        PT111=1013.0,
        PT112=1015.0,
        TT111=t_init,
        TT112=45.5,
        TT191=t_init + 3.0,
        RHT121=rh_init,
        GT121=0.0,
    )

    state[WATER_VAPOR_KEY] = p_h2o_init
    state[WATER_LOAD_KEY] = max(p_h2o_init, 0.18 * psat_init)
    return state
