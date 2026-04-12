# CubsEdge — Cubs Sabermetrics ML Dashboard

## What This Is
A full-stack web app that tracks Chicago Cubs sabermetric metrics, detects performance divergences, and uses ML models to predict team win/loss trends. Every stat is dynamically benchmarked against live MLB averages with percentile rankings, grade badges, and plain English explanations so anyone — from a data scientist to a casual fan — can understand what the numbers mean.

Research/learning project deployed as a public web app.

---

## Tech Stack
- **Backend**: Python 3.11+ / FastAPI
- **Data Ingestion**: pybaseball (pulls from Statcast, FanGraphs, Baseball Reference)
- **ML**: scikit-learn, XGBoost, pandas, numpy
- **Database**: SQLite for v1 (portable, zero-config; migrate to PostgreSQL later if needed)
- **Frontend**: React + Vite + Tailwind CSS + Recharts + Chart.js
- **Deployment**: Railway (backend API + scheduled jobs) or Render; Vercel (frontend)

---

## Project Structure
```
cubsedge/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry
│   │   ├── routers/
│   │   │   ├── pitching.py          # Pitching metrics endpoints
│   │   │   ├── hitting.py           # Hitting metrics endpoints
│   │   │   ├── defense.py           # Defensive metrics endpoints
│   │   │   ├── team.py              # Team-level & win prediction endpoints
│   │   │   ├── predictions.py       # ML prediction endpoints
│   │   │   └── benchmarks.py        # Dynamic benchmark endpoints
│   │   ├── services/
│   │   │   ├── ingestion.py         # pybaseball data pull + transform
│   │   │   ├── features.py          # Feature engineering pipeline
│   │   │   ├── ml_engine.py         # Model training, evaluation, prediction
│   │   │   ├── benchmark_engine.py  # MLB benchmark computation + percentiles
│   │   │   └── divergence_engine.py # Divergence detection with benchmark context
│   │   ├── models/
│   │   │   ├── schemas.py           # Pydantic models
│   │   │   └── database.py          # SQLite/SQLAlchemy setup
│   │   └── config.py
│   ├── scripts/
│   │   ├── seed_historical.py       # One-time: load 2021-2025 Cubs + league data
│   │   ├── seed_benchmarks.py       # One-time: compute baseline benchmarks from prior season
│   │   └── daily_update.py          # Cron: pull latest game data + refresh benchmarks weekly
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        # Main overview (see Dashboard Design below)
│   │   │   ├── PitchingLab.jsx      # Pitcher deep-dives (see Pitching Lab Design below)
│   │   │   ├── HittingLab.jsx       # Hitter deep-dives (mirror Pitching Lab patterns)
│   │   │   ├── DefenseLab.jsx       # OAA, DRS, framing metrics with benchmarks
│   │   │   ├── Predictions.jsx      # ML win/loss trends, backtesting, model performance
│   │   │   └── Divergences.jsx      # Full alert feed with benchmark context
│   │   ├── components/
│   │   │   ├── BenchmarkGauge.jsx   # Reusable: gauge bar with MLB avg marker + percentile
│   │   │   ├── GradeBadge.jsx       # Reusable: Elite/Above Avg/Avg/Below Avg/Poor badge
│   │   │   ├── MetricCard.jsx       # Reusable: stat card with benchmark, grade, plain English
│   │   │   ├── PlayerStatRow.jsx    # Reusable: player row with stat, percentile, bar, explanation
│   │   │   ├── PitchArsenalCard.jsx # Pitch-type benchmarked card
│   │   │   ├── DivergenceAlert.jsx  # Alert row with percentile context on both stats
│   │   │   ├── WinTrendChart.jsx    # Multi-line: actual, ML predicted, Pythagorean, .500 pace
│   │   │   ├── VelocityTrend.jsx    # Per-pitcher velo chart with MLB avg line
│   │   │   ├── FatigueChart.jsx     # Within-game velo by pitch count bucket
│   │   │   ├── PercentileBar.jsx    # Horizontal percentile ranking bar
│   │   │   ├── PredictionRow.jsx    # Game prediction with win%, home adv factor
│   │   │   └── VerdictBox.jsx       # Bottom-line plain English summary box
│   │   ├── hooks/
│   │   │   ├── useApi.js
│   │   │   └── useBenchmarks.js     # Hook to fetch + cache current MLB benchmarks
│   │   ├── utils/
│   │   │   ├── grading.js           # Percentile-to-grade logic
│   │   │   └── formatting.js        # Stat formatting, delta display, +/- prefix
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── docs/
│   └── model_decisions.md           # Document ML decisions and results
└── CLAUDE.md
```

---

## Design System

### Aesthetic
Dark theme, data-dense. Bloomberg Terminal meets ESPN+.

### Colors
```
Navy background:    #0E1629
Surface panels:     #141B2D
Surface hover:      #1A2340
Cubs blue accent:   #0E3386
Cubs red:           #CC3433
Text primary:       #E8ECF4
Text secondary:     #8892A8
Border:             rgba(255,255,255, 0.08)

Signal colors:
  Green (elite/positive):   #34D399
  Light green (above avg):  #6EE7B7
  Amber (watch/below avg):  #FBBF24
  Red (regress/poor):       #F87171
  Blue accent:              #60A5FA
  Purple:                   #A78BFA
  Cyan:                     #22D3EE
  Pink:                     #F472B6
```

### Typography
- **Data/numbers**: JetBrains Mono (monospace) — all stat values, percentiles, deltas
- **Labels/prose**: DM Sans (sans-serif) — all headings, explanations, plain English text

### Grading System (applied to EVERY stat, EVERY page)
| Grade | Percentile | Color | Badge Background |
|-------|-----------|-------|-----------------|
| Elite | >= 90th | #34D399 | rgba(52,211,153, 0.20) |
| Above avg | >= 75th | #6EE7B7 | rgba(110,231,183, 0.12) |
| Average | 25th-75th | #8892A8 | rgba(255,255,255, 0.08) |
| Below avg | <= 25th | #FBBF24 | rgba(251,191,36, 0.15) |
| Poor | <= 10th | #F87171 | rgba(248,113,113, 0.15) |

For stats where lower is better (ERA, BB%, Hard Hit%, Barrel%), invert the percentile before assigning the grade.

### Cubs Logo
44px circle, Cubs blue (#0E3386) fill, 3px Cubs red (#CC3433) border, white bold "C" centered. Replace with official SVG asset when available.

---

## Dynamic Benchmark System (CRITICAL — applies to entire app)

### Rule: No stat appears anywhere without its MLB benchmark context. If a number shows without a percentile, grade, and plain English explanation, that is a bug.

### Database Tables
```sql
CREATE TABLE benchmarks (
    id INTEGER PRIMARY KEY,
    season INTEGER,
    stat_name TEXT,
    position_group TEXT,       -- 'SP', 'RP', 'ALL_HITTERS', 'C', 'IF', 'OF'
    mean REAL,
    median REAL,
    p10 REAL,
    p25 REAL,
    p75 REAL,
    p90 REAL,
    sample_size INTEGER,
    updated_at TIMESTAMP
);

CREATE TABLE pitch_type_benchmarks (
    id INTEGER PRIMARY KEY,
    season INTEGER,
    pitch_type TEXT,           -- 'FF', 'SL', 'CU', 'FC', 'CH', 'FS', 'SI'
    stat_name TEXT,            -- 'avg_velo', 'whiff_pct', 'vert_movement', 'horiz_break'
    mean REAL,
    p25 REAL,
    p75 REAL,
    p90 REAL,
    sample_size INTEGER,
    updated_at TIMESTAMP
);

CREATE TABLE player_benchmarks (
    id INTEGER PRIMARY KEY,
    player_id INTEGER,
    stat_name TEXT,
    value REAL,
    percentile INTEGER,
    grade TEXT,
    mlb_avg REAL,
    delta REAL,
    updated_at TIMESTAMP
);
```

### Benchmark Pipeline (benchmark_engine.py)
1. **Preseason load** (`seed_benchmarks.py`): Pull prior full-season league averages via pybaseball (`fg_pitching_data`, `fg_batting_data`, Statcast pitch-level) for qualified players. Compute mean, median, percentile breakpoints. Store in `benchmarks` and `pitch_type_benchmarks`.
2. **In-season rolling update** (weekly via `daily_update.py`):
   - Before ~30 team games: 100% prior season benchmarks
   - 30-80 team games: blend 70% current / 30% prior
   - After ~80 team games: 100% current season
3. **Daily percentile refresh**: Compute each Cubs player's percentile rank against all qualified MLB players at that position. Update `player_benchmarks`.
4. **Pitch-type refresh** (weekly): Recompute MLB averages per pitch type from Statcast pitch-level data.

### Benchmark API Endpoints
```
GET /api/benchmarks/current                    → All current MLB avgs by stat + position
GET /api/benchmarks/percentile?stat=K_pct&value=28.4&position=SP   → { percentile, grade, mlb_avg, delta }
GET /api/benchmarks/player/{player_id}         → All benchmarked stats for a player
GET /api/benchmarks/pitch-type/{pitch_type}    → MLB avgs for that pitch type
```

---

## Frontend Benchmark Components

### BenchmarkGauge.jsx
Reusable horizontal gauge:
- Gray track (full width, 6-8px tall, rounded)
- Gray tick at MLB average position (2px wide, labeled "MLB X.XX")
- Colored circle at player position (8-12px, color = grade color)
- Below: delta text ("1.09 below avg") + percentile ("72nd percentile")
- Props: `value`, `mlbAvg`, `min`, `max`, `lowerIsBetter`, `percentile`, `grade`

### GradeBadge.jsx
Small pill: "ELITE" / "ABOVE AVG" / "AVG" / "BELOW AVG" / "POOR"
- JetBrains Mono, 8-9px, font-weight 600
- Color + background from grading table
- Props: `grade`

### MetricCard.jsx (dashboard top row)
- Stat label (uppercase monospace, 9px, dim)
- Plain English explanation (italic, blue accent, 10px)
- Value (20-22px bold monospace, grade-colored) + GradeBadge inline
- Subtitle with MLB avg reference
- BenchmarkGauge
- Delta + percentile footer
- Props: `label`, `plainEnglish`, `value`, `mlbAvg`, `percentile`, `grade`, `subtitle`, `min`, `max`, `lowerIsBetter`

### PlayerStatRow.jsx (pitching/hitting panels)
- Player name | stat value + tiny percentile | comparison value + tiny percentile | progress bar
- Below: plain English one-liner explaining gap meaning
- Props: `name`, `stat1`, `stat1Pctile`, `stat2`, `stat2Pctile`, `barFill`, `barColor`, `explanation`

### PitchArsenalCard.jsx
- Colored dot + pitch name + role description
- 4-column mini-stat grid: Velo (vs pitch-type avg), Usage%, Whiff% (vs avg), Movement (vs avg)
- Each mini-stat shows value, MLB avg, and delta with color
- Plain English one-liner
- Props: `pitchType`, `color`, `role`, `stats[]` (each with value, mlbAvg, delta)

### VerdictBox.jsx
- Blue-tinted background box
- Title: "Bottom line — [Name]"
- Body: plain English summary referencing key benchmarks and actionable conclusion
- Props: `playerName`, `verdictText`, `verdictGrade`

---

## Core Metrics Reference

### Pitching (per pitcher + team aggregate)
| Stat | Plain English | Better |
|------|--------------|--------|
| ERA | Runs allowed per 9 innings | Lower |
| FIP | Pitching quality removing luck and defense | Lower |
| xFIP | FIP normalizing home run luck | Lower |
| xERA | Expected ERA from batted ball quality | Lower |
| K% | How often he strikes batters out | Higher |
| BB% | How often he gives free bases | Lower |
| K-BB% | Strikeouts minus walks — best quick measure | Higher |
| SwStr% | How often batters swing and miss | Higher |
| CSW% | Called strikes + whiffs — stuff quality score | Higher |
| Hard Hit% against | % of batted balls hit 95+ mph off him | Lower |
| Barrel% against | % of perfect-contact damage balls | Lower |
| Velocity | Fastball speed (per start + within game) | Higher |
| Spin rate | Ball spin by pitch type | Context |

### Hitting (per batter + team aggregate)
| Stat | Plain English | Better |
|------|--------------|--------|
| wRC+ | Overall hitting value (100 = exactly average) | Higher |
| wOBA | Weighted on-base average — values each outcome by run value | Higher |
| xBA | Expected batting avg from contact quality | Higher |
| xSLG | Expected slugging from contact quality | Higher |
| xwOBA | Expected wOBA from exit velo + launch angle | Higher |
| Barrel% | % of balls at ideal speed + angle for damage | Higher |
| Hard Hit% | % of balls hit 95+ mph | Higher |
| Avg Exit Velo | How hard he hits the ball on average | Higher |
| O-Swing% | How often he chases bad pitches | Lower |
| Z-Contact% | How often he makes contact on strikes | Higher |
| Chase Rate | How often he swings at bad pitches | Lower |
| Sprint Speed | Running speed (ft/sec) | Higher |
| BsR | Baserunning value in runs | Higher |
| BABIP | Batting avg on balls in play — luck indicator | Context |

### Defense
| Stat | Plain English | Better |
|------|--------------|--------|
| OAA | Outs Above Average — fielding value (0 = avg) | Higher |
| DRS | Defensive Runs Saved vs average fielder | Higher |
| Framing Runs | Extra strikes catcher steals from umpire | Higher |

---

## Divergence Detection (divergence_engine.py)

### Thresholds
```python
DIVERGENCE_THRESHOLDS = {
    "era_fip_gap": 0.75,
    "ba_xba_gap": 0.030,
    "woba_xwoba_gap": 0.025,
    "babip_xbabip_gap": 0.040,
    "velo_drop_mph": 1.5,
    "barrel_babip_diverge": True,
}
```

### Alert Format
Each alert includes: badge (BREAKOUT/REGRESS/WATCH/INJURY), player name, both stat values with individual percentile ranks, MLB avg gap, and plain English explanation of what will likely happen.

---

## ML Models

### Model 1: Game Outcome (XGBoost classifier)
Features: Rolling 10-game team FIP, wRC+, OAA, run diff, home/away, opponent strength, rest days, bullpen usage last 3 days.
Target: Win/Loss. Display with baselines: "Coin flip = 50%. Vegas ~55%. Our model: X%."

### Model 2: Win Trend (Ridge regression → LSTM)
Features: Rolling 30-game Pythagorean W%, FIP trend, wRC+ trend, roster WAR, SOS remaining.
Target: Next-10-game win total ± CI. Display: "Avg error: ±X wins. Pythagorean alone: ±Y."

### Model 3: Regression Detection (z-score + anomaly detection)
Features: Current stats vs career norms + vs MLB benchmarks. Output: regression probability. Display: "X of 10 flags prove correct within 30 days."

### Feature Importance Display
Plain English labels: "Rolling FIP" → "Pitching quality", "wRC+ trend" → "Hitting trend", "Run differential" → "Run margin", "Bullpen leverage" → "Bullpen fatigue", "Home/away" → "Home vs away"

---

## Win Trend Chart (WinTrendChart.jsx)

Lines:
1. Actual cumulative wins (solid blue, dots)
2. ML predicted wins (dashed green)
3. Pythagorean expected wins (dashed gold)
4. .500 pace (light gray dashed — average team baseline)
5. Projected range (shaded blue band after current game, CI)

Legend above. Y-axis: "Cumulative wins". Below chart: plain English summary.

---

## Dashboard Page Layout

1. Header: Cubs logo + CUBSEDGE + nav tabs
2. Grading legend bar (all 5 grades + "Benchmarks update weekly from live MLB data")
3. Top metrics row (5-col): Record, Pythag W-L, Team wRC+, Team FIP, Run Diff — full MetricCard with benchmarks
4. Win trend chart (full width)
5. Middle row (2-col): Divergence Alerts + Game Predictions
6. Bottom row (3-col): Pitching summary + Hitting summary + Defense & Model Quality

---

## Pitching Lab Page Layout

1. Header + nav (Pitching lab active)
2. Grading legend bar
3. Page title + explanation
4. Pitcher tabs with status badges
5. Profile header (avatar + name + details)
6. Two-col top: Performance benchmarks (full BenchmarkGauge per stat) | Pitch arsenal (per-pitch-type benchmarks)
7. Three-col bottom: Velocity trend (with MLB avg line) | Recent starts (with MLB avg start reference) | Percentile rankings (all stats sorted)
8. Verdict box (plain English conclusion)

---

## Hitting Lab Page Layout
Mirror Pitching Lab: hitter tabs, profile header, performance benchmarks, recent games, percentile rankings, verdict box.

---

## Data Pipeline

1. `seed_historical.py` — Load 2021-2025 Cubs + ALL MLB player data for benchmarks
2. `seed_benchmarks.py` — Compute baseline benchmark tables from 2025 full-season
3. `daily_update.py` — Pull yesterday's data, refresh percentiles daily, refresh league benchmarks weekly, retrain models weekly

### pybaseball Functions
```python
from pybaseball import (
    team_batting, team_pitching, schedule_and_record,
    fg_pitching_data, fg_batting_data,
    statcast, statcast_pitcher,
    playerid_lookup, batting_stats, pitching_stats
)
```

Cache aggressively. Never re-pull same date range. Statcast available ~24hr after games. Run daily at 6 AM CT.

---

## Environment Variables
```
DATABASE_URL=sqlite:///./cubsedge.db
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
```

## Commands
```bash
cd backend && pip install -r requirements.txt
python scripts/seed_historical.py
python scripts/seed_benchmarks.py
uvicorn app.main:app --reload

cd frontend && npm install && npm run dev
```

---

## Implementation Order

### Phase 1: Data + Benchmarks
1. FastAPI backend + SQLite + SQLAlchemy (including benchmark tables)
2. Ingestion service — Cubs data AND league-wide data
3. Seed 2024-2025 historical (Cubs + all MLB)
4. Build benchmark_engine.py
5. Run seed_benchmarks.py
6. API endpoints: metrics + benchmarks

### Phase 2: Frontend Foundation
7. Scaffold React + Vite + Tailwind
8. Build reusable components FIRST: BenchmarkGauge, GradeBadge, MetricCard, PlayerStatRow, VerdictBox, PitchArsenalCard
9. Build grading + formatting utilities
10. Build useBenchmarks hook

### Phase 3: Dashboard
11. Dashboard page with all panels
12. Win Trend Chart
13. Divergence alerts with benchmark context
14. Game predictions
15. Summary panels

### Phase 4: Deep-Dive Pages
16. Pitching Lab (full profiles, arsenal, velocity, fatigue, verdicts)
17. Hitting Lab (mirror patterns)
18. Defense Lab
19. Divergences page
20. Predictions page with backtesting

### Phase 5: ML Pipeline
21. Feature engineering
22. Game Outcome model (XGBoost)
23. Win Trend model (Ridge)
24. Regression Detection model
25. Wire to frontend
26. Weekly retrain schedule

### Phase 6: Deploy
27. Dockerize backend
28. Deploy backend (Railway/Render)
29. Deploy frontend (Vercel)
30. Daily update cron + weekly benchmark refresh cron

---

## Non-Negotiable Rules
1. Every stat gets a benchmark. No exceptions. No page is exempt.
2. Plain English explanations are a core feature, not nice-to-have.
3. The grading legend bar appears on every page.
4. Benchmarks are dynamic — computed from live MLB data, never hardcoded.
5. Pitch-type stats are compared against their pitch-type cohort, not all pitches.
6. Document all model decisions in /docs/model_decisions.md.
