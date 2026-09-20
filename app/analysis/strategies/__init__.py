"""
Stratégies de comparaison cycle simulé vs cycle réel.

Trois implémentations actuellement :
  - InterpolationStrategy : pure interpolation temporelle après un
    recalage unique sur la phase d'ancrage.
  - PhaseResyncStrategy : recalage par phase, mesure des écarts
    temporels par phase ET écarts de valeurs après resync.
  - PhaseNormalizedStrategy : comparaison des valeurs sur un axe 0-100 %
    propre à chaque phase, plus robuste aux petits déphasages.

Ces stratégies suivent le pattern Strategy (interface commune
ComparisonStrategy). On peut en ajouter d'autres sans modifier
le code appelant.
"""

from app.analysis.strategies.base import (
    ComparisonStrategy,
    StrategyName,
)
from app.analysis.strategies.interpolation_strategy import (
    InterpolationStrategy,
)
from app.analysis.strategies.phase_resync_strategy import (
    PhaseResyncStrategy,
    PhaseDiscrepancy,
)
from app.analysis.strategies.phase_normalized_strategy import (
    PhaseNormalizedStrategy,
)

__all__ = [
    "ComparisonStrategy",
    "StrategyName",
    "InterpolationStrategy",
    "PhaseResyncStrategy",
    "PhaseDiscrepancy",
    "PhaseNormalizedStrategy",
]
