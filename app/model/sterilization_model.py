"""
Moteur de simulation empirique du stérilisateur EtO — façade publique.

Ce module expose les interfaces contractuelles utilisées par le reste du
projet (plot_tab, real_cycle_tab, pdf_report) :

    • Segment          — structure de données d'un pas de simulation
    • SterilizationModel — façade qui délègue à GrafcetCycle
    • PHASE_FIELD_RULES  — règles d'activation par phase (RecipeTab)
    • phase_is_active()  — utilisé par RecipeTab et GrafcetCycle
    • lerp()             — utilisé par PlotTab pour l'interpolation
    • effective_rate()   — utilitaire de vitesse recette
    • safe_duration_from_pressure() — durée d'une transition de pression

La logique physique est dans :
    app/model/signals.py   — constantes + make_initial_state
    app/model/physics.py   — équations différentielles (fonctions pures)
    app/model/actuators.py — ActuatorState + mapping GRAFCET
    app/model/grafcet.py   — GrafcetCycle (machine à états)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.model.constants import VARIABLES, WATER_VAPOR_KEY


# ────────────────────────────────────────────────────────────────────
# Structures de données
# ────────────────────────────────────────────────────────────────────

@dataclass
class Segment:
    """Segment temporel produit par la simulation (~ une sous-phase)."""
    name: str
    duration: float
    start_state: Dict[str, float]
    end_state: Dict[str, float]


# ────────────────────────────────────────────────────────────────────
# Helpers numériques
# ────────────────────────────────────────────────────────────────────

def lerp(a: float, b: float, u: float) -> float:
    """Interpolation linéaire entre a et b (u ∈ [0, 1])."""
    return a + (b - a) * u


def make_state(**kwargs: float) -> Dict[str, float]:
    """Construit un état initial avec toutes les variables à 0
    puis applique les overrides passés en kwargs."""
    state = {k: 0.0 for k in VARIABLES}
    state.update(kwargs)
    return state


def effective_rate(rate_value: float, fallback_rate: float) -> float:
    """Convertit une vitesse recette (mbar/min) en vitesse réelle.
    Si la recette indique 999 (« automatique »), on utilise le
    fallback mesuré sur cycles réels."""
    if rate_value >= 900:
        return fallback_rate
    return max(rate_value, 1e-6)


def safe_duration_from_pressure(
    delta_p: float,
    rate_value: float,
    fallback_rate: float,
    min_duration: float = 0.1,
) -> float:
    """Durée d'une transition de pression bornée par un plancher."""
    rate_eff = effective_rate(rate_value, fallback_rate)
    return max(min_duration, abs(delta_p) / rate_eff)


def compute_water_saturation_pressure_mbar(temp_c: float) -> float:
    """Pression de saturation de l'eau (formule de Magnus, mbar)."""
    exponent = (7.5 * float(temp_c)) / (237.3 + float(temp_c))
    return 6.1078 * (10.0 ** exponent)


# ────────────────────────────────────────────────────────────────────
# Champs surveillés par phase (utilisé par phase_is_active)
# ────────────────────────────────────────────────────────────────────

PHASE_FIELD_RULES: Dict[str, List[str]] = {
    "Préconditionnement": ["T130 - Durée préconditionnement"],
    "Vide initial": ["SP140 - Consigne pression vide", "R140 - Vitesse de vide"],
    "Test de fuite bas": ["T160 - Durée"],
    "Test de fuite haut": [
        "SP170 - Pression casse vide azote", "R170 - Vitesse injection azote",
        "T190 - Durée test", "SP200 - Consigne vide", "R200 - Vitesse de vide",
    ],
    "Dilution azote": [
        "SP220 - Pression dilution azote", "R220 - Vitesse injection dilution azote",
        "SP230 - Consigne pression vide", "R230 - Vitesse du vide",
        "NB220 - Nombre dilution azote",
    ],
    "Conditionnement dynamique": [
        "T250 - Durée conditionnement dynamique", "P250 - Nombre de pulses",
        "HR260 - Humidité conditionnement",
    ],
    "Injection vapeur": [
        "DP300 - Pression injection vapeur", "HR300 - Consigne humidité",
        "R300 - Vitesse injection vapeur",
    ],
    "Stabilisation humidité": [
        "T310 - Temps stabilisation", "SP320 - Consigne de vide",
        "R320 - Vitesse de vide",
    ],
    "Injection gaz 1": [
        "DP330 - Injection gaz 1", "R330 - Vitesse injection gaz 1",
        "T350 - Stabilisation gaz 1",
    ],
    "Injection gaz 2": [
        "DP390 - Injection gaz 2", "R390 - Vitesse injection gaz 2",
        "T410 - Stabilisation gaz 2",
    ],
    "Injection gaz 3": [
        "DP450 - Injection gaz 3", "R450 - Vitesse injection gaz 3",
        "T470 - Stabilisation gaz 3",
    ],
    "Injection gaz 4": [
        "DP510 - Injection gaz 4", "R510 - Vitesse injection gaz 4",
        "T530 - Stabilisation gaz 4",
    ],
    "Flush azote": [
        "DP570 - Injection azote", "R570 - Vitesse injection azote",
    ],
    "Exposition EtO": [
        "T580 - Temps exposition", "EC580 - Concentration cible",
    ],
    "Vide avant rinçage": [
        "SP590 - Consigne vide", "R590 - Vitesse de vide",
    ],
    "Rinçage azote": [
        "SP620 - Pression casse vide azote", "R620 - Vitesse casse vide azote",
        "T630 - Stabilisation casse vide", "SP640 - Consigne vide",
        "R640 - Vitesse de vide", "T660 - Stabilisation vide",
        "NB620 - Nombre de rinçages azote",
    ],
    "Rinçage air": [
        "SP680 - Pression casse vide air", "R680 - Vitesse casse vide air",
        "T690 - Stabilisation casse vide", "SP700 - Consigne vide",
        "R700 - Vitesse de vide", "T720 - Stabilisation vide",
        "NB680 - Nombre de rinçages air",
    ],
    "Rinçage additionnel": [
        "SP740 - Pression casse vide air", "R740 - Vitesse casse vide air",
        "T750 - Stabilisation casse vide", "SP760 - Consigne vide",
        "R760 - Vitesse de vide", "T780 - Stabilisation vide",
        "NB740 - Nombre de rinçages additionnels",
    ],
    "Casse vide air finale": [
        "SP790 - Consigne finale", "R790 - Vitesse finale",
    ],
}


def phase_is_active(phase_name: str, phase_data: Dict[str, float]) -> bool:
    """Retourne True si au moins un champ surveillé de la phase est non-nul."""
    monitored_fields = PHASE_FIELD_RULES.get(phase_name, list(phase_data.keys()))
    return any(abs(float(phase_data.get(field, 0.0))) > 1e-9 for field in monitored_fields)


# ────────────────────────────────────────────────────────────────────
# Modèle de simulation
# ────────────────────────────────────────────────────────────────────

class SterilizationModel:
    """
    Modèle empirique du stérilisateur EtO.

    Coefficients calibrés sur 3 cycles réels.
    Voir constantes K111_*, K112_*, K191_* pour le détail thermique,
    et constantes RATE_* pour les vitesses fallback machine.
    """

    # Constantes physiques
    R_UNIV = 8.314
    M_ETO = 0.04405
    V_CUVE = 16.9
    DT_INTERNAL = 0.5
    VACUUM_RATE_REFERENCE = 79.0
    TOTAL_ETO_MASS_KG = 12.1
    MIN_EFFECTIVE_PRESSURE = 1e-3
    MIN_SATURATION_PRESSURE = 0.5
    T_AMBIENT = 20.0

    # Jacket (TT112) — calibré sur cycles réels
    K112_TRACK = 0.045
    K112_PRESSURE = 0.0043

    # Chambre (TT111) — globaux
    K111_WALL = 0.0055
    K111_STEAM = 0.0100
    K111_GAS = 0.0250
    K111_PRESSURE = 0.0035
    K111_LOSS = 0.0045

    # Sonde charge (TT191)
    K191_FROM_111 = 0.032
    K191_FROM_112 = 0.012
    K191_LOSS = 0.0022

    # Vapeur / humidité relative
    STEAM_TO_VAPOR_GAIN = 0.72
    DEC_STEAM_TO_VAPOR_GAIN = 0.62
    VAPOR_RELAX_DEC_STAB = 0.12
    VAPOR_RELAX_DEC_POSTVAC = 0.10
    VAPOR_RELAX_STAB = 0.10
    VAPOR_RELAX_GAS_STAB = 0.06
    VAPOR_RELAX_EXPO = 0.05
    VAPOR_RELAX_RINSE = 0.06
    PREEXPO_RH_EQ = 54.0
    PREEXPO_VAC_RH_EQ = 28.0
    GAS_INJECTION_RH_EQ = 25.0
    GAS_STAB_RH_EQ = 24.5
    EXPO_RH_EQ = 51.4
    EXPO_DRY_RH_EQ = 27.0
    RINSE_BREAK_RH_EQ = 28.0
    RINSE_VAC_RH_EQ = 18.0
    RINSE_DAMPING = 0.10
    RINSE_BREAK_PUMP_FACTOR = 0.12
    RINSE_VAC_PUMP_FACTOR = 0.30
    FINAL_VAC_PUMP_FACTOR = 0.25
    GAS_CUMULATIVE_FACTOR = 0.10
    RINSE_SMALL_NOISE = 0.35

    # Préconditionnement
    K111_PRECON_WALL = 0.0035
    K111_PRECON_LOSS = 0.0020
    K191_PRECON_FROM_111 = 0.018
    K191_PRECON_FROM_112 = 0.006
    K191_PRECON_LOSS = 0.0018
    PRECON_RH_EQ = 38.0
    PRECON_VAPOR_RELAX = 0.008
    PRECON_VAPOR_DRIFT = 0.005

    # Vitesses machine réelles (fallback quand recette = 999)
    RATE_VACUUM_FROM_ATM = 69.0
    RATE_VACUUM_MID = 55.0
    RATE_VACUUM_LOW = 24.0
    RATE_N2_BREAK_SLOW = 52.0
    RATE_N2_RINSE = 45.0
    RATE_AIR_BREAK = 99.0
    RATE_ETO_INJECTION = 113.0
    RATE_N2_GAS = 55.0
    RATE_STEAM = 16.0

    def __init__(self, recipe: Dict[str, Dict[str, float]]) -> None:
        self.recipe = recipe

    def simulate(self) -> Tuple[List[Segment], float]:
        """Délègue la simulation à GrafcetCycle et retourne (segments, durée_totale)."""
        from app.model.grafcet import GrafcetCycle  # import tardif — évite le cycle
        return GrafcetCycle(self.recipe).simulate()

    # ── Helpers thermodynamiques (conservés pour rétrocompatibilité) ──
    # ── Helpers thermodynamiques ────────────────────────────────────

    def _eto_p_from_mass(self, mass_kg: float, temperature_c: float) -> float:
        """Pression partielle EtO selon loi des gaz parfaits (mbar)."""
        mass_kg = max(0.0, mass_kg)
        tk = max(273.15, temperature_c + 273.15)
        return (mass_kg / self.M_ETO * self.R_UNIV * tk / self.V_CUVE) / 100.0

    def _eto_pressure_from_mass(self, mass_kg: float, temperature_c: float) -> float:
        """Alias rétrocompatible."""
        return self._eto_p_from_mass(mass_kg, temperature_c)

    def _eto_mass_from_total_recipe(self, gas_specs) -> float:
        s = 0.0
        for pname, _, _, _, mf in gas_specs:
            if phase_is_active(pname, self.recipe[pname]):
                s += mf
        return s

    def _finalize_state(self, state: Dict[str, float]) -> None:
        """Borne et nettoie l'état après chaque pas de simulation."""
        for key in [*VARIABLES, WATER_VAPOR_KEY]:
            v = state.get(key, 0.0)
            if not math.isfinite(v):
                state[key] = 0.0
        state[WATER_VAPOR_KEY] = max(0.0, state.get(WATER_VAPOR_KEY, 0.0))
        state["GT121"] = max(0.0, min(self.TOTAL_ETO_MASS_KG, state["GT121"]))
        state["TT112"] = max(0.0, min(80.0, state["TT112"]))
        state["TT111"] = max(0.0, min(80.0, state["TT111"]))
        state["TT191"] = max(0.0, min(80.0, state["TT191"]))
        state["PT111"] = max(0.0, state["PT111"])
        state["PT112"] = max(0.0, state["PT112"])
        psat = max(self.MIN_SATURATION_PRESSURE,
                   compute_water_saturation_pressure_mbar(state["TT111"]))
        state[WATER_VAPOR_KEY] = min(state[WATER_VAPOR_KEY], 1.02 * psat)
        state["RHT121"] = 100.0 * state[WATER_VAPOR_KEY] / psat
