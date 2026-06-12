"""
09_onoff — On/off CRUDO por jugador (net rating del equipo con él EN CANCHA vs EN BANCA).

ON  = puntos/posesiones del equipo (y del rival) acumulados mientras el jugador estuvo en cancha.
OFF = total del partido (en los partidos que jugó) MENOS lo de ON -> rendimiento con él en banca.
Posesiones por estimador de Oliver: Pos = FGA - OREB + TOV + 0.44*FTA (mismo on y off).

  ORtg = 100*PTS/Pos del equipo ; DRtg = 100*PTS_riv/Pos_riv ; Net = ORtg - DRtg
  on_off = Net_on - Net_off

*** CRUDO / DESCRIPTIVO, NO CAUSAL ***
Dice si el equipo fue mejor/peor con el jugador en cancha; NO aísla su aporte de CON QUIÉN juega
(un suplente que sale con titulares puede inflar; un titular que carga minutos sin descanso, deprimir).
No es RAPM ni ajusta por compañeros/rivales. Para ranking causal hace falta un modelo aparte.

Pool: jugadores con MIN totales >= 200 (mismo del paso 06). Excluye exclusions + lineup_exclusions.
Salida: data/agg/{slug}/players_onoff.csv
"""
import csv
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

trk = importlib.import_module("07_tracking")
opp_mod = importlib.import_module("08_opportunity")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
MIN_POOL = 200.0
# El diferencial on/off es inestable si la muestra ON u OFF es chica (un iron-man tiene poquísimas
# posesiones en banca -> su Net_off es ruido). Para el ranking exigimos un piso de posesiones EN AMBAS.
QUAL_POSS = 200


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def estats(e):
    """Stats de posesión + puntos de un evento, para el equipo que lo ejecuta."""
    at = e.get("actionType")
    s = {}
    made = int(e.get("success", 0)) == 1
    if at in ("2pt", "3pt"):
        s["FGA"] = 1
        if made:
            s["PTS"] = 3 if at == "3pt" else 2
    elif at == "freethrow":
        s["FTA"] = 1
        if made:
            s["PTS"] = 1
    elif at == "turnover":
        s["TOV"] = 1
    elif at == "rebound":
        s["OREB" if e.get("subType") == "offensive" else "DREB"] = 1
    return s


def poss(c):
    return c["FGA"] - c["OREB"] + c["TOV"] + 0.44 * c["FTA"]


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slug(phase)
    idmap = {(r["matchId"], r["team"], r["name"]): r["personId"]
             for r in csv.DictReader((out / "player_id_map.csv").open(encoding="utf-8"))}
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    skip = trk.load_exclusions() | trk.load_lineup_exclusions()
    ids = [m for m in schedule[phase] if m not in skip]

    tm_on = defaultdict(lambda: defaultdict(float))    # personId -> contexto equipo on-court
    opp_on = defaultdict(lambda: defaultdict(float))
    tm_tot = defaultdict(lambda: defaultdict(float))   # personId -> total equipo en sus partidos
    opp_tot = defaultdict(lambda: defaultdict(float))

    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        pid, pteam = {}, {}
        for t in ("1", "2"):
            code = d["tm"][t]["code"]
            for k, p in d["tm"][t]["pl"].items():
                pp = idmap.get((mid, code, p.get("name")))
                if pp:
                    pid[(int(t), int(k))] = pp
                    pteam[pp] = int(t)
        teamtot = {1: defaultdict(float), 2: defaultdict(float)}
        pon_tm = defaultdict(lambda: defaultdict(float))
        pon_opp = defaultdict(lambda: defaultdict(float))
        for e, oncourt in opp_mod.walk_oncourt(d):
            st = estats(e)
            if not st:
                continue
            tno = int(e["tno"]) if e.get("tno") else 0
            if tno not in (1, 2):
                continue
            other = 2 if tno == 1 else 1
            for k, v in st.items():
                teamtot[tno][k] += v
            for p in oncourt[tno]:
                key = pid.get((tno, p))
                if key:
                    for k, v in st.items():
                        pon_tm[key][k] += v
            for p in oncourt[other]:
                key = pid.get((other, p))
                if key:
                    for k, v in st.items():
                        pon_opp[key][k] += v
        for pp, t in pteam.items():
            for k, v in pon_tm[pp].items():
                tm_on[pp][k] += v
            for k, v in pon_opp[pp].items():
                opp_on[pp][k] += v
            for k, v in teamtot[t].items():
                tm_tot[pp][k] += v
            for k, v in teamtot[2 if t == 1 else 1].items():
                opp_tot[pp][k] += v

    tot = {r["personId"]: r for r in
           csv.DictReader((out / "players_totals.csv").open(encoding="utf-8"))}
    pool = [p for p, r in tot.items() if float(r["MIN"]) >= MIN_POOL]

    rows = []
    for pp in pool:
        r = tot[pp]
        on_p, off_p = poss(tm_on[pp]), poss(tm_tot[pp]) - poss(tm_on[pp])
        on_o, off_o = poss(opp_on[pp]), poss(opp_tot[pp]) - poss(opp_on[pp])
        pts_on, pts_off = tm_on[pp]["PTS"], tm_tot[pp]["PTS"] - tm_on[pp]["PTS"]
        opp_on_pts, opp_off_pts = opp_on[pp]["PTS"], opp_tot[pp]["PTS"] - opp_on[pp]["PTS"]
        ortg_on = 100 * pts_on / on_p if on_p else 0
        drtg_on = 100 * opp_on_pts / on_o if on_o else 0
        ortg_off = 100 * pts_off / off_p if off_p else 0
        drtg_off = 100 * opp_off_pts / off_o if off_o else 0
        net_on, net_off = ortg_on - drtg_on, ortg_off - drtg_off
        rows.append({
            "personId": pp, "name": r["name"], "team": r["team"], "pos": r["pos"],
            "MIN": r["MIN"], "GP": r["GP"],
            "Poss_on": round(on_p), "ORtg_on": round(ortg_on, 1), "DRtg_on": round(drtg_on, 1),
            "Net_on": round(net_on, 1),
            "Poss_off": round(off_p), "ORtg_off": round(ortg_off, 1), "DRtg_off": round(drtg_off, 1),
            "Net_off": round(net_off, 1),
            "on_off": round(net_on - net_off, 1),
            "qualified": round(on_p) >= QUAL_POSS and round(off_p) >= QUAL_POSS,
        })
    rows.sort(key=lambda x: -x["on_off"])
    cols = ["personId", "name", "team", "pos", "MIN", "GP", "Poss_on", "ORtg_on", "DRtg_on",
            "Net_on", "Poss_off", "ORtg_off", "DRtg_off", "Net_off", "on_off", "qualified"]
    with (out / "players_onoff.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    qual = [r for r in rows if r["qualified"]]
    print(f"On/off CRUDO (descriptivo, NO causal) — pool MIN>={MIN_POOL:.0f}: {len(rows)} jugadores")
    print(f"Calificados (Poss_on y Poss_off >= {QUAL_POSS}): {len(qual)}")
    head = f"  {'jugador':<20}{'eq':<5}{'on_off':>7}{'Net_on':>8}{'Net_off':>8}{'Poss_on':>9}{'Poss_off':>9}"

    def block(title, rs):
        print(f"\n=== {title} ===")
        print(head)
        for r in rs:
            print(f"  {r['name']:<20}{r['team']:<5}{r['on_off']:>+7}{r['Net_on']:>+8}{r['Net_off']:>+8}{r['Poss_on']:>9}{r['Poss_off']:>9}")

    block("TOP 5 on/off (CALIFICADOS)", qual[:5])
    block("BOTTOM 5 on/off (CALIFICADOS)", qual[-5:])
    block("TOP 5 on/off (sin filtro - ojo muestra)", rows[:5])
    print(f"\nSalida: {out / 'players_onoff.csv'}")


if __name__ == "__main__":
    main()
