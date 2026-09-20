"""
Onglet d'import et de visualisation d'un cycle réel extrait d'un PDF.

Délègue l'extraction au module `eto_pdf_extractor` (déjà existant).
Cet onglet ne fait que :
  1. Choisir un fichier PDF
  2. Appeler extract_cycle_from_pdf()
  3. Afficher les métadonnées + statistiques d'extraction
  4. Tracer les courbes des 3 variables actuellement comparées
     (PT111, TT112, RHT121) — extensible aux 4 autres via les
     cases à cocher

Expose à `AnalysisTab` (à venir) :
  - get_real_cycle() → CycleData | None
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.model.constants import COMPARED_VARS, LEFT_AXIS_VARS
from app.var_styles import VAR_COLORS, VAR_UNITS

_HIDDEN_PLOT_VARS = {"TT191", "GT121"}

# Import direct de l'extracteur (même dossier que main.py)
try:
    from eto_pdf_extractor import (
        CycleData,
        CycleStep,
        extract_cycle_from_pdf,
    )
    EXTRACTOR_AVAILABLE = True
    EXTRACTOR_ERROR: Optional[str] = None
except ImportError as e:
    CycleData = None  # type: ignore
    CycleStep = None  # type: ignore
    extract_cycle_from_pdf = None  # type: ignore
    EXTRACTOR_AVAILABLE = False
    EXTRACTOR_ERROR = str(e)


class RealCycleTab(QWidget):
    """Onglet de chargement et visualisation d'un cycle réel."""

    def __init__(self) -> None:
        super().__init__()
        self.cycle: Optional["CycleData"] = None
        self.checkboxes: Dict[str, QCheckBox] = {}
        self._build_ui()

    # ── Construction UI ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)

        # Avertissement si l'extracteur n'est pas dispo
        if not EXTRACTOR_AVAILABLE:
            warn = QLabel(
                f"Module eto_pdf_extractor introuvable : {EXTRACTOR_ERROR}\n"
                "Placer eto_pdf_extractor.py à côté de main.py."
            )
            warn.setStyleSheet("color: #B22222; padding: 8px;")
            warn.setWordWrap(True)
            main.addWidget(warn)

        # Bandeau du haut : bouton + statut
        top = QHBoxLayout()
        self.btn_load = QPushButton("Charger un PDF de cycle réel…")
        self.btn_load.clicked.connect(self.load_pdf)
        self.btn_load.setEnabled(EXTRACTOR_AVAILABLE)
        top.addWidget(self.btn_load)

        self.status_label = QLabel("Aucun PDF chargé.")
        self.status_label.setStyleSheet("color: #555; padding-left: 12px;")
        top.addWidget(self.status_label)
        top.addStretch()
        main.addLayout(top)

        # Splitter horizontal : métadonnées+contrôles à gauche, graphe à droite
        splitter = QSplitter(Qt.Horizontal)

        # ── Panneau gauche : métadonnées + variables ────────────────
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Métadonnées extraites
        self.meta_box = QGroupBox("Informations du cycle")
        self.meta_form = QFormLayout(self.meta_box)
        self.meta_labels = {
            "fichier":  QLabel("—"),
            "lot":      QLabel("—"),
            "recette":  QLabel("—"),
            "equip":    QLabel("—"),
            "debut":    QLabel("—"),
            "duree":    QLabel("—"),
            "points":   QLabel("—"),
            "type_pdf": QLabel("—"),
        }
        for lbl in self.meta_labels.values():
            lbl.setStyleSheet("color: #222;")
        self.meta_form.addRow("Fichier :", self.meta_labels["fichier"])
        self.meta_form.addRow("Lot :", self.meta_labels["lot"])
        self.meta_form.addRow("Recette :", self.meta_labels["recette"])
        self.meta_form.addRow("Équipement :", self.meta_labels["equip"])
        self.meta_form.addRow("Début :", self.meta_labels["debut"])
        self.meta_form.addRow("Durée :", self.meta_labels["duree"])
        self.meta_form.addRow("Points :", self.meta_labels["points"])
        self.meta_form.addRow("Type PDF :", self.meta_labels["type_pdf"])
        left_layout.addWidget(self.meta_box)

        # Variables affichables
        vars_box = QGroupBox("Variables à afficher")
        vars_layout = QVBoxLayout(vars_box)
        hint = QLabel(
            "Variables actuellement comparées sim/réel : "
            f"{', '.join(COMPARED_VARS)}.\nLes autres sont disponibles "
            "pour visualisation."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 11px;")
        vars_layout.addWidget(hint)

        all_vars = ["PT111", "PT112", "TT111", "TT112", "TT191", "RHT121", "GT121"]
        for var in all_vars:
            if var in _HIDDEN_PLOT_VARS:
                continue
            cb = QCheckBox(f"{var}  ({VAR_UNITS[var]})")
            cb.setChecked(var in COMPARED_VARS)
            cb.toggled.connect(self._redraw_if_loaded)
            self.checkboxes[var] = cb
            vars_layout.addWidget(cb)
        left_layout.addWidget(vars_box)

        left_layout.addStretch()

        # ── Panneau droit : canvas matplotlib ───────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.canvas)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([320, 900])
        main.addWidget(splitter)

        self._draw_placeholder()

    # ── Chargement / extraction ─────────────────────────────────────

    def load_pdf(self) -> None:
        """Ouvre un dialogue de sélection puis lance l'extraction."""
        if not EXTRACTOR_AVAILABLE:
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Charger PDF cycle réel",
            str(Path.cwd()), "Fichiers PDF (*.pdf)"
        )
        if not path:
            return

        # Indicateur de progression sommaire (extraction OCR peut être longue)
        self.status_label.setText("Extraction en cours…")
        self.status_label.setStyleSheet("color: #888; padding-left: 12px;")
        self.btn_load.setEnabled(False)
        self.repaint()  # force le rafraîchissement de l'UI

        try:
            cycle = extract_cycle_from_pdf(path)
        except FileNotFoundError as e:
            self._show_error("Fichier introuvable", str(e))
            return
        except RuntimeError as e:
            # Typiquement : OCR demandé mais pytesseract non installé
            self._show_error("Erreur d'extraction", str(e))
            return
        except Exception as e:
            self._show_error(
                "Erreur inattendue lors de l'extraction",
                f"{type(e).__name__} : {e}"
            )
            return
        finally:
            self.btn_load.setEnabled(EXTRACTOR_AVAILABLE)

        if cycle.is_empty():
            self._show_error(
                "Extraction vide",
                "Aucune étape n'a pu être extraite du PDF.\n"
                "Vérifier que le fichier contient bien un tableau "
                "'Étapes de cycle' au format attendu."
            )
            self.status_label.setText("Extraction vide.")
            self.status_label.setStyleSheet("color: #B22222; padding-left: 12px;")
            return

        # Tout est OK : on stocke et on rafraîchit
        self.cycle = cycle
        self._populate_metadata(cycle)
        self._draw_curves()

        n = len(cycle.steps)
        self.status_label.setText(
            f"Cycle chargé — {n} points extraits, "
            f"{cycle.total_duration_min:.1f} min."
        )
        self.status_label.setStyleSheet("color: #2E7D32; padding-left: 12px;")

    # ── API publique ────────────────────────────────────────────────

    def get_real_cycle(self):
        """Retourne le CycleData courant (ou None si rien de chargé).
        Utilisé par AnalysisTab pour la comparaison sim vs réel."""
        return self.cycle

    # ── Privé : affichage métadonnées ───────────────────────────────

    def _populate_metadata(self, cycle) -> None:
        """Remplit le formulaire de métadonnées à partir du CycleData."""
        path = Path(cycle.source_file)
        self.meta_labels["fichier"].setText(path.name)
        self.meta_labels["lot"].setText(cycle.batch_name or "—")
        self.meta_labels["recette"].setText(cycle.recipe_name or "—")
        self.meta_labels["equip"].setText(cycle.equipment or "—")

        if cycle.start_time:
            self.meta_labels["debut"].setText(
                cycle.start_time.strftime("%d/%m/%Y %H:%M:%S"))
        else:
            self.meta_labels["debut"].setText("—")

        self.meta_labels["duree"].setText(
            f"{cycle.total_duration_min:.1f} min  "
            f"({cycle.total_duration_min/60.0:.2f} h)"
        )
        self.meta_labels["points"].setText(f"{len(cycle.steps)} mesures")

        pdf_type = getattr(cycle, "pdf_type", "?")
        type_str = {
            "text": "texte natif (extraction directe)",
            "scanned": "scanné (OCR)",
        }.get(pdf_type, pdf_type)
        self.meta_labels["type_pdf"].setText(type_str)

    # ── Privé : tracé ───────────────────────────────────────────────

    def _draw_placeholder(self) -> None:
        """Dessine un message vide tant qu'aucun PDF n'est chargé."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5,
                "Charger un PDF pour visualiser le cycle réel",
                ha="center", va="center",
                fontsize=12, color="#888",
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    def _redraw_if_loaded(self) -> None:
        """Redessine si un cycle est chargé (appelé sur toggle de checkbox)."""
        if self.cycle is not None:
            self._draw_curves()

    def _draw_curves(self) -> None:
        """Trace les courbes des variables cochées + marqueurs de phases."""
        if self.cycle is None or not self.cycle.steps:
            self._draw_placeholder()
            return

        # Variables actuellement cochées
        selected = [
            v for v, cb in self.checkboxes.items()
            if cb.isChecked() and v not in _HIDDEN_PLOT_VARS
        ]
        if not selected:
            self._draw_placeholder()
            return

        # Extraction des séries temporelles
        t = [s.t_min for s in self.cycle.steps]
        series = self._extract_series(self.cycle.steps)

        self.figure.clear()
        ax_l = self.figure.add_subplot(111)
        ax_r = ax_l.twinx()

        for var in selected:
            ax = ax_l if var in LEFT_AXIS_VARS else ax_r
            ax.plot(t, series[var], label=var,
                    color=VAR_COLORS.get(var), linewidth=1.4)

        # Marqueurs verticaux aux transitions de phases (changement de step_name)
        self._draw_phase_transitions(ax_l)

        # Mise en forme
        ax_l.set_title(
            f"Cycle réel — {self.cycle.batch_name or Path(self.cycle.source_file).stem}",
            fontsize=11,
        )
        ax_l.set_xlabel("Temps (min)")
        ax_l.set_ylabel("°C / %RH")
        ax_r.set_ylabel("mbar")
        ax_l.grid(True, alpha=0.3)

        # Légende combinée (gauche + droite)
        lh, ll = ax_l.get_legend_handles_labels()
        rh, rl = ax_r.get_legend_handles_labels()
        if lh + rh:
            ax_l.legend(lh + rh, ll + rl, loc="upper right",
                        fontsize=9, framealpha=0.9)

        self.figure.tight_layout()
        self.canvas.draw()

    @staticmethod
    def _extract_series(steps) -> Dict[str, List[float]]:
        """Convertit la liste de CycleStep en dictionnaire de séries."""
        return {
            "PT111":  [s.pt111  for s in steps],
            "PT112":  [s.pt112  for s in steps],
            "TT111":  [s.tt111  for s in steps],
            "TT112":  [s.tt112  for s in steps],
            "TT191":  [s.tt191  for s in steps],
            "RHT121": [s.rht121 for s in steps],
            "GT121":  [s.gt121  for s in steps],
        }

    def _draw_phase_transitions(self, ax) -> None:
        """Trace des lignes verticales aux changements d'étape."""
        if not self.cycle or not self.cycle.steps:
            return
        prev_name = None
        for s in self.cycle.steps:
            if s.step_name != prev_name and prev_name is not None:
                ax.axvline(s.t_min, color="#999", linewidth=0.5,
                           alpha=0.4, linestyle="--")
            prev_name = s.step_name

    # ── Privé : gestion d'erreurs ───────────────────────────────────

    def _show_error(self, title: str, message: str) -> None:
        """Affiche un QMessageBox et met à jour le statut."""
        QMessageBox.critical(self, title, message)
        self.status_label.setText(title)
        self.status_label.setStyleSheet("color: #B22222; padding-left: 12px;")
