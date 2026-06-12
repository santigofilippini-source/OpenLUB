"""
13_player_shotzones — Cartas de tiro POR JUGADOR (personId), reusando zonas (11) + render (12).

Para cada jugador del pool (MIN>=200): FGA/FGM/eFG% por zona, con FGA visible al lado del % (zonas de
pocos intentos NO son conclusión). Carta visual SVG con el flip de Y anclado; el GOLDEN TEST de Moller
corre como GATE antes de generar cualquier carta (si falla, aborta).

Identidad por personId (paso 05): el tiro trae tno/pno locales -> se mapean a personId por partido.
Salida: player_shotzones.csv (long) + charts/players/{personId}.svg
Scouting: genera cartas de los anotadores top de cada rival de Urunday.
"""
import csv
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

zones = importlib.import_module("11_shotzones")
chart = importlib.import_module("12_shotchart")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
MIN_POOL = 200.0
ZONE_ORDER = zones.ZONE_ORDER


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slug(phase)
    idmap = {(r["matchId"], r["team"], r["name"]): r["personId"]
             for r in csv.DictReader((out / "player_id_map.csv").open(encoding="utf-8"))}
    tot = {r["personId"]: r for r in
           csv.DictReader((out / "players_totals.csv").open(encoding="utf-8"))}
    pool = {p for p, r in tot.items() if float(r["MIN"]) >= MIN_POOL}

    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    excl = zones.load_exclusions()
    ids = [m for m in schedule[phase] if m not in excl]

    zacc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # personId -> zone -> [FGA,FGM,3PM]
    shots = defaultdict(list)                                    # personId -> [(x,y,made,is3)]
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
                z = zones.zone(s)
                made = int(s.get("r", 0)) == 1
                three = s["actionType"] == "3pt"
                zacc[pp][z][0] += 1
                zacc[pp][z][1] += 1 if made else 0
                zacc[pp][z][2] += 1 if (made and three) else 0
                shots[pp].append((float(s["x"]), float(s["y"]), made, three))

    # CSV long del pool
    rows = []
    for pp in pool:
        r = tot[pp]
        for z in ZONE_ORDER:
            v = zacc[pp].get(z)
            if not v or not v[0]:
                continue
            fga, fgm, tpm = v
            rows.append({"personId": pp, "name": r["name"], "team": r["team"], "MIN": r["MIN"],
                         "zone": z, "FGA": fga, "FGM": fgm,
                         "FGpct": round(100 * fgm / fga, 1),
                         "eFG": round(100 * (fgm + 0.5 * tpm) / fga, 1)})
    with (out / "player_shotzones.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["personId", "name", "team", "MIN", "zone", "FGA", "FGM", "FGpct", "eFG"])
        w.writeheader()
        w.writerows(rows)

    def profile(name):
        pp = next((p for p, r in tot.items() if r["name"] == name), None)
        if not pp:
            print(f"  {name}: no encontrado"); return
        r = tot[pp]
        print(f"\n=== {name} ({r['team']}, {r['pos']}) MIN={r['MIN']} — perfil de zona ===")
        print(f"  {'zona':<16}{'FGA':>5}{'FGM':>5}{'FG%':>7}{'eFG%':>7}")
        tfga = 0
        for z in ZONE_ORDER:
            v = zacc[pp].get(z)
            if v and v[0]:
                fga, fgm, tpm = v
                tfga += fga
                print(f"  {z:<16}{fga:>5}{fgm:>5}{100*fgm/fga:>7.1f}{100*(fgm+0.5*tpm)/fga:>7.1f}")
        print(f"  {'TOTAL FGA':<16}{tfga:>5}")

    print("=== SANITY: perfil de zona de Sarni y Weaver ===")
    profile("M. Sarni")
    profile("E. Weaver")

    # ===== GATE: golden test (vertical + lateralidad) antes de cualquier carta =====
    print()
    if not chart.golden_test() or not zones.lateral_golden_test():
        print("ABORTADO: golden test no pasa, no se generan cartas."); sys.exit(1)

    cdir = out / "charts" / "players"
    cdir.mkdir(parents=True, exist_ok=True)

    def make_chart(pp):
        r = tot[pp]
        n = sum(zacc[pp][z][0] for z in zacc[pp])
        chart.svg_chart(shots[pp], cdir / f"{slug(r['name'])}_{r['team']}.svg",
                        f"{r['name']} ({r['team']}) — {n} tiros, Clasificatorio")

    # sanity charts
    for nm in ("M. Sarni", "E. Weaver"):
        pp = next(p for p, r in tot.items() if r["name"] == nm)
        make_chart(pp)

    # ===== SCOUTING: top anotadores de cada rival de Urunday =====
    rivals = sorted({r["team"] for r in tot.values()} - {"UUN"})
    print("\n=== SCOUTING: cartas de top-anotadores por rival de Urunday ===")
    for tcode in rivals:
        scorers = sorted([r for r in tot.values() if r["team"] == tcode and float(r["MIN"]) >= MIN_POOL],
                         key=lambda r: -int(r["PTS"]))[:3]
        names = []
        for r in scorers:
            make_chart(r["personId"])
            names.append(f"{r['name']} ({int(r['PTS'])}p)")
        print(f"  {tcode}: " + ", ".join(names))

    print(f"\nZonas: {out / 'player_shotzones.csv'}  | cartas: {cdir}")


if __name__ == "__main__":
    main()
