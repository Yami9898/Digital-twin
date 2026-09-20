"""
Moteur d'analyse / comparaison cycle simulé vs cycle réel.

Architecture :
  - phase_mapping.py    : chargement & utilisation de config/phase_mapping.json
  - time_aligner.py     : calcul de l'offset temporel sim ↔ réel
  - sim_interpolator.py : interpolation des séries simulées
  - thresholds.py       : chargement & application des seuils OK/WARN/FAIL
  - comparator.py       : dispatcher + structures de résultat
  - strategies/         : implémentations des méthodes de comparaison
"""

from app.analysis.phase_mapping import (
    PhaseMapping,
    load_phase_mapping,
)
from app.analysis.time_aligner import (
    AlignmentResult,
    align_origins,
)
from app.analysis.sim_interpolator import SimInterpolator
from app.analysis.thresholds import (
    Thresholds,
    classify_error,
    load_thresholds,
)
from app.analysis.comparator import (
    ComparisonPoint,
    ComparisonResult,
    VariableAggregate,
    compare_cycles,
)
from app.analysis.strategies import (
    ComparisonStrategy,
    StrategyName,
    InterpolationStrategy,
    PhaseResyncStrategy,
    PhaseNormalizedStrategy,
    PhaseDiscrepancy,
)

__all__ = [
    "PhaseMapping",
    "load_phase_mapping",
    "AlignmentResult",
    "align_origins",
    "SimInterpolator",
    "Thresholds",
    "classify_error",
    "load_thresholds",
    "ComparisonPoint",
    "ComparisonResult",
    "VariableAggregate",
    "compare_cycles",
    "ComparisonStrategy",
    "StrategyName",
    "InterpolationStrategy",
    "PhaseResyncStrategy",
    "PhaseNormalizedStrategy",
    "PhaseDiscrepancy",
]
