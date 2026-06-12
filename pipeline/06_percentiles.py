"""
06_percentiles — Percentiles vs liga (SOLO Clasificatorio), por personId.

Pool: jugadores con MINUTOS TOTALES >= MIN_POOL (NO el GP>=50% del leaderboard; un umbral
por minutos incluye a los de alto rendimiento por minuto con muestra suficiente).

Métricas percentiladas (0-100), sin on-court (eso espera al tracking de stints):
  Eficiencia / tasas:  TS%, eFG%, FTr (FTA/FGA), AST/TO
  Contables en per-36: PTS, REB, OREB, DREB, AST, STL, BLK, TOV
OJO dirección: en TOV per-36, percentil ALTO = MÁS pérdidas (no es "mejor"). El resto, alto = mejor.

Entrada: data/agg/{slug}/players_totals.csv (totales por personId, del paso 03).
Salida:  data/agg/{slug}/players_percentiles.csv
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
MIN_POOL = 200.0


def slug(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def f(v):
    return float(v or 0)


def metrics(r: dict) -> dict:
    """Calcula las métricas crudas de un jugador a partir de sus totales."""
    pts, fga, fta = f(r["PTS"]), f(r["FGA"]), f(r["FTA"])
    fgm, tpm = f(r["FGM"]), f(r["3PM"])
    ast, tov, mn = f(r["AST"]), f(r["TOV"]), f(r["MIN"])
    p36 = (lambda x: round(x / mn * 36, 2)) if mn else (lambda x: 0.0)
    return {
        "TS%": round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + fta) else 0.0,
        "eFG%": round((fgm + 0.5 * tpm) / fga * 100, 1) if fga else 0.0,
        "FTr": round(fta / fga * 100, 1) if fga else 0.0,
        "AST/TO": round(ast / tov, 2) if tov else round(ast, 2),
        "PTS36": p36(pts), "REB36": p36(f(r["REB"])),
        "OREB36": p36(f(r["OREB"])), "DREB36": p36(f(r["DREB"])),
        "AST36": p36(ast), "STL36": p36(f(r["STL"])),
        "BLK36": p36(f(r["BLK"])), "TOV36": p36(tov),
    }


METRIC_COLS = ["TS%", "eFG%", "FTr", "AST/TO", "PTS36", "REB36",
               "OREB36", "DREB36", "AST36", "STL36", "BLK36", "TOV36"]


def pctl(value, arr):
    """Percentil-de-score (mean rank): % del pool con valor < x, más medio empate."""
    n = len(arr)
    below = sum(1 for v in arr if v < value)
    equal = sum(1 for v in arr if v == value)
    return round(100 * (below + 0.5 * equal) / n, 1)


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slug(phase)
    rows = list(csv.DictReader((out / "players_totals.csv").open(encoding="utf-8")))

    pool = [r for r in rows if f(r["MIN"]) >= MIN_POOL]
    vals = {r["personId"]: metrics(r) for r in rows}        # métricas de TODOS (para referencia)
    arrs = {m: [vals[r["personId"]][m] for r in pool] for m in METRIC_COLS}  # solo pool

    # escribir percentiles del pool
    cols = ["personId", "name", "team", "pos", "MIN", "GP"]
    for m in METRIC_COLS:
        cols += [m, m + "_pct"]
    out_rows = []
    for r in pool:
        v = vals[r["personId"]]
        row = {"personId": r["personId"], "name": r["name"], "team": r["team"],
               "pos": r["pos"], "MIN": r["MIN"], "GP": r["GP"]}
        for m in METRIC_COLS:
            row[m] = v[m]
            row[m + "_pct"] = pctl(v[m], arrs[m])
        out_rows.append(row)
    with (out / "players_percentiles.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(out_rows, key=lambda x: -x["PTS36_pct"]))

    print(f"Pool (MIN>={MIN_POOL:.0f}): {len(pool)} de {len(rows)} jugadores")

    def show(name, ref=False):
        r = next((x for x in rows if x["name"] == name), None)
        if not r:
            print(f"  {name}: no encontrado"); return
        v = vals[r["personId"]]
        tag = "  (FUERA del pool, percentil de referencia)" if ref else ""
        print(f"\n{name} [{r['team']} {r['pos']}] MIN={r['MIN']} GP={r['GP']}{tag}")
        for m in METRIC_COLS:
            print(f"   {m:<7} {v[m]:>6}  pct {pctl(v[m], arrs[m]):>5}")

    print("\n=== SANITY CHECK ===")
    show("M. Sarni")
    show("E. Weaver")
    show("A. Gilder Jr.", ref=f(next(x for x in rows if x['name']=='A. Gilder Jr.')['MIN']) < MIN_POOL)
    print(f"\nSalida: {out / 'players_percentiles.csv'}")


if __name__ == "__main__":
    main()
