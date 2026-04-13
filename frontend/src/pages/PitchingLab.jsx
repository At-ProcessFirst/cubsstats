import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { usePlayerBenchmarks, useBenchmarks } from '../hooks/useBenchmarks'
import { formatStat, ordinal, STAT_LABELS, STAT_ABBREVS, STAT_EXPLANATIONS } from '../utils/formatting'
import { gradeFromPercentile, LOWER_IS_BETTER, normalizeGradeKey } from '../utils/grading'
import GradingLegend from '../components/GradingLegend'
import GradeBadge from '../components/GradeBadge'
import BenchmarkGauge from '../components/BenchmarkGauge'
import PercentileBar from '../components/PercentileBar'
import PitchArsenalCard from '../components/PitchArsenalCard'
import VelocityTrend from '../components/VelocityTrend'
import VerdictBox from '../components/VerdictBox'

const PITCHING_STATS = [
  { key: 'era', min: 1.5, max: 7.0, lib: true },
  { key: 'fip', min: 1.5, max: 7.0, lib: true },
  { key: 'xfip', min: 2.0, max: 6.5, lib: true },
  { key: 'xera', min: 2.0, max: 7.0, lib: true },
  { key: 'k_pct', min: 5, max: 40, lib: false },
  { key: 'bb_pct', min: 2, max: 15, lib: true },
  { key: 'k_bb_pct', min: -5, max: 30, lib: false },
  { key: 'swstr_pct', min: 5, max: 20, lib: false },
  { key: 'csw_pct', min: 20, max: 40, lib: false },
  { key: 'hard_hit_pct', min: 20, max: 50, lib: true },
  { key: 'barrel_pct', min: 2, max: 15, lib: true },
  { key: 'avg_velo', min: 85, max: 100, lib: false },
]

const PITCH_TYPE_NAMES = {
  FF: '4-Seam Fastball', SI: 'Sinker', FC: 'Cutter',
  SL: 'Slider', CU: 'Curveball', CH: 'Changeup', FS: 'Splitter',
}
const PITCH_COLORS = {
  FF: '#F87171', SI: '#FB923C', FC: '#FBBF24',
  SL: '#60A5FA', CU: '#A78BFA', CH: '#34D399', FS: '#22D3EE',
}

function statusBadge(pitcher, playerBenchmarks) {
  if (!playerBenchmarks?.length) return { label: 'NEW', color: '#8892A8' }
  const eraB = playerBenchmarks.find(b => b.stat_name === 'era')
  const fipB = playerBenchmarks.find(b => b.stat_name === 'fip')
  if (eraB && fipB && eraB.value && fipB.value) {
    const gap = eraB.value - fipB.value
    if (gap < -0.75) return { label: 'REGRESS', color: '#F87171' }
    if (gap > 0.75) return { label: 'BREAKOUT', color: '#34D399' }
  }
  if (eraB?.percentile != null) {
    if (eraB.percentile >= 75) return { label: 'ELITE', color: '#34D399' }
    if (eraB.percentile <= 25) return { label: 'WATCH', color: '#FBBF24' }
  }
  return { label: 'STABLE', color: '#8892A8' }
}

function buildVerdict(pitcher, benchmarks) {
  if (!pitcher || !benchmarks?.length) return null
  const name = pitcher.name
  const parts = []
  const eraB = benchmarks.find(b => b.stat_name === 'era')
  const fipB = benchmarks.find(b => b.stat_name === 'fip')
  const kB = benchmarks.find(b => b.stat_name === 'k_pct')

  if (eraB) {
    const g = gradeFromPercentile(eraB.percentile)
    parts.push(`ERA of ${eraB.value?.toFixed(2)} ranks in the ${ordinal(eraB.percentile)} percentile (${g.label.toLowerCase()})`)
  }
  if (fipB && eraB) {
    const gap = eraB.value - fipB.value
    if (Math.abs(gap) >= 0.5) {
      parts.push(gap > 0
        ? `but FIP (${fipB.value?.toFixed(2)}) suggests he's pitching better than his ERA shows — expect improvement`
        : `however FIP (${fipB.value?.toFixed(2)}) suggests some luck — ERA may rise`
      )
    }
  }
  if (kB) parts.push(`striking out batters at a ${ordinal(kB.percentile)} percentile rate`)

  // Fallback: generate from raw stats when benchmarks unavailable
  if (!parts.length && pitcher) {
    if (pitcher.era != null) parts.push(`${pitcher.era.toFixed(2)} ERA through ${pitcher.ip?.toFixed(1) || '?'} innings`)
    if (pitcher.fip != null) {
      const gap = (pitcher.era || 0) - pitcher.fip
      if (Math.abs(gap) >= 0.5) {
        parts.push(`True ERA (FIP) of ${pitcher.fip.toFixed(2)} ${gap > 0 ? 'suggests regression ahead — the ERA has been inflated by luck' : 'shows the actual pitching is better than results indicate'}`)
      }
    }
    if (pitcher.k_pct != null) parts.push(`${pitcher.k_pct.toFixed(1)}% strikeout rate`)
  }
  return parts.length ? parts.join('. ') + '.' : `${name}'s early-season sample is still small — check back as the body of work grows.`
}

export default function PitchingLab() {
  const { data: pitchers, loading: pitchLoading } = useApi('/pitching/cubs/enriched')
  const { getBenchmark, getMlbAvg, loading: benchLoading } = useBenchmarks()
  const [selectedId, setSelectedId] = useState(null)

  const sortedPitchers = useMemo(() => {
    if (!pitchers?.length) return []
    return [...pitchers].sort((a, b) => (b.ip || 0) - (a.ip || 0))
  }, [pitchers])

  const activePitcher = useMemo(() => {
    if (!sortedPitchers.length) return null
    if (selectedId) return sortedPitchers.find(p => p.player_id === selectedId) || sortedPitchers[0]
    return sortedPitchers[0]
  }, [sortedPitchers, selectedId])

  const activeId = activePitcher?.player_id
  const { playerBenchmarks, statMap, getPlayerStat, loading: pbLoading } = usePlayerBenchmarks(activeId)

  const posGroup = activePitcher?.position_group || 'SP'

  // Build percentile rankings sorted by strength
  const rankings = useMemo(() => {
    if (!playerBenchmarks?.length) return []
    return [...playerBenchmarks]
      .filter(b => PITCHING_STATS.some(s => s.key === b.stat_name))
      .sort((a, b) => (b.percentile || 0) - (a.percentile || 0))
  }, [playerBenchmarks])

  const verdict = buildVerdict(activePitcher, playerBenchmarks)
  const overallGrade = useMemo(() => {
    if (!rankings.length) return null
    const avg = rankings.reduce((s, r) => s + (r.percentile || 50), 0) / rankings.length
    return gradeFromPercentile(Math.round(avg))
  }, [rankings])

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Grading Legend */}
      <GradingLegend />

      {/* 2. Page title */}
      <div>
        <h1 className="text-xl font-bold text-text-primary">Pitching Lab</h1>
        <p className="text-sm text-text-secondary mt-1">
          Deep-dive into every Cubs pitcher — all stats benchmarked against the MLB
        </p>
      </div>

      {/* 3. Pitcher tabs */}
      {pitchLoading ? (
        <div className="flex gap-2">{Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 w-32 rounded bg-surface-hover animate-pulse" />
        ))}</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {sortedPitchers.map(p => {
            const isActive = p.player_id === activeId
            const badge = statusBadge(p, isActive ? playerBenchmarks : [])
            return (
              <button
                key={p.player_id}
                onClick={() => setSelectedId(p.player_id)}
                className={`px-3 py-2 rounded-lg border transition-colors text-sm font-medium flex items-center gap-2 ${
                  isActive
                    ? 'bg-cubs-blue border-cubs-blue text-white'
                    : 'bg-surface border-white-8 text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                }`}
              >
                <span>{p.name}</span>
                <span
                  className="text-[8px] px-1.5 py-0.5 rounded font-bold"
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    color: badge.color,
                    backgroundColor: `${badge.color}22`,
                  }}
                >
                  {badge.label}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* 4. Profile header */}
      {activePitcher && (
        <div className="bg-surface rounded-lg border border-white-8 p-4 flex items-center gap-4">
          {/* Avatar placeholder */}
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold text-white"
            style={{ backgroundColor: '#0E3386', border: '2px solid #CC3433' }}
          >
            {activePitcher.name?.charAt(0) || 'P'}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-text-primary">{activePitcher.name}</h2>
              {overallGrade && <GradeBadge grade={overallGrade.label} size="md" />}
            </div>
            <div className="flex items-center gap-4 mt-1">
              <Stat label="Role" value={posGroup} />
              <Stat label="IP" value={activePitcher.ip?.toFixed(1)} />
              <Stat label="G" value={activePitcher.games} />
              <Stat label="GS" value={activePitcher.games_started} />
              <Stat label="ERA" value={activePitcher.era?.toFixed(2)} />
              <Stat label="FIP" value={activePitcher.fip?.toFixed(2)} />
            </div>
          </div>
        </div>
      )}

      {/* 5. Two-col: Performance Benchmarks | Pitch Arsenal */}
      {activePitcher && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Left: Performance vs MLB */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-4"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PERFORMANCE VS MLB
            </h3>
            <div className="flex flex-col gap-5">
              {PITCHING_STATS.map(({ key, min, max, lib }) => {
                const val = activePitcher[key]
                if (val == null) return null
                const bench = getBenchmark(key, posGroup)
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
                    <BenchmarkGauge
                      value={val} mlbAvg={mlbAvg} min={min} max={max}
                      lowerIsBetter={lib} percentile={pctile}
                    />
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right: Pitch Arsenal — only shown when Statcast data is available */}
          <div>
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PITCH ARSENAL
            </h3>
            <p className="text-[10px] text-text-secondary italic mb-3">
              Velocity, movement, whiff rates — from Statcast pitch-level data
            </p>
          </div>
        </div>
      )}

      {/* 6. Three-col: Velocity Trend | Recent Starts | Percentile Rankings */}
      {activePitcher && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Velocity Trend */}
          <VelocityTrend
            data={[]}
            mlbAvg={getMlbAvg('avg_velo', posGroup)}
            playerName={activePitcher.name}
          />

          {/* Recent Starts */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              RECENT STARTS
            </h3>
            <div className="text-sm text-text-secondary italic flex items-center justify-center h-[180px]">
              Season game log
            </div>
            {getBenchmark('era', posGroup) && (
              <div className="mt-2 pt-2 border-t border-white-8">
                <span className="text-[9px] text-text-secondary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  MLB avg start: {getBenchmark('era', posGroup)?.mean?.toFixed(2)} ERA
                </span>
              </div>
            )}
          </div>

          {/* Percentile Rankings */}
          <div className="bg-surface rounded-lg border border-white-8 p-4">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              PERCENTILE RANKINGS
            </h3>
            {!rankings.length ? (
              <div className="text-sm text-text-secondary italic flex items-center justify-center h-[180px]">
                Rankings based on league benchmarks
              </div>
            ) : (
              <div className="flex flex-col">
                {rankings.map(r => (
                  <PercentileBar
                    key={r.stat_name}
                    label={STAT_LABELS[r.stat_name] || r.stat_name}
                    value={r.value}
                    percentile={r.percentile}
                    statName={r.stat_name}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. Verdict Box */}
      {activePitcher && verdict && (
        <VerdictBox
          playerName={activePitcher.name}
          verdictText={verdict}
          verdictGrade={overallGrade?.label}
        />
      )}
    </div>
  )
}

function Stat({ label, value }) {
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
