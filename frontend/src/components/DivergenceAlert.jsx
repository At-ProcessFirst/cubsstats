import { ordinal } from '../utils/formatting'

const ALERT_COLORS = {
  BREAKOUT: { color: '#34D399', bg: 'rgba(52,211,153, 0.12)' },
  REGRESS: { color: '#F87171', bg: 'rgba(248,113,113, 0.12)' },
  WATCH: { color: '#FBBF24', bg: 'rgba(251,191,36, 0.12)' },
  INJURY: { color: '#F472B6', bg: 'rgba(244,114,182, 0.12)' },
}

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

  // Determine if stat2 is a league average benchmark (not a player stat)
  const isBenchmark = stat2Name?.toLowerCase().includes('league avg') ||
                      stat2Name?.toLowerCase().includes('mlb avg')

  return (
    <div
      className="rounded-lg p-3 border transition-all hover:brightness-110 card-elevated"
      style={{
        backgroundColor: alertInfo.bg,
        borderColor: `${alertInfo.color}33`,
        borderLeft: `3px solid ${alertInfo.color}`,
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

      {/* Stat comparison — player stat prominent, benchmark dimmer */}
      <div className="flex flex-wrap items-center gap-2 md:gap-3 mb-2">
        {/* Player's stat — large and prominent */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-text-secondary">{stat1Name}:</span>
          <span
            className="text-[14px] font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: alertInfo.color,
            }}
          >
            {stat1Value}
          </span>
          {stat1Percentile != null && (
            <span className="text-[9px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              ({ordinal(stat1Percentile)})
            </span>
          )}
        </div>

        {/* Comparison indicator */}
        <span className="text-[10px] text-text-secondary">→</span>

        {/* Benchmark or comparison stat — smaller, clearly secondary */}
        <div className="flex items-center gap-1">
          {isBenchmark ? (
            <>
              <span className="text-[9px] text-text-secondary">MLB avg:</span>
              <span className="text-[11px] text-text-secondary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {stat2Value}
              </span>
            </>
          ) : (
            <>
              <span className="text-[10px] text-text-secondary">{stat2Name}:</span>
              <span className="text-[12px] font-bold text-text-primary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {stat2Value}
              </span>
              {stat2Percentile != null && (
                <span className="text-[9px] text-text-secondary"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  ({ordinal(stat2Percentile)})
                </span>
              )}
            </>
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
