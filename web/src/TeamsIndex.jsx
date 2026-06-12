import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

export default function TeamsIndex() {
  const { teams } = useData()
  const list = Object.values(teams).sort((a, b) => b.ratings.NetRtg - a.ratings.NetRtg)

  return (
    <div>
      <div className="home-head">
        <h1>Equipos · LUB Clasificatorio</h1>
        <span className="meta">12 equipos · ordenados por Net Rating</span>
      </div>
      <div className="teams-grid">
        {list.map((t) => {
          const net = t.ratings.NetRtg
          const isUru = t.code === HOME_TEAM
          return (
            <Link key={t.code} to={`/team/${t.code}`} className={`tcard ${isUru ? 'tcard-uru' : ''}`}>
              <div className="tcard-top">
                <span className="tcard-name">{t.name}</span>
                <span className={`badge sm ${isUru ? 'uru' : 'rival'}`}>{t.code}</span>
              </div>
              <div className="tcard-net" style={{ color: net > 0 ? '#16a34a' : '#dc2626' }}>
                {net > 0 ? '+' : ''}{net} <span className="tcard-netlbl">Net</span>
              </div>
              <div className="tcard-sub">ORtg {t.ratings.ORtg} · DRtg {t.ratings.DRtg} · Pace {t.ratings.Pace}</div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
