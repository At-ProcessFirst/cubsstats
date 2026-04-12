import GradeBadge from './GradeBadge'
import { ordinal } from '../utils/formatting'

/**
 * Alert badge color mapping.
 */
const ALERT_COLORS = {
  BREAKOUT: { color: '#34D399', bg: 'rgba(52,211,153, 0.12)' },
  REGRESS: { color: '#F87171', bg: 'rgba(248,113,113, 0.12)' },
  WATCH: { color: '#FBBF24', bg: 'rgba(251,191,36, 0.12)' },
  INJURY: { color: '#F472B6', bg: 'rgba(244,114,182, 0.12)' },
}

/**
 * Divergence alert row with percentile context on both stats.
 *
 * Shows: badge, player name, both stat values with percentile ranks,
 * and plain English explanation.
 *
 * @param {object} props
 * @param {string} props.alertType - BREAKOUT, REGRESS, WATCH, INJURY
 * @param {string} props.playerName - Player name
 * @param {string} props.stat1Name - First stat name
 * @param {number|string} props.stat1Value - First stat value
 * @param {number} [props.stat1Percentile] - First stat percentile
 * @param {string} props.stat2Name - Second stat name
 * @param {number|string} props.stat2Value - Second stat value
 * @param {number} [props.stat2Percentile] - Second stat percentile
 * @param {string} props.explanation - Plain English explanation
 */
export default function DivergenceAlert({
  alertType,
  playerName,
  stat1Name,
  stat1Value,
  stat1Percentile,
  stat2Name,
  stat2Value,
  stat2Percentile,
  explanation,
}) {
  const alertInfo = ALERT_COLORS[alertType] || ALERT_COLORS.WATCH

  return (
    <div
      className="rounded-lg p-3 border transition-colors hover:brightness-110"
      style={{
        backgroundColor: alertInfo.bg,
        borderColor: `${alertInfo.color}33`,
      }}
    >
      {/* Header: badge + player name */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className="px-2 py-0.5 rounded text-[9px] font-bold tracking-wider"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: alertInfo.color,
            backgroundColor: `${alertInfo.color}22`,
          }}
        >
          {alertType}
        </span>
        <span className="text-sm font-semibold text-text-primary">
          {playerName}
        </span>
      </div>

      {/* Stat comparison */}
      <div className="flex items-center gap-4 mb-2">
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-text-secondary">
            {stat1Name}:
          </span>
          <span
            className="text-[12px] font-bold text-text-primary"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {stat1Value}
          </span>
          {stat1Percentile != null && (
            <span
              className="text-[9px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              ({ordinal(stat1Percentile)})
            </span>
          )}
        </div>

        <span className="text-[10px] text-text-secondary">vs</span>

        <div className="flex items-center gap-1">
          <span className="text-[10px] text-text-secondary">
            {stat2Name}:
          </span>
          <span
            className="text-[12px] font-bold text-text-primary"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {stat2Value}
          </span>
          {stat2Percentile != null && (
            <span
              className="text-[9px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              ({ordinal(stat2Percentile)})
            </span>
          )}
        </div>
      </div>

      {/* Explanation */}
      {explanation && (
        <p className="text-[11px] text-text-secondary italic leading-snug">
          {explanation}
        </p>
      )}
    </div>
  )
}
