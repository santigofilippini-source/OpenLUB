"""
11_shotzones — Análisis de tiro POR ZONA (sin render). Paso A de cartas de tiro.

Clasifica cada tiro de `tm.{1,2}.shot[]` en zonas con coords NORMALIZADAS de lado:
- Normalización de lado (analítica): el lado lejano se rota 180° para superponer todo en una
  media cancha (basket en x alto). Fold por x: si x<50 -> x'=100-x, y'=100-y.
  (Esto es SOLO normalización analítica; el flip de Y de render es del paso B, separado.)
- A metros: X_m = x*0.28 (cancha 28m), Y_m = y*0.15 (15m). Aro a 1.575m del fondo -> (26.425, 7.5).

Zonas: 2pt -> restringida (<=1.25m del aro) / pintura (llave 4.9x5.8m) / media.
       3pt -> esquina / ala / frente (por ángulo desde el aro).
FGA/FGM/3PM/FG%/eFG% por zona y por equipo, agregado sobre la fase (excluye exclusions.csv).

VALIDACIÓN: el eFG% reconstruido de las zonas == eFG% del boxscore (teams_totals.csv). Si no cuadra,
el shot[] está incompleto.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"

RX, RY = 26.425, 7.5          # aro en metros (fold a basket de x alto)
RESTRICTED = 1.25             # radio zona restringida (m)
KEY_BACK = 28 - 5.8           # X_m >= 22.2 dentro de la llave (5.8m de fondo)
KEY_HALFW = 2.45              # media anchura llave (4.9m)


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def zone(s):
    """Clasifica un tiro (dict con x,y,actionType) en su zona, con coords normalizadas de lado."""
    x, y = float(s["x"]), float(s["y"])
    if x < 50:                       # lado lejano -> rotar 180°
        x, y = 100 - x, 100 - y
    xm, ym = x * 0.28, y * 0.15
    dx, dy = RX - xm, ym - RY        # dx>0 = hacia mediocancha (frente al aro)
    d = math.hypot(xm - RX, ym - RY)
    if s["actionType"] == "3pt":
        ang = abs(math.degrees(math.atan2(dy, dx)))
        side = "izq" if dy < 0 else "der"
        if ang >= 68:
            return f"3 esquina {side}"
        if ang >= 23:
            return f"3 ala {side}"
        return "3 frente"
    # 2pt
    if d <= RESTRICTED:
        return "restringida"
    if xm >= KEY_BACK and abs(ym - RY) <= KEY_HALFW:
        return "pintura"
    return "media"


# orden de zonas para mostrar
ZONE_ORDER = ["restringida", "pintura", "media", "3 esquina izq", "3 ala izq",
              "3 frente", "3 ala der", "3 esquina der"]


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slug(phase)
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = [m for m in schedule[phase] if m not in load_exclusions()]

    # acc[(code, zone)] = [FGA, FGM, 3PM]
    acc = defaultdict(lambda: [0, 0, 0])
    name = {}
    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        for t in ("1", "2"):
            tm = d["tm"][t]
            code = tm["code"]
            name[code] = tm["name"]
            for s in tm.get("shot", []):
                z = zone(s)
                made = int(s.get("r", 0)) == 1
                three = s["actionType"] == "3pt"
                acc[(code, z)][0] += 1
                acc[(code, z)][1] += 1 if made else 0
                acc[(code, z)][2] += 1 if (made and three) else 0

    # salida CSV
    rows = []
    for (code, z), (fga, fgm, tpm) in acc.items():
        rows.append({"team": code, "zone": z, "FGA": fga, "FGM": fgm, "3PM": tpm,
                     "FGpct": round(100 * fgm / fga, 1) if fga else 0,
                     "eFG": round(100 * (fgm + 0.5 * tpm) / fga, 1) if fga else 0})
    rows.sort(key=lambda r: (r["team"], ZONE_ORDER.index(r["zone"]) if r["zone"] in ZONE_ORDER else 99))
    with (out / "shot_zones_by_team.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "zone", "FGA", "FGM", "3PM", "FGpct", "eFG"])
        w.writeheader()
        w.writerows(rows)

    # validación vs boxscore
    box = {r["code"]: r for r in csv.DictReader((out / "teams_totals.csv").open(encoding="utf-8"))}

    def team_efg_from_zones(code):
        fga = sum(v[0] for (c, z), v in acc.items() if c == code)
        fgm = sum(v[1] for (c, z), v in acc.items() if c == code)
        tpm = sum(v[2] for (c, z), v in acc.items() if c == code)
        return fga, fgm, tpm, (100 * (fgm + 0.5 * tpm) / fga if fga else 0)

    print("=== VALIDACIÓN eFG% reconstruido (zonas) vs boxscore ===")
    print(f"  {'equipo':<6}{'FGA z/box':>14}{'FGM z/box':>14}{'3PM z/box':>12}{'eFG z':>7}{'eFG box':>8}")
    okall = True
    for code in sorted(box):
        fga, fgm, tpm, efg = team_efg_from_zones(code)
        bfga, bfgm, btpm = int(box[code]["FGA"]), int(box[code]["FGM"]), int(box[code]["3PM"])
        befg = 100 * (bfgm + 0.5 * btpm) / bfga if bfga else 0
        ok = (fga, fgm, tpm) == (bfga, bfgm, btpm)
        okall = okall and ok
        flag = "" if ok else "  <-- NO CUADRA"
        print(f"  {code:<6}{fga:>6}/{bfga:<7}{fgm:>6}/{bfgm:<7}{tpm:>5}/{btpm:<6}{efg:>7.1f}{befg:>8.1f}{flag}")
    print(f"\n  => {'TODOS CUADRAN' if okall else 'HAY DESAJUSTES'}")

    def show(code):
        print(f"\n=== {name.get(code, code)} ({code}) — desglose por zona ===")
        print(f"  {'zona':<16}{'FGA':>5}{'FGM':>5}{'FG%':>7}{'eFG%':>7}")
        for z in ZONE_ORDER:
            v = acc.get((code, z))
            if v and v[0]:
                fga, fgm, tpm = v
                print(f"  {z:<16}{fga:>5}{fgm:>5}{100*fgm/fga:>7.1f}{100*(fgm+0.5*tpm)/fga:>7.1f}")

    show("UUN")
    show("CAP")
    print(f"\nSalida: {out / 'shot_zones_by_team.csv'}")


if __name__ == "__main__":
    main()
