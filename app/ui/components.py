"""
Composants UI réutilisables.

Contient :
  - StatusBadge        : badge coloré (OK / WARN / FAIL / NA / PENDING)
  - AssistantPlaceholder : panneau réservé pour l'assistant recette (futur)
  - AISummaryPlaceholder : zone réservée pour le résumé IA (futur)

IMPORTANT : Ces composants ne contiennent AUCUNE logique IA, aucun appel API,
aucune connexion à un modèle LLM ou à n8n. Ils servent uniquement à préparer
l'interface pour une intégration future.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.ui.styles import BORDER, PRIMARY_DARK, PRIMARY_LIGHT, WHITE


# ── Badge de statut ────────────────────────────────────────────────────────

class StatusBadge(QLabel):
    """
    Badge coloré indiquant un statut.

    Statuts reconnus : OK, WARN, FAIL, NA, PENDING.
    Peut être mis à jour dynamiquement via set_status().
    """

    _PRESETS: dict[str, tuple[str, str, str]] = {
        "OK":      ("#E8F5E9", "#2E7D32", "Atteint"),
        "WARN":    ("#FFF8E1", "#E65100", "À vérifier"),
        "FAIL":    ("#FFEBEE", "#C62828", "Non atteint"),
        "NA":      ("#F5F5F5", "#9E9E9E", "Non applicable"),
        "PENDING": ("#EDE7F6", "#6A1B9A", "En attente"),
    }

    def __init__(self, status: str = "NA", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        bg, fg, text = self._PRESETS.get(status, self._PRESETS["NA"])
        self.setText(text)
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            "border-radius: 10px; padding: 3px 10px; "
            "font-size: 11px; font-weight: 600;"
        )


# ── Panneau assistant (placeholder) ───────────────────────────────────────

class AssistantPlaceholder(QFrame):
    """
    Panneau latéral réservé pour l'assistant recette.

    Ce panneau est un PLACEHOLDER visuel pur.
    Il n'exécute aucune logique IA, n'appelle aucun modèle ou service.
    L'intégration réelle de l'assistant sera effectuée lors d'une étape future.
    Les boutons sont volontairement désactivés (disabled).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AssistantPanel")
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ── Titre + badge statut ─────────────────────────────────────
        header_row = QHBoxLayout()

        title = QLabel("Assistant recette")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {PRIMARY_DARK}; "
            "background: transparent; border: none;"
        )
        header_row.addWidget(title, 1)

        badge = QLabel("Non connecté")
        badge.setStyleSheet(
            "background-color: #F5F5F5; color: #9E9E9E; "
            "border-radius: 10px; padding: 2px 9px; "
            "font-size: 10px; font-weight: 600; border: none;"
        )
        badge.setAlignment(Qt.AlignVCenter)
        header_row.addWidget(badge)

        layout.addLayout(header_row)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER}; background: {BORDER}; max-height: 1px; border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Message principal ────────────────────────────────────────
        msg = QLabel(
            "Cette zone sera utilisée pour\n"
            "guider la saisie de recette lors\n"
            "d'une prochaine étape."
        )
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(
            "color: #78909C; font-size: 12px; "
            "background: transparent; border: none; padding: 6px 0;"
        )
        layout.addWidget(msg)

        # ── Note de responsabilité ───────────────────────────────────
        note = QLabel(
            "La validation finale reste\n"
            "sous la responsabilité\n"
            "de l'utilisateur."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet(
            f"color: {PRIMARY_DARK}; font-size: 11px; "
            f"background-color: {PRIMARY_LIGHT}; "
            "border-radius: 6px; padding: 8px; border: none;"
        )
        layout.addWidget(note)

        layout.addStretch()

        # ── Boutons futurs (désactivés) ──────────────────────────────
        future_lbl = QLabel("Fonctions à venir :")
        future_lbl.setStyleSheet(
            "color: #AAAAAA; font-size: 10px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        layout.addWidget(future_lbl)

        _future_buttons = [
            "Vérifier les champs manquants",
            "Expliquer la phase sélectionnée",
            "Résumer la recette",
            "Préparer la simulation",
        ]
        for label in _future_buttons:
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.setStyleSheet(
                "QPushButton {"
                "  border: 1px dashed #C8D8D6;"
                "  border-radius: 5px;"
                "  color: #C8D8D6;"
                "  background: transparent;"
                "  padding: 5px 8px;"
                "  font-size: 11px;"
                "  font-weight: 400;"
                "  text-align: left;"
                "}"
            )
            layout.addWidget(btn)

        # ── Pied de page ─────────────────────────────────────────────
        footer = QLabel("Intégration future — Non connecté")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(
            "color: #D0D8D8; font-size: 10px; margin-top: 4px; "
            "background: transparent; border: none;"
        )
        layout.addWidget(footer)


# ── Zone résumé IA (placeholder) ──────────────────────────────────────────

class AISummaryPlaceholder(QFrame):
    """
    Zone réservée pour le résumé intelligent du cycle.

    Ce composant est un PLACEHOLDER visuel pur.
    Il n'effectue aucune analyse, ne génère aucun texte automatiquement.
    L'intégration du module IA sera effectuée lors d'une étape future.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SummaryCard")
        self.setFixedHeight(90)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        # Texte
        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title = QLabel("Résumé intelligent du cycle")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {PRIMARY_DARK}; "
            "background: transparent; border: none;"
        )
        text_col.addWidget(title)

        desc = QLabel(
            "Le résumé automatique du cycle sera intégré ultérieurement. "
            "Cette zone affichera les interprétations générées par le module IA "
            "lors d'une prochaine mise à jour."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            "color: #78909C; font-size: 11px; "
            "background: transparent; border: none;"
        )
        text_col.addWidget(desc)
        text_col.addStretch()

        layout.addLayout(text_col, 1)

        # Badge statut
        badge = QLabel("En attente\nd'intégration")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(90)
        badge.setStyleSheet(
            "background-color: #EDE7F6; color: #6A1B9A; "
            "border-radius: 8px; padding: 6px 8px; "
            "font-size: 10px; font-weight: 600; border: none;"
        )
        layout.addWidget(badge)
