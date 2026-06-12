import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

// Percentiles clave a mostrar (clave en players.json -> etiqueta).
const PCTS = [
  { key: 'PTS36', label: 'PTS36' },
  { key: 'TS%', label: 'TS%' },
  { key: 'eFG%', label: 'eFG%' },
  { key: 'USG%', label: 'USG%' },
  { key: 'AST%', label: 'AST%' },
  { key: 'REB%', label: 'REB%' },
  { key: 'STL%', label: 'STL%' },
  { key: 'BLK%', label: 'BLK%' },
]

// Heat 0(rojo)->50(amarillo)->100(verde) para el percentil.
function heat(pct) {
  if (pct == null) return undefined
  const hue = pct * 1.2 // 0=rojo, 120=verde
  return `hsl(${hue}, 65%, 88%)`
}

export default function PlayerStats() {
  const { players } = useData()
  const rows = Object.values(players)
  const [sort, setSort] = useState({ key: 'MIN', asc: false })
  const [onlyPool, setOnlyPool] = useState(false)

  const val = (p, key) => {
    if (key === 'name') return p.name
    if (key === 'MIN' || key === 'GP') return p[key]
    if (key === 'PPG') return p.GP ? p.basic.PTS / p.GP : 0
    if (key === 'PTS') return p.basic.PTS
    // percentil
    return p.percentiles[key]?.pct ?? null
  }

  const visible = onlyPool ? rows.filter((p) => p.inPool) : rows

  const sorted = [...visible].sort((a, b) => {
    const va = val(a, sort.key)
    const vb = val(b, sort.key)
    if (sort.key === 'name') return sort.asc ? va.localeCompare(vb) : vb.localeCompare(va)
    // nulos (sin percentil, <200') siempre al fondo
    const na = va == null ? -Infinity : va
    const nb = vb == null ? -Infinity : vb
    return sort.asc ? na - nb : nb - na
  })

  const clickSort = (key) =>
    setSort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: false }))
  const arrow = (key) => (sort.key === key ? (sort.asc ? ' ▲' : ' ▼') : '')

  return (
    <div>
      <div className="home-head">
        <h1>Estadísticas de jugador</h1>
        <span className="meta">
          {visible.length} jugadores · LUB Clasificatorio · clic en la columna para ordenar
        </span>
      </div>

      <label className="poolfilter">
        <input type="checkbox" checked={onlyPool} onChange={(e) => setOnlyPool(e.target.checked)} />
        Solo muestra suficiente (≥200′)
      </label>

      <div className="card full" style={{ overflowX: 'auto' }}>
        <table className="ltable">
          <thead>
            <tr className="grp">
              <th></th>
              <th className="g-rtg" colSpan={4}>Volumen</th>
              <th className="g-atk" colSpan={PCTS.length}>Percentiles vs liga (0–100)</th>
            </tr>
            <tr>
              <th className="lcol" onClick={() => clickSort('name')} style={{ cursor: 'pointer' }}>
                Jugador{arrow('name')}
              </th>
              <th className="g-rtg" onClick={() => clickSort('GP')} style={{ cursor: 'pointer' }}>GP{arrow('GP')}</th>
              <th className="g-rtg" onClick={() => clickSort('MIN')} style={{ cursor: 'pointer' }}>MIN{arrow('MIN')}</th>
              <th className="g-rtg" onClick={() => clickSort('PTS')} style={{ cursor: 'pointer' }}>PTS{arrow('PTS')}</th>
              <th className="g-rtg" onClick={() => clickSort('PPG')} style={{ cursor: 'pointer' }}>PPG{arrow('PPG')}</th>
              {PCTS.map((c) => (
                <th
                  key={c.key}
                  className={`g-atk ${sort.key === c.key ? 'sorted' : ''}`}
                  onClick={() => clickSort(c.key)}
                  style={{ cursor: 'pointer' }}
                >
                  {c.label}{arrow(c.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const isUru = p.team === HOME_TEAM
              return (
                <tr key={p.personId} className={isUru ? 'row-uru' : ''}>
                  <td className="lcol">
                    <Link to={`/player/${p.personId}`} className="tlink">{p.name}</Link>
                    <span className="pteam">{p.team}</span>
                    {!p.inPool && <span className="tag-low" title="Menos de 200 minutos: muestra chica, percentiles no calculados"> · &lt;200′</span>}
                  </td>
                  <td className="g-rtg">{p.GP}</td>
                  <td className="g-rtg">{Math.round(p.MIN)}</td>
                  <td className="g-rtg">{p.basic.PTS}</td>
                  <td className="g-rtg">{p.GP ? (p.basic.PTS / p.GP).toFixed(1) : '—'}</td>
                  {PCTS.map((c) => {
                    const m = p.percentiles[c.key]
                    return (
                      <td
                        key={c.key}
                        className="g-atk pcell"
                        style={{ background: heat(m?.pct) }}
                        title={m ? `valor real: ${m.val}` : 'muestra <200′'}
                      >
                        {m ? Math.round(m.pct) : '—'}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="legend">
        Cada celda de percentil es el puesto del jugador vs toda la liga (Clasificatorio): 100 = mejor,
        50 = mediana. Verde alto, rojo bajo. <b>PTS/MIN/GP son totales</b> de la temporada; PPG = puntos
        por partido. Los jugadores con <b>&lt;200′</b> no entran al pool de percentiles (muestra chica):
        se listan igual, con el volumen, pero sin percentil. Urunday resaltado en azul.
      </p>
    </div>
  )
}
