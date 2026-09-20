"""
Onglet de tracé du cycle simulé.

Affiche les courbes des 7 variables suivies en fonction du temps,
avec deux axes (gauche : °C/%RH, droite : mbar/kg). Permet l'export
PDF du rapport via ReportLab.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.model.constants import LEFT_AXIS_VARS, VARIABLES
from app.model.sterilization_model import SterilizationModel, lerp
from app.utils.pdf_report import REPORTLAB_AVAILABLE, export_cycle_report_pdf

_HIDDEN_PLOT_VARS = {"TT191", "GT121"}


class PlotTab(QWidget):
    """Onglet de visualisation de la simulation."""

    def __init__(self) -> None:
        super().__init__()
        self.recipe_provider = None
        self.duration_label = QLabel("Durée finale du cycle : --")
        self.phase_count_label = QLabel("Nombre de segments : --")
        self.figure = Figure(figsize=(11, 6))
        self.canvas = FigureCanvas(self.figure)
        self.checkboxes: Dict[str, QCheckBox] = {}
        self._last_segments: List = []
        self._last_total_duration: float = 0.0
        self._last_recipe_name: str = ""
        self._comparison_callback = None
        self._build_ui()

    def _build_ui(self) -> None:
        ml = QVBoxLayout(self)

        # Bandeau info
        ti = QHBoxLayout()
        ti.addWidget(self.duration_label)
        ti.addWidget(self.phase_count_label)
        ti.addStretch()
        ml.addLayout(ti)

        # Splitter : panneau gauche (contrôles) + canvas
        splitter = QSplitter(Qt.Horizontal)

        lp = QWidget()
        ll = QVBoxLayout(lp)
        ll.setSpacing(8)
        adv = QLabel("Conseil : ne pas afficher tous les paramètres en même temps.")
        adv.setWordWrap(True)
        ll.addWidget(adv)
        ll.addWidget(QLabel("Paramètres à afficher"))

        default_checks = [
            ("PT111", True), ("PT112", False), ("TT111", True),
            ("TT112", False), ("RHT121", True),
        ]
        for name, checked in default_checks:
            cb = QCheckBox(name)
            cb.setMinimumHeight(28)
            cb.setStyleSheet(
                "QCheckBox { spacing: 12px; padding: 3px 0; }"
                "QCheckBox::indicator { width: 18px; height: 18px; }"
            )
            cb.setChecked(checked)
            cb.toggled.connect(self._redraw_last_plot)
            self.checkboxes[name] = cb
            ll.addWidget(cb)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Affichage libre",
            "Focus pression",
            "Focus température / humidité",
        ])
        self.mode_combo.currentIndexChanged.connect(self._redraw_last_plot)
        ll.addWidget(QLabel("Mode d'affichage"))
        ll.addWidget(self.mode_combo)

        btn_launch = QPushButton("Lancer la simulation")
        btn_launch.setObjectName("BtnSimulation")
        btn_launch.setFixedHeight(36)
        btn_launch.clicked.connect(self.refresh_plot)
        ll.addWidget(btn_launch)

        btn_report = QPushButton("Générer un rapport PDF")
        btn_report.setObjectName("BtnSecondary")
        btn_report.setFixedHeight(36)
        btn_report.clicked.connect(self.export_pdf_report)
        ll.addWidget(btn_report)

        self._btn_compare = QPushButton("Comparer à un cycle réel")
        self._btn_compare.setObjectName("BtnSecondary")
        self._btn_compare.setFixedHeight(36)
        self._btn_compare.clicked.connect(self._on_compare_clicked)
        ll.addWidget(self._btn_compare)

        ll.addStretch()

        rp = QWidget()
        rl = QVBoxLayout(rp)
        rl.addWidget(self.canvas)

        splitter.addWidget(lp)
        splitter.addWidget(rp)
        splitter.setSizes([260, 950])
        ml.addWidget(splitter)

    # ── API publique ────────────────────────────────────────────────

    def set_recipe_provider(self, provider) -> None:
        """Connecte le fournisseur de recette (RecipeTab)."""
        self.recipe_provider = provider

    def set_comparison_callback(self, callback) -> None:
        """Injecte le callback appelé lors du clic 'Comparer'."""
        self._comparison_callback = callback

    def refresh_plot(self) -> None:
        """Lance la simulation et trace les courbes sélectionnées."""
        if self.recipe_provider is None:
            return
        recipe = self.recipe_provider.get_recipe_data()
        rng = getattr(self.recipe_provider, "get_recipe_name", None)
        recipe_name = rng() if callable(rng) else "Recette sans nom"

        model = SterilizationModel(recipe)
        segments, total_duration = model.simulate()

        # Mémorise pour la comparaison
        self._last_segments = segments
        self._last_total_duration = total_duration
        self._last_recipe_name = recipe_name

        self.duration_label.setText(
            f"Durée finale du cycle : {total_duration:.2f} min "
            f"({total_duration/60.0:.2f} h)"
        )
        self.phase_count_label.setText(f"Nombre de segments : {len(segments)}")

        self._draw_segments(segments, total_duration)

    def _draw_segments(self, segments: List, total_duration: float) -> None:
        """Redessine les courbes à partir d'une simulation déjà calculée."""
        self.figure.clear()
        ax_l = self.figure.add_subplot(111)
        ax_r = ax_l.twinx()

        selected = self._selected_variables()

        # Reconstruction d'une série temporelle continue
        series = {var: {"x": [], "y": []} for var in VARIABLES}
        cur_t = 0.0
        budget = 8000
        ns = max(1, len(segments))
        mn_pts = 8
        mx_pts = 220
        extra_budget = max(0, budget - ns * mn_pts)
        td_safe = max(1e-6, total_duration)

        for seg in segments:
            dt = max(0.01, seg.duration)
            w = dt / td_safe
            pts = min(mx_pts, max(mn_pts, mn_pts + int(round(w * extra_budget))))
            for i in range(pts):
                u = i / (pts - 1) if pts > 1 else 1.0
                t = cur_t + u * dt
                for var in VARIABLES:
                    series[var]["x"].append(t)
                    series[var]["y"].append(
                        lerp(seg.start_state[var], seg.end_state[var], u))
            cur_t += dt

        for var in selected:
            ax = ax_l if var in LEFT_AXIS_VARS else ax_r
            ax.plot(series[var]["x"], series[var]["y"], label=var)

        # Lignes verticales aux transitions
        el = 0.0
        for seg in segments:
            ax_l.axvline(el, linewidth=0.6, alpha=0.25)
            el += seg.duration
        ax_l.axvline(total_duration, linewidth=0.6, alpha=0.25)

        ax_l.set_title("Cycle simulé en fonction du temps")
        ax_l.set_xlabel("Temps (min)")
        ax_l.set_ylabel("%RH / °C")
        ax_l.set_ylim(0, 100)
        ax_r.set_ylabel("mbar")
        ax_l.grid(True, alpha=0.3)

        lh, ll2 = ax_l.get_legend_handles_labels()
        rh, rl2 = ax_r.get_legend_handles_labels()
        if lh + rh:
            ax_l.legend(lh + rh, ll2 + rl2, loc="upper right")

        self.figure.tight_layout()
        self.canvas.draw()

    def export_pdf_report(self) -> None:
        """Exporte un PDF récapitulatif de la simulation courante."""
        if self.recipe_provider is None:
            return
        if not REPORTLAB_AVAILABLE:
            QMessageBox.warning(
                self, "Export PDF indisponible",
                "La bibliothèque Python 'reportlab' est requise.\n"
                "Installer avec : pip install reportlab"
            )
            return

        recipe = self.recipe_provider.get_recipe_data()
        rng = getattr(self.recipe_provider, "get_recipe_name", None)
        recipe_name = rng() if callable(rng) else "Recette sans nom"

        model = SterilizationModel(recipe)
        segments, total_duration = model.simulate()

        default_fn = (
            f"rapport_cycle_simule_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport PDF",
            str(Path.cwd() / default_fn), "Fichiers PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:
            export_cycle_report_pdf(
                pdf_path=path, recipe_name=recipe_name,
                segments=segments, total_duration=total_duration,
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Erreur d'export PDF",
                f"Le rapport PDF n'a pas pu être généré.\n\nDétails : {exc}"
            )
            return

        QMessageBox.information(
            self, "Export PDF terminé",
            f"Le rapport a été enregistré ici :\n{path}"
        )

    def _on_compare_clicked(self) -> None:
        """Bascule vers l'onglet Comparaison avec la recette courante."""
        if self.recipe_provider is not None:
            self.refresh_plot()

        if not self._last_segments:
            QMessageBox.warning(
                self,
                "Simulation absente",
                "La simulation n'a pas pu être lancée.",
            )
            return
        if self._comparison_callback is not None:
            self._comparison_callback(self._last_segments, self._last_recipe_name)

    # ── Privé ───────────────────────────────────────────────────────

    def _redraw_last_plot(self, *_) -> None:
        """Actualise seulement l'affichage des variables sélectionnées."""
        if not self._last_segments:
            return
        self._draw_segments(self._last_segments, self._last_total_duration)

    def _selected_variables(self) -> List[str]:
        mode = self.mode_combo.currentText()
        if mode == "Focus pression":
            return ["PT111", "PT112"]
        if mode == "Focus température / humidité":
            return ["TT111", "TT112", "RHT121"]
        return [
            n for n, cb in self.checkboxes.items()
            if cb.isChecked() and n not in _HIDDEN_PLOT_VARS
        ]
