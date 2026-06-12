"""
19_similarity — Jugadores MÁS PARECIDOS por distancia en el espacio de PERCENTILES (Clasificatorio).

Para cada jugador del pool de percentiles (>=200 min, los 111 de players_percentiles.csv) calcula los
N más parecidos midiendo distancia sobre los 19 PERCENTILES (columnas *_pct), no sobre stats crudas:
así todas las escalas son comparables (cada eje 0-100) y ninguna métrica domina por su magnitud.

Distancia = brecha RMS de percentil: dist = sqrt(media de (p_a - p_b)^2 sobre las 19 métricas).
Es interpretable: "en promedio difieren ~dist puntos de percentil por métrica". MÁS BAJO = más
parecido. SIEMPRE se reporta la distancia de cada match: en una liga chica el "más parecido" puede
estar lejos (= el menos distinto, no un gemelo). El contexto (mediana del 1er vecino, etc.) viaja en
el JSON para que la vista marque si el match es bueno o flojo.

Dos modos: GLOBAL (toda la liga) y por POSICIÓN (mismo grupo posicional). Como el feed etiqueta las
posiciones de forma inconsistente (G/PG/SG y F/PF/C), se agrupan en 3 familias (ver BUCKET) y se
expone la familia usada — transparente, no inventa una taxonomía fina que el dato no soporta.

LIMITACIÓN (honesta, va en el disclaimer de la vista): es similitud ESTADÍSTICA (perfil de
producción), NO estilo de juego. Además las 19 métricas incluyen versiones por-36 y por-% del mismo
fundamento (reb, ast…) que correlacionan: el peso igual cuenta doble esos ejes. Punto de partida para
scouting, no conclusión. Pool: solo Clasificatorio. NO toca ningún paso existente.
"""
import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGG = ROOT / "data" / "agg" / "clasificatorio_lub_25_26"
WEB_DATA = ROOT / "web" / "public" / "data"
PHASE = "Clasificatorio LUB 25/26"
TOPN = 12   # cuántos vecinos guardar por modo (la vista decide cuántos mostrar)

# Agrupación posicional en 3 familias (las labels del feed son inconsistentes).
BUCKET = {"PG": "perimetro", "SG": "perimetro", "G": "perimetro",
          "F": "ala", "PF": "ala", "C": "interior"}
BUCKET_LABEL = {"perimetro": "Perímetro (bases/escoltas)",
                "ala": "Alas (aleros/ala-pivots)", "interior": "Interiores (pivots)"}


def main():
    rows = list(csv.DictReader((AGG / "players_percentiles.csv").open(encoding="utf-8")))
    pct = [c for c in rows[0] if c.endswith("_pct")]
    nd = len(pct)

    vec, meta = {}, {}
    for r in rows:
        pid = r["personId"]
        vec[pid] = [float(r[c]) for c in pct]
        meta[pid] = {"personId": pid, "name": r["name"], "team": r["team"], "pos": r["pos"],
                     "bucket": BUCKET.get(r["pos"], "ala")}

    def dist(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(vec[a], vec[b])) / nd)

    def neighbors(pid, pool):
        ds = sorted(((round(dist(pid, o), 1), o) for o in pool if o != pid))
        return [{**{k: meta[o][k] for k in ("personId", "name", "team", "pos")}, "dist": d}
                for d, o in ds[:TOPN]]

    ids = list(vec)
    players = {}
    for pid in ids:
        bucket = meta[pid]["bucket"]
        same = [o for o in ids if meta[o]["bucket"] == bucket]
        players[pid] = {**meta[pid], "bucketLabel": BUCKET_LABEL[meta[pid]["bucket"]],
                        "bucketN": len(same),
                        "global": neighbors(pid, ids), "byPos": neighbors(pid, same)}

    # --- contexto de distancias (para bandas "bueno/moderado/flojo" y disclaimer) ---
    nn = [players[pid]["global"][0]["dist"] for pid in ids]   # distancia al 1er vecino global
    allp = [round(dist(ids[i], ids[j]), 1) for i in range(len(ids)) for j in range(i + 1, len(ids))]
    ctx = {
        "metrics": [c[:-4] for c in pct], "nMetrics": nd, "poolSize": len(ids),
        "nnMin": min(nn), "nnMedian": round(statistics.median(nn), 1), "nnMax": max(nn),
        "pairMedian": round(statistics.median(allp), 1), "pairMax": max(allp),
    }

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "similarity.json").write_text(json.dumps(
        {"phase": PHASE, "ctx": ctx, "buckets": BUCKET_LABEL, "players": players},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- CSV (ground truth, top-N global por jugador) ---
    with (AGG / "similarity_global.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["personId", "name", "rank", "match_personId", "match_name", "match_team",
                    "match_pos", "dist"])
        for pid in ids:
            for k, nb in enumerate(players[pid]["global"], 1):
                w.writerow([pid, meta[pid]["name"], k, nb["personId"], nb["name"], nb["team"],
                            nb["pos"], nb["dist"]])

    # ===================== GROUND TRUTH =====================
    print("=" * 70)
    print(f"SIMILITUD — espacio de {nd} percentiles · pool {len(ids)} jugadores (Clasificatorio)")
    print("Distancia = brecha RMS de percentil por métrica (más bajo = más parecido)")
    print("=" * 70)
    print(f"\nContexto de distancias:")
    print(f"  Distancia al MÁS parecido (1er vecino), todos: min={ctx['nnMin']} "
          f"mediana={ctx['nnMedian']} max={ctx['nnMax']}")
    print(f"  Todas las parejas: mediana={ctx['pairMedian']} max={ctx['pairMax']}")
    print(f"  -> Lectura: un match por DEBAJO de ~{ctx['nnMedian']} es bueno; cerca del max ({ctx['nnMax']})")
    print(f"     es 'el menos distinto', no un gemelo.")

    dem = next(pid for pid in ids if "Demers" in meta[pid]["name"])
    print(f"\n5 más parecidos a {meta[dem]['name']} ({meta[dem]['team']}, {meta[dem]['pos']}) — GLOBAL:")
    for nb in players[dem]["global"][:5]:
        print(f"  {nb['name'][:22]:<22} {nb['team']:<5} {nb['pos']:<3} dist={nb['dist']}")
    print(f"  (su match más cercano está a {players[dem]['global'][0]['dist']} vs mediana liga "
          f"{ctx['nnMedian']} -> Demers es relativamente único, sin comp fuerte)")
    print(f"\n5 más parecidos a {meta[dem]['name']} — por POSICIÓN ({players[dem]['bucketLabel']}, "
          f"{players[dem]['bucketN']} jugadores):")
    for nb in players[dem]["byPos"][:5]:
        print(f"  {nb['name'][:22]:<22} {nb['team']:<5} {nb['pos']:<3} dist={nb['dist']}")

    print(f"\nJSON web: {WEB_DATA / 'similarity.json'}")
    print(f"CSV ground truth: {AGG / 'similarity_global.csv'}")


if __name__ == "__main__":
    main()
