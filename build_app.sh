#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_app.sh — Construit "ETO Digital Twin.app" (macOS)
# Usage :  ./build_app.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Activation du virtualenv ──────────────────────────────────────────────────
source eto_env/bin/activate

echo "▶  Vérification des dépendances..."
python -c "import PySide6, matplotlib, scipy, numpy" \
  && echo "   OK" \
  || { echo "   ✗ Dépendances manquantes — lancez : pip install -r requirements.txt"; exit 1; }

# ── Nettoyage des builds précédents ──────────────────────────────────────────
echo "▶  Nettoyage (build/ dist/)..."
rm -rf build dist

# ── Régénération de l'icône si absente ───────────────────────────────────────
if [[ ! -f assets/icon.icns ]]; then
  echo "▶  Génération de l'icône..."
  python assets/generate_icon.py
fi

# ── Build PyInstaller ─────────────────────────────────────────────────────────
echo "▶  Build PyInstaller (peut prendre 1-2 min)..."
pyinstaller --noconfirm EtoDigitalTwin.spec

# ── Résultat ──────────────────────────────────────────────────────────────────
APP="dist/ETO Digital Twin.app"
if [[ -d "$APP" ]]; then
  echo ""
  echo "✓  Application prête : $(pwd)/$APP"
  echo ""
  echo "   Pour l'ouvrir maintenant :"
  echo "     open \"$APP\""
  echo ""
  echo "   Pour l'installer dans /Applications :"
  echo "     cp -r \"$APP\" /Applications/"
else
  echo "✗  Build échoué — vérifiez les logs ci-dessus."
  exit 1
fi
