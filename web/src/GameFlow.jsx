import { useState } from 'react'
import { useData, HOME_TEAM } from './App.jsx'

const BLUE = '#2563eb'
const RED = '#dc2626'

// Mapea cada muestra a su minuto de juego y arma los puntos {x:min, v:dif}.
function buildPts(m) {
  const { bounds, periods, lead } = m
  const n = lead.length
  const ends = bounds.map((b, p) => (p + 1 < bounds.length ? bounds[p + 1] - 1 : n - 1))
  const cum = []
  let t = 0
  for (const [, len] of periods) { cum.push(t); t += len }
  const pts = lead.map((v, i) => {
    let p = 0
    while (p + 1 < bounds.length && i >= bounds[p + 1]) p++
    const start = bounds[p], end = ends[p], len = periods[p][1]
    const frac = end > start ? (i - start) / (end - start) : 0
    return { x: cum[p] + frac * len, v }
  })
  return { pts, total: t, cum }
}

// Diferencia máxima a favor de cada lado + cambios de mando, en perspectiva ya orientada.
function summarize(lead) {
  let top = 0, bot = 0, changes = 0, prev = 0
  for (const v of lead) {
    if (v > top) top = v
    if (v < bot) bot = v
    const s = Math.sign(v)
    if (s !== 0 && prev !== 0 && s !== prev) changes++
    if (s !== 0) prev = s
  }
  return { top, bot: -bot, changes }
}

function Chart({ m }) {
  // Orientar: el equipo foco (Urunday) arriba/positivo. Si es tm2, se invierte el signo.
  const flip = m.t2 === HOME_TEAM
  const lead = flip ? m.lead.map((v) => -v) : m.lead
  const top = flip ? { code: m.t2, name: m.n2, score: m.s2 } : { code: m.t1, name: m.n1, score: m.s1 }
  const bot = flip ? { code: m.t1, name: m.n1, score: m.s1 } : { code: m.t2, name: m.n2, score: m.s2 }
  const topColor = top.code === HOME_TEAM ? BLUE : RED
  const botColor = bot.code === HOME_TEAM ? BLUE : RED

  const oriented = { ...m, lead }
  const { pts, total, cum } = buildPts(oriented)
  const { top: maxTop, bot: maxBot, changes } = summarize(lead)

  // lienzo
  const W = 760, H = 360
  const mL = 44, mR = 16, mT = 24, mB = 34
  const plotW = W - mL - mR, plotH = H - mT - mB
  const midY = mT + plotH / 2
  const yMax = Math.max(6, maxTop, maxBot) * 1.12
  const X = (min) => mL + (min / total) * plotW
  const Y = (v) => midY - (v / yMax) * (plotH / 2)

  const poly = pts.map((p) => `${X(p.x).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ')
  const area = `M ${X(pts[0].x).toFixed(1)} ${midY} L ` +
    pts.map((p) => `${X(p.x).toFixed(1)} ${Y(p.v).toFixed(1)}`).join(' L ') +
    ` L ${X(pts[pts.length - 1].x).toFixed(1)} ${midY} Z`

  // ticks del eje Y (diferencia) cada 5 o 10 según rango
  const step = yMax > 25 ? 10 : 5
  const yticks = []
  for (let v = step; v <= yMax; v += step) yticks.push(v)

  const last = pts[pts.length - 1]
  const finalDiff = lead[lead.length - 1]

  return (
    <div className="card full">
      <div className="gf-scoreline">
        <span className="gf-team" style={{ color: topColor }}>
          <b>{top.name}</b> {top.score}
        </span>
        <span className="gf-sep">vs</span>
        <span className="gf-team" style={{ color: botColor }}>
          {bot.score} <b>{bot.name}</b>
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
        <defs>
          <clipPath id="gf-up"><rect x="0" y="0" width={W} height={midY} /></clipPath>
          <clipPath id="gf-dn"><rect x="0" y={midY} width={W} height={H - midY} /></clipPath>
        </defs>

        {/* relleno bicolor: arriba = equipo de arriba, abajo = el otro */}
        <path d={area} fill={topColor} opacity="0.14" clipPath="url(#gf-up)" />
        <path d={area} fill={botColor} opacity="0.14" clipPath="url(#gf-dn)" />

        {/* grilla horizontal + etiquetas de diferencia */}
        {yticks.map((v) => (
          <g key={v}>
            <line x1={mL} y1={Y(v)} x2={W - mR} y2={Y(v)} stroke="#eef1f6" />
            <line x1={mL} y1={Y(-v)} x2={W - mR} y2={Y(-v)} stroke="#eef1f6" />
            <text x={mL - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="#9aa1ad">+{v}</text>
            <text x={mL - 6} y={Y(-v) + 3} textAnchor="end" fontSize="10" fill="#9aa1ad">+{v}</text>
          </g>
        ))}

        {/* línea cero (empate) */}
        <line x1={mL} y1={midY} x2={W - mR} y2={midY} stroke="#64748b" strokeWidth="1.2" />
        <text x={mL - 6} y={midY + 3} textAnchor="end" fontSize="10" fill="#64748b">0</text>

        {/* divisores de período + etiquetas */}
        {cum.map((c, i) => (
          <line key={i} x1={X(c)} y1={mT} x2={X(c)} y2={H - mB}
                stroke="#dfe3ec" strokeWidth={i === 0 ? 0 : 1} />
        ))}
        <line x1={X(total)} y1={mT} x2={X(total)} y2={H - mB} stroke="#dfe3ec" />
        {m.periods.map(([lab], i) => {
          const a = cum[i], b = i + 1 < cum.length ? cum[i + 1] : total
          return (
            <text key={i} x={X((a + b) / 2)} y={H - mB + 16} textAnchor="middle"
                  fontSize="11" fill="#6b7280" fontWeight="600">{lab}</text>
          )
        })}

        {/* curva de la diferencia */}
        <polyline points={poly} fill="none" stroke="#1f2937" strokeWidth="2"
                  strokeLinejoin="round" strokeLinecap="round" />

        {/* punto final + diferencia de cierre (= boxscore) */}
        <circle cx={X(last.x)} cy={Y(last.v)} r="4" fill={finalDiff >= 0 ? topColor : botColor} />
        <text x={X(last.x) - 6} y={Y(last.v) + (finalDiff >= 0 ? -8 : 16)} textAnchor="end"
              fontSize="12" fontWeight="700" fill={finalDiff >= 0 ? topColor : botColor}>
          {finalDiff >= 0 ? '+' : ''}{finalDiff}
        </text>
      </svg>

      <div className="gf-readout">
        <span>Máx. <b style={{ color: topColor }}>{top.code}</b> +{maxTop}</span>
        <span>Máx. <b style={{ color: botColor }}>{bot.code}</b> +{maxBot}</span>
        <span>Cambios de mando: <b>{changes}</b></span>
        <span className="muted">Cierre +{Math.abs(finalDiff)} = marcador final {top.score}-{bot.score}</span>
      </div>
    </div>
  )
}

export default function GameFlow() {
  const { gameflow } = useData()
  // Partidos de Urunday primero (el resto de la liga queda accesible abajo).
  const uru = gameflow.filter((m) => m.t1 === HOME_TEAM || m.t2 === HOME_TEAM)
  const [sel, setSel] = useState(uru[0]?.matchId)
  const match = gameflow.find((m) => m.matchId === sel)

  const label = (m) => {
    const home = m.t1 === HOME_TEAM
    const opp = home ? { n: m.n2, s: m.s2 } : { n: m.n1, s: m.s1 }
    const us = home ? m.s1 : m.s2
    const won = us > opp.s
    return { opp: opp.n, res: `${us}-${opp.s}`, won }
  }

  return (
    <div>
      <div className="home-head">
        <h1>Análisis de Partido</h1>
        <span className="meta">Flujo del marcador · diferencia de puntos minuto a minuto</span>
      </div>

      <div className="card full" style={{ marginBottom: 16 }}>
        <h2>Partidos de Urunday ({uru.length})</h2>
        <div className="gf-picker">
          {uru.map((m) => {
            const l = label(m)
            return (
              <button key={m.matchId}
                      className={`gf-game ${m.matchId === sel ? 'on' : ''} ${l.won ? 'win' : 'loss'}`}
                      onClick={() => setSel(m.matchId)}>
                <span className="gf-vs">vs {l.opp}</span>
                <span className="gf-res">{l.won ? 'G' : 'P'} {l.res}</span>
              </button>
            )
          })}
        </div>
      </div>

      {match && <Chart m={match} />}

      <p className="legend">
        La curva es la <b>diferencia de puntos</b> a lo largo del partido (muestreada cada ~10s desde el
        feed oficial FIBA LiveStats). Por encima de la línea 0 manda <b>Urunday</b>; por debajo, el rival.
        Las divisiones verticales son los cuartos. El número del final es el cierre de la curva y
        <b> coincide exacto con el marcador del boxscore</b> (validado en los 131 partidos del Clasificatorio).
      </p>
    </div>
  )
}
