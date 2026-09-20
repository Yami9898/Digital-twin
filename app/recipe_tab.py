"""
Onglet d'entrée de recette.

Saisie de tous les paramètres recette (par phase) avec activation/
désactivation de chaque phase, et expose la recette assemblée via
get_recipe_data() pour les autres onglets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHeaderView, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database import recipe_repository
from app.database.connection import DatabaseConnectionError


@dataclass
class PhaseWidgetGroup:
    """Regroupe les widgets Qt d'une phase (titre, champs, case d'activation)."""
    title: str
    fields: Dict[str, QDoubleSpinBox]
    enabled_checkbox: QCheckBox | None = None


class RecipeSelectionDialog(QDialog):
    """Selection d'une recette MySQL active a charger dans le formulaire."""

    def __init__(
        self,
        recipes: list[dict],
        delete_callback: Callable[[int], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._delete_callback = delete_callback
        self.setWindowTitle("Charger une recette")
        self.resize(720, 350)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(recipes), 4)
        self.table.setHorizontalHeaderLabels(
            ["Nom", "Version", "Type de cycle", "Mise à jour"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        for row, recipe in enumerate(recipes):
            updated_at = recipe.get("updated_at")
            date_text = (
                updated_at.strftime("%d/%m/%Y %H:%M")
                if hasattr(updated_at, "strftime")
                else str(updated_at or "")
            )
            values = [
                recipe.get("name", ""),
                recipe.get("version", ""),
                recipe.get("cycle_type") or "",
                date_text,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.table.item(row, 0).setData(Qt.UserRole, int(recipe["id"]))

        if recipes:
            self.table.selectRow(0)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setObjectName("BtnDanger")
        self._open_button = QPushButton("Ouvrir")
        self._cancel_button = QPushButton("Annuler")
        self._open_button.setObjectName("BtnSecondary")
        self._cancel_button.setObjectName("BtnSecondary")
        for button in (self.delete_button, self._open_button, self._cancel_button):
            button.setFixedHeight(36)

        button_row.addWidget(self.delete_button)
        button_row.addStretch()
        button_row.addWidget(self._open_button)
        button_row.addWidget(self._cancel_button)
        self._open_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)
        self.delete_button.clicked.connect(self._delete_selected_recipe)
        layout.addLayout(button_row)
        self.table.doubleClicked.connect(self.accept)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self._update_actions()

    def selected_recipe_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).data(Qt.UserRole))

    def _update_actions(self) -> None:
        has_selection = self.selected_recipe_id() is not None
        self.delete_button.setEnabled(has_selection)
        self._open_button.setEnabled(has_selection)

    def _delete_selected_recipe(self) -> None:
        recipe_id = self.selected_recipe_id()
        if recipe_id is None:
            return
        row = self.table.currentRow()
        name = self.table.item(row, 0).text()
        answer = QMessageBox.question(
            self,
            "Supprimer recette",
            f"Supprimer la recette « {name} » de la liste active ?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._delete_callback is not None and not self._delete_callback(recipe_id):
            return
        self.table.removeRow(row)
        if self.table.rowCount():
            self.table.selectRow(min(row, self.table.rowCount() - 1))
        self._update_actions()
        QMessageBox.information(self, "Recette supprimée", f"La recette « {name} » a été supprimée.")


class RecipeTab(QWidget):
    """
    Onglet de saisie de recette.

    Expose :
      - get_recipe_data() → dict {phase_name: {field_name: value}}
      - get_recipe_name() → str
    """

    def __init__(self) -> None:
        super().__init__()
        self.phase_groups: List[PhaseWidgetGroup] = []
        self._is_loading_recipe = False
        self._current_db_recipe_id: int | None = None
        self._build_ui()
        self._default_recipe_data = self._collect_recipe_data(include_enabled=True)

    # ── Construction de l'UI ────────────────────────────────────────

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        intro = QLabel(
            "Entrée de recette. Ce modèle inclut le préconditionnement "
            "thermique et calcule la durée totale du cycle."
        )
        intro.setWordWrap(True)
        main_layout.addWidget(intro)
        main_layout.addWidget(self._build_database_actions())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cl = QVBoxLayout(content)

        # Paramètres généraux
        gb = QGroupBox("Paramètres généraux de recette")
        gf = QFormLayout(gb)
        self.recipe_name = QComboBox()
        self.recipe_name.setEditable(True)
        self.recipe_name.addItems([
            "Recette standard", "Recette courte", "Recette personnalisée",
        ])

        gf.addRow("Nom de recette", self.recipe_name)

        self.jacket_tt112_setpoint = self._make_spinbox(20.0, 80.0, 49.0, " °C")
        gf.addRow("Consigne TT112 / Jacket", self.jacket_tt112_setpoint)
        self.t_init_spinbox = self._make_spinbox(10.0, 60.0, 40.0, " °C")
        gf.addRow("T_INIT - Température initiale chambre", self.t_init_spinbox)
        self.rh_init_spinbox = self._make_spinbox(0.0, 100.0, 30.0, " %RH")
        gf.addRow("RH_INIT - Humidité initiale chambre", self.rh_init_spinbox)
        cl.addWidget(gb)

        # Liste des phases avec leurs champs
        phase_definitions: List[Tuple[str, List[Tuple]]] = [
            ("Préconditionnement", [
                ("T130 - Durée préconditionnement", 0, 600, 360, " min"),
            ]),
            ("Vide initial", [
                ("SP140 - Consigne pression vide", 0, 1500, 70, " mbar"),
                ("R140 - Vitesse de vide", 0, 2000, 50, " mbar/min"),
            ]),
            ("Test de fuite bas", [
                ("T160 - Durée", 0, 300, 10, " min"),
            ]),
            ("Test de fuite haut", [
                ("SP170 - Pression casse vide azote", 0, 1500, 700, " mbar"),
                ("R170 - Vitesse injection azote", 0, 2000, 50, " mbar/min"),
                ("T190 - Durée test", 0, 300, 15, " min"),
                ("SP200 - Consigne vide", 0, 1500, 70, " mbar"),
                ("R200 - Vitesse de vide", 0, 2000, 50, " mbar/min"),
            ]),
            ("Dilution azote", [
                ("SP220 - Pression dilution azote", 0, 1500, 0, " mbar"),
                ("R220 - Vitesse injection dilution azote", 0, 3000, 999, " mbar/min"),
                ("SP230 - Consigne pression vide", 0, 1500, 0, " mbar"),
                ("R230 - Vitesse du vide", 0, 3000, 999, " mbar/min"),
                ("NB220 - Nombre dilution azote", 0, 20, 0, ""),
            ]),
            ("Conditionnement dynamique", [
                ("T250 - Durée conditionnement dynamique", 0, 500, 0, " min"),
                ("P250 - Nombre de pulses", 0, 200, 0, ""),
                ("HR260 - Humidité conditionnement", 0, 100, 0, " %RH"),
            ]),
            ("Injection vapeur", [
                ("DP300 - Pression injection vapeur", 0, 500, 10, " mbar"),
                ("HR300 - Consigne humidité", 0, 100, 0, " %RH"),
                ("R300 - Vitesse injection vapeur", 0, 2000, 10, " mbar/min"),
            ]),
            ("Stabilisation humidité", [
                ("T310 - Temps stabilisation", 0, 500, 120, " min"),
                ("SP320 - Consigne de vide", 0, 1500, 50, " mbar"),
                ("R320 - Vitesse de vide", 0, 3000, 50, " mbar/min"),
            ]),
            ("Injection gaz 1", [
                ("DP330 - Injection gaz 1", 0, 500, 100, " mbar"),
                ("R330 - Vitesse injection gaz 1", 0, 3000, 999, " mbar/min"),
                ("T350 - Stabilisation gaz 1", 0, 60, 1, " min"),
            ]),
            ("Injection gaz 2", [
                ("DP390 - Injection gaz 2", 0, 500, 150, " mbar"),
                ("R390 - Vitesse injection gaz 2", 0, 3000, 999, " mbar/min"),
                ("T410 - Stabilisation gaz 2", 0, 60, 1, " min"),
            ]),
            ("Injection gaz 3", [
                ("DP450 - Injection gaz 3", 0, 500, 250, " mbar"),
                ("R450 - Vitesse injection gaz 3", 0, 3000, 999, " mbar/min"),
                ("T470 - Stabilisation gaz 3", 0, 60, 1, " min"),
            ]),
            ("Injection gaz 4", [
                ("DP510 - Injection gaz 4", 0, 500, 50, " mbar"),
                ("R510 - Vitesse injection gaz 4", 0, 3000, 999, " mbar/min"),
                ("T530 - Stabilisation gaz 4", 0, 60, 1, " min"),
            ]),
            ("Flush azote", [
                ("DP570 - Injection azote", 0, 500, 30, " mbar"),
                ("R570 - Vitesse injection azote", 0, 3000, 999, " mbar/min"),
            ]),
            ("Exposition EtO", [
                ("T580 - Temps exposition", 0, 1000, 180, " min"),
                ("EC580 - Concentration cible", 0, 2000, 520, " mg/L"),
            ]),
            ("Vide avant rinçage", [
                ("SP590 - Consigne vide", 0, 1500, 100, " mbar"),
                ("R590 - Vitesse de vide", 0, 3000, 50, " mbar/min"),
            ]),
            ("Rinçage azote", [
                ("SP620 - Pression casse vide azote", 0, 1500, 400, " mbar"),
                ("R620 - Vitesse casse vide azote", 0, 3000, 50, " mbar/min"),
                ("T630 - Stabilisation casse vide", 0, 60, 1, " min"),
                ("SP640 - Consigne vide", 0, 1500, 100, " mbar"),
                ("R640 - Vitesse de vide", 0, 3000, 50, " mbar/min"),
                ("T660 - Stabilisation vide", 0, 60, 1, " min"),
                ("NB620 - Nombre de rinçages azote", 0, 50, 1, ""),
            ]),
            ("Rinçage air", [
                ("SP680 - Pression casse vide air", 0, 1500, 750, " mbar"),
                ("R680 - Vitesse casse vide air", 0, 3000, 50, " mbar/min"),
                ("T690 - Stabilisation casse vide", 0, 60, 1, " min"),
                ("SP700 - Consigne vide", 0, 1500, 100, " mbar"),
                ("R700 - Vitesse de vide", 0, 3000, 50, " mbar/min"),
                ("T720 - Stabilisation vide", 0, 60, 1, " min"),
                ("NB680 - Nombre de rinçages air", 0, 50, 3, ""),
            ]),
            ("Rinçage additionnel", [
                ("SP740 - Pression casse vide air", 0, 1500, 0, " mbar"),
                ("R740 - Vitesse casse vide air", 0, 3000, 999, " mbar/min"),
                ("T750 - Stabilisation casse vide", 0, 60, 0, " min"),
                ("SP760 - Consigne vide", 0, 1500, 0, " mbar"),
                ("R760 - Vitesse de vide", 0, 3000, 999, " mbar/min"),
                ("T780 - Stabilisation vide", 0, 60, 0, " min"),
                ("NB740 - Nombre de rinçages additionnels", 0, 200, 0, ""),
            ]),
            ("Casse vide air finale", [
                ("SP790 - Consigne finale", 0, 1500, 870, " mbar"),
                ("R790 - Vitesse finale", 0, 3000, 50, " mbar/min"),
            ]),
        ]

        for title, field_specs in phase_definitions:
            cl.addWidget(self._build_phase_box(title, field_specs))

        cl.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _build_database_actions(self) -> QGroupBox:
        """Actions discretes de persistance des recettes dans MySQL."""
        box = QGroupBox("Recettes en base de données")
        layout = QVBoxLayout(box)
        actions = QHBoxLayout()

        self.db_new_button = QPushButton("Nouvelle recette")
        self.db_load_button = QPushButton("Charger recette")
        self.db_save_button = QPushButton("Enregistrer recette")
        for button in (
            self.db_new_button,
            self.db_load_button,
            self.db_save_button,
        ):
            button.setObjectName("BtnSecondary")

        actions.addWidget(self.db_new_button)
        actions.addWidget(self.db_load_button)
        actions.addWidget(self.db_save_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.db_status_label = QLabel("Aucune recette chargée depuis MySQL.")
        self.db_status_label.setStyleSheet("color: #607D8B; font-size: 12px;")
        layout.addWidget(self.db_status_label)

        self.db_new_button.clicked.connect(self._new_database_recipe)
        self.db_load_button.clicked.connect(self._load_database_recipe)
        self.db_save_button.clicked.connect(self._save_database_recipe)
        return box

    def _make_spinbox(self, minimum, maximum, value, suffix="") -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setDecimals(2)
        box.setSuffix(suffix)
        box.setSingleStep(1)
        box.setMinimumWidth(150)
        return box

    def _build_phase_box(self, title: str, field_specs: List[tuple]) -> QGroupBox:
        box = QGroupBox(title)
        layout = QFormLayout(box)
        fields: Dict[str, QDoubleSpinBox] = {}

        enabled_cb = QCheckBox("Phase activée")
        enabled_cb.setChecked(True)
        layout.addRow(enabled_cb)

        widgets = []
        for label, mn, mx, val, sfx in field_specs:
            spin = self._make_spinbox(mn, mx, val, sfx)
            layout.addRow(label, spin)
            fields[label] = spin
            widgets.append(spin)

        def on_toggle(checked: bool, _w=widgets) -> None:
            for w in _w:
                w.setEnabled(checked)

        enabled_cb.toggled.connect(on_toggle)
        on_toggle(True)

        self.phase_groups.append(PhaseWidgetGroup(
            title=title, fields=fields, enabled_checkbox=enabled_cb))
        return box

    # ── Données du formulaire ────────────────────────────────────────

    def _collect_recipe_data(self, include_enabled: bool = False) -> Dict[str, Dict[str, float]]:
        data: Dict[str, Dict[str, float]] = {
            "Général": {
                "Nom recette": 0.0,
                "TS_JACKET - Consigne TT112": self.jacket_tt112_setpoint.value(),
                "T_INIT - Température initiale chambre": self.t_init_spinbox.value(),
                "RH_INIT - Humidité initiale chambre": self.rh_init_spinbox.value(),
            }
        }
        for group in self.phase_groups:
            enabled = group.enabled_checkbox is None or group.enabled_checkbox.isChecked()
            phase_data: Dict[str, float] = {}
            if include_enabled:
                phase_data["__enabled__"] = 1.0 if enabled else 0.0
            if enabled:
                phase_data.update({name: widget.value() for name, widget in group.fields.items()})
            else:
                phase_data.update({name: 0.0 for name in group.fields.keys()})
            data[group.title] = phase_data
        return data

    def _apply_recipe_data(self, data: Dict[str, Dict[str, float]]) -> None:
        self._is_loading_recipe = True
        try:
            general = data.get("Général", {})
            self.jacket_tt112_setpoint.setValue(float(general.get(
                "TS_JACKET - Consigne TT112", self.jacket_tt112_setpoint.value())))
            self.t_init_spinbox.setValue(float(general.get(
                "T_INIT - Température initiale chambre", self.t_init_spinbox.value())))
            self.rh_init_spinbox.setValue(float(general.get(
                "RH_INIT - Humidité initiale chambre", self.rh_init_spinbox.value())))

            for group in self.phase_groups:
                phase_data = data.get(group.title, {})
                if group.enabled_checkbox is not None and "__enabled__" in phase_data:
                    group.enabled_checkbox.setChecked(bool(phase_data["__enabled__"]))
                for field_name, widget in group.fields.items():
                    if field_name in phase_data:
                        widget.setValue(float(phase_data[field_name]))
        finally:
            self._is_loading_recipe = False

    def get_recipe_data_from_form(self) -> Dict[str, Dict[str, float]]:
        """Retourne tous les champs du formulaire, activation des phases incluse."""
        return self._collect_recipe_data(include_enabled=True)

    def load_recipe_data_into_form(self, recipe_data: Dict[str, Dict[str, float]]) -> None:
        """Charge une recette persistée dans les champs existants du formulaire."""
        if not isinstance(recipe_data, dict):
            raise ValueError("Les données de recette doivent être un dictionnaire.")
        self._apply_recipe_data(recipe_data)

    # ── Persistance MySQL ───────────────────────────────────────────

    def _show_database_error(self, exc: Exception) -> None:
        if isinstance(exc, DatabaseConnectionError):
            message = (
                "Connexion à la base de données impossible. "
                "Vérifiez que MySQL/MAMP est lancé."
            )
        else:
            message = f"Opération impossible sur la base de données :\n{exc}"
        QMessageBox.critical(self, "Base de données", message)

    def _new_database_recipe(self) -> None:
        self.load_recipe_data_into_form(self._default_recipe_data)
        with QSignalBlocker(self.recipe_name):
            self.recipe_name.setCurrentText("Recette personnalisée")
        self._current_db_recipe_id = None
        self.db_status_label.setText("Nouvelle recette non enregistrée.")

    def _save_database_recipe(self) -> None:
        name = self.get_recipe_name()
        if not name or name == "Recette sans nom":
            name = self._ask_recipe_name("Enregistrer recette", "")
            if name is None:
                return
            with QSignalBlocker(self.recipe_name):
                self.recipe_name.setCurrentText(name)
        try:
            recipes = recipe_repository.get_all_recipes()
            matching_recipe = next(
                (recipe for recipe in recipes if recipe.get("name") == name),
                None,
            )
            recipe_data = self.get_recipe_data_from_form()
            if matching_recipe is None:
                recipe_id = recipe_repository.save_recipe(
                    name=name,
                    recipe_data=recipe_data,
                )
                message = f"La recette « {name} » a été enregistrée dans MySQL."
            else:
                recipe_id = int(matching_recipe["id"])
                updated = recipe_repository.update_recipe(
                    recipe_id=recipe_id,
                    name=name,
                    recipe_data=recipe_data,
                )
                if not updated:
                    raise ValueError("La recette active à enregistrer est introuvable.")
                message = f"La recette « {name} » a été mise à jour dans MySQL."
        except Exception as exc:
            self._show_database_error(exc)
            return
        self._current_db_recipe_id = recipe_id
        self.db_status_label.setText(f"Recette MySQL chargée : {name} (id {recipe_id}).")
        QMessageBox.information(
            self, "Recette enregistrée", message
        )

    def _load_database_recipe(self) -> None:
        try:
            recipes = recipe_repository.get_all_recipes()
        except Exception as exc:
            self._show_database_error(exc)
            return
        if not recipes:
            QMessageBox.information(
                self, "Charger recette", "Aucune recette active n'est enregistrée dans MySQL."
            )
            return
        dialog = RecipeSelectionDialog(recipes, self._deactivate_database_recipe, self)
        if dialog.exec() != QDialog.Accepted:
            return
        recipe_id = dialog.selected_recipe_id()
        if recipe_id is None:
            return
        try:
            recipe = recipe_repository.get_recipe_by_id(recipe_id)
            if recipe is None:
                raise ValueError("La recette sélectionnée n'existe plus.")
            self.load_recipe_data_into_form(recipe["recipe_data"])
        except Exception as exc:
            self._show_database_error(exc)
            return
        self._current_db_recipe_id = recipe_id
        with QSignalBlocker(self.recipe_name):
            self.recipe_name.setCurrentText(str(recipe["name"]))
        self.db_status_label.setText(
            f"Recette MySQL chargée : {recipe['name']} (id {recipe_id})."
        )

    def _deactivate_database_recipe(self, recipe_id: int) -> bool:
        try:
            deactivated = recipe_repository.deactivate_recipe(recipe_id)
        except Exception as exc:
            self._show_database_error(exc)
            return False
        if not deactivated:
            QMessageBox.warning(
                self, "Supprimer recette", "La recette active à supprimer est introuvable."
            )
            return False
        if self._current_db_recipe_id == recipe_id:
            self._current_db_recipe_id = None
            self.db_status_label.setText("Aucune recette chargée depuis MySQL.")
        return True

    def _ask_recipe_name(self, title: str, default: str = "") -> str | None:
        name, ok = QInputDialog.getText(self, title, "Nom de la recette :", text=default)
        if not ok:
            return None
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Nom invalide", "Le nom de la recette ne peut pas être vide.")
            return None
        return name

    # ── Interface utilisée par les autres onglets ────────────────────

    def get_recipe_data(self) -> Dict[str, Dict[str, float]]:
        """Retourne le dictionnaire complet de la recette pour la simulation."""
        return self._collect_recipe_data(include_enabled=False)

    def get_recipe_name(self) -> str:
        return self.recipe_name.currentText().strip() or "Recette sans nom"
