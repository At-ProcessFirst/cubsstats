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
  const { data: upcoming, loading: upLoading } = useApi('/team/upcoming?limit=10')
  const { data: trendData } = useApi('/team/win-trend')
  const { data: record } = useApi('/team/record')

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
      {!modelReady && (
        <div className="bg-surface rounded-lg border border-white-8 p-4 flex items-center gap-3"
          style={{ borderLeftWidth: 3, borderLeftColor: '#60A5FA' }}>
          <span className="text-xl">🧠</span>
          <div>
            <p className="text-sm text-text-primary font-medium">
              ML models are being trained
            </p>
            <p className="text-[11px] text-text-secondary mt-0.5">
              Predictions will appear after sufficient game data is collected. The Game Outcome model
              needs 30+ games, and the Win Trend model needs 40+ games to produce reliable forecasts.
              Regression detection is active and runs using z-score analysis against MLB benchmarks.
            </p>
          </div>
        </div>
      )}

      {/* Win Trend Chart */}
      <WinTrendChart
        data={trendData || []}
        summary={record?.wins != null
          ? `Cubs are ${record.wins}-${record.losses}. ${modelReady ? '' : 'ML projections will appear once models are trained.'}`
          : 'Win trend data will populate after game data is seeded.'
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
            {!modelReady && (
              <span className="text-[9px] text-text-secondary italic">Awaiting model training</span>
            )}
          </div>

          <div className="flex items-center gap-4 mb-3 pb-2 border-b border-white-8">
            <BasePill label="Coin flip" value="50%" />
            <BasePill label="Home adv" value="54%" />
            <BasePill label="Model" value={modelReady && predictions?.win_probability != null
              ? `${(predictions.win_probability * 100).toFixed(1)}%` : '—'} accent />
          </div>

          {upLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-surface-hover animate-pulse" />
              ))}
            </div>
          ) : !upcoming?.length ? (
            <p className="text-sm text-text-secondary italic py-4 text-center">No upcoming games scheduled</p>
          ) : (
            upcoming.map(g => (
              <PredictionRow key={g.game_pk}
                opponent={g.opponent} date={g.date} isHome={g.is_home}
                winProbability={null} status="model_not_trained" />
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
            Plain English labels show what each ML feature means in baseball terms
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(FEATURE_LABELS).map(([key, label]) => (
              <div key={key} className="flex items-center gap-2 py-1.5 px-3 rounded bg-surface-hover">
                <div className="w-1.5 h-6 rounded-full bg-accent-blue opacity-30" />
                <div>
                  <span className="text-[10px] text-text-primary font-medium block">{label}</span>
                  <span className="text-[8px] text-text-secondary"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}>{key}</span>
                </div>
              </div>
            ))}
          </div>
          {!modelReady && (
            <p className="text-[10px] text-text-secondary italic mt-3">
              Feature importance bars will appear after model training.
            </p>
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
                    color: f.regression_probability > 0.6 ? '#F87171' : f.regression_probability > 0.3 ? '#FBBF24' : '#8892A8',
                  }}>
                  {(f.regression_probability * 100).toFixed(0)}% prob
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-secondary italic py-4 text-center">
            {regression?.total_players_analyzed
              ? `Analyzed ${regression.total_players_analyzed} players — no significant regression flags detected.`
              : 'Regression detection will run after player benchmarks are computed.'}
          </p>
        )}
      </div>
    </div>
  )
}

function ModelCard({ title, model, target, status, error, baselines = [] }) {
  const isReady = ['active', 'trained'].includes(status)
  const statusLabel = error ? 'ERROR' : isReady ? 'ACTIVE' : 'PENDING'
  const statusColor = error ? '#F87171' : isReady ? '#34D399' : '#FBBF24'

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
