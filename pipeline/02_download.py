"""
02_download — Baja y cachea los data.json de una fase (default: Clasificatorio).

- Lee los matchId desde data/schedule/schedule.json.
- Cachea cada data.json crudo en data/raw/matches/{matchId}.json (no rebaja si existe).
- Delay entre requests (rate limiting).
- Estado del partido: el data.json NO trae matchStatus (ese campo solo está en el
  endpoint de competición). Se DERIVA de clock/period/periodsMax/score y se marca lo que
  no esté completo. Se reconstruye el boxscore para confirmar cierre contra el marcador.
- Escribe un índice en data/schedule/{slug}_index.csv con estado y cierre por partido.
"""
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DATA_URL = "https://fibalivestats.dcd.shared.geniussports.com/data/{mid}/data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (OpenLUB downloader)"}
DELAY = 1.5
DEFAULT_PHASE = "Clasificatorio LUB 25/26"


def slug(phase: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", phase.lower()).strip("_")


def fetch(mid: str) -> tuple[dict | None, str]:
    """Devuelve (data, source) donde source es 'cache'|'web'. None si falló."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{mid}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), "cache"
    r = requests.get(DATA_URL.format(mid=mid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    cache.write_text(r.text, encoding="utf-8")
    time.sleep(DELAY)
    return json.loads(r.text), "web"


def derive_status(d: dict) -> str:
    """COMPLETE si terminó el tiempo (regular o prórroga) con marcador; si no, INCOMPLETE/NODATA.

    OJO con la prórroga: en OT el campo `period` REINICIA a 1 y `periodType` pasa a "OVERTIME".
    Por eso no alcanza con `period >= periodsMax` — hay que contemplar el caso OT.
    """
    tm = d.get("tm", {})
    s1 = int(tm.get("1", {}).get("score", 0) or 0)
    s2 = int(tm.get("2", {}).get("score", 0) or 0)
    period = int(d.get("period", 0) or 0)
    pmax = int(d.get("periodsMax", 4) or 4)
    clock = d.get("clock", "")
    ptype = d.get("periodType", "")
    ended = clock in ("00:00", "0:00", "")
    if s1 == 0 and s2 == 0 and period == 0:
        return "NODATA"
    if ended and (ptype == "OVERTIME" or period >= pmax):
        return "COMPLETE"
    return "INCOMPLETE"


def boxscore_closes(d: dict) -> bool:
    for t in ("1", "2"):
        tm = d["tm"][t]
        pts = sum(int(p.get("sPoints", 0) or 0) for p in tm["pl"].values())
        score = int(tm.get("score", 0) or 0)
        qsum = sum(int(tm.get(f"p{i}_score", 0) or 0) for i in range(1, 5))
        # con OT, qsum (4 cuartos) puede ser < score; exigimos pts==score y qsum<=score
        if not (pts == score and qsum <= score):
            return False
    return True


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = schedule[phase]
    print(f"Fase: {phase}  ({len(ids)} partidos)")

    rows = []
    ok = downloaded = failed = 0
    flagged = []
    for i, mid in enumerate(ids, 1):
        try:
            d, src = fetch(mid)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [{i:>3}/{len(ids)}] {mid}  ERROR {e}")
            rows.append({"matchId": mid, "status": "FETCH_ERROR", "closes": "",
                         "team1": "", "team2": "", "score1": "", "score2": "", "src": "fail"})
            continue
        downloaded += 1
        status = derive_status(d)
        closes = boxscore_closes(d) if status != "NODATA" else False
        tm = d.get("tm", {})
        t1, t2 = tm.get("1", {}), tm.get("2", {})
        if status == "COMPLETE" and closes:
            ok += 1
        if status != "COMPLETE" or not closes:
            flagged.append((mid, status, closes, t1.get("name"), t2.get("name")))
        rows.append({"matchId": mid, "status": status, "closes": closes,
                     "team1": t1.get("name"), "team2": t2.get("name"),
                     "score1": t1.get("score"), "score2": t2.get("score"), "src": src})

    out = SCH_DIR / f"{slug(phase)}_index.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["matchId", "status", "closes", "team1",
                                          "team2", "score1", "score2", "src"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nBajaron OK (HTTP+JSON): {downloaded}/{len(ids)}  | fallos: {failed}")
    print(f"COMPLETE + boxscore cierra: {ok}/{len(ids)}")
    if flagged:
        print(f"\nFLAGGED ({len(flagged)}) — no COMPLETE o no cierra:")
        for mid, st, cl, a, b in flagged:
            print(f"  {mid}  status={st} closes={cl}  {a} vs {b}")
    else:
        print("\nNingún partido flaggeado: los 132 COMPLETE y cierran.")
    print(f"\nÍndice: {out}")


if __name__ == "__main__":
    main()
