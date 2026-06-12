"""
17_quarter_splits — Rendimiento DESGLOSADO POR CUARTO (Q1–Q4 + prórrogas), por equipo.

Reconstruye desde el `pbp` del data.json, por partido y por equipo:
  - puntos A FAVOR y EN CONTRA por cuarto (sumando tiros encestados del play-by-play),
  - tiros por cuarto (FGA/FGM/3PM) y eFG% por cuarto (ofensivo y defensivo = el del rival).
Luego agrega a NIVEL LIGA: para cada equipo del Clasificatorio, su PROMEDIO por cuarto
(puntos favor, contra, diferencial) y eFG% pooled, sobre TODOS sus partidos. La muestra
(partidos detrás de cada promedio) viaja en el JSON para que la web la muestre.

Por qué desde el pbp y no de `p{n}_score`: el boxscore solo trae Q1–Q4 (no las prórrogas) y no
trae tiros por cuarto. El pbp da todo y además permite la doble validación de abajo.

VALIDACIÓN DURA (regla de oro del proyecto, igual que gameflow):
  1. suma de los cuartos (incl. OT) de cada equipo == su total del boxscore (tm.score), y
  2. los Q1–Q4 reconstruidos == p{n}_score del boxscore.
Si ALGÚN partido no cierra, se ABORTA el export (no se publica nada).

Base = Clasificatorio (temporada regular), COMPLETE menos exclusiones — igual pool que el resto.
NO toca ningún paso existente. Salida: data/agg/<fase>/quarter_splits_by_{match,team}.csv y
web/public/data/quarter_splits.json (liga completa; la web arranca por Urunday).
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
WEB_DATA = ROOT / "web" / "public" / "data"
PHASE = "Clasificatorio LUB 25/26"
INDEX = "clasificatorio_lub_25_26_index.csv"

# valor en puntos de cada tipo de tiro encestado
PTS = {"2pt": 2, "3pt": 3, "freethrow": 1}


def slug(p):
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def i(v):
    return int(v or 0)


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def qlabel(period_type, period):
    """Etiqueta de cuarto: REGULAR 1..4 -> Q1..Q4 ; OVERTIME n -> OT{n} (period reinicia en OT)."""
    if period_type == "OVERTIME":
        return f"OT{period}"
    return f"Q{period}"


def build_match(mid):
    """Desglose por cuarto de un partido, validado contra el boxscore. Devuelve:
       {q: {tno: [pts, fga, fgm, tpm]}}, más los codes/score del boxscore.
    Lanza ValueError si la curva de cuartos no cierra (suma != total, o Q!= p{n}_score)."""
    d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))

    # acc[q][tno] = [pts, fga, fgm, tpm]  (tno: 1 = tm.1, 2 = tm.2)
    acc = defaultdict(lambda: {1: [0, 0, 0, 0], 2: [0, 0, 0, 0]})
    for e in d["pbp"]:
        tno = e.get("tno")
        if tno not in (1, 2):
            continue
        at = e.get("actionType")
        if at not in PTS:
            continue
        q = qlabel(e.get("periodType"), e["period"])
        cell = acc[q][tno]
        if at in ("2pt", "3pt"):
            cell[1] += 1                       # FGA
            if e.get("success") == 1:
                cell[0] += PTS[at]             # pts
                cell[2] += 1                   # FGM
                if at == "3pt":
                    cell[3] += 1               # 3PM
        elif e.get("success") == 1:            # freethrow encestado
            cell[0] += 1

    t1, t2 = d["tm"]["1"], d["tm"]["2"]
    for tno, tm in ((1, t1), (2, t2)):
        # (1) suma de todos los cuartos == total del boxscore
        tot = sum(acc[q][tno][0] for q in acc)
        if tot != i(tm["score"]):
            raise ValueError(f"{mid} {tm['code']}: suma de cuartos {tot} != total boxscore "
                             f"{i(tm['score'])}")
        # (2) cada Q1..Q4 reconstruido == p{n}_score del boxscore
        for n in range(1, 5):
            got = acc[f"Q{n}"][tno][0] if f"Q{n}" in acc else 0
            want = i(tm.get(f"p{n}_score"))
            if got != want:
                raise ValueError(f"{mid} {tm['code']}: Q{n} reconstruido {got} != p{n}_score {want}")

    return acc, t1["code"], t2["code"], t1["name"], t2["name"]


# orden de cuartos para mostrar (OT colapsa en un único balde "OT", muestra chica)
QORDER = ["Q1", "Q2", "Q3", "Q4", "OT"]


def main():
    excl = load_exclusions()
    ids = [r["matchId"] for r in csv.DictReader((SCH_DIR / INDEX).open(encoding="utf-8"))
           if r["status"] == "COMPLETE" and r["matchId"] not in excl]

    # Por equipo y cuarto: acumular [pf, pa, fga_of, fgm_of, tpm_of, fga_df, fgm_df, tpm_df, games].
    # Los OT (OT1, OT2…) se colapsan en un único balde "OT".
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0, 0]))
    name = {}
    by_match_rows = []   # ground truth partido a partido
    bad = []

    for mid in ids:
        try:
            acc, c1, c2, n1, n2 = build_match(mid)
        except ValueError as e:
            bad.append(str(e))
            continue
        name[c1], name[c2] = n1, n2
        # ¿qué cuartos (incl. OTs) hubo en este partido?
        present = sorted(acc.keys(), key=lambda q: (q.startswith("OT"), q))
        for tno, code, opp in ((1, c1, c2), (2, c2, c1)):
            otd = present and any(q.startswith("OT") for q in present)
            seen_ot = False
            for q in present:
                of = acc[q][tno]       # [pts, fga, fgm, tpm]  propio
                df = acc[q][3 - tno]   # del rival = puntos/tiros EN CONTRA
                bucket = "OT" if q.startswith("OT") else q
                a = agg[code][bucket]
                a[0] += of[0]; a[1] += df[0]
                a[2] += of[1]; a[3] += of[2]; a[4] += of[3]
                a[5] += df[1]; a[6] += df[2]; a[7] += df[3]
                # games del balde: Q1-Q4 += 1 por partido; OT += 1 sola vez aunque haya OT1+OT2
                if bucket != "OT":
                    a[8] += 1
                elif not seen_ot:
                    a[8] += 1; seen_ot = True
                by_match_rows.append({
                    "matchId": mid, "team": code, "opp": opp, "quarter": q,
                    "pf": of[0], "pa": df[0], "FGA": of[1], "FGM": of[2], "3PM": of[3],
                    "eFG": round(100 * (of[2] + 0.5 * of[3]) / of[1], 1) if of[1] else 0,
                })

    if bad:
        print("ABORTADO: hay partidos cuyo desglose por cuarto NO cierra contra el boxscore:")
        for b in bad:
            print("  -", b)
        raise SystemExit(1)

    # --- salida CSV (ground truth) ---
    out = ROOT / "data" / "agg" / slug(PHASE)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "quarter_splits_by_match.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["matchId", "team", "opp", "quarter",
                                          "pf", "pa", "FGA", "FGM", "3PM", "eFG"])
        w.writeheader()
        w.writerows(by_match_rows)

    def efg(fgm, tpm, fga):
        return round(100 * (fgm + 0.5 * tpm) / fga, 1) if fga else 0

    team_rows = []
    teams_json = {}
    for code in sorted(agg):
        gp = agg[code]["Q1"][8]   # partidos del equipo (todos tienen Q1)
        quarters = []
        for q in QORDER:
            a = agg[code].get(q)
            if not a or a[8] == 0:
                continue
            g = a[8]
            quarters.append({
                "q": q, "gp": g,
                "pf": round(a[0] / g, 1), "pa": round(a[1] / g, 1),
                "diff": round((a[0] - a[1]) / g, 1),
                "fga": round(a[2] / g, 1), "efg": efg(a[3], a[4], a[2]),
                "d_fga": round(a[5] / g, 1), "d_efg": efg(a[6], a[7], a[5]),
            })
            team_rows.append({
                "team": code, "quarter": q, "GP": g,
                "PF": round(a[0] / g, 1), "PA": round(a[1] / g, 1),
                "Dif": round((a[0] - a[1]) / g, 1),
                "FGA": round(a[2] / g, 1), "eFG": efg(a[3], a[4], a[2]),
                "D_FGA": round(a[5] / g, 1), "D_eFG": efg(a[6], a[7], a[5]),
            })
        teams_json[code] = {"code": code, "name": name[code], "GP": gp, "quarters": quarters}

    with (out / "quarter_splits_by_team.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "quarter", "GP", "PF", "PA", "Dif",
                                          "FGA", "eFG", "D_FGA", "D_eFG"])
        w.writeheader()
        w.writerows(team_rows)

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "quarter_splits.json").write_text(
        json.dumps({"phase": PHASE, "teams": teams_json}, ensure_ascii=False,
                   separators=(",", ":")), encoding="utf-8")

    n_ot = sum(1 for c in agg if "OT" in agg[c])
    print(f"OK: {len(ids)} partidos, desglose por cuarto validado vs boxscore (suma==total Y "
          f"Q1-Q4==p_score) en TODOS.")
    print(f"quarter_splits.json: {len(teams_json)} equipos ({n_ot} con prórrogas en su historial)")
    print(f"CSV ground truth: {out / 'quarter_splits_by_match.csv'} (partido a partido) y "
          f"quarter_splits_by_team.csv")


if __name__ == "__main__":
    main()
