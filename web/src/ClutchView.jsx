import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

// Celda de eFG%: tasa solo si la muestra (FGA) llega al umbral; si no, gris "muestra insuficiente".
function Efg({ row }) {
  if (row.qualified) return <span className="cl-efg">{row.eFG.toFixed(1)}</span>
  return <span className="cl-insuf" title={`Solo ${row.FGA} tiros clutch — muestra insuficiente`}>—</span>
}

const tone = (eFG, qualified) => (!qualified ? '#9aa1ad' : eFG >= 50 ? '#16a34a' : '#dc2626')

export default function ClutchView() {
  const { clutch } = useData()
  const { thresholds, totalGames, clutchGames, totalPoss } = clutch
  const [onlyQual, setOnlyQual] = useState(false)
  const [psort, setPsort] = useState({ key: 'FGA', asc: false })

  const players = [...clutch.players]
    .filter((p) => !onlyQual || p.qualified)
    .sort((a, b) => {
      const va = a[psort.key], vb = b[psort.key]
      const r = typeof va === 'string' ? String(va).localeCompare(String(vb)) : va - vb
      return psort.asc ? r : -r
    })
  const pclick = (key) => setPsort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: false }))
  const parrow = (key) => (psort.key === key ? (psort.asc ? ' ▲' : ' ▼') : '')

  const teams = [...clutch.teams].sort((a, b) => b.FGA - a.FGA)

  return (
    <div>
      <div className="home-head">
        <h1>Clutch</h1>
        <span className="meta">Últimos 5:00 de Q4/OT con diferencia ≤ 5 puntos · LUB Clasificatorio</span>
      </div>

      {/* Banner de honestidad: la muestra clutch de la LUB es minúscula */}
      <div className="card full cl-warn">
        <b>Leé esto antes de los números.</b> El clutch en la LUB es <b>anécdota, no estadística</b>:
        solo <b>{clutchGames} de {totalGames}</b> partidos tuvieron momentos clutch, con <b>{totalPoss}</b>{' '}
        posesiones clutch en <b>toda</b> la liga (las dos selecciones juntas) — menos que un solo partido
        normal. Por eso: los <b>conteos</b> (puntos, tiros, pérdidas) se muestran siempre, pero el{' '}
        <b>eFG%</b> aparece solo con muestra suficiente (jugador ≥ {thresholds.playerFGA} tiros, equipo
        ≥ {thresholds.teamFGA}); por debajo va en gris como <span className="cl-insuf">muestra insuficiente</span>.
        Tomá todo con pinzas.
      </div>

      {/* --- Equipos --- */}
      <div className="card full" style={{ overflowX: 'auto', marginBottom: 18 }}>
        <h2>Por equipo</h2>
        <table className="ltable">
          <thead>
            <tr>
              <th className="lcol">Equipo</th>
              <th>PJ clutch</th><th>Pos</th><th>PTS</th><th>FG</th><th>3PM</th><th>TOV</th>
              <th>eFG%</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((t) => {
              const isUru = t.code === HOME_TEAM
              return (
                <tr key={t.code} className={isUru ? 'row-uru' : ''}>
                  <td className="lcol">
                    <Link to={`/team/${t.code}`} className="tlink">{t.name}</Link>
                  </td>
                  <td>{t.clutchGames}</td>
                  <td>{t.Poss.toFixed(1)}</td>
                  <td>{t.PTS}</td>
                  <td>{t.FGM}-{t.FGA}</td>
                  <td>{t['3PM']}</td>
                  <td>{t.TOV}</td>
                  <td style={{ color: tone(t.eFG, t.qualified), fontWeight: 700 }}><Efg row={t} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* --- Jugadores --- */}
      <div className="card full" style={{ overflowX: 'auto' }}>
        <div className="cl-head">
          <h2 style={{ margin: 0 }}>Por jugador</h2>
          <label className="poolfilter" style={{ margin: 0 }}>
            <input type="checkbox" checked={onlyQual} onChange={(e) => setOnlyQual(e.target.checked)} />
            Solo muestra suficiente (≥ {thresholds.playerFGA} tiros)
          </label>
        </div>
        <table className="ltable">
          <thead>
            <tr>
              <th className="lcol">Jugador</th>
              <th>Eq</th>
              {[['clutchGames', 'PJ'], ['PTS', 'PTS'], ['FGA', 'FG'], ['3PM', '3PM'], ['TOV', 'TOV'], ['eFG', 'eFG%']].map(
                ([k, lbl]) => (
                  <th key={k} className={psort.key === k ? 'sorted' : ''}
                      onClick={() => pclick(k)} style={{ cursor: 'pointer' }}>{lbl}{parrow(k)}</th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {players.map((p) => {
              const isUru = p.team === HOME_TEAM
              return (
                <tr key={p.personId} className={isUru ? 'row-uru' : ''}>
                  <td className="lcol">
                    <Link to={`/player/${p.personId}`} className="tlink">{p.name}</Link>
                  </td>
                  <td>{p.team}</td>
                  <td>{p.clutchGames}</td>
                  <td>{p.PTS}</td>
                  <td>{p.FGM}-{p.FGA}</td>
                  <td>{p['3PM']}</td>
                  <td>{p.TOV}</td>
                  <td style={{ color: tone(p.eFG, p.qualified), fontWeight: 700 }}><Efg row={p} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="legend">
          <b>FG</b> = encestados-intentados clutch · <b>PJ</b> = partidos con minutos clutch · ordená por
          cualquier columna. El <b>eFG%</b> está en gris cuando hay menos de {thresholds.playerFGA} tiros
          (muestra insuficiente): preferimos no dar un dato antes que dar ruido.
        </p>
      </div>
    </div>
  )
}
