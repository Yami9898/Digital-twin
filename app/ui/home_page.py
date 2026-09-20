"""
Page d'accueil — deux grandes cartes cliquables.

Émet :
  simulate_clicked  → l'utilisateur veut simuler un cycle
  analyze_clicked   → l'utilisateur veut analyser un cycle réel

Aucune logique métier dans ce module.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.ui.styles import BG_MAIN, BORDER, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, WHITE


# ── Carte cliquable ────────────────────────────────────────────────────────

class _ClickableCard(QFrame):
    """
    Grande carte cliquable avec icône, titre et description.
    Émet `clicked` au clic souris gauche ou au clic du bouton interne.
    """

    clicked = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        button_label: str = "Ouvrir",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HomeCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(300, 240)
        self.setMaximumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 28)
        layout.setSpacing(12)

        # ── Titre ────────────────────────────────────────────────────
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: 19px; font-weight: 800; color: {PRIMARY_DARK}; "
            "border: none; background: transparent;"
        )
        layout.addWidget(title_lbl)

        # ── Description ──────────────────────────────────────────────
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "font-size: 13px; color: #546E7A; "
            "border: none; background: transparent; line-height: 150%;"
        )
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # ── Bouton ───────────────────────────────────────────────────
        btn = QPushButton(button_label)
        btn.setObjectName("BtnPrimary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.clicked.connect(self.clicked)
        layout.addWidget(btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ── Page d'accueil ─────────────────────────────────────────────────────────

class HomePage(QWidget):
    """
    Page d'accueil avec deux rubriques principales.

    Signaux :
      simulate_clicked  — l'utilisateur ouvre la section Simulation
      analyze_clicked   — l'utilisateur ouvre la section Analyse
    """

    simulate_clicked  = Signal()
    analyze_clicked   = Signal()
    calibrate_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePage")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Fond général
        self.setStyleSheet(f"QWidget#HomePage {{ background-color: {BG_MAIN}; }}")

        # Zone centrale scrollable pour conserver les cartes sur les petits écrans
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("HomeContent")
        content.setStyleSheet(f"QWidget#HomeContent {{ background-color: {BG_MAIN}; }}")
        center = QVBoxLayout(content)
        center.setContentsMargins(80, 60, 80, 40)
        center.setSpacing(28)

        # ── Titre principal ──────────────────────────────────────────
        title = QLabel("Digital Twin — Stérilisateur EtO")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 30px; font-weight: 800; color: {PRIMARY_DARK}; "
            "letter-spacing: 0.4px;"
        )
        center.addWidget(title)

        # ── Sous-titre ───────────────────────────────────────────────
        subtitle = QLabel(
            "Simulation théorique du cycle  ·  Analyse de cycle réel  ·  Calibration versionnée"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #78909C; font-weight: 400;")
        center.addWidget(subtitle)

        # ── Ligne décorative ─────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(3)
        sep.setStyleSheet(
            f"background-color: {PRIMARY}; border: none; border-radius: 2px;"
        )
        sep.setMaximumWidth(120)
        sep.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sep_wrapper = QHBoxLayout()
        sep_wrapper.addStretch()
        sep_wrapper.addWidget(sep)
        sep_wrapper.addStretch()
        center.addLayout(sep_wrapper)

        # ── Cartes ───────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(36)
        cards_row.addStretch(1)

        self._card_simulate = _ClickableCard(
            title="Simuler un cycle",
            description=(
                "Créez ou ajustez une recette de stérilisation, "
                "lancez une simulation et visualisez le comportement "
                "théorique du cycle phase par phase."
            ),
            button_label="Simuler un cycle",
        )
        self._card_simulate.clicked.connect(self.simulate_clicked)
        cards_row.addWidget(self._card_simulate, 3)

        self._card_analyze = _ClickableCard(
            title="Analyser un cycle réel",
            description=(
                "Importez un rapport PDF d'un cycle réel, "
                "extrayez les données enregistrées et comparez-les "
                "à la simulation théorique."
            ),
            button_label="Analyser un cycle",
        )
        self._card_analyze.clicked.connect(self.analyze_clicked)
        cards_row.addWidget(self._card_analyze, 3)

        self._card_calibrate = _ClickableCard(
            title="Calibration versionnée",
            description=(
                "Regroupez plusieurs cycles réels, lancez une calibration "
                "par moindres carrés non linéaires et gérez l'historique "
                "des calibrations avec retour arrière sécurisé."
            ),
            button_label="Calibrer le modèle",
        )
        self._card_calibrate.clicked.connect(self.calibrate_clicked)
        cards_row.addWidget(self._card_calibrate, 3)

        cards_row.addStretch(1)
        center.addLayout(cards_row)

        # ── Bloc d'information ───────────────────────────────────────
        info_row = QHBoxLayout()
        info_row.setSpacing(20)
        info_row.addStretch(1)

        for label in [
            "Modèle physique EtO",
            "Import PDF cycle réel",
            "Comparaison sim / réel",
            "Calibration versionnée",
        ]:
            chip = QFrame()
            chip.setStyleSheet(
                f"background-color: {WHITE}; border: 1px solid {BORDER}; "
                "border-radius: 20px;"
            )
            chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(14, 8, 16, 8)
            chip_layout.setSpacing(8)
            chip_lbl = QLabel(label)
            chip_lbl.setStyleSheet(
                f"font-size: 12px; color: #546E7A; font-weight: 500; "
                "border: none; background: transparent;"
            )
            chip_layout.addWidget(chip_lbl)
            info_row.addWidget(chip)

        info_row.addStretch(1)
        center.addLayout(info_row)

        center.addStretch()

        # ── Pied de page ─────────────────────────────────────────────
        footer = QLabel("Digital Twin EtO v5")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #B0BEC5;")
        center.addWidget(footer)

        scroll.setWidget(content)
        root.addWidget(scroll)
