"""
app/guide/guide_widget.py
Aurora Process Navigator — module d'exploration du cycle EtO.

Ce widget constitue le module guide intégré à la page de simulation.
Identité visuelle propre (palette Aurora : indigo / violet / cyan) distincte
du vert principal de l'application principale.

Ce widget est 100 % local et hors ligne. Aucune API, aucun service externe.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from app.guide.guide_content import NODES, PHASES_ORDER
from app.guide.guide_engine import GuideEngine
from app.guide.guide_style import (
    AMBER_SOFT, BLUE_LIGHT, BORDER, CAUTION_BG, CAUTION_TEXT,
    CYAN_BRIGHT, GUIDE_BG, IMPACT_AUG_AC, IMPACT_AUG_BG, IMPACT_DIM_AC,
    IMPACT_DIM_BG, IMPACT_SUP_AC, IMPACT_SUP_BG, INDIGO_DEEP,
    LAYER_COMPARAISON, LAYER_GRAFCET, LAYER_PHYSIQUE, LAYER_RECETTE,
    LAYER_SIGNAUX, LAVENDER, MISSION_DT, MISSION_PROCESSUS, MISSION_RECETTE,
    MISSION_VIGILANCE, PARAMS_BG, RETENIR_ACC, RETENIR_BG, ROLE_BG,
    SIGNALS_BG, TEXT, VIOLET_SOFT, WHITE,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _lighten(hex_color: str, amount: float) -> str:
    """Retourne une version claire de hex_color mélangée avec du blanc."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02X}{:02X}{:02X}".format(
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
    )


# ── Constantes ────────────────────────────────────────────────────────────────
_LAYER_COURBES = "#26C6DA"

_MISSION_ACCENT: dict[str, str] = {
    "processus_eto": MISSION_PROCESSUS,
    "vigilance":     MISSION_VIGILANCE,
    "aide_recette":  MISSION_RECETTE,
    "digital_twin":  MISSION_DT,
}

_DT_ARCH_LAYERS = [
    {"label": "Recette",                   "color": LAYER_RECETTE,     "target": "dt_couche_recette"},
    {"label": "GRAFCET / séquencement",    "color": LAYER_GRAFCET,     "target": "dt_couche_grafcet"},
    {"label": "Couche physique",           "color": LAYER_PHYSIQUE,    "target": "dt_couche_physique"},
    {"label": "Couche signaux",            "color": LAYER_SIGNAUX,     "target": "dt_couche_signaux"},
    {"label": "Courbes simulées",          "color": _LAYER_COURBES,    "target": "dt_sim_theorique"},
    {"label": "Comparaison réel / simulé", "color": LAYER_COMPARAISON, "target": "dt_comparaison"},
]


# ════════════════════════════════════════════════════════════════════════════
# Sous-composants
# ════════════════════════════════════════════════════════════════════════════

class _AuroraHeader(QFrame):
    """Header du guide interactif local."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(94)
        self.setObjectName("GuideHeader")
        self.setStyleSheet(
            f"QFrame#GuideHeader {{ background-color: {INDIGO_DEEP}; "
            f"border: none; border-radius: 12px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 9)
        cl.setSpacing(3)

        title = QLabel("Guide de simulation")
        title.setStyleSheet(
            "color: white; font-size: 15px; font-weight: 700; background: transparent;"
        )
        cl.addWidget(title)

        subtitle = QLabel("Explorez le cycle EtO, les phases et le digital twin.")
        subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.84); font-size: 10px; background: transparent;"
        )
        cl.addWidget(subtitle)

        status = QLabel("Guide local — sans modification de recette")
        status.setStyleSheet(
            "color: rgba(255,255,255,0.68); font-size: 9px; background: transparent;"
        )
        cl.addWidget(status)

        outer.addWidget(content, stretch=1)

        accent_line = QWidget()
        accent_line.setFixedHeight(3)
        accent_line.setStyleSheet(f"background-color: {CYAN_BRIGHT};")
        outer.addWidget(accent_line)


class _MissionCard(QFrame):
    """Carte de mission — bande colorée gauche, badge, titre, description."""

    def __init__(self, title: str, description: str, badge: str,
                 accent: str, callback: Callable, parent=None) -> None:
        super().__init__(parent)
        self._callback = callback
        hover_bg = _lighten(accent, 0.92)
        self.setObjectName("MissionCard")
        self._normal = (
            f"QFrame#MissionCard {{ background-color: {WHITE}; border: none; border-radius: 10px; }}"
        )
        self._hover = (
            f"QFrame#MissionCard {{ background-color: {hover_bg}; border: none; border-radius: 10px; }}"
        )
        self.setStyleSheet(self._normal)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        band = QWidget()
        band.setFixedWidth(5)
        band.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        band.setObjectName("missionBand")
        band.setStyleSheet(
            f"QWidget#missionBand {{ background-color: {accent}; "
            f"border-top-left-radius: 9px; border-bottom-left-radius: 9px; }}"
        )
        outer.addWidget(band)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.setContentsMargins(0, 0, 0, 0)

        bdg = QLabel(badge.upper())
        bdg.setStyleSheet(
            f"background-color: {accent}; color: white; border-radius: 8px; "
            f"padding: 2px 7px; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;"
        )
        bdg.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(bdg)
        top.addStretch()

        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"color: {accent}; font-size: 18px; font-weight: 700; background: transparent;"
        )
        top.addWidget(arrow)
        cl.addLayout(top)

        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {TEXT}; background: transparent;"
        )
        cl.addWidget(t)

        if description:
            d = QLabel(description)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 10px; color: #5F6B7C; background: transparent;")
            cl.addWidget(d)

        outer.addWidget(content, stretch=1)

    def enterEvent(self, event) -> None:
        self.setStyleSheet(self._hover)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(self._normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._callback()
        super().mousePressEvent(event)


class _PhaseNavCard(QFrame):
    """Carte de navigation simple pour les menus génériques."""

    def __init__(self, title: str, description: str, badge: str,
                 callback: Callable, parent=None) -> None:
        super().__init__(parent)
        self._callback = callback
        self.setObjectName("PhaseNavCard")
        self._normal = (
            f"QFrame#PhaseNavCard {{ background-color: {WHITE}; border: none; border-radius: 8px; }}"
        )
        self._hover = (
            f"QFrame#PhaseNavCard {{ background-color: {LAVENDER}; border: none; border-radius: 8px; }}"
        )
        self.setStyleSheet(self._normal)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.setContentsMargins(0, 0, 0, 0)

        bdg = QLabel(badge)
        bdg.setStyleSheet(
            f"background-color: {LAVENDER}; color: {INDIGO_DEEP}; "
            f"border-radius: 7px; padding: 1px 7px; font-size: 9px; font-weight: 600;"
        )
        bdg.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(bdg)
        top.addStretch()

        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"color: {VIOLET_SOFT}; font-size: 16px; font-weight: 700; background: transparent;"
        )
        top.addWidget(arrow)
        layout.addLayout(top)

        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT}; background: transparent;"
        )
        layout.addWidget(t)

        if description:
            d = QLabel(description)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 10px; color: #5F6B7C; background: transparent;")
            layout.addWidget(d)

    def enterEvent(self, event) -> None:
        self.setStyleSheet(self._hover)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(self._normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._callback()
        super().mousePressEvent(event)


class _OrbitalTimeline(QWidget):
    """Frise uniforme et cliquable des phases du cycle EtO."""

    def __init__(self, navigate_callback: Callable, parent=None) -> None:
        super().__init__(parent)
        self._navigate = navigate_callback
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        for i, phase in enumerate(PHASES_ORDER):
            layout.addWidget(
                self._make_row(i + 1, phase, is_last=(i == len(PHASES_ORDER) - 1))
            )

    def _make_row(self, number: int, phase: dict, is_last: bool) -> QWidget:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h = QHBoxLayout(container)
        h.setContentsMargins(4, 0, 0, 0)
        h.setSpacing(0)

        # Colonne gauche : pastille + connecteur
        left = QWidget()
        left.setFixedWidth(32)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        lv.setAlignment(Qt.AlignHCenter)

        circle = QLabel(f"{number:02d}")
        circle.setFixedSize(26, 26)
        circle.setAlignment(Qt.AlignCenter)
        circle.setStyleSheet(
            f"background-color: {INDIGO_DEEP}; color: {WHITE}; "
            f"border: 2px solid {CYAN_BRIGHT}; border-radius: 13px; "
            f"font-size: 9px; font-weight: 700;"
        )
        lv.addWidget(circle, 0, Qt.AlignHCenter)

        if not is_last:
            line = QWidget()
            line.setFixedWidth(2)
            line.setMinimumHeight(16)
            line.setStyleSheet("background-color: #B0E8F5; border: none;")
            lv.addWidget(line, 1, Qt.AlignHCenter)

        h.addWidget(left)

        # Le bouton conserve le même poids visuel pour chaque phase.
        right = QWidget()
        right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 3, 4, 5)
        rv.setSpacing(1)

        node_id = phase["node_id"]

        name_btn = QPushButton(phase["label"])
        name_btn.setFlat(True)
        name_btn.setCursor(Qt.PointingHandCursor)
        name_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        name_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT}; font-size: 11px; font-weight: 600; "
            f"text-align: left; background: transparent; border: none; padding: 4px 6px; }}"
            f"QPushButton:hover {{ color: {INDIGO_DEEP}; background-color: {LAVENDER}; "
            f"border-radius: 6px; }}"
        )
        name_btn.clicked.connect(lambda _=False, nid=node_id: self._navigate(nid))
        rv.addWidget(name_btn)

        h.addWidget(right, 1)
        return container


class _PhaseDetailHeader(QFrame):
    """En-tête structuré pour une fiche de phase."""

    def __init__(self, title: str, subtitle: str, intro: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PhaseDetailHeader")
        self.setStyleSheet(
            f"QFrame#PhaseDetailHeader {{ background-color: {INDIGO_DEEP}; "
            f"border: none; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        if title:
            t = QLabel(title)
            t.setWordWrap(True)
            t.setStyleSheet(
                "color: white; font-size: 14px; font-weight: 700; background: transparent;"
            )
            layout.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setWordWrap(True)
            s.setStyleSheet(
                f"color: {CYAN_BRIGHT}; font-size: 10px; font-weight: 600; "
                f"background: transparent; letter-spacing: 0.3px;"
            )
            layout.addWidget(s)

        if intro:
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: rgba(255,255,255,0.18);")
            layout.addWidget(sep)
            i = QLabel(intro)
            i.setWordWrap(True)
            i.setStyleSheet(
                "color: rgba(255,255,255,0.80); font-size: 11px; "
                "background: transparent; font-style: italic;"
            )
            layout.addWidget(i)


class _SectionBlock(QFrame):
    """Bloc section avec couleur de fond selon le type de contenu."""

    _HEADING_BG = {
        "Rôle":      (ROLE_BG,    BLUE_LIGHT),
        "Signaux":   (SIGNALS_BG, CYAN_BRIGHT),
        "Lien avec": (SIGNALS_BG, CYAN_BRIGHT),
        "Note sur":  (SIGNALS_BG, CYAN_BRIGHT),
    }

    def __init__(self, heading: str, text: str, parent=None) -> None:
        super().__init__(parent)
        bg = WHITE
        for key, (block_bg, _) in self._HEADING_BG.items():
            if heading.startswith(key):
                bg = block_bg
                break
        self.setObjectName("SectionBlock")
        self.setStyleSheet(
            f"QFrame#SectionBlock {{ background-color: {bg}; border: none; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        if heading:
            h = QLabel(heading)
            h.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {INDIGO_DEEP}; background: transparent;"
            )
            layout.addWidget(h)

        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
        layout.addWidget(t)


class _RetenirBlock(QFrame):
    """Encadré À retenir — fond indigo clair."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RetenirBlock")
        self.setStyleSheet(
            f"QFrame#RetenirBlock {{ background-color: {RETENIR_BG}; border: none; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        lbl = QLabel("À retenir")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {RETENIR_ACC}; "
            f"background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(lbl)

        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
        layout.addWidget(t)


class _ImpactCard(QFrame):
    """Carte individuelle du triptyque Impact."""

    _CFG = {
        "augmente": ("▲", IMPACT_AUG_BG, IMPACT_AUG_AC, "Augmenter"),
        "diminue":  ("▼", IMPACT_DIM_BG, IMPACT_DIM_AC, "Diminuer"),
        "supprime": ("✕", IMPACT_SUP_BG, IMPACT_SUP_AC, "Supprimer"),
    }

    def __init__(self, direction: str, text: str, parent=None) -> None:
        super().__init__(parent)
        icon, bg, accent, label = self._CFG.get(direction, ("?", WHITE, BORDER, direction))
        self.setObjectName("ImpactCard")
        self.setStyleSheet(
            f"QFrame#ImpactCard {{ background-color: {bg}; border: none; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        row = QHBoxLayout()
        row.setSpacing(5)
        row.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {accent}; font-size: 12px; font-weight: 700; background: transparent;"
        )
        row.addWidget(icon_lbl)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {accent}; "
            f"background: transparent; letter-spacing: 0.3px;"
        )
        row.addWidget(lbl)
        row.addStretch()
        layout.addLayout(row)

        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
        layout.addWidget(t)


class _ImpactTriptych(QWidget):
    """Bloc Impact en triptyque vertical."""

    def __init__(self, label: str, augmente: str, diminue: str, supprime: str,
                 parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Titre de section
        sep_row = QHBoxLayout()
        sep_row.setContentsMargins(0, 0, 0, 2)

        sep_l = QWidget()
        sep_l.setFixedHeight(1)
        sep_l.setStyleSheet("background: #D4F3F8;")
        sep_l.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        caption = f"  Impact — {label}  " if label else "  Impact  "
        title_lbl = QLabel(caption)
        title_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {INDIGO_DEEP}; "
            f"background: transparent; letter-spacing: 0.5px;"
        )

        sep_r = QWidget()
        sep_r.setFixedHeight(1)
        sep_r.setStyleSheet("background: #D4F3F8;")
        sep_r.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sep_row.addWidget(sep_l)
        sep_row.addWidget(title_lbl)
        sep_row.addWidget(sep_r)
        layout.addLayout(sep_row)

        for direction, text in [("augmente", augmente), ("diminue", diminue), ("supprime", supprime)]:
            if text:
                layout.addWidget(_ImpactCard(direction, text))


class _PrudenceBlock(QFrame):
    """Encadré Prudence — fond ambre."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PrudenceBlock")
        self.setStyleSheet(
            f"QFrame#PrudenceBlock {{ background-color: {CAUTION_BG}; border: none; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        lbl = QLabel("Prudence")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {CAUTION_TEXT}; "
            f"background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(lbl)

        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet("font-size: 11px; color: #4E342E; background: transparent;")
        layout.addWidget(t)


class _ParamsBlock(QFrame):
    """Tableau des paramètres — fond lavande."""

    def __init__(self, items: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ParamsBlock")
        self.setStyleSheet(
            f"QFrame#ParamsBlock {{ background-color: {PARAMS_BG}; border: none; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        title = QLabel("Paramètres du formulaire recette")
        title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {INDIGO_DEEP}; "
            f"background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(title)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {VIOLET_SOFT}; border: none;")
        layout.addWidget(sep)

        for item in items:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)

            name_lbl = QLabel(item.get("name", ""))
            name_lbl.setFixedWidth(52)
            name_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {INDIGO_DEEP}; "
                f"background: white; border-radius: 4px; padding: 1px 4px;"
            )

            unit_lbl = QLabel(item.get("unit", ""))
            unit_lbl.setFixedWidth(44)
            unit_lbl.setStyleSheet("font-size: 10px; color: #78909C; background: transparent;")

            desc_lbl = QLabel(item.get("desc", ""))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")

            row.addWidget(name_lbl)
            row.addWidget(unit_lbl)
            row.addWidget(desc_lbl, 1)
            layout.addLayout(row)


class _ArchLayerCard(QFrame):
    """Carte couche pour la vue architecture Digital Twin."""

    def __init__(self, label: str, color: str, callback: Callable, parent=None) -> None:
        super().__init__(parent)
        self._callback = callback
        hover_bg = _lighten(color, 0.90)
        self.setObjectName("ArchLayerCard")
        self._normal = (
            f"QFrame#ArchLayerCard {{ background-color: {WHITE}; border: none; border-radius: 8px; }}"
        )
        self._hover = (
            f"QFrame#ArchLayerCard {{ background-color: {hover_bg}; border: none; border-radius: 8px; }}"
        )
        self.setStyleSheet(self._normal)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        band = QWidget()
        band.setFixedWidth(5)
        band.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        band.setObjectName(f"archBand_{id(self)}")
        band.setStyleSheet(
            f"QWidget#archBand_{id(self)} {{ background-color: {color}; "
            f"border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}"
        )
        outer.addWidget(band)

        cl = QHBoxLayout()
        cl.setContentsMargins(10, 9, 10, 9)
        cl.setSpacing(6)

        t = QLabel(label)
        t.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT}; background: transparent;"
        )
        cl.addWidget(t, 1)

        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: 700; background: transparent;"
        )
        cl.addWidget(arrow)

        content_w = QWidget()
        content_w.setStyleSheet("background: transparent;")
        content_w.setLayout(cl)
        outer.addWidget(content_w, 1)

    def enterEvent(self, event) -> None:
        self.setStyleSheet(self._hover)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(self._normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._callback()
        super().mousePressEvent(event)


class _ArchArrow(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__("↓", parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.setStyleSheet(
            f"color: {BORDER}; font-size: 14px; font-weight: 700; background: transparent;"
        )


# ════════════════════════════════════════════════════════════════════════════
# Widget principal
# ════════════════════════════════════════════════════════════════════════════

class GuideWidget(QWidget):
    """
    Aurora Process Navigator — widget principal du guide de simulation.
    Intégré dans le QSplitter de SimulationPage.
    Moteur de navigation : GuideEngine (app/guide/guide_engine.py).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._engine = GuideEngine()
        self._anim_out = None
        self._anim_in  = None
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self.setMinimumWidth(230)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._build_skeleton()
        self._render()

    def _build_skeleton(self) -> None:
        self.setStyleSheet(f"background-color: {GUIDE_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_wrap = QWidget()
        header_wrap.setStyleSheet(f"background-color: {GUIDE_BG};")
        header_layout = QVBoxLayout(header_wrap)
        header_layout.setContentsMargins(10, 10, 10, 6)
        header_layout.addWidget(_AuroraHeader())
        root.addWidget(header_wrap)

        # Barre de navigation
        self._nav_bar = QWidget()
        self._nav_bar.setObjectName("GuideNavigation")
        self._nav_bar.setStyleSheet(
            f"QWidget#GuideNavigation {{ background-color: {WHITE}; border: none; }}"
        )
        nav_layout = QVBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(10, 6, 10, 6)
        nav_layout.setSpacing(3)

        self._crumb_container = QWidget()
        self._crumb_container.setStyleSheet("background: transparent;")
        self._crumb_layout = QHBoxLayout(self._crumb_container)
        self._crumb_layout.setContentsMargins(0, 0, 0, 0)
        self._crumb_layout.setSpacing(3)
        nav_layout.addWidget(self._crumb_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self._btn_back = QPushButton("← Retour")
        self._btn_back.setFlat(True)
        self._btn_back.setStyleSheet(
            f"QPushButton {{ color: {INDIGO_DEEP}; font-size: 11px; font-weight: 600; "
            f"background: transparent; border: none; padding: 2px 0px; }}"
            f"QPushButton:hover {{ color: {VIOLET_SOFT}; }}"
        )
        self._btn_back.clicked.connect(self._go_back)

        self._btn_home = QPushButton("Accueil")
        self._btn_home.setFlat(True)
        self._btn_home.setStyleSheet(
            f"QPushButton {{ color: #607D8B; font-size: 11px; "
            f"background: transparent; border: none; padding: 2px 0px; }}"
            f"QPushButton:hover {{ color: {INDIGO_DEEP}; }}"
        )
        self._btn_home.clicked.connect(self._go_home)

        btn_row.addWidget(self._btn_back)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_home)
        nav_layout.addLayout(btn_row)
        root.addWidget(self._nav_bar)

        # Zone de contenu défilante
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet(f"background-color: {GUIDE_BG};")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(10, 12, 10, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._content_widget)
        root.addWidget(self._scroll, stretch=1)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _navigate(self, node_id: str) -> None:
        self._engine.navigate(node_id)
        self._render_with_fade()

    def _go_back(self) -> None:
        self._engine.go_back()
        self._render_with_fade()

    def _go_home(self) -> None:
        self._engine.go_home()
        self._render_with_fade()

    # ── Transitions ────────────────────────────────────────────────────────

    def _render_with_fade(self) -> None:
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self._content_widget)
            self._content_widget.setGraphicsEffect(self._opacity_effect)

        anim_out = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim_out.setDuration(90)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.OutCubic)

        def _after_out() -> None:
            self._render()
            anim_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
            anim_in.setDuration(140)
            anim_in.setStartValue(0.0)
            anim_in.setEndValue(1.0)
            anim_in.setEasingCurve(QEasingCurve.InCubic)
            anim_in.start()
            self._anim_in = anim_in

        anim_out.finished.connect(_after_out)
        anim_out.start()
        self._anim_out = anim_out

    # ── Rendu ──────────────────────────────────────────────────────────────

    def _render(self) -> None:
        self._clear_content()
        self._update_nav_bar()

        node = self._engine.current()
        nid  = node.get("id", "")
        ntype = node.get("type", "menu")

        if nid == "home":
            self._render_home(node)
        elif nid == "digital_twin":
            self._render_digital_twin_menu(node)
        elif ntype == "menu" and node.get("show_frieze"):
            self._render_processus_menu(node)
        elif ntype == "menu":
            self._render_generic_menu(node)
        else:
            self._render_detail(node)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _update_nav_bar(self) -> None:
        while self._crumb_layout.count():
            item = self._crumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        crumbs   = self._engine.breadcrumb()
        can_back = self._engine.can_go_back()
        self._nav_bar.setVisible(can_back)

        if len(crumbs) > 1:
            for i, (title, _) in enumerate(crumbs):
                is_last = (i == len(crumbs) - 1)
                short   = self._shorten(title, 16)
                badge   = QLabel(short)
                if is_last:
                    badge.setStyleSheet(
                        f"background-color: {INDIGO_DEEP}; color: white; "
                        f"border-radius: 8px; padding: 2px 7px; font-size: 9px; font-weight: 700;"
                    )
                else:
                    badge.setStyleSheet(
                        f"background-color: {LAVENDER}; color: {INDIGO_DEEP}; "
                        f"border-radius: 8px; padding: 2px 7px; font-size: 9px; font-weight: 600;"
                    )
                badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self._crumb_layout.addWidget(badge)

                if not is_last:
                    sep = QLabel("›")
                    sep.setStyleSheet(
                        f"color: {CYAN_BRIGHT}; font-size: 11px; background: transparent;"
                    )
                    self._crumb_layout.addWidget(sep)

        self._crumb_layout.addStretch()
        self._btn_back.setVisible(can_back)
        self._btn_home.setVisible(can_back)

    @staticmethod
    def _shorten(text: str, max_len: int) -> str:
        if text == "Guide de simulation":
            return "Guide"
        return text[:max_len] + "…" if len(text) > max_len else text

    # ── Rendus spécialisés ─────────────────────────────────────────────────

    def _render_home(self, node: dict) -> None:
        subtitle = QLabel("Choisissez un thème pour explorer.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-size: 11px; color: #5F6B7C; background: transparent; margin-bottom: 4px;"
        )
        self._content_layout.addWidget(subtitle)

        for card in node.get("cards", []):
            target = card.get("target", "")
            accent = _MISSION_ACCENT.get(target, INDIGO_DEEP)
            w = _MissionCard(
                title=card.get("title", ""),
                description=card.get("description", ""),
                badge=card.get("badge", ""),
                accent=accent,
                callback=lambda nid=target: self._navigate(nid),
            )
            self._content_layout.addWidget(w)
        self._content_layout.addStretch()

    def _render_processus_menu(self, node: dict) -> None:
        if node.get("intro"):
            intro = QLabel(node["intro"])
            intro.setWordWrap(True)
            intro.setStyleSheet(
                f"font-size: 11px; color: {TEXT}; background: transparent; margin-bottom: 4px;"
            )
            self._content_layout.addWidget(intro)

        frise_hdr = QFrame()
        frise_hdr.setObjectName("TimelineHeader")
        frise_hdr.setStyleSheet(
            f"QFrame#TimelineHeader {{ background-color: {INDIGO_DEEP}; "
            f"border: none; border-radius: 6px; }}"
        )
        fh_lay = QHBoxLayout(frise_hdr)
        fh_lay.setContentsMargins(10, 7, 10, 7)
        fh_title = QLabel("Cycle EtO — séquence des phases")
        fh_title.setStyleSheet(
            "color: white; font-size: 11px; font-weight: 700; background: transparent;"
        )
        fh_lay.addWidget(fh_title)
        self._content_layout.addWidget(frise_hdr)

        self._content_layout.addWidget(_OrbitalTimeline(self._navigate))
        self._content_layout.addStretch()

    def _render_digital_twin_menu(self, node: dict) -> None:
        if node.get("intro"):
            intro = QLabel(node["intro"])
            intro.setWordWrap(True)
            intro.setStyleSheet(
                f"font-size: 11px; color: {TEXT}; background: transparent; margin-bottom: 4px;"
            )
            self._content_layout.addWidget(intro)

        arch_hdr = QFrame()
        arch_hdr.setObjectName("ArchitectureHeader")
        arch_hdr.setStyleSheet(
            f"QFrame#ArchitectureHeader {{ background-color: {INDIGO_DEEP}; "
            f"border: none; border-radius: 6px; }}"
        )
        ah_lay = QHBoxLayout(arch_hdr)
        ah_lay.setContentsMargins(10, 7, 10, 7)
        ah_title = QLabel("Architecture en couches")
        ah_title.setStyleSheet(
            "color: white; font-size: 11px; font-weight: 700; background: transparent;"
        )
        ah_lay.addWidget(ah_title)
        self._content_layout.addWidget(arch_hdr)

        for i, layer in enumerate(_DT_ARCH_LAYERS):
            tgt = layer["target"]
            self._content_layout.addWidget(_ArchLayerCard(
                label=layer["label"],
                color=layer["color"],
                callback=lambda nid=tgt: self._navigate(nid),
            ))
            if i < len(_DT_ARCH_LAYERS) - 1:
                self._content_layout.addWidget(_ArchArrow())

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #D4F3F8;")
        self._content_layout.addWidget(sep)

        other_lbl = QLabel("Autres composants")
        other_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {INDIGO_DEEP}; "
            f"background: transparent; margin-top: 4px; margin-bottom: 2px;"
        )
        self._content_layout.addWidget(other_lbl)

        arch_targets = {layer["target"] for layer in _DT_ARCH_LAYERS}
        for card in node.get("cards", []):
            target = card.get("target", "")
            if target not in arch_targets:
                self._content_layout.addWidget(_PhaseNavCard(
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    badge=card.get("badge", ""),
                    callback=lambda nid=target: self._navigate(nid),
                ))
        self._content_layout.addStretch()

    def _render_generic_menu(self, node: dict) -> None:
        if node.get("subtitle"):
            s = QLabel(node["subtitle"])
            s.setWordWrap(True)
            s.setStyleSheet(
                f"font-size: 11px; color: #5F6B7C; background: transparent; margin-bottom: 2px;"
            )
            self._content_layout.addWidget(s)

        if node.get("intro"):
            i = QLabel(node["intro"])
            i.setWordWrap(True)
            i.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
            self._content_layout.addWidget(i)

        if node.get("subtitle") or node.get("intro"):
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: #D4F3F8;")
            self._content_layout.addWidget(sep)

        for card in node.get("cards", []):
            target = card.get("target", "")
            self._content_layout.addWidget(_PhaseNavCard(
                title=card.get("title", ""),
                description=card.get("description", ""),
                badge=card.get("badge", ""),
                callback=lambda nid=target: self._navigate(nid),
            ))
        self._content_layout.addStretch()

    def _render_detail(self, node: dict) -> None:
        self._content_layout.addWidget(
            _PhaseDetailHeader(
                title=node.get("title", ""),
                subtitle=node.get("subtitle", ""),
                intro=node.get("intro", ""),
            )
        )
        for block in node.get("blocks", []):
            w = self._build_block(block)
            if w is not None:
                self._content_layout.addWidget(w)
        self._content_layout.addStretch()

    def _build_block(self, block: dict) -> QWidget | None:
        kind = block.get("kind", "section")
        if kind == "section":
            return _SectionBlock(block.get("heading", ""), block.get("text", ""))
        if kind == "retenir":
            return _RetenirBlock(block.get("text", ""))
        if kind == "impact":
            return _ImpactTriptych(
                block.get("label", ""),
                block.get("augmente", ""),
                block.get("diminue", ""),
                block.get("supprime", ""),
            )
        if kind == "prudence":
            return _PrudenceBlock(block.get("text", ""))
        if kind == "params":
            return _ParamsBlock(block.get("items", []))
        return None
