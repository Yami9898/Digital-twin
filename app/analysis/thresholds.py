"""
Chargement et application des seuils d'acceptation OK/WARN/FAIL.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class VariableThreshold:
    """Seuils pour une variable donnée."""
    unit: str
    ok_threshold: float       # |error| <= ok_threshold        → OK
    warn_threshold: float     # ok < |error| <= warn_threshold → WARN
    comment: str = ""


@dataclass
class DurationThresholds:
    """Seuils pour la comparaison de durée totale."""
    ok_ratio: float = 0.10
    warn_ratio: float = 0.25


@dataclass
class Thresholds:
    """Ensemble des seuils du projet."""
    by_variable: Dict[str, VariableThreshold] = field(default_factory=dict)
    duration: DurationThresholds = field(default_factory=DurationThresholds)

    def status_for(self, variable: str, error: float) -> str:
        """Retourne 'OK', 'WARN' ou 'FAIL' selon la magnitude de l'erreur."""
        return classify_error(error, self.by_variable.get(variable))


# ────────────────────────────────────────────────────────────────────
# Fonctions
# ────────────────────────────────────────────────────────────────────

def load_thresholds(path: str | Path) -> Thresholds:
    """Charge le JSON et retourne une instance de Thresholds."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de seuils introuvable : {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    by_var: Dict[str, VariableThreshold] = {}
    for var, spec in data.get("thresholds", {}).items():
        by_var[var] = VariableThreshold(
            unit=str(spec.get("unit", "")),
            ok_threshold=float(spec.get("ok_threshold", 0.0)),
            warn_threshold=float(spec.get("warn_threshold", 0.0)),
            comment=str(spec.get("comment", "")),
        )

    dur_spec = data.get("duration_thresholds", {})
    duration = DurationThresholds(
        ok_ratio=float(dur_spec.get("ok_ratio", 0.10)),
        warn_ratio=float(dur_spec.get("warn_ratio", 0.25)),
    )

    return Thresholds(by_variable=by_var, duration=duration)


def classify_error(error: float,
                   threshold: VariableThreshold | None) -> str:
    """Classifie une erreur en OK/WARN/FAIL selon les seuils.
    Si aucun seuil n'est défini, retourne '—'."""
    if threshold is None:
        return "—"
    abs_err = abs(error)
    if abs_err <= threshold.ok_threshold:
        return "OK"
    if abs_err <= threshold.warn_threshold:
        return "WARN"
    return "FAIL"
