"""
Stratégie d'interpolation temporelle pure.

Méthode :
  1. Recalage unique sur la phase d'ancrage (ex: début "Vide initial")
  2. Pour chaque point réel, on calcule t_sim = t_real - offset
  3. On interpole le simulé à t_sim et on compare

Avantages : simple, 100% objective, méthode classique de validation
de modèle.

Inconvénient : si le simulé dérive temporellement (ex: il fait le vide
plus vite que le réel), les écarts de valeur seront grossis.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

from app.analysis.phase_mapping import PhaseMapping
from app.analysis.sim_interpolator import SimInterpolator
from app.analysis.strategies.base import ComparisonStrategy, StrategyName
from app.analysis.thresholds import Thresholds
from app.analysis.time_aligner import align_origins
from app.model.constants import COMPARED_VARS
from app.model.sterilization_model import Segment

if TYPE_CHECKING:
    from app.analysis.comparator import ComparisonResult


class InterpolationStrategy(ComparisonStrategy):
    """Stratégie d'interpolation temporelle après recalage unique."""

    name = StrategyName.INTERPOLATION
    display_name = "Interpolation temporelle"
    description = (
        "Recale les deux cycles sur leur phase d'ancrage, puis compare "
        "chaque point réel à la valeur simulée interpolée au même instant. "
        "Méthode simple et objective."
    )

    def compare(
        self,
        sim_segments: Sequence[Segment],
        real_steps: Sequence,
        mapping: PhaseMapping,
        thresholds: Thresholds,
        *,
        variables: Optional[List[str]] = None,
        apply_filter: bool = True,
    ) -> "ComparisonResult":
        from app.analysis.comparator import (
            ComparisonResult, ComparisonPoint, _extract_real_values,
            _compute_aggregates, _safe_ratio, _classify_duration,
        )

        vars_to_compare = variables or list(COMPARED_VARS)

        # 1. Alignement unique
        alignment = align_origins(sim_segments, real_steps, mapping)

        # 2. Interpolateur
        interp = SimInterpolator(sim_segments)

        result = ComparisonResult(
            strategy=self.name,
            alignment=alignment,
            sim_duration_min=interp.total_duration,
        )
        result.real_duration_min = real_steps[-1].t_min if real_steps else 0.0

        # 3. Boucle sur points réels
        for step in real_steps:
            category = mapping.category_of_real(step.step_name)

            if apply_filter and category in mapping.filter_categories:
                result.n_filtered += 1
                continue

            t_sim = alignment.real_to_sim_time(step.t_min)
            in_range = (0.0 <= t_sim <= interp.total_duration)
            if not in_range:
                result.n_out_of_sim_range += 1

            sim_vals = (interp.at(t_sim) if in_range
                        else {v: float('nan') for v in vars_to_compare})
            sim_phase = interp.phase_at(t_sim) if in_range else ""

            real_vals = _extract_real_values(step, vars_to_compare)

            errors: Dict[str, float] = {}
            statuses: Dict[str, str] = {}
            for var in vars_to_compare:
                sv = sim_vals.get(var, float('nan'))
                rv = real_vals.get(var, 0.0)
                if math.isnan(sv) or not in_range:
                    errors[var] = float('nan')
                    statuses[var] = "—"
                else:
                    err = sv - rv
                    errors[var] = err
                    statuses[var] = thresholds.status_for(var, err)

            result.points.append(ComparisonPoint(
                t_real=step.t_min,
                t_sim_aligned=t_sim,
                real_phase=step.step_name,
                sim_phase=sim_phase,
                category=category,
                in_sim_range=in_range,
                real_values=real_vals,
                sim_values=sim_vals,
                errors=errors,
                statuses=statuses,
                sync_status="ALIGNED",  # toujours aligné dans cette stratégie
            ))

        # 4. Agrégats + durée
        result.aggregates = _compute_aggregates(
            result.points, vars_to_compare, thresholds)
        result.duration_error_ratio = _safe_ratio(
            result.sim_duration_min - result.real_duration_min,
            result.real_duration_min,
        )
        result.duration_status = _classify_duration(
            result.duration_error_ratio, thresholds)

        return result
