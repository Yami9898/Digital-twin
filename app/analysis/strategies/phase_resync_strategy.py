"""
Stratégie de comparaison avec resync par phase.

Méthode (différente de l'interpolation pure) :

  1. Recalage initial sur la phase d'ancrage (ex: « Vide initial »).

  2. Parcourir le réel point par point :

     a. Au DÉBUT d'une nouvelle phase réelle (catégorie X) :
        - Regarder où en est le simulé à cet instant (avec l'offset courant).
        - Si le simulé est dans la même catégorie X → OK, on comparera.
        - Sinon → DÉSYNC : on note l'écart temporel et on recale en
          cherchant la prochaine occurrence de catégorie X dans le simulé.

     b. À l'INTÉRIEUR d'une phase (point intermédiaire dans la même
        catégorie que le précédent) :
        - Comparaison normale aux valeurs interpolées.

  3. À la fin, on a deux jeux d'informations :
     - Liste de **PhaseDiscrepancy** : un par phase, mesure l'écart
       temporel entre début sim et début réel de cette catégorie.
     - Liste de **ComparisonPoint** : les comparaisons de valeurs
       (PT, TT, RH) point par point, comme en interpolation.

Cette stratégie sépare proprement deux questions :
  - Mon modèle prédit-il les bonnes valeurs ? (errors)
  - Mon modèle prédit-il les bonnes durées ? (phase_discrepancies)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from app.analysis.phase_mapping import PhaseMapping
from app.analysis.sim_interpolator import SimInterpolator
from app.analysis.strategies.base import ComparisonStrategy, StrategyName
from app.analysis.thresholds import Thresholds
from app.analysis.time_aligner import align_origins
from app.model.constants import COMPARED_VARS
from app.model.sterilization_model import Segment

if TYPE_CHECKING:
    from app.analysis.comparator import ComparisonResult


# ────────────────────────────────────────────────────────────────────
# Structure : écart temporel par phase
# ────────────────────────────────────────────────────────────────────

@dataclass
class PhaseDiscrepancy:
    """Mesure l'écart temporel entre début sim et début réel d'une phase."""

    category: str                 # catégorie de la phase
    real_phase_name: str          # nom tel qu'écrit dans le PDF
    sim_phase_name: str           # nom de la phase sim correspondante
                                  # (chaîne vide si pas trouvée)
    occurrence: int               # 1ère, 2e, … occurrence de cette catégorie

    t_real_start: float           # début de la phase dans le réel (min)
    t_sim_start_expected: float   # où le sim devrait être (avec offset)
    t_sim_start_actual: float     # début effectif de la phase dans le sim
                                  # (NaN si pas trouvée)

    drift_min: float              # t_sim_actual - t_sim_expected
                                  # > 0 : la phase commence plus TARD dans
                                  #       le simé que prévu → simé en retard
                                  # < 0 : la phase commence plus TÔT dans
                                  #       le simé → simé en avance

    direction: str                # 'sim_avance' | 'sim_retard' | 'aligne' | 'introuvable'
    status: str                   # 'OK' | 'WARN' | 'FAIL' | 'MISSING'


# ────────────────────────────────────────────────────────────────────
# Structure interne : liste compactée des phases simulées
# ────────────────────────────────────────────────────────────────────

@dataclass
class SimPhaseBlock:
    """Bloc contigu de segments simulés de même nom = une phase macro."""
    name: str
    t_start: float
    t_end: float
    index: int  # position dans la liste


# ────────────────────────────────────────────────────────────────────
# Stratégie principale
# ────────────────────────────────────────────────────────────────────

class PhaseResyncStrategy(ComparisonStrategy):
    """Comparaison avec resync à chaque transition de phase réelle."""

    name = StrategyName.PHASE_RESYNC
    display_name = "Resync par phase"
    description = (
        "Suit les phases du cycle réel une par une. À chaque transition, "
        "vérifie que le simulé est dans la même phase ; sinon, note l'écart "
        "temporel et resynchronise sur le début de la phase correspondante "
        "côté simulé. Mesure les écarts de durée par phase EN PLUS des "
        "écarts de valeurs."
    )

    # Seuils pour qualifier l'écart temporel par phase (en minutes)
    PHASE_DRIFT_OK_MIN = 2.0
    PHASE_DRIFT_WARN_MIN = 10.0

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

        # 1. Préparation
        sim_blocks = _build_sim_phase_blocks(sim_segments)
        interp = SimInterpolator(sim_segments)

        # Alignement initial sur la phase d'ancrage
        alignment = align_origins(sim_segments, real_steps, mapping)
        dt_offset = alignment.dt_offset

        result = ComparisonResult(
            strategy=self.name,
            alignment=alignment,
            sim_duration_min=interp.total_duration,
        )
        result.real_duration_min = real_steps[-1].t_min if real_steps else 0.0

        # Compteur d'occurrences par catégorie (1ère, 2e, …)
        category_occurrences: Dict[str, int] = {}

        # Pour suivre l'avancement dans sim_blocks lors du resync
        current_sim_block_idx = 0

        # Mémoire de la catégorie de la phase réelle précédente
        prev_real_category: Optional[str] = None

        # 2. Boucle sur les points réels
        for step in real_steps:
            real_category = mapping.category_of_real(step.step_name)

            # Filtrage
            if apply_filter and real_category in mapping.filter_categories:
                result.n_filtered += 1
                prev_real_category = real_category
                continue

            # ── Détection de transition de phase ────────────────────
            is_new_phase = (real_category != prev_real_category)

            if is_new_phase and real_category is not None:
                # On rentre dans une nouvelle catégorie réelle
                category_occurrences[real_category] = (
                    category_occurrences.get(real_category, 0) + 1
                )
                occurrence = category_occurrences[real_category]

                # Position attendue dans le simulé (avec offset courant)
                t_sim_expected = step.t_min - dt_offset

                # Quelle phase est le simulé en train de faire ?
                sim_block_now = _block_at_time(sim_blocks, t_sim_expected)
                sim_category_now = (
                    mapping.category_of_sim(sim_block_now.name)
                    if sim_block_now else None
                )

                if sim_category_now == real_category:
                    # ─── Aligné : pas de désync ─────────────────────
                    discrepancy = PhaseDiscrepancy(
                        category=real_category,
                        real_phase_name=step.step_name,
                        sim_phase_name=sim_block_now.name,
                        occurrence=occurrence,
                        t_real_start=step.t_min,
                        t_sim_start_expected=t_sim_expected,
                        t_sim_start_actual=sim_block_now.t_start,
                        drift_min=sim_block_now.t_start - t_sim_expected,
                        direction="aligne",
                        status=self._classify_drift(
                            abs(sim_block_now.t_start - t_sim_expected)),
                    )
                else:
                    # ─── Désync : chercher la nième occurrence de la
                    # catégorie réelle dans le simulé, à partir du
                    # bloc courant ──────────────────────────────────
                    target = _find_nth_block_of_category(
                        sim_blocks, real_category, occurrence, mapping,
                        from_index=current_sim_block_idx,
                    )

                    if target is None:
                        # Le simulé n'a pas cette catégorie (ou plus assez
                        # d'occurrences)
                        discrepancy = PhaseDiscrepancy(
                            category=real_category,
                            real_phase_name=step.step_name,
                            sim_phase_name="",
                            occurrence=occurrence,
                            t_real_start=step.t_min,
                            t_sim_start_expected=t_sim_expected,
                            t_sim_start_actual=float('nan'),
                            drift_min=float('nan'),
                            direction="introuvable",
                            status="MISSING",
                        )
                    else:
                        # Mesure de la dérive : si target.t_start est avant
                        # t_sim_expected, le simé est en AVANCE (la phase
                        # est déjà passée dans le sim). Sinon en RETARD.
                        drift = target.t_start - t_sim_expected
                        direction = ("sim_avance" if drift < 0
                                     else "sim_retard")

                        discrepancy = PhaseDiscrepancy(
                            category=real_category,
                            real_phase_name=step.step_name,
                            sim_phase_name=target.name,
                            occurrence=occurrence,
                            t_real_start=step.t_min,
                            t_sim_start_expected=t_sim_expected,
                            t_sim_start_actual=target.t_start,
                            drift_min=drift,
                            direction=direction,
                            status=self._classify_drift(abs(drift)),
                        )

                        # ─── RESYNC : on met à jour l'offset ────────
                        # Nouveau offset tel que t_sim_recalé = target.t_start
                        # quand t_real = step.t_min
                        # → offset = step.t_min - target.t_start
                        dt_offset = step.t_min - target.t_start
                        current_sim_block_idx = target.index

                result.phase_discrepancies.append(discrepancy)

            # ── Comparaison de valeurs au point courant ─────────────
            t_sim = step.t_min - dt_offset
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

            sync_status = ("RESYNCED" if is_new_phase and real_category
                           is not None else "ALIGNED")

            result.points.append(ComparisonPoint(
                t_real=step.t_min,
                t_sim_aligned=t_sim,
                real_phase=step.step_name,
                sim_phase=sim_phase,
                category=real_category,
                in_sim_range=in_range,
                real_values=real_vals,
                sim_values=sim_vals,
                errors=errors,
                statuses=statuses,
                sync_status=sync_status,
            ))

            prev_real_category = real_category

        # 3. Agrégats + durée
        result.aggregates = _compute_aggregates(
            result.points, vars_to_compare, thresholds)
        result.duration_error_ratio = _safe_ratio(
            result.sim_duration_min - result.real_duration_min,
            result.real_duration_min,
        )
        result.duration_status = _classify_duration(
            result.duration_error_ratio, thresholds)

        return result

    # ── Helpers ─────────────────────────────────────────────────────

    def _classify_drift(self, abs_drift_min: float) -> str:
        if abs_drift_min <= self.PHASE_DRIFT_OK_MIN:
            return "OK"
        if abs_drift_min <= self.PHASE_DRIFT_WARN_MIN:
            return "WARN"
        return "FAIL"


# ────────────────────────────────────────────────────────────────────
# Helpers privés au module
# ────────────────────────────────────────────────────────────────────

def _build_sim_phase_blocks(segments: Sequence[Segment]) -> List[SimPhaseBlock]:
    """Compacte la liste de segments en phases macro (groupes contigus
    de même nom). Indispensable parce que le moteur crée plusieurs
    sous-segments par phase (ex: 'Vide initial' = N segments)."""
    blocks: List[SimPhaseBlock] = []
    if not segments:
        return blocks

    t = 0.0
    cur_name = segments[0].name
    cur_start = 0.0

    for seg in segments:
        if seg.name != cur_name:
            blocks.append(SimPhaseBlock(
                name=cur_name, t_start=cur_start,
                t_end=t, index=len(blocks),
            ))
            cur_name = seg.name
            cur_start = t
        t += seg.duration

    blocks.append(SimPhaseBlock(
        name=cur_name, t_start=cur_start,
        t_end=t, index=len(blocks),
    ))
    return blocks


def _block_at_time(blocks: List[SimPhaseBlock],
                    t: float) -> Optional[SimPhaseBlock]:
    """Retourne le bloc qui contient l'instant t, ou None si hors plage."""
    if not blocks:
        return None
    if t < blocks[0].t_start:
        return blocks[0]
    if t > blocks[-1].t_end:
        return blocks[-1]
    for blk in blocks:
        if blk.t_start <= t <= blk.t_end:
            return blk
    return None


def _find_nth_block_of_category(
    blocks: List[SimPhaseBlock],
    category: str,
    occurrence: int,
    mapping: PhaseMapping,
    *,
    from_index: int = 0,
) -> Optional[SimPhaseBlock]:
    """Cherche le n-ième bloc dont la catégorie correspond, à partir
    de from_index. Retourne None si introuvable.

    Note : l'occurrence est globale (depuis le début du simulé), pas
    relative à from_index. C'est important : si le simulé fait 4
    injections de gaz, la 3e occurrence reste la 3e même si on est
    déjà passé devant les deux premières.
    """
    found = 0
    for blk in blocks:
        if mapping.category_of_sim(blk.name) == category:
            found += 1
            if found == occurrence and blk.index >= from_index:
                return blk
            # Si on cherche la 3e mais on n'est pas encore au from_index,
            # on continue à compter
    return None
