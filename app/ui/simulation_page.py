"""
Page "Simuler un cycle".

Structure :
  SimulationPage (QWidget)
  ├── En-tête de section
  └── QTabWidget
       ├── Onglet "Recette"
       │    ├── QSplitter
       │    │    ├── RecipeTab   (formulaire recette existant — inchangé)
       │    │    └── GuideWidget (guide interactif local — aucune connexion IA)
       │    └── Barre "Lancer la simulation"
       └── Onglet "Résultats de simulation"
            └── PlotTab           (courbe simulée existante — inchangée)

RÈGLE : Ce fichier ne modifie pas RecipeTab ni PlotTab.
Il les instancie, les connecte selon l'API existante, et les encapsule
dans la nouvelle structure visuelle.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from app.guide.guide_widget import GuideWidget
from app.plot_tab import PlotTab
from app.recipe_tab import RecipeTab
from app.ui.styles import PRIMARY_DARK, PRIMARY_LIGHT, WHITE


class SimulationPage(QWidget):
    """
    Page principale de simulation.

    Instancie RecipeTab et PlotTab, les connecte selon l'API existante,
    et les présente dans une interface à deux onglets.

    Signal :
      compare_requested(segments, recipe_name) — l'utilisateur veut comparer
          avec un cycle réel. Le parent (MainWindow) gère la navigation.
    """

    compare_requested = Signal(list, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # ── Instanciation des onglets existants ─────────────────────
        # On instancie ici (et non dans MainWindow) pour que cette page
        # soit autonome. Les onglets existants sont utilisés tels quels.
        self.recipe_tab = RecipeTab()
        self.plot_tab   = PlotTab()

        # Connexion selon l'API existante (inchangée)
        self.plot_tab.set_recipe_provider(self.recipe_tab)
        # On intercepte le callback "comparer" pour relayer via notre signal
        self.plot_tab.set_comparison_callback(self._relay_compare)

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
            self._scrollable_page(self._build_recipe_tab(), minimum_height=650),
            "Recette",
        )
        self._tab_widget.addTab(
            self._scrollable_page(self._build_results_tab(), minimum_height=650),
            "Résultats de simulation",
        )

    @staticmethod
    def _scrollable_page(content: QWidget, minimum_height: int) -> QScrollArea:
        """Fait défiler verticalement un onglet complet lorsque sa hauteur manque."""
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

        title = QLabel("Simuler un cycle")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {PRIMARY_DARK}; "
            "background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()

        hint = QLabel("Remplissez la recette, puis lancez la simulation.")
        hint.setStyleSheet("font-size: 12px; color: #78909C; background: transparent;")
        hl.addWidget(hint)

        return header

    def _build_recipe_tab(self) -> QWidget:
        """
        Onglet "Recette".

        Contient :
          - RecipeTab (existant, à gauche dans un QSplitter)
          - GuideWidget à droite (guide interactif local, aucune connexion IA)
          - Barre de lancement en bas
        """
        page = QWidget()
        page.setStyleSheet(f"background-color: {WHITE};")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # QSplitter : formulaire | guide interactif local
        splitter = QSplitter(Qt.Horizontal)

        # Côté gauche — RecipeTab dans un wrapper transparent
        recipe_wrapper = QWidget()
        recipe_wrapper.setStyleSheet("background: transparent;")
        rw_layout = QVBoxLayout(recipe_wrapper)
        rw_layout.setContentsMargins(0, 0, 0, 0)
        rw_layout.setSpacing(0)
        rw_layout.addWidget(self.recipe_tab)

        splitter.addWidget(recipe_wrapper)

        # Côté droit — Guide de simulation interactif
        guide = GuideWidget()
        splitter.addWidget(guide)

        # Tailles initiales : recette large, guide réduit
        splitter.setSizes([900, 270])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, True)

        page_layout.addWidget(splitter, stretch=1)

        # Barre de lancement (fixe en bas)
        page_layout.addWidget(self._build_launch_bar())

        return page

    def _build_launch_bar(self) -> QWidget:
        """Barre fixe avec le bouton principal 'Lancer la simulation'."""
        bar = QWidget()
        bar.setFixedHeight(58)
        bar.setStyleSheet(
            f"background-color: {WHITE}; "
            "border-top: 1px solid #E0ECEB;"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 10, 20, 10)

        info = QLabel("Vérifiez les paramètres recette, puis lancez la simulation.")
        info.setStyleSheet("font-size: 12px; color: #78909C;")
        bl.addWidget(info)
        bl.addStretch()

        self._btn_launch = QPushButton("Lancer la simulation")
        self._btn_launch.setObjectName("BtnPrimary")
        self._btn_launch.setFixedHeight(36)
        self._btn_launch.setMinimumWidth(210)
        self._btn_launch.clicked.connect(self._on_launch_clicked)
        bl.addWidget(self._btn_launch)

        return bar

    def _build_results_tab(self) -> QWidget:
        """
        Onglet "Résultats de simulation".

        Contient :
          - PlotTab (existant — courbe + contrôles + bouton Comparer)
        """
        page = QWidget()
        page.setStyleSheet(f"background-color: {WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        pl.addWidget(self.plot_tab, stretch=1)

        return page

    # ── API publique ──────────────────────────────────────────────────

    def switch_to_results(self) -> None:
        """Bascule directement sur l'onglet Résultats (depuis l'extérieur)."""
        self._tab_widget.setCurrentIndex(1)

    # ── Privé ─────────────────────────────────────────────────────────

    def _on_launch_clicked(self) -> None:
        """Lance le calcul de simulation puis bascule sur l'onglet Résultats."""
        self.plot_tab.refresh_plot()
        self._tab_widget.setCurrentIndex(1)

    def _relay_compare(self, segments: List, recipe_name: str) -> None:
        """
        Intercepte le callback de PlotTab ("Comparer à un cycle réel")
        et le relaie comme signal Qt vers le parent (MainWindow).
        """
        if not segments:
            QMessageBox.warning(
                self,
                "Simulation absente",
                "Lancez d'abord une simulation avant de comparer.",
            )
            return
        self.compare_requested.emit(segments, recipe_name)
