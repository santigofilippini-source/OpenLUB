import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

const ZONE_ORDER = ['restringida', 'pintura', 'media', '3 esquina izq', '3 ala izq',
  '3 frente', '3 ala der', '3 esquina der']

// FGA mínimo por defecto según el volumen típico de cada zona (las esquinas tienen pocos intentos).
const MIN_FGA_OPTS = [10, 20, 30, 50]
const TOP_N = 8

export default function ZoneLeaders() {
  const { players } = useData()
  const [minFGA, setMinFGA] = useState(20)

  // {zone: [{player, FGA, eFG}]}
  const byZone = {}
  for (const z of ZONE_ORDER) byZone[z] = []
  for (const p of Object.values(players)) {
    for (const zr of p.zones || []) {
      if (!byZone[zr.zone]) continue
      if (zr.FGA >= minFGA) byZone[zr.zone].push({ p, FGA: zr.FGA, eFG: zr.eFG })
    }
  }
  for (const z of ZONE_ORDER) byZone[z].sort((a, b) => b.eFG - a.eFG)

  return (
    <div>
      <div className="home-head">
        <h1>Líderes por zona · eFG%</h1>
        <span className="meta">LUB Clasificatorio · mejores tiradores por sector de cancha</span>
      </div>

      <div className="zlctrl">
        <span>FGA mínimo:</span>
        {MIN_FGA_OPTS.map((n) => (
          <button
            key={n}
            className={`chip ${minFGA === n ? 'chip-on' : ''}`}
            onClick={() => setMinFGA(n)}
          >
            ≥ {n}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 8, fontSize: 13 }}>
          el FGA va al lado de cada % — pocos intentos no es conclusión
        </span>
      </div>

      <div className="zlgrid">
        {ZONE_ORDER.map((z) => {
          const list = byZone[z].slice(0, TOP_N)
          return (
            <div key={z} className="card zlcard">
              <h2>{z}</h2>
              {list.length === 0 ? (
                <p className="muted" style={{ fontSize: 13, margin: 0 }}>
                  Nadie llega a {minFGA} intentos en esta zona.
                </p>
              ) : (
                <table className="zones">
                  <thead>
                    <tr>
                      <th>Jugador</th>
                      <th>eFG%</th>
                      <th>FGA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map(({ p, FGA, eFG }, i) => {
                      const isUru = p.team === HOME_TEAM
                      return (
                        <tr key={p.personId} className={isUru ? 'row-uru' : ''}>
                          <td style={{ textAlign: 'left' }}>
                            <span className="zlrank">{i + 1}.</span>
                            <Link to={`/player/${p.personId}`} className="tlink">{p.name}</Link>
                            <span className="pteam">{p.team}</span>
                          </td>
                          <td className="efg-good">{eFG.toFixed(1)}</td>
                          <td className="fga">{FGA}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )
        })}
      </div>

      <p className="legend">
        eFG% = field goal % ajustado por el valor extra del triple. El ranking exige un piso de intentos
        (FGA) para no premiar a quien tiró 3 veces y embocó. El FGA real va al lado de cada porcentaje.
        Urunday resaltado en azul.
      </p>
    </div>
  )
}
