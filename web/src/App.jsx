import { useEffect, useState, createContext, useContext } from 'react'
import { HashRouter, Routes, Route, Link, Outlet, useParams } from 'react-router-dom'
import Home from './Home.jsx'
import PlayerProfile from './PlayerProfile.jsx'
import TeamProfile from './TeamProfile.jsx'
import TeamsIndex from './TeamsIndex.jsx'
import TeamStats from './TeamStats.jsx'
import PlayerStats from './PlayerStats.jsx'
import ZoneLeaders from './ZoneLeaders.jsx'
import HeadToHead from './HeadToHead.jsx'

const DataContext = createContext(null)
export const useData = () => useContext(DataContext)
export const HOME_TEAM = 'UUN'

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      fetch('/data/players.json').then((r) => r.json()),
      fetch('/data/teams.json').then((r) => r.json()),
      fetch('/data/results.json').then((r) => r.json()),
    ])
      .then(([players, teams, results]) => setData({ players, teams, results }))
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="wrap">Error cargando datos: {error}</div>
  if (!data) return <div className="wrap">Cargando…</div>

  return (
    <DataContext.Provider value={data}>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/teams" element={<TeamsIndex />} />
            <Route path="/stats/teams" element={<TeamStats />} />
            <Route path="/stats/players" element={<PlayerStats />} />
            <Route path="/stats/zones" element={<ZoneLeaders />} />
            <Route path="/stats/h2h" element={<HeadToHead />} />
            <Route path="/player/:id" element={<PlayerRoute />} />
            <Route path="/team/:code" element={<TeamRoute />} />
          </Route>
        </Routes>
      </HashRouter>
    </DataContext.Provider>
  )
}

function Layout() {
  return (
    <>
      <div className="wrap">
        <div className="topbar">
          <Link to="/" className="logo">URUNDAY</Link>
          <span className="sub">Analítica interna · LUB 25/26 · Clasificatorio</span>
          <nav className="topnav">
            <Link to="/">Inicio</Link>
            <Link to="/teams">Equipos</Link>
            <Link to="/stats/teams">Four Factors</Link>
            <Link to="/stats/players">Jugadores</Link>
            <Link to="/stats/zones">Zonas</Link>
            <Link to="/stats/h2h">Cara a Cara</Link>
          </nav>
        </div>
        <Outlet />
      </div>
    </>
  )
}

function PlayerRoute() {
  const { players } = useData()
  const { id } = useParams()
  const player = players[id]
  if (!player) return <div>Jugador no encontrado.</div>
  return <PlayerProfile player={player} />
}

function TeamRoute() {
  const { teams, players } = useData()
  const { code } = useParams()
  const team = teams[code]
  if (!team) return <div>Equipo no encontrado.</div>
  return <TeamProfile team={team} players={players} />
}
