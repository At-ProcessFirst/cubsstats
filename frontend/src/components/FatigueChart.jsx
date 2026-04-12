import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Cell,
} from 'recharts'

/**
 * Within-game velocity by pitch count bucket.
 * Shows how a pitcher's velocity changes as pitch count increases.
 *
 * @param {object} props
 * @param {Array} props.data - Array of { bucket, velo, pitches }
 *   e.g. [{ bucket: "1-15", velo: 95.2, pitches: 15 }, ...]
 * @param {number} [props.baselineVelo] - First-inning / first-bucket velocity for reference
 * @param {string} [props.playerName] - Pitcher name
 */
export default function FatigueChart({ data = [], baselineVelo, playerName }) {
  if (!data.length) {
    return (
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3
          className="text-[11px] uppercase tracking-widest text-text-secondary mb-2"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          FATIGUE CHART {playerName ? `— ${playerName}` : ''}
        </h3>
        <div className="h-[180px] flex items-center justify-center text-text-secondary text-sm">
          No in-game pitch data available
        </div>
      </div>
    )
  }

  // Color bars based on velo drop from baseline
  const getBarColor = (velo) => {
    if (!baselineVelo) return '#60A5FA'
    const drop = baselineVelo - velo
    if (drop <= 0.5) return '#34D399' // Fresh
    if (drop <= 1.0) return '#6EE7B7' // Fine
    if (drop <= 1.5) return '#FBBF24' // Fading
    return '#F87171' // Fatigued
  }

  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4">
      <h3
        className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        FATIGUE CHART {playerName ? `— ${playerName}` : ''}
      </h3>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="bucket"
            tick={{ fontSize: 9, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
            label={{
              value: 'Pitch Count',
              position: 'bottom',
              style: { fontSize: 9, fill: '#8892A8' },
              offset: -2,
            }}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 9, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
            width={35}
            label={{
              value: 'mph',
              angle: -90,
              position: 'insideLeft',
              style: { fontSize: 9, fill: '#8892A8' },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#141B2D',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
            }}
            formatter={(value, name) => [
              `${value.toFixed(1)} mph`,
              name === 'velo' ? 'Avg Velo' : name,
            ]}
          />

          {/* Baseline reference */}
          {baselineVelo != null && (
            <ReferenceLine
              y={baselineVelo}
              stroke="#8892A833"
              strokeDasharray="4 3"
            />
          )}

          <Bar dataKey="velo" radius={[3, 3, 0, 0]} name="Avg Velo">
            {data.map((entry, i) => (
              <Cell key={i} fill={getBarColor(entry.velo)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
