"""
app/guide/guide_style.py
Palette Aurora — identité visuelle du module guide de simulation.

Distincte du vert principal (#009990) de l'application principale.
Le guide = espace d'exploration / pédagogie. L'application = outil industriel.

Centraliser toutes les constantes ici facilite les ajustements futurs.
"""

# ── Couleurs de base ──────────────────────────────────────────────────────────
GUIDE_BG      = "#F7F8FF"   # Fond général du guide
INDIGO_DEEP   = "#243B6B"   # Indigo profond — header, titres, pastilles
VIOLET_SOFT   = "#6C63FF"   # Violet doux — accent recette, impact "diminuer"
CYAN_BRIGHT   = "#00B8D9"   # Cyan lumineux — accent processus, timeline
BLUE_LIGHT    = "#EAF7FF"   # Bleu clair — fond blocs « Rôle »
LAVENDER      = "#EEF0FF"   # Lavande — fond blocs « Paramètres »
AMBER_SOFT    = "#FFB84D"   # Ambre doux — accent vigilance (réservé)
TEXT          = "#1F2933"   # Texte principal
BORDER        = "#D8DDF0"   # Bordures légères
WHITE         = "#FFFFFF"

# ── Alertes / Prudence ────────────────────────────────────────────────────────
CAUTION_BG     = "#FFF3D6"   # Fond blocs Prudence (orange universel)
CAUTION_TEXT   = "#B86B00"   # Texte blocs Prudence
CAUTION_BORDER = "#F5C06A"   # Bordure blocs Prudence

# ── Blocs de contenu ──────────────────────────────────────────────────────────
ROLE_BG      = "#EAF7FF"    # Blocs « Rôle »
SIGNALS_BG   = "#E3F8FC"    # Blocs « Signaux associés » / « Lien modèle »
PARAMS_BG    = "#EEF0FF"    # Blocs « Paramètres »
RETENIR_BG   = "#E8ECF7"    # Blocs « À retenir »
RETENIR_ACC  = INDIGO_DEEP  # Accent « À retenir »

# ── Cartes mission (écran d'accueil) ─────────────────────────────────────────
MISSION_PROCESSUS = CYAN_BRIGHT   # Comprendre le processus EtO
MISSION_VIGILANCE = AMBER_SOFT    # Points de vigilance
MISSION_RECETTE   = VIOLET_SOFT   # Aide à la création d'une recette
MISSION_DT        = INDIGO_DEEP   # Comprendre le digital twin

# ── Impact triptyque ─────────────────────────────────────────────────────────
IMPACT_AUG_BG = "#E0F7FC"   # Fond Augmenter
IMPACT_AUG_AC = CYAN_BRIGHT  # Accent Augmenter
IMPACT_DIM_BG = "#EEF0FF"   # Fond Diminuer
IMPACT_DIM_AC = VIOLET_SOFT  # Accent Diminuer
IMPACT_SUP_BG = "#FFF3D6"   # Fond Supprimer
IMPACT_SUP_AC = "#E65100"   # Accent Supprimer

# ── Architecture Digital Twin ─────────────────────────────────────────────────
LAYER_RECETTE     = VIOLET_SOFT
LAYER_GRAFCET     = INDIGO_DEEP
LAYER_PHYSIQUE    = CYAN_BRIGHT
LAYER_SIGNAUX     = "#4FC3F7"   # Bleu ciel (distinct du cyan bright)
LAYER_COURBES     = "#26C6DA"   # Cyan intermédiaire
LAYER_COMPARAISON = AMBER_SOFT
