import { Link } from 'react-router-dom'
import Radar from './Radar.jsx'
import ShotChart from './ShotChart.jsx'

const RADAR_METRICS = ['TS%', 'USG%', 'AST%', 'REB%', 'STL%', 'BLK%']

export default function PlayerProfile({ player }) {
  const isUru = player.team === 'UUN'
  const b = player.basic
  const pct = player.percentiles

  const axes = RADAR_METRICS
    .filter((m) => pct[m])
    .map((m) => ({ label: m, value: pct[m].pct }))

  return (
    <div>
      <div className="player-head">
        <h1>{player.name}</h1>
        <Link to={`/team/${player.team}`} className={`badge ${isUru ? 'uru' : 'rival'}`}>{player.teamName}</Link>
        <span className="meta">{player.pos} · {player.GP} PJ · {Math.round(player.MIN)} min</span>
      </div>

      <div className="grid">
        {/* (a) básicas */}
        <div className="card">
          <h2>Stats básicas</h2>
          <div className="stats">
            <Stat v={(b.PTS / player.GP).toFixed(1)} l="PTS/PJ" />
            <Stat v={(b.REB / player.GP).toFixed(1)} l="REB/PJ" />
            <Stat v={(b.AST / player.GP).toFixed(1)} l="AST/PJ" />
            <Stat v={`${b.FGpct}%`} l="FG%" />
            <Stat v={b.PTS} l="Puntos" />
            <Stat v={Math.round(player.MIN)} l="Minutos" />
            <Stat v={player.GP} l="Partidos" />
            <Stat v={`${b.FGM}/${b.FGA}`} l="FG" />
          </div>
        </div>

        {/* (b) radar percentiles */}
        <div className="card">
          <h2>Percentiles vs liga {player.inPool ? '' : '(fuera de pool ≥200 min)'}</h2>
          {axes.length ? (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Radar axes={axes} color={isUru ? '#2563eb' : '#dc2626'} />
            </div>
          ) : (
            <p style={{ color: '#6b7280' }}>Sin percentiles (muestra &lt; 200 min).</p>
          )}
          <div className="legend">Percentil 0–100 sobre el pool de la liga (≥200 min). Más alto = mejor.</div>
        </div>

        {/* (c) carta de tiro por zona */}
        <div className="card full">
          <h2>Carta de tiro por zona</h2>
          <div className="chartwrap">
            <div className="svgbox light">
              {player.shots && player.shots.length ? (
                <ShotChart shots={player.shots} />
              ) : (
                <p style={{ color: '#94a3b8', padding: 20 }}>Sin tiros registrados.</p>
              )}
            </div>
            <div className="ztab">
              <table className="zones">
                <thead>
                  <tr><th>Zona</th><th>FGA</th><th>FGM</th><th>FG%</th><th>eFG%</th></tr>
                </thead>
                <tbody>
                  {player.zones.map((z) => (
                    <tr key={z.zone}>
                      <td>{z.zone}</td>
                      <td className="fga">{z.FGA}</td>
                      <td>{z.FGM}</td>
                      <td>{z.FGpct.toFixed(1)}</td>
                      <td className={z.eFG >= 55 ? 'efg-hi' : ''}>{z.eFG.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="legend">FGA visible: zonas de pocos intentos no son conclusión.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({ v, l }) {
  return (
    <div className="stat">
      <div className="v">{v}</div>
      <div className="l">{l}</div>
    </div>
  )
}
