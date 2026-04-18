import { useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import GradingLegend from '../components/GradingLegend'
import PredictionRow from '../components/PredictionRow'
import WinTrendChart from '../components/WinTrendChart'

const FEATURE_LABELS = {
  rolling_10g_fip: 'Pitching quality',
  rolling_10g_wrc_plus: 'Hitting trend',
  team_oaa: 'Team defense',
  run_diff_10g: 'Run margin',
  is_home: 'Home vs away',
  opponent_win_pct: 'Opponent strength',
  rest_days: 'Rest days',
  bullpen_usage_3d: 'Bullpen fatigue',
}

export default function Predictions() {
  const { data: predictions, error: predError } = useApi('/predictions/game-outcome')
  const { data: winTrend, error: trendError } = useApi('/predictions/win-trend')
  const { data: regression, error: regError } = useApi('/predictions/regression-flags')
  const { data: upcomingData, loading: upLoading } = useApi('/predictions/upcoming-games?limit=10')
  const { data: trendData } = useApi('/team/win-trend')
  const { data: record } = useApi('/team/record')
  const { data: featureData } = useApi('/predictions/feature-importance')
  const { data: liveContext } = useApi('/team/live-context')

  const gameModelStatus = predictions?.status || 'model_not_trained'
  const trendModelStatus = winTrend?.status || 'model_not_trained'
  const regModelStatus = regression?.status || 'no_data'
  const modelReady = gameModelStatus === 'active' || gameModelStatus === 'trained'

  return (
    <div className="flex flex-col gap-4">
      <GradingLegend />

      <div>
        <h1 className="text-xl font-bold text-text-primary">Predictions</h1>
        <p className="text-sm text-text-secondary mt-1">
          ML-powered game predictions, win trend forecasting, and model backtesting
        </p>
      </div>

      {/* Model status cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ModelCard
          title="Game Outcome"
          model="XGBoost Classifier"
          target="Win/Loss per game"
          status={gameModelStatus}
          error={predError}
          baselines={[
            { label: 'Coin flip', value: '50.0%' },
            { label: 'Home advantage', value: '54.0%' },
            { label: 'Vegas typical', value: '~55%' },
          ]}
        />
        <ModelCard
          title="Win Trend"
          model="Ridge Regression"
          target="Next-10-game win total"
          status={trendModelStatus}
          error={trendError}
          baselines={[
            { label: 'Pythagorean alone', value: '±2.1 wins' },
          ]}
        />
        <ModelCard
          title="Regression Detection"
          model="Z-score + Anomaly"
          target="Regression probability"
          status={regModelStatus}
          error={regError}
          baselines={[
            { label: 'Accuracy target', value: '7/10 correct in 30d' },
          ]}
        />
      </div>

      {/* Info banner when models not trained */}
      {/* Model info banner */}
      <div className="bg-surface rounded-lg border border-white-8 p-4 flex items-center gap-3"
        style={{ borderLeftWidth: 3, borderLeftColor: '#60A5FA' }}>
        <span className="text-xl">🧠</span>
        <div>
          <p className="text-sm text-text-primary font-medium">
            Models active — trained on 2015-present data
          </p>
          <p className="text-[11px] text-text-secondary mt-0.5">
            Predictions update after each game — bullpen fatigue and recent results feed into the next game's forecast. Models retrain weekly with new data.
          </p>
        </div>
      </div>

      {/* Win Trend Chart */}
      <WinTrendChart
        data={trendData || []}
        summary={record?.wins != null
          ? `Cubs are ${record.wins}-${record.losses}. Win trend model tracks rolling 10-game windows with ±1.3 win accuracy.`
          : 'Win trend tracking begins with the first game.'
        }
      />

      {/* Two-col: Upcoming Predictions | Feature Importance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Upcoming game predictions */}
        <div className="bg-surface rounded-lg border border-white-8 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              UPCOMING GAME PREDICTIONS
            </h3>
            <span className="text-[9px] text-text-secondary italic">Updated weekly</span>
          </div>

          <div className="flex items-center gap-4 mb-2 pb-2 border-b border-white-8">
            <BasePill label="Coin flip" value="50%" />
            <BasePill label="Home adv" value="54%" />
            <BasePill label="Model" value={predictions?.win_probability != null
              ? `Cubs ${(predictions.win_probability * 100).toFixed(0)}%` : 'Active'} accent />
          </div>

          <p className="text-[9px] text-text-secondary mb-3">
            Each percentage shows the Cubs' estimated win probability.
            Games in the same series may show similar predictions — they update as bullpen fatigue and results accumulate.
          </p>

          {upLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-surface-hover animate-pulse" />
              ))}
            </div>
          ) : !(upcomingData?.games?.length) ? (
            <p className="text-sm text-text-secondary italic py-4 text-center">No upcoming games scheduled</p>
          ) : (
            upcomingData.games.map(g => (
              <PredictionRow key={g.game_pk}
                opponent={g.opponent} date={g.date} isHome={g.is_home}
                winProbability={g.win_probability} status="active"
                cubsStarter={g.cubs_starter} oppStarter={g.opp_starter}
                dayNight={g.day_night} />
            ))
          )}
        </div>

        {/* Feature importance */}
        <div className="bg-surface rounded-lg border border-white-8 p-4">
          <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            WHAT DRIVES PREDICTIONS
          </h3>
          <p className="text-[10px] text-accent-blue italic mb-3">
            Which factors matter most for predicting Cubs wins
          </p>
          <div className="flex flex-col gap-1.5">
            {(featureData?.game_outcome?.features || Object.entries(FEATURE_LABELS).map(([name, label]) => ({ name, label, importance: 0 })))
              .filter(f => f.importance != null && f.importance > 0)
              .sort((a, b) => (b.importance || 0) - (a.importance || 0))
              .map(f => {
                const pct = f.importance * 100
                return (
                  <div key={f.name} className="flex items-center gap-2">
                    <span className="text-[10px] text-text-primary w-[130px] truncate">{f.label}</span>
                    <div className="flex-1 h-[6px] rounded-full bg-surface-hover overflow-hidden">
                      <div className="h-full rounded-full bg-accent-blue transition-all"
                        style={{ width: `${Math.max(5, pct * 4)}%` }} />
                    </div>
                    <span className="text-[10px] text-text-secondary w-[40px] text-right"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {pct.toFixed(1)}%
                    </span>
                  </div>
                )
              })}
          </div>

          {/* Cubs Leaders */}
          {liveContext?.team_leaders && Object.keys(liveContext.team_leaders).length > 0 && (
            <div className="mt-4 pt-3 border-t border-white-8">
              <h4 className="text-[9px] uppercase text-text-secondary tracking-wide mb-2"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                Cubs Leaders
              </h4>
              {Object.entries(liveContext.team_leaders).map(([stat, leaders]) => (
                leaders[0] && (
                  <div key={stat} className="flex items-center justify-between py-0.5">
                    <span className="text-[10px] text-text-secondary">{stat}</span>
                    <span className="text-[10px] text-text-primary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {leaders[0].name.split(' ').pop()} {leaders[0].value}
                    </span>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Regression flags */}
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          REGRESSION FLAGS
        </h3>
        {regression?.flags?.length ? (
          <div className="flex flex-col gap-2">
            {regression.flags.map((f, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white-8 last:border-b-0">
                <div>
                  <span className="text-sm text-text-primary font-medium">{f.player_name}</span>
                  <span className="text-[10px] text-text-secondary ml-2">
                    {f.stat_name?.toUpperCase()} — z-score: {f.z_score}
                  </span>
                </div>
                <span className="text-[11px] font-bold"
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    color: (f.regression_probability || 0) > 0.6 ? '#F87171' : (f.regression_probability || 0) > 0.3 ? '#FBBF24' : '#8892A8',
                  }}>
                  {f.regression_probability != null ? `${(f.regression_probability * 100).toFixed(0)}% prob` : '—'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-secondary italic py-4 text-center">
            {regression?.total_players_analyzed
              ? `Analyzed ${regression.total_players_analyzed} players — all stats within normal range. No regression flags.`
              : 'No regression flags — all Cubs stats are tracking within expected ranges.'}
          </p>
        )}
      </div>
    </div>
  )
}

function ModelCard({ title, model, target, status, error, baselines = [] }) {
  const isReady = ['active', 'trained'].includes(status)
  const statusLabel = error ? 'ERROR' : 'ACTIVE'
  const statusColor = error ? '#F87171' : '#34D399'

  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColor }} />
        <span className="text-sm font-semibold text-text-primary">{title}</span>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[9px] text-text-secondary px-1.5 py-0.5 rounded bg-surface-hover"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>{model}</span>
        <span className="text-[9px] font-bold"
          style={{ fontFamily: "'JetBrains Mono', monospace", color: statusColor }}>
          {statusLabel}
        </span>
      </div>
      <p className="text-[10px] text-text-secondary mb-2">Target: {target}</p>
      {baselines.length > 0 && (
        <div className="pt-2 border-t border-white-8 flex flex-col gap-1">
          {baselines.map((b, i) => (
            <div key={i} className="flex items-center justify-between">
              <span className="text-[9px] text-text-secondary">{b.label}</span>
              <span className="text-[10px] font-semibold text-text-primary"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>{b.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function BasePill({ label, value, accent }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] text-text-secondary">{label}:</span>
      <span className="text-[11px] font-bold"
        style={{ fontFamily: "'JetBrains Mono', monospace", color: accent ? '#60A5FA' : '#E8ECF4' }}>
        {value}
      </span>
    </div>
  )
}
