import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

export default function Home() {
  const { players, teams } = useData()
  const [q, setQ] = useState('')

  const all = useMemo(() => Object.values(players), [players])
  const results = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return []
    return all
      .filter((p) => p.name.toLowerCase().includes(s) || p.teamName.toLowerCase().includes(s))
      .sort((a, b) => b.basic.PTS - a.basic.PTS)
      .slice(0, 12)
  }, [q, all])

  const home = teams[HOME_TEAM]
  const roster = [...home.roster].sort((a, b) => b.ppg - a.ppg)

  return (
    <div>
      {/* Buscador global de toda la liga (scouting de rivales) */}
      <div className="card searchcard">
        <h2>Buscar jugador · toda la liga</h2>
        <input
          className="search"
          placeholder="Nombre de jugador o equipo… (p.ej. Vescovi, Peñarol)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        {results.length > 0 && (
          <div className="results">
            {results.map((p) => (
              <Link key={p.personId} to={`/player/${p.personId}`} className="result">
                <span className="rname">{p.name}</span>
                <span className={`badge sm ${p.team === HOME_TEAM ? 'uru' : 'rival'}`}>{p.team}</span>
                <span className="rmeta">{p.basic.PTS} pts · {Math.round(p.MIN)}′</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Home = mi equipo */}
      <div className="home-head">
        <h1>{home.name}</h1>
        <Link to={`/team/${HOME_TEAM}`} className="btn">Ver perfil de equipo →</Link>
      </div>

      <div className="roster-grid">
        {roster.map((p) => (
          <Link key={p.personId} to={`/player/${p.personId}`} className="rcard">
            <div className="rcard-top">
              <span className="rcard-name">{p.name}</span>
              <span className="rcard-pos">{p.pos}</span>
            </div>
            <div className="rcard-line">
              <b>{p.ppg}</b> pts/pj · {p.GP} PJ · {p.MIN}′
              {!p.inPool && <span className="tag-low"> muestra &lt;200′</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
