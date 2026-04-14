/**
 * Game prediction row with Cubs win probability and favorability indicator.
 */
export default function PredictionRow({
  opponent,
  date,
  isHome,
  winProbability,
  status,
}) {
  const isModelReady = status !== 'model_not_trained' && winProbability != null
  const pct = isModelReady ? (winProbability * 100).toFixed(0) : null
  const pctNum = pct ? parseFloat(pct) : null

  const getProbColor = (p) => {
    if (p == null) return '#8892A8'
    if (p >= 58) return '#34D399'
    if (p >= 52) return '#6EE7B7'
    if (p >= 48) return '#8892A8'
    if (p >= 42) return '#FBBF24'
    return '#F87171'
  }

  const getFavorLabel = (p) => {
    if (p == null) return null
    if (p >= 55) return { text: 'FAVORED', color: '#34D399' }
    if (p >= 45) return { text: 'TOSS-UP', color: '#8892A8' }
    return { text: 'UNDERDOG', color: '#FBBF24' }
  }

  const favor = getFavorLabel(pctNum)

  return (
    <div className="flex items-center gap-2 md:gap-3 py-2.5 border-b border-white-8 last:border-b-0">
      {/* Date */}
      <span
        className="text-[10px] text-text-secondary w-[55px] md:w-[60px]"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {date}
      </span>

      {/* Matchup */}
      <div className="flex items-center gap-1 w-[75px] md:w-[90px]">
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
                backgroundColor: getProbColor(pctNum),
              }}
            />
          )}
        </div>

        {/* Cubs win probability — explicitly labeled */}
        <span
          className="text-[12px] font-bold w-[65px] text-right"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: isModelReady ? getProbColor(pctNum) : '#8892A8',
          }}
        >
          {isModelReady ? `Cubs ${pct}%` : '—'}
        </span>
      </div>

      {/* Favorability indicator */}
      {favor && (
        <span
          className="text-[7px] md:text-[8px] px-1.5 py-0.5 rounded font-bold tracking-wider w-[62px] text-center"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: favor.color,
            backgroundColor: `${favor.color}18`,
          }}
        >
          {favor.text}
        </span>
      )}

      {/* Home indicator */}
      {isHome && (
        <span
          className="text-[8px] px-1.5 py-0.5 rounded bg-cubs-blue/20 text-accent-blue"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          HOME
        </span>
      )}
    </div>
  )
}
