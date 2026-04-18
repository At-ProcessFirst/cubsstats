import { gradeFromPercentile } from '../utils/grading'
import { ordinal, formatStat } from '../utils/formatting'

/**
 * Horizontal percentile ranking bar.
 * Shows stat label, value, and a colored bar representing percentile rank (0-100).
 *
 * @param {object} props
 * @param {string} props.label - Stat label
 * @param {number|string} props.value - Display value
 * @param {number} props.percentile - Percentile rank (1-99)
 * @param {string} [props.statName] - Stat key for formatting
 */
export default function PercentileBar({ label, value, percentile, statName }) {
  const gradeInfo = gradeFromPercentile(percentile)
  const pctWidth = Math.max(2, Math.min(100, percentile || 0))

  return (
    <div className="flex items-center gap-3 py-1">
      {/* Label */}
      <span
        className="text-[10px] text-text-secondary w-[80px] text-right truncate"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {label}
      </span>

      {/* Value */}
      <span
        className="text-[11px] font-semibold w-[55px] text-right"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          color: gradeInfo.color,
        }}
      >
        {value != null ? (statName ? formatStat(value, statName) : value) : '—'}
      </span>

      {/* Bar */}
      <div className="flex-1 h-[5px] rounded-full bg-surface-hover overflow-hidden relative">
        {/* 50th percentile marker */}
        <div className="absolute top-0 left-1/2 w-px h-full bg-text-secondary/30" />
        <div
          className="h-full rounded-full animate-bar-fill"
          style={{
            width: `${pctWidth}%`,
            background: `linear-gradient(90deg, ${gradeInfo.color}, ${gradeInfo.color}66)`,
          }}
        />
      </div>

      {/* Percentile label */}
      <span
        className="text-[9px] w-[32px] text-right"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          color: gradeInfo.color,
        }}
      >
        {percentile != null ? `${ordinal(percentile)}` : '—'}
      </span>
    </div>
  )
}
