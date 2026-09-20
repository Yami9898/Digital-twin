# Calibration versionnée — Digital Twin EtO

## Aperçu

Ce module implémente une calibration versionnée du modèle grey-box EtO par **moindres carrés non linéaires**. Il garantit un retour arrière sûr : `signals.py` n'est jamais modifié.

---

## Architecture des instantanés (retour arrière sûr)

```
data/
├── calibrations/
│   ├── default.json          ← valeurs usine (auto-créé depuis signals.py)
│   ├── calibration_001.json
│   ├── calibration_002.json
│   └── ...
└── active_calibration.json   ← {"active": "calibration_002"}
```

### Principe

| Couche | Rôle |
|--------|------|
| `signals.py` | Valeurs physiques **immuables** — socle usine, jamais modifié |
| `data/calibrations/*.json` | Instantanés versionnés des coefficients calibrés |
| `data/active_calibration.json` | Pointeur vers l'instantané actif |
| `coefficient_store.py` | Applique les deltas JSON aux modules du modèle au runtime |

**Au démarrage**, `main.py` lit `active_calibration.json` et patche les trois modules Python (`signals`, `physics`, `grafcet`) avec les coefficients de l'instantané actif via `setattr`. Le code source reste intact.

**Retour arrière** = changer le pointeur `active_calibration.json` sur `"default"` et restaurer les valeurs de `signals.py`. Aucun instantané n'est supprimé par défaut.

---

## Méthode de calibration

### Algorithme

**scipy.optimize.least_squares** avec `method='trf'` (Trust Region Reflective).

Minimise la somme pondérée des résidus au carré :

```
J(θ) = Σ_cycles Σ_points Σ_var  w_var · [sim_var(θ, t) − real_var(t)]²
```

### Variables calibrées

| Variable | Pondération | Justification |
|----------|-------------|---------------|
| TT111 (°C) | 1/40 | Plage typique ~40 °C |
| TT112 (°C) | 1/40 | Plage typique ~40 °C |
| TT191 (°C) | 1/40 | Plage typique ~40 °C |
| RHT121 (%) | 1/100 | Plage 0–100 % |

La pression n'est **pas** calibrée : elle est pilotée par consigne recette.

### Point de départ

Les valeurs usine de `signals.py` (`FACTORY_DEFAULTS`) servent de point de départ physique pour l'optimiseur. Cela garantit que les coefficients initiaux correspondent à un comportement physiquement raisonnable.

### Bornes physiques

Chaque coefficient a des bornes inférieures et supérieures définies dans `CALIBRATABLE_BOUNDS` (ex. taux de relaxation ≥ 0, humidité ∈ [5, 45] %RH). La méthode TRF respecte ces bornes à chaque itération.

### Fonction résidu

Pour un vecteur θ :
1. `coefficient_store.override(θ)` patche temporairement les modules du modèle
2. `SterilizationModel(recipe).simulate()` produit les segments simulés
3. `_sim_at(segments, t_real, var)` interpole la valeur simulée à l'instant réel
4. Résidu = `w_var × (sim_val − real_val)`
5. Restauration des valeurs précédentes à la sortie du context manager

### Cycles calibration vs validation

- **Calibration** : participent à l'optimisation (minimisation J(θ))
- **Validation** : évalués après optimisation, pas utilisés pour calibrer (mesure de généralisation)

---

## Paramètres calibrables

| Nom | Plage | Impact |
|-----|-------|--------|
| `K112_TRACK` | [0.001, 0.30] | Vitesse de suivi TT112 → consigne |
| `K112_PRESSURE` | [0, 0.02] | Effet pression sur TT112 |
| `VAPOR_RELAX_EXPO` | [0.005, 0.30] | Relaxation RH phase exposition |
| `VAPOR_RELAX_RINSE` | [0.005, 0.30] | Relaxation RH rinçages |
| `VAPOR_RELAX_STAB` | [0.005, 0.30] | Relaxation RH stabilisation |
| `EXPO_RH_EQ` | [30, 75] % | Cible RH exposition (DEC actif) |
| `EXPO_DRY_RH_EQ` | [20, 65] % | Cible RH exposition (DEC inactif) |
| `RINSE_BREAK_RH_EQ` | [10, 45] % | Cible RH casse-vide rinçage |
| `RINSE_VAC_RH_EQ` | [5, 35] % | Cible RH vide rinçage |
| `PREEXPO_RH_EQ` | [30, 70] % | Cible RH stabilisation vapeur |
| `LOAD_DESORPTION_RATE` | [0.01, 0.40] | Vitesse désorption charge |
| `LOAD_ABSORPTION_RATE` | [0.001, 0.08] | Vitesse absorption charge |
| `RINSE_RH_FLOOR` | [5, 35] % | Plancher RH pendant rinçages |
| `STEAM_TARGET_RELAX` | [0.05, 1.0] | Vitesse pilotage vapeur HR300 |
| `STEAM_TO_VAPOR_GAIN` | [0.05, 1.5] | Gain injection vapeur → P_H2O |
| `RATE_VACUUM_FROM_ATM` | [20, 200] mbar/min | Vitesse pompe à vide depuis ATM |
| `RATE_VACUUM_MID` | [10, 150] mbar/min | Vitesse pompe à vide depuis ~400 mbar |
| `RATE_STEAM` | [3, 40] mbar/min | Vitesse injection vapeur |
| `RATE_N2_BREAK_SLOW` | [10, 150] mbar/min | Vitesse casse-vide azote lente |
| `RATE_N2_RINSE` | [10, 120] mbar/min | Vitesse injection azote rinçage |

---

## Structure du code

```
app/calibration/
├── __init__.py
├── coefficient_store.py          # Couche de patch runtime (singleton)
├── snapshot_manager.py           # CRUD instantanés JSON + activation
├── least_squares_calibrator.py   # Algorithme scipy + métriques
└── README.md                     # Ce fichier

app/ui/
└── calibration_page.py           # Interface utilisateur (PySide6)
```

---

## Sécurité du retour arrière

1. `signals.py` n'est **jamais** écrit — il est lu une seule fois à l'import pour `FACTORY_DEFAULTS`.
2. `coefficient_store.override()` sauvegarde les valeurs courantes avant le patch et les restaure à la sortie, même en cas d'exception.
3. L'instantané `default` est protégé : il est auto-créé mais jamais écrasé ni supprimé.
4. Chaque calibration crée un **nouvel** instantané numéroté (`calibration_NNN`), sans modifier les précédents.
5. Le pointeur `active_calibration.json` est le seul fichier modifié lors d'un changement de calibration active — un simple retour à `"default"` suffit à restaurer l'état usine.
