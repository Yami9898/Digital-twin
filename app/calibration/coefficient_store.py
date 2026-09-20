"""
app/calibration/coefficient_store.py
Couche de coefficients actifs — ne touche JAMAIS signals.py.

Au démarrage, apply_snapshot() patche app.model.signals, app.model.physics
et app.model.grafcet avec les coefficients de la calibration active (JSON).
Si "default" est actif, aucun patch n'est appliqué : signals.py reste intact.

Pendant la calibration, override() est un context manager qui patche
temporairement les trois modules et les restaure à la sortie.

Pourquoi patcher les trois modules ?
  - app.model.physics et app.model.grafcet importent les constantes de signals
    via `from signals import X` au chargement : les noms sont liés localement.
  - Modifier signals.X ne change pas physics.X ni grafcet.X déjà liés.
  - Seul setattr(phys_module, 'X', valeur) met à jour le dictionnaire global
    du module, ce que les fonctions voient à chaque appel.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict

import app.model.signals as _sig
import app.model.physics as _phys
import app.model.grafcet as _graf

# ── Noms importés dans chaque module (déduits des listes d'import) ────────────

_PHYS_NAMES: frozenset = frozenset({
    "K112_TRACK", "K112_PRESSURE",
    "K191_PRECON_FROM_111", "K191_PRECON_FROM_112", "K191_PRECON_LOSS",
    "PREEXPO_RH_EQ", "PREEXPO_VAC_RH_EQ", "GAS_INJECTION_RH_EQ", "GAS_STAB_RH_EQ",
    "VAPOR_RELAX_GAS_STAB", "RINSE_DAMPING", "RINSE_SMALL_NOISE", "VAPOR_RELAX_RINSE",
    "LOAD_DESORPTION_RATE", "LOAD_ABSORPTION_RATE", "LOAD_DEPLETION_FACTOR", "RINSE_RH_FLOOR",
    "STEAM_TARGET_RELAX", "STEAM_LOAD_STORAGE", "GAS_DRYING_DRIFT",
})

_GRAF_NAMES: frozenset = frozenset({
    "PRECON_RH_EQ", "PRECON_VAPOR_RELAX", "PRECON_VAPOR_DRIFT",
    "STEAM_TO_VAPOR_GAIN", "DEC_STEAM_TO_VAPOR_GAIN",
    "VAPOR_RELAX_DEC_STAB", "VAPOR_RELAX_DEC_POSTVAC", "VAPOR_RELAX_STAB",
    "VAPOR_RELAX_GAS_STAB", "VAPOR_RELAX_EXPO", "VAPOR_RELAX_RINSE",
    "EXPO_RH_EQ", "EXPO_DRY_RH_EQ",
    "RINSE_BREAK_RH_EQ", "RINSE_VAC_RH_EQ",
    "RINSE_BREAK_PUMP_FACTOR", "RINSE_VAC_PUMP_FACTOR", "FINAL_VAC_PUMP_FACTOR",
    "GAS_CUMULATIVE_FACTOR",
    "RATE_VACUUM_FROM_ATM", "RATE_VACUUM_MID", "RATE_VACUUM_LOW",
    "RATE_N2_BREAK_SLOW", "RATE_N2_RINSE", "RATE_AIR_BREAK",
    "RATE_ETO_INJECTION", "RATE_N2_GAS", "RATE_STEAM",
})

# ── Paramètres calibrables avec bornes physiques (min, max) ──────────────────
# Uniquement des scalaires de signals.py impactant TT111/TT112/TT191/RHT121.

CALIBRATABLE_BOUNDS: Dict[str, tuple] = {
    # Enveloppe thermique (TT112)
    "K112_TRACK":              (0.001, 0.300),
    "K112_PRESSURE":           (0.000, 0.020),
    # Humidité relative (RHT121)
    "VAPOR_RELAX_EXPO":        (0.005, 0.300),
    "VAPOR_RELAX_RINSE":       (0.005, 0.300),
    "VAPOR_RELAX_STAB":        (0.005, 0.300),
    "VAPOR_RELAX_GAS_STAB":    (0.005, 0.300),
    "EXPO_RH_EQ":              (30.0,  75.0),
    "EXPO_DRY_RH_EQ":          (20.0,  65.0),
    "RINSE_BREAK_RH_EQ":       (10.0,  45.0),
    "RINSE_VAC_RH_EQ":          (5.0,  35.0),
    "PREEXPO_RH_EQ":           (30.0,  70.0),
    "GAS_INJECTION_RH_EQ":     (10.0,  55.0),
    "GAS_STAB_RH_EQ":          (10.0,  55.0),
    "LOAD_DESORPTION_RATE":    (0.010, 0.400),
    "LOAD_ABSORPTION_RATE":    (0.001, 0.080),
    "RINSE_RH_FLOOR":          (5.0,   35.0),
    "STEAM_TARGET_RELAX":      (0.050, 1.000),
    "STEAM_TO_VAPOR_GAIN":     (0.050, 1.500),
    # Vitesses machine (influencent les durées de phase et donc les profils T/RH)
    "RATE_VACUUM_FROM_ATM":    (20.0, 200.0),
    "RATE_VACUUM_MID":         (10.0, 150.0),
    "RATE_STEAM":              (3.0,   40.0),
    "RATE_N2_BREAK_SLOW":      (10.0, 150.0),
    "RATE_N2_RINSE":           (10.0, 120.0),
}

# ── Valeurs usine capturées UNE SEULE FOIS à l'import (avant tout patch) ─────
# Immuables : signals.py ne change jamais sur disque.

FACTORY_DEFAULTS: Dict[str, float] = {
    name: float(getattr(_sig, name, 0.0))
    for name in CALIBRATABLE_BOUNDS
}

_lock = threading.Lock()


# ── API publique ──────────────────────────────────────────────────────────────

def apply_snapshot(coefficients: Dict[str, float]) -> None:
    """Applique un jeu de coefficients JSON aux trois modules du modèle (idempotent)."""
    with _lock:
        for name, value in coefficients.items():
            _set(name, float(value))


def restore_defaults() -> None:
    """Restaure les valeurs usine de signals.py dans les trois modules."""
    apply_snapshot(FACTORY_DEFAULTS)


def current_values() -> Dict[str, float]:
    """Retourne les valeurs calibrables actuellement actives (lues depuis signals)."""
    return {name: float(getattr(_sig, name, FACTORY_DEFAULTS.get(name, 0.0)))
            for name in CALIBRATABLE_BOUNDS}


@contextmanager
def override(coefficients: Dict[str, float]):
    """Context manager : patch temporaire pour la fonction résidu de scipy.

    Thread-safe via _lock. Restaure exactement les valeurs précédentes à la sortie,
    même en cas d'exception.
    """
    # Sauvegarder l'état courant de chaque nom concerné dans les 3 modules
    saved: Dict[str, Dict] = {"sig": {}, "phys": {}, "graf": {}}
    for name in coefficients:
        if hasattr(_sig, name):
            saved["sig"][name] = getattr(_sig, name)
        if name in _PHYS_NAMES and hasattr(_phys, name):
            saved["phys"][name] = getattr(_phys, name)
        if name in _GRAF_NAMES and hasattr(_graf, name):
            saved["graf"][name] = getattr(_graf, name)

    with _lock:
        for name, value in coefficients.items():
            _set(name, float(value))
    try:
        yield
    finally:
        with _lock:
            for name, value in saved["sig"].items():
                setattr(_sig, name, value)
            for name, value in saved["phys"].items():
                setattr(_phys, name, value)
            for name, value in saved["graf"].items():
                setattr(_graf, name, value)


# ── Interne ───────────────────────────────────────────────────────────────────

def _set(name: str, value: float) -> None:
    """Écrit name=value dans signals + physics + grafcet selon appartenance."""
    if hasattr(_sig, name):
        setattr(_sig, name, value)
    if name in _PHYS_NAMES and hasattr(_phys, name):
        setattr(_phys, name, value)
    if name in _GRAF_NAMES and hasattr(_graf, name):
        setattr(_graf, name, value)
