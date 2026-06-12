"""
15_export_json — Exporta los CSV del pipeline a JSON estático para la web interna (Vite+React).

Toma players_totals, players_percentiles, player_shotzones, players_onoff, teams_ratings y produce:
  web/public/data/players.json   { personId: {basic, percentiles, zones, onoff, chart} }   (LIGA COMPLETA)
  web/public/data/teams.json     { code: {ratings + 4 factores} }
  web/public/charts/{personId}.svg  (copia de las cartas ya generadas, keyeadas por personId)

Foco Urunday = navegación; el dataset es la liga entera (todo jugador tiene perfil). Una clave por personId.
"""
import csv
import importlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

zones = importlib.import_module("11_shotzones")
chart12 = importlib.import_module("12_shotchart")  # golden_test, render

ROOT = Path(__file__).resolve().parent.parent
AGG = ROOT / "data" / "agg" / "clasificatorio_lub_25_26"
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
WEB_DATA = ROOT / "web" / "public" / "data"
WEB_CHARTS = ROOT / "web" / "public" / "charts"
CHARTS_SRC = AGG / "charts" / "players"
PHASE = "Clasificatorio LUB 25/26"

PERC_META = {"personId", "name", "team", "pos", "MIN", "GP"}


def team_zones():
    """Camina la fase y devuelve (off, deff, league) por equipo: code -> zone -> [FGA,FGM,3PM]."""
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = [m for m in schedule[PHASE] if m not in zones.load_exclusions()]
    off = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    deff = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    league = defaultdict(lambda: [0, 0, 0])
    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        code = {t: d["tm"][t]["code"] for t in ("1", "2")}
        for t in ("1", "2"):
            other = "2" if t == "1" else "1"
            for s in d["tm"][t].get("shot", []):
                zn = zones.zone(s); made = int(s.get("r", 0)) == 1; three = s["actionType"] == "3pt"
                league[zn][0] += 1; league[zn][1] += made; league[zn][2] += (made and three)
                for acc, c in ((off, code[t]), (deff, code[other])):
                    v = acc[c][zn]; v[0] += 1; v[1] += made; v[2] += (made and three)
    return off, deff, league


def render_shot(x, y):
    """Coords de DIBUJO (0-100): fold del lado lejano al aro bajo (izquierda) + flip Y de render.
    cx = x folded ; cy = 100 - y folded. Misma convención del golden test (cy=100-y)."""
    if x > 50:
        x, y = 100 - x, 100 - y      # normalización de lado (180° del lado lejano)
    return round(x, 2), round(100 - y, 2)   # flip Y de render


def collect_player_shots(idmap):
    """{personId: [{x,y,made}]} en convención de render, sobre la fase (excluye exclusions)."""
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = [m for m in schedule[PHASE] if m not in zones.load_exclusions()]
    out = defaultdict(list)
    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        pid = {}
        for t in ("1", "2"):
            code = d["tm"][t]["code"]
            for k, p in d["tm"][t]["pl"].items():
                pp = idmap.get((mid, code, p.get("name")))
                if pp:
                    pid[(int(t), int(k))] = pp
        for t in ("1", "2"):
            for s in d["tm"][t].get("shot", []):
                pp = pid.get((int(s["tno"]), int(s["pno"])))
                if not pp:
                    continue
                cx, cy = render_shot(float(s["x"]), float(s["y"]))
                out[pp].append({"x": cx, "y": cy, "made": int(s.get("r", 0)) == 1})
    return out


def efg(v):
    return round(100 * (v[1] + 0.5 * v[2]) / v[0], 1) if v[0] else 0


def zone_list(acc, league):
    tot = sum(acc[z][0] for z in acc) or 1
    out = []
    for z in zones.ZONE_ORDER:
        v = acc.get(z)
        if v and v[0]:
            out.append({"zone": z, "FGA": v[0], "sharePct": round(100 * v[0] / tot, 1),
                        "eFG": efg(v), "leagueEFG": efg(league[z])})
    return out


def role(usg_pct, ast_pct):
    """Clasifica rol cruzando percentiles de USG% y AST% (igual que el dossier, paso 14)."""
    if ast_pct >= 75 and usg_pct >= 60:
        return ("creator", "anota y arma")
    if ast_pct >= 70:
        return ("playmaker", "armador")
    if ast_pct < 20:
        return ("finisher", "finalizador puro")
    if usg_pct >= 70:
        return ("scorer_vol", "anotador de volumen")
    return ("scorer", "anotador")


def generators(team_players):
    """Top-8 por PTS con USG%/AST% y rol (separa quién arma de quién solo anota)."""
    out = []
    for p in sorted(team_players, key=lambda p: -p["basic"]["PTS"])[:8]:
        usg, ast = p["percentiles"].get("USG%"), p["percentiles"].get("AST%")
        if not usg or not ast:
            out.append({"personId": p["personId"], "name": p["name"], "pos": p["pos"],
                        "PTS": p["basic"]["PTS"], "roleCode": "low", "role": "muestra <200′"})
            continue
        code, label = role(usg["pct"], ast["pct"])
        out.append({"personId": p["personId"], "name": p["name"], "pos": p["pos"],
                    "PTS": p["basic"]["PTS"], "USG": usg["val"], "USGpct": usg["pct"],
                    "AST": ast["val"], "ASTpct": ast["pct"], "roleCode": code, "role": label})
    return out


def tactical_reading(off_acc, deff_acc, league, gens):
    """Recuadro: qué explotarles / qué quitarles / a quién presionar (porteado del paso 14)."""
    Z = zones.ZONE_ORDER
    o_str = max((z for z in Z if off_acc.get(z) and off_acc[z][0]),
                key=lambda z: efg(off_acc[z]) - efg(league[z]), default=None)
    d_weak = max((z for z in Z if deff_acc.get(z) and deff_acc[z][0] >= 20),
                 key=lambda z: efg(deff_acc[z]) - efg(league[z]), default=None)
    if d_weak and efg(deff_acc[d_weak]) - efg(league[d_weak]) >= 3:
        explotar = f"{d_weak}: le anotan {efg(deff_acc[d_weak]):.0f} eFG ahí (liga {efg(league[d_weak]):.0f}), sobre la media."
    else:
        explotar = "Sin agujero defensivo claro (defienden todo ≤ media): buscar volumen de aro y segundas oportunidades."
    quitar = (f"{o_str}: su tiro más eficiente ({efg(off_acc[o_str]):.0f} eFG vs liga {efg(league[o_str]):.0f}). Cerrar ese sector."
              if o_str else "")
    creators = [g["name"] for g in gens if g["roleCode"] in ("creator", "playmaker")]
    if creators:
        presionar = f"{', '.join(creators)}: generan el juego (AST% top liga). Presionar la FUENTE, no al finalizador."
    elif gens:
        presionar = f"{gens[0]['name']}: su principal volumen ofensivo."
    else:
        presionar = ""
    return {"explotar": explotar, "quitar": quitar, "presionar": presionar}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def read(name):
    return list(csv.DictReader((AGG / name).open(encoding="utf-8")))


def num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return v


def main():
    # GATE: el golden test de Moller debe pasar antes de exportar coords de tiro.
    if not chart12.golden_test():
        raise SystemExit("ABORTADO: golden test FALLA, orientación de tiro no confiable.")

    WEB_DATA.mkdir(parents=True, exist_ok=True)

    totals = {r["personId"]: r for r in read("players_totals.csv")}
    perc = {r["personId"]: r for r in read("players_percentiles.csv")}
    onoff = {r["personId"]: r for r in read("players_onoff.csv")}
    teams_r = {r["code"]: r for r in read("teams_ratings.csv")}
    idmap = {(r["matchId"], r["team"], r["name"]): r["personId"] for r in read("player_id_map.csv")}
    pshots = collect_player_shots(idmap)

    zones = {}
    for r in read("player_shotzones.csv"):
        zones.setdefault(r["personId"], []).append({
            "zone": r["zone"], "FGA": int(r["FGA"]), "FGM": int(r["FGM"]),
            "FGpct": float(r["FGpct"]), "eFG": float(r["eFG"]),
        })

    # percentiles -> {metric: {val, pct}}
    def perc_block(pid):
        r = perc.get(pid)
        if not r:
            return {}
        out = {}
        for col in r:
            if col in PERC_META or col.endswith("_pct"):
                continue
            pc = r.get(col + "_pct")
            if pc not in (None, ""):
                out[col] = {"val": num(r[col]), "pct": num(pc)}
        return out

    players = {}
    for pid, t in totals.items():
        fga, fgm = int(t["FGA"]), int(t["FGM"])
        o = onoff.get(pid)
        players[pid] = {
            "personId": pid, "name": t["name"], "team": t["team"],
            "teamName": teams_r.get(t["team"], {}).get("name", t["team"]),
            "pos": t["pos"], "GP": int(t["GP"]), "MIN": float(t["MIN"]),
            "basic": {
                "PTS": int(t["PTS"]), "REB": int(t["REB"]), "AST": int(t["AST"]),
                "FGM": fgm, "FGA": fga, "FGpct": round(100 * fgm / fga, 1) if fga else 0,
                "3PM": int(t["3PM"]), "3PA": int(t["3PA"]),
                "FTM": int(t["FTM"]), "FTA": int(t["FTA"]),
                "STL": int(t["STL"]), "BLK": int(t["BLK"]), "TOV": int(t["TOV"]),
            },
            "percentiles": perc_block(pid),
            "zones": zones.get(pid, []),
            "onoff": ({
                "on_off": num(o["on_off"]), "Net_on": num(o["Net_on"]), "Net_off": num(o["Net_off"]),
                "ORtg_on": num(o["ORtg_on"]), "DRtg_on": num(o["DRtg_on"]),
                "Poss_on": num(o["Poss_on"]), "Poss_off": num(o["Poss_off"]),
                "qualified": o["qualified"] == "True",
            } if o else None),
            "shots": pshots.get(pid, []),
            "inPool": pid in perc,
        }

    # --- equipos: ratings + zonas atk/def + líderes + plantel ---
    off, deff, league = team_zones()
    by_team = defaultdict(list)
    for pid, p in players.items():
        by_team[p["team"]].append(p)

    def leaders(roster, stat):
        rows = [(p, p["basic"][stat] / p["GP"]) for p in roster if p["GP"]]
        rows.sort(key=lambda x: -x[1])
        return [{"personId": p["personId"], "name": p["name"], "val": round(v, 1)} for p, v in rows[:3]]

    teams = {}
    for code, r in teams_r.items():
        roster = sorted(by_team.get(code, []), key=lambda p: -p["MIN"])
        gens = generators(by_team.get(code, []))
        teams[code] = {
            "code": code, "name": r["name"],
            "ratings": {k: num(v) for k, v in r.items() if k not in ("code", "name")},
            "reading": tactical_reading(off[code], deff[code], league, gens),
            "generators": gens,
            "zonesOff": zone_list(off[code], league),
            "zonesDef": zone_list(deff[code], league),
            "leaders": {"pts": leaders(roster, "PTS"), "reb": leaders(roster, "REB"),
                        "ast": leaders(roster, "AST")},
            "roster": [{"personId": p["personId"], "name": p["name"], "pos": p["pos"],
                        "GP": p["GP"], "MIN": round(p["MIN"]), "ppg": round(p["basic"]["PTS"] / p["GP"], 1) if p["GP"] else 0,
                        "inPool": p["inPool"]} for p in roster],
        }

    (WEB_DATA / "players.json").write_text(json.dumps(players, ensure_ascii=False, indent=1), encoding="utf-8")
    (WEB_DATA / "teams.json").write_text(json.dumps(teams, ensure_ascii=False, indent=1), encoding="utf-8")

    npool = sum(1 for p in players.values() if p["inPool"])
    nshots = sum(1 for p in players.values() if p["shots"])
    print(f"players.json: {len(players)} jugadores ({npool} con percentiles, {nshots} con tiros)")
    print(f"teams.json: {len(teams)} equipos")
    print(f"Salida en {WEB_DATA}")


if __name__ == "__main__":
    main()
