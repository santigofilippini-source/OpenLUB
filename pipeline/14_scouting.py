"""
14_scouting — Dossier de scouting por equipo (1 .md por rival). Plantilla validada con Peñarol.

Para cada equipo: (a) perfil de zona ATAQUE y DEFENSA (vol% + eFG vs liga); (b) generadores
(PTS x USG% x AST% del paso 08, separando quién ARMA de quién solo anota); (c) referencia a las
cartas de los top-anotadores (paso 13). Fuente: Clasificatorio (no cubre playoffs ni imports tardíos).

Genera data/agg/{slug}/scouting/{TEAM}.md para los rivales de Urunday (todos menos UUN).
"""
import csv
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

z = importlib.import_module("11_shotzones")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"
ZO = z.ZONE_ORDER
HOME = "UUN"


def slugp(p):
    import re
    return re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")


def efg(v):
    return 100 * (v[1] + 0.5 * v[2]) / v[0] if v[0] else 0


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    out = ROOT / "data" / "agg" / slugp(phase)
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    ids = [m for m in schedule[phase] if m not in z.load_exclusions()]

    teams = set()
    name = {}
    league = defaultdict(lambda: [0, 0, 0])
    off = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    deff = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for mid in ids:
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        code = {t: d["tm"][t]["code"] for t in ("1", "2")}
        for t in ("1", "2"):
            teams.add(code[t]); name[code[t]] = d["tm"][t]["name"]
            other = "2" if t == "1" else "1"
            for s in d["tm"][t].get("shot", []):
                zn = z.zone(s); made = int(s.get("r", 0)) == 1; three = s["actionType"] == "3pt"
                league[zn][0] += 1; league[zn][1] += made; league[zn][2] += (made and three)
                o = off[code[t]][zn]; o[0] += 1; o[1] += made; o[2] += (made and three)
                e = deff[code[other]][zn]; e[0] += 1; e[1] += made; e[2] += (made and three)

    pct = {r["personId"]: r for r in csv.DictReader((out / "players_percentiles.csv").open(encoding="utf-8"))}
    tot = {r["personId"]: r for r in csv.DictReader((out / "players_totals.csv").open(encoding="utf-8"))}

    sdir = out / "scouting"
    sdir.mkdir(parents=True, exist_ok=True)
    rivals = sorted(teams - {HOME})
    for tc in rivals:
        write_dossier(sdir, tc, name, off[tc], deff[tc], league, pct, tot)
    print(f"Dossiers ({len(rivals)} rivales) en {sdir}")
    for tc in rivals:
        print(f"  {tc}.md  ({name[tc]})")


def ztable(acc, league, total_label):
    tot = sum(acc[zz][0] for zz in acc) or 1
    lines = [f"| Zona | Vol% | eFG | Liga | |", "|---|--:|--:|--:|--|"]
    for zz in ZO:
        v = acc.get(zz)
        if not v or not v[0]:
            continue
        e, le = efg(v), efg(league[zz])
        flag = "🔴" if e - le >= 6 else ("🔵" if le - e >= 6 else "")
        lines.append(f"| {zz} | {100*v[0]/tot:.1f} | {e:.1f} | {le:.1f} | {flag} |")
    return "\n".join(lines), tot


def role(p, pts_rank):
    """Clasifica rol del jugador segun USG%/AST% percentiles."""
    try:
        ap = float(p.get("AST%_pct", 0) or 0)
        up = float(p.get("USG%_pct", 0) or 0)
    except ValueError:
        return ""
    if ap >= 75 and up >= 60:
        return "🎯 anota Y arma"
    if ap >= 70:
        return "🅰️ armador"
    if ap < 20:
        return "finalizador puro"
    if up >= 70:
        return "anotador de volumen"
    return "anotador"


def write_dossier(sdir, tc, name, off, deff, league, pct, tot):
    players = sorted([r for r in tot.values() if r["team"] == tc and float(r["MIN"]) >= 200],
                     key=lambda r: -int(r["PTS"]))
    otab, ovol = ztable(off, league, "atk")
    dtab, dvol = ztable(deff, league, "def")

    # lecturas automáticas
    o_strength = max((zz for zz in ZO if off.get(zz, [0])[0]),
                     key=lambda zz: efg(off[zz]) - efg(league[zz]), default=None)
    d_strength = min((zz for zz in ZO if deff.get(zz, [0])[0] and deff[zz][0] >= 20),
                     key=lambda zz: efg(deff[zz]) - efg(league[zz]), default=None)
    d_weak = max((zz for zz in ZO if deff.get(zz, [0])[0] and deff[zz][0] >= 20),
                 key=lambda zz: efg(deff[zz]) - efg(league[zz]), default=None)

    md = []
    md.append(f"# 📋 Dossier de scouting — {name[tc]} ({tc})")
    md.append(f"\n**Fuente:** LUB 25/26 · fase **Clasificatorio** · ⚠️ *no cubre Playoffs ni imports de "
              f"llegada tardía (muestra regular-season; un refuerzo posterior no está o tiene muestra chica).*\n")

    # ===== RECUADRO: 3 bullets para el que dirige (lee en 30s) =====
    if d_weak and efg(deff[d_weak]) - efg(league[d_weak]) >= 3:
        explotar = f"**{d_weak}** — le anotan {efg(deff[d_weak]):.0f} eFG ahí (liga {efg(league[d_weak]):.0f}), sobre la media."
    else:
        explotar = "No tienen agujero defensivo claro (defienden todo ≤ media): buscar volumen de aro y **segundas oportunidades**."
    quitar = f"**{o_strength}** — es su tiro más eficiente ({efg(off[o_strength]):.0f} eFG vs liga {efg(league[o_strength]):.0f}). Cerrar ese sector."
    creators = [r["name"] for r in players[:8]
                if float(pct.get(r["personId"], {}).get("AST%_pct", 0) or 0) >= 70]
    if creators:
        presionar = f"**{', '.join(creators)}** — generan el juego (AST% top liga). Presionar la FUENTE, no al finalizador."
    elif players:
        presionar = f"**{players[0]['name']}** — su principal volumen ofensivo."
    else:
        presionar = "—"
    md.append("> ### 🎯 Plan en 30 segundos")
    md.append(f">\n> - **QUÉ EXPLOTARLES:** {explotar}")
    md.append(f"> - **QUÉ QUITARLES:** {quitar}")
    md.append(f"> - **A QUIÉN PRESIONAR:** {presionar}\n")

    md.append("## (a) Perfil de zona\n")
    md.append("**ATAQUE** (vol% del total de tiros; eFG vs promedio de liga; 🔴 mete por encima de la media):\n")
    md.append(otab)
    if o_strength:
        md.append(f"\n→ Mayor ventaja ofensiva: **{o_strength}** (eFG {efg(off[o_strength]):.1f} vs liga {efg(league[o_strength]):.1f}).\n")
    md.append("\n**DEFENSA** (lo que le tiran los rivales; 🔵 lo defiende por debajo de la media):\n")
    md.append(dtab)
    if d_strength:
        md.append(f"\n→ Fortaleza defensiva: **{d_strength}** ({efg(deff[d_strength]):.1f} vs liga {efg(league[d_strength]):.1f}).")
        if d_weak and efg(deff[d_weak]) - efg(league[d_weak]) >= 3:
            md.append(f" A explotar: **{d_weak}** ({efg(deff[d_weak]):.1f} vs {efg(league[d_weak]):.1f}, sobre la media).\n")
        else:
            md.append(" Sin zona defensiva débil clara: defienden todo a la media o por debajo.\n")

    md.append("\n## (b) Generadores (PTS × USG% × AST%)\n")
    md.append("| Jugador | Pos | PTS | MIN | USG% (pct) | AST% (pct) | Rol |")
    md.append("|---|--|--:|--:|--:|--:|--|")
    for i, r in enumerate(players[:8]):
        p = pct.get(r["personId"], {})
        u = f"{p.get('USG%','-')} ({p.get('USG%_pct','-')})"
        a = f"{p.get('AST%','-')} ({p.get('AST%_pct','-')})"
        md.append(f"| {r['name']} | {r['pos']} | {r['PTS']} | {r['MIN']} | {u} | {a} | {role(p, i)} |")
    creators = [r["name"] for r in players[:8] if float(pct.get(r["personId"], {}).get("AST%_pct", 0) or 0) >= 70]
    if creators:
        md.append(f"\n→ Arman, no solo anotan: **{', '.join(creators)}**. Presionar la FUENTE de juego, "
                  f"no solo a los finalizadores.\n")

    md.append("\n## (c) Cartas de tiro (top-3 anotadores, ya generadas)\n")
    for r in players[:3]:
        f = f"{slugp(r['name'])}_{tc}.svg"
        md.append(f"- [{r['name']}](../charts/players/{f}) — {r['PTS']}p")
    md.append("\nDetalle por jugador y zona: `player_shotzones.csv` (filtrar por personId).")

    (sdir / f"{tc}.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
