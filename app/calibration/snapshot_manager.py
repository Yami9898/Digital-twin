"""
app/calibration/snapshot_manager.py
Gestion des instantanés de calibration versionnés.

Arborescence :
  <projet>/data/calibrations/default.json          — usine (auto-créé)
  <projet>/data/calibrations/calibration_001.json
  <projet>/data/calibrations/calibration_002.json
  ...
  <projet>/data/active_calibration.json             — {"active": "default"}

Format d'un instantané :
  {
    "id":          "calibration_003",
    "created_at":  "2026-06-02T14:30:00",
    "label":       "Calibration 3",
    "cycles_used": [{"pdf": "cycle_A.pdf", "recipe_id": 5, "role": "calibration"}, ...],
    "coefficients": {"K112_TRACK": 0.045, ...},
    "metrics":     {"TT111": {"rmse": 1.2, "mae": 0.9}, ...},
    "parent":      "calibration_002"
  }

L'instantané "default" contient les valeurs usine de signals.py et ne peut
pas être supprimé ni écrasé : il est le point de retour ultime.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.calibration.coefficient_store import FACTORY_DEFAULTS, apply_snapshot, restore_defaults

# ── Chemins ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR      = _PROJECT_ROOT / "data" / "calibrations"
ACTIVE_FILE   = _PROJECT_ROOT / "data" / "active_calibration.json"

DEFAULT_ID = "default"


# ── SnapshotManager ───────────────────────────────────────────────────────────

class SnapshotManager:
    """Gère les instantanés JSON versionnés sur disque."""

    def __init__(self) -> None:
        self._ensure_dirs()
        self._ensure_default()

    # ── Initialisation ────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_default(self) -> None:
        """Crée default.json depuis les valeurs usine si absent."""
        path = DATA_DIR / "default.json"
        if not path.exists():
            snap = {
                "id":          DEFAULT_ID,
                "created_at":  datetime.now().isoformat(timespec="seconds"),
                "label":       "Valeurs par défaut",
                "cycles_used": [],
                "coefficients": FACTORY_DEFAULTS,
                "metrics":     {},
                "parent":      None,
            }
            path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")

        if not ACTIVE_FILE.exists():
            ACTIVE_FILE.write_text(
                json.dumps({"active": DEFAULT_ID}, indent=2), encoding="utf-8"
            )

    # ── Lecture ───────────────────────────────────────────────────────

    def get_active_id(self) -> str:
        try:
            return json.loads(ACTIVE_FILE.read_text(encoding="utf-8")).get("active", DEFAULT_ID)
        except Exception:
            return DEFAULT_ID

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        path = DATA_DIR / f"{snapshot_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_snapshots(self) -> List[Dict]:
        """Retourne tous les instantanés triés : 'default' en premier, puis par date desc."""
        snaps = []
        for path in DATA_DIR.glob("*.json"):
            try:
                snap = json.loads(path.read_text(encoding="utf-8"))
                snaps.append(snap)
            except Exception:
                continue
        # default en premier, reste par date décroissante
        snaps.sort(key=lambda s: (s["id"] != DEFAULT_ID, s.get("created_at", "")))
        return snaps

    # ── Écriture ──────────────────────────────────────────────────────

    def save_snapshot(self, snapshot: Dict) -> str:
        """Sauvegarde un instantané JSON et retourne son id."""
        snap_id = snapshot["id"]
        path = DATA_DIR / f"{snap_id}.json"
        path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        return snap_id

    def next_id(self) -> str:
        """Génère le prochain identifiant calibration_NNN."""
        existing = [
            p.stem for p in DATA_DIR.glob("calibration_*.json")
            if re.match(r"^calibration_\d{3}$", p.stem)
        ]
        if not existing:
            return "calibration_001"
        nums = [int(s.split("_")[1]) for s in existing]
        return f"calibration_{max(nums) + 1:03d}"

    def create_snapshot(
        self,
        coefficients: Dict[str, float],
        metrics: Dict,
        cycles_used: List[Dict],
        label: str = "",
        parent: Optional[str] = None,
    ) -> Dict:
        """Construit et persiste un nouvel instantané versionné."""
        snap_id = self.next_id()
        active  = self.get_active_id()
        snap = {
            "id":          snap_id,
            "created_at":  datetime.now().isoformat(timespec="seconds"),
            "label":       label or snap_id.replace("_", " ").title(),
            "cycles_used": cycles_used,
            "coefficients": coefficients,
            "metrics":     metrics,
            "parent":      parent or active,
        }
        self.save_snapshot(snap)
        return snap

    # ── Activation ────────────────────────────────────────────────────

    def set_active(self, snapshot_id: str) -> bool:
        """Change le pointeur actif et applique les coefficients au modèle.

        Retourne True si l'activation a réussi.
        """
        snap = self.get_snapshot(snapshot_id)
        if snap is None:
            return False

        ACTIVE_FILE.write_text(
            json.dumps({"active": snapshot_id}, indent=2), encoding="utf-8"
        )

        if snapshot_id == DEFAULT_ID:
            restore_defaults()
        else:
            apply_snapshot(snap.get("coefficients", {}))

        return True

    def reset_to_default(self) -> None:
        """Active l'instantané par défaut (valeurs usine)."""
        self.set_active(DEFAULT_ID)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Supprime un instantané non-usine.

        Si l'instantané supprimé est actif, le modèle revient d'abord aux
        valeurs par défaut.
        """
        if snapshot_id == DEFAULT_ID:
            return False

        path = DATA_DIR / f"{snapshot_id}.json"
        if not path.exists():
            return False

        if self.get_active_id() == snapshot_id:
            self.reset_to_default()

        path.unlink()
        return True
