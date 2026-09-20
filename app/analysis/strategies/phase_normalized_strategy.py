"""
Stratégie de comparaison normalisée par phase.

Cette stratégie compare chaque phase sur un axe relatif 0-100 %, ce qui évite
qu'un léger déphasage global fausse les métriques.

Cas particulier PT111/PT112 : la pression contient des fronts très rapides.
Deux courbes peuvent être visuellement correctes, mais un front déplacé de
quelques minutes peut créer un RMSE très élevé. Pour les pressions seulement,
l'erreur est donc calculée avec la valeur simulée la plus proche du réel dans
une petite fenêtre locale autour du point normalisé. L'affichage des courbes ne
change pas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
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


@dataclass
class _RealPhaseBlock:
    category: str
    phase_name: str
    steps: Sequence
    t_start: float
    t_end: float
    occurrence: int

    @property
    def duration(self) -> float:
        return max(0.0, self.t_end - self.t_start)


@dataclass
class _SimPhaseBlock:
    category: str
    phase_name: str
    t_start: float
    t_end: float
    occurrence: int

    @property
    def duration(self) -> float:
        return max(0.0, self.t_end - self.t_start)


class PhaseNormalizedStrategy(ComparisonStrategy):
    """Comparaison des valeurs sur un temps relatif propre à chaque phase."""

    name = StrategyName.PHASE_NORMALIZED
    display_name = "Comparaison normalisée par phase"
    description = (
        "Compare chaque phase sur un temps relatif 0-100 %, afin d'éviter "
        "qu'un léger déphasage temporel crée de fausses erreurs de valeur."
    )

    MIN_PHASE_DURATION_MIN = 0.5
    MIN_REAL_POINTS_PER_PHASE = 2
    N_SAMPLES_PER_PHASE = 40

    PRESSURE_VARS = {"PT111", "PT112"}
    PRESSURE_WINDOW_REL = 0.06
    PRESSURE_WINDOW_MIN = 1.0
    PRESSURE_WINDOW_MAX = 6.0
    PRESSURE_WINDOW_SAMPLES = 13

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
            ComparisonPoint,
            ComparisonResult,
            _compute_aggregates,
            _safe_ratio,
            _classify_duration,
        )

        vars_to_compare = variables or list(COMPARED_VARS)
        interp = SimInterpolator(sim_segments)
        alignment = align_origins(sim_segments, real_steps, mapping)

        result = ComparisonResult(
            strategy=self.name,
            alignment=alignment,
            sim_duration_min=interp.total_duration,
        )
        result.real_duration_min = real_steps[-1].t_min if real_steps else 0.0

        real_blocks = _build_real_phase_blocks(real_steps, mapping, apply_filter)
        sim_blocks = _build_sim_phase_blocks(sim_segments, mapping)
        sim_by_key = {(b.category, b.occurrence): b for b in sim_blocks}

        for rb in real_blocks:
            if rb.duration < self.MIN_PHASE_DURATION_MIN:
                result.n_filtered += len(rb.steps)
                continue
            if len(rb.steps) < self.MIN_REAL_POINTS_PER_PHASE:
                result.n_filtered += len(rb.steps)
                continue

            sb = sim_by_key.get((rb.category, rb.occurrence))
            if sb is None or sb.duration < self.MIN_PHASE_DURATION_MIN:
                result.n_out_of_sim_range += len(rb.steps)
                continue

            for k in range(self.N_SAMPLES_PER_PHASE):
                tau = k / (self.N_SAMPLES_PER_PHASE - 1)
                t_real = rb.t_start + tau * rb.duration
                t_sim = sb.t_start + tau * sb.duration

                real_vals = _interpolate_real_values(rb.steps, t_real, vars_to_compare)
                sim_vals = interp.at(t_sim)

                errors: Dict[str, float] = {}
                statuses: Dict[str, str] = {}
                for var in vars_to_compare:
                    sv = sim_vals.get(var, float("nan"))
                    rv = real_vals.get(var, float("nan"))
                    if math.isnan(sv) or math.isnan(rv):
                        errors[var] = float("nan")
                        statuses[var] = "—"
                    else:
                        sv_metric = sv
                        if var in self.PRESSURE_VARS:
                            sv_metric = _closest_sim_value_in_phase_window(
                                interp=interp,
                                var=var,
                                target_value=rv,
                                center_t=t_sim,
                                phase_start=sb.t_start,
                                phase_end=sb.t_end,
                                rel_window=self.PRESSURE_WINDOW_REL,
                                min_window=self.PRESSURE_WINDOW_MIN,
                                max_window=self.PRESSURE_WINDOW_MAX,
                                n_samples=self.PRESSURE_WINDOW_SAMPLES,
                            )
                        err = sv_metric - rv
                        errors[var] = err
                        statuses[var] = thresholds.status_for(var, err)

                result.points.append(ComparisonPoint(
                    t_real=t_real,
                    t_sim_aligned=t_sim,
                    real_phase=rb.phase_name,
                    sim_phase=sb.phase_name,
                    category=rb.category,
                    in_sim_range=True,
                    real_values=real_vals,
                    sim_values={v: sim_vals.get(v, float("nan")) for v in vars_to_compare},
                    errors=errors,
                    statuses=statuses,
                    sync_status="PHASE_NORMALIZED",
                ))

        result.aggregates = _compute_aggregates(
            result.points, vars_to_compare, thresholds)
        result.duration_error_ratio = _safe_ratio(
            result.sim_duration_min - result.real_duration_min,
            result.real_duration_min,
        )
        result.duration_status = _classify_duration(
            result.duration_error_ratio, thresholds)
        return result


def _closest_sim_value_in_phase_window(
    *,
    interp: SimInterpolator,
    var: str,
    target_value: float,
    center_t: float,
    phase_start: float,
    phase_end: float,
    rel_window: float,
    min_window: float,
    max_window: float,
    n_samples: int,
) -> float:
    phase_duration = max(0.0, phase_end - phase_start)
    half_window = min(max_window, max(min_window, rel_window * phase_duration))
    t0 = max(phase_start, center_t - half_window)
    t1 = min(phase_end, center_t + half_window)
    if t1 <= t0 or n_samples <= 1:
        return interp.at(center_t).get(var, float("nan"))

    closest_value = interp.at(center_t).get(var, float("nan"))
    closest_error = abs(closest_value - target_value) if not math.isnan(closest_value) else float("inf")
    for i in range(n_samples):
        u = i / (n_samples - 1)
        t = t0 + u * (t1 - t0)
        value = interp.at(t).get(var, float("nan"))
        if math.isnan(value):
            continue
        error = abs(value - target_value)
        if error < closest_error:
            closest_error = error
            closest_value = value
    return closest_value


def _build_real_phase_blocks(
    steps: Sequence,
    mapping: PhaseMapping,
    apply_filter: bool,
) -> List[_RealPhaseBlock]:
    blocks: List[_RealPhaseBlock] = []
    if not steps:
        return blocks

    occurrence_count: Dict[str, int] = {}
    current_category: Optional[str] = None
    current_name = ""
    current_steps: List = []
    current_start = 0.0

    def close_block(t_end: float) -> None:
        nonlocal current_category, current_name, current_steps, current_start
        if current_category is None or not current_steps:
            return
        occurrence_count[current_category] = occurrence_count.get(current_category, 0) + 1
        blocks.append(_RealPhaseBlock(
            category=current_category,
            phase_name=current_name,
            steps=list(current_steps),
            t_start=current_start,
            t_end=max(current_start, t_end),
            occurrence=occurrence_count[current_category],
        ))

    for step in steps:
        category = mapping.category_of_real(step.step_name)
        if apply_filter and category in mapping.filter_categories:
            category = None

        if category != current_category:
            close_block(float(step.t_min))
            current_category = category
            current_name = step.step_name if category is not None else ""
            current_steps = []
            current_start = float(step.t_min)

        if category is not None:
            current_steps.append(step)

    close_block(float(steps[-1].t_min))
    return blocks


def _build_sim_phase_blocks(
    segments: Sequence[Segment],
    mapping: PhaseMapping,
) -> List[_SimPhaseBlock]:
    blocks: List[_SimPhaseBlock] = []
    if not segments:
        return blocks

    occurrence_count: Dict[str, int] = {}
    t = 0.0
    current_category: Optional[str] = None
    current_name = ""
    current_start = 0.0

    def close_block(t_end: float) -> None:
        nonlocal current_category, current_name, current_start
        if current_category is None:
            return
        occurrence_count[current_category] = occurrence_count.get(current_category, 0) + 1
        blocks.append(_SimPhaseBlock(
            category=current_category,
            phase_name=current_name,
            t_start=current_start,
            t_end=max(current_start, t_end),
            occurrence=occurrence_count[current_category],
        ))

    for seg in segments:
        category = mapping.category_of_sim(seg.name)
        if category != current_category:
            close_block(t)
            current_category = category
            current_name = seg.name if category is not None else ""
            current_start = t
        t += max(0.0, float(seg.duration))

    close_block(t)
    return blocks


def _interpolate_real_values(
    steps: Sequence,
    t: float,
    variables: List[str],
) -> Dict[str, float]:
    from app.analysis.comparator import _extract_real_values

    if not steps:
        return {v: float("nan") for v in variables}

    if t <= steps[0].t_min:
        return _extract_real_values(steps[0], variables)
    if t >= steps[-1].t_min:
        return _extract_real_values(steps[-1], variables)

    for i in range(len(steps) - 1):
        a = steps[i]
        b = steps[i + 1]
        if a.t_min <= t <= b.t_min:
            dt = max(1e-9, float(b.t_min) - float(a.t_min))
            u = (t - float(a.t_min)) / dt
            av = _extract_real_values(a, variables)
            bv = _extract_real_values(b, variables)
            return {
                var: av[var] + u * (bv[var] - av[var])
                for var in variables
            }

    return _extract_real_values(steps[-1], variables)
