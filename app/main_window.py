"""
Fenêtre principale — nouvelle architecture de navigation.

Structure :
  QMainWindow
  └── QWidget central
       ├── TopBar (fixe, 48 px)  — titre de l'application + bouton retour accueil
       └── QStackedWidget
            ├── index 0 : HomePage         (page d'accueil)
            ├── index 1 : SimulationPage   (section Simuler un cycle)
            └── index 2 : AnalysisPage     (section Analyser un cycle réel)

Navigation :
  HomePage  →  clic carte Simuler       →  SimulationPage
  HomePage  →  clic carte Analyser      →  AnalysisPage
  SimulationPage → "Comparer à un cycle réel"    →  AnalysisPage
  TopBar    →  bouton "← Accueil"       →  HomePage (depuis n'importe quelle page)

RÈGLE : Ce fichier gère uniquement la navigation et l'assemblage.
Toute la logique métier reste dans les couches existantes.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QMainWindow,
)

from app.ui.analysis_page import AnalysisPage
from app.ui.calibration_page import CalibrationPage
from app.ui.home_page import HomePage
from app.ui.simulation_page import SimulationPage
from app.ui.styles import PRIMARY_DARK

# Index des pages dans le QStackedWidget
_PAGE_HOME        = 0
_PAGE_SIM         = 1
_PAGE_ANALYSIS    = 2
_PAGE_CALIBRATION = 3


class MainWindow(QMainWindow):
    """Fenêtre principale — orchestre la navigation entre les trois pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Digital Twin EtO")
        self.resize(1280, 850)
        self.setMinimumSize(900, 600)
        self._build_ui()

    # ── Construction de l'interface ───────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("MainContent")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barre supérieure fixe
        self._top_bar = self._build_top_bar()
        root.addWidget(self._top_bar)

        # Pile de pages
        self._stack = QStackedWidget()

        self._home_page        = HomePage()
        self._sim_page         = SimulationPage()
        self._analysis_page    = AnalysisPage()
        self._calibration_page = CalibrationPage()

        self._stack.addWidget(self._home_page)           # 0
        self._stack.addWidget(self._sim_page)            # 1
        self._stack.addWidget(self._analysis_page)       # 2
        self._stack.addWidget(self._calibration_page)    # 3

        root.addWidget(self._stack, stretch=1)

        # ── Connexions des signaux ────────────────────────────────────
        self._home_page.simulate_clicked.connect(self._go_simulation)
        self._home_page.analyze_clicked.connect(self._go_analysis)
        self._home_page.calibrate_clicked.connect(self._go_calibration)
        self._sim_page.compare_requested.connect(self._open_comparison)

        # Affichage initial : accueil
        self._navigate_to(_PAGE_HOME)

        # Calcul de la simulation de départ (chargement en arrière-plan)
        # identique à l'ancien comportement de MainWindow
        self._sim_page.plot_tab.refresh_plot()

    def _build_top_bar(self) -> QWidget:
        """Barre de navigation supérieure (titre + bouton retour accueil)."""
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(48)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(16)

        # ── Nom de l'application ──────────────────────────────────────
        app_name = QLabel("Digital Twin EtO")
        app_name.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: white; "
            "letter-spacing: 0.3px; background: transparent;"
        )
        layout.addWidget(app_name)
        layout.addStretch()

        # ── Indicateur de page courante ───────────────────────────────
        self._lbl_breadcrumb = QLabel("")
        self._lbl_breadcrumb.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 12px; background: transparent;"
        )
        layout.addWidget(self._lbl_breadcrumb)

        # ── Bouton retour accueil ─────────────────────────────────────
        self._btn_back = QPushButton("Accueil")
        self._btn_back.setObjectName("BtnBack")
        self._btn_back.setFixedHeight(30)
        self._btn_back.clicked.connect(self._go_home)
        layout.addWidget(self._btn_back)

        return bar

    # ── Navigation ────────────────────────────────────────────────────

    def _navigate_to(self, page_index: int) -> None:
        """Change la page active et met à jour la barre supérieure."""
        self._stack.setCurrentIndex(page_index)

        labels = {
            _PAGE_HOME:        ("", False),
            _PAGE_SIM:         ("Simuler un cycle", True),
            _PAGE_ANALYSIS:    ("Analyser un cycle réel", True),
            _PAGE_CALIBRATION: ("Calibration", True),
        }
        breadcrumb, show_back = labels.get(page_index, ("", True))
        self._lbl_breadcrumb.setText(breadcrumb)
        self._btn_back.setVisible(show_back)

    def _go_home(self) -> None:
        self._navigate_to(_PAGE_HOME)

    def _go_simulation(self) -> None:
        self._navigate_to(_PAGE_SIM)

    def _go_analysis(self) -> None:
        self._navigate_to(_PAGE_ANALYSIS)

    def _go_calibration(self) -> None:
        self._calibration_page.refresh_history()
        self._navigate_to(_PAGE_CALIBRATION)

    def _open_comparison(self, segments: List, recipe_name: str) -> None:
        """
        Reçoit la demande de comparaison depuis SimulationPage,
        transmet les segments à AnalysisPage et bascule sur cette page.
        """
        self._analysis_page.set_sim_segments(segments, recipe_name)
        self._navigate_to(_PAGE_ANALYSIS)
