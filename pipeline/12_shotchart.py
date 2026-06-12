"""
12_shotchart — Carta de tiro VISUAL (con render). Paso B.

DOS transformaciones SEPARADAS (CLAUDE.md), nunca acumular a ciegas:
1) Normalización de lado (analítica): fold del lado lejano, x'=100-x, y'=100-y (solo para agregados).
2) Convención de RENDER (dibujo): cx = x  ;  cy = 100 - y   (X directo, Y invertido).
   Esto reproduce el render oficial de FIBA LiveStats `sc.html` (ajload_2.js: `bottom:y%; left:x%`).
   OJO: el OTRO render oficial (embednf shotchart, hosted.dcd) usa `top:y%` -> está ESPEJADO en Y.
   NO anclar contra el embednf shotchart: reintroduce el bug de Y. Anclar SIEMPRE contra sc.html.

GOLDEN TEST (Moller #20, 2845330, P1) — debe pasar antes de aceptar cualquier carta:
  2pt pull-up ENCESTADO  x~7,  y~24 -> ABAJO-izquierda (cx<50, cy>50), pegado al aro.
  3pt jumpshot FALLADO   x~23, y~90 -> ARRIBA-izquierda (cx<50, cy<50), sobre el arco.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"


def render(x, y):
    """Coords de dibujo 0-100: X directo, Y invertido (convención FIBA LiveStats sc.html)."""
    return x, 100 - y


def normalize_side(x, y):
    """Fold del lado lejano a una media cancha (basket de x alto). Solo para agregados."""
    if x < 50:
        return 100 - x, 100 - y
    return x, y


def golden_test():
    d = json.loads((ROOT / "data" / "raw" / "2845330.json").read_text(encoding="utf-8"))
    shots = [s for s in d["tm"]["2"]["shot"] if int(s.get("pno")) == 7 and int(s.get("per")) == 1]
    made = next(s for s in shots if s["actionType"] == "2pt" and int(s["r"]) == 1)
    miss = next(s for s in shots if s["actionType"] == "3pt" and int(s["r"]) == 0)

    print("=== GOLDEN TEST — Moller (#20, 2845330, P1), convención sc.html (cx=x, cy=100-y) ===")
    ok = True
    for label, s, want in [("2pt pull-up ENCESTADO", made, "ABAJO-izq"),
                           ("3pt jumpshot FALLADO", miss, "ARRIBA-izq")]:
        cx, cy = render(float(s["x"]), float(s["y"]))
        horiz = "izq" if cx < 50 else "der"
        vert = "ABAJO" if cy > 50 else "ARRIBA"
        got = f"{vert}-{horiz}"
        passed = got == want
        ok = ok and passed
        # comparación con el marcador oficial sc.html: bottom = y%  => cy(desde arriba)=100-y
        off_bottom = float(s["y"])  # sc.html: bottom:y%
        print(f"  {label:<24} feed x={float(s['x']):.1f} y={float(s['y']):.1f} -> cx={cx:.1f} cy={cy:.1f} "
              f"=> {got}  (esperado {want})  {'PASA' if passed else 'FALLA'}")
        print(f"      sc.html oficial: bottom:{off_bottom:.0f}% left:{float(s['x']):.0f}%  "
              f"(cy desde arriba = 100-bottom = {100-off_bottom:.0f} == {cy:.0f} {'OK' if abs(100-off_bottom-cy)<0.5 else 'MISMATCH'})")
    print(f"\n  => GOLDEN TEST {'PASA' if ok else 'FALLA'}\n")
    return ok


def svg_chart(shots, path, title):
    """SVG simple de media cancha (landscape, aro a la derecha) con tiros normalizados+renderizados.
    shots: lista de (x,y,made,is3) crudos del feed."""
    W, H, pad = 560, 300, 20
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">',
             f'<rect x="0" y="0" width="{W}" height="{H}" fill="#1b1b1b"/>',
             f'<text x="{pad}" y="16" fill="#ddd" font-size="13">{title}</text>',
             f'<rect x="{pad}" y="{pad+8}" width="{W-2*pad}" height="{H-2*pad-8}" fill="none" stroke="#555"/>']
    ax, ay, aw, ah = pad, pad + 8, W - 2 * pad, H - 2 * pad - 8
    for x, y, made, is3 in shots:
        nx, ny = normalize_side(x, y)
        cx, cy = render(nx, ny)
        px = ax + cx / 100 * aw
        py = ay + cy / 100 * ah
        if made:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.4" fill="#2ec26b" opacity="0.85"/>')
        else:
            parts.append(f'<path d="M{px-3.2:.1f} {py-3.2:.1f} L{px+3.2:.1f} {py+3.2:.1f} '
                         f'M{px-3.2:.1f} {py+3.2:.1f} L{px+3.2:.1f} {py-3.2:.1f}" stroke="#e0556b" stroke-width="1.6"/>')
    parts.append('</svg>')
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def main():
    if not golden_test():
        print("ABORTADO: el golden test no pasa, no se generan cartas.")
        sys.exit(1)

    out = ROOT / "data" / "agg" / "clasificatorio_lub_25_26" / "charts"
    out.mkdir(parents=True, exist_ok=True)

    # carta de Moller raw (P1) para confirmación visual del golden test
    d = json.loads((ROOT / "data" / "raw" / "2845330.json").read_text(encoding="utf-8"))
    moller = [(float(s["x"]), float(s["y"]), int(s["r"]) == 1, s["actionType"] == "3pt")
              for s in d["tm"]["2"]["shot"] if int(s.get("pno")) == 7]
    # NOTA: para el golden, render RAW (sin fold) -> uso normalize off pasando ya-normalizados:
    svg_raw = []
    for x, y, made, is3 in moller:
        svg_raw.append((x, y, made, is3))
    # render sin fold: temporariamente evito normalize dibujando con x crudo (fold solo cambia si x<50)
    svg_chart_raw(svg_raw, out / "golden_moller_raw.svg", "Golden test — A. Moller raw (P1) | verde=encestado x=fallado")

    # carta agregada de UUN (fold de lado + render) sobre la fase
    import csv
    SCH = ROOT / "data" / "schedule"
    excl = {r["matchId"] for r in csv.DictReader((SCH / "exclusions.csv").open(encoding="utf-8"))}
    schedule = json.loads((SCH / "schedule.json").read_text(encoding="utf-8"))
    uun = []
    for mid in [m for m in schedule["Clasificatorio LUB 25/26"] if m not in excl]:
        dm = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        for t in ("1", "2"):
            if dm["tm"][t]["code"] == "UUN":
                for s in dm["tm"][t].get("shot", []):
                    uun.append((float(s["x"]), float(s["y"]), int(s["r"]) == 1, s["actionType"] == "3pt"))
    svg_chart(uun, out / "uun_team.svg", f"Urunday (UUN) — carta agregada Clasificatorio ({len(uun)} tiros)")
    print(f"Cartas en {out}  (golden_moller_raw.svg, uun_team.svg)")


def svg_chart_raw(shots, path, title):
    """Igual que svg_chart pero SIN fold (para el golden test, coords crudas)."""
    W, H, pad = 560, 300, 20
    ax, ay, aw, ah = pad, pad + 8, W - 2 * pad, H - 2 * pad - 8
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#1b1b1b"/>',
             f'<text x="{pad}" y="16" fill="#ddd" font-size="13">{title}</text>',
             f'<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" fill="none" stroke="#555"/>']
    for x, y, made, is3 in shots:
        cx, cy = render(x, y)
        px, py = ax + cx / 100 * aw, ay + cy / 100 * ah
        if made:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#2ec26b"/>')
        else:
            parts.append(f'<path d="M{px-3.5:.1f} {py-3.5:.1f} L{px+3.5:.1f} {py+3.5:.1f} '
                         f'M{px-3.5:.1f} {py+3.5:.1f} L{px+3.5:.1f} {py-3.5:.1f}" stroke="#e0556b" stroke-width="1.8"/>')
    parts.append('</svg>')
    Path(path).write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
