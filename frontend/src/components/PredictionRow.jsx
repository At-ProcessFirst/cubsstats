/**
 * Game prediction row with win probability and home advantage factor.
 *
 * @param {object} props
 * @param {string} props.opponent - Opponent team abbreviation
 * @param {string} props.date - Game date string
 * @param {boolean} props.isHome - Whether Cubs are home
 * @param {number} [props.winProbability] - Model win probability (0-1)
 * @param {number} [props.homeAdvantage] - Home advantage factor
 * @param {string} [props.status] - "model_not_trained" or active
 */
export default function PredictionRow({
  opponent,
  date,
  isHome,
  winProbability,
  homeAdvantage,
  status,
}) {
  const isModelReady = status !== 'model_not_trained' && winProbability != null
  const pct = isModelReady ? (winProbability * 100).toFixed(1) : null

  // Color based on win probability
  const getProbColor = (p) => {
    if (p == null) return '#8892A8'
    if (p >= 60) return '#34D399'
    if (p >= 52) return '#6EE7B7'
    if (p >= 48) return '#8892A8'
    if (p >= 40) return '#FBBF24'
    return '#F87171'
  }

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-white-8 last:border-b-0">
      {/* Date */}
      <span
        className="text-[10px] text-text-secondary w-[60px]"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {date}
      </span>

      {/* Matchup */}
      <div className="flex items-center gap-1.5 w-[100px]">
        <span className="text-[10px] text-text-secondary">
          {isHome ? 'vs' : '@'}
        </span>
        <span
          className="text-sm font-semibold text-text-primary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {opponent}
        </span>
      </div>

      {/* Win probability bar */}
      <div className="flex-1 flex items-center gap-2">
        <div className="flex-1 h-[6px] rounded-full bg-surface-hover overflow-hidden">
          {isModelReady && (
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${pct}%`,
                backgroundColor: getProbColor(parseFloat(pct)),
              }}
            />
          )}
        </div>

        {/* Probability display */}
        <span
          className="text-[13px] font-bold w-[55px] text-right"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: isModelReady ? getProbColor(parseFloat(pct)) : '#8892A8',
          }}
        >
          {isModelReady ? `${pct}%` : '—'}
        </span>
      </div>

      {/* Home advantage indicator */}
      {isHome && (
        <span
          className="text-[9px] px-1.5 py-0.5 rounded bg-cubs-blue/20 text-accent-blue"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          HOME
        </span>
      )}
    </div>
  )
}
