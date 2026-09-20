"""
app/ui/calibration_page.py
Page Calibration — calibration versionnée du modèle EtO.

Sections :
  A) Gestion des cycles (import PDF, appariement recette, rôle cal/val)
  B) Lancement de la calibration (bouton + résultats RMSE avant/après)
  C) Historique des instantanés avec activation / retour arrière

Navigation : ajoutée à QStackedWidget (index 3) dans main_window.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.ui.styles import (
    BG_MAIN, BORDER, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT,
    TEXT_MAIN, WHITE,
)
from app.calibration.snapshot_manager import SnapshotManager
from app.calibration.coefficient_store import FACTORY_DEFAULTS

_CALIB_BUTTON_STYLE = f"""
QPushButton {{
    background-color: {WHITE};
    color: {PRIMARY_DARK};
    border: 1.5px solid {PRIMARY};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: {PRIMARY_LIGHT};
    border-color: {PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: #C0E8E4;
}}
QPushButton:disabled {{
    background-color: #F5F7F7;
    color: #A7B5B8;
    border-color: #D3DDDF;
}}
"""

_CALIB_DANGER_STYLE = """
QPushButton {
    background-color: #C62828;
    color: white;
    border: 1.5px solid #B71C1C;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: #B71C1C;
}
QPushButton:pressed {
    background-color: #8E1616;
}
QPushButton:disabled {
    background-color: #E8B9B9;
    color: #FFF5F5;
    border-color: #E0B4B4;
}
"""

_CALIB_PAGE_STYLE = f"""
QWidget {{
    background-color: {BG_MAIN};
}}
QPushButton {{
    background-color: {WHITE};
    color: {PRIMARY_DARK};
    border: 1.5px solid {PRIMARY};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: {PRIMARY_LIGHT};
    border-color: {PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: #C0E8E4;
}}
QPushButton:disabled {{
    background-color: #F5F7F7;
    color: #A7B5B8;
    border-color: #D3DDDF;
}}
QPushButton#BtnPrimary {{
    background-color: {PRIMARY};
    color: {WHITE};
    border: 1.5px solid {PRIMARY_DARK};
}}
QPushButton#BtnPrimary:hover {{
    background-color: {PRIMARY_DARK};
}}
QPushButton#BtnDanger {{
    background-color: #C62828;
    color: {WHITE};
    border: 1.5px solid #B71C1C;
}}
QPushButton#BtnDanger:hover {{
    background-color: #B71C1C;
}}
QPushButton#BtnDanger:pressed {{
    background-color: #8E1616;
}}
QPushButton#BtnDanger:disabled {{
    background-color: #E8B9B9;
    color: #FFF5F5;
    border-color: #E0B4B4;
}}
"""

# Import tardif pour éviter les cycles
# from app.calibration.least_squares_calibrator import LeastSquaresCalibrator
# from eto_pdf_extractor import extract_cycle_from_pdf
# from app.database.recipe_repository import get_all_recipes, get_recipe_by_id


# ── Worker QThread ─────────────────────────────────────────────────────────────

class _CalibrationWorker(QThread):
    """Exécute LeastSquaresCalibrator dans un thread séparé."""

    progress   = Signal(str, int)    # (message, pourcentage 0-100)
    finished   = Signal(object)      # CalibrationResult
    error      = Signal(str)

    def __init__(self, pairs: list, param_names: Optional[List[str]] = None) -> None:
        super().__init__()
        self._pairs       = pairs
        self._param_names = param_names

    def run(self) -> None:
        try:
            from app.calibration.least_squares_calibrator import LeastSquaresCalibrator
            calibrator = LeastSquaresCalibrator(
                self._pairs,
                param_names=self._param_names,
                progress_callback=lambda msg, pct: self.progress.emit(msg, pct),
            )
            result = calibrator.run()
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Ligne de cycle PDF ─────────────────────────────────────────────────────────

class _CycleRow(QWidget):
    """Une rangée de la liste des cycles : PDF | Recette | Rôle | Supprimer."""

    removed = Signal(object)  # self

    def __init__(
        self,
        pdf_path:    str,
        recipes:     List[Tuple[int, str]],    # [(recipe_id, recipe_name), ...]
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pdf_path = pdf_path
        self._cycle_data = None   # chargé à la demande

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Nom du fichier
        name_lbl = QLabel(Path(pdf_path).name)
        name_lbl.setMinimumWidth(180)
        name_lbl.setStyleSheet("font-size: 12px; color: #455A64;")
        layout.addWidget(name_lbl, 3)

        # Appariement recette
        self._recipe_combo = QComboBox()
        self._recipe_combo.setMinimumWidth(200)
        self._recipe_combo.addItem("— sélectionner une recette —", None)
        for rid, rname in recipes:
            self._recipe_combo.addItem(rname, rid)
        layout.addWidget(self._recipe_combo, 4)

        # Rôle calibration / validation
        self._role_combo = QComboBox()
        self._role_combo.addItem("Calibration", "calibration")
        self._role_combo.addItem("Validation",  "validation")
        layout.addWidget(self._role_combo, 2)

        # Bouton supprimer
        btn_remove = QPushButton("✕")
        btn_remove.setFixedSize(26, 26)
        btn_remove.setObjectName("BtnDanger")
        btn_remove.setToolTip("Retirer ce cycle")
        btn_remove.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(btn_remove)

    @property
    def recipe_id(self) -> Optional[int]:
        return self._recipe_combo.currentData()

    @property
    def role(self) -> str:
        return self._role_combo.currentData()

    def cycle_data(self):
        """Charge (et met en cache) les données du PDF."""
        if self._cycle_data is None:
            from eto_pdf_extractor import extract_cycle_from_pdf
            try:
                self._cycle_data = extract_cycle_from_pdf(self.pdf_path)
            except Exception as exc:
                raise RuntimeError(f"Impossible d'extraire {Path(self.pdf_path).name} : {exc}")
        return self._cycle_data


# ── Panneau A+B : Cycles + Calibration ────────────────────────────────────────

class _DataPanel(QWidget):
    """Paneau gauche : liste des cycles + bouton Calibrer + résultats."""

    calibration_done = Signal(object)   # CalibrationResult

    def __init__(self, manager: SnapshotManager, parent=None) -> None:
        super().__init__(parent)
        self._manager  = manager
        self._rows:    List[_CycleRow] = []
        self._recipes: List[Tuple[int, str]] = []
        self._worker:  Optional[_CalibrationWorker] = None

        self._load_recipes()
        self._build_ui()

    def _load_recipes(self) -> None:
        try:
            from app.database.recipe_repository import get_all_recipes
            rows = get_all_recipes()
            self._recipes = [(r["id"], r["name"]) for r in rows]
        except Exception:
            self._recipes = []

    # ── Construction UI ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # ── Section A : Cycles ────────────────────────────────────────
        grp_cycles = QGroupBox("A — Cycles de calibration")
        grp_layout = QVBoxLayout(grp_cycles)
        grp_layout.setSpacing(8)

        # Barre d'outils
        toolbar = QHBoxLayout()
        btn_import = QPushButton("+ Importer des PDF…")
        btn_import.setObjectName("BtnSecondary")
        btn_import.clicked.connect(self._import_pdfs)
        toolbar.addWidget(btn_import)
        toolbar.addStretch()
        lbl_hint = QLabel("Associez chaque rapport PDF à sa recette, puis son rôle.")
        lbl_hint.setStyleSheet("font-size: 11px; color: #78909C;")
        toolbar.addWidget(lbl_hint)
        grp_layout.addLayout(toolbar)

        # En-tête colonne
        header = QHBoxLayout()
        for txt, stretch in [("Rapport PDF", 3), ("Recette", 4), ("Rôle", 2), ("", 0)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {PRIMARY_DARK};"
            )
            header.addWidget(lbl, stretch)
        header.addSpacing(30)
        grp_layout.addLayout(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        grp_layout.addWidget(sep)

        # Zone scrollable des rangées
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(180)
        scroll.setMaximumHeight(300)
        self._rows_container = QWidget()
        self._rows_layout    = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 4, 0, 4)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()
        scroll.setWidget(self._rows_container)
        grp_layout.addWidget(scroll)

        self._empty_lbl = QLabel("Aucun cycle importé. Cliquez sur « Importer des PDF… ».")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("font-size: 12px; color: #90A4AE; padding: 12px;")
        self._rows_layout.insertWidget(0, self._empty_lbl)

        root.addWidget(grp_cycles)

        # ── Section B : Calibration ───────────────────────────────────
        grp_calib = QGroupBox("B — Lancer la calibration")
        grp_calib_layout = QVBoxLayout(grp_calib)
        grp_calib_layout.setSpacing(10)

        btn_row = QHBoxLayout()
        self._btn_calibrate = QPushButton("Calibrer")
        self._btn_calibrate.setObjectName("BtnPrimary")
        self._btn_calibrate.setFixedHeight(36)
        self._btn_calibrate.setMinimumWidth(120)
        self._btn_calibrate.clicked.connect(self._start_calibration)
        btn_row.addWidget(self._btn_calibrate)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(18)
        btn_row.addWidget(self._progress, 1)
        grp_calib_layout.addLayout(btn_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 11px; color: #607D8B;")
        grp_calib_layout.addWidget(self._status_lbl)

        # Tableau résultats RMSE avant/après
        self._result_table = QTableWidget(0, 5)
        self._result_table.setHorizontalHeaderLabels(
            ["Variable", "RMSE avant", "RMSE après", "MAE après", "Amélioration"]
        )
        self._result_table.horizontalHeader().setStretchLastSection(True)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.setMinimumHeight(120)
        self._result_table.setMaximumHeight(180)
        self._result_table.setVisible(False)
        grp_calib_layout.addWidget(self._result_table)

        root.addWidget(grp_calib)
        root.addStretch()

    # ── Import PDF ────────────────────────────────────────────────────

    def _import_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Sélectionner les rapports PDF", "", "Rapports PDF (*.pdf)"
        )
        for path in paths:
            self._add_row(path)

    def _add_row(self, pdf_path: str) -> None:
        row = _CycleRow(pdf_path, self._recipes, self._rows_container)
        row.removed.connect(self._remove_row)
        self._rows_layout.insertWidget(
            self._rows_layout.count() - 1, row
        )
        self._rows.append(row)
        self._update_empty_label()

    def _remove_row(self, row: _CycleRow) -> None:
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        if row in self._rows:
            self._rows.remove(row)
        self._update_empty_label()

    def _update_empty_label(self) -> None:
        self._empty_lbl.setVisible(len(self._rows) == 0)

    # ── Calibration ───────────────────────────────────────────────────

    def _start_calibration(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        # Vérifier appariements
        errors = []
        for row in self._rows:
            if row.recipe_id is None:
                errors.append(f"• {Path(row.pdf_path).name} — aucune recette sélectionnée")
        if errors:
            QMessageBox.warning(
                self, "Appariement incomplet",
                "Veuillez associer une recette à chaque rapport :\n" + "\n".join(errors),
            )
            return

        calib_count = sum(1 for r in self._rows if r.role == "calibration")
        if calib_count == 0:
            QMessageBox.warning(
                self, "Aucun cycle de calibration",
                "Marquez au moins un cycle comme « Calibration ».",
            )
            return

        # Construire les paires (CycleData, recipe_dict, role)
        pairs = []
        for row in self._rows:
            try:
                cycle_data = row.cycle_data()
            except RuntimeError as exc:
                QMessageBox.critical(self, "Erreur PDF", str(exc))
                return

            try:
                from app.database.recipe_repository import get_recipe_by_id
                db_row = get_recipe_by_id(row.recipe_id)
            except Exception as exc:
                QMessageBox.critical(
                    self, "Erreur base de données",
                    f"Impossible de charger la recette : {exc}",
                )
                return

            if db_row is None:
                QMessageBox.critical(
                    self, "Recette introuvable",
                    f"La recette id={row.recipe_id} est introuvable.",
                )
                return

            # get_recipe_by_id retourne le row complet ; SterilizationModel
            # attend uniquement le dict des phases (recipe_data).
            recipe_data = db_row.get("recipe_data")
            if not recipe_data:
                QMessageBox.critical(
                    self, "Recette vide",
                    f"La recette « {db_row.get('name', row.recipe_id)} » "
                    "ne contient pas de données de phases.",
                )
                return

            pairs.append((cycle_data, recipe_data, row.role))

        # Lancer le worker
        self._btn_calibrate.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_lbl.setText("Préparation…")
        self._result_table.setVisible(False)

        self._worker = _CalibrationWorker(pairs)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, message: str, pct: int) -> None:
        self._progress.setValue(pct)
        self._status_lbl.setText(message)

    def _on_finished(self, result) -> None:
        self._btn_calibrate.setEnabled(True)
        self._progress.setVisible(False)

        if not result.success:
            self._status_lbl.setText(f"Calibration incomplète : {result.message}")
        else:
            self._status_lbl.setText(
                f"Calibration terminée — {result.n_evaluations} évaluations, "
                f"coût {result.cost_before:.4f} → {result.cost_after:.4f}"
            )
            self._show_results(result)
            self.calibration_done.emit(result)

    def _on_error(self, message: str) -> None:
        self._btn_calibrate.setEnabled(True)
        self._progress.setVisible(False)
        self._status_lbl.setText(f"Erreur : {message}")
        QMessageBox.critical(self, "Erreur de calibration", message)

    def _show_results(self, result) -> None:
        vars_display = [
            ("TT111",  "Temp. chambre (°C)"),
            ("TT112",  "Temp. enveloppe (°C)"),
            ("RHT121", "Humidité (%)"),
        ]
        self._result_table.setRowCount(len(vars_display))
        for row_idx, (var, label) in enumerate(vars_display):
            m_before = result.metrics_before.get(var)
            m_after  = result.metrics_after.get(var)
            rmse_b   = m_before.rmse if m_before else 0.0
            rmse_a   = m_after.rmse  if m_after  else 0.0
            mae_a    = m_after.mae   if m_after  else 0.0
            pct_impr = (rmse_b - rmse_a) / max(rmse_b, 1e-9) * 100.0

            cells = [
                label,
                f"{rmse_b:.3f}",
                f"{rmse_a:.3f}",
                f"{mae_a:.3f}",
                f"{pct_impr:+.1f} %",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled)
                if col == 4:
                    color = "#2E7D32" if pct_impr > 0 else "#C62828"
                    item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(color))
                self._result_table.setItem(row_idx, col, item)

        self._result_table.resizeColumnsToContents()
        self._result_table.setVisible(True)

    def get_pairs_summary(self) -> List[Dict]:
        """Retourne un résumé des cycles utilisés (pour l'instantané JSON)."""
        summary = []
        for row in self._rows:
            summary.append({
                "pdf":       Path(row.pdf_path).name,
                "recipe_id": row.recipe_id,
                "role":      row.role,
            })
        return summary


# ── Panneau C : Historique ────────────────────────────────────────────────────

class _HistoryPanel(QWidget):
    """Panneau droit : liste des instantanés avec activation."""

    snapshot_activated = Signal()   # indique à la page de rafraîchir
    _RMSE_VARS = ("TT111", "TT112", "RHT121")

    def __init__(self, manager: SnapshotManager, parent=None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        grp = QGroupBox("C — Historique des calibrations")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(8)

        # Tableau des instantanés
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Label", "Date", "Cycles", "RMSE moy."]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(200)
        self._table.itemSelectionChanged.connect(self._update_buttons_state)
        grp_layout.addWidget(self._table)

        # Boutons
        btn_row = QHBoxLayout()
        self._btn_activate = QPushButton("Activer cet instantané")
        self._btn_activate.setStyleSheet(_CALIB_BUTTON_STYLE)
        self._btn_activate.clicked.connect(self._activate_selected)
        btn_row.addWidget(self._btn_activate)

        btn_default = QPushButton("Revenir aux valeurs par défaut")
        btn_default.setStyleSheet(_CALIB_BUTTON_STYLE)
        btn_default.clicked.connect(self._reset_to_default)
        btn_row.addWidget(btn_default)

        self._btn_delete = QPushButton("Supprimer")
        self._btn_delete.setStyleSheet(_CALIB_DANGER_STYLE)
        self._btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self._btn_delete)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setStyleSheet(_CALIB_BUTTON_STYLE)
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        grp_layout.addLayout(btn_row)

        # Indicateur de calibration active
        self._active_lbl = QLabel("")
        self._active_lbl.setStyleSheet(
            f"font-size: 12px; color: {PRIMARY_DARK}; font-weight: 600;"
        )
        grp_layout.addWidget(self._active_lbl)

        root.addWidget(grp)

    def refresh(self) -> None:
        """Recharge la liste depuis le disque."""
        snapshots  = self._manager.list_snapshots()
        active_id  = self._manager.get_active_id()

        self._table.setRowCount(len(snapshots))
        for row_idx, snap in enumerate(snapshots):
            snap_id  = snap.get("id", "")
            is_active = snap_id == active_id

            rmse_str = self._format_mean_rmse(snap.get("metrics", {}))

            n_cycles = len(snap.get("cycles_used", []))
            date_str = snap.get("created_at", "")[:16].replace("T", " ")

            cells = [
                snap_id,
                snap.get("label", ""),
                date_str,
                str(n_cycles),
                rmse_str,
            ]
            for col, text in enumerate(cells):
                cell_text = ("★ " + text) if (col == 0 and is_active) else text
                item = QTableWidgetItem(cell_text)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setData(Qt.UserRole, snap_id)
                if is_active:
                    from PySide6.QtGui import QColor
                    item.setBackground(QColor(PRIMARY_LIGHT))
                self._table.setItem(row_idx, col, item)

        self._table.resizeColumnsToContents()
        active_snap = self._manager.get_snapshot(active_id) or {}
        self._active_lbl.setText(
            f"Calibration active : {active_snap.get('label', active_id)}"
        )
        self._update_buttons_state()

    def _format_mean_rmse(self, metrics: Dict) -> str:
        """RMSE moyenne des métriques de calibration, compatible anciens snapshots."""
        calibration_metrics = metrics.get("calibration") if isinstance(metrics, dict) else {}
        if not isinstance(calibration_metrics, dict):
            calibration_metrics = {}
        metrics_by_var = calibration_metrics or metrics

        rmse_vals = []
        if isinstance(metrics_by_var, dict):
            for var in self._RMSE_VARS:
                metric = metrics_by_var.get(var)
                if isinstance(metric, dict) and isinstance(metric.get("rmse"), (int, float)):
                    rmse_vals.append(float(metric["rmse"]))

        return f"{sum(rmse_vals)/len(rmse_vals):.3f}" if rmse_vals else "—"

    def _selected_id(self) -> Optional[str]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _update_buttons_state(self) -> None:
        snap_id = self._selected_id()
        has_selection = snap_id is not None
        self._btn_activate.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection and snap_id != "default")

    def _activate_selected(self) -> None:
        snap_id = self._selected_id()
        if snap_id is None:
            QMessageBox.information(
                self, "Sélection vide", "Sélectionnez d'abord un instantané dans la liste."
            )
            return
        if self._manager.set_active(snap_id):
            snap = self._manager.get_snapshot(snap_id)
            label = snap.get("label", snap_id) if snap else snap_id
            QMessageBox.information(
                self, "Calibration activée",
                f"L'instantané « {label} » est maintenant actif.\n"
                "Relancez une simulation pour voir les résultats mis à jour.",
            )
            self.refresh()
            self.snapshot_activated.emit()
        else:
            QMessageBox.warning(self, "Erreur", f"Instantané « {snap_id} » introuvable.")

    def _delete_selected(self) -> None:
        snap_id = self._selected_id()
        if snap_id is None:
            QMessageBox.information(
                self, "Sélection vide", "Sélectionnez d'abord une calibration dans la liste."
            )
            return
        if snap_id == "default":
            QMessageBox.warning(
                self, "Suppression impossible",
                "La calibration par défaut ne peut pas être supprimée.",
            )
            return

        snap = self._manager.get_snapshot(snap_id)
        label = snap.get("label", snap_id) if snap else snap_id
        is_active = snap_id == self._manager.get_active_id()
        extra = (
            "\n\nCette calibration est active : le modèle reviendra aux valeurs par défaut."
            if is_active else ""
        )
        reply = QMessageBox.question(
            self,
            "Supprimer la calibration",
            f"Supprimer définitivement « {label} » ?{extra}",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        if self._manager.delete_snapshot(snap_id):
            QMessageBox.information(
                self, "Calibration supprimée",
                f"La calibration « {label} » a été supprimée.",
            )
            self.refresh()
            if is_active:
                self.snapshot_activated.emit()
        else:
            QMessageBox.warning(
                self, "Erreur",
                f"La calibration « {label} » n'a pas pu être supprimée.",
            )

    def _reset_to_default(self) -> None:
        reply = QMessageBox.question(
            self,
            "Revenir aux valeurs par défaut",
            "Revenir aux valeurs usine (signals.py) ?\n"
            "Les instantanés existants ne seront pas supprimés.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            self._manager.reset_to_default()
            QMessageBox.information(
                self, "Valeurs par défaut restaurées",
                "Le modèle utilise maintenant les valeurs usine.\n"
                "Relancez une simulation pour voir les résultats mis à jour.",
            )
            self.refresh()
            self.snapshot_activated.emit()


# ── Page Calibration ──────────────────────────────────────────────────────────

class CalibrationPage(QWidget):
    """
    Page principale de calibration versionnée.

    Intégrée dans MainWindow à l'index 3 du QStackedWidget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._manager = SnapshotManager()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(_CALIB_PAGE_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(18)

        # ── En-tête ───────────────────────────────────────────────────
        header = QVBoxLayout()
        title = QLabel("Calibration versionnée du modèle")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {PRIMARY_DARK};"
        )
        header.addWidget(title)

        subtitle = QLabel(
            "Importez des cycles réels, calibrez les coefficients par moindres carrés "
            "non linéaires, et gérez l'historique des calibrations avec retour arrière."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #546E7A;")
        header.addWidget(subtitle)

        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background: {PRIMARY}; border: none; border-radius: 1px;")
        header.addWidget(sep)
        root.addLayout(header)

        # ── Splitter : Données (gauche) | Historique (droite) ─────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Panneau gauche : A+B
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._data_panel = _DataPanel(self._manager)
        self._data_panel.calibration_done.connect(self._on_calibration_done)
        left_scroll.setWidget(self._data_panel)

        # Panneau droit : C
        self._history_panel = _HistoryPanel(self._manager)
        self._history_panel.snapshot_activated.connect(self._on_snapshot_activated)

        splitter.addWidget(left_scroll)
        splitter.addWidget(self._history_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, stretch=1)

    # ── Connexions inter-panneaux ─────────────────────────────────────

    def _on_calibration_done(self, result) -> None:
        """Sauvegarde l'instantané après une calibration réussie."""
        cycles_summary = self._data_panel.get_pairs_summary()

        # Sérialiser les métriques en dict JSON-compatible
        def _metrics_dict(metrics):
            out = {}
            for var, m in metrics.items():
                out[var] = {"rmse": m.rmse, "mae": m.mae, "bias": m.bias, "n": m.n}
            return out

        metrics_json = {
            "calibration": _metrics_dict(result.metrics_after),
        }
        if result.metrics_valid:
            metrics_json["validation"] = _metrics_dict(result.metrics_valid)

        snap = self._manager.create_snapshot(
            coefficients  = result.coefficients,
            metrics       = metrics_json,
            cycles_used   = cycles_summary,
        )

        # Activer automatiquement la nouvelle calibration
        self._manager.set_active(snap["id"])

        QMessageBox.information(
            self,
            "Calibration sauvegardée",
            f"L'instantané « {snap['label']} » a été créé et activé.\n"
            "Relancez une simulation pour utiliser les nouveaux coefficients.",
        )
        self._history_panel.refresh()

    def _on_snapshot_activated(self) -> None:
        self._history_panel.refresh()

    def refresh_history(self) -> None:
        """Appelé depuis l'extérieur pour forcer un rechargement de l'historique."""
        self._history_panel.refresh()
