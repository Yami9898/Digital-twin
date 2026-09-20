"""
app/model/actuators.py
État des actionneurs et mapping GRAFCET → actionneurs.

Seule cette couche peut émettre des commandes vers les actionneurs.
La couche physics.py lit ActuatorState pour savoir quoi simuler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


# ── Alarme cycle ──────────────────────────────────────────────────────

class CycleAlarm(Exception):
    """Alarme levée quand une précondition de sécurité est violée en cours de cycle.

    Attributs:
        level (int): 1 = avertissement, 2 = arrêt immédiat, 3 = arrêt d'urgence.
    """

    def __init__(self, message: str, level: int = 2) -> None:
        super().__init__(message)
        self.level = level


# ── État actionneurs ──────────────────────────────────────────────────

@dataclass
class ActuatorState:
    """Snapshot de l'état de tous les actionneurs à un instant donné.

    Booléens = vanne/pompe ouverte (True) ou fermée (False).
    Flottants = niveau de puissance thermoplongeur [0.0 – 1.0].
    """
    VP_vacuum:    bool  = False  # pompe à vide
    PV_vide:      bool  = False  # vanne vide chambre
    PV_N2:        bool  = False  # vanne injection azote
    PV_EtO:       bool  = False  # vanne injection EtO / vaporiseur
    PV_steam:     bool  = False  # vanne injection vapeur
    PV_air:       bool  = False  # vanne casse vide air
    EH_jacket:    float = 0.0    # thermoplongeur double enveloppe (0 – 1)
    EH_vaporizer: float = 0.0    # thermoplongeur vaporiseur gaz (0 – 1)
    EH_generator: float = 0.0    # thermoplongeur générateur vapeur (0 – 1)
    CP_jacket:    bool  = False  # pompe circulation jacket
    CP_vaporizer: bool  = False  # pompe circulation vaporiseur
    RC_recirc:    bool  = False  # turbine recirculation chambre


# ── États GRAFCET connus ──────────────────────────────────────────────

_KNOWN_STATES: frozenset[str] = frozenset({
    "S0", "S1", "S2", "S3", "S4", "S4a", "S4b",
    "S5", "S6", "S7", "S8", "S9", "S10",
    "S11", "S12", "S12a", "S12b", "S12c", "S13",
})


# ── Mapping état GRAFCET → actionneurs ───────────────────────────────

def actuators_for_state(
    state_id: str,
    sub_state: str = "",
) -> ActuatorState:
    """Retourne l'ActuatorState correspondant à l'état GRAFCET *state_id*.

    Args:
        state_id:  Identifiant d'état GRAFCET (ex. "S2", "S8").
        sub_state: Sous-phase interne à l'état. Valeurs reconnues par état :
                   S4/S4a  : "injection" | "hold" (maintien passif) | "vide"
                   S4b     : "steam" | "stabilisation" (post-steam ou post-vide) | "vide"
                   S8      : "eto_injection" | "n2_injection" | "" (stabilisation)
                   S11     : "injection" | "stabilisation" (post-inj ou post-vide) | "vide"
                   S12/S12a: "break" | "stabilisation" (post-break ou post-vide) | "vide"

    Raises:
        ValueError: Si *state_id* n'appartient pas aux états GRAFCET connus.
    """
    if state_id not in _KNOWN_STATES:
        raise ValueError(
            f"actuators_for_state: état inconnu '{state_id}'. "
            f"États valides : {sorted(_KNOWN_STATES)}"
        )

    if state_id == "S0":
        return ActuatorState(EH_jacket=0.3)

    if state_id == "S1":
        return ActuatorState(EH_jacket=1.0, CP_jacket=True, RC_recirc=True)

    if state_id == "S2":
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S3":
        return ActuatorState()  # test fuite bas — passif

    if state_id in ("S4", "S4a"):
        if sub_state == "injection":
            return ActuatorState(PV_N2=True)
        if sub_state == "hold":
            # Test fuite haut : maintien passif — on observe la dérive, pompe à vide OFF
            return ActuatorState()
        # "vide" → mise sous vide réelle
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S4b":
        if sub_state == "steam":
            return ActuatorState(PV_steam=True, EH_generator=1.0, RC_recirc=True)
        if sub_state == "stabilisation":
            # Stabilisation post-steam ou post-vide : RC actif, chauffage jacket modéré
            return ActuatorState(RC_recirc=True, EH_jacket=0.5)
        # "vide" → mise sous vide DEC
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S5":
        return ActuatorState(PV_steam=True, EH_generator=1.0, RC_recirc=True)

    if state_id == "S6":
        return ActuatorState(RC_recirc=True, EH_jacket=0.8)

    if state_id == "S7":
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S8":
        # Injections gaz alternées EtO / N2
        if sub_state == "eto_injection":
            return ActuatorState(PV_EtO=True, CP_vaporizer=True,
                                  EH_vaporizer=1.0, RC_recirc=True)
        if sub_state == "n2_injection":
            return ActuatorState(PV_N2=True, RC_recirc=True)
        # stabilisation entre injections
        return ActuatorState(RC_recirc=True, EH_jacket=0.5)

    if state_id == "S9":
        return ActuatorState(RC_recirc=True, EH_jacket=0.5)

    if state_id == "S10":
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S11":
        if sub_state == "injection":
            return ActuatorState(PV_N2=True, RC_recirc=True)
        if sub_state == "stabilisation":
            # Stabilisation post-injection ou post-vide : recirculation, pas de pompe
            return ActuatorState(RC_recirc=True)
        # "vide" → mise sous vide réelle
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id in ("S12", "S12a"):
        if sub_state == "break":
            return ActuatorState(PV_air=True, RC_recirc=True)
        if sub_state == "stabilisation":
            # Stabilisation après break air ou après vide : recirculation passive
            return ActuatorState(RC_recirc=True)
        # "vide" → mise sous vide réelle
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S12b":
        return ActuatorState()  # attente validation opérateur

    if state_id == "S12c":
        return ActuatorState(VP_vacuum=True, PV_vide=True)

    if state_id == "S13":
        return ActuatorState(PV_air=True)

    return ActuatorState()  # fallback (ne devrait pas être atteint)


# ── Vérification de sécurité ──────────────────────────────────────────

def safety_check(
    state_id: str,
    signals: Dict[str, float],
    door_closed: bool = True,
    gasket_inflated: bool = True,
) -> Tuple[bool, str]:
    """Vérifie les préconditions de sécurité avant d'activer l'état *state_id*.

    Args:
        state_id:        Identifiant d'état GRAFCET.
        signals:         État courant des capteurs.
        door_closed:     True si la porte de la chambre est fermée et verrouillée.
        gasket_inflated: True si les joints gonflables sont en pression.

    Returns:
        (True, "")            → préconditions satisfaites, cycle peut continuer.
        (False, "raison")     → précondition violée, raison décrite.

    Raises:
        ValueError: Si *state_id* n'est pas dans les états GRAFCET connus.
        CycleAlarm: Si une sécurité de niveau 2 est violée pendant une phase active.
    """
    if state_id not in _KNOWN_STATES:
        raise ValueError(
            f"safety_check: état inconnu '{state_id}'. "
            f"États valides : {sorted(_KNOWN_STATES)}"
        )

    pt111 = signals.get("PT111", 1013.0)

    # ── Pompe à vide active ──────────────────────────────────────────
    if state_id in ("S2", "S7", "S10", "S12c"):
        if not door_closed:
            return False, "VP_vacuum / PV_vide interdits : porte ouverte"

    # ── Injection sous vide (EtO, N2 gaz, vapeur) ───────────────────
    if state_id in ("S5", "S8"):
        if not door_closed:
            return False, "Injection gaz/vapeur interdite : porte ouverte"
        if not gasket_inflated:
            return False, "Injection gaz/vapeur interdite : joints non gonflés"
        if pt111 >= 800:
            reason = f"Pression chambre trop élevée pour injection ({pt111:.0f} mbar ≥ 800)"
            raise CycleAlarm(reason, level=2)

    # ── Casse vide air ───────────────────────────────────────────────
    if state_id in ("S13", "S12", "S12a"):
        if not door_closed:
            return False, "Casse vide air interdite : porte ouverte"
        if pt111 >= 900:
            return False, f"Pression trop haute pour casse vide air ({pt111:.0f} mbar ≥ 900)"

    # ── Exposition EtO ───────────────────────────────────────────────
    if state_id == "S9":
        if signals.get("GT121", 0.0) <= 0.0:
            raise CycleAlarm("Exposition EtO : concentration EtO nulle (GT121 = 0)", level=2)
        if signals.get("TT111", 0.0) <= 30.0:
            raise CycleAlarm(
                f"Exposition EtO : température chambre trop basse "
                f"({signals['TT111']:.1f} °C ≤ 30 °C)", level=2
            )

    return True, ""
