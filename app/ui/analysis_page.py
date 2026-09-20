"""
Page "Analyser un cycle réel".

Structure :
  AnalysisPage (QWidget)
  ├── En-tête de section
  └── QTabWidget
       ├── Onglet "Cycle réel"   → RealCycleTab (existant — inchangé)
       └── Onglet "Comparaison"  → ComparisonTab (existant — inchangé)

RÈGLE : Ce fichier ne modifie pas RealCycleTab ni ComparisonTab.
Il les instancie et les encapsule dans la nouvelle structure visuelle.

La méthode set_sim_segments() permet de transmettre un cycle simulé
depuis SimulationPage (via MainWindow) pour préparer la comparaison.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout,
    QWidget,
)

from app.comparison_tab import ComparisonTab
from app.real_cycle_tab import RealCycleTab
from app.ui.styles import PRIMARY_DARK, PRIMARY_LIGHT, WHITE


class AnalysisPage(QWidget):
    """
    Page d'analyse de cycle réel.

    Instancie RealCycleTab et ComparisonTab, et les présente
    dans une interface à deux onglets.

    API publique :
      set_sim_segments(segments, recipe_name) — transmet les segments
          simulés depuis SimulationPage et bascule sur l'onglet Comparaison.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Instanciation des onglets existants (inchangés)
        self.real_tab        = RealCycleTab()
        self.comparison_tab  = ComparisonTab()

        self._build_ui()

    # ── Construction de l'interface ───────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # En-tête de section
        root.addWidget(self._build_section_header())

        # QTabWidget principal
        self._tab_widget = QTabWidget()
        root.addWidget(self._tab_widget, stretch=1)

        self._tab_widget.addTab(
            self._scrollable_page(self.real_tab, minimum_height=650),
            "Cycle réel",
        )
        self._tab_widget.addTab(
            self._scrollable_page(self.comparison_tab, minimum_height=1020),
            "Comparaison",
        )

    @staticmethod
    def _scrollable_page(content: QWidget, minimum_height: int) -> QScrollArea:
        """Fait défiler verticalement les vues d'analyse riches en contenu."""
        content.setMinimumHeight(minimum_height)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _build_section_header(self) -> QWidget:
        """Bandeau coloré avec le titre de la section."""
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(
            f"background-color: {PRIMARY_LIGHT}; "
            "border-bottom: 1px solid #C4DDD9;"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)

        title = QLabel("Analyser un cycle réel")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {PRIMARY_DARK}; "
            "background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()

        hint = QLabel("Importez un rapport PDF, puis lancez la comparaison.")
        hint.setStyleSheet("font-size: 12px; color: #78909C; background: transparent;")
        hl.addWidget(hint)

        return header

    # ── API publique ──────────────────────────────────────────────────

    def set_sim_segments(self, segments: List, recipe_name: str = "") -> None:
        """
        Transmet les segments simulés à ComparisonTab et bascule
        automatiquement sur l'onglet Comparaison.

        Appelé par MainWindow quand l'utilisateur clique sur
        "Comparer à un cycle réel" depuis SimulationPage.
        """
        self.comparison_tab.set_sim_segments(segments, recipe_name)
        self._tab_widget.setCurrentIndex(1)

    def switch_to_real_tab(self) -> None:
        """Bascule sur l'onglet 'Cycle réel' (depuis l'extérieur)."""
        self._tab_widget.setCurrentIndex(0)

    def switch_to_comparison(self) -> None:
        """Bascule sur l'onglet 'Comparaison' (depuis l'extérieur)."""
        self._tab_widget.setCurrentIndex(1)
