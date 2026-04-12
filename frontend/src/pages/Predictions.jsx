import { useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { formatStat } from '../utils/formatting'
import GradingLegend from '../components/GradingLegend'
import PredictionRow from '../components/PredictionRow'
import WinTrendChart from '../components/WinTrendChart'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts'

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

const MOCK_BACKTEST = [
  { month: 'Apr', accuracy: null, baseline: 50 },
  { month: 'May', accuracy: null, baseline: 50 },
  { month: 'Jun', accuracy: null, baseline: 50 },
  { month: 'Jul', accuracy: null, baseline: 50 },
  { month: 'Aug', accuracy: null, baseline: 50 },
  { month: 'Sep', accuracy: null, baseline: 50 },
]

export default function Predictions() {
  const { data: predictions } = useApi('/predictions/game-outcome')
  const { data: winTrend } = useApi('/predictions/win-trend')
  const { data: regression } = useApi('/predictions/regression-flags')
  const { data: upcoming, loading: upLoading } = useApi('/team/upcoming?limit=10')
  const { data: trendData } = useApi('/team/win-trend')
  const { data: record } = useApi('/team/record')

  const modelReady = predictions?.status !== 'model_not_trained'

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
      <div className="grid grid-cols-3 gap-3">
        <ModelCard
          title="Game Outcome"
          model="XGBoost Classifier"
          target="Win/Loss per game"
          status={predictions?.status}
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
          status={winTrend?.status}
          baselines={[
            { label: 'Pythagorean alone', value: '±2.1 wins' },
          ]}
        />
        <ModelCard
          title="Regression Detection"
          model="Z-score + Anomaly"
          target="Regression probability"
          status={regression?.status}
          baselines={[
            { label: 'Accuracy target', value: '7/10 correct in 30d' },
          ]}
        />
      </div>

      {/* Win Trend Chart */}
      <WinTrendChart
        data={trendData || []}
        summary={record?.wins != null
          ? `Cubs are ${record.wins}-${record.losses}. ML projections will appear here once the model is trained in Phase 5.`
          : 'Win trend data will populate after game data is seeded.'
        }
      />

      {/* Two-col: Upcoming Predictions | Backtesting */}
      <div className="grid grid-cols-2 gap-4">
        {/* Upcoming game predictions */}
        <div className="bg-surface rounded-lg border border-white-8 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[11px] uppercase tracking-widest text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              UPCOMING GAME PREDICTIONS
            </h3>
            {!modelReady && (
              <span className="text-[9px] text-cubs-red italic">Model pending — Phase 5</span>
            )}
          </div>

          <div className="flex items-center gap-4 mb-3 pb-2 border-b border-white-8">
            <BasePill label="Coin flip" value="50%" />
            <BasePill label="Home adv" value="54%" />
            <BasePill label="Model" value={modelReady ? `${(predictions.win_probability * 100).toFixed(1)}%` : '—'} accent />
          </div>

          {upLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-surface-hover animate-pulse" />
              ))}
            </div>
          ) : !upcoming?.length ? (
            <p className="text-sm text-text-secondary italic py-4 text-center">No upcoming games</p>
          ) : (
            upcoming.map(g => (
              <PredictionRow key={g.game_pk}
                opponent={g.opponent} date={g.date} isHome={g.is_home}
                winProbability={null} status="model_not_trained" />
            ))
          )}
        </div>

        {/* Backtesting visualization */}
        <div className="bg-surface rounded-lg border border-white-8 p-4">
          <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            MODEL BACKTESTING
          </h3>

          {!modelReady ? (
            <div className="flex flex-col items-center justify-center h-[250px] gap-3">
              <div className="w-12 h-12 rounded-full bg-surface-hover flex items-center justify-center">
                <span className="text-2xl">📊</span>
              </div>
              <p className="text-sm text-text-secondary text-center">
                Backtesting results will appear after model training in Phase 5
              </p>
              <p className="text-[10px] text-text-secondary italic text-center max-w-[280px]">
                We'll show monthly accuracy vs baseline (coin flip at 50%), precision/recall,
                and feature importance rankings
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={MOCK_BACKTEST} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="month"
                  tick={{ fontSize: 10, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} tickLine={false} />
                <YAxis domain={[40, 70]}
                  tick={{ fontSize: 10, fill: '#8892A8', fontFamily: "'JetBrains Mono'" }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} tickLine={false} />
                <Tooltip contentStyle={{
                  backgroundColor: '#141B2D', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8, fontSize: 11, fontFamily: "'JetBrains Mono'"
                }} />
                <Bar dataKey="accuracy" radius={[3, 3, 0, 0]} name="Model Accuracy %">
                  {MOCK_BACKTEST.map((e, i) => (
                    <Cell key={i} fill={e.accuracy ? (e.accuracy >= 55 ? '#34D399' : '#FBBF24') : '#1A2340'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Feature importance */}
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        <h3 className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          FEATURE IMPORTANCE — WHAT DRIVES PREDICTIONS
        </h3>
        <p className="text-[10px] text-accent-blue italic mb-3">
          Plain English labels show what each ML feature means in baseball terms
        </p>
        <div className="grid grid-cols-4 gap-3">
          {Object.entries(FEATURE_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 py-1.5 px-3 rounded bg-surface-hover">
              <div className="w-1.5 h-6 rounded-full bg-accent-blue opacity-30" />
              <div>
                <span className="text-[10px] text-text-primary font-medium block">{label}</span>
                <span className="text-[8px] text-text-secondary" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{key}</span>
              </div>
            </div>
          ))}
        </div>
        {!modelReady && (
          <p className="text-[10px] text-text-secondary italic mt-3">
            Feature importance bars will appear after model training. Currently showing feature definitions.
          </p>
        )}
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
              <div key={i} className="text-sm text-text-primary">{JSON.stringify(f)}</div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-secondary italic py-4 text-center">
            Regression detection model outputs will appear here after Phase 5 training.
            Target: 7 of 10 flags prove correct within 30 days.
          </p>
        )}
      </div>
    </div>
  )
}

function ModelCard({ title, model, target, status, baselines = [] }) {
  const isReady = status !== 'model_not_trained'
  return (
    <div className="bg-surface rounded-lg border border-white-8 p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: isReady ? '#34D399' : '#F87171' }} />
        <span className="text-sm font-semibold text-text-primary">{title}</span>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[9px] text-text-secondary px-1.5 py-0.5 rounded bg-surface-hover"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}>{model}</span>
        <span className="text-[9px] font-bold"
          style={{ fontFamily: "'JetBrains Mono', monospace", color: isReady ? '#34D399' : '#F87171' }}>
          {isReady ? 'ACTIVE' : 'PENDING'}
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
