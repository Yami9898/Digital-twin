"""
Recalage temporel entre cycle simulé et cycle réel.

Principe : on identifie une phase commune (l'« ancre ») dans les deux
cycles via le mapping de catégories, puis on calcule le décalage à
appliquer au réel pour que les deux origines coïncident.

  t_sim_aligné = t_real - dt_offset

Le simulé reste la référence (axe temporel = celui de la simulation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.analysis.phase_mapping import PhaseMapping
from app.model.sterilization_model import Segment


@dataclass
class AlignmentResult:
    """Résultat du calcul d'alignement."""

    # Catégorie effectivement utilisée comme ancre (None si aucune trouvée).
    anchor_category: Optional[str]

    # Décalage à soustraire du temps réel pour obtenir le temps simulé.
    # dt_offset = t_real_anchor - t_sim_anchor
    dt_offset: float

    # Informations de diagnostic (pour affichage / debug).
    t_sim_anchor: Optional[float]
    t_real_anchor: Optional[float]
    sim_phase_name: Optional[str]
    real_phase_name: Optional[str]

    @property
    def is_aligned(self) -> bool:
        """True si une ancre a pu être trouvée."""
        return self.anchor_category is not None

    def real_to_sim_time(self, t_real: float) -> float:
        """Convertit un temps réel en temps simulé."""
        return t_real - self.dt_offset


def align_origins(
    sim_segments: Sequence[Segment],
    real_steps: Sequence,  # List[CycleStep] mais on évite l'import circulaire
    mapping: PhaseMapping,
) -> AlignmentResult:
    """
    Cherche la première catégorie d'ancrage qui existe à la fois dans
    le simulé et dans le réel, puis calcule l'offset temporel.

    Si aucune ancre n'est trouvée, retourne un offset de 0
    (équivalent : on suppose que les deux cycles démarrent en même
    temps, ce qui peut être faux).
    """
    sim_starts = _build_sim_phase_starts(sim_segments)
    real_starts = _build_real_phase_starts(real_steps)

    for category in mapping.anchor_categories:
        # Y a-t-il un segment simulé dans cette catégorie ?
        t_sim, sim_name = _find_first_in_category(sim_starts, category,
                                                  mapping, is_sim=True)
        # Y a-t-il un point réel dans cette catégorie ?
        t_real, real_name = _find_first_in_category(real_starts, category,
                                                    mapping, is_sim=False)

        if t_sim is not None and t_real is not None:
            return AlignmentResult(
                anchor_category=category,
                dt_offset=t_real - t_sim,
                t_sim_anchor=t_sim,
                t_real_anchor=t_real,
                sim_phase_name=sim_name,
                real_phase_name=real_name,
            )

    # Aucune ancre commune trouvée
    return AlignmentResult(
        anchor_category=None,
        dt_offset=0.0,
        t_sim_anchor=None,
        t_real_anchor=None,
        sim_phase_name=None,
        real_phase_name=None,
    )


# ────────────────────────────────────────────────────────────────────
# Helpers privés
# ────────────────────────────────────────────────────────────────────

def _build_sim_phase_starts(segments: Sequence[Segment]) -> List[tuple]:
    """Retourne [(t_début, nom_phase)] pour chaque NOUVEAU nom de phase.
    Le modèle crée plusieurs segments par phase, on ne prend que le
    premier de chaque suite de segments homonymes."""
    starts: List[tuple] = []
    t = 0.0
    prev_name: Optional[str] = None
    for seg in segments:
        if seg.name != prev_name:
            starts.append((t, seg.name))
            prev_name = seg.name
        t += seg.duration
    return starts


def _build_real_phase_starts(steps: Sequence) -> List[tuple]:
    """Retourne [(t_min, step_name)] pour chaque NOUVELLE phase réelle."""
    starts: List[tuple] = []
    prev_name: Optional[str] = None
    for s in steps:
        if s.step_name != prev_name:
            starts.append((s.t_min, s.step_name))
            prev_name = s.step_name
    return starts


def _find_first_in_category(
    starts: List[tuple],
    category: str,
    mapping: PhaseMapping,
    is_sim: bool,
) -> tuple:
    """Cherche le premier (t, nom) dont le nom appartient à la catégorie.
    Retourne (None, None) si aucun trouvé."""
    classifier = (mapping.category_of_sim if is_sim
                  else mapping.category_of_real)
    for t, name in starts:
        if classifier(name) == category:
            return t, name
    return None, None
