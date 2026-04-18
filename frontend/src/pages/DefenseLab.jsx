import { useApi } from '../hooks/useApi'
import GradingLegend from '../components/GradingLegend'

export default function DefenseLab() {
  const { data, loading } = useApi('/defense/fielding')
  const players = data?.players || []

  // Compute team totals
  const totals = players.reduce((acc, p) => ({
    total_chances: acc.total_chances + (p.total_chances || 0),
    putouts: acc.putouts + (p.putouts || 0),
    assists: acc.assists + (p.assists || 0),
    errors: acc.errors + (p.errors || 0),
    double_plays: acc.double_plays + (p.double_plays || 0),
  }), { total_chances: 0, putouts: 0, assists: 0, errors: 0, double_plays: 0 })

  const teamFldPct = totals.total_chances > 0
    ? ((totals.total_chances - totals.errors) / totals.total_chances).toFixed(3)
    : '.000'

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Defense Lab</h1>
        <p className="text-sm text-text-secondary mt-1">
          Cubs fielding stats by position — errors, assists, and fielding percentage
        </p>
      </div>

      {/* Team summary cards */}
      {players.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryCard label="Team Fielding %" value={teamFldPct} />
          <SummaryCard label="Total Errors" value={totals.errors} />
          <SummaryCard label="Double Plays" value={totals.double_plays} />
          <SummaryCard label="Total Assists" value={totals.assists} />
        </div>
      )}

      {/* Metric legend */}
      <div className="bg-surface rounded-lg border border-white-8 px-4 py-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {[
          ['Fld%', 'Fielding Percentage'],
          ['TC', 'Total Chances'],
          ['PO', 'Putouts'],
          ['A', 'Assists'],
          ['E', 'Errors'],
          ['DP', 'Double Plays'],
        ].map(([abbr, full]) => (
          <span key={abbr} className="text-[10px] text-text-secondary">
            <span className="font-semibold text-text-primary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{abbr}</span>
            {' = '}{full}
          </span>
        ))}
      </div>

      {/* Fielding stats table */}
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          FIELDING BY PLAYER
        </h3>

        {loading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-6 rounded bg-surface-hover animate-pulse"
                style={{ width: `${60 + Math.random() * 40}%` }} />
            ))}
          </div>
        ) : !players.length ? (
          <p className="text-sm text-text-secondary italic py-4 text-center">
            Fielding data updates after games are played
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white-8">
                  {['Player', 'Pos', 'G', 'Inn', 'TC', 'PO', 'A', 'E', 'Fld%', 'DP'].map(h => (
                    <th key={h} className="text-[10px] uppercase text-text-secondary pb-2 pr-3 whitespace-nowrap font-semibold"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {players.map((p, i) => (
                  <tr key={`${p.player_id}-${p.position}-${i}`}
                    className={`border-b border-white-8 last:border-b-0 hover:bg-surface-hover transition-colors ${i % 2 === 1 ? 'bg-white/[0.02]' : ''}`}>
                    <td className="py-1.5 pr-3 text-sm text-text-primary font-medium whitespace-nowrap">
                      {p.name}
                    </td>
                    <td className="py-1.5 pr-3 text-[11px] text-text-secondary"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {p.position}
                    </td>
                    <NumCell value={p.games} />
                    <td className="py-1.5 pr-3 text-[11px] text-text-primary"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {p.innings}
                    </td>
                    <NumCell value={p.total_chances} />
                    <NumCell value={p.putouts} />
                    <NumCell value={p.assists} />
                    <NumCell value={p.errors} highlight={p.errors > 0} />
                    <td className="py-1.5 pr-3 text-[11px] font-semibold"
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        color: parseFloat(p.fielding_pct) >= 0.990 ? '#34D399'
                          : parseFloat(p.fielding_pct) >= 0.970 ? '#8892A8' : '#F87171',
                      }}>
                      {p.fielding_pct}
                    </td>
                    <NumCell value={p.double_plays} />
                  </tr>
                ))}

                {/* Team totals row */}
                <tr className="border-t-2 border-white-8 font-bold bg-white/[0.03]">
                  <td className="py-2.5 pr-3 text-sm text-text-primary font-bold">Team Total</td>
                  <td className="py-2 pr-3" />
                  <td className="py-2 pr-3" />
                  <td className="py-2 pr-3" />
                  <NumCell value={totals.total_chances} bold />
                  <NumCell value={totals.putouts} bold />
                  <NumCell value={totals.assists} bold />
                  <NumCell value={totals.errors} bold highlight={totals.errors > 0} />
                  <td className="py-2 pr-3 text-[11px] font-bold text-text-primary"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {teamFldPct}
                  </td>
                  <NumCell value={totals.double_plays} bold />
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value }) {
  return (
    <div className="bg-surface rounded-lg border border-white-8 p-3">
      <span className="text-[9px] uppercase tracking-widest text-text-secondary block mb-1"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}>{label}</span>
      <span className="text-[20px] md:text-[24px] font-bold text-text-primary"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
    </div>
  )
}

function NumCell({ value, bold, highlight }) {
  return (
    <td className={`py-1.5 pr-3 text-[11px] ${bold ? 'font-bold' : ''}`}
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        color: highlight ? '#F87171' : '#E8ECF4',
      }}>
      {value ?? 0}
    </td>
  )
}
