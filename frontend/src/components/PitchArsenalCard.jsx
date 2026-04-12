import { formatDelta } from '../utils/formatting'

/**
 * Pitch-type benchmarked card.
 *
 * - Colored dot + pitch name + role description
 * - 4-column mini-stat grid: Velo (vs avg), Usage%, Whiff% (vs avg), Movement (vs avg)
 * - Each mini-stat shows value, MLB avg, and delta with color
 * - Plain English one-liner
 *
 * @param {object} props
 * @param {string} props.pitchType - Pitch type code (e.g. "FF")
 * @param {string} props.pitchName - Display name (e.g. "4-Seam Fastball")
 * @param {string} props.color - Dot color hex
 * @param {string} props.role - Role description (e.g. "Primary fastball")
 * @param {Array} props.stats - Array of { label, value, mlbAvg, delta, unit }
 * @param {string} [props.explanation] - Plain English one-liner
 */
export default function PitchArsenalCard({
  pitchType,
  pitchName,
  color,
  role,
  stats = [],
  explanation,
}) {
  return (
    <div className="bg-surface rounded-lg border border-white-8 p-3 hover:bg-surface-hover transition-colors">
      {/* Header: dot + name + role */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-3 h-3 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <span
          className="text-sm font-semibold text-text-primary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {pitchName || pitchType}
        </span>
        {role && (
          <span className="text-[10px] text-text-secondary ml-auto">
            {role}
          </span>
        )}
      </div>

      {/* 4-column mini-stat grid */}
      <div className="grid grid-cols-4 gap-2">
        {stats.map((s, i) => {
          const deltaVal = s.delta != null ? s.delta : (s.mlbAvg != null && s.value != null ? s.value - s.mlbAvg : null)
          const deltaColor = deltaVal != null
            ? deltaVal > 0 ? '#34D399' : deltaVal < 0 ? '#F87171' : '#8892A8'
            : '#8892A8'

          return (
            <div key={i} className="flex flex-col gap-0.5">
              <span
                className="text-[8px] uppercase tracking-wide text-text-secondary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {s.label}
              </span>
              <span
                className="text-[13px] font-bold text-text-primary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {s.value != null ? s.value : '—'}
                {s.unit || ''}
              </span>
              <span
                className="text-[9px] text-text-secondary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                avg {s.mlbAvg != null ? s.mlbAvg : '—'}
              </span>
              {deltaVal != null && (
                <span
                  className="text-[9px] font-semibold"
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    color: deltaColor,
                  }}
                >
                  {formatDelta(deltaVal, 1)}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Plain English */}
      {explanation && (
        <p className="mt-2 text-[10px] text-accent-blue italic leading-tight">
          {explanation}
        </p>
      )}
    </div>
  )
}
