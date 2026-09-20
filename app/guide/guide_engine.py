"""
app/guide/guide_engine.py
Navigation du guide : nœud courant, pile d'historique, fil d'Ariane.

Aucune logique métier, aucune dépendance PySide6.
"""

from __future__ import annotations

from typing import List, Tuple

from app.guide.guide_content import NODES


class GuideEngine:
    """
    Gère la navigation dans l'arbre de nœuds du guide.

    Méthodes publiques :
      current()       → dict du nœud courant
      navigate(id)    → aller à un nœud, empile l'historique
      go_back()       → reculer d'un niveau
      go_home()       → revenir à l'accueil (vide l'historique)
      breadcrumb()    → liste de (titre, node_id) représentant le chemin
    """

    HOME_ID = "home"

    def __init__(self) -> None:
        self._history: List[str] = []   # pile des node_id visités
        self._current_id: str = self.HOME_ID

    # ── Interface publique ─────────────────────────────────────────────

    def current(self) -> dict:
        """Retourne le nœud courant (dict)."""
        return NODES.get(self._current_id, NODES[self.HOME_ID])

    def navigate(self, node_id: str) -> bool:
        """
        Navigue vers node_id.
        Retourne True si le nœud existe, False sinon.
        """
        if node_id not in NODES:
            return False
        self._history.append(self._current_id)
        self._current_id = node_id
        return True

    def go_back(self) -> None:
        """Revient au nœud précédent. Ne fait rien si on est à l'accueil."""
        if self._history:
            self._current_id = self._history.pop()

    def go_home(self) -> None:
        """Revient à l'accueil et vide l'historique."""
        self._history.clear()
        self._current_id = self.HOME_ID

    def can_go_back(self) -> bool:
        return bool(self._history)

    def breadcrumb(self) -> List[Tuple[str, str]]:
        """
        Retourne le fil d'Ariane : liste de (titre_court, node_id).
        Le premier élément est toujours l'accueil.
        Le dernier est le nœud courant.
        """
        crumb: List[Tuple[str, str]] = []
        for nid in self._history:
            node = NODES.get(nid, {})
            crumb.append((node.get("title", nid), nid))
        current = self.current()
        crumb.append((current.get("title", self._current_id), self._current_id))
        return crumb
