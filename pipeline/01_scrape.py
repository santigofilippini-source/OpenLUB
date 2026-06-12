"""
01_scrape — Listado de partidos (matchId) por fase de la LUB 25/26.

El schedule NO tiene endpoint JSON: es HTML server-rendered del embed de FUBB.
De cada página de fase se extraen los matchId de los links de partido.

Gotchas (ver CLAUDE.md, seccion schedule):
  1. Los links vienen con barras ESCAPADAS dentro del HTML:
     ...\\/competition\\/42104\\/match\\/2741411\\/summary?...
     -> el regex debe contemplar el backslash: r'match\\\\/(\\d+)\\\\/summary'
  2. Cada partido aparece DOS veces (variantes livenow / notlive del mismo link)
     -> hay que deduplicar.
  3. "Reclasificatiorio LUB 25/26" lleva la ERRATA tal cual la escribe el sistema.
     Si se escribe bien ("Reclasificatorio"), el endpoint devuelve 0 partidos.

Salida:
  data/schedule/schedule.json  -> {fase: [matchId, ...]}
  data/schedule/schedule.csv   -> columnas: matchId, fase
  data/raw/schedule/{slug}.html -> cache del HTML crudo por fase

NO baja los data.json de cada partido (eso es el paso siguiente del pipeline).
"""

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

# --- Config ---------------------------------------------------------------

COMPETITION_ID = 42104

SCHEDULE_URL = (
    "https://hosted.dcd.shared.geniussports.com/embednf/FUBB/es/"
    "competition/{competition_id}/schedule?phaseName={phase}"
)

# phaseName EXACTOS como los espera el sistema. OJO con la errata de la fase 2:
# "Reclasificatiorio" (no "Reclasificatorio") — sin la errata devuelve 0 partidos.
PHASES = [
    "Clasificatorio LUB 25/26",
    "Reclasificatiorio LUB 25/26",  # errata intencional del sistema
    "Titulo LUB 25/26",
    "Playoffs LUB 25/26",
]

# Gotcha 1: barras escapadas. Gotcha 2: dedup (cada match sale 2x).
MATCH_ID_RE = re.compile(r"match\\/(\d+)\\/summary")

REQUEST_DELAY_S = 1.5  # rate limiting para no ser bloqueado por Genius Sports
HEADERS = {"User-Agent": "Mozilla/5.0 (OpenLUB schedule scraper)"}

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "schedule"
OUT_DIR = ROOT / "data" / "schedule"


# --- Helpers --------------------------------------------------------------

def slug(phase: str) -> str:
    """Nombre de archivo seguro a partir del phaseName."""
    return re.sub(r"[^a-z0-9]+", "_", phase.lower()).strip("_")


def fetch_phase_html(phase: str) -> str:
    """Baja (y cachea) el HTML del schedule de una fase."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{slug(phase)}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    url = SCHEDULE_URL.format(competition_id=COMPETITION_ID, phase=quote(phase))
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    cache.write_text(resp.text, encoding="utf-8")
    time.sleep(REQUEST_DELAY_S)
    return resp.text


def extract_match_ids(html: str) -> list[str]:
    """Extrae matchId de los links de partido, deduplicando y preservando orden."""
    seen: list[str] = []
    for mid in MATCH_ID_RE.findall(html):
        if mid not in seen:
            seen.append(mid)
    return seen


def scrape_schedule() -> dict[str, list[str]]:
    """Itera las 4 fases y devuelve {fase: [matchId, ...]}."""
    result: dict[str, list[str]] = {}
    for phase in PHASES:
        html = fetch_phase_html(phase)
        ids = extract_match_ids(html)
        result[phase] = ids
        print(f"  {phase:<32} -> {len(ids):>3} partidos")
    return result


def save(schedule: dict[str, list[str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "schedule.json").write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT_DIR / "schedule.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["matchId", "fase"])
        for phase, ids in schedule.items():
            for mid in ids:
                w.writerow([mid, phase])


def main() -> None:
    print("Scrapeando schedule LUB 25/26 (4 fases)...")
    schedule = scrape_schedule()
    save(schedule)
    total = sum(len(v) for v in schedule.values())
    print(f"\nTotal: {total} partidos en {len(schedule)} fases.")
    print(f"Guardado en {OUT_DIR / 'schedule.json'} y schedule.csv")


if __name__ == "__main__":
    main()
