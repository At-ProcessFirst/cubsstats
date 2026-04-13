#!/usr/bin/env python3
"""
diagnose.py — Print full database diagnostics before making any changes.

Usage:
    cd backend
    python -m scripts.diagnose
"""

import os
import sys

sys.path.insert(0, ".")

from sqlalchemy import text, inspect
from app.models.database import SessionLocal, engine, init_db

init_db()
db = SessionLocal()
inspector = inspect(engine)

# 1. Print ALL column names for every table
print("=" * 60)
print("TABLE SCHEMAS")
print("=" * 60)
for table in sorted(inspector.get_table_names()):
    columns = [col['name'] for col in inspector.get_columns(table)]
    print(f"\n{table}: {columns}")

# 2. Check pitcher_season_stats for K and BB data
print("\n\n" + "=" * 60)
print("PITCHER SEASON STATS SAMPLE (2026)")
print("=" * 60)
row = db.execute(text("SELECT * FROM pitcher_season_stats WHERE season=2026 LIMIT 1")).fetchone()
if row:
    print(dict(row._mapping))
else:
    print("NO 2026 PITCHER SEASON STATS")
count = db.execute(text("SELECT COUNT(*) FROM pitcher_season_stats WHERE season=2026")).scalar()
print(f"Total 2026 pitcher season stats: {count}")
cubs = db.execute(text("SELECT COUNT(*) FROM pitcher_season_stats WHERE season=2026 AND team='CHC'")).scalar()
print(f"Cubs 2026 pitcher season stats: {cubs}")

# 3. Check hitter_season_stats sample
print("\n\n" + "=" * 60)
print("HITTER SEASON STATS SAMPLE (2026)")
print("=" * 60)
row = db.execute(text("SELECT * FROM hitter_season_stats WHERE season=2026 LIMIT 1")).fetchone()
if row:
    print(dict(row._mapping))
else:
    print("NO 2026 HITTER SEASON STATS")
count = db.execute(text("SELECT COUNT(*) FROM hitter_season_stats WHERE season=2026")).scalar()
print(f"Total 2026 hitter season stats: {count}")
cubs = db.execute(text("SELECT COUNT(*) FROM hitter_season_stats WHERE season=2026 AND team='CHC'")).scalar()
print(f"Cubs 2026 hitter season stats: {cubs}")

# 4. Check pitcher_game_stats
print("\n\n" + "=" * 60)
print("PITCHER GAME STATS")
print("=" * 60)
for season in [2024, 2025, 2026]:
    count = db.execute(text(f"SELECT COUNT(*) FROM pitcher_game_stats WHERE season={season}")).scalar()
    print(f"  {season}: {count} rows")
if db.execute(text("SELECT COUNT(*) FROM pitcher_game_stats WHERE season=2026")).scalar() > 0:
    row = db.execute(text("SELECT * FROM pitcher_game_stats WHERE season=2026 LIMIT 1")).fetchone()
    print(f"  Sample: {dict(row._mapping)}")

# 5. Check hitter_game_stats
print("\n\n" + "=" * 60)
print("HITTER GAME STATS")
print("=" * 60)
for season in [2024, 2025, 2026]:
    count = db.execute(text(f"SELECT COUNT(*) FROM hitter_game_stats WHERE season={season}")).scalar()
    print(f"  {season}: {count} rows")

# 6. Check benchmarks
print("\n\n" + "=" * 60)
print("BENCHMARKS")
print("=" * 60)
count = db.execute(text("SELECT COUNT(*) FROM benchmarks")).scalar()
print(f"Total benchmarks: {count}")
rows = db.execute(text("SELECT season, stat_name, position_group, mean, p25, p75, p90, sample_size FROM benchmarks ORDER BY season DESC, stat_name LIMIT 15")).fetchall()
for r in rows:
    print(f"  {dict(r._mapping)}")

# 7. Check player_benchmarks
print("\n\n" + "=" * 60)
print("PLAYER BENCHMARKS")
print("=" * 60)
count = db.execute(text("SELECT COUNT(*) FROM player_benchmarks")).scalar()
print(f"Total player benchmarks: {count}")
if count > 0:
    rows = db.execute(text("SELECT * FROM player_benchmarks LIMIT 5")).fetchall()
    for r in rows:
        print(f"  {dict(r._mapping)}")

# 8. Check defense_season_stats
print("\n\n" + "=" * 60)
print("DEFENSE SEASON STATS")
print("=" * 60)
count = db.execute(text("SELECT COUNT(*) FROM defense_season_stats")).scalar()
print(f"Total defense stats: {count}")
if count > 0:
    row = db.execute(text("SELECT * FROM defense_season_stats LIMIT 1")).fetchone()
    print(f"  Sample: {dict(row._mapping)}")

# 9. Check team_season_stats
print("\n\n" + "=" * 60)
print("TEAM SEASON STATS")
print("=" * 60)
rows = db.execute(text("SELECT * FROM team_season_stats WHERE team='CHC' ORDER BY season")).fetchall()
for r in rows:
    d = dict(r._mapping)
    print(f"  {d['season']}: W={d.get('wins')} L={d.get('losses')} ERA={d.get('team_era')} FIP={d.get('team_fip')} K%={d.get('team_k_pct')} BB%={d.get('team_bb_pct')} wRC+={d.get('team_wrc_plus')} RS={d.get('runs_scored')} RA={d.get('runs_allowed')}")

# 10. Check model files
print("\n\n" + "=" * 60)
print("MODEL FILES")
print("=" * 60)
model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
abs_model_dir = os.path.abspath(model_dir)
print(f"Model directory: {abs_model_dir}")
if os.path.exists(abs_model_dir):
    files = os.listdir(abs_model_dir)
    print(f"Files: {files}")
    for f in files:
        path = os.path.join(abs_model_dir, f)
        size = os.path.getsize(path)
        print(f"  {f}: {size} bytes")
else:
    print("models/ directory does not exist")

# 11. Check model_status table
print("\n\n" + "=" * 60)
print("MODEL STATUS TABLE")
print("=" * 60)
try:
    rows = db.execute(text("SELECT * FROM model_status")).fetchall()
    print(f"Rows: {len(rows)}")
    for r in rows:
        print(f"  {dict(r._mapping)}")
except Exception as e:
    print(f"model_status table error: {e}")

# 12. Check statcast_pitches
print("\n\n" + "=" * 60)
print("STATCAST PITCHES")
print("=" * 60)
count = db.execute(text("SELECT COUNT(*) FROM statcast_pitches")).scalar()
print(f"Total statcast pitches: {count}")

# 13. Check games
print("\n\n" + "=" * 60)
print("GAMES")
print("=" * 60)
for season in [2024, 2025, 2026]:
    total = db.execute(text(f"SELECT COUNT(*) FROM games WHERE season={season}")).scalar()
    final = db.execute(text(f"SELECT COUNT(*) FROM games WHERE season={season} AND status='final' AND (home_team='CHC' OR away_team='CHC')")).scalar()
    print(f"  {season}: {total} total, {final} final Cubs games")

# 14. Check players
print("\n\n" + "=" * 60)
print("PLAYERS")
print("=" * 60)
total = db.execute(text("SELECT COUNT(*) FROM players")).scalar()
cubs = db.execute(text("SELECT COUNT(*) FROM players WHERE is_cubs=true")).scalar()
print(f"Total players: {total}, Cubs: {cubs}")

# 15. Check editorials
print("\n\n" + "=" * 60)
print("EDITORIALS")
print("=" * 60)
count = db.execute(text("SELECT COUNT(*) FROM editorials")).scalar()
print(f"Total editorials: {count}")
if count > 0:
    rows = db.execute(text("SELECT id, editorial_type, title, LENGTH(body) as body_len FROM editorials ORDER BY created_at DESC LIMIT 5")).fetchall()
    for r in rows:
        print(f"  {dict(r._mapping)}")

db.close()
print("\n\nDIAGNOSTICS COMPLETE")
