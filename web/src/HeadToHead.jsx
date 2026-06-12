import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

export default function HeadToHead() {
  const { teams, results } = useData()
  const codes = Object.keys(teams)

  // stats[code] = { vs: {opp: {w,l,diff}}, w, l, diff }
  const stats = {}
  for (const c of codes) stats[c] = { vs: {}, w: 0, l: 0, diff: 0 }
  const bump = (a, b, sa, sb) => {
    const v = (stats[a].vs[b] ??= { w: 0, l: 0, diff: 0 })
    const win = sa > sb
    v.w += win ? 1 : 0
    v.l += win ? 0 : 1
    v.diff += sa - sb
    stats[a].w += win ? 1 : 0
    stats[a].l += win ? 0 : 1
    stats[a].diff += sa - sb
  }
  for (const g of results) {
    if (!stats[g.t1] || !stats[g.t2]) continue
    bump(g.t1, g.t2, g.s1, g.s2)
    bump(g.t2, g.t1, g.s2, g.s1)
  }

  // orden tipo tabla de posiciones: por victorias, desempate por diferencial.
  const order = [...codes].sort((a, b) => stats[b].w - stats[a].w || stats[b].diff - stats[a].diff)

  return (
    <div>
      <div className="home-head">
        <h1>Cara a Cara</h1>
        <span className="meta">{results.length} partidos · LUB Clasificatorio · fila vs columna</span>
      </div>

      <div className="card full" style={{ overflowX: 'auto' }}>
        <table className="h2h">
          <thead>
            <tr>
              <th className="lcol">Equipo</th>
              {order.map((c) => (
                <th key={c} className={c === HOME_TEAM ? 'col-uru' : ''}>{c}</th>
              ))}
              <th className="tot">Total</th>
              <th className="tot">Dif</th>
            </tr>
          </thead>
          <tbody>
            {order.map((row) => {
              const isUruRow = row === HOME_TEAM
              return (
                <tr key={row} className={isUruRow ? 'row-uru' : ''}>
                  <td className="lcol">
                    <Link to={`/team/${row}`} className="tlink">{teams[row].name}</Link>
                    <span className="pteam">{row}</span>
                  </td>
                  {order.map((col) => {
                    if (col === row) return <td key={col} className="diag">—</td>
                    const v = stats[row].vs[col]
                    if (!v) return <td key={col} className="muted">·</td>
                    const cls = v.w > v.l ? 'h2h-win' : v.l > v.w ? 'h2h-loss' : 'h2h-even'
                    return (
                      <td key={col} className={`${cls} ${col === HOME_TEAM ? 'col-uru' : ''}`} title={`Diferencial acumulado: ${v.diff > 0 ? '+' : ''}${v.diff}`}>
                        <span className="h2h-rec">{v.w}-{v.l}</span>
                        <span className="h2h-diff">{v.diff > 0 ? '+' : ''}{v.diff}</span>
                      </td>
                    )
                  })}
                  <td className="tot">{stats[row].w}-{stats[row].l}</td>
                  <td className="tot" style={{ color: stats[row].diff > 0 ? '#16a34a' : '#dc2626', fontWeight: 700 }}>
                    {stats[row].diff > 0 ? '+' : ''}{stats[row].diff}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="legend">
        Cada celda = récord de la <b>fila</b> contra la <b>columna</b> (victorias-derrotas) y, abajo, el
        diferencial de puntos acumulado en esos partidos. Verde = serie ganada, rojo = perdida, gris =
        empatada. Las dos últimas columnas son el récord y el diferencial de toda la temporada. Urunday
        resaltado en azul.
      </p>
      <p className="legend">
        El <b>FODA</b> (fortalezas y debilidades tácticas de cada rival) no es una tabla aparte: vive en el
        <b> perfil de cada equipo</b> — el recuadro "Plan en 30s" (qué explotarles, qué quitarles, a quién
        presionar) y las zonas de ataque/defensa vs liga. Clic en el nombre del equipo para abrirlo.
      </p>
    </div>
  )
}
