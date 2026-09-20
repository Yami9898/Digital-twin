"""
Comparateur principal cycle simulé vs cycle réel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

from app.analysis.phase_mapping import PhaseMapping
from app.analysis.thresholds import Thresholds
from app.analysis.time_aligner import AlignmentResult
from app.model.constants import COMPARED_VARS
from app.model.sterilization_model import Segment

if TYPE_CHECKING:
    from app.analysis.strategies.phase_resync_strategy import PhaseDiscrepancy


@dataclass
class ComparisonPoint:
    """Une ligne du tableau de comparaison."""

    t_real: float
    t_sim_aligned: float
    real_phase: str
    sim_phase: str
    category: Optional[str]
    in_sim_range: bool

    real_values: Dict[str, float]
    sim_values: Dict[str, float]
    errors: Dict[str, float]
    statuses: Dict[str, str]

    sync_status: str = "ALIGNED"


@dataclass
class VariableAggregate:
    """Métriques agrégées pour une variable."""
    n: int = 0
    rmse: float = 0.0
    mae: float = 0.0
    bias: float = 0.0
    max_abs_error: float = 0.0
    max_signed_error: float = 0.0
    status: str = "—"


@dataclass
class ComparisonResult:
    """Résultat complet de la comparaison."""

    strategy: str = "interpolation"
    alignment: Optional[AlignmentResult] = None
    points: List[ComparisonPoint] = field(default_factory=list)
    aggregates: Dict[str, VariableAggregate] = field(default_factory=dict)
    phase_discrepancies: List["PhaseDiscrepancy"] = field(default_factory=list)

    n_filtered: int = 0
    n_out_of_sim_range: int = 0
    sim_duration_min: float = 0.0
    real_duration_min: float = 0.0
    duration_error_ratio: float = 0.0
    duration_status: str = "—"

    @property
    def n_compared(self) -> int:
        return sum(1 for p in self.points if p.in_sim_range)


def compare_cycles(
    sim_segments: Sequence[Segment],
    real_steps: Sequence,
    mapping: PhaseMapping,
    thresholds: Thresholds,
    *,
    variables: Optional[List[str]] = None,
    apply_filter: bool = True,
    strategy: str = "interpolation",
) -> ComparisonResult:
    """Compare un cycle simulé à un cycle réel selon la stratégie choisie."""
    from app.analysis.strategies import (
        InterpolationStrategy,
        PhaseNormalizedStrategy,
        PhaseResyncStrategy,
        StrategyName,
    )

    if isinstance(strategy, StrategyName):
        strategy_name = strategy.value
    else:
        strategy_name = str(strategy).lower()

    if strategy_name == StrategyName.PHASE_RESYNC.value:
        strat = PhaseResyncStrategy()
    elif strategy_name == StrategyName.PHASE_NORMALIZED.value:
        strat = PhaseNormalizedStrategy()
    elif strategy_name == StrategyName.INTERPOLATION.value:
        strat = InterpolationStrategy()
    else:
        raise ValueError(
            f"Stratégie inconnue : {strategy!r}. "
            f"Valeurs valides : {[s.value for s in StrategyName]}"
        )

    return strat.compare(
        sim_segments, real_steps, mapping, thresholds,
        variables=variables, apply_filter=apply_filter,
    )


def _extract_real_values(step, variables: List[str]) -> Dict[str, float]:
    return {
        "PT111":  float(getattr(step, "pt111",  0.0)),
        "PT112":  float(getattr(step, "pt112",  0.0)),
        "TT111":  float(getattr(step, "tt111",  0.0)),
        "TT112":  float(getattr(step, "tt112",  0.0)),
        "TT191":  float(getattr(step, "tt191",  0.0)),
        "RHT121": float(getattr(step, "rht121", 0.0)),
        "GT121":  float(getattr(step, "gt121",  0.0)),
    }


def _compute_aggregates(points: List[ComparisonPoint],
                        variables: List[str],
                        thresholds: Thresholds,
                        ) -> Dict[str, VariableAggregate]:
    aggregates: Dict[str, VariableAggregate] = {}

    for var in variables:
        errors = [p.errors[var] for p in points
                  if p.in_sim_range
                  and not math.isnan(p.errors.get(var, float('nan')))]

        agg = VariableAggregate()
        agg.n = len(errors)
        if errors:
            agg.rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
            agg.mae = sum(abs(e) for e in errors) / len(errors)
            agg.bias = sum(errors) / len(errors)
            agg.max_signed_error = max(errors, key=abs)
            agg.max_abs_error = abs(agg.max_signed_error)
            agg.status = thresholds.status_for(var, agg.rmse)

        aggregates[var] = agg

    return aggregates


def _safe_ratio(num: float, den: float) -> float:
    if abs(den) < 1e-9:
        return 0.0
    return num / den


def _classify_duration(error_ratio: float, thresholds: Thresholds) -> str:
    r = abs(error_ratio)
    if r <= thresholds.duration.ok_ratio:
        return "OK"
    if r <= thresholds.duration.warn_ratio:
        return "WARN"
    return "FAIL"
