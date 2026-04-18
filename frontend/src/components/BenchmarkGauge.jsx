import { gradeFromPercentile } from '../utils/grading'
import { formatDeltaWithContext, ordinal } from '../utils/formatting'

/**
 * Horizontal gauge bar with MLB average marker + player position.
 *
 * - Gray track (full width, 6px tall, rounded)
 * - Gray tick at MLB average position (2px wide, labeled "MLB X.XX")
 * - Colored circle at player position (10px, color = grade color)
 * - Below: delta text + percentile
 *
 * @param {object} props
 * @param {number} props.value - Player's stat value
 * @param {number} props.mlbAvg - MLB league average
 * @param {number} props.min - Gauge minimum
 * @param {number} props.max - Gauge maximum
 * @param {boolean} [props.lowerIsBetter] - Invert direction
 * @param {number} [props.percentile] - Player's percentile rank
 * @param {string} [props.grade] - Grade key (computed from percentile if missing)
 */
export default function BenchmarkGauge({
  value,
  mlbAvg,
  min,
  max,
  lowerIsBetter = false,
  percentile,
  grade,
}) {
  if (value == null || min == null || max == null) return null

  const range = max - min || 1
  const clamp = (v) => Math.max(0, Math.min(100, ((v - min) / range) * 100))

  const playerPos = clamp(value)
  const avgPos = mlbAvg != null ? clamp(mlbAvg) : null

  const gradeInfo = grade
    ? gradeFromPercentile(percentile)
    : gradeFromPercentile(percentile)

  const delta = mlbAvg != null ? value - mlbAvg : null

  return (
    <div className="w-full">
      {/* Gauge track */}
      <div className="relative w-full h-[6px] rounded-full bg-surface-hover mt-1">
        {/* MLB average tick */}
        {avgPos != null && (
          <div
            className="absolute top-[-3px] w-[2px] h-[12px] bg-text-secondary rounded-full"
            style={{ left: `${avgPos}%` }}
          >
            <span
              className="absolute top-[-16px] left-1/2 -translate-x-1/2 text-[9px] text-text-secondary whitespace-nowrap"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              MLB {mlbAvg != null ? (Number.isInteger(mlbAvg) ? mlbAvg : mlbAvg.toFixed(2)) : ''}
            </span>
          </div>
        )}

        {/* Player position dot */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-[10px] h-[10px] rounded-full border-2 border-navy"
          style={{
            left: `calc(${playerPos}% - 5px)`,
            backgroundColor: gradeInfo.color,
            boxShadow: `0 0 6px ${gradeInfo.color}88`,
          }}
        />
      </div>

      {/* Footer: delta + percentile */}
      <div className="flex items-center justify-between mt-2">
        <span
          className="text-[10px] text-text-secondary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {delta != null ? formatDeltaWithContext(delta, lowerIsBetter) : ''}
        </span>
        {percentile != null && (
          <span
            className="text-[10px]"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: gradeInfo.color,
            }}
          >
            {ordinal(percentile)} percentile
          </span>
        )}
      </div>
    </div>
  )
}
