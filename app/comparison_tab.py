"""
Onglet de comparaison cycle simulé vs cycle réel.

Affiche les courbes simulées et réelles côte à côte ou superposées, et calcule
les métriques par interpolation temporelle.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.model.constants import COMPARED_VARS, LEFT_AXIS_VARS, VARIABLES
from app.var_styles import VAR_COLORS, VAR_UNITS

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_PHASE_MAPPING_PATH = _CONFIG_DIR / "phase_mapping.json"
_THRESHOLDS_PATH = _CONFIG_DIR / "comparison_thresholds.json"

try:
    from eto_pdf_extractor import CycleData, CycleStep, extract_cycle_from_pdf
    EXTRACTOR_AVAILABLE = True
    EXTRACTOR_ERROR: Optional[str] = None
except ImportError as _e:
    CycleData = None       # type: ignore[assignment,misc]
    CycleStep = None       # type: ignore[assignment,misc]
    extract_cycle_from_pdf = None  # type: ignore[assignment]
    EXTRACTOR_AVAILABLE = False
    EXTRACTOR_ERROR = str(_e)

_STATUS_FG = {"OK": "#2E7D32", "WARN": "#E65100", "FAIL": "#B71C1C", "—": "#757575"}
_RESULT_TABLE_VARS = ("TT111", "TT112", "RHT121")
_METRIC_STRATEGY = "interpolation"
_PLOT_TITLE_SIZE = 15
_PLOT_LABEL_SIZE = 13
_PLOT_TICK_SIZE = 12
_PLOT_LEGEND_SIZE = 11
_HIDDEN_PLOT_VARS = {"TT191", "GT121"}


class ComparisonTab(QWidget):
    """Onglet de comparaison cycle simulé vs cycle réel."""

    def __init__(self) -> None:
        super().__init__()
        self._sim_segments: List = []
        self._recipe_name: str = ""
        self._real_cycle = None
        self._last_result = None
        self.checkboxes: Dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(18)
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        ctrl = QWidget()
        ctrl.setMaximumWidth(330)
        ctrl.setMinimumHeight(820)
        ctrl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        ctrl_layout = QVBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(0, 0, 4, 0)
        ctrl_layout.setSpacing(14)

        sim_box = QGroupBox("Simulation")
        sim_layout = QVBoxLayout(sim_box)
        self._lbl_sim_status = QLabel("Aucune simulation chargée.")
        self._lbl_sim_status.setWordWrap(True)
        self._lbl_sim_status.setStyleSheet("color: #888;")
        sim_layout.addWidget(self._lbl_sim_status)
        ctrl_layout.addWidget(sim_box)

        real_box = QGroupBox("Cycle réel")
        real_layout = QVBoxLayout(real_box)
        if not EXTRACTOR_AVAILABLE:
            warn_lbl = QLabel(f"eto_pdf_extractor introuvable :\n{EXTRACTOR_ERROR}")
            warn_lbl.setStyleSheet("color: #B22222; font-size: 10px;")
            warn_lbl.setWordWrap(True)
            real_layout.addWidget(warn_lbl)
        self._btn_load_pdf = QPushButton("Importer cycle réel (PDF)…")
        self._btn_load_pdf.clicked.connect(self._load_real_pdf)
        self._btn_load_pdf.setEnabled(EXTRACTOR_AVAILABLE)
        real_layout.addWidget(self._btn_load_pdf)
        self._lbl_real_status = QLabel("Aucun cycle réel chargé.")
        self._lbl_real_status.setWordWrap(True)
        self._lbl_real_status.setStyleSheet("color: #888;")
        real_layout.addWidget(self._lbl_real_status)
        ctrl_layout.addWidget(real_box)

        vars_box = QGroupBox("Variables à afficher")
        vars_box.setObjectName("VariablesBox")
        vars_box.setMinimumHeight(280)
        vars_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        vars_layout = QVBoxLayout(vars_box)
        vars_layout.setContentsMargins(14, 14, 14, 14)
        vars_layout.setSpacing(5)
        for var in VARIABLES:
            if var in _HIDDEN_PLOT_VARS:
                continue
            cb = QCheckBox(f"{var}  ({VAR_UNITS[var]})")
            cb.setMinimumHeight(24)
            cb.setStyleSheet(
                "QCheckBox { spacing: 10px; padding: 2px 0; }"
                "QCheckBox::indicator { width: 16px; height: 16px; }"
            )
            cb.setChecked(var in COMPARED_VARS)
            cb.toggled.connect(self._redraw_if_ready)
            self.checkboxes[var] = cb
            vars_layout.addWidget(cb)
        ctrl_layout.addWidget(vars_box)

        opts_box = QGroupBox("Options")
        opts_box.setMinimumHeight(135)
        opts_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setContentsMargins(14, 18, 14, 14)
        opts_layout.setSpacing(8)
        opts_layout.addWidget(QLabel("Stratégie métrique :"))
        self._combo_strategy = QComboBox()
        self._combo_strategy.addItem("Interpolation temporelle")
        opts_layout.addWidget(self._combo_strategy)
        self._chk_overlay = QCheckBox("Superposer les courbes")
        self._chk_overlay.setChecked(False)
        self._chk_overlay.toggled.connect(self._redraw_if_ready)
        opts_layout.addWidget(self._chk_overlay)
        ctrl_layout.addWidget(opts_box)

        self._btn_compare = QPushButton("Lancer la comparaison")
        self._btn_compare.setEnabled(False)
        self._btn_compare.clicked.connect(self._run_comparison)
        ctrl_layout.addWidget(self._btn_compare)

        align_box = QGroupBox("Alignement / méthode")
        align_layout = QVBoxLayout(align_box)
        self._lbl_alignment = QLabel("—")
        self._lbl_alignment.setWordWrap(True)
        self._lbl_alignment.setStyleSheet("color: #555; font-size: 10px;")
        align_layout.addWidget(self._lbl_alignment)
        ctrl_layout.addWidget(align_box)
        ctrl_layout.addStretch()

        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(13, 5.6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(self.canvas)

        top_splitter.addWidget(ctrl)
        top_splitter.addWidget(plot_widget)
        top_splitter.setSizes([310, 1000])
        top_splitter.setMinimumHeight(700)
        top_splitter.setFixedHeight(700)
        main.addWidget(top_splitter)
        main.addSpacing(72)

        self._result_box = QGroupBox("Critères de comparaison")
        self._result_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._result_box.setStyleSheet("QGroupBox { margin-top: 24px; padding-top: 10px; }")
        result_layout = QVBoxLayout(self._result_box)
        cols = ["Variable", "N points", "RMSE", "MAE", "Biais"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._table.setMinimumHeight(120)
        result_layout.addWidget(self._table)

        bottom_bar = QHBoxLayout()
        self._lbl_duration = QLabel("Durée cycle : —")
        self._lbl_duration.setStyleSheet("font-weight: bold;")
        bottom_bar.addWidget(self._lbl_duration)
        bottom_bar.addStretch()
        self._btn_export = QPushButton("Exporter rapport PDF")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export_report)
        bottom_bar.addWidget(self._btn_export)
        result_layout.addLayout(bottom_bar)
        main.addWidget(self._result_box)
        main.addStretch()
        self._draw_placeholder()

    def _fit_results_table_height(self) -> None:
        header_h = self._table.horizontalHeader().height()
        rows_h = sum(self._table.rowHeight(row) for row in range(self._table.rowCount()))
        frame_h = self._table.frameWidth() * 2
        table_h = header_h + rows_h + frame_h + 6
        self._table.setFixedHeight(max(120, table_h))
        self._table.updateGeometry()
        self._result_box.updateGeometry()
        self.updateGeometry()

    def set_sim_segments(self, segments: List, recipe_name: str = "") -> None:
        self._sim_segments = segments
        self._recipe_name = recipe_name
        self._lbl_sim_status.setText(f"Simulation chargée : {recipe_name or '(sans nom)'}")
        self._lbl_sim_status.setStyleSheet("color: #2E7D32;")
        self._btn_compare.setEnabled(self._real_cycle is not None)

    def _load_real_pdf(self) -> None:
        if not EXTRACTOR_AVAILABLE:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer cycle réel", str(Path.cwd()), "Fichiers cycle (*.pdf *.htm *.html)"
        )
        if not path:
            return
        self._lbl_real_status.setText("Extraction en cours…")
        self._lbl_real_status.setStyleSheet("color: #888;")
        self._btn_load_pdf.setEnabled(False)
        self.repaint()
        try:
            cycle = extract_cycle_from_pdf(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'extraction", f"{type(exc).__name__} : {exc}")
            self._lbl_real_status.setText("Erreur d'extraction.")
            self._lbl_real_status.setStyleSheet("color: #B22222;")
            self._btn_load_pdf.setEnabled(EXTRACTOR_AVAILABLE)
            return
        finally:
            self._btn_load_pdf.setEnabled(EXTRACTOR_AVAILABLE)

        if cycle.is_empty():
            QMessageBox.warning(self, "Extraction vide", "Aucune étape n'a pu être extraite du fichier.")
            self._lbl_real_status.setText("Extraction vide.")
            self._lbl_real_status.setStyleSheet("color: #B22222;")
            return

        self._real_cycle = cycle
        batch = cycle.batch_name or Path(cycle.source_file).stem
        self._lbl_real_status.setText(f"{batch} — {len(cycle.steps)} points, {cycle.total_duration_min:.1f} min")
        self._lbl_real_status.setStyleSheet("color: #2E7D32;")
        self._btn_compare.setEnabled(bool(self._sim_segments))
        if self._sim_segments:
            self._draw_all()

    def _build_sim_continuous_series(self) -> Tuple[List[float], Dict[str, List[float]]]:
        """Reconstruit les courbes simulées continues sur l'axe du temps réel.

        Contrairement à l'ancien affichage, on ne sous-échantillonne plus le
        simulé uniquement aux points du rapport réel. Les courbes restent donc
        visuellement fidèles même si les points de mesure réels sont rares ou
        légèrement déphasés.
        """
        if _METRIC_STRATEGY == "phase_normalized":
            normalized = self._build_phase_normalized_sim_series()
            if normalized is not None:
                return normalized

        from app.analysis import align_origins
        from app.analysis.phase_mapping import load_phase_mapping
        from app.model.sterilization_model import lerp

        mapping = load_phase_mapping(_PHASE_MAPPING_PATH)
        alignment = align_origins(self._sim_segments, self._real_cycle.steps, mapping)
        offset = alignment.dt_offset if alignment and alignment.is_aligned else 0.0

        total_duration = sum(max(0.0, float(seg.duration)) for seg in self._sim_segments)
        series = {var: [] for var in VARIABLES}
        t_axis: List[float] = []
        cur_t = 0.0
        budget = 8000
        min_pts = 6
        max_pts = 180
        extra_budget = max(0, budget - len(self._sim_segments) * min_pts)
        td_safe = max(1e-6, total_duration)

        for seg in self._sim_segments:
            dt = max(0.01, float(seg.duration))
            pts = min(max_pts, max(min_pts, min_pts + int(round((dt / td_safe) * extra_budget))))
            for i in range(pts):
                u = i / (pts - 1) if pts > 1 else 1.0
                t_axis.append(cur_t + u * dt + offset)
                for var in VARIABLES:
                    series[var].append(lerp(seg.start_state[var], seg.end_state[var], u))
            cur_t += dt
        return t_axis, series

    def _build_phase_normalized_sim_series(self) -> Optional[Tuple[List[float], Dict[str, List[float]]]]:
        """Dessine le simulé sur l'axe réel avec un recalage phase par phase.

        Pour les phases sans correspondance dans le simulé (catégorie inconnue
        ou occurrence manquante), l'offset global est utilisé en fallback afin
        de conserver une courbe continue sans plages vides.
        """
        import math as _math
        from app.analysis import align_origins
        from app.analysis.phase_mapping import load_phase_mapping
        from app.analysis.sim_interpolator import SimInterpolator
        from app.analysis.strategies.phase_normalized_strategy import (
            _build_real_phase_blocks,
            _build_sim_phase_blocks,
        )

        mapping = load_phase_mapping(_PHASE_MAPPING_PATH)
        alignment = align_origins(self._sim_segments, self._real_cycle.steps, mapping)
        dt_offset = alignment.dt_offset if alignment and alignment.is_aligned else 0.0

        real_blocks = _build_real_phase_blocks(self._real_cycle.steps, mapping, apply_filter=True)
        sim_blocks = _build_sim_phase_blocks(self._sim_segments, mapping)
        sim_by_key = {(block.category, block.occurrence): block for block in sim_blocks}

        interp = SimInterpolator(self._sim_segments)
        series = {var: [] for var in VARIABLES}
        t_axis: List[float] = []
        total_real = max(1e-6, self._real_cycle.steps[-1].t_min if self._real_cycle.steps else 0.0)
        budget = 8000
        min_pts = 6
        max_pts = 180

        for real_block in real_blocks:
            if real_block.duration <= 0.0:
                continue

            sim_block = sim_by_key.get((real_block.category, real_block.occurrence))
            use_normalized = sim_block is not None and sim_block.duration > 0.0

            if t_axis and not _math.isnan(t_axis[-1]):
                t_axis.append(float("nan"))
                for var in VARIABLES:
                    series[var].append(float("nan"))

            pts = min(
                max_pts,
                max(min_pts, min_pts + int(round((real_block.duration / total_real) * budget))),
            )
            for i in range(pts):
                tau = i / (pts - 1) if pts > 1 else 1.0
                t_real = real_block.t_start + tau * real_block.duration
                if use_normalized:
                    t_sim = sim_block.t_start + tau * sim_block.duration
                else:
                    t_sim = t_real - dt_offset
                values = interp.at(t_sim)
                t_axis.append(t_real)
                for var in VARIABLES:
                    series[var].append(values.get(var, float("nan")))

        if not t_axis:
            return None
        return t_axis, series

    @staticmethod
    def _extract_real_series(steps) -> Dict[str, List[float]]:
        return {
            "PT111":  [s.pt111  for s in steps],
            "PT112":  [s.pt112  for s in steps],
            "TT111":  [s.tt111  for s in steps],
            "TT112":  [s.tt112  for s in steps],
            "TT191":  [s.tt191  for s in steps],
            "RHT121": [s.rht121 for s in steps],
            "GT121":  [s.gt121  for s in steps],
        }

    def _draw_placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "Chargez une simulation et un cycle réel,\npuis cliquez « Lancer la comparaison ».",
            ha="center", va="center", fontsize=11, color="#888", transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    def _redraw_if_ready(self) -> None:
        if self._sim_segments and self._real_cycle is not None:
            self._draw_all()

    def _draw_all(self) -> None:
        if not self._sim_segments or self._real_cycle is None:
            self._draw_placeholder()
            return
        t_sim, sim_series = self._build_sim_continuous_series()
        t_real = [s.t_min for s in self._real_cycle.steps]
        real_series = self._extract_real_series(self._real_cycle.steps)
        selected = [
            v for v, cb in self.checkboxes.items()
            if cb.isChecked() and v not in _HIDDEN_PLOT_VARS
        ]
        batch = self._real_cycle.batch_name or Path(self._real_cycle.source_file).stem

        self.figure.clear()
        if self._chk_overlay.isChecked():
            self._draw_overlay(t_sim, sim_series, t_real, real_series, selected, batch)
        else:
            self._draw_side_by_side(t_sim, sim_series, t_real, real_series, selected, batch)
        self.figure.tight_layout(pad=1.6)
        self.canvas.draw()

    def _draw_overlay(self, t_sim, sim_series, t_real, real_series, selected, batch) -> None:
        ax_l = self.figure.add_subplot(111)
        ax_r = ax_l.twinx()
        for var in selected:
            ax = ax_l if var in LEFT_AXIS_VARS else ax_r
            color = VAR_COLORS.get(var)
            ax.plot(t_sim, sim_series[var], label=f"{var} simulated", color=color, linewidth=1.5)
            ax.plot(t_real, real_series[var], label=f"{var} real", color=color, linewidth=1.5, linestyle="--", alpha=0.75)
        ax_l.set_title(
            f"Overlay - {self._recipe_name or 'simulation'} vs {batch}",
            fontsize=_PLOT_TITLE_SIZE,
            fontweight="bold",
            pad=12,
        )
        self._apply_axis_labels(ax_l, ax_r)
        self._add_legend(ax_l, ax_r)

    def _draw_side_by_side(self, t_sim, sim_series, t_real, real_series, selected, batch) -> None:
        ax_sim_l = self.figure.add_subplot(1, 2, 1)
        ax_sim_r = ax_sim_l.twinx()
        ax_real_l = self.figure.add_subplot(1, 2, 2)
        ax_real_r = ax_real_l.twinx()

        for var in selected:
            color = VAR_COLORS.get(var)
            ax_s = ax_sim_l if var in LEFT_AXIS_VARS else ax_sim_r
            ax_r = ax_real_l if var in LEFT_AXIS_VARS else ax_real_r
            ax_s.plot(t_sim, sim_series[var], label=var, color=color, linewidth=1.5)
            ax_r.plot(t_real, real_series[var], label=var, color=color, linewidth=1.5)

        ax_sim_l.set_title(
            f"Simulated - {self._recipe_name or 'simulation'}\n(aligned continuous curve)",
            fontsize=_PLOT_TITLE_SIZE,
            fontweight="bold",
            pad=12,
        )
        ax_real_l.set_title(
            f"Real - {batch}",
            fontsize=_PLOT_TITLE_SIZE,
            fontweight="bold",
            pad=12,
        )
        for ax_l, ax_r in [(ax_sim_l, ax_sim_r), (ax_real_l, ax_real_r)]:
            self._apply_axis_labels(ax_l, ax_r)
            self._add_legend(ax_l, ax_r)
        self._draw_phase_transitions(ax_sim_l, use_sim=True)
        self._draw_phase_transitions(ax_real_l, use_sim=False)

    @staticmethod
    def _apply_axis_labels(ax_l, ax_r) -> None:
        ax_l.set_xlabel("Aligned real time (min)", fontsize=_PLOT_LABEL_SIZE, labelpad=9)
        ax_l.set_ylabel("Temperature / Humidity (°C / %RH)", fontsize=_PLOT_LABEL_SIZE, labelpad=9)
        ax_l.set_ylim(0, 100)
        ax_r.set_ylabel("Pressure (mbar)", fontsize=_PLOT_LABEL_SIZE, labelpad=9)
        ax_l.tick_params(axis="both", labelsize=_PLOT_TICK_SIZE)
        ax_r.tick_params(axis="both", labelsize=_PLOT_TICK_SIZE)
        ax_l.grid(True, alpha=0.3)

    @staticmethod
    def _add_legend(ax_l, ax_r) -> None:
        lh, ll = ax_l.get_legend_handles_labels()
        rh, rl = ax_r.get_legend_handles_labels()
        if lh + rh:
            ax_l.legend(lh + rh, ll + rl, loc="upper right", fontsize=_PLOT_LEGEND_SIZE, framealpha=0.9)

    def _draw_phase_transitions(self, ax, *, use_sim: bool) -> None:
        if use_sim:
            if _METRIC_STRATEGY == "phase_normalized":
                self._draw_real_phase_transition_lines(ax)
                return
            # Les transitions visuelles du simulé sont tracées dans son axe aligné.
            from app.analysis import align_origins
            from app.analysis.phase_mapping import load_phase_mapping
            mapping = load_phase_mapping(_PHASE_MAPPING_PATH)
            alignment = align_origins(self._sim_segments, self._real_cycle.steps, mapping)
            offset = alignment.dt_offset if alignment and alignment.is_aligned else 0.0
            t = offset
            for seg in self._sim_segments:
                ax.axvline(t, color="#999", linewidth=0.5, alpha=0.25, linestyle="--")
                t += seg.duration
        else:
            self._draw_real_phase_transition_lines(ax)

    def _draw_real_phase_transition_lines(self, ax) -> None:
        prev = None
        for step in self._real_cycle.steps:
            if step.step_name != prev and prev is not None:
                ax.axvline(step.t_min, color="#999", linewidth=0.5, alpha=0.25, linestyle="--")
            prev = step.step_name

    def _run_comparison(self) -> None:
        if not self._sim_segments or self._real_cycle is None:
            QMessageBox.warning(self, "Données manquantes", "Chargez une simulation et un cycle réel avant de comparer.")
            return
        from app.analysis import compare_cycles
        from app.analysis.phase_mapping import load_phase_mapping
        from app.analysis.thresholds import load_thresholds

        try:
            mapping = load_phase_mapping(_PHASE_MAPPING_PATH)
            thresholds = load_thresholds(_THRESHOLDS_PATH)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Configuration manquante", str(exc))
            return

        try:
            result = compare_cycles(
                self._sim_segments, self._real_cycle.steps, mapping, thresholds,
                variables=VARIABLES, strategy=_METRIC_STRATEGY,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de comparaison", f"{type(exc).__name__} : {exc}")
            return
        self._last_result = result
        self._update_alignment_label(result)
        self._update_results_table(result)
        self._btn_export.setEnabled(True)
        self._draw_all()

    def _update_alignment_label(self, result) -> None:
        al = result.alignment
        strategy_label = self._combo_strategy.currentText()
        if al is None or not al.is_aligned:
            self._lbl_alignment.setText(f"Méthode : {strategy_label}\nAucune ancre trouvée.")
        else:
            extra = ""
            if result.strategy == "phase_normalized":
                extra = "\nMétriques : comparaison 0-100 % dans chaque phase."
            self._lbl_alignment.setText(
                f"Méthode : {strategy_label}\n"
                f"Ancre : {al.anchor_category}\n"
                f"Offset visuel : {al.dt_offset:+.1f} min{extra}"
            )

    def _update_results_table(self, result) -> None:
        aggs = result.aggregates
        rows_data: List[Tuple] = []
        for var in _RESULT_TABLE_VARS:
            agg = aggs.get(var)
            unit = VAR_UNITS.get(var, "")
            if agg is None:
                rows_data.append((f"{var} ({unit})", "—", "—", "—", "—"))
            else:
                rows_data.append((
                    f"{var} ({unit})", str(agg.n), f"{agg.rmse:.3f}",
                    f"{agg.mae:.3f}", f"{agg.bias:+.3f}",
                ))
        dur_pct = result.duration_error_ratio * 100
        rows_data.append(("Durée cycle", "—", "—", "—", f"{dur_pct:+.1f} %"))
        self._table.setRowCount(len(rows_data))
        for row_i, row in enumerate(rows_data):
            for col_i, cell in enumerate(row):
                item = QTableWidgetItem(str(cell))
                item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row_i, col_i, item)
        self._table.resizeColumnsToContents()
        self._fit_results_table_height()
        self._lbl_duration.setText(
            f"Durée — Simulé : {result.sim_duration_min:.1f} min  |  "
            f"Réel : {result.real_duration_min:.1f} min  |  "
            f"Écart : {dur_pct:+.1f} %"
        )
        self._lbl_duration.setStyleSheet(
            f"font-weight: bold; color: {_STATUS_FG.get(result.duration_status, '#757575')};"
        )

    def _export_report(self) -> None:
        from app.utils.pdf_report import REPORTLAB_AVAILABLE
        if not REPORTLAB_AVAILABLE:
            QMessageBox.warning(self, "Export PDF indisponible", "Installer : pip install reportlab")
            return
        if self._last_result is None:
            return
        default_fn = f"rapport_comparaison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", str(Path.cwd() / default_fn), "Fichiers PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self._generate_comparison_pdf(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'export", f"Le rapport n'a pas pu être généré.\n\nDétails : {exc}")
            return
        QMessageBox.information(self, "Export terminé", f"Rapport enregistré :\n{path}")

    def _generate_comparison_pdf(self, path: str) -> None:
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        result = self._last_result
        styles = getSampleStyleSheet()
        batch = ""
        if self._real_cycle:
            batch = self._real_cycle.batch_name or Path(self._real_cycle.source_file).stem
        table_data = [["Variable", "N points", "RMSE", "MAE", "Biais"]]
        for var in _RESULT_TABLE_VARS:
            agg = result.aggregates.get(var)
            unit = VAR_UNITS.get(var, "")
            if agg is None:
                table_data.append([f"{var} ({unit})", "—", "—", "—", "—"])
            else:
                table_data.append([
                    f"{var} ({unit})", str(agg.n), f"{agg.rmse:.3f}",
                    f"{agg.mae:.3f}", f"{agg.bias:+.3f}",
                ])
        doc = SimpleDocTemplate(str(Path(path)), pagesize=landscape(A4), leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
        dur_pct = result.duration_error_ratio * 100
        al = result.alignment
        align_info = "—"
        if al and al.is_aligned:
            align_info = f"{al.anchor_category} | offset visuel : {al.dt_offset:+.1f} min"
        strategy_label = self._combo_strategy.currentText()
        story = [
            Paragraph("Rapport de comparaison — Simulé vs Réel", styles["Title"]),
            Spacer(1, 4*mm),
            Paragraph(f"Recette simulée : {escape(self._recipe_name or '—')}", styles["Normal"]),
            Paragraph(f"Cycle réel : {escape(batch or '—')}", styles["Normal"]),
            Paragraph(f"Méthode : {escape(strategy_label)}", styles["Normal"]),
            Paragraph(f"Ancre temporelle : {escape(align_info)}", styles["Normal"]),
            Paragraph(
                f"Durée simulée : {result.sim_duration_min:.1f} min | "
                f"Durée réelle : {result.real_duration_min:.1f} min | "
                f"Écart : {dur_pct:+.1f} %",
                styles["Normal"],
            ),
            Spacer(1, 4*mm),
        ]
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F6C8C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAF2F6")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C7D1")),
        ]
        tbl = Table(table_data, colWidths=[60*mm, 22*mm, 22*mm, 22*mm, 22*mm], repeatRows=1)
        tbl.setStyle(TableStyle(style_cmds))
        story.append(tbl)
        doc.build(story)
