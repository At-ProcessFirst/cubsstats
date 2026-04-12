import { gradeFromPercentile } from '../utils/grading'
import { ordinal } from '../utils/formatting'

/**
 * Player row with stat, percentile, bar, and explanation.
 *
 * Layout:
 *  - Player name | stat value + tiny percentile | comparison value + tiny percentile | progress bar
 *  - Below: plain English one-liner explaining gap meaning
 */
export default function PlayerStatRow({
  name,
  stat1,
  stat1Pctile,
  stat2,
  stat2Pctile,
  barFill,
  barColor,
  explanation,
}) {
  const grade1 = gradeFromPercentile(stat1Pctile)
  const grade2 = stat2Pctile != null ? gradeFromPercentile(stat2Pctile) : null

  return (
    <div className="py-2 border-b border-white-8 last:border-b-0">
      {/* Main row */}
      <div className="flex items-center gap-3">
        {/* Player name */}
        <span className="text-sm text-text-primary font-medium w-[140px] truncate">
          {name}
        </span>

        {/* Stat 1 */}
        <div className="flex items-center gap-1 w-[90px]">
          <span
            className="text-sm font-semibold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: grade1.color,
            }}
          >
            {stat1}
          </span>
          {stat1Pctile != null && (
            <span
              className="text-[8px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {ordinal(stat1Pctile)}
            </span>
          )}
        </div>

        {/* Stat 2 (comparison) */}
        {stat2 != null && (
          <div className="flex items-center gap-1 w-[90px]">
            <span
              className="text-sm font-semibold"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: grade2 ? grade2.color : '#8892A8',
              }}
            >
              {stat2}
            </span>
            {stat2Pctile != null && (
              <span
                className="text-[8px] text-text-secondary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {ordinal(stat2Pctile)}
              </span>
            )}
          </div>
        )}

        {/* Progress bar */}
        <div className="flex-1 h-[6px] rounded-full bg-surface-hover overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${Math.max(2, Math.min(100, barFill || 0))}%`,
              backgroundColor: barColor || grade1.color,
            }}
          />
        </div>
      </div>

      {/* Explanation */}
      {explanation && (
        <p className="mt-1 text-[10px] text-text-secondary italic pl-[140px]">
          {explanation}
        </p>
      )}
    </div>
  )
}
