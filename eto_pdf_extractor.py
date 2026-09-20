"""
eto_pdf_extractor.py — Extracteur de données cycle réel depuis rapports PDF machine
=================================================================================
Supporte les deux formats de rapports :
  - Format FR  : colonnes Date / Etapes / PT 111 / PT 112 / TT 111 / TT 112 / TT 191 / RHT 121 / GT 121
  - Format EN  : colonnes Date / Step  / PT 111 / PT 112 / TT 111 / TT 112 / TT 191 / RHT 121 (sans GT)

Usage autonome :
    python3 eto_pdf_extractor.py rapport.pdf

Retourne :
    CycleData  — dataclass contenant les métadonnées + liste de CycleStep
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import pdfplumber
except ImportError:
    raise ImportError("pdfplumber est requis : pip install pdfplumber --break-system-packages")

# OCR optionnel pour les PDFs scannés (images)
try:
    import pytesseract
    from PIL import Image as PILImage
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ────────────────────────────────────────────────────────────────────────────
# Structures de données
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class CycleStep:
    """Un point de mesure issu du tableau 'Etapes de cycle'."""
    timestamp: datetime
    step_name: str
    pt111: float
    pt112: float
    tt111: float
    tt112: float
    tt191: float
    rht121: float
    gt121: float = 0.0
    # Temps en minutes depuis le début du cycle (calculé après chargement)
    t_min: float = 0.0


@dataclass
class CycleData:
    """Données complètes d'un cycle réel extrait d'un PDF."""
    source_file: str
    batch_name: str = ""
    recipe_name: str = ""
    equipment: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_min: float = 0.0
    steps: List[CycleStep] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.steps) == 0

    def variables_at_time(self, t_min: float) -> dict:
        """Interpolation linéaire de toutes les variables à un temps t_min."""
        if not self.steps:
            return {}
        if t_min <= self.steps[0].t_min:
            s = self.steps[0]
        elif t_min >= self.steps[-1].t_min:
            s = self.steps[-1]
        else:
            # Trouver l'intervalle
            for i in range(len(self.steps) - 1):
                s0, s1 = self.steps[i], self.steps[i + 1]
                if s0.t_min <= t_min <= s1.t_min:
                    if s1.t_min == s0.t_min:
                        s = s1
                    else:
                        u = (t_min - s0.t_min) / (s1.t_min - s0.t_min)
                        return {
                            "PT111": s0.pt111 + u * (s1.pt111 - s0.pt111),
                            "PT112": s0.pt112 + u * (s1.pt112 - s0.pt112),
                            "TT111": s0.tt111 + u * (s1.tt111 - s0.tt111),
                            "TT112": s0.tt112 + u * (s1.tt112 - s0.tt112),
                            "TT191": s0.tt191 + u * (s1.tt191 - s0.tt191),
                            "RHT121": s0.rht121 + u * (s1.rht121 - s0.rht121),
                            "GT121": s0.gt121 + u * (s1.gt121 - s0.gt121),
                        }
            s = self.steps[-1]
        return {
            "PT111": s.pt111, "PT112": s.pt112,
            "TT111": s.tt111, "TT112": s.tt112,
            "TT191": s.tt191, "RHT121": s.rht121, "GT121": s.gt121,
        }


# ────────────────────────────────────────────────────────────────────────────
# Parseur de timestamp
# ────────────────────────────────────────────────────────────────────────────

_TS_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y\n%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
]


def _parse_timestamp(raw: str) -> Optional[datetime]:
    """Parse un timestamp brut (peut contenir des sauts de ligne)."""
    raw = raw.replace("\n", " ").strip()
    # Normaliser les espaces multiples
    raw = re.sub(r"\s+", " ", raw)
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _safe_float(s: str, default: float = 0.0) -> float:
    """Convertit une chaîne en float, retourne default si impossible."""
    try:
        return float(str(s).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default


# ────────────────────────────────────────────────────────────────────────────
# Détection du format de rapport
# ────────────────────────────────────────────────────────────────────────────

def _detect_format(header_row: list) -> str:
    """
    Retourne 'FR' (9 colonnes avec GT121) ou 'EN' (8 colonnes sans GT121)
    ou 'UNKNOWN'.
    """
    if not header_row:
        return "UNKNOWN"
    cols = [str(c).strip().replace("\n", " ").lower() for c in header_row]
    has_gt = any("gt" in c for c in cols)
    has_date = any(c in ("date",) for c in cols)
    has_step = any(c in ("etapes", "step", "étapes") for c in cols)
    if has_date and has_step:
        return "FR" if has_gt else "EN"
    return "UNKNOWN"


# ────────────────────────────────────────────────────────────────────────────
# Extraction du tableau de données sur une page (PDF texte natif)
# ────────────────────────────────────────────────────────────────────────────

def _extract_rows_from_page(page) -> List[CycleStep]:
    """
    Extrait les lignes de données d'une page pdfplumber (PDF texte natif).
    Gère les deux formats FR (9 cols) et EN (8 cols).
    """
    steps: List[CycleStep] = []
    tables = page.extract_tables()
    if not tables:
        return steps

    col_map: dict = {}

    for table in tables:
        if not table:
            continue

        for row in table:
            if row is None:
                continue

            # Ligne d'en-tête ?
            cols_lower = [str(c or "").replace("\n", " ").strip().lower() for c in row]
            is_header = (
                any(c in ("date",) for c in cols_lower)
                and any(c in ("etapes", "step", "étapes") for c in cols_lower)
            )

            if is_header:
                col_map = {}
                for i, c in enumerate(cols_lower):
                    c_clean = c.replace(" ", "")
                    if c == "date": col_map["date"] = i
                    elif c in ("etapes", "step", "étapes"): col_map["step"] = i
                    elif "pt111" in c_clean or c == "pt 111": col_map["pt111"] = i
                    elif "pt112" in c_clean or c == "pt 112": col_map["pt112"] = i
                    elif "tt111" in c_clean or c == "tt 111": col_map["tt111"] = i
                    elif "tt112" in c_clean or c == "tt 112": col_map["tt112"] = i
                    elif "tt191" in c_clean or c == "tt 191": col_map["tt191"] = i
                    elif "rht121" in c_clean or "rht" in c_clean: col_map["rht121"] = i
                    elif "gt121" in c_clean or c == "gt 121": col_map["gt121"] = i
                continue

            if not col_map:
                continue

            date_idx = col_map.get("date", 0)
            raw_date = str(row[date_idx] or "").strip() if date_idx < len(row) else ""
            ts = _parse_timestamp(raw_date)
            if ts is None:
                continue

            step_idx = col_map.get("step", 1)
            step_name = str(row[step_idx] or "").replace("\n", " ").strip() if step_idx < len(row) else ""

            def _get(key: str, default: float = 0.0) -> float:
                idx = col_map.get(key)
                if idx is None or idx >= len(row):
                    return default
                return _safe_float(row[idx], default)

            steps.append(CycleStep(
                timestamp=ts,
                step_name=step_name,
                pt111=_get("pt111"), pt112=_get("pt112"),
                tt111=_get("tt111"), tt112=_get("tt112"),
                tt191=_get("tt191"), rht121=_get("rht121"),
                gt121=_get("gt121", 0.0),
            ))

    return steps


# ────────────────────────────────────────────────────────────────────────────
# Extraction depuis texte OCR (PDF scanné)
# ────────────────────────────────────────────────────────────────────────────

def _extract_rows_from_text_ocr(text: str) -> List[CycleStep]:
    """
    Extrait les lignes de données depuis du texte brut OCR.
    Cherche les patterns : date heure  nom_etape  val val val val val val val
    """
    steps: List[CycleStep] = []

    # Pattern : date (dd/mm/yyyy) heure (hh:mm:ss) puis nom puis 7-9 nombres
    # Le nom peut contenir des espaces et des ':'
    date_re = re.compile(
        r"(\d{2}/\d{2}/\d{4})[,\s]+(\d{2}:\d{2}(?::\d{2})?)"
    )

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = date_re.search(line)
        if not m:
            continue

        raw_dt = f"{m.group(1)} {m.group(2)}"
        ts = _parse_timestamp(raw_dt)
        if ts is None:
            continue

        # Tout ce qui suit la date/heure
        remainder = line[m.end():].strip()

        # Extraire tous les nombres (flottants ou entiers) à la fin
        numbers = re.findall(r'-?\d+(?:[.,]\d+)?', remainder)
        # Les derniers 7-9 nombres sont les valeurs des capteurs
        # (PT111 PT112 TT111 TT112 TT191 RHT121 GT121)
        floats = [_safe_float(n) for n in numbers]

        if len(floats) < 6:
            continue  # pas assez de valeurs

        # Le nom de l'étape = tout ce qui est entre la date et les premiers grands nombres
        # On retire les nombres de la fin du remainder pour trouver le nom
        # Stratégie : trouver le premier nombre > 10 (probablement PT111 ≥ 50)
        # ou les 7 derniers nombres
        vals = floats[-7:] if len(floats) >= 7 else floats[-6:] + [0.0]

        # Reconstituer le nom : remainder sans les nombres de fin
        name_part = remainder
        # Supprimer les occurrences des valeurs de la fin (de droite à gauche)
        for n in reversed(numbers[-7:]):
            # Supprimer la dernière occurrence de ce nombre dans name_part
            idx = name_part.rfind(n)
            if idx >= 0:
                name_part = name_part[:idx]
        step_name = re.sub(r'\s+', ' ', name_part).strip()
        # Nettoyer les artefacts OCR en début de nom
        step_name = re.sub(r'^[^a-zA-ZÀ-ÿ0-9]+', '', step_name).strip()

        if not step_name:
            step_name = "?"

        # Assigner les valeurs selon le nombre de colonnes
        if len(vals) >= 7:
            pt111, pt112, tt111, tt112, tt191, rht121, gt121 = vals[:7]
        else:
            pt111, pt112, tt111, tt112, tt191, rht121 = vals[:6]
            gt121 = 0.0

        step = CycleStep(
            timestamp=ts,
            step_name=step_name,
            pt111=pt111, pt112=pt112,
            tt111=tt111, tt112=tt112,
            tt191=tt191, rht121=rht121,
            gt121=gt121,
        )
        steps.append(step)

    return steps


def _is_scanned_pdf(pdf) -> bool:
    """Retourne True si le PDF est composé d'images (pas de texte extractible)."""
    total_chars = sum(len(page.chars) for page in pdf.pages[:3])
    total_images = sum(len(page.images) for page in pdf.pages[:3])
    return total_chars == 0 and total_images > 0


def _extract_rows_via_ocr(pdf) -> List[CycleStep]:
    """
    Extrait les données via OCR (pour PDFs scannés).
    Cherche les pages contenant le tableau d'étapes.
    """
    if not OCR_AVAILABLE:
        raise RuntimeError(
            "pytesseract et Pillow sont requis pour les PDFs scannés.\n"
            "Installez-les : pip install pytesseract pillow --break-system-packages\n"
            "Et installez Tesseract : sudo apt-get install tesseract-ocr"
        )

    all_steps: List[CycleStep] = []
    # Mots-clés indiquant une page avec le tableau d'étapes
    STEP_KEYWORDS = [
        "gonflage", "vide initiale", "vide initial", "inflating",
        "injection", "exposition", "etapes", "step report",
        "stabilisation", "rincage", "rinsing"
    ]

    for page in pdf.pages:
        # OCR à résolution 200 dpi pour bon rapport qualité/vitesse
        img = page.to_image(resolution=200)
        pil_img = img.original
        text = pytesseract.image_to_string(pil_img, lang='eng', config='--psm 6')
        text_lower = text.lower()

        # Vérifier si cette page contient des données d'étapes
        if not any(kw in text_lower for kw in STEP_KEYWORDS):
            continue

        steps = _extract_rows_from_text_ocr(text)
        all_steps.extend(steps)

    return all_steps
    """
    Extrait les lignes de données d'une page pdfplumber.
    Gère les deux formats FR (9 cols) et EN (8 cols).
    Fusionne les tableaux fragmentés détectés par pdfplumber.
    """
    steps: List[CycleStep] = []
    tables = page.extract_tables()
    if not tables:
        return steps

    detected_format = "UNKNOWN"
    col_map: dict = {}

    for table in tables:
        if not table:
            continue

        for row in table:
            if row is None:
                continue

            # Ligne d'en-tête ?
            cols_lower = [str(c or "").replace("\n", " ").strip().lower() for c in row]
            is_header = (
                any(c in ("date",) for c in cols_lower)
                and any(c in ("etapes", "step", "étapes") for c in cols_lower)
            )

            if is_header:
                detected_format = _detect_format(row)
                # Construire la carte des colonnes
                col_map = {}
                for i, c in enumerate(cols_lower):
                    c_clean = c.replace(" ", "")
                    if c in ("date",): col_map["date"] = i
                    elif c in ("etapes", "step", "étapes"): col_map["step"] = i
                    elif "pt111" in c_clean or c == "pt 111": col_map["pt111"] = i
                    elif "pt112" in c_clean or c == "pt 112": col_map["pt112"] = i
                    elif "tt111" in c_clean or c == "tt 111": col_map["tt111"] = i
                    elif "tt112" in c_clean or c == "tt 112": col_map["tt112"] = i
                    elif "tt191" in c_clean or c == "tt 191": col_map["tt191"] = i
                    elif "rht121" in c_clean or "rht" in c_clean: col_map["rht121"] = i
                    elif "gt121" in c_clean or c == "gt 121": col_map["gt121"] = i
                continue  # ne pas traiter l'en-tête comme une ligne de données

            # Ligne de données : doit contenir un timestamp dans la 1ère colonne
            if not col_map:
                continue

            date_idx = col_map.get("date", 0)
            raw_date = str(row[date_idx] or "").strip() if date_idx < len(row) else ""
            ts = _parse_timestamp(raw_date)
            if ts is None:
                continue

            # Extraire le nom de l'étape
            step_idx = col_map.get("step", 1)
            step_name = str(row[step_idx] or "").replace("\n", " ").strip() if step_idx < len(row) else ""

            def _get(key: str, default: float = 0.0) -> float:
                idx = col_map.get(key)
                if idx is None or idx >= len(row):
                    return default
                return _safe_float(row[idx], default)

            step = CycleStep(
                timestamp=ts,
                step_name=step_name,
                pt111=_get("pt111"),
                pt112=_get("pt112"),
                tt111=_get("tt111"),
                tt112=_get("tt112"),
                tt191=_get("tt191"),
                rht121=_get("rht121"),
                gt121=_get("gt121", 0.0),
            )
            steps.append(step)

    return steps


# ────────────────────────────────────────────────────────────────────────────
# Extraction des métadonnées (batch name, recipe, etc.)
# ────────────────────────────────────────────────────────────────────────────

def _extract_metadata(pdf) -> dict:
    """
    Extrait les métadonnées depuis les premières pages du rapport.
    Cherche les patterns : Numéro de lot, Recette, Equipement, Début, Fin.
    """
    meta = {
        "batch_name": "",
        "recipe_name": "",
        "equipment": "",
        "start_time": None,
        "end_time": None,
    }

    # Patterns multilingues
    patterns = {
        "batch_name":  [r"(?:Numéro de lot|Batch name|Lot)\s*[:\|]\s*(.+?)(?:\s{2,}|\n|$)"],
        "recipe_name": [r"(?:Recette de stérilisation|Sterilization recipe|Recette)\s*[:\|]\s*(.+?)(?:\s{2,}|\n|$)"],
        "equipment":   [r"(?:Equipement|Equipment)\s*[:\|]\s*(.+?)(?:\s{2,}|\n|$)"],
        "start_time":  [r"(?:Début|Start|Début)\s*[:\|]?\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})"],
        "end_time":    [r"(?:Fin|End)\s*[:\|]?\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})"],
    }

    # Scanner les 3 premières pages
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        for key, pats in patterns.items():
            if meta[key]:  # déjà trouvé
                continue
            for pat in pats:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if key in ("start_time", "end_time"):
                        meta[key] = _parse_timestamp(val)
                    else:
                        meta[key] = val
                    break

    return meta


# ────────────────────────────────────────────────────────────────────────────
# Fonction principale d'extraction
# ────────────────────────────────────────────────────────────────────────────

def extract_cycle_from_pdf(pdf_path: str) -> CycleData:
    """
    Extrait toutes les données d'un rapport PDF machine.
    Supporte automatiquement :
      - PDFs texte natif (HTM exportés en PDF) → extraction directe via pdfplumber
      - PDFs scannés (images photographiées) → OCR via tesseract

    Args:
        pdf_path: chemin vers le fichier PDF

    Returns:
        CycleData avec steps triés chronologiquement et t_min calculé
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {pdf_path}")

    all_steps: List[CycleStep] = []
    pdf_type = "text"

    with pdfplumber.open(str(path)) as pdf:
        # 1. Métadonnées
        meta = _extract_metadata(pdf)

        # 2. Détecter le type de PDF
        if _is_scanned_pdf(pdf):
            pdf_type = "scanned"
            all_steps = _extract_rows_via_ocr(pdf)
        else:
            # PDF texte natif : extraction via tableaux pdfplumber
            pdf_type = "text"
            for page in pdf.pages:
                text = page.extract_text() or ""
                if any(kw in text for kw in [
                    "Etapes", "Step report", "Etapes de cycle",
                    "PT 111", "PT111", "Date"
                ]):
                    steps = _extract_rows_from_page(page)
                    all_steps.extend(steps)

    # 3. Dédupliquer
    seen = set()
    unique_steps = []
    for s in all_steps:
        key = (s.timestamp, s.step_name)
        if key not in seen:
            seen.add(key)
            unique_steps.append(s)

    # 4. Trier chronologiquement
    unique_steps.sort(key=lambda s: s.timestamp)

    # 5. Calculer t_min
    if unique_steps:
        t0 = unique_steps[0].timestamp
        for s in unique_steps:
            s.t_min = (s.timestamp - t0).total_seconds() / 60.0

    # 6. Durée totale
    total_min = unique_steps[-1].t_min if len(unique_steps) >= 2 else 0.0

    result = CycleData(
        source_file=str(path),
        batch_name=meta["batch_name"],
        recipe_name=meta["recipe_name"],
        equipment=meta["equipment"],
        start_time=meta["start_time"],
        end_time=meta["end_time"],
        total_duration_min=total_min,
        steps=unique_steps,
    )
    result.pdf_type = pdf_type  # attribut informatif
    return result


# ────────────────────────────────────────────────────────────────────────────
# Affichage de résumé
# ────────────────────────────────────────────────────────────────────────────

def print_cycle_summary(cycle: CycleData) -> None:
    """Affiche un résumé lisible du cycle extrait."""
    print(f"\n{'='*65}")
    print(f"  CYCLE EXTRAIT : {cycle.batch_name or Path(cycle.source_file).stem}")
    print(f"{'='*65}")
    print(f"  Fichier     : {Path(cycle.source_file).name}")
    print(f"  Recette     : {cycle.recipe_name}")
    print(f"  Équipement  : {cycle.equipment}")
    if cycle.start_time:
        print(f"  Début       : {cycle.start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    if cycle.end_time:
        print(f"  Fin         : {cycle.end_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Durée totale: {cycle.total_duration_min:.1f} min ({cycle.total_duration_min/60:.2f} h)")
    print(f"  Points      : {len(cycle.steps)}")
    print()

    if not cycle.steps:
        print("  ⚠ Aucune étape extraite.")
        return

    # Tableau résumé
    print(f"  {'t(min)':>7}  {'Étape':<42} {'PT111':>6} {'TT111':>6} {'TT112':>6} {'RH':>6} {'GT':>6}")
    print(f"  {'-'*7}  {'-'*42} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for s in cycle.steps:
        name = s.step_name[:42]
        print(f"  {s.t_min:>7.1f}  {name:<42} {s.pt111:>6.0f} {s.tt111:>6.1f} {s.tt112:>6.1f} {s.rht121:>6.1f} {s.gt121:>6.1f}")


# ────────────────────────────────────────────────────────────────────────────
# Calcul des écarts simulé vs réel
# ────────────────────────────────────────────────────────────────────────────

def compute_comparison(
    real_cycle: CycleData,
    sim_segments: list,
) -> dict:
    """
    Compare un cycle réel (CycleData) avec des segments simulés.

    Args:
        real_cycle: données réelles extraites du PDF
        sim_segments: liste de Segment issus de SterilizationModel.simulate()

    Returns:
        dict avec 'rmse_by_var', 'points', 'mean_errors'
    """
    VARS = ["PT111", "PT112", "TT111", "TT112", "TT191", "RHT121", "GT121"]

    # Reconstruire une fonction t→valeurs pour la simulation
    # (interpolation linéaire entre segments)
    sim_timeline = []  # liste de (t_min, {var: val})
    t = 0.0
    for seg in sim_segments:
        # Point de début
        sim_timeline.append((t, dict(seg.start_state)))
        t += seg.duration
    if sim_segments:
        sim_timeline.append((t, dict(sim_segments[-1].end_state)))

    def sim_at(t_query: float) -> dict:
        if not sim_timeline:
            return {v: 0.0 for v in VARS}
        if t_query <= sim_timeline[0][0]:
            return sim_timeline[0][1]
        if t_query >= sim_timeline[-1][0]:
            return sim_timeline[-1][1]
        for i in range(len(sim_timeline) - 1):
            t0, v0 = sim_timeline[i]
            t1, v1 = sim_timeline[i + 1]
            if t0 <= t_query <= t1:
                if t1 == t0:
                    return v1
                u = (t_query - t0) / (t1 - t0)
                return {k: v0.get(k, 0) + u * (v1.get(k, 0) - v0.get(k, 0)) for k in VARS}
        return sim_timeline[-1][1]

    # Calculer les erreurs à chaque point réel
    errors = {v: [] for v in VARS}
    points = []

    for step in real_cycle.steps:
        t_q = step.t_min
        sim_vals = sim_at(t_q)
        real_vals = {
            "PT111": step.pt111, "PT112": step.pt112,
            "TT111": step.tt111, "TT112": step.tt112,
            "TT191": step.tt191, "RHT121": step.rht121,
            "GT121": step.gt121,
        }
        pt = {"t_min": t_q, "step": step.step_name, "real": real_vals, "sim": sim_vals}
        for v in VARS:
            e = sim_vals.get(v, 0.0) - real_vals.get(v, 0.0)
            errors[v].append(e)
            pt[f"err_{v}"] = e
        points.append(pt)

    import math
    rmse = {}
    mean_err = {}
    for v in VARS:
        if errors[v]:
            rmse[v] = math.sqrt(sum(e**2 for e in errors[v]) / len(errors[v]))
            mean_err[v] = sum(errors[v]) / len(errors[v])
        else:
            rmse[v] = 0.0
            mean_err[v] = 0.0

    return {
        "rmse_by_var": rmse,
        "mean_errors": mean_err,
        "points": points,
        "n_points": len(points),
    }


# ────────────────────────────────────────────────────────────────────────────
# Point d'entrée autonome
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python3 eto_pdf_extractor.py <rapport.pdf> [rapport2.pdf ...]")
        sys.exit(1)

    for pdf_path in sys.argv[1:]:
        try:
            cycle = extract_cycle_from_pdf(pdf_path)
            print_cycle_summary(cycle)
        except Exception as e:
            print(f"\nERREUR sur {pdf_path} : {e}")
            import traceback
            traceback.print_exc()