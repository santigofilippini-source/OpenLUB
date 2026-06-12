"""
07_tracking — On-court por partido desde las substitutions del pbp (quintetos / stints).

Modelo (validado contra la estructura del feed):
- El pbp viene en orden CRONOLÓGICO INVERSO -> procesar al revés. `gt`="MM:SS" cuenta hacia
  ATRÁS desde el largo del período (10:00 regular, 5:00 OT).
- Quinteto inicial:
    P1  -> los 5 con flag `starter` en el data.json.
    P2+ -> el quinteto PERSISTE del cierre del período anterior; los cambios de arranque se
           registran como subs en gt=10:00 (0s transcurridos antes) y ajustan el quinteto.
- Minutos por jugador = suma de segmentos en cancha entre timestamps de sub, por período.

VALIDACIÓN OBLIGATORIA (este módulo NO construye nada encima hasta pasar):
  minutos del tracking == `sMinutes` del boxscore, por jugador y por partido, en los 131.
Reporta cuántos cuadran al segundo y lista los que no (cada uno = sub mal trackeado).
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "matches"
SCH_DIR = ROOT / "data" / "schedule"
DEFAULT_PHASE = "Clasificatorio LUB 25/26"


def gtsec(g: str) -> int:
    """'MM:SS' -> segundos enteros (para normalizar sMinutes del boxscore)."""
    a = g.split(":")
    return int(a[0]) * 60 + int(a[1])


def clocksec(c: str) -> float:
    """'MM:SS:CC' (CC = centésimas) -> segundos con decimales. Da la precisión real del sub."""
    a = c.split(":")
    return int(a[0]) * 60 + int(a[1]) + (int(a[2]) / 100 if len(a) > 2 else 0)


def load_exclusions():
    f = SCH_DIR / "exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def load_lineup_exclusions():
    """Partidos con subs corruptos en el feed: se excluyen del tracking de stints/on-off
    (su boxscore sigue siendo válido para agregados)."""
    f = SCH_DIR / "lineup_exclusions.csv"
    return {r["matchId"] for r in csv.DictReader(f.open(encoding="utf-8"))} if f.exists() else set()


def pkey(e) -> int:
    """Orden absoluto de período. OT reinicia `period` a 1 con periodType=OVERTIME -> va DESPUÉS
    de los 4 regulares (OT período 1 -> 5, etc.). Sin esto, la OT colisiona con el P1 regular."""
    p = int(e["period"])
    return 4 + p if e.get("periodType") == "OVERTIME" else p


def track_match(d: dict):
    """Devuelve {(tno, pno): segundos en cancha} por tracking de subs.

    Itera el pbp en orden cronológico REAL (= invertido, porque el feed viene al revés) y aplica
    cada sub en secuencia. Esto respeta el orden de los subs simultáneos del fin de cuarto (cambios
    masivos), que es donde se rompía la versión que reordenaba por clock.
    Lanza ValueError si un quinteto queda != 5 al cierre de un período (sub realmente desbalanceado).
    """
    len_reg = int(d.get("periodLengthREGULAR", 10)) * 60.0
    len_ot = int(d.get("periodLengthOVERTIME", 5)) * 60.0

    oncourt = {}
    for t in ("1", "2"):
        oncourt[int(t)] = {int(k) for k, p in d["tm"][t]["pl"].items() if p.get("starter")}
        if len(oncourt[int(t)]) != 5:
            raise ValueError(f"team {t} starters != 5 ({len(oncourt[int(t)])})")

    secs = defaultdict(float)
    cur_pk = None
    plen = len_reg
    last = len_reg  # segundos remanentes en el último timestamp procesado

    for e in reversed(d["pbp"]):           # orden cronológico real
        if not e.get("period"):
            continue
        pk = pkey(e)
        c = clocksec(e["clock"])
        if pk != cur_pk:                   # arranca un período nuevo
            if cur_pk is not None:
                for tno, lineup in oncourt.items():
                    if len(lineup) != 5:
                        raise ValueError(f"cierre P{cur_pk} team {tno} oncourt={len(lineup)}")
            cur_pk = pk
            plen = len_reg if pk <= 4 else len_ot
            last = plen
        seg = last - c
        if seg > 0:
            for tno, lineup in oncourt.items():
                for pno in lineup:
                    secs[(tno, pno)] += seg
        last = c
        if e.get("actionType") == "substitution":
            tno, pno = int(e["tno"]), int(e["pno"])
            if e.get("subType") == "in":
                oncourt[tno].add(pno)
            elif e.get("subType") == "out":
                oncourt[tno].discard(pno)
    for tno, lineup in oncourt.items():    # cierre del último período
        if len(lineup) != 5:
            raise ValueError(f"cierre final team {tno} oncourt={len(lineup)}")
    return secs


def mmss(sec: int) -> str:
    return f"{sec // 60}:{sec % 60:02d}"


def validate(mid: str):
    """Devuelve (ok, lista de mismatches [(tno,pno,name,tracked,box)])."""
    d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
    try:
        secs = track_match(d)
    except ValueError as e:
        return False, [("-", "-", str(e), "", "")]
    mism = []
    for t in ("1", "2"):
        tno = int(t)
        for k, p in d["tm"][t]["pl"].items():
            box_sec = gtsec(p.get("sMinutes") or "0:00")
            tracked_sec = round(secs.get((tno, int(k)), 0))
            if tracked_sec != box_sec:
                mism.append((tno, k, p.get("name"), mmss(tracked_sec), mmss(box_sec),
                             tracked_sec - box_sec))
    return len(mism) == 0, mism


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHASE
    schedule = json.loads((SCH_DIR / "schedule.json").read_text(encoding="utf-8"))
    lineup_excl = load_lineup_exclusions()
    ids = [m for m in schedule[phase] if m not in load_exclusions() and m not in lineup_excl]

    exact = 0
    rounding = []   # quinteto OK, solo redondeo (max |delta| <= 2s)
    structural = []  # oncourt != 5
    mistrack = []   # gaps grandes -> sub mal trackeado
    for mid in ids:
        ok, mism = validate(mid)
        if ok:
            exact += 1
            continue
        if any(len(r) != 6 for r in mism):           # error estructural
            structural.append((mid, mism))
        elif max(abs(r[5]) for r in mism) <= 2:       # solo redondeo ±1-2s
            rounding.append((mid, mism))
        else:
            mistrack.append((mid, mism))

    def tag(mid):
        d = json.loads((RAW_DIR / f"{mid}.json").read_text(encoding="utf-8"))
        return f"{d['tm']['1']['code']} vs {d['tm']['2']['code']}"

    print(f"Tracking de minutos vs boxscore — {phase}")
    print(f"  Partidos trackeados: {len(ids)}  (+ {len(lineup_excl)} excluidos por feed corrupto: {sorted(lineup_excl)})")
    print(f"  Exactos al segundo (todos los jugadores): {exact}")
    print(f"  Solo redondeo ±1-2s (quinteto correcto):  {len(rounding)}")
    print(f"  => QUINTETO BIEN TRACKEADO: {exact + len(rounding)}/{len(ids)}")
    print(f"  Mistrack REAL (estructural o gap grande):  {len(structural) + len(mistrack)}")

    if structural:
        print(f"\n--- ESTRUCTURALES (oncourt != 5) [{len(structural)}] ---")
        for mid, mism in structural:
            print(f"  {mid} ({tag(mid)}): {mism[0][2]}")
    if mistrack:
        print(f"\n--- GAPS GRANDES (sub mal trackeado) [{len(mistrack)}] ---")
        for mid, mism in mistrack:
            print(f"  {mid} ({tag(mid)}): {len(mism)} jugadores, max gap {max(abs(r[5]) for r in mism)}s")
            for tno, pno, name, tr, bx, delta in mism[:6]:
                print(f"      t{tno} #{pno} {name}: tracking={tr} box={bx} (diff {delta:+d}s)")


if __name__ == "__main__":
    main()
