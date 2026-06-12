import { Link } from 'react-router-dom'
import { HOME_TEAM } from './App.jsx'

export default function TeamProfile({ team, players }) {
  const isUru = team.code === HOME_TEAM
  const r = team.ratings
  const roster = [...team.roster].sort((a, b) => b.MIN - a.MIN)

  return (
    <div>
      <div className="player-head">
        <h1>{team.name}</h1>
        <span className={`badge ${isUru ? 'uru' : 'rival'}`}>{team.code}</span>
        <span className="meta">{r.GP} PJ</span>
      </div>

      {/* recuadro de lectura táctica (el TL;DR del dossier de scouting) */}
      <div className="reading">
        <div className="reading-title">🎯 Plan en 30 segundos</div>
        <ul>
          <li><b>Qué explotarles:</b> {team.reading.explotar}</li>
          <li><b>Qué quitarles:</b> {team.reading.quitar}</li>
          <li><b>A quién presionar:</b> {team.reading.presionar}</li>
        </ul>
      </div>

      {/* ratings (módulo 4) */}
      <div className="card">
        <h2>Ratings (por 100 posesiones)</h2>
        <div className="stats">
          <Stat v={r.ORtg} l="ORtg" />
          <Stat v={r.DRtg} l="DRtg" />
          <Stat v={`${r.NetRtg > 0 ? '+' : ''}${r.NetRtg}`} l="Net" hi={r.NetRtg > 0} />
          <Stat v={r.Pace} l="Pace" />
          <Stat v={`${r['eFG%']}%`} l="eFG%" />
          <Stat v={`${r['TOV%']}%`} l="TOV%" />
          <Stat v={`${r['ORB%']}%`} l="ORB%" />
          <Stat v={`${r['FTR']}`} l="FT Rate" />
        </div>
      </div>

      {/* generadores: quién arma vs quién solo anota (cruce USG% x AST%) */}
      <div className="card">
        <h2>Generadores (PTS × USG% × AST%)</h2>
        <table className="zones gens">
          <thead>
            <tr><th>Jugador</th><th>Pos</th><th>PTS</th><th>USG% (pct)</th><th>AST% (pct)</th><th>Rol</th></tr>
          </thead>
          <tbody>
            {team.generators.map((g) => (
              <tr key={g.personId}>
                <td><Link to={`/player/${g.personId}`} className="glink">{g.name}</Link></td>
                <td>{g.pos}</td>
                <td className="fga">{g.PTS}</td>
                <td>{g.USG != null ? `${g.USG} (${g.USGpct})` : '—'}</td>
                <td>{g.AST != null ? `${g.AST} (${g.ASTpct})` : '—'}</td>
                <td><span className={`role role-${g.roleCode}`}>{g.role}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="legend">Verde = arma para otros (presionar la fuente). Gris = anota de lo que le crean.</div>
      </div>

      <div className="grid">
        <ZoneCard title="Tiro — ATAQUE" rows={team.zonesOff} />
        <ZoneCard title="Tiro — DEFENSA (lo que le tiran)" rows={team.zonesDef} defense />
      </div>

      <div className="grid">
        <div className="card">
          <h2>Líderes (por partido)</h2>
          <LeaderRow label="Puntos" items={team.leaders.pts} suffix="pts" />
          <LeaderRow label="Rebotes" items={team.leaders.reb} suffix="reb" />
          <LeaderRow label="Asistencias" items={team.leaders.ast} suffix="ast" />
        </div>

        <div className="card">
          <h2>Plantel ({roster.length})</h2>
          <div className="rosterlist">
            {roster.map((p) => (
              <Link key={p.personId} to={`/player/${p.personId}`} className="rrow">
                <span className="rrow-name">{p.name}</span>
                <span className="rrow-pos">{p.pos}</span>
                <span className="rrow-stat">{p.ppg} pts · {p.MIN}′</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ZoneCard({ title, rows, defense }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <table className="zones">
        <thead>
          <tr><th>Zona</th><th>Vol%</th><th>eFG%</th><th>Liga</th></tr>
        </thead>
        <tbody>
          {rows.map((z) => {
            const edge = z.eFG - z.leagueEFG
            // ataque: verde si mete sobre la media; defensa: verde si permite bajo la media
            const good = defense ? edge <= -6 : edge >= 6
            const bad = defense ? edge >= 6 : edge <= -6
            return (
              <tr key={z.zone}>
                <td>{z.zone}</td>
                <td>{z.sharePct}</td>
                <td className={good ? 'efg-good' : bad ? 'efg-bad' : ''}>{z.eFG}</td>
                <td className="muted">{z.leagueEFG}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="legend">{defense ? 'Verde = lo defiende por debajo de la media de liga.' : 'Verde = mete por encima de la media de liga.'}</div>
    </div>
  )
}

function LeaderRow({ label, items, suffix }) {
  return (
    <div className="leadrow">
      <span className="leadlabel">{label}</span>
      <span className="leaditems">
        {items.map((it, i) => (
          <Link key={it.personId} to={`/player/${it.personId}`} className="leaditem">
            {i + 1}. {it.name} <b>{it.val}</b> {suffix}
          </Link>
        ))}
      </span>
    </div>
  )
}

function Stat({ v, l, hi }) {
  return (
    <div className="stat">
      <div className="v" style={hi ? { color: '#16a34a' } : undefined}>{v}</div>
      <div className="l">{l}</div>
    </div>
  )
}
