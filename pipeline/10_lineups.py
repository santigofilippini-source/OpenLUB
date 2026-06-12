"""
10_lineups — Quintetos (lineups de 5) POR EQUIPO, con net rating crudo.

Para cada partido se recorre el pbp y, a cada evento, el quinteto del equipo en cancha suma su
OFENSA (PTS/posesiones propias) y el quinteto rival suma su DEFENSA (PTS/posesiones del rival contra
él). Se agrega por (equipo, frozenset de 5 personId) a lo largo de los 130 partidos trackeados.

  ORtg = 100*PTS/Pos (ofensiva del quinteto) ; DRtg = 100*PTS_riv/Pos_riv (rival vs el quinteto)
  Net = ORtg - DRtg ; Pos = posesiones ofensivas del quinteto juntas

Piso: >= MIN_POSS posesiones juntas (default 100) para reportar con confianza.

*** CRUDO, sin ajuste por rival -> NO COMPARABLE ENTRE EQUIPOS ***
Un +15 de un quinteto de Cordón NO supera a un +10 de Peñarol: enfrentaron rivales distintos y la
muestra es chica. Sirve para comparar quintetos DENTRO de un mismo equipo, no para un ranking de liga.
"""
import csv
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

trk = importlib.import_module("07_tracking")
opp_mod = importlib.import_module("08_opportunity")
onoff = importlib.import_module("09_onoff")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
MIN_POSS = 100


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def poss(c):
    return c["FGA"] - c["OREB"] + c["TOV"] + 0.44 * c["FTA"]


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    team_filter = sys.argv[2].upper() if len(sys.argv) > 2 else None
    out = ROOT / "data" / "agg" / slug(phase)
    idmap = {(r["matchId"], r["team"], r["name"]): r["personId"]
             for r in csv.DictReader((out / "player_id_map.csv").open(encoding="utf-8"))}
    pid_name = {r["personId"]: r["name"] for r in
                csv.DictReader((out / "players_totals.csv").open(encoding="utf-8"))}
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    skip = trk.load_exclusions() | trk.load_lineup_exclusions()
    ids = [m for m in schedule[phase] if m not in skip]

    # (team_code, frozenset personId) -> {'off':Counter, 'def':Counter}
    lu = defaultdict(lambda: {"off": defaultdict(float), "def": defaultdict(float)})

    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        code = {1: d["tm"]["1"]["code"], 2: d["tm"]["2"]["code"]}
        pid = {}
        for t in ("1", "2"):
            for k, p in d["tm"][t]["pl"].items():
                pp = idmap.get((mid, code[int(t)], p.get("name")))
                if pp:
                    pid[(int(t), int(k))] = pp
        for e, oncourt in opp_mod.walk_oncourt(d):
            st = onoff.estats(e)
            if not st:
                continue
            tno = int(e["tno"]) if e.get("tno") else 0
            if tno not in (1, 2):
                continue
            other = 2 if tno == 1 else 1
            L = frozenset(pid.get((tno, p)) for p in oncourt[tno])
            Lo = frozenset(pid.get((other, p)) for p in oncourt[other])
            if None not in L and len(L) == 5:
                for k, v in st.items():
                    lu[(code[tno], L)]["off"][k] += v
            if None not in Lo and len(Lo) == 5:
                for k, v in st.items():
                    lu[(code[other], Lo)]["def"][k] += v

    rows = []
    for (team, L), s in lu.items():
        op = poss(s["off"])
        dp = poss(s["def"])
        if op < MIN_POSS:
            continue
        ortg = 100 * s["off"]["PTS"] / op if op else 0
        drtg = 100 * s["def"]["PTS"] / dp if dp else 0
        names = " / ".join(sorted(pid_name.get(p, p) for p in L))
        rows.append({
            "team": team, "lineup": names,
            "Poss": round(op), "ORtg": round(ortg, 1), "DRtg": round(drtg, 1),
            "Net": round(ortg - drtg, 1),
            "personIds": "|".join(sorted(L)),
        })
    rows.sort(key=lambda r: (r["team"], -r["Poss"]))

    cols = ["team", "lineup", "Poss", "ORtg", "DRtg", "Net", "personIds"]
    with (out / "lineups_by_team.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"Quintetos por equipo (CRUDO, >= {MIN_POSS} pos) — {sum(1 for _ in rows)} quintetos")
    print("NO comparable entre equipos (rivales distintos, sin ajuste).")
    show = [r for r in rows if not team_filter or r["team"] == team_filter] or rows
    if team_filter:
        print(f"\n=== Quintetos de {team_filter} (>= {MIN_POSS} pos, por posesiones) ===")
        print(f"  {'Poss':>5} {'ORtg':>6} {'DRtg':>6} {'Net':>6}  quinteto")
        for r in show:
            print(f"  {r['Poss']:>5} {r['ORtg']:>6} {r['DRtg']:>6} {r['Net']:>+6}  {r['lineup']}")
    print(f"\nSalida: {out / 'lineups_by_team.csv'}")


if __name__ == "__main__":
    main()
