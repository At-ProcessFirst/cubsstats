/**
 * LiveTicker — horizontal info strip showing streak, standings, today's game, starter matchup.
 */
export default function LiveTicker({ liveContext }) {
  if (!liveContext) return null

  const { streak, standings, today } = liveContext

  // Find Cubs position in standings
  const cubsStanding = standings?.find(s => s.abbrev === 'CHC')
  const cubsRank = standings?.findIndex(s => s.abbrev === 'CHC') + 1

  // Format game time to Central Time
  const formatTime = (iso) => {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      return d.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        timeZone: 'America/Chicago',
      }) + ' CT'
    } catch {
      return ''
    }
  }

  const getStarterText = () => {
    if (!today) return null
    const home = today.home_starter?.name || 'TBD'
    const away = today.away_starter?.name || 'TBD'
    if (today.is_home) return `${home} vs ${away}`
    return `${away} vs ${home}`
  }

  const ordinalSuffix = (n) => {
    if (n === 1) return '1st'
    if (n === 2) return '2nd'
    if (n === 3) return '3rd'
    return `${n}th`
  }

  const isFinal = today?.status === 'Final'
  const cubsWon = today?.cubs_score != null && today?.opp_score != null && today.cubs_score > today.opp_score

  // Game display: show score if final, time if scheduled
  const GameInfo = () => {
    if (!today) return <span className="text-[12px] text-text-secondary italic">Off day</span>

    if (isFinal) {
      return (
        <div className="flex items-center gap-2">
          <span
            className="text-[12px] font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: cubsWon ? '#34D399' : '#F87171',
            }}
          >
            Cubs {today.cubs_score}, {today.opponent} {today.opp_score}
          </span>
          <span
            className="text-[9px] font-bold px-1.5 py-0.5 rounded"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: cubsWon ? '#34D399' : '#F87171',
              backgroundColor: cubsWon ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
            }}
          >
            {cubsWon ? 'WIN' : 'LOSS'}
          </span>
        </div>
      )
    }

    return (
      <div className="flex items-center gap-2">
        <span className="text-[12px] text-text-primary font-medium"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {today.is_home ? 'vs' : '@'} {today.opponent}
        </span>
        <span className="text-[11px] text-text-secondary">
          {today.day_night === 'day' ? 'today' : 'tonight'} {formatTime(today.game_time)}
        </span>
        {today.status !== 'Scheduled' && today.status !== 'Pre-Game' && (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-cubs-blue/20 text-accent-blue"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {today.status.toUpperCase()}
          </span>
        )}
      </div>
    )
  }

  const hasStreak = streak && streak.count > 0
  const hasStandings = cubsStanding != null

  return (
    <div className="bg-surface rounded-lg border border-white-8 px-3 md:px-4 py-2.5">
      {/* Desktop: single row */}
      <div className="hidden md:flex items-center gap-4">
        {/* Live pulse + streak */}
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
          </span>
          {hasStreak && (
            <span
              className="text-[11px] font-bold px-1.5 py-0.5 rounded"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: streak.type === 'W' ? '#34D399' : '#F87171',
                backgroundColor: streak.type === 'W' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
              }}
            >
              {streak.type}{streak.count} streak
            </span>
          )}
        </div>

        {hasStandings && (
          <>
            <span className="text-white-8">|</span>
            <span className="text-[12px] text-text-primary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              NL Central: {ordinalSuffix(cubsRank)} ({cubsStanding.wins}-{cubsStanding.losses}{cubsStanding.games_back !== '-' ? `, ${cubsStanding.games_back} GB` : ''})
            </span>
          </>
        )}

        <span className="text-white-8">|</span>

        <GameInfo />

        {/* Starter matchup — only show for non-final games */}
        {today && !isFinal && (
          <>
            <span className="text-white-8">|</span>
            <span className="text-[11px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {getStarterText()}
            </span>
          </>
        )}
      </div>

      {/* Mobile: 2-row grid */}
      <div className="md:hidden grid grid-cols-2 gap-x-3 gap-y-2">
        {/* Row 1: Streak + Standings */}
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
          </span>
          {hasStreak && (
            <span
              className="text-[10px] font-bold px-1 py-0.5 rounded"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: streak.type === 'W' ? '#34D399' : '#F87171',
                backgroundColor: streak.type === 'W' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
              }}
            >
              {streak.type}{streak.count}
            </span>
          )}
        </div>
        {hasStandings ? (
          <span className="text-[10px] text-text-primary text-right"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {ordinalSuffix(cubsRank)} NLC ({cubsStanding.wins}-{cubsStanding.losses})
          </span>
        ) : <span />}

        {/* Row 2: Game result/status */}
        {today ? (
          isFinal ? (
            <span className="text-[10px] font-bold col-span-2"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: cubsWon ? '#34D399' : '#F87171',
              }}>
              {cubsWon ? 'W' : 'L'} — Cubs {today.cubs_score}, {today.opponent} {today.opp_score}
            </span>
          ) : (
            <>
              <span className="text-[10px] text-text-primary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {today.is_home ? 'vs' : '@'} {today.opponent} {today.day_night === 'day' ? 'today' : 'tonight'}
              </span>
              <span className="text-[10px] text-text-secondary text-right truncate"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {getStarterText()}
              </span>
            </>
          )
        ) : (
          <span className="text-[10px] text-text-secondary italic col-span-2">Off day</span>
        )}
      </div>
    </div>
  )
}
