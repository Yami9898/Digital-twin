"""
Interface commune des stratégies de comparaison.

Toute stratégie produit un `ComparisonResult` (défini dans comparator.py)
à partir des mêmes entrées : segments simulés, points réels, mapping
de phases et seuils.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Sequence, TYPE_CHECKING

from app.analysis.phase_mapping import PhaseMapping
from app.analysis.thresholds import Thresholds
from app.model.sterilization_model import Segment

if TYPE_CHECKING:
    from app.analysis.comparator import ComparisonResult


class StrategyName(str, Enum):
    """Identifiants des stratégies (utilisés par l'UI pour le choix)."""
    INTERPOLATION = "interpolation"
    PHASE_RESYNC = "phase_resync"
    PHASE_NORMALIZED = "phase_normalized"


class ComparisonStrategy(ABC):
    """Interface abstraite des stratégies de comparaison."""

    name: StrategyName
    display_name: str          # libellé affiché à l'utilisateur
    description: str           # explication courte (1-2 phrases)

    @abstractmethod
    def compare(
        self,
        sim_segments: Sequence[Segment],
        real_steps: Sequence,                # List[CycleStep]
        mapping: PhaseMapping,
        thresholds: Thresholds,
        *,
        variables: Optional[List[str]] = None,
        apply_filter: bool = True,
    ) -> "ComparisonResult":
        """Effectue la comparaison et retourne le résultat structuré."""
        ...
