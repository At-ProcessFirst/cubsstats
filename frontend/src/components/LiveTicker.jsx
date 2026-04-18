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

  // Starter matchup text
  const getStarterText = () => {
    if (!today) return null
    const home = today.home_starter?.name || 'TBD'
    const away = today.away_starter?.name || 'TBD'
    // Show Cubs starter first
    if (today.is_home) return `${home} vs ${away}`
    return `${away} vs ${home}`
  }

  const ordinalSuffix = (n) => {
    if (n === 1) return '1st'
    if (n === 2) return '2nd'
    if (n === 3) return '3rd'
    return `${n}th`
  }

  return (
    <div className="bg-surface rounded-lg border border-white-8 px-3 md:px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {/* Streak */}
      {streak && streak.count > 0 && (
        <div className="flex items-center gap-1.5">
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: streak.type === 'W' ? '#34D399' : '#F87171',
              backgroundColor: streak.type === 'W' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
            }}
          >
            {streak.type}{streak.count}
          </span>
          <span className="text-[10px] text-text-secondary">streak</span>
        </div>
      )}

      {/* Divider */}
      {streak?.count > 0 && <span className="text-white-8 hidden md:inline">|</span>}

      {/* Standings position */}
      {cubsStanding && (
        <span
          className="text-[11px] text-text-primary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          NL Central: {ordinalSuffix(cubsRank)} ({cubsStanding.wins}-{cubsStanding.losses}{cubsStanding.games_back !== '-' ? `, ${cubsStanding.games_back} GB` : ''})
        </span>
      )}

      <span className="text-white-8 hidden md:inline">|</span>

      {/* Today's game */}
      {today ? (
        <div className="flex items-center gap-1.5">
          <span
            className="text-[11px] text-text-primary"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {today.is_home ? 'vs' : '@'} {today.opponent}
          </span>
          <span className="text-[10px] text-text-secondary">
            {today.day_night === 'day' ? 'today' : 'tonight'} {formatTime(today.game_time)}
          </span>
          {today.status !== 'Scheduled' && today.status !== 'Pre-Game' && (
            <span
              className="text-[8px] font-bold px-1 py-0.5 rounded bg-cubs-blue/20 text-accent-blue"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {today.status.toUpperCase()}
            </span>
          )}
        </div>
      ) : (
        <span className="text-[11px] text-text-secondary italic">Off day</span>
      )}

      {/* Starter matchup */}
      {today && (
        <>
          <span className="text-white-8 hidden md:inline">|</span>
          <span
            className="text-[10px] text-text-secondary"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {getStarterText()}
          </span>
        </>
      )}
    </div>
  )
}
