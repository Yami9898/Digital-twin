"""
Chargement et utilisation du fichier `config/phase_mapping.json`.

Le mapping ne sert PAS à apparier 1-à-1 des phases simulées et réelles
(la comparaison se fait par interpolation temporelle). Il sert à :

  1. Trouver la **phase d'ancrage** pour le recalage temporel
     (par exemple « début du Vide initial »).
  2. **Catégoriser** chaque point réel pour le tableau de comparaison
     et le filtrage optionnel.

Charger une fois au démarrage avec `load_phase_mapping(path)`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PhaseMapping:
    """Représentation en mémoire du fichier de mapping."""

    # Catégories à essayer dans l'ordre pour le recalage temporel.
    anchor_categories: List[str]

    # Catégories à exclure de la comparaison.
    filter_categories: List[str]

    # Catégorie → liste de noms (côté simulation).
    sim_categories: Dict[str, List[str]] = field(default_factory=dict)

    # Catégorie → liste de noms (côté réel / PDF).
    real_categories: Dict[str, List[str]] = field(default_factory=dict)

    # ── Méthodes de lookup ──────────────────────────────────────────

    def category_of_real(self, real_step_name: str) -> Optional[str]:
        """Retourne la catégorie d'un nom de phase issu du PDF réel.
        Insensible à la casse et aux espaces autour. None si inconnu."""
        norm = _normalize(real_step_name)
        for category, names in self.real_categories.items():
            if any(_normalize(n) == norm for n in names):
                return category
        return None

    def category_of_sim(self, sim_step_name: str) -> Optional[str]:
        """Retourne la catégorie d'un nom de phase issu de la simulation.
        Vérifie aussi les correspondances partielles (le simulé ajoute
        souvent des suffixes du type ' - injection', ' - vide')."""
        norm = _normalize(sim_step_name)
        # Match exact d'abord
        for category, names in self.sim_categories.items():
            if any(_normalize(n) == norm for n in names):
                return category
        # Match par préfixe (ex: "Vide initial" match "Vide initial")
        for category, names in self.sim_categories.items():
            for n in names:
                norm_n = _normalize(n)
                if norm.startswith(norm_n) or norm_n.startswith(norm):
                    return category
        return None

    def is_filtered_real(self, real_step_name: str) -> bool:
        """True si cette phase réelle doit être exclue de la comparaison."""
        cat = self.category_of_real(real_step_name)
        return cat is not None and cat in self.filter_categories


# ────────────────────────────────────────────────────────────────────
# Chargement
# ────────────────────────────────────────────────────────────────────

def load_phase_mapping(path: str | Path) -> PhaseMapping:
    """Charge le fichier JSON et retourne un PhaseMapping prêt à l'emploi."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de mapping introuvable : {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return PhaseMapping(
        anchor_categories=list(data.get("anchor_categories", [])),
        filter_categories=list(data.get("filter_categories", [])),
        sim_categories=dict(data.get("simulated_phase_categories", {})),
        real_categories=dict(data.get("real_phase_categories", {})),
    )


# ────────────────────────────────────────────────────────────────────
# Helpers privés
# ────────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Normalise un nom de phase pour comparaison robuste.
    - lowercase
    - espaces multiples → un seul
    - strip
    """
    return " ".join(s.lower().split()).strip()
