"""
05_player_identity — Crosswalk personId <-> jugador, y re-llaveo de identidad.

El data.json NO trae personId de jugador (solo de árbitros). El personId vive en el
embed server-rendered de Genius Sports (host hosted.dcd, embednf), en los links /person/{id}:
  https://hosted.dcd.shared.geniussports.com/embednf/FUBB/es/competition/{compId}/match/{matchId}/boxscore
Cada fila de jugador linkea a /person/{personId} con el nombre (en alt de la foto, o como
texto del <a> cuando no hay foto). Se cosecha ese mapeo y se joinea al data.json por nombre.

Salidas (data/agg/{slug}/):
  player_crosswalk.csv   personId, display, teams, name_keys, GP
  identity_unmatched.csv jugadores del data.json sin personId (para auditar)
Reporta el cambio en jugadores únicos al re-llavear (name+team -> personId).
"""
import csv
import html as htmllib
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
EMB_DIR = ROOT / "data" / "raw" / "embednf_box"
SCH_DIR = ROOT / "data" / "schedule"
COMPETITION_ID = 42104
BOX_URL = ("https://hosted.dcd.shared.geniussports.com/embednf/FUBB/es/"
           "competition/{cid}/match/{mid}/boxscore")
HEADERS = {"User-Agent": "Mozilla/5.0 (OpenLUB identity)"}
DELAY = 1.5
DEFAULT_PHASE = "Clasificatorio LUB 25/26"

# Overrides manuales (team, name del data.json) -> personId.
# Casos que NO se resuelven por encoding: typo en el data.json o jugador ausente del embednf.
MANUAL_OVERRIDES = {
    ("COR", "A. Glider"): "2577763",       # typo de "A. Gilder Jr." (mismo jugador) en el data.json
    ("GOE", "M. Serventich"): "LOCAL:GOE-SERVENTICH",  # 37s en 1 PJ, NO aparece en el boxscore embednf
}


def slug(p): return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")
def i(v): return int(v or 0)


def norm(s: str) -> str:
    """Normaliza nombre para join: sin acentos ni puntuación, mayúsculas, espacios colapsados.
    El embednf codifica acentos/apóstrofes distinto del data.json (Peña, Acuña, O'neal)."""
    s = (s or "").replace("\\n", " ")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def fetch_box(mid: str) -> str | None:
    """Devuelve el HTML del boxscore embednf, o None si no existe (404/error)."""
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    cache = EMB_DIR / f"{mid}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    r = requests.get(BOX_URL.format(cid=COMPETITION_ID, mid=mid), headers=HEADERS, timeout=30)
    time.sleep(DELAY)
    if r.status_code != 200:
        return None
    cache.write_text(r.text, encoding="utf-8")
    return r.text


def crosswalk_from_box(html: str):
    """boxscore embednf -> (name_map, fam_map).
    name_map = {NAME_NORM: personId}; fam_map = {APELLIDO_NORM: personId} solo si el
    apellido es ÚNICO en el partido (fallback para discrepancias de inicial/apóstrofe)."""
    clean = html.replace('\\/', '/').replace('\\"', '"')
    # el embednf deja escapes unicode literales (Ñ por Ñ) y entidades HTML (&#039; por ')
    clean = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), clean)
    clean = htmllib.unescape(clean)
    name_map = {}
    fam_count = defaultdict(set)
    for pid, inner in re.findall(r'person/(\d+)\?">(.*?)</a>', clean, re.DOTALL):
        m = re.search(r'alt="([^"]+)"', inner)
        name = norm(m.group(1) if m else re.sub(r'<[^>]+>', '', inner))
        if not name:
            continue
        name_map.setdefault(name, pid)
        fam = name.split()[-1]  # último token = apellido
        fam_count[fam].add(pid)
    fam_map = {f: next(iter(p)) for f, p in fam_count.items() if len(p) == 1}
    return name_map, fam_map


def played(p) -> bool:
    mins = p.get("sMinutes") or ""
    return mins not in ("", "0:00", "00:00")


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = [m for m in schedule[phase] if m not in load_exclusions()]
    print(f"Fase: {phase} ({len(ids)} partidos). Cosechando personId del embednf...")

    pid_oldkeys = defaultdict(set)   # personId -> {(code,fam,first)}
    pid_meta = defaultdict(lambda: {"display": "", "teams": set(), "GP": 0})
    oldkey_pids = defaultdict(set)   # (code,fam,first) -> {personId}
    oldkeys_all = set()
    unmatched = []
    box_404 = []
    id_map = []   # fila-a-fila: (matchId, team, name del data.json) -> personId, para el paso 03

    for n, mid in enumerate(ids, 1):
        html = fetch_box(mid)
        if html is None:
            box_404.append(mid)
            continue
        name_map, fam_map = crosswalk_from_box(html)
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        for t in ("1", "2"):
            tm = d["tm"][t]
            code = tm.get("code")
            for p in tm["pl"].values():
                if not played(p):
                    continue
                oldkey = (code, p.get("internationalFamilyName"), p.get("internationalFirstName"))
                oldkeys_all.add(oldkey)
                pid = name_map.get(norm(p.get("name"))) \
                    or fam_map.get(norm(p.get("internationalFamilyName"))) \
                    or MANUAL_OVERRIDES.get((code, p.get("name")))
                if not pid:
                    unmatched.append({"matchId": mid, "team": code, "name": p.get("name")})
                    continue
                pid_oldkeys[pid].add(oldkey)
                oldkey_pids[oldkey].add(pid)
                id_map.append({"matchId": mid, "team": code, "name": p.get("name"), "personId": pid})
                m = pid_meta[pid]
                m["display"] = p.get("name")
                m["teams"].add(code)
                m["GP"] += 1
        if n % 25 == 0:
            print(f"  ...{n}/{len(ids)} partidos")

    out = ROOT / "data" / "agg" / slug(phase)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "player_crosswalk.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["personId", "display", "teams", "name_keys", "GP"])
        for pid, m in sorted(pid_meta.items(), key=lambda x: -x[1]["GP"]):
            keys = "; ".join(f"{c}/{fa}/{fi}" for c, fa, fi in sorted(pid_oldkeys[pid]))
            w.writerow([pid, m["display"], "|".join(sorted(m["teams"])), keys, m["GP"]])
    with (out / "identity_unmatched.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["matchId", "team", "name"])
        w.writeheader()
        w.writerows(unmatched)
    with (out / "player_id_map.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["matchId", "team", "name", "personId"])
        w.writeheader()
        w.writerows(id_map)

    old_unique = len(oldkeys_all)
    new_unique = len(pid_meta)
    collapses = {pid: ks for pid, ks in pid_oldkeys.items() if len(ks) > 1}
    splits = {ok: ps for ok, ps in oldkey_pids.items() if len(ps) > 1}

    print(f"\n=== RE-LLAVEO name+team -> personId ===")
    print(f"Únicos (name+team): {old_unique}")
    print(f"Únicos (personId):  {new_unique}   (delta {new_unique - old_unique})")
    print(f"Jugadores-partido sin personId (unmatched): {len(unmatched)}")
    print(f"Partidos sin boxscore embednf (404): {len(box_404)} {box_404 if box_404 else ''}")
    print(f"\nCOLAPSOS (1 personId con >1 name+team key) = {len(collapses)}:")
    for pid, ks in collapses.items():
        teams = "|".join(sorted(pid_meta[pid]["teams"]))
        print(f"  {pid} {pid_meta[pid]['display']:<20} teams={teams}: {sorted(ks)}")
    print(f"\nSPLITS (1 name+team key con >1 personId) = {len(splits)}:")
    for ok, ps in splits.items():
        print(f"  {ok}: {sorted(ps)}")
    print(f"\nCrosswalk: {out / 'player_crosswalk.csv'}")


if __name__ == "__main__":
    main()
