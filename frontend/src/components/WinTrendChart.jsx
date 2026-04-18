import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, Area, ComposedChart,
} from 'recharts'

/**
 * Win Trend Chart — multi-line cumulative wins over the season.
 *
 * Lines:
 *  1. Actual cumulative wins (solid blue, dots)
 *  2. ML predicted wins (dashed green)
 *  3. Pythagorean expected wins (dashed gold)
 *  4. .500 pace (light gray dashed)
 *  5. Projected range (shaded blue band after current game)
 *
 * @param {object} props
 * @param {Array} props.data - Array of { game, actual, predicted, pythagorean, pace500, ciLow, ciHigh }
 * @param {string} [props.summary] - Plain English summary below chart
 */
export default function WinTrendChart({ data = [], summary }) {
  if (!data.length) {
    return (
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3
          className="text-sm font-semibold text-text-secondary mb-2"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          WIN TREND
        </h3>
        <div className="h-[250px] flex items-center justify-center text-text-secondary text-sm">
          Season data will appear as games are played
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4">
      <h3
        className="text-sm font-semibold text-text-secondary mb-3"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        WIN TREND
      </h3>

      <div className="h-[220px] md:h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="game"
            tick={{ fontSize: 10, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickLine={false}
            label={{
              value: 'Cumulative Wins',
              angle: -90,
              position: 'insideLeft',
              style: { fontSize: 10, fill: '#8892A8' },
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
            labelStyle={{ color: '#E8ECF4' }}
          />
          <Legend
            wrapperStyle={{ fontSize: 10, fontFamily: "'JetBrains Mono'" }}
          />

          {/* Projected CI band */}
          <Area
            dataKey="ciHigh"
            stroke="none"
            fill="rgba(96,165,250, 0.10)"
            name="Projected range"
          />
          <Area
            dataKey="ciLow"
            stroke="none"
            fill="#0E1629"
          />

          {/* .500 pace */}
          <Line
            dataKey="pace500"
            stroke="#8892A833"
            strokeDasharray="6 4"
            dot={false}
            name=".500 pace"
            strokeWidth={1}
          />

          {/* Pythagorean expected */}
          <Line
            dataKey="pythagorean"
            stroke="#FBBF24"
            strokeDasharray="5 3"
            dot={false}
            name="Pythagorean"
            strokeWidth={1.5}
          />

          {/* ML predicted */}
          <Line
            dataKey="predicted"
            stroke="#34D399"
            strokeDasharray="5 3"
            dot={false}
            name="ML Predicted"
            strokeWidth={1.5}
          />

          {/* Actual wins */}
          <Line
            dataKey="actual"
            stroke="#60A5FA"
            dot={{ r: 2, fill: '#60A5FA' }}
            name="Actual"
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
      </div>

      {/* Summary */}
      {summary && (
        <p className="mt-3 text-[11px] text-text-secondary italic leading-snug">
          {summary}
        </p>
      )}
    </div>
  )
}
