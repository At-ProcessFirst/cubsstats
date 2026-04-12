# CubsEdge — ML Model Decisions

## Model 1: Game Outcome (XGBoost Classifier)

**Status:** Implemented (Phase 5)

**Target:** Win/Loss binary classification per game

**Algorithm:** XGBClassifier with 100 estimators, max_depth=4, learning_rate=0.1, subsample=0.8

**Features (8):**
| Feature | Plain English | Source |
|---------|--------------|--------|
| rolling_10g_fip | Pitching quality (10-game) | Team season FIP |
| rolling_10g_wrc_plus | Hitting trend (10-game) | Team season wRC+ |
| team_oaa | Team defense | Sum of Cubs OAA |
| run_diff_10g | Run margin (10-game) | Cumulative RS - RA over last 10 |
| is_home | Home vs away | Game location (1.0 / 0.0) |
| opponent_win_pct | Opponent strength | Opponent's current season win% |
| rest_days | Rest days | Days since last game |
| bullpen_usage_3d | Bullpen fatigue | Total RP innings in last 3 days |

**Training:** Cross-validated with 5-fold CV. Trains on 2+ seasons of historical data. Minimum 30 games required.

**Baselines:**
- Coin flip: 50%
- Home team historical advantage: ~54%
- Vegas implied: ~55%

**Persistence:** Saved via joblib to `backend/models/game_outcome.joblib`

**Retraining:** Weekly via `weekly_refresh.py`

---

## Model 2: Win Trend (Ridge Regression)

**Status:** Implemented (Phase 5)

**Target:** Next-10-game win total (0-10) ± 95% confidence interval

**Algorithm:** Ridge regression with alpha=1.0

**Features (5):**
| Feature | Plain English | Source |
|---------|--------------|--------|
| rolling_30g_pythag_wpct | Pythagorean pace (30-game) | RS^1.83 / (RS^1.83 + RA^1.83) over 30 games |
| fip_trend | Pitching trend | Linear slope of FIP over 30 games |
| wrc_plus_trend | Hitting trend | Linear slope of wRC+ over 30 games |
| roster_war | Roster quality | Placeholder (future: active roster WAR) |
| sos_remaining | Schedule difficulty remaining | Avg opponent win% for remaining games |

**Training:** 5-fold CV with MAE scoring. Minimum 15 windows needed. One row per 10-game sliding window.

**Confidence interval:** 95% CI = prediction ± 1.96 * residual_std

**Display:** "Avg error: ±X wins. Pythagorean alone: ±2.1 wins."

**Persistence:** Saved via joblib to `backend/models/win_trend.joblib` (includes residual_std)

---

## Model 3: Regression Detection (Z-score Anomaly Detection)

**Status:** Implemented (Phase 5)

**Approach:** For each Cubs player stat, compute z-score against the MLB benchmark distribution for that stat and position group.

**Z-score computation:**
1. Get MLB benchmark (mean, p25, p75) for the stat
2. Estimate std from IQR: std ≈ (p75 - p25) / 1.35
3. z = (player_value - mlb_mean) / std
4. For lower-is-better stats, negate z so positive always = "above average"

**Regression probability formula:**
- |z| >= 2.0: prob = min(0.95, 0.5 + |z| * 0.15)
- |z| >= 1.5: prob = 0.4 + (|z| - 1.5) * 0.2
- |z| < 1.5: prob = max(0, |z| * 0.25)

**Flag threshold:** |z| >= 1.5 OR regression_probability >= 0.4

**Stats analyzed:**
- Pitchers (IP >= 15): ERA, FIP, K%, BB%, Hard Hit%, Barrel%
- Hitters (PA >= 30): wRC+, wOBA, BABIP, Barrel%, Hard Hit%, O-Swing%

**Direction labels:**
- z > 1.5: "likely_decline"
- z < -1.5: "likely_improve"
- else: "toward_mean"

**Validation target:** "7 of 10 flags prove correct within 30 days"

**No persistence needed:** Z-scores computed live from current benchmarks.

---

## API Endpoints

| Endpoint | Model | Returns |
|----------|-------|---------|
| GET /api/predictions/game-outcome | XGBoost | win_probability, confidence, feature_importance |
| GET /api/predictions/win-trend | Ridge | predicted_wins, ci_lower, ci_upper, avg_error |
| GET /api/predictions/regression-flags | Z-score | flags[], total_flags, accuracy_target |
| GET /api/predictions/model-status | All | training status, metadata per model |
| GET /api/predictions/feature-importance | All | feature names + plain English labels + weights |

## Retraining Schedule

All models retrain weekly via `scripts/weekly_refresh.py` (Step 7).
- Game Outcome: Refit XGBoost on all available seasons
- Win Trend: Refit Ridge on all available sliding windows
- Regression Detection: No retraining — z-scores recompute live from benchmarks
