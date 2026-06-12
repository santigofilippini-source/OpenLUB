"""
03_aggregate — Boxscore agregado de la fase (default: Clasificatorio).

Agrega el boxscore acumulado y promedios de la fase, por JUGADOR y por EQUIPO,
y arma las tablas de líderes (PPG, RPG, APG).

- Lee los matchId de la fase desde data/schedule/schedule.json.
- EXCLUYE los matchId presentes en data/schedule/exclusions.csv (incompletos genuinos).
- Identidad (el feed no trae IDs numéricos, ver CLAUDE.md):
    equipo  = `code`
    jugador = (code_equipo, internationalFamilyName, internationalFirstName)
- GP (games played) = partidos con minutos jugados > 0.
- NO calcula ratings ni percentiles (eso es un paso posterior).

Salidas (en data/agg/{slug}/):
  players_totals.csv     totales por jugador
  players_pergame.csv    promedios por jugador
  teams_totals.csv       totales por equipo
  teams_pergame.csv      promedios por equipo
  leaders_ppg.csv / leaders_rpg.csv / leaders_apg.csv
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"

# Stats contables del boxscore (claves 's*' del jugador / 'tot_s*' del equipo)
COUNTING = [
    "sPoints", "sFieldGoalsMade", "sFieldGoalsAttempted",
    "sTwoPointersMade", "sTwoPointersAttempted",
    "sThreePointersMade", "sThreePointersAttempted",
    "sFreeThrowsMade", "sFreeThrowsAttempted",
    "sReboundsOffensive", "sReboundsDefensive", "sReboundsTotal",
    "sAssists", "sSteals", "sBlocks", "sTurnovers", "sFoulsPersonal",
]
# nombres cortos para columnas de salida
SHORT = {
    "sPoints": "PTS", "sFieldGoalsMade": "FGM", "sFieldGoalsAttempted": "FGA",
    "sTwoPointersMade": "2PM", "sTwoPointersAttempted": "2PA",
    "sThreePointersMade": "3PM", "sThreePointersAttempted": "3PA",
    "sFreeThrowsMade": "FTM", "sFreeThrowsAttempted": "FTA",
    "sReboundsOffensive": "OREB", "sReboundsDefensive": "DREB", "sReboundsTotal": "REB",
    "sAssists": "AST", "sSteals": "STL", "sBlocks": "BLK",
    "sTurnovers": "TOV", "sFoulsPersonal": "PF",
}


def slug(phase: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", phase.lower()).strip("_")


def mins_to_sec(s) -> int:
    if not s or s in ("0:00", "00:00"):
        return 0
    parts = str(s).split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return 0
    return 0


def load_exclusions() -> set[str]:
    f = SCH_DIR / "exclusions.csv"
    if not f.exists():
        return set()
    with f.open(encoding="utf-8") as fh:
        return {row["matchId"] for row in csv.DictReader(fh)}


def i(v) -> int:
    return int(v or 0)


def load_id_map():
    """{(matchId, team, name del data.json): personId} desde el paso 05."""
    f = ROOT / "data" / "agg" / slug(DEFAULT_PHASE) / "player_id_map.csv"
    return {(r["matchId"], r["team"], r["name"]): r["personId"]
            for r in csv.DictReader(f.open(encoding="utf-8"))}


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    excl = load_exclusions()
    ids = [m for m in schedule[phase] if m not in excl]
    print(f"Fase: {phase}")
    print(f"Partidos: {len(schedule[phase])} - {len(excl & set(schedule[phase]))} excluidos = {len(ids)} usados")

    # CANÓNICO: identidad por personId (paso 05). Un player-game sin personId en el mapa
    # es un DNP/0-min que el paso 05 no contó -> se saltea (alinea la definición de GP).
    id_map = load_id_map()

    # acumuladores
    pl = defaultdict(lambda: {"GP": 0, "GS": 0, "sec": 0, **{k: 0 for k in COUNTING}})
    pl_meta = {}
    tm = defaultdict(lambda: {"GP": 0, **{k: 0 for k in COUNTING}})
    tm_meta = {}

    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        for t in ("1", "2"):
            team = d["tm"][t]
            code = team.get("code")
            tm_meta[code] = team.get("name")
            tm[code]["GP"] += 1
            for k in COUNTING:
                tm[code][k] += i(team.get("tot_" + k))
            for p in team["pl"].values():
                key = id_map.get((mid, code, p.get("name")))
                if key is None:
                    continue  # no jugó (sin personId en el mapa)
                rec = pl[key]
                rec["GP"] += 1
                rec["GS"] += 1 if p.get("starter") else 0
                rec["sec"] += mins_to_sec(p.get("sMinutes"))
                for k in COUNTING:
                    rec[k] += i(p.get(k))
                pl_meta[key] = {"personId": key, "team": code, "name": p.get("name"),
                                "pos": p.get("playingPosition", "")}

    out = ROOT / "data" / "agg" / slug(phase)
    out.mkdir(parents=True, exist_ok=True)
    write_players(out, pl, pl_meta)
    write_teams(out, tm, tm_meta)
    leaders(out, pl, pl_meta, tm)
    print(f"\nSalidas en {out}")


def write_players(out, pl, meta):
    cols = ["personId", "team", "name", "pos", "GP", "GS", "MIN"] + [SHORT[k] for k in COUNTING]
    tot_rows, pg_rows = [], []
    for key, r in pl.items():
        m = meta[key]
        base = {"personId": m["personId"], "team": m["team"], "name": m["name"],
                "pos": m["pos"], "GP": r["GP"], "GS": r["GS"]}
        tot = {**base, "MIN": round(r["sec"] / 60, 1)}
        for k in COUNTING:
            tot[SHORT[k]] = r[k]
        tot_rows.append(tot)
        gp = r["GP"] or 1
        pg = {**base, "MIN": round(r["sec"] / 60 / gp, 1)}
        for k in COUNTING:
            pg[SHORT[k]] = round(r[k] / gp, 1)
        pg_rows.append(pg)
    _csv(out / "players_totals.csv", cols, sorted(tot_rows, key=lambda x: -x["PTS"]))
    _csv(out / "players_pergame.csv", cols, sorted(pg_rows, key=lambda x: -x["PTS"]))


def write_teams(out, tm, meta):
    cols = ["code", "name", "GP"] + [SHORT[k] for k in COUNTING]
    tot_rows, pg_rows = [], []
    for code, r in tm.items():
        base = {"code": code, "name": meta[code], "GP": r["GP"]}
        tot = dict(base)
        for k in COUNTING:
            tot[SHORT[k]] = r[k]
        tot_rows.append(tot)
        gp = r["GP"] or 1
        pg = dict(base)
        for k in COUNTING:
            pg[SHORT[k]] = round(r[k] / gp, 1)
        pg_rows.append(pg)
    _csv(out / "teams_totals.csv", cols, sorted(tot_rows, key=lambda x: -x["PTS"]))
    _csv(out / "teams_pergame.csv", cols, sorted(pg_rows, key=lambda x: -x["PTS"]))


def leaders(out, pl, meta, tm):
    # Calificado para liderato = GP >= 50% de los partidos de su equipo (regla estándar de leaderboard)
    rows = []
    for key, r in pl.items():
        m = meta[key]
        team_gp = tm[m["team"]]["GP"]
        gp = r["GP"] or 1
        rows.append({
            "personId": m["personId"], "team": m["team"], "name": m["name"], "pos": m["pos"],
            "GP": r["GP"], "teamGP": team_gp,
            "qualified": r["GP"] >= 0.5 * team_gp,
            "PPG": round(r["sPoints"] / gp, 1),
            "RPG": round(r["sReboundsTotal"] / gp, 1),
            "APG": round(r["sAssists"] / gp, 1),
        })
    cols = ["rank", "personId", "name", "team", "pos", "GP", "PPG", "RPG", "APG", "qualified"]
    for metric in ("PPG", "RPG", "APG"):
        q = sorted([r for r in rows if r["qualified"]], key=lambda x: -x[metric])
        ranked = [{"rank": n + 1, **{c: r[c] for c in cols if c != "rank"}}
                  for n, r in enumerate(q)]
        _csv(out / f"leaders_{metric.lower()}.csv", cols, ranked)
        print(f"\n=== Líderes {metric} (calificados, top 10) ===")
        for r in ranked[:10]:
            print(f"  {r['rank']:>2}. {r['name']:<22} {r['team']:<5} {metric}={r[metric]:<5} (GP {r['GP']})")


def _csv(path, cols, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
