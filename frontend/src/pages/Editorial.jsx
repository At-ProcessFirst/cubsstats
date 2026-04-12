import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { Link } from 'react-router-dom'
import GradingLegend from '../components/GradingLegend'

const TYPE_META = {
  daily_takeaway: { label: 'DAILY TAKEAWAY', color: '#60A5FA', icon: '📝' },
  weekly_state: { label: 'WEEKLY STATE', color: '#A78BFA', icon: '📊' },
  player_spotlight: { label: 'PLAYER SPOTLIGHT', color: '#34D399', icon: '🔦' },
  prediction_recap: { label: 'PREDICTION RECAP', color: '#FBBF24', icon: '🎯' },
}

const TYPE_FILTERS = ['ALL', 'daily_takeaway', 'weekly_state', 'player_spotlight', 'prediction_recap']

/**
 * Render editorial body with inline stat styling.
 * Stats formatted like "3.42 ERA" or "118 wRC+" get blue monospace treatment.
 * Player names that match known Cubs get turned into clickable chips.
 */
function StyledBody({ body, playerIds = [] }) {
  if (!body) return null

  // Highlight stat patterns: numbers followed by stat abbreviations
  const statPattern = /(\d+\.?\d*)\s*(ERA|FIP|xFIP|xERA|wRC\+|wOBA|xBA|xSLG|xwOBA|OAA|DRS|BABIP|K%|BB%|SwStr%|CSW%|IP|PA|HR|AVG|OBP|SLG|mph)(\s*\([^)]*\))?/g

  const parts = body.split(statPattern)

  return (
    <div className="text-[14px] text-text-primary leading-relaxed whitespace-pre-line">
      {parts.map((part, i) => {
        // Every 4th group starting at 1 is the number, 2 is the stat abbr, 3 is the paren
        const groupPos = i % 4
        if (groupPos === 1) {
          // Number part
          return (
            <span
              key={i}
              className="font-bold"
              style={{ fontFamily: "'JetBrains Mono', monospace", color: '#60A5FA' }}
            >
              {part}
            </span>
          )
        }
        if (groupPos === 2) {
          // Stat abbreviation
          return (
            <span
              key={i}
              className="font-semibold"
              style={{ fontFamily: "'JetBrains Mono', monospace", color: '#60A5FA' }}
            >
              {' '}{part}
            </span>
          )
        }
        if (groupPos === 3 && part) {
          // Parenthetical (percentile info)
          return (
            <span
              key={i}
              className="text-[12px]"
              style={{ fontFamily: "'JetBrains Mono', monospace", color: '#8892A8' }}
            >
              {part}
            </span>
          )
        }
        // Regular text
        return <span key={i}>{part}</span>
      })}
    </div>
  )
}

function PlayerChips({ playerIds = [] }) {
  if (!playerIds.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {playerIds.map(id => (
        <Link
          key={id}
          to={`/pitching`}
          className="text-[9px] px-2 py-1 rounded-full bg-cubs-blue/20 text-accent-blue hover:bg-cubs-blue/30 transition-colors"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          #{id}
        </Link>
      ))}
    </div>
  )
}

function HeroCard({ editorial }) {
  if (!editorial) return null
  const meta = TYPE_META[editorial.editorial_type] || TYPE_META.daily_takeaway

  return (
    <div
      className="bg-surface rounded-xl border border-white-8 p-6"
      style={{ borderLeftWidth: 4, borderLeftColor: meta.color }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{meta.icon}</span>
        <span
          className="text-[9px] uppercase tracking-widest font-bold px-2 py-0.5 rounded"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: meta.color,
            backgroundColor: `${meta.color}18`,
          }}
        >
          {meta.label}
        </span>
        <span className="text-[10px] text-text-secondary ml-auto">
          {editorial.created_at ? new Date(editorial.created_at).toLocaleDateString('en-US', {
            weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
          }) : ''}
        </span>
      </div>

      <h2 className="text-lg font-bold text-text-primary mb-3">
        {editorial.title}
      </h2>

      <StyledBody body={editorial.body} playerIds={editorial.player_ids} />
      <PlayerChips playerIds={editorial.player_ids} />
    </div>
  )
}

function EditorialGridCard({ editorial }) {
  const meta = TYPE_META[editorial.editorial_type] || TYPE_META.daily_takeaway

  return (
    <div
      className="bg-surface rounded-lg border border-white-8 p-4 hover:bg-surface-hover transition-colors cursor-pointer"
      style={{ borderLeftWidth: 3, borderLeftColor: meta.color }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="text-[8px] uppercase tracking-widest font-semibold px-1.5 py-0.5 rounded"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            color: meta.color,
            backgroundColor: `${meta.color}18`,
          }}
        >
          {meta.label}
        </span>
        <span className="text-[9px] text-text-secondary ml-auto">
          {editorial.created_at ? new Date(editorial.created_at).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric',
          }) : ''}
        </span>
      </div>

      <h4 className="text-sm font-semibold text-text-primary mb-1.5 line-clamp-2">
        {editorial.title}
      </h4>

      <p className="text-[11px] text-text-secondary leading-snug line-clamp-3">
        {editorial.summary || editorial.body?.slice(0, 150)}
      </p>

      {editorial.player_ids?.length > 0 && (
        <div className="flex gap-1 mt-2">
          {editorial.player_ids.slice(0, 3).map(id => (
            <span
              key={id}
              className="text-[8px] px-1.5 py-0.5 rounded bg-surface-hover text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              #{id}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Editorial() {
  const { data: latestData } = useApi('/editorials/latest')
  const { data: allData, loading } = useApi('/editorials?limit=50')
  const [filter, setFilter] = useState('ALL')

  const editorials = allData?.editorials || []
  const latest = latestData

  const filtered = useMemo(() => {
    if (filter === 'ALL') return editorials
    return editorials.filter(e => e.editorial_type === filter)
  }, [editorials, filter])

  // Separate hero (latest) from grid (rest)
  const gridItems = filtered.filter(e => e.id !== latest?.id)

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Editorial</h1>
        <p className="text-sm text-text-secondary mt-1">
          AI-generated analysis powered by Claude — every insight backed by specific stats and MLB benchmarks
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2">
        {TYPE_FILTERS.map(t => {
          const isActive = filter === t
          const meta = TYPE_META[t] || { label: 'ALL', color: '#60A5FA' }
          const label = t === 'ALL' ? 'ALL' : meta.label
          const color = t === 'ALL' ? '#60A5FA' : meta.color
          return (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`px-3 py-1.5 rounded text-[11px] font-medium transition-colors ${
                isActive ? 'text-white' : 'text-text-secondary hover:text-text-primary'
              }`}
              style={{
                backgroundColor: isActive ? `${color}22` : 'transparent',
                borderWidth: 1,
                borderColor: isActive ? `${color}44` : 'rgba(255,255,255,0.08)',
              }}
            >
              <span style={{ color: isActive ? color : undefined }}>{label}</span>
            </button>
          )
        })}
      </div>

      {/* Hero card — latest editorial */}
      {latest && filter === 'ALL' && <HeroCard editorial={latest} />}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-36 rounded-lg bg-surface-hover animate-pulse" />
          ))}
        </div>
      ) : !filtered.length ? (
        <div className="bg-surface rounded-lg border border-white-8 p-8 text-center">
          <p className="text-lg text-text-secondary mb-2">No editorials yet</p>
          <p className="text-sm text-text-secondary italic">
            Editorials are auto-generated after each game and weekly on Mondays.
            They can also be triggered manually via the API.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {gridItems.map(e => (
            <EditorialGridCard key={e.id} editorial={e} />
          ))}
        </div>
      )}

      {/* How it works */}
      <div className="bg-surface rounded-lg border border-white-8 p-4 mt-2">
        <h3
          className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          HOW EDITORIALS WORK
        </h3>
        <div className="grid grid-cols-4 gap-4">
          {Object.entries(TYPE_META).map(([type, meta]) => (
            <div key={type} className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5">
                <span>{meta.icon}</span>
                <span
                  className="text-[9px] font-bold tracking-wider"
                  style={{ fontFamily: "'JetBrains Mono', monospace", color: meta.color }}
                >
                  {meta.label}
                </span>
              </div>
              <p className="text-[10px] text-text-secondary leading-snug">
                {type === 'daily_takeaway' && 'Generated after each Cubs game with box score stats and divergence context.'}
                {type === 'weekly_state' && 'Monday morning overview: team standing, Pythagorean record, top performers.'}
                {type === 'player_spotlight' && 'Triggered when a player has significant divergence flags or breakout stats.'}
                {type === 'prediction_recap' && 'Weekly review of ML model accuracy vs baselines.'}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
