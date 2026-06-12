"""
16_gameflow — Reconstruye el FLUJO DE PARTIDO (evolución de la diferencia de puntos) desde el
`leaddata` del data.json y lo exporta a JSON estático para la web (`web/public/data/gameflow.json`).

`leaddata` es una lista de 2 filas:
  fila 0 = etiquetas: marca dónde ARRANCA cada período ('P1','P2','P3','P4','OT1'...), resto ''.
  fila 1 = la diferencia de puntos muestreada (tm1 − tm2) a lo largo del partido.
Muestreo ~cada 10s: 62 muestras por período regular (10 min), ~32 por prórroga (5 min).

VALIDACIÓN DURA (regla de oro del proyecto): la ÚLTIMA muestra de la curva == diferencia del
boxscore (tm1.score − tm2.score) en TODOS los partidos. Si alguno no cierra, se ABORTA el export.

Base = Clasificatorio (temporada regular), COMPLETE menos exclusiones — igual pool que results.json.
Se exporta la liga completa (cualquier partido tiene flujo); la web arranca por los de Urunday.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
WEB_DATA = ROOT / "web" / "public" / "data"
PHASE = "Clasificatorio LUB 25/26"


def load_exclusions():
    """matchId excluidos del pool de agregados (incompletos genuinos)."""
    p = SCH_DIR / "exclusions.csv"
    if not p.exists():
        return set()
    return {r["matchId"] for r in csv.DictReader(p.open(encoding="utf-8"))}


def period_len(label, d):
    """Largo en minutos del período según su etiqueta (regular vs prórroga)."""
    if label.startswith("OT"):
        return int(d.get("periodLengthOVERTIME", 5))
    return int(d.get("periodLengthREGULAR", 10))


def build_match(mid):
    """Devuelve el dict de gameflow de un partido, o lanza si la curva no cierra contra el boxscore."""
    d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
    labels, lead = d["leaddata"][0], d["leaddata"][1]
    lead = [int(v) for v in lead]

    # bounds = índice de muestra donde arranca cada período. La 1ª muestra real (idx 0, 0-0) se
    # pliega dentro de P1, así la curva arranca en 0 al minuto 0.
    marks = [(i, lab) for i, lab in enumerate(labels) if lab]
    bounds = [0] + [i for i, _ in marks[1:]]          # P1 forzado a 0
    periods = [[lab, period_len(lab, d)] for _, lab in marks]

    t1, t2 = d["tm"]["1"], d["tm"]["2"]
    s1, s2 = int(t1["score"]), int(t2["score"])

    # VALIDACIÓN DURA: cierre de la curva == diferencia del boxscore.
    if lead[-1] != s1 - s2:
        raise ValueError(f"{mid}: cierre de leaddata {lead[-1]} != boxscore {s1 - s2} "
                         f"({t1['code']} {s1}-{s2} {t2['code']})")

    return {
        "matchId": str(mid),
        "t1": t1["code"], "t2": t2["code"],
        "n1": t1["name"], "n2": t2["name"],
        "s1": s1, "s2": s2,
        "periods": periods,   # [[label, minutos], ...]
        "bounds": bounds,     # idx de muestra de inicio de cada período (alineado con periods)
        "lead": lead,         # diferencia tm1 − tm2 por muestra
    }


def main():
    excl = load_exclusions()
    index = SCH_DIR / "clasificatorio_lub_25_26_index.csv"
    ids = [r["matchId"] for r in csv.DictReader(index.open(encoding="utf-8"))
           if r["status"] == "COMPLETE" and r["matchId"] not in excl]

    out, bad = [], []
    for mid in ids:
        try:
            out.append(build_match(mid))
        except ValueError as e:
            bad.append(str(e))

    if bad:
        print("ABORTADO: hay partidos cuya curva NO cierra contra el boxscore:")
        for b in bad:
            print("  -", b)
        raise SystemExit(1)

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "gameflow.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    uru = sum(1 for m in out if "UUN" in (m["t1"], m["t2"]))
    print(f"gameflow.json: {len(out)} partidos (cierre validado vs boxscore), {uru} de Urunday")
    print(f"Salida en {WEB_DATA / 'gameflow.json'}")


if __name__ == "__main__":
    main()
