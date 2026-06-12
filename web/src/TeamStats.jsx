import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

// Columnas de la tabla. dir = sentido "bueno" (1 = más alto mejor, -1 = más bajo mejor),
// usado solo para colorear suavemente. group separa ataque / defensa.
const COLS = [
  { key: 'GP', label: 'PJ', group: 'id', dir: 0, dec: 0 },
  { key: 'ORtg', label: 'ORtg', group: 'rtg', dir: 1, dec: 1 },
  { key: 'DRtg', label: 'DRtg', group: 'rtg', dir: -1, dec: 1 },
  { key: 'NetRtg', label: 'Net', group: 'rtg', dir: 1, dec: 1, net: true },
  { key: 'Pace', label: 'Pace', group: 'rtg', dir: 0, dec: 1 },
  { key: 'eFG%', label: 'eFG%', group: 'atk', dir: 1, dec: 1 },
  { key: 'TOV%', label: 'TOV%', group: 'atk', dir: -1, dec: 1 },
  { key: 'ORB%', label: 'ORB%', group: 'atk', dir: 1, dec: 1 },
  { key: 'FTR', label: 'FTR', group: 'atk', dir: 1, dec: 1 },
  { key: 'D_eFG%', label: 'eFG%', group: 'def', dir: -1, dec: 1 },
  { key: 'D_TOV%', label: 'TOV%', group: 'def', dir: 1, dec: 1 },
  { key: 'DRB%', label: 'DRB%', group: 'def', dir: 1, dec: 1 },
  { key: 'D_FTR', label: 'FTR', group: 'def', dir: -1, dec: 1 },
]

export default function TeamStats() {
  const { teams } = useData()
  const rows = Object.values(teams)
  const [sort, setSort] = useState({ key: 'NetRtg', asc: false })

  const sorted = [...rows].sort((a, b) => {
    const va = a.ratings[sort.key]
    const vb = b.ratings[sort.key]
    return sort.asc ? va - vb : vb - va
  })

  const clickSort = (key) =>
    setSort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: false }))

  const arrow = (key) => (sort.key === key ? (sort.asc ? ' ▲' : ' ▼') : '')

  return (
    <div>
      <div className="home-head">
        <h1>Estadísticas de equipo · Four Factors</h1>
        <span className="meta">12 equipos · LUB Clasificatorio · clic en la columna para ordenar</span>
      </div>

      <div className="card full" style={{ overflowX: 'auto', marginBottom: 18 }}>
        <table className="ltable">
          <thead>
            <tr className="grp">
              <th></th>
              <th></th>
              <th className="g-rtg" colSpan={4}>Rating</th>
              <th></th>
              <th className="g-atk" colSpan={4}>Four Factors · Ataque</th>
              <th className="g-def" colSpan={4}>Four Factors · Defensa</th>
            </tr>
            <tr>
              <th className="lcol" onClick={() => clickSort('name')} style={{ cursor: 'pointer' }}>
                Equipo
              </th>
              {COLS.map((c) => (
                <th
                  key={c.key}
                  className={`g-${c.group} ${sort.key === c.key ? 'sorted' : ''}`}
                  onClick={() => clickSort(c.key)}
                  style={{ cursor: 'pointer' }}
                >
                  {c.label}
                  {arrow(c.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => {
              const isUru = t.code === HOME_TEAM
              return (
                <tr key={t.code} className={isUru ? 'row-uru' : ''}>
                  <td className="lcol">
                    <Link to={`/team/${t.code}`} className="tlink">
                      {t.name}
                    </Link>
                  </td>
                  {COLS.map((c) => {
                    const v = t.ratings[c.key]
                    let style = {}
                    if (c.net) style.color = v > 0 ? '#16a34a' : '#dc2626'
                    if (c.net) style.fontWeight = 700
                    return (
                      <td key={c.key} className={`g-${c.group}`} style={style}>
                        {c.net && v > 0 ? '+' : ''}
                        {v.toFixed(c.dec)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="legend" style={{ marginTop: -8, marginBottom: 18 }}>
        <b>Ataque</b> = lo que genera el equipo. <b>Defensa</b> = lo que le permite al rival (eFG%/FTR
        bajos y TOV%/DRB% altos son buena defensa). Net = ORtg − DRtg. Urunday resaltado en azul.
      </p>

      <Scatter rows={rows} />
    </div>
  )
}

// Scatter ORtg (x) vs DRtg (y, invertido: buena defensa arriba). Estilo OpenACB:
// arriba-derecha = élite (ataca y defiende), abajo-izquierda = flojo en ambas.
function Scatter({ rows }) {
  const W = 640
  const H = 460
  const pad = { t: 30, r: 24, b: 46, l: 52 }
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b

  const oVals = rows.map((r) => r.ratings.ORtg)
  const dVals = rows.map((r) => r.ratings.DRtg)
  const oMin = Math.min(...oVals) - 3
  const oMax = Math.max(...oVals) + 3
  const dMin = Math.min(...dVals) - 3
  const dMax = Math.max(...dVals) + 3
  const oAvg = oVals.reduce((a, b) => a + b, 0) / oVals.length
  const dAvg = dVals.reduce((a, b) => a + b, 0) / dVals.length

  const x = (o) => pad.l + ((o - oMin) / (oMax - oMin)) * iw
  // DRtg invertido: menor DRtg (mejor defensa) va ARRIBA
  const y = (d) => pad.t + ((d - dMin) / (dMax - dMin)) * ih

  const cx0 = x(oAvg)
  const cy0 = y(dAvg)

  return (
    <div className="card full">
      <h2>ORtg vs DRtg · cada punto es un equipo</h2>
      <div style={{ overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 680, display: 'block' }}>
          {/* marco */}
          <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="#fafbff" stroke="#e5e8ef" />
          {/* líneas de promedio liga */}
          <line x1={cx0} y1={pad.t} x2={cx0} y2={pad.t + ih} stroke="#c7cede" strokeDasharray="4 4" />
          <line x1={pad.l} y1={cy0} x2={pad.l + iw} y2={cy0} stroke="#c7cede" strokeDasharray="4 4" />
          {/* etiquetas de cuadrante */}
          <text x={pad.l + iw - 6} y={pad.t + 14} textAnchor="end" className="quad">élite ▲</text>
          <text x={pad.l + 6} y={pad.t + ih - 6} className="quad">flojo</text>
          {/* ejes */}
          <text x={pad.l + iw / 2} y={H - 10} textAnchor="middle" className="axlbl">
            Ataque — ORtg →
          </text>
          <text
            x={16}
            y={pad.t + ih / 2}
            textAnchor="middle"
            className="axlbl"
            transform={`rotate(-90 16 ${pad.t + ih / 2})`}
          >
            ← Defensa — DRtg
          </text>
          {/* puntos */}
          {rows.map((r) => {
            const isUru = r.code === HOME_TEAM
            const px = x(r.ratings.ORtg)
            const py = y(r.ratings.DRtg)
            return (
              <g key={r.code}>
                <circle cx={px} cy={py} r={isUru ? 7 : 5} fill={isUru ? '#2563eb' : '#94a3b8'} />
                <text
                  x={px + (isUru ? 10 : 8)}
                  y={py + 4}
                  className={isUru ? 'ptlbl uru' : 'ptlbl'}
                >
                  {r.code}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <p className="legend">
        Eje X = ataque (ORtg, derecha mejor). Eje Y = defensa (DRtg, <b>arriba mejor</b>, está
        invertido). Líneas punteadas = promedio de la liga. Arriba-derecha es el cuadrante de élite.
      </p>
    </div>
  )
}
