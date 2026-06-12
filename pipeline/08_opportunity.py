"""
08_opportunity — Tasas de oportunidad (USG%, AST%, REB%, OREB%, DREB%, STL%, BLK%) ON-COURT.

Denominadores = oportunidades del EQUIPO / RIVAL mientras el jugador estuvo en cancha (no totales
del partido). Se recorre el pbp en orden cronológico (igual que 07), se mantiene el quinteto por
equipo y a cada evento de boxscore se le acreditan los contextos team/opp a los 5 en cancha.

Numeradores = stats propios del jugador (players_totals.csv, por personId).
  USG%  = 100 * (FGA + 0.44*FTA + TOV) / (Tm FGA + 0.44*FTA + TOV)_oncourt
  AST%  = 100 * AST / (Tm FGM_oncourt - FGM)
  REB%  = 100 * REB / (Tm REB + Opp REB)_oncourt
  OREB% = 100 * OREB / (Tm OREB + Opp DREB)_oncourt
  DREB% = 100 * DREB / (Tm DREB + Opp OREB)_oncourt
  STL%  = 100 * STL / Opp_Pos_oncourt        (Opp_Pos = FGA - OREB + TOV + 0.44*FTA)
  BLK%  = 100 * BLK / Opp_2PA_oncourt

Excluye exclusions.csv (boxscore) y lineup_exclusions.csv (feed corrupto).
Integra los percentiles (pool MIN>=200) a players_percentiles.csv.
"""
import csv
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

trk = importlib.import_module("07_tracking")  # pkey, clocksec, exclusiones

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
MIN_POOL = 200.0


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def starters(d, t):
    return {int(k) for k, p in d["tm"][t]["pl"].items() if p.get("starter")}


def walk_oncourt(d):
    """Genera (evento, oncourt) en orden cronológico; oncourt = {tno: set(pno)} ANTES del evento."""
    oncourt = {1: set(starters(d, "1")), 2: set(starters(d, "2"))}
    for e in reversed(d["pbp"]):
        if not e.get("period"):
            continue
        yield e, oncourt
        if e.get("actionType") == "substitution":
            tno, pno = int(e["tno"]), int(e["pno"])
            if e.get("subType") == "in":
                oncourt[tno].add(pno)
            elif e.get("subType") == "out":
                oncourt[tno].discard(pno)


# stat de equipo que aporta cada evento al denominador (None = no aporta)
def event_team_stats(e):
    at = e.get("actionType")
    s = {}
    if at in ("2pt", "3pt"):
        s["FGA"] = 1
        if int(e.get("success", 0)) == 1:
            s["FGM"] = 1
        if at == "2pt":
            s["2PA"] = 1
    elif at == "freethrow":
        s["FTA"] = 1
    elif at == "turnover":
        s["TOV"] = 1
    elif at == "rebound":
        s["OREB" if e.get("subType") == "offensive" else "DREB"] = 1
    return s


def accumulate(ids):
    """Por personId: contextos team/opp on-court. Devuelve (tm, opp) dicts de Counters."""
    tm = defaultdict(lambda: defaultdict(float))
    opp = defaultdict(lambda: defaultdict(float))
    # validación: por (mid,tno) sumar usage de jugadores vs 5*usage de equipo
    sample_close = []
    for idx, mid in enumerate(ids):
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        pid = {}  # (tno,pno) -> personId
        idmap = ID_MAP
        for t in ("1", "2"):
            code = d["tm"][t]["code"]
            for k, p in d["tm"][t]["pl"].items():
                pp = idmap.get((mid, code, p.get("name")))
                if pp:
                    pid[(int(t), int(k))] = pp
        team_usg = defaultdict(float)       # usage de equipo (para validación)
        sum_tm_usg_on = defaultdict(float)  # suma de tm_usg_on de los jugadores
        for e, oncourt in walk_oncourt(d):
            st = event_team_stats(e)
            if not st:
                continue
            tno = int(e["tno"]) if e.get("tno") else 0
            if tno not in (1, 2):
                continue
            other = 2 if tno == 1 else 1
            usg_ev = st.get("FGA", 0) + 0.44 * st.get("FTA", 0) + st.get("TOV", 0)
            team_usg[tno] += usg_ev
            for p in oncourt[tno]:
                key = pid.get((tno, p))
                if not key:
                    continue
                for k, v in st.items():
                    tm[key][k] += v
                sum_tm_usg_on[tno] += usg_ev
            for p in oncourt[other]:
                key = pid.get((other, p))
                if not key:
                    continue
                for k, v in st.items():
                    opp[key][k] += v
        if idx < 8:  # muestra de validación
            for tno in (1, 2):
                if team_usg[tno]:
                    sample_close.append((mid, tno, sum_tm_usg_on[tno] / team_usg[tno]))
    return tm, opp, sample_close


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slug(phase)
    global ID_MAP
    ID_MAP = {(r["matchId"], r["team"], r["name"]): r["personId"]
              for r in csv.DictReader((out / "player_id_map.csv").open(encoding="utf-8"))}

    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    skip = trk.load_exclusions() | trk.load_lineup_exclusions()
    ids = [m for m in schedule[phase] if m not in skip]

    tm, opp, sample = accumulate(ids)

    # numeradores del jugador desde players_totals
    tot = {r["personId"]: r for r in
           csv.DictReader((out / "players_totals.csv").open(encoding="utf-8"))}

    def fnum(r, k):
        return float(r.get(k, 0) or 0)

    rates = {}
    for pidv, r in tot.items():
        T, O = tm[pidv], opp[pidv]
        usg_den = T["FGA"] + 0.44 * T["FTA"] + T["TOV"]
        ast_den = T["FGM"] - fnum(r, "FGM")
        oreb_den = T["OREB"] + O["DREB"]
        dreb_den = T["DREB"] + O["OREB"]
        reb_den = T["OREB"] + T["DREB"] + O["OREB"] + O["DREB"]
        opp_pos = O["FGA"] - O["OREB"] + O["TOV"] + 0.44 * O["FTA"]
        opp_2pa = O["2PA"]
        rates[pidv] = {
            "USG%": round(100 * (fnum(r, "FGA") + 0.44 * fnum(r, "FTA") + fnum(r, "TOV")) / usg_den, 1) if usg_den else 0.0,
            "AST%": round(100 * fnum(r, "AST") / ast_den, 1) if ast_den > 0 else 0.0,
            "REB%": round(100 * fnum(r, "REB") / reb_den, 1) if reb_den else 0.0,
            "OREB%": round(100 * fnum(r, "OREB") / oreb_den, 1) if oreb_den else 0.0,
            "DREB%": round(100 * fnum(r, "DREB") / dreb_den, 1) if dreb_den else 0.0,
            "STL%": round(100 * fnum(r, "STL") / opp_pos, 1) if opp_pos else 0.0,
            "BLK%": round(100 * fnum(r, "BLK") / opp_2pa, 1) if opp_2pa else 0.0,
        }

    NEW = ["USG%", "AST%", "REB%", "OREB%", "DREB%", "STL%", "BLK%"]
    pool = [pidv for pidv, r in tot.items() if float(r["MIN"]) >= MIN_POOL]
    arrs = {m: [rates[pidv][m] for pidv in pool] for m in NEW}

    def pctl(x, arr):
        n = len(arr)
        return round(100 * (sum(1 for v in arr if v < x) + 0.5 * sum(1 for v in arr if v == x)) / n, 1)

    # merge a players_percentiles.csv (mismo pool >=200)
    pct_path = out / "players_percentiles.csv"
    existing = list(csv.DictReader(pct_path.open(encoding="utf-8")))
    cols = list(existing[0].keys())
    for m in NEW:
        cols += [m, m + "_pct"]
    for row in existing:
        pidv = row["personId"]
        for m in NEW:
            row[m] = rates[pidv][m]
            row[m + "_pct"] = pctl(rates[pidv][m], arrs[m])
    with pct_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(existing)

    # === VALIDACIÓN: USG de los 5 en cancha suma ~100% ===
    print(f"Tasas de oportunidad on-court — pool MIN>={MIN_POOL:.0f}: {len(pool)} jugadores")
    print("\n=== VALIDACIÓN: usage on-court de los 5 / usage del equipo (debe ser ~5.00 =>")
    print("    los 5 en cancha cubren ~100% del usage en cada posesión) ===")
    for mid, tno, ratio in sample:
        print(f"  {mid} t{tno}: ratio = {ratio:.3f}  (5 jugadores suman {ratio/5*100:.1f}% del usage de equipo)")

    print("\n=== SANITY percentiles (USG/AST/REB%) ===")
    name2pid = {r["name"]: pidv for pidv, r in tot.items()}
    for who in ("M. Sarni", "E. Weaver", "A. Gilder Jr."):
        pidv = name2pid.get(who)
        if not pidv or pidv not in pool:
            print(f"  {who}: fuera de pool"); continue
        v = rates[pidv]
        cells = "  ".join(f"{m} {v[m]:>5} (pct {pctl(v[m], arrs[m]):>5})" for m in ("USG%", "AST%", "REB%"))
        print(f"  {who:<15} {cells}")
    print(f"\nIntegrado en {pct_path}")


if __name__ == "__main__":
    main()
