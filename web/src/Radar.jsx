// Radar de percentiles hecho a mano en SVG (sin dependencias).
// axes: [{ label, value }] con value en 0..100 (percentil).
export default function Radar({ axes, size = 320, color = '#2563eb' }) {
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 46
  const n = axes.length
  const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2
  const point = (i, frac) => [cx + r * frac * Math.cos(angle(i)), cy + r * frac * Math.sin(angle(i))]

  const rings = [0.25, 0.5, 0.75, 1]
  const valuePts = axes.map((a, i) => point(i, Math.max(0, Math.min(100, a.value)) / 100))
  const poly = valuePts.map((p) => p.join(',')).join(' ')

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* anillos */}
      {rings.map((ring, k) => (
        <polygon
          key={k}
          points={axes.map((_, i) => point(i, ring).join(',')).join(' ')}
          fill="none"
          stroke="#e5e8ef"
          strokeWidth="1"
        />
      ))}
      {/* ejes + etiquetas */}
      {axes.map((a, i) => {
        const [ex, ey] = point(i, 1)
        const [lx, ly] = point(i, 1.18)
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={ex} y2={ey} stroke="#e5e8ef" strokeWidth="1" />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="#6b7280">
              {a.label}
            </text>
            <text x={lx} y={ly + 13} textAnchor="middle" dominantBaseline="middle" fontSize="11" fontWeight="700" fill={color}>
              {Number.isInteger(a.value) ? a.value : a.value.toFixed(1)}
            </text>
          </g>
        )
      })}
      {/* polígono de valores */}
      <polygon points={poly} fill={color} fillOpacity="0.18" stroke={color} strokeWidth="2" />
      {valuePts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="3" fill={color} />
      ))}
    </svg>
  )
}
