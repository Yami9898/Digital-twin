"""
Palette et feuille de style Qt globale.

Usage :
    from app.ui.styles import GLOBAL_STYLESHEET, PRIMARY, ...
    app.setStyleSheet(GLOBAL_STYLESHEET)

Ne contient aucune logique métier — uniquement des constantes de couleur
et un stylesheet Qt compatible PySide6.
"""

from __future__ import annotations

# ── Palette principale ─────────────────────────────────────────────────────
PRIMARY       = "#009990"   # vert médical
PRIMARY_DARK  = "#007D78"   # vert foncé
PRIMARY_LIGHT = "#E6F4F1"   # vert très clair (backgrounds doux)
BG_MAIN       = "#FAF8F3"   # blanc cassé / fond général
TEXT_MAIN     = "#1F2933"   # texte principal (quasi-noir)
BORDER        = "#D9E2E1"   # gris clair bordures
WHITE         = "#FFFFFF"

# ── Couleurs de statut ─────────────────────────────────────────────────────
#  Clé : (fond, texte)
STATUS_COLORS: dict[str, tuple[str, str]] = {
    "OK":      ("#E8F5E9", "#2E7D32"),
    "WARN":    ("#FFF8E1", "#E65100"),
    "FAIL":    ("#FFEBEE", "#C62828"),
    "NA":      ("#F5F5F5", "#9E9E9E"),
    "PENDING": ("#EDE7F6", "#6A1B9A"),
}

# ── Feuille de style Qt ────────────────────────────────────────────────────
GLOBAL_STYLESHEET = f"""

/* ═══════════════════════════════════════
   BASE
═══════════════════════════════════════ */

QMainWindow, QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_MAIN};
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ═══════════════════════════════════════
   BARRE SUPÉRIEURE
═══════════════════════════════════════ */

QWidget#TopBar {{
    background-color: {PRIMARY_DARK};
    border-bottom: 2px solid #006B66;
}}

/* ═══════════════════════════════════════
   BOUTONS
═══════════════════════════════════════ */

/* Bouton principal (vert plein) */
QPushButton#BtnPrimary {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 22px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.2px;
}}
QPushButton#BtnPrimary:hover {{
    background-color: {PRIMARY_DARK};
}}
QPushButton#BtnPrimary:pressed {{
    background-color: #006060;
}}
QPushButton#BtnPrimary:disabled {{
    background-color: #B2DFDB;
    color: #E0F2F1;
}}

/* Bouton secondaire (contour vert) */
QPushButton#BtnSecondary {{
    background-color: transparent;
    color: {PRIMARY};
    border: 1.5px solid {PRIMARY};
    border-radius: 6px;
    padding: 7px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#BtnSecondary:hover {{
    background-color: {PRIMARY_LIGHT};
}}
QPushButton#BtnSecondary:pressed {{
    background-color: #C0E8E4;
}}
QPushButton#BtnSecondary:disabled {{
    border-color: #B0BEC5;
    color: #B0BEC5;
}}

/* Action destructive (contour rouge) */
QPushButton#BtnDanger {{
    background-color: transparent;
    color: #C62828;
    border: 1.5px solid #C62828;
    border-radius: 6px;
    padding: 7px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#BtnDanger:hover {{
    background-color: #FFEBEE;
}}
QPushButton#BtnDanger:pressed {{
    background-color: #FFCDD2;
}}
QPushButton#BtnDanger:disabled {{
    border-color: #E0B4B4;
    color: #CFA2A2;
}}

/* Action de simulation mise en évidence (contour rouge) */
QPushButton#BtnSimulation {{
    background-color: #FFFFFF;
    color: #C62828;
    border: 1.5px solid #C62828;
    border-radius: 6px;
    padding: 7px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#BtnSimulation:hover {{
    background-color: #FFEBEE;
}}
QPushButton#BtnSimulation:pressed {{
    background-color: #FFCDD2;
}}
QPushButton#BtnSimulation:disabled {{
    border-color: #E0B4B4;
    color: #CFA2A2;
}}

/* Bouton retour (dans la top bar) */
QPushButton#BtnBack {{
    background-color: transparent;
    color: white;
    border: 1px solid rgba(255,255,255,0.40);
    border-radius: 5px;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#BtnBack:hover {{
    background-color: rgba(255,255,255,0.15);
    border-color: rgba(255,255,255,0.7);
}}
QPushButton#BtnBack:pressed {{
    background-color: rgba(255,255,255,0.25);
}}

/* ═══════════════════════════════════════
   CARTES & PANNEAUX
═══════════════════════════════════════ */

/* Carte cliquable de la page d'accueil */
QFrame#HomeCard {{
    background-color: {WHITE};
    border: 1.5px solid {BORDER};
    border-radius: 14px;
}}
QFrame#HomeCard:hover {{
    border-color: {PRIMARY};
    background-color: {PRIMARY_LIGHT};
}}

/* Panneau assistant (placeholder) */
QFrame#AssistantPanel {{
    background-color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin: 6px;
}}

/* Carte résumé / info */
QFrame#SummaryCard {{
    background-color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════
   GROUPBOX
═══════════════════════════════════════ */

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 4px;
    font-weight: 600;
    color: {PRIMARY_DARK};
    background-color: {WHITE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: {PRIMARY_DARK};
}}

/* ═══════════════════════════════════════
   ONGLETS
═══════════════════════════════════════ */

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: 2px solid {PRIMARY};
    background-color: {WHITE};
    border-radius: 0 0 6px 6px;
}}
QTabBar::tab {{
    background-color: #EEF1F0;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 5px 5px 0 0;
    padding: 9px 20px;
    color: #607D8B;
    font-weight: 500;
    min-width: 130px;
}}
QTabBar::tab:selected {{
    background-color: {WHITE};
    color: {PRIMARY_DARK};
    font-weight: 700;
    border-top: 2px solid {PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {PRIMARY_LIGHT};
    color: {PRIMARY_DARK};
}}

/* ═══════════════════════════════════════
   SCROLL
═══════════════════════════════════════ */

QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {BG_MAIN};
    width: 7px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #C8D8D6;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PRIMARY};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background: {BG_MAIN};
    height: 7px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #C8D8D6;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {PRIMARY};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ═══════════════════════════════════════
   CHAMPS DE SAISIE
═══════════════════════════════════════ */

QDoubleSpinBox, QSpinBox {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 3px 7px;
    background-color: {WHITE};
    min-height: 24px;
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {PRIMARY};
    background-color: #FAFFFF;
}}
QDoubleSpinBox:disabled, QSpinBox:disabled {{
    background-color: #F5F5F5;
    color: #AAAAAA;
    border-color: #E0E0E0;
}}

QComboBox {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    background-color: {WHITE};
    min-height: 26px;
}}
QComboBox:focus {{
    border-color: {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    background-color: {WHITE};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {PRIMARY_DARK};
}}

QLineEdit {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    background-color: {WHITE};
}}
QLineEdit:focus {{
    border-color: {PRIMARY};
}}

/* ═══════════════════════════════════════
   CASES À COCHER
═══════════════════════════════════════ */

QCheckBox {{
    spacing: 6px;
    color: {TEXT_MAIN};
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1.5px solid #AAB8B7;
    border-radius: 3px;
    background-color: {WHITE};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {PRIMARY};
}}

/* ═══════════════════════════════════════
   TABLEAU
═══════════════════════════════════════ */

QTableWidget {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {WHITE};
    gridline-color: #EEF0F0;
    alternate-background-color: #F7FAFA;
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY_LIGHT};
    color: {PRIMARY_DARK};
}}
QHeaderView::section {{
    background-color: {PRIMARY_LIGHT};
    color: {PRIMARY_DARK};
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
}}

/* ═══════════════════════════════════════
   SPLITTER
═══════════════════════════════════════ */

QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* ═══════════════════════════════════════
   MESSAGES / LABELS SPÉCIAUX
═══════════════════════════════════════ */

QLabel#SectionTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {PRIMARY_DARK};
}}

QLabel#SubTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT_MAIN};
}}

QLabel#InfoLabel {{
    color: #607D8B;
    font-size: 12px;
}}

/* ═══════════════════════════════════════
   BOUTONS STANDARDS (non objectName)
═══════════════════════════════════════ */

QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: #006060;
}}
QPushButton:disabled {{
    background-color: #B2DFDB;
    color: #E0F2F1;
}}

"""
