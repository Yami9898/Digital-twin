"""
Interpolation des séries simulées à un instant t arbitraire.

Le `SterilizationModel` produit des `Segment`s : chacun a un état au
début et à la fin, et une durée. Pour comparer aux points du PDF réel
(qui peuvent tomber n'importe où dans la timeline), on a besoin de
pouvoir évaluer le simulé en un instant quelconque.

Méthode : interpolation linéaire entre l'état au début et à la fin
du segment qui contient l'instant demandé. C'est cohérent avec la
manière dont le simulé est tracé dans PlotTab.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.model.constants import VARIABLES
from app.model.sterilization_model import Segment, lerp


class SimInterpolator:
    """
    Interpolateur de la série simulée.

    Usage :
        interp = SimInterpolator(segments)
        vals = interp.at(t_min)  # dict {var: value}
    """

    def __init__(self, segments: Sequence[Segment]) -> None:
        # On précalcule les bornes de chaque segment pour faire
        # une recherche dichotomique en O(log N) à chaque .at()
        self._segments: List[Segment] = list(segments)
        self._starts: List[float] = []
        self._ends: List[float] = []

        t = 0.0
        for seg in self._segments:
            self._starts.append(t)
            t += seg.duration
            self._ends.append(t)

        self._total_duration = t

    @property
    def total_duration(self) -> float:
        return self._total_duration

    def at(self, t: float) -> Dict[str, float]:
        """
        Retourne les valeurs interpolées au temps t (en minutes).

        Comportement aux bornes :
          - t <= 0           → état initial du 1er segment
          - t >= durée_totale → état final du dernier segment
          - sinon            → interpolation linéaire dans le bon segment
        """
        if not self._segments:
            return {var: 0.0 for var in VARIABLES}

        if t <= self._starts[0]:
            return dict(self._segments[0].start_state)
        if t >= self._ends[-1]:
            return dict(self._segments[-1].end_state)

        idx = self._find_segment_index(t)
        seg = self._segments[idx]
        seg_start = self._starts[idx]
        seg_end = self._ends[idx]
        seg_duration = max(1e-9, seg_end - seg_start)

        u = (t - seg_start) / seg_duration
        return {
            var: lerp(
                seg.start_state.get(var, 0.0),
                seg.end_state.get(var, 0.0),
                u,
            )
            for var in VARIABLES
        }

    def phase_at(self, t: float) -> str:
        """Retourne le nom du segment simulé contenant l'instant t."""
        if not self._segments:
            return ""
        if t <= self._starts[0]:
            return self._segments[0].name
        if t >= self._ends[-1]:
            return self._segments[-1].name
        return self._segments[self._find_segment_index(t)].name

    # ── Recherche dichotomique ──────────────────────────────────────

    def _find_segment_index(self, t: float) -> int:
        """Recherche dichotomique du segment contenant t (t > 0, t < total)."""
        lo, hi = 0, len(self._segments) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if t < self._starts[mid]:
                hi = mid - 1
            elif t > self._ends[mid]:
                lo = mid + 1
            else:
                return mid
        # Fallback (ne devrait pas arriver vu les bornes vérifiées en amont)
        return max(0, min(lo, len(self._segments) - 1))
