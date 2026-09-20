"""
app/calibration/least_squares_calibrator.py
Calibration par moindres carrés non linéaires (scipy TRF).

Méthode :
  Minimise Σ_cycles Σ_points Σ_var  w_var · [sim_var(θ) − real_var]²
  sur les cycles marqués « calibration » (les cycles « validation » ne
  participent pas à l'optimisation mais sont évalués après).

  Variables calibrées : TT111, TT112, TT191, RHT121 (pas la pression,
  pilotée par consigne recette).

  Pondération normalisée par l'échelle de chaque variable :
    w_T   = 1 / 40   (températures en °C, plage typique ~40 °C)
    w_RH  = 1 / 100  (humidité en %, plage 0–100 %)

  Point de départ : valeurs usine de FACTORY_DEFAULTS (physiques).
  Bornes : CALIBRATABLE_BOUNDS (bornes physiques par coefficient).
  Méthode scipy : 'trf' (Trust Region Reflective), compatible avec les bornes.

Usage :
  calibrator = LeastSquaresCalibrator(pairs, progress_callback=cb)
  result = calibrator.run()
"""

from __future__ import annotations

import math
import sys
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares

from app.calibration.coefficient_store import (
    CALIBRATABLE_BOUNDS,
    FACTORY_DEFAULTS,
    override,
)
from app.model.sterilization_model import SterilizationModel

# Variables comparées et leurs poids de normalisation
_VARIABLES: List[str] = ["TT111", "TT112", "TT191", "RHT121"]
_WEIGHTS:   Dict[str, float] = {
    "TT111":  1.0 / 40.0,
    "TT112":  1.0 / 40.0,
    "TT191":  1.0 / 40.0,
    "RHT121": 1.0 / 100.0,
}
# Mapping attribut CycleStep → clé variable
_STEP_ATTR: Dict[str, str] = {
    "TT111":  "tt111",
    "TT112":  "tt112",
    "TT191":  "tt191",
    "RHT121": "rht121",
}


@dataclass
class VarMetrics:
    rmse: float = 0.0
    mae:  float = 0.0
    bias: float = 0.0
    n:    int   = 0


@dataclass
class CalibrationResult:
    success:        bool
    coefficients:   Dict[str, float]             = field(default_factory=dict)
    metrics_before: Dict[str, VarMetrics]        = field(default_factory=dict)
    metrics_after:  Dict[str, VarMetrics]        = field(default_factory=dict)
    metrics_valid:  Dict[str, VarMetrics]        = field(default_factory=dict)
    message:        str                          = ""
    n_evaluations:  int                          = 0
    cost_before:    float                        = 0.0
    cost_after:     float                        = 0.0


class LeastSquaresCalibrator:
    """
    Calibrateur par moindres carrés non linéaires.

    pairs : liste de (CycleData, recipe_dict, role)
            role = 'calibration' ou 'validation'
    param_names : sous-ensemble de CALIBRATABLE_BOUNDS à optimiser.
                  Par défaut : tous les paramètres calibrables.
    progress_callback : fonction(message: str, pct: int) appelée pendant l'optimisation.
    """

    def __init__(
        self,
        pairs: List[Tuple],
        param_names: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.pairs   = pairs
        self.param_names = (
            param_names if param_names is not None else list(CALIBRATABLE_BOUNDS.keys())
        )
        self._cb    = progress_callback or (lambda msg, pct: None)
        self._nfev  = 0

    # ── Interface publique ────────────────────────────────────────────

    def run(self) -> CalibrationResult:
        calib_pairs = [(cd, rec) for cd, rec, role in self.pairs if role == "calibration"]
        valid_pairs = [(cd, rec) for cd, rec, role in self.pairs if role == "validation"]

        if not calib_pairs:
            return CalibrationResult(
                success=False,
                message="Aucun cycle de calibration sélectionné.",
            )

        # ── Point de départ et bornes ─────────────────────────────────
        x0    = np.array([FACTORY_DEFAULTS.get(n, 0.0) for n in self.param_names])
        lower = np.array([CALIBRATABLE_BOUNDS[n][0]    for n in self.param_names])
        upper = np.array([CALIBRATABLE_BOUNDS[n][1]    for n in self.param_names])

        # ── Métriques avant calibration ───────────────────────────────
        self._cb("Calcul des métriques initiales…", 3)
        metrics_before = self._compute_metrics(calib_pairs, None)
        cost_before    = self._total_cost(metrics_before)

        # ── Optimisation ──────────────────────────────────────────────
        self._cb("Optimisation en cours…", 8)
        self._nfev = 0

        try:
            result = least_squares(
                self._residuals,
                x0,
                args=(calib_pairs,),
                bounds=(lower, upper),
                method="trf",
                max_nfev=600,
                ftol=1e-6,
                xtol=1e-6,
                gtol=1e-6,
                verbose=0,
            )
        except Exception as exc:
            return CalibrationResult(
                success=False,
                message=f"Erreur scipy : {exc}",
                coefficients=dict(zip(self.param_names, x0.tolist())),
                metrics_before=metrics_before,
            )

        optimized: Dict[str, float] = {
            name: float(result.x[i]) for i, name in enumerate(self.param_names)
        }

        # ── Métriques après calibration ───────────────────────────────
        self._cb("Calcul des métriques finales…", 90)
        metrics_after = self._compute_metrics(calib_pairs, optimized)
        metrics_valid = self._compute_metrics(valid_pairs, optimized) if valid_pairs else {}
        cost_after    = self._total_cost(metrics_after)

        self._cb("Terminé.", 100)

        # scipy considère 'success' si xtol/ftol/gtol atteint
        success = result.success or (cost_after < cost_before)

        return CalibrationResult(
            success=success,
            coefficients=optimized,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            metrics_valid=metrics_valid,
            message=result.message,
            n_evaluations=result.nfev,
            cost_before=cost_before,
            cost_after=cost_after,
        )

    # ── Résidu ───────────────────────────────────────────────────────

    def _residuals(
        self, x: np.ndarray, pairs: List[Tuple]
    ) -> np.ndarray:
        self._nfev += 1
        if self._nfev % 15 == 0:
            pct = min(88, 8 + int(self._nfev * 0.13))
            self._cb(f"Itération {self._nfev}…", pct)

        coefficients = {name: float(x[i]) for i, name in enumerate(self.param_names)}
        residuals: List[float] = []

        with override(coefficients):
            for cycle_data, recipe in pairs:
                n_steps = max(1, len(cycle_data.steps))
                try:
                    segments, _ = SterilizationModel(recipe).simulate()
                except Exception as exc:
                    # Paramètres hors domaine physique ou recette invalide
                    print(f"[calibration] simulate() failed: {exc}", file=sys.stderr)
                    residuals.extend([10.0] * n_steps * len(_VARIABLES))
                    continue

                for step in cycle_data.steps:
                    t = float(step.t_min)
                    for var in _VARIABLES:
                        real_val = float(getattr(step, _STEP_ATTR[var], 0.0))
                        sim_val  = _sim_at(segments, t, var)
                        residuals.append(_WEIGHTS[var] * (sim_val - real_val))

        return np.array(residuals) if residuals else np.zeros(1)

    # ── Métriques ─────────────────────────────────────────────────────

    def _compute_metrics(
        self,
        pairs:        List[Tuple],
        coefficients: Optional[Dict[str, float]],
    ) -> Dict[str, VarMetrics]:
        """RMSE / MAE / biais par variable sur l'ensemble des paires."""
        if not pairs:
            return {}

        errors: Dict[str, List[float]] = {v: [] for v in _VARIABLES}
        ctx = override(coefficients) if coefficients else nullcontext()

        with ctx:
            for cycle_data, recipe in pairs:
                try:
                    segments, _ = SterilizationModel(recipe).simulate()
                except Exception as exc:
                    print(f"[calibration] _compute_metrics simulate() failed: {exc}", file=sys.stderr)
                    continue
                for step in cycle_data.steps:
                    t = float(step.t_min)
                    for var in _VARIABLES:
                        real_val = float(getattr(step, _STEP_ATTR[var], 0.0))
                        sim_val  = _sim_at(segments, t, var)
                        errors[var].append(sim_val - real_val)

        result: Dict[str, VarMetrics] = {}
        for var in _VARIABLES:
            err = errors[var]
            if err:
                result[var] = VarMetrics(
                    rmse = math.sqrt(sum(e * e for e in err) / len(err)),
                    mae  = sum(abs(e) for e in err) / len(err),
                    bias = sum(err) / len(err),
                    n    = len(err),
                )
            else:
                result[var] = VarMetrics()
        return result

    @staticmethod
    def _total_cost(metrics: Dict[str, VarMetrics]) -> float:
        return sum(m.rmse for m in metrics.values() if m.n > 0)


# ── Interpolation temporelle dans les segments ────────────────────────────────

def _sim_at(segments, t_min: float, var: str) -> float:
    """Valeur interpolée de `var` au temps t_min (min) dans la liste de segments."""
    if not segments:
        return 0.0
    accumulated = 0.0
    for seg in segments:
        t_start = accumulated
        t_end   = accumulated + seg.duration
        if t_start <= t_min <= t_end:
            u = (t_min - t_start) / max(seg.duration, 1e-9)
            u = max(0.0, min(1.0, u))
            a = seg.start_state.get(var, 0.0)
            b = seg.end_state.get(var, 0.0)
            return a + u * (b - a)
        accumulated = t_end
    # t_min dépasse la durée totale : valeur finale
    return segments[-1].end_state.get(var, 0.0)
