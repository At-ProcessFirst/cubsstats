import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { usePlayerBenchmarks, useBenchmarks } from '../hooks/useBenchmarks'
import { formatStat, ordinal, STAT_LABELS, STAT_ABBREVS, STAT_EXPLANATIONS } from '../utils/formatting'
import { gradeFromPercentile, LOWER_IS_BETTER } from '../utils/grading'
import GradingLegend from '../components/GradingLegend'
import GradeBadge from '../components/GradeBadge'
import BenchmarkGauge from '../components/BenchmarkGauge'
import PercentileBar from '../components/PercentileBar'
import VerdictBox from '../components/VerdictBox'

const HITTING_STATS = [
  { key: 'wrc_plus', min: 50, max: 180, lib: false },
  { key: 'woba', min: .220, max: .420, lib: false },
  { key: 'xba', min: .180, max: .320, lib: false },
  { key: 'xslg', min: .250, max: .600, lib: false },
  { key: 'xwoba', min: .220, max: .420, lib: false },
  { key: 'barrel_pct', min: 0, max: 20, lib: false },
  { key: 'hard_hit_pct', min: 20, max: 60, lib: false },
  { key: 'avg_exit_velo', min: 82, max: 96, lib: false },
  { key: 'o_swing_pct', min: 15, max: 45, lib: true },
  { key: 'z_contact_pct', min: 70, max: 98, lib: false },
  { key: 'chase_rate', min: 15, max: 45, lib: true },
  { key: 'sprint_speed', min: 23, max: 31, lib: false },
  { key: 'bsr', min: -5, max: 8, lib: false },
  { key: 'babip', min: .220, max: .400, lib: false },
]

function statusBadge(hitter, benchmarks) {
  if (!benchmarks?.length) return { label: 'NEW', color: '#8892A8' }
  const wrcB = benchmarks.find(b => b.stat_name === 'wrc_plus')
  const xwobaB = benchmarks.find(b => b.stat_name === 'xwoba')
  const wobaB = benchmarks.find(b => b.stat_name === 'woba')
  if (wobaB && xwobaB && wobaB.value && xwobaB.value) {
    const gap = wobaB.value - xwobaB.value
    if (gap > 0.030) return { label: 'REGRESS', color: '#F87171' }
    if (gap < -0.025) return { label: 'BREAKOUT', color: '#34D399' }
  }
  if (wrcB?.percentile != null) {
    if (wrcB.percentile >= 75) return { label: 'ELITE', color: '#34D399' }
    if (wrcB.percentile <= 25) return { label: 'WATCH', color: '#FBBF24' }
  }
  return { label: 'STABLE', color: '#8892A8' }
}

function buildVerdict(hitter, benchmarks) {
  if (!hitter || !benchmarks?.length) return null
  const parts = []
  const wrcB = benchmarks.find(b => b.stat_name === 'wrc_plus')
  const wobaB = benchmarks.find(b => b.stat_name === 'woba')
  const xwobaB = benchmarks.find(b => b.stat_name === 'xwoba')
  const barrelB = benchmarks.find(b => b.stat_name === 'barrel_pct')

  if (wrcB) {
    const g = gradeFromPercentile(wrcB.percentile)
    parts.push(`wRC+ of ${Math.round(wrcB.value)} ranks ${ordinal(wrcB.percentile)} percentile (${g.label.toLowerCase()})`)
  }
  if (wobaB && xwobaB) {
    const gap = wobaB.value - xwobaB.value
    if (Math.abs(gap) >= 0.020) {
      parts.push(gap > 0
        ? `wOBA (.${(wobaB.value * 1000).toFixed(0)}) outpacing xwOBA (.${(xwobaB.value * 1000).toFixed(0)}) — some regression likely`
        : `xwOBA (.${(xwobaB.value * 1000).toFixed(0)}) ahead of wOBA (.${(wobaB.value * 1000).toFixed(0)}) — breakout potential`
      )
    }
  }
  if (barrelB) parts.push(`barrel rate at the ${ordinal(barrelB.percentile)} percentile`)
  return parts.length ? parts.join('. ') + '.' : `${hitter.name} has limited benchmark data available.`
}

export default function HittingLab() {
  const { data: hitters, loading: hitLoading } = useApi('/hitting/cubs/enriched')
  const { getBenchmark, loading: benchLoading } = useBenchmarks()
  const [selectedId, setSelectedId] = useState(null)

  const sortedHitters = useMemo(() => {
    if (!hitters?.length) return []
    return [...hitters].sort((a, b) => (b.pa || 0) - (a.pa || 0))
  }, [hitters])

  const activeHitter = useMemo(() => {
    if (!sortedHitters.length) return null
    if (selectedId) return sortedHitters.find(h => h.player_id === selectedId) || sortedHitters[0]
    return sortedHitters[0]
  }, [sortedHitters, selectedId])

  const activeId = activeHitter?.player_id
  const { playerBenchmarks, getPlayerStat, loading: pbLoading } = usePlayerBenchmarks(activeId)

  const rankings = useMemo(() => {
    if (!playerBenchmarks?.length) return []
    return [...playerBenchmarks]
      .filter(b => HITTING_STATS.some(s => s.key === b.stat_name))
      .sort((a, b) => (b.percentile || 0) - (a.percentile || 0))
  }, [playerBenchmarks])

  const verdict = buildVerdict(activeHitter, playerBenchmarks)
  const overallGrade = useMemo(() => {
    if (!rankings.length) return null
    const avg = rankings.reduce((s, r) => s + (r.percentile || 50), 0) / rankings.length
    return gradeFromPercentile(Math.round(avg))
  }, [rankings])

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Hitting Lab</h1>
        <p className="text-sm text-text-secondary mt-1">
          Deep-dive into every Cubs hitter — all stats benchmarked against the MLB
        </p>
      </div>

      {/* Hitter tabs */}
      {hitLoading ? (
        <div className="flex gap-2">{Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-10 w-32 rounded bg-surface-hover animate-pulse" />
        ))}</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {sortedHitters.map(h => {
            const isActive = h.player_id === activeId
            const badge = statusBadge(h, isActive ? playerBenchmarks : [])
            return (
              <button
                key={h.player_id}
                onClick={() => setSelectedId(h.player_id)}
                className={`px-3 py-2 rounded-lg border transition-colors text-sm font-medium flex items-center gap-2 ${
                  isActive
                    ? 'bg-cubs-blue border-cubs-blue text-white'
                    : 'bg-surface border-white-8 text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                }`}
              >
                <span>{h.name}</span>
                <span className="text-[8px] px-1.5 py-0.5 rounded font-bold"
                  style={{ fontFamily: "'JetBrains Mono', monospace", color: badge.color, backgroundColor: `${badge.color}22` }}>
                  {badge.label}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* Profile header */}
      {activeHitter && (
        <div className="bg-surface rounded-lg border border-white-8 p-4 flex items-center gap-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold text-white"
            style={{ backgroundColor: '#0E3386', border: '2px solid #CC3433' }}>
            {activeHitter.name?.charAt(0) || 'H'}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-text-primary">{activeHitter.name}</h2>
              {overallGrade && <GradeBadge grade={overallGrade.label} size="md" />}
            </div>
            <div className="flex items-center gap-4 mt-1">
              <StatPill label="Pos" value={activeHitter.position || activeHitter.position_group} />
              <StatPill label="PA" value={activeHitter.pa} />
              <StatPill label="G" value={activeHitter.games} />
              <StatPill label="AVG" value={activeHitter.avg?.toFixed(3)} />
              <StatPill label="wRC+" value={activeHitter.wrc_plus != null ? Math.round(activeHitter.wrc_plus) : null} />
              <StatPill label="wOBA" value={activeHitter.woba?.toFixed(3)} />
            </div>
          </div>
        </div>
      )}

      {/* Two-col: Performance Benchmarks | Contact & Plate Discipline */}
      {activeHitter && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Performance vs MLB */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-4"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PERFORMANCE VS MLB
            </h3>
            <div className="flex flex-col gap-5">
              {HITTING_STATS.slice(0, 8).map(({ key, min, max, lib }) => {
                const val = activeHitter[key]
                if (val == null) return null
                const bench = getBenchmark(key, 'ALL_HITTERS')
                const pb = getPlayerStat(key)
                const mlbAvg = bench?.mean
                const pctile = pb?.percentile ?? null
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold text-text-primary">
                          {STAT_LABELS[key] || key}
                        </span>
                        <span className="text-[8px] text-text-secondary"
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {STAT_ABBREVS[key]}
                        </span>
                        {pctile != null && <GradeBadge grade={gradeFromPercentile(pctile).label} />}
                      </div>
                      <span className="text-[13px] font-bold"
                        style={{ fontFamily: "'JetBrains Mono', monospace", color: pctile != null ? gradeFromPercentile(pctile).color : '#E8ECF4' }}>
                        {formatStat(val, key)}
                      </span>
                    </div>
                    {STAT_EXPLANATIONS[key] && (
                      <p className="text-[9px] text-accent-blue italic mb-1">{STAT_EXPLANATIONS[key]}</p>
                    )}
                    <BenchmarkGauge value={val} mlbAvg={mlbAvg} min={min} max={max}
                      lowerIsBetter={lib} percentile={pctile} />
                  </div>
                )
              })}
            </div>
          </div>

          {/* Plate Discipline & Speed */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-4"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PLATE DISCIPLINE & SPEED
            </h3>
            <div className="flex flex-col gap-5">
              {HITTING_STATS.slice(8).map(({ key, min, max, lib }) => {
                const val = activeHitter[key]
                if (val == null) return null
                const bench = getBenchmark(key, 'ALL_HITTERS')
                const pb = getPlayerStat(key)
                const mlbAvg = bench?.mean
                const pctile = pb?.percentile ?? null
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold text-text-primary">
                          {STAT_LABELS[key] || key}
                        </span>
                        <span className="text-[8px] text-text-secondary"
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {STAT_ABBREVS[key]}
                        </span>
                        {pctile != null && <GradeBadge grade={gradeFromPercentile(pctile).label} />}
                      </div>
                      <span className="text-[13px] font-bold"
                        style={{ fontFamily: "'JetBrains Mono', monospace", color: pctile != null ? gradeFromPercentile(pctile).color : '#E8ECF4' }}>
                        {formatStat(val, key)}
                      </span>
                    </div>
                    {STAT_EXPLANATIONS[key] && (
                      <p className="text-[9px] text-accent-blue italic mb-1">{STAT_EXPLANATIONS[key]}</p>
                    )}
                    <BenchmarkGauge value={val} mlbAvg={mlbAvg} min={min} max={max}
                      lowerIsBetter={lib} percentile={pctile} />
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Three-col: Recent Games | Percentile Rankings | Season Splits */}
      {activeHitter && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Recent Games */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              RECENT GAMES
            </h3>
            <div className="text-sm text-text-secondary italic flex items-center justify-center h-[180px]">
              Game log data available after seeding
            </div>
          </div>

          {/* Percentile Rankings */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PERCENTILE RANKINGS
            </h3>
            {!rankings.length ? (
              <div className="text-sm text-text-secondary italic flex items-center justify-center h-[180px]">
                Benchmark data available after seeding
              </div>
            ) : (
              <div className="flex flex-col">
                {rankings.map(r => (
                  <PercentileBar key={r.stat_name}
                    label={STAT_LABELS[r.stat_name] || r.stat_name}
                    value={r.value} percentile={r.percentile} statName={r.stat_name} />
                ))}
              </div>
            )}
          </div>

          {/* Batted Ball Profile */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              BATTED BALL PROFILE
            </h3>
            <div className="flex flex-col gap-3">
              {[
                { label: 'Avg Exit Velo', key: 'avg_exit_velo' },
                { label: 'Barrel%', key: 'barrel_pct' },
                { label: 'Hard Hit%', key: 'hard_hit_pct' },
                { label: 'BABIP', key: 'babip' },
              ].map(({ label, key }) => {
                const val = activeHitter[key]
                const pb = getPlayerStat(key)
                return (
                  <div key={key} className="flex items-center justify-between py-1 border-b border-white-8 last:border-b-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-text-secondary">{label}</span>
                      {pb && <GradeBadge grade={gradeFromPercentile(pb.percentile).label} />}
                    </div>
                    <span className="text-[12px] font-bold"
                      style={{ fontFamily: "'JetBrains Mono', monospace", color: pb ? gradeFromPercentile(pb.percentile).color : '#E8ECF4' }}>
                      {val != null ? formatStat(val, key) : '—'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Verdict */}
      {activeHitter && verdict && (
        <VerdictBox playerName={activeHitter.name} verdictText={verdict} verdictGrade={overallGrade?.label} />
      )}
    </div>
  )
}

function StatPill({ label, value }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[9px] text-text-secondary uppercase">{label}</span>
      <span className="text-[12px] font-semibold text-text-primary"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {value ?? '—'}
      </span>
    </div>
  )
}
