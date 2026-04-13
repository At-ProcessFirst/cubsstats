import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'

/**
 * Per-pitcher velocity trend chart with MLB average line.
 *
 * @param {object} props
 * @param {Array} props.data - Array of { date, velo } (per start or per game)
 * @param {number} [props.mlbAvg] - MLB average fastball velocity
 * @param {string} [props.playerName] - Pitcher name for title
 */
export default function VelocityTrend({ data = [], mlbAvg, playerName }) {
  if (!data.length) {
    return null  // Hide entirely when no Statcast velocity data
  }

  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4">
      <h3
        className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        VELOCITY TREND {playerName ? `— ${playerName}` : ''}
      </h3>

      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 9, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
            width={35}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#141B2D',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
            }}
            formatter={(value) => [`${value.toFixed(1)} mph`, 'Velo']}
          />

          {/* MLB avg reference line */}
          {mlbAvg != null && (
            <ReferenceLine
              y={mlbAvg}
              stroke="#8892A8"
              strokeDasharray="4 3"
              label={{
                value: `MLB ${mlbAvg.toFixed(1)}`,
                position: 'right',
                style: {
                  fontSize: 9,
                  fill: '#8892A8',
                  fontFamily: "'JetBrains Mono'",
                },
              }}
            />
          )}

          <Line
            dataKey="velo"
            stroke="#CC3433"
            dot={{ r: 3, fill: '#CC3433' }}
            strokeWidth={2}
            name="Velocity"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
