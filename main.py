"""
Point d'entrée du Digital Twin Stérilisateur EtO.

Lance l'application PySide6, applique le stylesheet global,
et délègue toute la logique aux modules du package `app/`.

Usage :
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.styles import GLOBAL_STYLESHEET


def _init_calibration() -> None:
    """Charge la calibration active depuis data/active_calibration.json.

    Si l'instantané actif n'est pas "default", ses coefficients sont appliqués
    aux modules du modèle avant l'ouverture de la fenêtre. signals.py n'est
    jamais modifié — seul le dictionnaire global des modules est patché.
    """
    try:
        from app.calibration.snapshot_manager import SnapshotManager
        manager   = SnapshotManager()
        active_id = manager.get_active_id()
        if active_id != "default":
            snapshot = manager.get_snapshot(active_id)
            if snapshot and snapshot.get("coefficients"):
                from app.calibration.coefficient_store import apply_snapshot
                apply_snapshot(snapshot["coefficients"])
    except Exception:
        pass   # En cas d'erreur (dépendances absentes, etc.), continuer avec les défauts


def main() -> None:
    app = QApplication(sys.argv)

    # Palette et feuille de style globale (couleurs de l'application)
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # Appliquer la calibration active avant d'ouvrir la fenêtre
    _init_calibration()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
