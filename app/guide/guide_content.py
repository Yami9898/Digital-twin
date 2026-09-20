"""
app/guide/guide_content.py
Contenu pur du guide de simulation — aucune logique, aucune dépendance PySide6.

Sources :
  - Formulaire recette : app/recipe_tab.py  (noms de paramètres exacts)
  - Modèle GRAFCET    : app/model/grafcet.py (états S0–S13)
  - Signaux           : app/model/signals.py (noms exacts : PT111, RHT121…)
  - Données §7        : cahier des charges + rapports machine

Divergences code vs spec §7 signalées ici :
  - TT112 dans le code = température paroi / double enveloppe (pas capteur chambre 2)
  - RHT121 dans le code (pas d'espace, contrairement à la spec)
  - GT121 dans le code = masse EtO (kg) (pas d'espace)
  - GRAFCET simplifié : 16 états S0–S13, pas les 92 sous-étapes de l'AF
  - Paramètres absents du formulaire (non affichés) : T140, DP160, T170, T180,
    T200, HDHS320, PDHS320, HESS320, TEHS320, WT330/390/450/510,
    DP360/420/480/540, HEE580, DP600, T601, DP650, T650, R650,
    DP710, T710, R710

Structure de nœud :
  id       — identifiant unique
  type     — menu | detail | phase | architecture
  title    — titre affiché
  subtitle — sous-titre court
  intro    — paragraphe d'introduction (menu) ou chapeau (detail/phase)
  cards    — liste de cartes cliquables (type menu)
  blocks   — liste de blocs de contenu (type detail/phase/architecture)
  show_frieze — True si la frise des phases doit être affichée (menu processus)

Structure d'une carte :
  title, description, badge, target

Structure d'un bloc :
  kind = "section"   → {heading, text}
  kind = "retenir"   → {text}
  kind = "impact"    → {label, augmente, diminue, supprime}
  kind = "prudence"  → {text}
  kind = "params"    → {items: [{name, unit, desc}]}
"""

from __future__ import annotations

# ── Ordre des phases simulées (code) ──────────────────────────────────────────
# Extrait de grafcet.py _run() — c'est cet ordre qui sert de base à la frise.
PHASES_ORDER: list[dict] = [
    {"label": "Préconditionnement",       "node_id": "phase_preconditionnement",      "state": "S1",   "conditional": "T130 > 0"},
    {"label": "Vide initial",             "node_id": "phase_vide_initial",            "state": "S2",   "conditional": None},
    {"label": "Test de fuite bas",        "node_id": "phase_test_fuite_bas",          "state": "S3",   "conditional": None},
    {"label": "Test de fuite haut",       "node_id": "phase_test_fuite_haut",         "state": "S4",   "conditional": "SP170 > 0"},
    {"label": "Dilution azote",           "node_id": "phase_dilution_azote",          "state": "S4a",  "conditional": "NB220 > 0"},
    {"label": "Conditionnement dynamique","node_id": "phase_conditionnement_dyn",     "state": "S4b",  "conditional": "T250 > 0"},
    {"label": "Injection vapeur",         "node_id": "phase_injection_vapeur",        "state": "S5",   "conditional": None},
    {"label": "Stabilisation humidité",   "node_id": "phase_stabilisation_humidite",  "state": "S6",   "conditional": None},
    {"label": "Injection gaz 1",          "node_id": "phase_injection_gaz_1",         "state": "S8",   "conditional": None},
    {"label": "Injection gaz 2",          "node_id": "phase_injection_gaz_2",         "state": "S8",   "conditional": None},
    {"label": "Injection gaz 3",          "node_id": "phase_injection_gaz_3",         "state": "S8",   "conditional": None},
    {"label": "Injection gaz 4",          "node_id": "phase_injection_gaz_4",         "state": "S8",   "conditional": None},
    {"label": "Flush azote",              "node_id": "phase_flush_azote",             "state": "S8",   "conditional": None},
    {"label": "Exposition EtO",           "node_id": "phase_exposition_eto",          "state": "S9",   "conditional": None},
    {"label": "Vide avant rinçage",       "node_id": "phase_vide_avant_rincage",      "state": "S10",  "conditional": None},
    {"label": "Rinçage azote",            "node_id": "phase_rincage_azote",           "state": "S11",  "conditional": None},
    {"label": "Rinçage air",              "node_id": "phase_rincage_air",             "state": "S12",  "conditional": None},
    {"label": "Rinçage additionnel",      "node_id": "phase_rincage_additionnel",     "state": "S12a", "conditional": "NB740 > 0"},
    {"label": "Casse vide air finale",    "node_id": "phase_casse_vide_finale",       "state": "S13",  "conditional": None},
]


# ── Arbre de nœuds ────────────────────────────────────────────────────────────

NODES: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════════
    # ACCUEIL
    # ══════════════════════════════════════════════════════════════════════
    "home": {
        "id":       "home",
        "type":     "menu",
        "title":    "Guide de simulation",
        "subtitle": "Explorez le cycle, les phases, les paramètres et le fonctionnement du digital twin.",
        "intro":    "",
        "show_frieze": False,
        "cards": [
            {
                "title":       "Comprendre le processus EtO",
                "description": "Vue d'ensemble du cycle et détail de chaque phase.",
                "badge":       "Processus",
                "target":      "processus_eto",
            },
            {
                "title":       "Points de vigilance",
                "description": "Points à prendre en compte lors de la construction d'un cycle.",
                "badge":       "Vigilance",
                "target":      "vigilance",
            },
            {
                "title":       "Aide à la création d'une recette",
                "description": "Paramètres modifiables et effet de chaque réglage.",
                "badge":       "Recette",
                "target":      "aide_recette",
            },
            {
                "title":       "Comprendre le digital twin",
                "description": "Architecture, couches et limites du modèle.",
                "badge":       "Modèle",
                "target":      "digital_twin",
            },
        ],
        "blocks": [],
    },

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 — PROCESSUS EtO
    # ══════════════════════════════════════════════════════════════════════
    "processus_eto": {
        "id":       "processus_eto",
        "type":     "menu",
        "title":    "Comprendre le processus EtO",
        "subtitle": "Séquence des phases du cycle EtO",
        "intro":    (
            "Le cycle enchaîne jusqu'à 19 phases, de la préparation thermique "
            "jusqu'à la remontée en pression finale. Certaines phases peuvent "
            "être inactives selon la configuration de la recette."
        ),
        "show_frieze": True,
        "cards": [
            {"title": p["label"],
             "description": f"État GRAFCET {p['state']}",
             "badge": "Phase",
             "target": p["node_id"]}
            for p in PHASES_ORDER
        ],
        "blocks": [],
    },

    # ══════════════════════════════════════════════════════════════════════
    # PHASES — DÉTAIL (partagées entre Section 1 et Section 3)
    # ══════════════════════════════════════════════════════════════════════

    "phase_preconditionnement": {
        "id":       "phase_preconditionnement",
        "type":     "phase",
        "title":    "Préconditionnement",
        "subtitle": "GRAFCET S1 — exécutée selon la recette",
        "intro":    "Cette phase chauffe la chambre avant toute action chimique. Elle garantit les conditions thermiques stables que les phases suivantes supposent acquises.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La double enveloppe (jacket) monte en température jusqu'à la consigne TS_JACKET. "
                    "La chambre et la charge atteignent progressivement l'équilibre thermique. "
                    "Aucune vanne de pression n'est ouverte — la pression reste à la valeur en cours."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "TT111 — température chambre. TT112 — température paroi (double enveloppe). TT191 — sonde de charge.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "T130", "unit": "min", "desc": "Durée du préconditionnement."},
                    {"name": "TS_JACKET", "unit": "°C", "desc": "Consigne de température double enveloppe (paramètre général de recette)."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Sans préchauffage, les phases suivantes démarrent hors des conditions thermiques prévues.",
            },
            {
                "kind": "impact",
                "label": "T130",
                "augmente": "Préchauffe plus longtemps — équilibre thermique mieux atteint.",
                "diminue": "Risque de démarrer en dehors des conditions thermiques cibles.",
                "supprime": "Phase sautée (T130 = 0) — la simulation démarre à froid.",
            },
            {
                "kind": "prudence",
                "text": "La durée T130 doit correspondre à la recette validée par la démarche qualité.",
            },
        ],
    },

    "phase_vide_initial": {
        "id":       "phase_vide_initial",
        "type":     "phase",
        "title":    "Vide initial",
        "subtitle": "GRAFCET S2 — obligatoire",
        "intro":    "La pompe à vide extrait l'air de la chambre jusqu'à la consigne SP140. L'air résiduel diluerait les gaz injectés ensuite.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La pompe à vide descend la pression de l'atmosphère (~1 013 mbar) "
                    "jusqu'à SP140. Cette extraction d'air prépare la chambre pour recevoir "
                    "la vapeur et l'EtO dans des proportions maîtrisées."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111 et PT112 — pression chambre (capteur 1 et 2). Le modèle calcule la durée réelle à partir de SP140, R140 et de la pression initiale.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP140", "unit": "mbar", "desc": "Consigne de pression cible (fin de vide)."},
                    {"name": "R140",  "unit": "mbar/min", "desc": "Vitesse de pompage (999 = vitesse machine réelle)."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Un bon vide de départ conditionne toute la suite du cycle.",
            },
            {
                "kind": "impact",
                "label": "SP140",
                "augmente": "Vide moins poussé — plus d'air résiduel dans la chambre.",
                "diminue": "Vide plus profond — phase plus longue.",
                "supprime": "Phase obligatoire — impossible à désactiver.",
            },
            {
                "kind": "prudence",
                "text": "SP140 doit rester dans les limites de la pompe à vide de la machine. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_test_fuite_bas": {
        "id":       "phase_test_fuite_bas",
        "type":     "phase",
        "title":    "Test de fuite bas",
        "subtitle": "GRAFCET S3 — obligatoire",
        "intro":    "La chambre est isolée sous vide. On mesure la remontée de pression pour vérifier l'intégrité de l'enceinte.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Toutes les vannes sont fermées. La pression est observée pendant T160 minutes. "
                    "Une remontée de pression supérieure au seuil admissible indique une fuite. "
                    "Le modèle simule une fuite douce de 0,2 mbar/min."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111 et PT112 — dérive de pression observée pendant le test.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "T160", "unit": "min", "desc": "Durée du test de fuite bas."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Un test de fuite raté signale une fuite physique — le cycle doit être arrêté.",
            },
            {
                "kind": "impact",
                "label": "T160",
                "augmente": "Mesure plus longue — diagnostic plus fiable.",
                "diminue": "Mesure moins précise — fuite lente potentiellement non détectée.",
                "supprime": "Aucune vérification d'intégrité avant les injections.",
            },
            {
                "kind": "prudence",
                "text": "Le seuil d'acceptation dépend des spécifications machine — vérifier la recette validée.",
            },
        ],
    },

    "phase_test_fuite_haut": {
        "id":       "phase_test_fuite_haut",
        "type":     "phase",
        "title":    "Test de fuite haut",
        "subtitle": "GRAFCET S4 — exécutée selon la recette",
        "intro":    "On injecte de l'azote pour monter en pression (SP170), puis on mesure la chute pendant T190 minutes, puis on revient sous vide.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Test complémentaire au test bas : vérifie l'étanchéité sous pression positive. "
                    "L'azote est injecté jusqu'à SP170, stabilisé, puis la pression est observée. "
                    "Enfin, la chambre revient sous vide (SP200) pour la suite du cycle."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111 et PT112 — pression pendant l'injection azote, le test et le vide retour.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP170", "unit": "mbar", "desc": "Consigne casse-vide azote (pression de test)."},
                    {"name": "R170",  "unit": "mbar/min", "desc": "Vitesse injection azote."},
                    {"name": "T190",  "unit": "min", "desc": "Durée du test."},
                    {"name": "SP200", "unit": "mbar", "desc": "Consigne de vide retour."},
                    {"name": "R200",  "unit": "mbar/min", "desc": "Vitesse du vide retour."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Cette phase est exécutée selon les paramètres de la recette (SP170 > 0).",
            },
            {
                "kind": "impact",
                "label": "SP170",
                "augmente": "Test à pression plus élevée — plus sévère.",
                "diminue": "Test moins exigeant.",
                "supprime": "Phase désactivée (SP170 = 0) — pas de test sous pression positive.",
            },
            {
                "kind": "prudence",
                "text": "SP170 doit rester dans les limites mécaniques de l'enceinte. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_dilution_azote": {
        "id":       "phase_dilution_azote",
        "type":     "phase",
        "title":    "Dilution azote",
        "subtitle": "GRAFCET S4a — exécutée selon la recette",
        "intro":    "Cycles répétés injection azote / vide pour diluer les contaminants résiduels dans la chambre avant le conditionnement.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Chaque cycle injecte de l'azote jusqu'à SP220, puis revient sous vide "
                    "jusqu'à SP230. L'opération est répétée NB220 fois. "
                    "Chaque cycle dilue et extrait une fraction des contaminants résiduels."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111 et PT112 — pression d'injection et de vide. RHT121 — l'humidité chute légèrement à chaque vide.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP220",  "unit": "mbar", "desc": "Consigne de pression injection azote."},
                    {"name": "R220",   "unit": "mbar/min", "desc": "Vitesse injection azote (999 = max machine)."},
                    {"name": "SP230",  "unit": "mbar", "desc": "Consigne de vide entre deux cycles."},
                    {"name": "R230",   "unit": "mbar/min", "desc": "Vitesse du vide."},
                    {"name": "NB220",  "unit": "",     "desc": "Nombre de cycles de dilution."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Chaque cycle dilution–vide réduit la concentration résiduelle par un facteur multiplicatif.",
            },
            {
                "kind": "impact",
                "label": "NB220",
                "augmente": "Meilleure décontamination — durée plus longue.",
                "diminue": "Décontamination moins poussée.",
                "supprime": "Phase désactivée (NB220 = 0) — pas de dilution avant le conditionnement.",
            },
            {
                "kind": "prudence",
                "text": "Cette phase est exécutée si NB220 > 0. NB220 = 0 désactive entièrement la dilution.",
            },
        ],
    },

    "phase_conditionnement_dyn": {
        "id":       "phase_conditionnement_dyn",
        "type":     "phase",
        "title":    "Conditionnement dynamique (DEC)",
        "subtitle": "GRAFCET S4b — exécutée selon la recette",
        "intro":    "Cycles alternés injection vapeur / vide pour conditionner l'humidité de la charge. L'humidité atteinte ici influence les conditions d'exposition EtO représentées par le modèle.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Chaque pulse injecte de la vapeur, stabilise, puis fait un vide court. "
                    "L'alternance répétée (P250 pulses sur T250 minutes) homogénéise l'humidité "
                    "dans la charge et les emballages avant l'exposition à l'EtO."
                ),
            },
            {
                "kind": "section",
                "heading": "Lien avec le modèle physique",
                "text": "Le modèle applique la formule de Magnus pour calculer l'humidité relative à partir de la température et de la pression de vapeur. DEC_STEAM_TO_VAPOR_GAIN contrôle le gain vapeur par pulse.",
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — pression pulses. TT111 — température chambre. RHT121 — humidité relative.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "T250",  "unit": "min", "desc": "Durée totale du conditionnement dynamique."},
                    {"name": "P250",  "unit": "",    "desc": "Nombre de pulses vapeur / vide."},
                    {"name": "HR260", "unit": "%RH", "desc": "Consigne d'humidité relative cible."},
                ],
            },
            {
                "kind": "retenir",
                "text": "L'humidité contrôlée ici influence les conditions d'exposition EtO simulées par le modèle.",
            },
            {
                "kind": "impact",
                "label": "HR260",
                "augmente": "Humidité de conditionnement plus élevée — humidité simulée plus haute à l'entrée de l'exposition EtO.",
                "diminue": "Humidité plus basse — risque de sous-conditionnement.",
                "supprime": "Phase désactivée (T250 = 0) — conditionnement sans humidification dynamique.",
            },
            {
                "kind": "prudence",
                "text": "Cette phase est exécutée si T250 > 0. La consigne HR260 doit être conforme à la recette validée.",
            },
        ],
    },

    "phase_injection_vapeur": {
        "id":       "phase_injection_vapeur",
        "type":     "phase",
        "title":    "Injection vapeur",
        "subtitle": "GRAFCET S5",
        "intro":    "Injection directe de vapeur dans la chambre pour augmenter la pression partielle d'eau de DP300 mbar.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La vanne vapeur (PV_steam) s'ouvre et injecte jusqu'à ce que la pression "
                    "monte de DP300 mbar. La vapeur apporte l'humidité nécessaire à la réaction EtO "
                    "et contribue au conditionnement final avant l'exposition."
                ),
            },
            {
                "kind": "section",
                "heading": "Lien avec le modèle physique",
                "text": "La fonction inject_steam_vapor() ajoute de la pression partielle d'eau (P_H2O) proportionnellement à la pression de vapeur effectivement injectée. HR300 pilote la cible de RHT121.",
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée de pression. RHT121 — humidité relative augmente.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP300", "unit": "mbar",     "desc": "Delta de pression d'injection vapeur."},
                    {"name": "HR300", "unit": "%RH",      "desc": "Consigne d'humidité cible."},
                    {"name": "R300",  "unit": "mbar/min", "desc": "Vitesse d'injection vapeur."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Cette phase apporte la vapeur nécessaire à la réaction EtO.",
            },
            {
                "kind": "impact",
                "label": "DP300",
                "augmente": "Plus de vapeur injectée — humidité plus élevée.",
                "diminue": "Moins de vapeur — risque d'humidité insuffisante pour l'EtO.",
                "supprime": "Phase ignorée si DP300 = 0 — pas de montée en vapeur.",
            },
            {
                "kind": "prudence",
                "text": "HR300 trop élevé peut provoquer de la condensation sur le produit. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_stabilisation_humidite": {
        "id":       "phase_stabilisation_humidite",
        "type":     "phase",
        "title":    "Stabilisation humidité",
        "subtitle": "GRAFCET S6",
        "intro":    "On laisse l'humidité se répartir uniformément dans la chambre après l'injection vapeur, avant les injections de gaz.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La chambre maintient pression et humidité stables pendant T310 minutes. "
                    "La pression descend légèrement vers SP320 (vide doux) pour homogénéiser. "
                    "Le modèle fait relaxer RHT121 vers l'équilibre de pré-exposition."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "TT111, TT112, TT191 — température stable. RHT121 — humidité se stabilise. PT111, PT112 — légère descente vers SP320.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "T310",  "unit": "min",      "desc": "Durée de stabilisation humidité."},
                    {"name": "SP320", "unit": "mbar",     "desc": "Consigne de vide doux en fin de stabilisation."},
                    {"name": "R320",  "unit": "mbar/min", "desc": "Vitesse du vide doux."},
                ],
            },
            {
                "kind": "retenir",
                "text": "La stabilisation assure que toute la charge atteint l'humidité cible avant le gaz.",
            },
            {
                "kind": "impact",
                "label": "T310",
                "augmente": "Homogénéisation plus complète — meilleure uniformité.",
                "diminue": "Humidité potentiellement non homogène dans la charge.",
                "supprime": "Phase ignorée si T310 = 0 — homogénéité de l'humidité simulée potentiellement non atteinte avant le gaz.",
            },
            {
                "kind": "prudence",
                "text": "T310 trop court peut laisser des zones de la charge hors de la fenêtre d'humidité. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_injection_gaz_1": {
        "id":       "phase_injection_gaz_1",
        "type":     "phase",
        "title":    "Injection gaz 1",
        "subtitle": "GRAFCET S8 — EtO (1ère injection)",
        "intro":    "Première injection de gaz EtO dans la chambre. La pression partielle d'EtO augmente de DP330 mbar.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La vanne EtO (PV_EtO) s'ouvre. La pression monte de DP330 mbar "
                    "à la vitesse R330. GT121 (masse EtO injectée, kg) augmente. "
                    "Après l'injection, la chambre stabilise pendant T350 minutes."
                ),
            },
            {
                "kind": "section",
                "heading": "Lien avec le modèle physique",
                "text": "La pression partielle EtO est calculée via la loi des gaz parfaits (eto_p_from_mass). Les injections 1 et 3 sont EtO, les injections 2 et 4 sont azote.",
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée de pression. GT121 — masse EtO cumulée (kg). TT111 — température influence la pression partielle EtO.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP330", "unit": "mbar",     "desc": "Delta de pression d'injection gaz 1."},
                    {"name": "R330",  "unit": "mbar/min", "desc": "Vitesse d'injection (999 = max machine)."},
                    {"name": "T350",  "unit": "min",      "desc": "Temps de stabilisation après gaz 1."},
                ],
            },
            {
                "kind": "retenir",
                "text": "La somme des 4 injections gaz détermine la concentration finale d'EtO dans la chambre.",
            },
            {
                "kind": "impact",
                "label": "DP330",
                "augmente": "Plus d'EtO injecté — concentration plus élevée.",
                "diminue": "Moins d'EtO — concentration finale réduite.",
                "supprime": "Injection désactivée — concentration cible potentiellement non atteinte.",
            },
            {
                "kind": "prudence",
                "text": "La concentration résultante dépend de la somme des 4 injections. Toute modification doit être validée par la démarche qualité.",
            },
        ],
    },

    "phase_injection_gaz_2": {
        "id":       "phase_injection_gaz_2",
        "type":     "phase",
        "title":    "Injection gaz 2",
        "subtitle": "GRAFCET S8 — azote (2ème injection)",
        "intro":    "Deuxième injection de gaz : de l'azote est injecté pour diluer et homogénéiser le mélange EtO / azote dans la chambre.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La vanne azote (PV_N2) s'ouvre. La pression monte de DP390 mbar. "
                    "L'azote dilue légèrement l'EtO et améliore l'homogénéité du mélange. "
                    "Stabilisation pendant T410 minutes."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée de pression. GT121 — ne varie plus (azote injecté, pas EtO).",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP390", "unit": "mbar",     "desc": "Delta de pression d'injection gaz 2."},
                    {"name": "R390",  "unit": "mbar/min", "desc": "Vitesse d'injection."},
                    {"name": "T410",  "unit": "min",      "desc": "Temps de stabilisation après gaz 2."},
                ],
            },
            {
                "kind": "retenir",
                "text": "L'alternance EtO / azote permet d'atteindre la pression totale cible avec la proportion voulue d'EtO.",
            },
            {
                "kind": "impact",
                "label": "DP390",
                "augmente": "Pression totale plus haute — dilution de l'EtO légèrement plus forte.",
                "diminue": "Moins d'azote injecté — mélange moins homogène.",
                "supprime": "Injection désactivée — mélange moins bien réparti.",
            },
            {
                "kind": "prudence",
                "text": "Chaque injection est cumulative. Vérifier la cohérence de la recette globale avant modification.",
            },
        ],
    },

    "phase_injection_gaz_3": {
        "id":       "phase_injection_gaz_3",
        "type":     "phase",
        "title":    "Injection gaz 3",
        "subtitle": "GRAFCET S8 — EtO (3ème injection)",
        "intro":    "Troisième injection : de l'EtO est ajouté pour augmenter la concentration après l'injection azote.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Deuxième injection EtO du cycle (3ème injection au total). "
                    "DP450 est généralement la plus haute des 4 injections (ex. 250 mbar). "
                    "GT121 augmente à nouveau. Stabilisation pendant T470 minutes."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée de pression. GT121 — masse EtO cumulée augmente.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP450", "unit": "mbar",     "desc": "Delta de pression d'injection gaz 3."},
                    {"name": "R450",  "unit": "mbar/min", "desc": "Vitesse d'injection."},
                    {"name": "T470",  "unit": "min",      "desc": "Temps de stabilisation après gaz 3."},
                ],
            },
            {
                "kind": "retenir",
                "text": "C'est souvent l'injection la plus importante en delta de pression — elle définit la majorité de la concentration EtO.",
            },
            {
                "kind": "impact",
                "label": "DP450",
                "augmente": "Concentration EtO finale plus élevée.",
                "diminue": "Concentration finale réduite.",
                "supprime": "Injection désactivée — concentration cible potentiellement insuffisante.",
            },
            {
                "kind": "prudence",
                "text": "Toute modification de DP450 doit être intégrée dans le bilan global des 4 injections. Valider avec la démarche qualité.",
            },
        ],
    },

    "phase_injection_gaz_4": {
        "id":       "phase_injection_gaz_4",
        "type":     "phase",
        "title":    "Injection gaz 4",
        "subtitle": "GRAFCET S8 — azote (4ème injection)",
        "intro":    "Quatrième et dernière injection : azote pour finaliser la mise en pression et stabiliser le mélange avant l'exposition.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Dernière injection d'azote (ex. DP510 = 50 mbar). "
                    "Elle complète la mise en pression totale et améliore l'homogénéité "
                    "du mélange EtO / azote avant l'exposition. "
                    "Stabilisation pendant T530 minutes."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — pression finale du mélange. GT121 — masse EtO injectée totale (ne change pas avec l'azote).",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP510", "unit": "mbar",     "desc": "Delta de pression d'injection gaz 4."},
                    {"name": "R510",  "unit": "mbar/min", "desc": "Vitesse d'injection."},
                    {"name": "T530",  "unit": "min",      "desc": "Temps de stabilisation après gaz 4."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Après l'injection 4, la chambre est prête pour l'exposition EtO.",
            },
            {
                "kind": "impact",
                "label": "DP510",
                "augmente": "Pression totale légèrement plus haute — dilution de l'EtO légèrement plus forte.",
                "diminue": "Moins d'azote — pression totale plus basse.",
                "supprime": "Injection désactivée — mélange sans homogénéisation finale.",
            },
            {
                "kind": "prudence",
                "text": "Modification à valider dans le bilan global des 4 injections. Toute recette modifiée doit passer par la démarche qualité.",
            },
        ],
    },

    "phase_flush_azote": {
        "id":       "phase_flush_azote",
        "type":     "phase",
        "title":    "Flush azote",
        "subtitle": "GRAFCET S8 (entre injections gaz et exposition)",
        "intro":    "Injection d'azote après les 4 injections pour homogénéiser le mélange et stabiliser la pression avant l'exposition.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Un dernier flush d'azote (DP570) assure que le mélange EtO est bien réparti "
                    "dans toute la chambre avant l'exposition. "
                    "Le modèle réduit légèrement GT121 pendant le flush (homogénéisation simulée)."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée légère de pression. GT121 — légèrement réduit (redistribution).",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "DP570", "unit": "mbar",     "desc": "Delta de pression flush azote."},
                    {"name": "R570",  "unit": "mbar/min", "desc": "Vitesse d'injection."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Le flush finalise la composition gazeuse avant l'exposition.",
            },
            {
                "kind": "impact",
                "label": "DP570",
                "augmente": "Homogénéisation plus forte — légère dilution supplémentaire.",
                "diminue": "Flush moins efficace.",
                "supprime": "Phase ignorée si DP570 = 0 — pas de flush final.",
            },
            {
                "kind": "prudence",
                "text": "Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_exposition_eto": {
        "id":       "phase_exposition_eto",
        "type":     "phase",
        "title":    "Exposition EtO",
        "subtitle": "GRAFCET S9 — phase de stérilisation",
        "intro":    "Phase d'attente à température, humidité et pression stables. L'EtO agit sur les micro-organismes pendant la durée T580.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La chambre est maintenue en conditions stables : pression, température (TT111, TT112), "
                    "humidité (RHT121) et concentration EtO (GT121). "
                    "C'est la phase de stérilisation effective. "
                    "Un verrou de sécurité (safety_check) bloque la phase si les conditions sont hors seuil."
                ),
            },
            {
                "kind": "section",
                "heading": "Lien avec le modèle physique",
                "text": "EC580 pilote une correction légère de GT121 pour atteindre la concentration cible. Le modèle maintient la pression par hold_pressure() et relaxe RHT121 vers EXPO_RH_EQ (~51 %RH si DEC actif, ~49,6 %RH sinon).",
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112, TT111, TT112, TT191, RHT121, GT121 — tous les signaux sont actifs pendant l'exposition.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "T580",  "unit": "min",  "desc": "Durée d'exposition EtO."},
                    {"name": "EC580", "unit": "mg/L", "desc": "Concentration cible après 600 s. Pilote une correction de GT121."},
                ],
            },
            {
                "kind": "retenir",
                "text": "T580 doit être respecté — c'est la durée de contact EtO / micro-organismes.",
            },
            {
                "kind": "impact",
                "label": "T580",
                "augmente": "Exposition plus longue — durée simulée de maintien des conditions d'exposition plus longue.",
                "diminue": "Contact EtO plus court — durée simulée d'exposition réduite.",
                "supprime": "Phase ignorée si T580 = 0 — aucune exposition EtO simulée dans le cycle.",
            },
            {
                "kind": "prudence",
                "text": (
                    "Toute modification de T580 ou EC580 doit être validée par une démarche qualité procédé. "
                    "Le guide ne remplace pas cette validation."
                ),
            },
        ],
    },

    "phase_vide_avant_rincage": {
        "id":       "phase_vide_avant_rincage",
        "type":     "phase",
        "title":    "Vide avant rinçage",
        "subtitle": "GRAFCET S10",
        "intro":    "La pompe à vide évacue la majorité du gaz EtO de la chambre. C'est le début du dégazage.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "La chambre descend de la pression d'exposition jusqu'à SP590. "
                    "GT121 (masse EtO) chute de 85 % pendant cette phase. "
                    "Ce vide initial est le geste de dégazage le plus efficace du cycle."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — descente rapide de pression. GT121 — forte réduction de la masse EtO.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP590", "unit": "mbar",     "desc": "Consigne de vide avant rinçage."},
                    {"name": "R590",  "unit": "mbar/min", "desc": "Vitesse de pompage."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Ce vide élimine la majeure partie de l'EtO — c'est l'étape de dégazage la plus efficace.",
            },
            {
                "kind": "impact",
                "label": "SP590",
                "augmente": "Vide moins poussé — plus d'EtO résiduel avant les rinçages.",
                "diminue": "Vide plus profond — moins d'EtO résiduel, phase plus longue.",
                "supprime": "Phase ignorée si SP590 = 0 — dégazage insuffisant.",
            },
            {
                "kind": "prudence",
                "text": "SP590 doit permettre l'extraction suffisante d'EtO pour la sécurité des rinçages suivants. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    "phase_rincage_azote": {
        "id":       "phase_rincage_azote",
        "type":     "phase",
        "title":    "Rinçage azote",
        "subtitle": "GRAFCET S11 — NB620 cycles",
        "intro":    "Cycles répétés casse-vide azote / vide pour diluer les résidus d'EtO dans la chambre.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Chaque cycle : casse-vide azote jusqu'à SP620, stabilisation T630, "
                    "vide jusqu'à SP640, stabilisation T660. "
                    "Répété NB620 fois. "
                    "Chaque cycle dilue et extrait une fraction d'EtO résiduel."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — oscillations de pression par cycle. RHT121 — humidité varie. GT121 — masse EtO diminue progressivement.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP620", "unit": "mbar",     "desc": "Consigne casse-vide azote."},
                    {"name": "R620",  "unit": "mbar/min", "desc": "Vitesse injection azote."},
                    {"name": "T630",  "unit": "min",      "desc": "Stabilisation après casse-vide."},
                    {"name": "SP640", "unit": "mbar",     "desc": "Consigne de vide entre cycles."},
                    {"name": "R640",  "unit": "mbar/min", "desc": "Vitesse du vide."},
                    {"name": "T660",  "unit": "min",      "desc": "Stabilisation après vide."},
                    {"name": "NB620", "unit": "",         "desc": "Nombre de cycles de rinçage azote."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Chaque cycle réduit la concentration résiduelle d'EtO par dilution-extraction.",
            },
            {
                "kind": "impact",
                "label": "NB620",
                "augmente": "Dégazage plus complet — durée de rinçage plus longue.",
                "diminue": "Moins de cycles — résidus EtO potentiellement plus élevés.",
                "supprime": "Phase ignorée si NB620 = 0 — pas de rinçage azote.",
            },
            {
                "kind": "prudence",
                "text": "NB620 doit être suffisant pour respecter les limites de résidus EtO. La validation qualité est obligatoire.",
            },
        ],
    },

    "phase_rincage_air": {
        "id":       "phase_rincage_air",
        "type":     "phase",
        "title":    "Rinçage air",
        "subtitle": "GRAFCET S12 — NB680 cycles",
        "intro":    "Cycles répétés casse-vide air / vide pour finaliser la purge et amener la chambre vers des conditions sûres.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Chaque cycle : casse-vide air jusqu'à SP680, stabilisation T690, "
                    "vide jusqu'à SP700, stabilisation T720. "
                    "Répété NB680 fois. "
                    "Le rinçage air continue la dilution des résidus EtO avec de l'air, "
                    "rapprochant la chambre des conditions atmosphériques."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — montée progressive vers la pression atmosphérique. GT121 — masse EtO continue de diminuer. RHT121 — humidité diminue avec l'air sec.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP680", "unit": "mbar",     "desc": "Consigne casse-vide air (ex. 750 mbar)."},
                    {"name": "R680",  "unit": "mbar/min", "desc": "Vitesse injection air."},
                    {"name": "T690",  "unit": "min",      "desc": "Stabilisation après casse-vide."},
                    {"name": "SP700", "unit": "mbar",     "desc": "Consigne de vide entre cycles (ex. 100 mbar)."},
                    {"name": "R700",  "unit": "mbar/min", "desc": "Vitesse du vide."},
                    {"name": "T720",  "unit": "min",      "desc": "Stabilisation après vide."},
                    {"name": "NB680", "unit": "",         "desc": "Nombre de cycles de rinçage air (ex. 3)."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Le rinçage air ramène la chambre vers des conditions sûres pour l'ouverture.",
            },
            {
                "kind": "impact",
                "label": "NB680",
                "augmente": "Purge plus complète — résidus EtO plus faibles.",
                "diminue": "Purge moins efficace — résidus potentiellement plus élevés.",
                "supprime": "Phase ignorée si NB680 = 0 — pas de rinçage air.",
            },
            {
                "kind": "prudence",
                "text": "NB680 doit permettre d'atteindre les niveaux de résidus exigés. Toute modification nécessite une validation qualité.",
            },
        ],
    },

    "phase_rincage_additionnel": {
        "id":       "phase_rincage_additionnel",
        "type":     "phase",
        "title":    "Rinçage additionnel",
        "subtitle": "GRAFCET S12a — exécutée selon la recette",
        "intro":    "Rinçages supplémentaires si les résidus EtO nécessitent une purge prolongée au-delà des rinçages air standard.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Même principe que le rinçage air, appliqué en cycles additionnels. "
                    "Chaque cycle : casse-vide air (SP740), stabilisation (T750), "
                    "vide (SP760), stabilisation (T780). "
                    "Répété NB740 fois."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — pression. GT121 — résidus EtO continuent de diminuer.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP740", "unit": "mbar",     "desc": "Consigne casse-vide air additionnel."},
                    {"name": "R740",  "unit": "mbar/min", "desc": "Vitesse injection."},
                    {"name": "T750",  "unit": "min",      "desc": "Stabilisation après casse-vide."},
                    {"name": "SP760", "unit": "mbar",     "desc": "Consigne de vide additionnel."},
                    {"name": "R760",  "unit": "mbar/min", "desc": "Vitesse du vide."},
                    {"name": "T780",  "unit": "min",      "desc": "Stabilisation après vide."},
                    {"name": "NB740", "unit": "",         "desc": "Nombre de cycles additionnels."},
                ],
            },
            {
                "kind": "retenir",
                "text": "Cette phase est exécutée selon les paramètres de la recette (NB740 > 0).",
            },
            {
                "kind": "impact",
                "label": "NB740",
                "augmente": "Dégazage additionnel plus long — résidus encore plus faibles.",
                "diminue": "Moins de cycles supplémentaires.",
                "supprime": "Phase désactivée (NB740 = 0) — seuls les rinçages standard sont effectués.",
            },
            {
                "kind": "prudence",
                "text": "La nécessité du rinçage additionnel dépend des résultats de qualification et de la nature du produit. Valider avec la démarche qualité.",
            },
        ],
    },

    "phase_casse_vide_finale": {
        "id":       "phase_casse_vide_finale",
        "type":     "phase",
        "title":    "Casse vide air finale",
        "subtitle": "GRAFCET S13 — fin de cycle",
        "intro":    "Remontée finale à la pression atmosphérique (SP790). Prépare l'ouverture sécurisée de la chambre.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "L'air est admis progressivement jusqu'à la consigne SP790 (ex. 870 mbar). "
                    "C'est la dernière étape avant l'ouverture. "
                    "GT121 diminue encore légèrement avec l'air entrant."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux associés",
                "text": "PT111, PT112 — remontée vers SP790. GT121 — trace résiduelle d'EtO.",
            },
            {
                "kind": "params",
                "items": [
                    {"name": "SP790", "unit": "mbar",     "desc": "Consigne de pression finale (ex. 870 mbar)."},
                    {"name": "R790",  "unit": "mbar/min", "desc": "Vitesse de remontée en pression."},
                ],
            },
            {
                "kind": "retenir",
                "text": "SP790 doit être suffisant pour permettre l'ouverture de la porte en sécurité.",
            },
            {
                "kind": "impact",
                "label": "SP790",
                "augmente": "Pression plus haute — ouverture facilitée mécaniquement.",
                "diminue": "Pression insuffisante — ouverture potentiellement impossible.",
                "supprime": "Phase ignorée si SP790 = 0 — chambre non remontée en pression.",
            },
            {
                "kind": "prudence",
                "text": "SP790 doit correspondre aux spécifications mécaniques de la porte. Valeur cohérente avec la recette validée.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 — POINTS DE VIGILANCE
    # ══════════════════════════════════════════════════════════════════════
    "vigilance": {
        "id":       "vigilance",
        "type":     "menu",
        "title":    "Points de vigilance",
        "subtitle": "Contraintes à prendre en compte lors de la construction ou l'analyse d'un cycle",
        "intro":    (
            "Cette section rappelle les points à prendre en compte lors de la construction "
            "ou de l'analyse d'un cycle. Elle ne remplace pas la lecture des normes applicables "
            "ni la validation qualité / procédé."
        ),
        "show_frieze": False,
        "cards": [
            {
                "title":       "Paramètres critiques du cycle",
                "description": "Paramètres dont la modification impacte directement l'efficacité stérilisante.",
                "badge":       "Critique",
                "target":      "vig_param_critiques",
            },
            {
                "title":       "Traçabilité des recettes",
                "description": "Gestion et enregistrement des recettes en base de données.",
                "badge":       "Traçabilité",
                "target":      "vig_tracabilite",
            },
            {
                "title":       "Validation procédé",
                "description": "Exigences de validation avant tout cycle de production.",
                "badge":       "Validation",
                "target":      "vig_validation",
            },
            {
                "title":       "Contrôle des phases",
                "description": "Activation des phases et interdépendances à surveiller.",
                "badge":       "Contrôle",
                "target":      "vig_controle_phases",
            },
            {
                "title":       "Résidus EtO et aération",
                "description": "Niveaux de résidus après cycle — limites et précautions.",
                "badge":       "Sécurité",
                "target":      "vig_residus",
            },
            {
                "title":       "Limites de la simulation",
                "description": "Ce que le digital twin ne modélise pas ou simplifie.",
                "badge":       "Limites",
                "target":      "vig_limites",
            },
        ],
        "blocks": [],
    },

    "vig_param_critiques": {
        "id":       "vig_param_critiques",
        "type":     "detail",
        "title":    "Paramètres critiques du cycle",
        "subtitle": "",
        "intro":    "Certains paramètres ont un impact direct sur l'efficacité stérilisante. Leur modification doit toujours faire l'objet d'une évaluation procédé.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Paramètres d'exposition",
                "text": (
                    "T580 (durée d'exposition) et EC580 (concentration cible EtO) "
                    "définissent le contact effectif EtO / micro-organismes. "
                    "Ce sont les paramètres les plus critiques du cycle."
                ),
            },
            {
                "kind": "section",
                "heading": "Humidité et température",
                "text": (
                    "HR260, HR300 et TS_JACKET contrôlent les conditions physico-chimiques "
                    "de la chambre pendant le conditionnement et l'exposition. "
                    "L'EtO est plus efficace dans une plage d'humidité et de température définies."
                ),
            },
            {
                "kind": "section",
                "heading": "Injections de gaz",
                "text": (
                    "Les quatre DP (DP330, DP390, DP450, DP510) définissent la concentration totale d'EtO. "
                    "Leur somme doit correspondre à la concentration validée dans la recette procédé."
                ),
            },
            {
                "kind": "prudence",
                "text": "Toute modification d'un paramètre critique doit être évaluée et documentée par la démarche qualité avant mise en production.",
            },
        ],
    },

    "vig_tracabilite": {
        "id":       "vig_tracabilite",
        "type":     "detail",
        "title":    "Traçabilité des recettes",
        "subtitle": "",
        "intro":    "La base de données MySQL enregistre chaque recette avec son nom, sa version et la date de mise à jour.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Enregistrement",
                "text": (
                    "Toute recette peut être sauvegardée, rechargée ou supprimée depuis "
                    "le formulaire recette (boutons Nouvelle recette / Charger recette / Enregistrer recette). "
                    "La base de données conserve l'historique des modifications."
                ),
            },
            {
                "kind": "section",
                "heading": "Cohérence",
                "text": (
                    "Avant de lancer une simulation, vérifier que la recette affichée correspond "
                    "bien à la recette validée. "
                    "Le nom de recette et la version sont des indicateurs de traçabilité."
                ),
            },
            {
                "kind": "retenir",
                "text": "Une recette non enregistrée est perdue à la fermeture de l'application.",
            },
            {
                "kind": "prudence",
                "text": "La traçabilité numérique ne remplace pas la gestion documentaire qualité de l'entreprise.",
            },
        ],
    },

    "vig_validation": {
        "id":       "vig_validation",
        "type":     "detail",
        "title":    "Validation procédé",
        "subtitle": "",
        "intro":    "La simulation est un outil d'aide à la compréhension. Elle ne valide pas une recette pour la production.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Ce que la simulation fait",
                "text": (
                    "Elle calcule les courbes de pression, température, humidité et masse EtO "
                    "à partir d'une recette. Elle permet de visualiser et comparer un cycle simulé "
                    "à un cycle réel issu des rapports machine."
                ),
            },
            {
                "kind": "section",
                "heading": "Ce que la simulation ne fait pas",
                "text": (
                    "Elle ne garantit pas la stérilité du produit. "
                    "Elle ne valide pas une recette pour la production. "
                    "Elle ne remplace pas les essais biologiques ni la qualification procédé."
                ),
            },
            {
                "kind": "retenir",
                "text": "Toute recette destinée à la production doit être validée par une démarche qualité indépendante de la simulation.",
            },
            {
                "kind": "prudence",
                "text": "Le guide et la simulation sont des outils pédagogiques et d'analyse. La responsabilité de la validation reste à l'utilisateur et aux équipes qualité.",
            },
        ],
    },

    "vig_controle_phases": {
        "id":       "vig_controle_phases",
        "type":     "detail",
        "title":    "Contrôle des phases",
        "subtitle": "",
        "intro":    "Certaines phases sont exécutées seulement si leur paramètre de déclenchement est non nul.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Phases pilotées par la recette",
                "text": (
                    "Préconditionnement (T130 > 0), Test de fuite haut (SP170 > 0), "
                    "Dilution azote (NB220 > 0), Conditionnement dynamique (T250 > 0), "
                    "Rinçage additionnel (NB740 > 0). "
                    "Si le paramètre est à zéro, la phase est sautée sans message d'erreur."
                ),
            },
            {
                "kind": "section",
                "heading": "Interdépendances",
                "text": (
                    "L'état de fin d'une phase (pression, humidité) est l'état de départ de la suivante. "
                    "Désactiver ou modifier une phase impacte toutes les phases suivantes."
                ),
            },
            {
                "kind": "retenir",
                "text": "Vérifier l'activation de toutes les phases critiques avant de lancer la simulation.",
            },
            {
                "kind": "prudence",
                "text": "Ne jamais supprimer une phase sans évaluer l'impact sur le procédé. Certaines phases ne peuvent pas être supprimées sans risque.",
            },
        ],
    },

    "vig_residus": {
        "id":       "vig_residus",
        "type":     "detail",
        "title":    "Résidus EtO et aération",
        "subtitle": "",
        "intro":    "L'EtO est un agent alkylant toxique. Les résidus sur le produit après le cycle doivent respecter des limites strictes.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Dégazage dans la simulation",
                "text": (
                    "GT121 (masse EtO en kg) diminue tout au long des phases de rinçage. "
                    "Le modèle simule une réduction progressive mais ne calcule pas "
                    "les résidus sur le produit."
                ),
            },
            {
                "kind": "section",
                "heading": "Rinçages et aération",
                "text": (
                    "NB620 (rinçages azote) et NB680 (rinçages air) sont les leviers principaux "
                    "de dégazage. Leur nombre doit être suffisant pour respecter les limites "
                    "de résidus définies dans la qualification procédé."
                ),
            },
            {
                "kind": "retenir",
                "text": "Le modèle de simulation ne calcule pas les résidus EtO sur le produit — seule la qualification procédé le valide.",
            },
            {
                "kind": "prudence",
                "text": "Les niveaux de résidus acceptables dépendent de la nature du produit et de sa destination. Consulter la démarche qualité.",
            },
        ],
    },

    "vig_limites": {
        "id":       "vig_limites",
        "type":     "detail",
        "title":    "Limites de la simulation",
        "subtitle": "",
        "intro":    "Le digital twin est un modèle hybride calibré sur des cycles réels. Il comporte des simplifications.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Ce que le modèle simplifie",
                "text": (
                    "La cinétique de stérilisation biologique n'est pas modélisée. "
                    "Les résidus EtO sur le produit ne sont pas calculés. "
                    "La géométrie de la chambre et la distribution spatiale des gaz sont supposées homogènes."
                ),
            },
            {
                "kind": "section",
                "heading": "Calibration",
                "text": (
                    "Les constantes physiques (K111_*, K112_*, VAPOR_RELAX_*, RATE_*) "
                    "sont calibrées sur les cycles réels. "
                    "Toute dérive machine peut rendre la calibration inadaptée."
                ),
            },
            {
                "kind": "retenir",
                "text": "La simulation reproduit le comportement physique — elle ne prédit pas la conformité biologique.",
            },
            {
                "kind": "prudence",
                "text": "En cas d'écart significatif entre simulé et réel, vérifier la calibration du modèle avant toute conclusion.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 — AIDE À LA CRÉATION D'UNE RECETTE
    # Partage les mêmes nœuds de détail que la Section 1
    # ══════════════════════════════════════════════════════════════════════
    "aide_recette": {
        "id":       "aide_recette",
        "type":     "menu",
        "title":    "Aide à la création d'une recette",
        "subtitle": "Quelle phase voulez-vous configurer ou comprendre ?",
        "intro":    (
            "Choisissez une phase pour comprendre ses paramètres modifiables, "
            "leur effet sur la simulation et les précautions à prendre. "
            "Ce guide est purement explicatif — il ne modifie rien dans le formulaire."
        ),
        "show_frieze": False,
        "cards": [
            {"title": p["label"],
             "description": "Paramètres et effets",
             "badge": "Recette",
             "target": p["node_id"]}
            for p in PHASES_ORDER
        ],
        "blocks": [],
    },

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4 — COMPRENDRE LE DIGITAL TWIN
    # ══════════════════════════════════════════════════════════════════════
    "digital_twin": {
        "id":       "digital_twin",
        "type":     "menu",
        "title":    "Comprendre le digital twin",
        "subtitle": "Architecture et couches du modèle de simulation",
        "intro":    "Le digital twin est composé de plusieurs couches qui collaborent pour simuler le cycle. Choisissez une couche pour comprendre son rôle.",
        "show_frieze": False,
        "cards": [
            {"title": "Vue générale",          "description": "Architecture globale du jumeau numérique.",              "badge": "Architecture", "target": "dt_vue_generale"},
            {"title": "Couche recette",        "description": "Paramètres d'entrée du cycle simulé.",                   "badge": "Données",      "target": "dt_couche_recette"},
            {"title": "Couche GRAFCET",        "description": "Séquencement des phases et transitions.",                "badge": "Séquencement", "target": "dt_couche_grafcet"},
            {"title": "Couche physique",       "description": "Modèles mathématiques de pression, température, vapeur.","badge": "Modèle",       "target": "dt_couche_physique"},
            {"title": "Couche signaux",        "description": "Signaux simulés et leurs constantes.",                   "badge": "Signaux",      "target": "dt_couche_signaux"},
            {"title": "Simulation théorique",  "description": "Comment la simulation calcule le cycle complet.",        "badge": "Calcul",       "target": "dt_sim_theorique"},
            {"title": "Comparaison réel / simulé", "description": "Alignement et comparaison des courbes.",             "badge": "Analyse",      "target": "dt_comparaison"},
            {"title": "Extraction PDF",        "description": "Import des cycles réels depuis les rapports machine.","badge": "Import",       "target": "dt_extraction_pdf"},
            {"title": "Base de données recettes", "description": "Persistance et chargement des recettes (MySQL).",     "badge": "Base de données","target": "dt_base_donnees"},
            {"title": "Limites du modèle",     "description": "Ce que le modèle ne modélise pas.",                      "badge": "Limites",      "target": "dt_limites"},
        ],
        "blocks": [],
    },

    "dt_vue_generale": {
        "id":       "dt_vue_generale",
        "type":     "architecture",
        "title":    "Vue générale du digital twin",
        "subtitle": "",
        "intro":    "Le digital twin est une application bureau Python / PySide6 qui simule un cycle EtO à partir d'une recette.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Principe",
                "text": (
                    "L'utilisateur saisit une recette (paramètres par phase), lance la simulation, "
                    "et obtient les courbes des 7 signaux pour tout le cycle. "
                    "Il peut ensuite comparer la courbe simulée à un cycle réel importé depuis un rapport PDF."
                ),
            },
            {
                "kind": "section",
                "heading": "Couches du modèle",
                "text": (
                    "Recette → GRAFCET (séquencement) → Physique (calculs) → Signaux (sortie). "
                    "Les couches sont dans app/model/. L'interface est dans app/ui/ et app/recipe_tab.py."
                ),
            },
            {
                "kind": "section",
                "heading": "Navigation",
                "text": (
                    "Trois pages principales : Accueil, Simuler un cycle, Analyser un cycle réel. "
                    "La comparaison simulé / réel est accessible depuis l'onglet Résultats de simulation."
                ),
            },
            {
                "kind": "retenir",
                "text": "Toute la simulation est locale — aucun service externe n'est appelé.",
            },
        ],
    },

    "dt_couche_recette": {
        "id":       "dt_couche_recette",
        "type":     "architecture",
        "title":    "Couche recette",
        "subtitle": "Fichier : app/recipe_tab.py",
        "intro":    "La recette est le point d'entrée de la simulation. Elle contient tous les paramètres par phase.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "RecipeTab (formulaire) expose get_recipe_data() qui retourne un dictionnaire "
                    "{phase: {paramètre: valeur}}. Ce dictionnaire est passé à GrafcetCycle pour la simulation."
                ),
            },
            {
                "kind": "section",
                "heading": "Données reçues",
                "text": "Saisie de l'utilisateur : valeurs numériques pour chaque paramètre de chaque phase.",
            },
            {
                "kind": "section",
                "heading": "Données produites",
                "text": "Dictionnaire recette transmis à la couche GRAFCET. Persistance MySQL via recipe_repository.",
            },
            {
                "kind": "section",
                "heading": "Paramètres généraux",
                "text": "TS_JACKET (consigne double enveloppe, °C), T_INIT (température initiale chambre, °C), RH_INIT (humidité initiale, %RH).",
            },
            {
                "kind": "retenir",
                "text": "Toute modification de recette doit être sauvegardée avant de fermer l'application.",
            },
        ],
    },

    "dt_couche_grafcet": {
        "id":       "dt_couche_grafcet",
        "type":     "architecture",
        "title":    "Couche GRAFCET / séquencement",
        "subtitle": "Fichier : app/model/grafcet.py",
        "intro":    "GrafcetCycle orchestre l'enchaînement des phases et délègue les calculs à la couche physique.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "Implémente la machine à états du cycle (S0 à S13). "
                    "Pour chaque état, calcule la durée de la phase à partir des paramètres recette, "
                    "puis avance la simulation pas à pas (DT_INTERNAL = 0,5 min)."
                ),
            },
            {
                "kind": "section",
                "heading": "États GRAFCET du code",
                "text": (
                    "S0 Initiale → S1 Préconditionnement → S2 Vide initial → S3 Test fuite bas → "
                    "S4 Test fuite haut → S4a Dilution azote → S4b Conditionnement dynamique → "
                    "S5 Injection vapeur → S6 Stabilisation humidité → S8 Injections gaz × 4 + Flush → "
                    "S9 Exposition EtO → S10 Vide avant rinçage → S11 Rinçage azote → "
                    "S12 Rinçage air → S12a Rinçage additionnel → S13 Casse vide finale."
                ),
            },
            {
                "kind": "section",
                "heading": "Phases pilotées par la recette",
                "text": "S1, S4, S4a, S4b et S12a sont sautées si leur paramètre de déclenchement est nul dans la recette.",
            },
            {
                "kind": "section",
                "heading": "Données produites",
                "text": "Liste de Segment(name, duration, start_state, end_state) — un segment par pas de simulation. Consommée par PlotTab pour les courbes.",
            },
            {
                "kind": "retenir",
                "text": "Le code implémente 16 états simplifiés — pas les 92 sous-étapes du GRAFCET détaillé de l'AF.",
            },
        ],
    },

    "dt_couche_physique": {
        "id":       "dt_couche_physique",
        "type":     "architecture",
        "title":    "Couche physique",
        "subtitle": "Fichier : app/model/physics.py, signals.py",
        "intro":    "La couche physique calcule l'évolution des signaux à chaque pas de simulation à partir des actionneurs actifs.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Loi des gaz parfaits",
                "text": (
                    "La pression partielle d'EtO est calculée par eto_p_from_mass() : "
                    "P = (m / M_ETO) × R × T / V_CUVE / 100. "
                    "Cela relie masse injectée (GT121), température (TT111) et pression partielle EtO."
                ),
            },
            {
                "kind": "section",
                "heading": "Bilan thermique",
                "text": (
                    "TT111 (chambre) évolue sous l'effet de la paroi (K111_WALL), "
                    "des injections vapeur (K111_STEAM) et gaz (K111_GAS), "
                    "et des pertes thermiques (K111_LOSS). "
                    "TT191 (sonde charge) suit TT111 avec un retard (K191_FROM_111)."
                ),
            },
            {
                "kind": "section",
                "heading": "Formule de Magnus (humidité)",
                "text": (
                    "La pression de saturation de la vapeur d'eau est calculée par compute_water_saturation_pressure_mbar() "
                    "via la formule de Magnus : Psat = 6,1078 × 10^(7,5×T / (237,3+T)). "
                    "RHT121 = P_H2O / Psat × 100."
                ),
            },
            {
                "kind": "section",
                "heading": "Actionneurs",
                "text": (
                    "ActuatorState (app/model/actuators.py) définit quelles vannes sont ouvertes "
                    "(VP_vacuum, PV_steam, PV_EtO, PV_N2, EH_jacket, RC_recirc, CP_jacket). "
                    "La couche physique adapte ses calculs en fonction de ces états."
                ),
            },
            {
                "kind": "retenir",
                "text": "Le modèle est hybride : physique pour les principes, empirique pour les constantes de calibration.",
            },
        ],
    },

    "dt_couche_signaux": {
        "id":       "dt_couche_signaux",
        "type":     "architecture",
        "title":    "Couche signaux",
        "subtitle": "Fichier : app/model/signals.py",
        "intro":    "Les 7 signaux simulés correspondent aux capteurs réels de la machine.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Les 7 signaux du code",
                "text": (
                    "PT111 — pression chambre capteur 1 (mbar). "
                    "PT112 — pression chambre capteur 2 (mbar). "
                    "TT111 — température chambre capteur 1 (°C). "
                    "TT112 — température paroi / double enveloppe dynamique (°C). "
                    "TT191 — température sonde de charge (°C). "
                    "RHT121 — humidité relative (%RH). "
                    "GT121 — masse EtO injectée (kg)."
                ),
            },
            {
                "kind": "section",
                "heading": "Note sur TT112",
                "text": (
                    "Dans le code, TT112 représente la température dynamique de paroi "
                    "(double enveloppe / jacket), pilotée par K112_TRACK et K112_PRESSURE. "
                    "Dans les rapports machine, TT112 est listé comme capteur de chambre 2 — "
                    "le comportement simulé peut différer légèrement de la mesure réelle."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux internes (non affichés)",
                "text": "P_H2O — pression partielle vapeur (mbar). P_H2O_LOAD — humidité stockée dans la charge. Ces valeurs sont utilisées en interne pour calculer RHT121.",
            },
            {
                "kind": "section",
                "heading": "Offsets capteurs",
                "text": "DELTA_PT111 = −1,0 mbar et DELTA_PT112 = +1,0 mbar — décalages calibrés pour reproduire la différence inter-capteurs observée sur les cycles réels.",
            },
            {
                "kind": "retenir",
                "text": "Aucun signal de concentration EtO en temps réel — GT121 est une masse injectée, pas une mesure de concentration instantanée.",
            },
        ],
    },

    "dt_sim_theorique": {
        "id":       "dt_sim_theorique",
        "type":     "architecture",
        "title":    "Simulation théorique",
        "subtitle": "Fichiers : app/model/grafcet.py, sterilization_model.py",
        "intro":    "La simulation calcule le cycle complet en avançant le temps par pas de 0,5 minute.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Déroulement",
                "text": (
                    "GrafcetCycle.simulate() appelle _run(), qui enchaîne les méthodes de chaque phase. "
                    "Chaque phase est découpée en pas de DT_INTERNAL = 0,5 min. "
                    "À chaque pas, step_physics() met à jour PT111, PT112, TT111, TT112, TT191, RHT121, GT121."
                ),
            },
            {
                "kind": "section",
                "heading": "Sorties",
                "text": (
                    "La simulation retourne une liste de Segment. "
                    "Chaque segment a un nom de phase, une durée, et les états début / fin. "
                    "PlotTab trace les courbes à partir de ces segments."
                ),
            },
            {
                "kind": "section",
                "heading": "Durée calculée",
                "text": (
                    "La durée de chaque phase n'est pas un paramètre direct. "
                    "Elle est calculée par safe_duration_from_pressure() à partir des consignes et des vitesses. "
                    "Seul T130, T160, T190, T250, T310, T350, T410, T470, T530, T580, T630, T660, T690, T720, T750, T780 sont des durées directes."
                ),
            },
            {
                "kind": "retenir",
                "text": "La durée totale du cycle est la somme des durées de tous les segments — elle n'est pas saisie, elle est calculée.",
            },
        ],
    },

    "dt_comparaison": {
        "id":       "dt_comparaison",
        "type":     "architecture",
        "title":    "Comparaison réel / simulé",
        "subtitle": "Fichiers : app/analysis/, app/comparison_tab.py",
        "intro":    "L'application permet de superposer les courbes simulées et les courbes réelles d'un cycle importé.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Principe",
                "text": (
                    "Après simulation, le bouton « Comparer à un cycle réel » ouvre la page d'analyse. "
                    "L'utilisateur importe un rapport PDF (ou CSV) et les courbes sont alignées puis superposées."
                ),
            },
            {
                "kind": "section",
                "heading": "Alignement temporel",
                "text": (
                    "La couche app/analysis/ aligne les deux cycles par phases : "
                    "sim_interpolator.py, time_aligner.py, comparator.py. "
                    "Plusieurs stratégies d'alignement sont disponibles (interpolation, normalisation par phase, resynchronisation)."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux comparés",
                "text": "PT111, PT112, TT111, TT112, TT191, RHT121 — tous sauf GT121 (non mesuré dans les rapports machine).",
            },
            {
                "kind": "retenir",
                "text": "La comparaison met en évidence les écarts entre le modèle et la machine réelle — utile pour la calibration.",
            },
        ],
    },

    "dt_extraction_pdf": {
        "id":       "dt_extraction_pdf",
        "type":     "architecture",
        "title":    "Extraction PDF",
        "subtitle": "Fichier : eto_pdf_extractor.py",
        "intro":    "Les rapports de cycle machine (PDF) sont parsés pour extraire les données tabulaires du cycle réel.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "eto_pdf_extractor.py lit les fichiers PDF des rapports machine "
                    "et extrait les colonnes de la table « Étapes de cycle » : "
                    "temps, PT111, PT112, TT111, TT112, TT191, RHT121, GT121."
                ),
            },
            {
                "kind": "section",
                "heading": "Données reçues / produites",
                "text": (
                    "Reçoit : chemin vers un fichier PDF ou CSV. "
                    "Produit : DataFrame pandas avec les 7 signaux horodatés, "
                    "consommé par la page d'analyse."
                ),
            },
            {
                "kind": "retenir",
                "text": "Cette partie est à compléter selon l'architecture réelle du projet si le format PDF évolue.",
            },
            {
                "kind": "prudence",
                "text": "Le parseur est calibré sur le format des rapports machine. Un changement de format de rapport peut nécessiter une mise à jour du parseur.",
            },
        ],
    },

    "dt_base_donnees": {
        "id":       "dt_base_donnees",
        "type":     "architecture",
        "title":    "Base de données recettes",
        "subtitle": "Fichiers : app/database/",
        "intro":    "Les recettes sont persistées dans une base MySQL locale (MAMP ou équivalent).",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Rôle",
                "text": (
                    "recipe_repository.py expose save_recipe(), get_recipe_by_id(), "
                    "get_all_recipes(), update_recipe(), deactivate_recipe(). "
                    "connection.py gère la connexion MySQL."
                ),
            },
            {
                "kind": "section",
                "heading": "Données stockées",
                "text": (
                    "Chaque recette est stockée avec : nom, version, type de cycle, "
                    "données JSON de tous les paramètres, date de mise à jour. "
                    "La suppression est une désactivation logique (pas une suppression physique)."
                ),
            },
            {
                "kind": "section",
                "heading": "Prérequis",
                "text": "MySQL / MAMP doit être démarré avant d'utiliser les fonctions de base de données. Un message d'erreur s'affiche si la connexion échoue.",
            },
            {
                "kind": "retenir",
                "text": "La base de données est locale — aucune recette n'est envoyée vers un serveur externe.",
            },
        ],
    },

    "dt_limites": {
        "id":       "dt_limites",
        "type":     "architecture",
        "title":    "Limites du modèle",
        "subtitle": "",
        "intro":    "Le digital twin est un modèle calibré sur un ensemble limité de cycles. Il comporte des hypothèses simplificatrices.",
        "show_frieze": False,
        "cards": [],
        "blocks": [
            {
                "kind": "section",
                "heading": "Hypothèses du modèle",
                "text": (
                    "La chambre est supposée homogène (pas de gradient spatial). "
                    "La cinétique biologique de stérilisation n'est pas modélisée. "
                    "La charge (produit + emballages) est représentée uniquement par P_H2O_LOAD."
                ),
            },
            {
                "kind": "section",
                "heading": "Calibration",
                "text": (
                    "Les constantes sont calibrées sur 3 cycles de référence. "
                    "Une dérive machine ou un changement de chargement peut dégrader la précision."
                ),
            },
            {
                "kind": "section",
                "heading": "Signaux non simulés",
                "text": (
                    "Concentration EtO instantanée en mg/L — GT121 est une masse injectée, "
                    "pas une mesure de concentration dans le temps. "
                    "Résidus EtO sur le produit après cycle — non calculés."
                ),
            },
            {
                "kind": "retenir",
                "text": "En cas d'écart important simulé / réel, recalibrer le modèle plutôt que d'interpréter l'écart comme une anomalie machine.",
            },
            {
                "kind": "prudence",
                "text": "Cette partie est à compléter selon l'architecture réelle du projet si le modèle évolue.",
            },
        ],
    },

}
