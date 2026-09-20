"""
Constantes partagées entre les modules.

Centralise les listes de variables et leur affectation aux axes
matplotlib pour garantir la cohérence entre tracé simulé, tracé réel
et exports.
"""

from __future__ import annotations

from typing import List, Tuple

# Variables suivies par le digital twin (ordre logique d'affichage).
VARIABLES: List[str] = [
    "PT111", "PT112", "TT111", "TT112", "TT191", "RHT121", "GT121",
]

# Affectation aux axes matplotlib (cohérent entre tous les onglets).
#   - Axe gauche  : températures + humidité (échelle 0–100)
#   - Axe droit   : pressions + masse gaz   (échelle mbar / kg / mg·L⁻¹)
LEFT_AXIS_VARS = {"TT111", "TT112", "TT191", "RHT121"}
RIGHT_AXIS_VARS = {"PT111", "PT112", "GT121"}

# Clé interne pour la pression partielle de vapeur d'eau dans l'état.
WATER_VAPOR_KEY = "P_H2O"

# Colonnes du rapport PDF de cycle simulé.
REPORT_COLUMNS: List[Tuple[str, str | None]] = [
    ("Phase", None),
    ("Durée (min)", None),
    ("PT 111", "PT111"),
    ("PT 112", "PT112"),
    ("TT 111", "TT111"),
    ("TT 112", "TT112"),
    ("TT 191", "TT191"),
    ("RHT 121", "RHT121"),
    ("GT 121", "GT121"),
]

# Sous-ensemble des variables actuellement comparées simulé vs réel
# (sera étendu à la liste complète quand les capteurs seront tous
# validés sur les PDF réels).
COMPARED_VARS: List[str] = ["PT111", "TT112", "RHT121"]
