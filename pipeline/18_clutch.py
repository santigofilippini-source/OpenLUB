"""
18_clutch - Rendimiento en momentos CLUTCH, por equipo y por jugador (desde el pbp).

Definición estándar (NBA.com): ventana clutch = últimos 5:00 del Q4 (o de cualquier prórroga) con
diferencia de marcador <= 5 puntos. Se evalúa MOMENTO A MOMENTO: un evento cuenta como clutch si,
AL EJECUTARSE, el período califica, el reloj <= 5:00 y el margen PRE-evento es <= 5. (Pre-evento =
el marcador con el que se tomó la acción: a un tiro que estira de 5 a 7 se lo tomó en situación de
5, así que es clutch. El feed da `s1/s2` POST-evento; le resto los puntos de ese tiro al equipo
que anotó para obtener el margen previo.)

Reloj: el feed da `clock` "MM:SS:CC" en cuenta regresiva dentro del período -> últimos 5:00 = <= 300s.
En prórroga (5:00 de largo) eso es TODA la prórroga, como manda la definición.

Calcula, en esa ventana, por jugador y por equipo: PTS, FGA/FGM/3PM, FTA/FTM, TOV, eFG% y
(a nivel equipo) posesiones clutch (estimador de Oliver: FGA - OREB + TOV + 0.44*FTA).

NO construye vista ni umbral: PRIMERO imprime la DISTRIBUCIÓN de muestra (la LUB tiene clutch chico)
para decidir el umbral con datos. Base = Clasificatorio, COMPLETE menos exclusiones. Jugador keyeado
por personId (player_id_map.csv del paso 05). NO toca ningún paso existente.
"""
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
AGG = ROOT / "data" / "agg" / "clasificatorio_lub_25_26"
WEB_DATA = ROOT / "web" / "public" / "data"
INDEX = "clasificatorio_lub_25_26_index.csv"
PHASE = "Clasificatorio LUB 25/26"

CLUTCH_SECS = 300.0      # últimos 5:00
CLUTCH_MARGIN = 5        # diferencia <= 5
PTS = {"2pt": 2, "3pt": 3, "freethrow": 1}

# Umbrales de TIROS clutch (FGA) por debajo de los cuales la web NO muestra el eFG% (lo grisa con
# "muestra insuficiente"). Los conteos crudos (PTS, FGM-FGA, TOV) se muestran SIEMPRE: son hechos,
# no estimaciones. Decididos mirando la distribución real (clutch en la LUB es muy chico).
PLAYER_FGA_MIN = 10      # 9 jugadores califican en toda la liga
TEAM_FGA_MIN = 40        # 8 de 12 equipos califican


def slug(p):
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def clock_secs(c):
    """'MM:SS:CC' (regresivo) -> segundos restantes en el período. '' -> 99 (no clutch)."""
    if not c:
        return 99.0
    parts = c.split(":")
    mm, ss = int(parts[0]), int(parts[1])
    cc = int(parts[2]) if len(parts) > 2 else 0
    return mm * 60 + ss + cc / 100.0


def is_clutch_period(e):
    """Q4 regular (period 4) o cualquier prórroga."""
    pt = e.get("periodType")
    if pt == "OVERTIME":
        return True
    return pt == "REGULAR" and e.get("period", 0) >= 4


def event_points(e):
    """Puntos que anotó ESTE evento (0 si no fue canasta/FT convertida)."""
    at = e.get("actionType")
    if at in PTS and e.get("success") == 1:
        return PTS[at]
    return 0


def margin_pre(e):
    """Margen ABSOLUTO de marcador ANTES de aplicar este evento."""
    s1, s2 = int(e.get("s1") or 0), int(e.get("s2") or 0)
    p = event_points(e)
    if e.get("tno") == 1:
        s1 -= p
    elif e.get("tno") == 2:
        s2 -= p
    return abs(s1 - s2)


def main():
    excl = load_exclusions()
    ids = [r["matchId"] for r in csv.DictReader((SCH_DIR / INDEX).open(encoding="utf-8"))
           if r["status"] == "COMPLETE" and r["matchId"] not in excl]
    idmap = {(r["matchId"], r["team"], r["name"]): r["personId"]
             for r in csv.DictReader((AGG / "player_id_map.csv").open(encoding="utf-8"))}

    # acumuladores
    # player[pid] = [PTS,FGA,FGM,3PM,FTA,FTM,TOV] + set de partidos clutch
    P_STATS = ["PTS", "FGA", "FGM", "3PM", "FTA", "FTM", "TOV"]
    pl = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0])
    pl_games = defaultdict(set)
    pl_name = {}
    pl_team = {}
    # team[code] = [PTS,FGA,FGM,3PM,FTA,FTM,TOV,OREB]
    tm = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0])
    tm_name = {}
    tm_games = defaultdict(set)

    clutch_games = set()        # partidos con >=1 evento clutch

    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        code = {1: d["tm"]["1"]["code"], 2: d["tm"]["2"]["code"]}
        tm_name[code[1]] = d["tm"]["1"]["name"]; tm_name[code[2]] = d["tm"]["2"]["name"]
        # (tno,pno) -> personId
        pid = {}
        for t in (1, 2):
            for k, p in d["tm"][str(t)]["pl"].items():
                pp = idmap.get((mid, code[t], p.get("name")))
                if pp:
                    pid[(t, int(k))] = pp
                    pl_name[pp] = p.get("name")
                    pl_team[pp] = code[t]

        for e in d["pbp"]:
            tno = e.get("tno")
            if tno not in (1, 2):
                continue
            if not is_clutch_period(e):
                continue
            if clock_secs(e.get("clock", "")) > CLUTCH_SECS:
                continue
            if margin_pre(e) > CLUTCH_MARGIN:
                continue
            at = e.get("actionType")
            c = code[tno]
            clutch_games.add(mid)
            tm_games[c].add(mid)
            pp = pid.get((tno, e.get("pno")))
            if pp:
                pl_games[pp].add(mid)

            def add(arr, **kw):
                idx = {"PTS": 0, "FGA": 1, "FGM": 2, "3PM": 3, "FTA": 4, "FTM": 5, "TOV": 6}
                for k, v in kw.items():
                    arr[idx[k]] += v

            succ = e.get("success") == 1
            if at == "2pt":
                add(tm[c], FGA=1, **({"FGM": 1, "PTS": 2} if succ else {}))
                if pp: add(pl[pp], FGA=1, **({"FGM": 1, "PTS": 2} if succ else {}))
            elif at == "3pt":
                add(tm[c], FGA=1, **({"FGM": 1, "3PM": 1, "PTS": 3} if succ else {}))
                if pp: add(pl[pp], FGA=1, **({"FGM": 1, "3PM": 1, "PTS": 3} if succ else {}))
            elif at == "freethrow":
                add(tm[c], FTA=1, **({"FTM": 1, "PTS": 1} if succ else {}))
                if pp: add(pl[pp], FTA=1, **({"FTM": 1, "PTS": 1} if succ else {}))
            elif at == "turnover":
                add(tm[c], TOV=1)
                if pp: add(pl[pp], TOV=1)
            elif at == "rebound" and e.get("subType") == "offensive" and succ:
                tm[c][7] += 1   # OREB (solo a nivel equipo, para posesiones)

    def efg(s):
        return round(100 * (s[2] + 0.5 * s[3]) / s[1], 1) if s[1] else 0.0

    def poss(s):
        return s[1] - s[7] + s[6] + 0.44 * s[4]   # FGA - OREB + TOV + 0.44*FTA

    # --- CSV por equipo ---
    AGG.mkdir(parents=True, exist_ok=True)
    trows = []
    for c in sorted(tm):
        s = tm[c]
        trows.append({"team": c, "name": tm_name[c], "clutch_games": len(tm_games[c]),
                      "Poss": round(poss(s), 1), "PTS": s[0], "FGA": s[1], "FGM": s[2],
                      "3PM": s[3], "FTA": s[4], "FTM": s[5], "TOV": s[6], "eFG": efg(s)})
    trows.sort(key=lambda r: -r["FGA"])
    with (AGG / "clutch_by_team.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "name", "clutch_games", "Poss", "PTS",
                                          "FGA", "FGM", "3PM", "FTA", "FTM", "TOV", "eFG"])
        w.writeheader(); w.writerows(trows)

    # --- CSV por jugador ---
    prows = []
    for pp, s in pl.items():
        prows.append({"personId": pp, "name": pl_name[pp], "team": pl_team[pp],
                      "clutch_games": len(pl_games[pp]), "PTS": s[0], "FGA": s[1], "FGM": s[2],
                      "3PM": s[3], "FTA": s[4], "FTM": s[5], "TOV": s[6], "eFG": efg(s)})
    prows.sort(key=lambda r: (-r["FGA"], -r["PTS"]))
    with (AGG / "clutch_by_player.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["personId", "name", "team", "clutch_games", "PTS",
                                          "FGA", "FGM", "3PM", "FTA", "FTM", "TOV", "eFG"])
        w.writeheader(); w.writerows(prows)

    total_poss = sum(poss(tm[c]) for c in tm)

    # --- JSON para la web (umbral + flag qualified como fuente única de verdad) ---
    def jteam(r):
        return {"code": r["team"], "name": r["name"], "clutchGames": r["clutch_games"],
                "Poss": r["Poss"], "PTS": r["PTS"], "FGA": r["FGA"], "FGM": r["FGM"],
                "3PM": r["3PM"], "FTA": r["FTA"], "FTM": r["FTM"], "TOV": r["TOV"],
                "eFG": r["eFG"], "qualified": r["FGA"] >= TEAM_FGA_MIN}

    def jplayer(r):
        return {"personId": r["personId"], "name": r["name"], "team": r["team"],
                "clutchGames": r["clutch_games"], "PTS": r["PTS"], "FGA": r["FGA"],
                "FGM": r["FGM"], "3PM": r["3PM"], "FTA": r["FTA"], "FTM": r["FTM"],
                "TOV": r["TOV"], "eFG": r["eFG"], "qualified": r["FGA"] >= PLAYER_FGA_MIN}

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "clutch.json").write_text(json.dumps({
        "phase": PHASE,
        "thresholds": {"playerFGA": PLAYER_FGA_MIN, "teamFGA": TEAM_FGA_MIN},
        "totalGames": len(ids), "clutchGames": len(clutch_games),
        "totalPoss": round(total_poss),
        "teams": [jteam(r) for r in trows],
        "players": [jplayer(r) for r in prows if r["FGA"] > 0],
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ===================== DISTRIBUCIÓN DE MUESTRA (lo que pediste ANTES de la vista) =====================
    fga_all = [r["FGA"] for r in prows if r["FGA"] > 0]
    fga_all.sort(reverse=True)
    n_games = len(ids)

    print("=" * 72)
    print("DISTRIBUCIÓN DE MUESTRA CLUTCH - LUB Clasificatorio")
    print(f"Definición: últimos 5:00 de Q4/OT con margen <= {CLUTCH_MARGIN}. {n_games} partidos.")
    print("=" * 72)
    print(f"\nPartidos con algún momento clutch: {len(clutch_games)} de {n_games} "
          f"({100*len(clutch_games)/n_games:.0f}%)")
    print(f"Posesiones clutch en TODA la liga (estimador): {total_poss:.0f}")
    print(f"  -> promedio por partido clutch: {total_poss/len(clutch_games):.1f} pos "
          f"(repartidas entre los DOS equipos)")
    print(f"Tiros de campo (FGA) clutch en toda la liga: {sum(fga_all)}")

    print(f"\n--- Distribución de TIROS CLUTCH (FGA) por jugador ---")
    print(f"Jugadores con >=1 tiro clutch: {len(fga_all)}")
    if fga_all:
        print(f"  máximo (un jugador):        {fga_all[0]} tiros")
        print(f"  mediana (de los que tiran): {statistics.median(fga_all):.0f} tiros")
        print(f"  promedio:                   {statistics.mean(fga_all):.1f} tiros")
        for thr in (5, 10, 15, 20):
            n = sum(1 for v in fga_all if v >= thr)
            print(f"  jugadores con >= {thr:>2} tiros clutch: {n}")

    print(f"\n--- Top 12 por tiros clutch (FGA) [muestra al lado] ---")
    print(f"  {'jugador':<22}{'eq':<5}{'PJ':>3}{'FGA':>5}{'FGM':>5}{'3PM':>5}{'PTS':>5}{'TOV':>5}{'eFG%':>7}")
    for r in prows[:12]:
        print(f"  {r['name'][:22]:<22}{r['team']:<5}{r['clutch_games']:>3}{r['FGA']:>5}"
              f"{r['FGM']:>5}{r['3PM']:>5}{r['PTS']:>5}{r['TOV']:>5}{r['eFG']:>7.1f}")

    print(f"\n--- Clutch por EQUIPO (posesiones y tiros) ---")
    print(f"  {'equipo':<6}{'PJ':>4}{'Pos':>7}{'FGA':>5}{'FGM':>5}{'PTS':>5}{'TOV':>5}{'eFG%':>7}")
    for r in trows:
        print(f"  {r['team']:<6}{r['clutch_games']:>4}{r['Poss']:>7.1f}{r['FGA']:>5}"
              f"{r['FGM']:>5}{r['PTS']:>5}{r['TOV']:>5}{r['eFG']:>7.1f}")

    print(f"\nCSV: {AGG / 'clutch_by_team.csv'} y clutch_by_player.csv")
    print(f"JSON web: {WEB_DATA / 'clutch.json'} "
          f"(umbral jugador >={PLAYER_FGA_MIN} FGA, equipo >={TEAM_FGA_MIN} FGA para mostrar eFG%)")


if __name__ == "__main__":
    main()
