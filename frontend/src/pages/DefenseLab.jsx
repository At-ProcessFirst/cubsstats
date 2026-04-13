import { useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { useBenchmarks } from '../hooks/useBenchmarks'
import { formatStat, ordinal, STAT_LABELS, STAT_EXPLANATIONS } from '../utils/formatting'
import { gradeFromPercentile } from '../utils/grading'
import GradingLegend from '../components/GradingLegend'
import GradeBadge from '../components/GradeBadge'
import BenchmarkGauge from '../components/BenchmarkGauge'
import PercentileBar from '../components/PercentileBar'

const DEFENSE_STATS = [
  { key: 'oaa', label: 'OAA', min: -15, max: 15, lib: false, explanation: STAT_EXPLANATIONS.oaa },
  { key: 'drs', label: 'DRS', min: -15, max: 20, lib: false, explanation: STAT_EXPLANATIONS.drs },
  { key: 'framing_runs', label: 'Framing Runs', min: -10, max: 15, lib: false, explanation: STAT_EXPLANATIONS.framing_runs },
]

export default function DefenseLab() {
  const { data: defenders, loading: defLoading } = useApi('/defense/cubs/enriched')
  const { getBenchmark, loading: benchLoading } = useBenchmarks()

  const sortedDefenders = useMemo(() => {
    if (!defenders?.length) return []
    return [...defenders].sort((a, b) => {
      const aVal = (a.oaa || 0) + (a.drs || 0) + (a.framing_runs || 0)
      const bVal = (b.oaa || 0) + (b.drs || 0) + (b.framing_runs || 0)
      return bVal - aVal
    })
  }, [defenders])

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Defense Lab</h1>
        <p className="text-sm text-text-secondary mt-1">
          Fielding metrics for every Cubs defender — OAA, DRS, and catcher framing all benchmarked
        </p>
      </div>

      {/* Stat explainer cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {DEFENSE_STATS.map(s => (
          <div key={s.key} className="bg-surface rounded-lg border border-white-8 p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-semibold text-text-primary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.label}</span>
            </div>
            <p className="text-[10px] text-accent-blue italic mb-3">{s.explanation}</p>
            <div className="text-[9px] text-text-secondary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              0 = league average. Positive = better than average.
            </div>
          </div>
        ))}
      </div>

      {/* Player table */}
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          CUBS DEFENSIVE RANKINGS
        </h3>

        {defLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-8 rounded bg-surface-hover animate-pulse" style={{ width: `${70 + Math.random() * 30}%` }} />
            ))}
          </div>
        ) : !sortedDefenders.length ? (
          <p className="text-sm text-text-secondary italic py-8 text-center">
            No defensive data available — run seed scripts to populate
          </p>
        ) : (
          <div>
            {/* Header */}
            <div className="grid grid-cols-[140px_1fr_1fr_1fr_1fr] md:grid-cols-[200px_1fr_1fr_1fr_1fr] gap-2 pb-2 mb-2 border-b border-white-8">
              <span className="text-[8px] uppercase text-text-secondary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Player</span>
              <span className="text-[8px] uppercase text-text-secondary text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Pos</span>
              {DEFENSE_STATS.map(s => (
                <span key={s.key} className="text-[8px] uppercase text-text-secondary text-right"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.label}</span>
              ))}
            </div>

            {sortedDefenders.map(d => {
              const total = (d.oaa || 0) + (d.drs || 0) + (d.framing_runs || 0)
              const totalGrade = gradeFromPercentile(Math.max(1, Math.min(99, 50 + total * 3)))
              return (
                <div key={d.player_id} className="grid grid-cols-[140px_1fr_1fr_1fr_1fr] md:grid-cols-[200px_1fr_1fr_1fr_1fr] gap-2 py-2 border-b border-white-8 last:border-b-0 items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">{d.name}</span>
                    <GradeBadge grade={totalGrade.label} />
                  </div>
                  <span className="text-[11px] text-text-secondary text-right"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.position || '—'}</span>
                  {DEFENSE_STATS.map(s => {
                    const val = d[s.key]
                    const color = val != null
                      ? val > 5 ? '#34D399' : val > 0 ? '#6EE7B7' : val > -5 ? '#8892A8' : '#F87171'
                      : '#8892A8'
                    return (
                      <span key={s.key} className="text-[13px] font-bold text-right"
                        style={{ fontFamily: "'JetBrains Mono', monospace", color }}>
                        {val != null ? (val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1)) : '—'}
                      </span>
                    )
                  })}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Individual gauges for top defenders */}
      {sortedDefenders.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedDefenders.slice(0, 4).map(d => (
            <div key={d.player_id} className="bg-surface rounded-lg border border-white-8 p-4">
              <h4 className="text-sm font-semibold text-text-primary mb-3">{d.name}</h4>
              {DEFENSE_STATS.map(s => {
                const val = d[s.key]
                if (val == null) return null
                const pctile = Math.max(1, Math.min(99, Math.round(50 + val * 3)))
                return (
                  <div key={s.key} className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-text-secondary">{s.label}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[12px] font-bold"
                          style={{ fontFamily: "'JetBrains Mono', monospace", color: gradeFromPercentile(pctile).color }}>
                          {val > 0 ? '+' : ''}{val.toFixed(1)}
                        </span>
                        <GradeBadge grade={gradeFromPercentile(pctile).label} />
                      </div>
                    </div>
                    <BenchmarkGauge value={val} mlbAvg={0} min={s.min} max={s.max}
                      lowerIsBetter={false} percentile={pctile} />
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
