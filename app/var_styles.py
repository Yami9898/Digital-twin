"""
Styles partagés (couleurs, unités) pour toutes les variables suivies.

Importé par real_cycle_tab, plot_tab et comparison_tab pour garantir
la cohérence visuelle entre les onglets.
"""

from __future__ import annotations

from typing import Dict

VAR_COLORS: Dict[str, str] = {
    "PT111":  "#0F6C8C",  # bleu pression chambre
    "PT112":  "#3FA9C8",  # bleu clair pression jacket
    "TT111":  "#C6432F",  # rouge température chambre
    "TT112":  "#E8814A",  # orange jacket
    "TT191":  "#A0522D",  # marron sonde charge
    "RHT121": "#2E8B57",  # vert humidité
    "GT121":  "#6F4FA8",  # violet gaz EtO
}

VAR_UNITS: Dict[str, str] = {
    "PT111":  "mbar",
    "PT112":  "mbar",
    "TT111":  "°C",
    "TT112":  "°C",
    "TT191":  "°C",
    "RHT121": "%RH",
    "GT121":  "kg",
}
