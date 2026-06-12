// Carta de tiro dibujada nativamente desde coords {x,y,made} en convención de render (cy=100-y).
// Media cancha FIBA en metros (aro a la IZQUIERDA, según el golden test de Moller).
// x almacenado 0..50 (largo, *0.28 = m 0..14) ; y almacenado 0..100 (ancho, *0.15 = m 0..15).
const KX = 0.28, KY = 0.15
const RIM = { x: 1.575, y: 7.5 } // aro en metros

// línea de 3 (6.75m), corner a 0.9m de la banda (y=0.9 y y=14.1)
const R3 = 6.75
const cornerY1 = 0.9, cornerY2 = 14.1
const cornerX = RIM.x + Math.sqrt(R3 * R3 - (RIM.y - cornerY1) ** 2) // ~2.99

export default function ShotChart({ shots }) {
  const line = '#94a3b8'
  const sw = 0.06
  return (
    <svg viewBox="-0.3 -0.3 14.6 15.6" width="100%" preserveAspectRatio="xMidYMid meet"
         style={{ background: '#f8fafc', borderRadius: 8, display: 'block' }}>
      <g fill="none" stroke={line} strokeWidth={sw}>
        {/* contorno media cancha */}
        <rect x="0" y="0" width="14" height="15" />
        {/* pintura (llave) */}
        <rect x="0" y={RIM.y - 2.45} width="5.8" height="4.9" />
        {/* línea y círculo de tiro libre */}
        <circle cx="5.8" cy={RIM.y} r="1.8" />
        {/* tablero + aro */}
        <line x1="1.2" y1={RIM.y - 0.9} x2="1.2" y2={RIM.y + 0.9} stroke="#475569" strokeWidth="0.08" />
        <circle cx={RIM.x} cy={RIM.y} r="0.225" stroke="#475569" strokeWidth="0.07" />
        {/* zona restringida (semicírculo 1.25m) */}
        <path d={`M ${RIM.x} ${RIM.y - 1.25} A 1.25 1.25 0 0 1 ${RIM.x} ${RIM.y + 1.25}`} />
        {/* línea de 3: esquinas rectas + arco */}
        <line x1="0" y1={cornerY1} x2={cornerX} y2={cornerY1} />
        <line x1="0" y1={cornerY2} x2={cornerX} y2={cornerY2} />
        <path d={`M ${cornerX} ${cornerY1} A ${R3} ${R3} 0 0 1 ${cornerX} ${cornerY2}`} />
      </g>
      {/* tiros */}
      {shots.map((s, i) => {
        const cx = s.x * KX, cy = s.y * KY
        return s.made ? (
          <circle key={i} cx={cx} cy={cy} r="0.26" fill="#16a34a" fillOpacity="0.82" />
        ) : (
          <circle key={i} cx={cx} cy={cy} r="0.24" fill="none" stroke="#dc2626" strokeWidth="0.09" opacity="0.78" />
        )
      })}
    </svg>
  )
}
