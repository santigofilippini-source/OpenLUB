"""
04_team_ratings — Ratings de equipo sobre la fase (default: Clasificatorio, 131 partidos).

Calcula, por equipo y acumulado sobre la fase:
  - ORtg  = 100 * PTS / Pos            (puntos por 100 posesiones)
  - DRtg  = 100 * PTS_riv / Pos_riv
  - NetRtg = ORtg - DRtg
  - Pace  = posesiones por partido
  - Cuatro factores OFENSIVOS: eFG%, TOV%, ORB%, FT Rate
  - Cuatro factores DEFENSIVOS: los ofensivos del rival (eFG% riv, TOV% riv, DRB%, FTR riv)

Posesiones (estimador estándar de Oliver): Pos = FGA - OREB + TOV + 0.44*FTA
Usa los totales de equipo `tot_s*` del data.json, emparejando rival por partido.
EXCLUYE los matchId de exclusions.csv. NO calcula nada per-player.
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


def slug(p): return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")
def i(v): return int(v or 0)


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    if not f.exists():
        return set()
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))}


def team_line(tm):
    """Extrae los totales de equipo relevantes de un partido."""
    g = lambda k: i(tm.get("tot_" + k))
    return {
        "PTS": g("sPoints"), "FGA": g("sFieldGoalsAttempted"), "FGM": g("sFieldGoalsMade"),
        "3PM": g("sThreePointersMade"), "FTA": g("sFreeThrowsAttempted"), "FTM": g("sFreeThrowsMade"),
        "TOV": g("sTurnovers"), "OREB": g("sReboundsOffensive"), "DREB": g("sReboundsDefensive"),
    }


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    excl = load_exclusions()
    ids = [m for m in schedule[phase] if m not in excl]

    # acumular por equipo: stats propios (off) y del rival (def)
    off = defaultdict(lambda: defaultdict(int))
    dff = defaultdict(lambda: defaultdict(int))
    gp = defaultdict(int)
    name = {}

    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        t1, t2 = d["tm"]["1"], d["tm"]["2"]
        c1, c2 = t1.get("code"), t2.get("code")
        name[c1], name[c2] = t1.get("name"), t2.get("name")
        l1, l2 = team_line(t1), team_line(t2)
        for code, own, opp in ((c1, l1, l2), (c2, l2, l1)):
            gp[code] += 1
            for k, v in own.items():
                off[code][k] += v
            for k, v in opp.items():
                dff[code][k] += v

    def poss(s):
        return s["FGA"] - s["OREB"] + s["TOV"] + 0.44 * s["FTA"]

    rows = []
    for code in off:
        o, dd = off[code], dff[code]
        po, pd = poss(o), poss(dd)
        ortg = 100 * o["PTS"] / po if po else 0
        drtg = 100 * dd["PTS"] / pd if pd else 0
        # cuatro factores ofensivos
        efg = (o["FGM"] + 0.5 * o["3PM"]) / o["FGA"] if o["FGA"] else 0
        tov = o["TOV"] / (o["FGA"] + 0.44 * o["FTA"] + o["TOV"]) if o["FGA"] else 0
        orb = o["OREB"] / (o["OREB"] + dd["DREB"]) if (o["OREB"] + dd["DREB"]) else 0
        ftr = o["FTM"] / o["FGA"] if o["FGA"] else 0
        # cuatro factores defensivos (los ofensivos del rival)
        d_efg = (dd["FGM"] + 0.5 * dd["3PM"]) / dd["FGA"] if dd["FGA"] else 0
        d_tov = dd["TOV"] / (dd["FGA"] + 0.44 * dd["FTA"] + dd["TOV"]) if dd["FGA"] else 0
        drb = o["DREB"] / (o["DREB"] + dd["OREB"]) if (o["DREB"] + dd["OREB"]) else 0
        d_ftr = dd["FTM"] / dd["FGA"] if dd["FGA"] else 0
        rows.append({
            "code": code, "name": name[code], "GP": gp[code],
            "ORtg": round(ortg, 1), "DRtg": round(drtg, 1), "NetRtg": round(ortg - drtg, 1),
            "Pace": round(po / gp[code], 1),
            "eFG%": round(efg * 100, 1), "TOV%": round(tov * 100, 1),
            "ORB%": round(orb * 100, 1), "FTR": round(ftr * 100, 1),
            "D_eFG%": round(d_efg * 100, 1), "D_TOV%": round(d_tov * 100, 1),
            "DRB%": round(drb * 100, 1), "D_FTR": round(d_ftr * 100, 1),
        })
    rows.sort(key=lambda r: -r["NetRtg"])

    out = ROOT / "data" / "agg" / slug(phase)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["code", "name", "GP", "ORtg", "DRtg", "NetRtg", "Pace",
            "eFG%", "TOV%", "ORB%", "FTR", "D_eFG%", "D_TOV%", "DRB%", "D_FTR"]
    with (out / "teams_ratings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"Ratings de equipo - {phase} ({len(ids)} partidos)\n")
    print(f"{'#':>2} {'Equipo':<22} {'ORtg':>6} {'DRtg':>6} {'Net':>6} {'Pace':>6} "
          f"{'eFG%':>6} {'TOV%':>6} {'ORB%':>6} {'FTR':>6}")
    for n, r in enumerate(rows, 1):
        print(f"{n:>2} {r['name'][:22]:<22} {r['ORtg']:>6} {r['DRtg']:>6} {r['NetRtg']:>+6} "
              f"{r['Pace']:>6} {r['eFG%']:>6} {r['TOV%']:>6} {r['ORB%']:>6} {r['FTR']:>6}")
    print(f"\nSalida: {out / 'teams_ratings.csv'}")


if __name__ == "__main__":
    main()
