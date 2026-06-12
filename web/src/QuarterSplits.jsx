import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

const BLUE = '#2563eb'
const RED = '#dc2626'
const QS = ['Q1', 'Q2', 'Q3', 'Q4']

const dColor = (v) => (v > 0.05 ? '#16a34a' : v < -0.05 ? '#dc2626' : '#64748b')

// Diferencial promedio de un equipo en un cuarto dado (o null si no lo tiene).
const qdiff = (t, q) => {
  const r = t.quarters.find((x) => x.q === q)
  return r ? r.diff : null
}

export default function QuarterSplits() {
  const { quarters } = useData()
  const teams = Object.values(quarters.teams)
  const [sel, setSel] = useState(HOME_TEAM)
  const [sort, setSort] = useState({ key: 'Q4', asc: false })

  const sorted = [...teams].sort((a, b) => {
    if (sort.key === 'name') return sort.asc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)
    const va = qdiff(a, sort.key) ?? -99
    const vb = qdiff(b, sort.key) ?? -99
    return sort.asc ? va - vb : vb - va
  })
  const clickSort = (key) =>
    setSort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: false }))
  const arrow = (key) => (sort.key === key ? (sort.asc ? ' ▲' : ' ▼') : '')

  const team = quarters.teams[sel]

  return (
    <div>
      <div className="home-head">
        <h1>Rendimiento por cuarto</h1>
        <span className="meta">
          LUB Clasificatorio · promedio por cuarto sobre todos los partidos de cada equipo
        </span>
      </div>

      {/* Tabla liga: diferencial promedio por cuarto, equipo por fila */}
      <div className="card full" style={{ overflowX: 'auto', marginBottom: 18 }}>
        <table className="ltable">
          <thead>
            <tr>
              <th className="lcol" onClick={() => clickSort('name')} style={{ cursor: 'pointer' }}>
                Equipo{arrow('name')}
              </th>
              <th>PJ</th>
              {QS.map((q) => (
                <th key={q} className={sort.key === q ? 'sorted' : ''}
                    onClick={() => clickSort(q)} style={{ cursor: 'pointer' }}>
                  {q} Dif{arrow(q)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => {
              const isUru = t.code === HOME_TEAM
              return (
                <tr key={t.code}
                    className={`${isUru ? 'row-uru' : ''} ${t.code === sel ? 'row-sel' : ''}`}>
                  <td className="lcol">
                    <button className="tlink linkish" onClick={() => setSel(t.code)}>{t.name}</button>
                  </td>
                  <td>{t.GP}</td>
                  {QS.map((q) => {
                    const v = qdiff(t, q)
                    return (
                      <td key={q} style={{ color: dColor(v), fontWeight: 600 }}>
                        {v > 0 ? '+' : ''}{v.toFixed(1)}
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
        Cada celda es el <b>diferencial promedio</b> (puntos a favor − en contra) de ese equipo en ese
        cuarto, sobre sus <b>PJ</b> partidos. Verde = lo gana en promedio, rojo = lo pierde. Clic en un
        equipo para ver su detalle abajo. Urunday resaltado.
      </p>

      {team && <TeamDetail team={team} />}
    </div>
  )
}

function TeamDetail({ team }) {
  const isUru = team.code === HOME_TEAM
  const accent = isUru ? BLUE : RED
  const maxAbs = Math.max(2, ...team.quarters.map((q) => Math.abs(q.diff)))

  return (
    <div className="card full">
      <h2 style={{ color: accent }}>{team.name} · detalle por cuarto</h2>

      <div className="qs-grid">
        {/* tabla detalle */}
        <table className="ltable qs-detail">
          <thead>
            <tr>
              <th className="lcol">Cuarto</th>
              <th>PJ</th>
              <th>PF</th>
              <th>PC</th>
              <th>Dif</th>
              <th>eFG%</th>
              <th>eFG% riv</th>
            </tr>
          </thead>
          <tbody>
            {team.quarters.map((q) => (
              <tr key={q.q} className={q.q === 'OT' ? 'qs-ot' : ''}>
                <td className="lcol"><b>{q.q}</b></td>
                <td>{q.gp}</td>
                <td>{q.pf.toFixed(1)}</td>
                <td>{q.pa.toFixed(1)}</td>
                <td style={{ color: dColor(q.diff), fontWeight: 700 }}>
                  {q.diff > 0 ? '+' : ''}{q.diff.toFixed(1)}
                </td>
                <td>{q.efg.toFixed(1)}</td>
                <td>{q.d_efg.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* barras de diferencial por cuarto */}
        <div className="qs-bars">
          {team.quarters.map((q) => {
            const w = (Math.abs(q.diff) / maxAbs) * 50
            return (
              <div className="qs-bar-row" key={q.q}>
                <span className="qs-bar-lbl">{q.q}</span>
                <div className="qs-bar-track">
                  <div className="qs-bar-mid" />
                  <div className="qs-bar-fill"
                       style={{
                         left: q.diff >= 0 ? '50%' : `${50 - w}%`,
                         width: `${w}%`,
                         background: dColor(q.diff),
                       }} />
                </div>
                <span className="qs-bar-val" style={{ color: dColor(q.diff) }}>
                  {q.diff > 0 ? '+' : ''}{q.diff.toFixed(1)}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <p className="legend">
        <b>PF</b> = puntos a favor por cuarto · <b>PC</b> = en contra · <b>Dif</b> = diferencial · todo
        es <b>promedio por partido</b>. <b>PJ</b> = partidos detrás de cada promedio (muestra visible).
        {team.quarters.some((q) => q.q === 'OT') && (
          <> La fila <b>OT</b> agrega las prórrogas: muestra chica (ver PJ), tomar con pinzas.</>
        )}{' '}
        Validado: la suma de los cuartos de cada partido coincide exacto con el marcador del boxscore en
        los 131 del Clasificatorio. <Link to={`/team/${team.code}`} className="tlink">Ver perfil completo →</Link>
      </p>
    </div>
  )
}
