import { useMemo, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { formatStat } from '../utils/formatting'
import GradingLegend from '../components/GradingLegend'
import DivergenceAlert from '../components/DivergenceAlert'

const FILTER_OPTIONS = ['ALL', 'BREAKOUT', 'REGRESS', 'WATCH', 'INJURY']

export default function Divergences() {
  const { data: divergences, loading, error } = useApi('/divergences/enriched?limit=50')
  const { data: liveContext } = useApi('/team/live-context')
  const [filter, setFilter] = useState('ALL')
  const [showAllTxns, setShowAllTxns] = useState(false)

  const filtered = useMemo(() => {
    if (!divergences?.length) return []
    if (filter === 'ALL') return divergences
    return divergences.filter(d => d.alert_type === filter)
  }, [divergences, filter])

  const injuries = liveContext?.injuries || []

  const counts = useMemo(() => {
    if (!divergences?.length) return {}
    const c = { ALL: divergences.length }
    for (const d of divergences) {
      c[d.alert_type] = (c[d.alert_type] || 0) + 1
    }
    // Show IL count on INJURY tab if no stat-based injury alerts
    if (!c.INJURY && injuries.length > 0) {
      c.INJURY = injuries.length
    }
    return c
  }, [divergences, injuries])

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Divergence Alerts</h1>
        <p className="text-sm text-text-secondary mt-1">
          When a player's surface stats diverge from underlying metrics, regression or breakout is likely.
          Every alert shows both stats with their MLB percentile rank.
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 -mb-1">
        {FILTER_OPTIONS.map(opt => {
          const isActive = filter === opt
          const colors = {
            ALL: '#60A5FA', BREAKOUT: '#34D399', REGRESS: '#F87171',
            WATCH: '#FBBF24', INJURY: '#F472B6',
          }
          return (
            <button
              key={opt}
              onClick={() => setFilter(opt)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 shrink-0 ${
                isActive ? 'text-white' : 'text-text-secondary hover:text-text-primary'
              }`}
              style={{
                backgroundColor: isActive ? `${colors[opt]}22` : 'transparent',
                borderWidth: 1,
                borderColor: isActive ? `${colors[opt]}44` : 'rgba(255,255,255,0.08)',
              }}
            >
              <span style={{ color: isActive ? colors[opt] : undefined }}>{opt}</span>
              {counts[opt] != null && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    backgroundColor: `${colors[opt]}18`,
                    color: colors[opt],
                  }}>
                  {counts[opt]}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Divergence explanation box */}
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          <ExplainBox badge="BREAKOUT" color="#34D399"
            text="Player's underlying metrics suggest better performance ahead. Surface stats haven't caught up yet." />
          <ExplainBox badge="REGRESS" color="#F87171"
            text="Surface stats are outperforming underlying quality. Expect a pullback toward expected levels." />
          <ExplainBox badge="WATCH" color="#FBBF24"
            text="A stat is in unusual territory (e.g., extreme BABIP). Monitor for normalization." />
          <ExplainBox badge="INJURY" color="#F472B6"
            text="Velocity drop or sudden stat change consistent with injury risk. Track closely." />
        </div>
      </div>

      {/* Recent Transactions */}
      {liveContext?.transactions?.length > 0 && (
        <div className="bg-surface rounded-lg border border-white-8 p-4">
          <button
            onClick={() => setShowAllTxns(!showAllTxns)}
            className="flex items-center justify-between w-full"
          >
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              RECENT TRANSACTIONS ({liveContext.transactions.length})
            </h3>
            <span className="text-[10px] text-accent-blue">
              {showAllTxns ? 'Show less' : 'Show all'}
            </span>
          </button>
          <div className="mt-2 flex flex-col gap-1.5">
            {(showAllTxns ? liveContext.transactions : liveContext.transactions.slice(0, 5)).map((t, i) => (
              <div key={i} className="flex gap-2 py-1 border-b border-white-8 last:border-b-0">
                <span className="text-[10px] text-text-secondary shrink-0 w-[70px]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {t.date}
                </span>
                <span className="text-[11px] text-text-primary leading-snug">
                  {t.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* IL Roster — shown when INJURY filter is active */}
      {filter === 'INJURY' && injuries.length > 0 && (
        <div className="bg-surface rounded-lg border border-white-8 p-4 card-elevated"
          style={{ borderLeft: '3px solid #F472B6' }}>
          <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            CUBS INJURED LIST ({injuries.length} players)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {injuries.map((inj, i) => (
              <div key={i} className="flex items-center gap-2 py-1.5 px-3 rounded-lg"
                style={{ backgroundColor: 'rgba(244,114,182,0.08)' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-pink-400 shrink-0" />
                <span className="text-[12px] text-text-primary font-medium"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {inj.player_name}
                </span>
                <span className="text-[10px] text-text-secondary ml-auto shrink-0">
                  {inj.injury_type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alert feed */}
      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-surface-hover animate-pulse" />
          ))}
        </div>
      ) : !filtered.length && !(filter === 'INJURY' && injuries.length > 0) ? (
        <div className="bg-surface rounded-lg border border-white-8 p-8 text-center">
          <p className="text-lg text-text-secondary">
            {divergences?.length
              ? `No ${filter.toLowerCase()} alerts active`
              : 'All Cubs players are tracking their expected performance. No significant stat divergences detected.'}
          </p>
          <p className="text-sm text-text-secondary mt-2 italic">
            The regression detection system monitors every stat against MLB benchmarks daily.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map(d => (
            <DivergenceAlert
              key={d.id}
              alertType={d.alert_type}
              playerName={d.player_name}
              stat1Name={d.stat1_name}
              stat1Value={formatStat(d.stat1_value, d.stat1_name)}
              stat1Percentile={d.stat1_percentile}
              stat2Name={d.stat2_name}
              stat2Value={formatStat(d.stat2_value, d.stat2_name)}
              stat2Percentile={d.stat2_percentile}
              explanation={d.explanation}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ExplainBox({ badge, color, text }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[9px] font-bold tracking-wider px-2 py-0.5 rounded w-fit"
        style={{ fontFamily: "'JetBrains Mono', monospace", color, backgroundColor: `${color}18` }}>
        {badge}
      </span>
      <p className="text-[10px] text-text-secondary leading-snug">{text}</p>
    </div>
  )
}
