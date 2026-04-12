import GradeBadge from './GradeBadge'
import BenchmarkGauge from './BenchmarkGauge'
import { gradeFromPercentile } from '../utils/grading'
import { formatStat, formatDelta, ordinal } from '../utils/formatting'

/**
 * Dashboard stat card with benchmark, grade, plain English explanation.
 *
 * Layout:
 *  - Stat label (uppercase monospace, 9px, dim)
 *  - Plain English explanation (italic, blue accent, 10px)
 *  - Value (20-22px bold monospace, grade-colored) + GradeBadge inline
 *  - Subtitle with MLB avg reference
 *  - BenchmarkGauge
 *  - Delta + percentile footer
 */
export default function MetricCard({
  label,
  plainEnglish,
  value,
  mlbAvg,
  percentile,
  grade,
  subtitle,
  min,
  max,
  lowerIsBetter = false,
  statName,
}) {
  const gradeInfo = gradeFromPercentile(percentile)
  const delta = mlbAvg != null && value != null ? value - mlbAvg : null

  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4 flex flex-col gap-2 hover:bg-surface-hover transition-colors">
      {/* Stat label */}
      <span
        className="text-[9px] uppercase tracking-widest text-text-secondary"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {label}
      </span>

      {/* Plain English */}
      {plainEnglish && (
        <span className="text-[10px] italic text-accent-blue leading-tight">
          {plainEnglish}
        </span>
      )}

      {/* Value + Badge */}
      <div className="flex items-center gap-2">
        <span
          className="text-[22px] font-bold leading-none"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: gradeInfo.color,
          }}
        >
          {formatStat(value, statName)}
        </span>
        <GradeBadge grade={grade || gradeInfo.label} />
      </div>

      {/* Subtitle with MLB avg */}
      {subtitle ? (
        <span
          className="text-[10px] text-text-secondary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {subtitle}
        </span>
      ) : mlbAvg != null ? (
        <span
          className="text-[10px] text-text-secondary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          MLB avg: {formatStat(mlbAvg, statName)}
        </span>
      ) : null}

      {/* Gauge */}
      {min != null && max != null && (
        <BenchmarkGauge
          value={value}
          mlbAvg={mlbAvg}
          min={min}
          max={max}
          lowerIsBetter={lowerIsBetter}
          percentile={percentile}
          grade={grade}
        />
      )}

      {/* Delta + percentile footer (when no gauge) */}
      {(min == null || max == null) && percentile != null && (
        <div className="flex items-center justify-between mt-1">
          <span
            className="text-[10px] text-text-secondary"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {delta != null ? formatDelta(delta) : ''}
          </span>
          <span
            className="text-[10px]"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: gradeInfo.color,
            }}
          >
            {ordinal(percentile)} pctile
          </span>
        </div>
      )}
    </div>
  )
}
