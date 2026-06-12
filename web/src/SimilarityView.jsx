import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useData, HOME_TEAM } from './App.jsx'

// Banda de calidad del match según la distancia, anclada al contexto real de la liga:
//   <= mediana del 1er vecino  -> bueno   (más parecido que el comp típico)
//   <= máx del 1er vecino      -> moderado
//   por encima                 -> flojo   ("el menos distinto", no un gemelo)
function band(dist, ctx) {
  if (dist <= ctx.nnMedian) return { key: 'good', label: 'comp real', color: '#16a34a' }
  if (dist <= ctx.nnMax) return { key: 'mod', label: 'moderado', color: '#d97706' }
  return { key: 'weak', label: 'lejano', color: '#9aa1ad' }
}

export default function SimilarityView() {
  const { similarity, players: allPlayers } = useData()
  const { ctx } = similarity
  const pool = similarity.players

  // jugadores del pool ordenados por nombre para el selector
  const options = useMemo(
    () => Object.values(pool).sort((a, b) => a.name.localeCompare(b.name)),
    [pool],
  )
  const defaultId = (options.find((p) => p.team === HOME_TEAM) || options[0])?.personId
  const [sel, setSel] = useState(defaultId)
  const [mode, setMode] = useState('global') // 'global' | 'byPos'

  const p = pool[sel]
  const list = (mode === 'global' ? p.global : p.byPos).slice(0, 10)
  const best = p.global[0]?.dist

  return (
    <div>
      <div className="home-head">
        <h1>Jugadores parecidos</h1>
        <span className="meta">
          Distancia en {ctx.nMetrics} percentiles · pool {ctx.poolSize} (≥200 min, Clasificatorio)
        </span>
      </div>

      <div className="card full sim-warn">
        <b>Similitud estadística, no estilo de juego.</b> Compara el <b>perfil de producción</b>
        (percentiles vs la liga), no cómo juega cada uno. Es un <b>punto de partida para scouting, no una
        conclusión</b>. En una liga chica el "más parecido" puede estar lejos: por eso cada match muestra
        su <b>distancia</b> — más baja = más parecido. Referencia de la liga: el comp más cercano típico
        está a <b>{ctx.nnMedian}</b> (rango {ctx.nnMin}–{ctx.nnMax}).
      </div>

      <div className="card full">
        <div className="sim-controls">
          <label className="sim-pick">
            Jugador:&nbsp;
            <select value={sel} onChange={(e) => setSel(e.target.value)}>
              {options.map((o) => (
                <option key={o.personId} value={o.personId}>
                  {o.name} · {o.team} · {o.pos}
                </option>
              ))}
            </select>
          </label>
          <div className="sim-toggle">
            <button className={mode === 'global' ? 'on' : ''} onClick={() => setMode('global')}>
              Toda la liga
            </button>
            <button className={mode === 'byPos' ? 'on' : ''} onClick={() => setMode('byPos')}>
              Misma posición
            </button>
          </div>
        </div>

        <div className="sim-subhead">
          {mode === 'byPos' ? (
            <>Comparando dentro de <b>{p.bucketLabel}</b> ({p.bucketN} jugadores).</>
          ) : (
            <>Comparando contra los {ctx.poolSize} del pool.</>
          )}
          {best > ctx.nnMedian && (
            <span className="sim-unique">
              {' '}· El comp más cercano de {p.name} está a {best} (vs mediana {ctx.nnMedian}):
              perfil relativamente <b>único</b>, sin comp fuerte.
            </span>
          )}
        </div>

        <ul className="sim-list">
          {list.map((nb, i) => {
            const b = band(nb.dist, ctx)
            // largo de barra: más cerca = más larga (escala al rango de 1er vecino de la liga)
            const span = Math.max(ctx.nnMax, nb.dist)
            const w = Math.max(6, 100 * (1 - (nb.dist - ctx.nnMin) / (span - ctx.nnMin + 1e-6)))
            const inPool = allPlayers[nb.personId]
            return (
              <li key={nb.personId} className="sim-row">
                <span className="sim-rank">{i + 1}</span>
                <span className="sim-name">
                  {inPool ? (
                    <Link to={`/player/${nb.personId}`} className="tlink">{nb.name}</Link>
                  ) : (
                    nb.name
                  )}
                  <span className="sim-meta">{nb.team} · {nb.pos}</span>
                </span>
                <span className="sim-bar-wrap">
                  <span className="sim-bar" style={{ width: `${w}%`, background: b.color }} />
                </span>
                <span className="sim-dist" style={{ color: b.color }}>
                  {nb.dist.toFixed(1)}
                  <span className="sim-band">{b.label}</span>
                </span>
              </li>
            )
          })}
        </ul>

        <p className="legend">
          <b>Distancia</b> = brecha promedio de percentil por métrica entre los dos jugadores (más baja =
          más parecido). Verde = más parecido que el comp típico de la liga (≤ {ctx.nnMedian});
          ámbar = moderado; gris = lejano (≥ {ctx.nnMax}, "el menos distinto"). La distancia mezcla
          métricas por-36 y por-% del mismo fundamento, así que pesa doble el rebote/pase: leerla como
          orientación, no como número exacto.
        </p>
      </div>
    </div>
  )
}
