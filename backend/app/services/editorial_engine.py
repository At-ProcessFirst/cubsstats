"""
Editorial engine — generates analyst-voice editorials by calling the Claude API
with structured prompts built from current analytics state.

Four editorial types:
  1. Daily Takeaway — post-game analysis
  2. Weekly State — Monday season overview
  3. Player Spotlight — triggered by divergence flags
  4. Prediction Recap — weekly model performance review
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import (
    Editorial, Game, TeamSeasonStats, PitcherSeasonStats,
    HitterSeasonStats, DivergenceAlert, Player, PlayerBenchmark,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# System prompt — defines the analyst voice
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the CubsStats analyst — a sharp, data-driven baseball writer who covers the Chicago Cubs.

Your voice:
- Confident but not arrogant. You back every claim with a specific stat and its MLB percentile.
- You write for an audience that ranges from casual fans to data scientists. Lead with the insight, support with numbers.
- When you cite a stat, format it precisely: "3.42 ERA (72nd percentile)" or "wRC+ of 118 (above average)".
- You always explain what a stat means in plain English on first use.
- You flag when surface stats diverge from underlying metrics — these are your most valuable insights.
- Short paragraphs. No filler. Every sentence earns its place.
- Use the grading language: Elite (90th+), Above Average (75th+), Average (25th-75th), Below Average (25th-), Poor (10th-).

Rules:
- Never invent stats. Only use the data provided in the prompt.
- Always reference MLB averages when citing a Cubs stat.
- If a stat diverges from expected value, explain what will likely happen next.
- End with a clear, actionable bottom line.
- Do NOT use markdown headers or bullet points. Write in flowing prose paragraphs.
- Keep it under 300 words."""


# ---------------------------------------------------------------------------
# Context builders — assemble data for prompts
# ---------------------------------------------------------------------------

def _team_context(season: int, db: Session) -> str:
    """Build team state context string."""
    stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC",
        TeamSeasonStats.season == season,
    ).first()
    if not stats:
        return "No team data available yet."

    lines = [
        f"Cubs record: {stats.wins}-{stats.losses} ({stats.games_played} games played)",
        f"Run differential: {'+' if (stats.run_diff or 0) > 0 else ''}{stats.run_diff or 0}",
        f"Runs scored: {stats.runs_scored}, Runs allowed: {stats.runs_allowed}",
    ]
    if stats.pythag_wins:
        lines.append(f"Pythagorean record: {stats.pythag_wins}-{stats.pythag_losses}")
    if stats.team_era:
        lines.append(f"Team ERA: {stats.team_era:.2f}")
    if stats.team_fip:
        lines.append(f"Team FIP: {stats.team_fip:.2f}")
    if stats.team_wrc_plus:
        lines.append(f"Team wRC+: {stats.team_wrc_plus:.0f}")
    return "\n".join(lines)


def _game_context(game: Game, db: Session) -> str:
    """Build single game context."""
    is_home = game.home_team == "CHC"
    opp = game.away_team if is_home else game.home_team
    cubs_score = game.home_score if is_home else game.away_score
    opp_score = game.away_score if is_home else game.home_score
    result = "Won" if game.cubs_won else "Lost"
    loc = "home" if is_home else "away"
    return f"Cubs {result} {cubs_score}-{opp_score} {'vs' if is_home else 'at'} {opp} ({loc})"


def _divergence_context(season: int, db: Session) -> str:
    """Build divergence alerts context."""
    alerts = db.query(DivergenceAlert).filter(
        DivergenceAlert.is_active == True,
    ).order_by(DivergenceAlert.created_at.desc()).limit(10).all()
    if not alerts:
        return "No active divergence alerts."

    lines = []
    for a in alerts:
        player = db.query(Player).filter(Player.mlb_id == a.player_id).first()
        name = player.name if player else f"Player {a.player_id}"
        lines.append(
            f"[{a.alert_type}] {name}: {a.stat1_name} {a.stat1_value:.3f} "
            f"(pctile: {a.stat1_percentile}) vs {a.stat2_name} {a.stat2_value:.3f} "
            f"(pctile: {a.stat2_percentile}) — {a.explanation}"
        )
    return "\n".join(lines)


def _top_performers_context(season: int, db: Session) -> str:
    """Build top/bottom performers context."""
    lines = []

    pitchers = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season,
        PitcherSeasonStats.team == "CHC",
        PitcherSeasonStats.ip >= 10,
    ).order_by(PitcherSeasonStats.era.asc()).limit(3).all()

    for p in pitchers:
        player = db.query(Player).filter(Player.mlb_id == p.player_id).first()
        name = player.name if player else str(p.player_id)
        pb_era = db.query(PlayerBenchmark).filter(
            PlayerBenchmark.player_id == p.player_id,
            PlayerBenchmark.stat_name == "era",
        ).first()
        pctile = f" ({pb_era.percentile}th pctile)" if pb_era else ""
        lines.append(f"Pitcher: {name} — {p.ip:.1f} IP, {p.era:.2f} ERA{pctile}, {p.fip:.2f} FIP")

    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.team == "CHC",
        HitterSeasonStats.pa >= 20,
    ).order_by(HitterSeasonStats.wrc_plus.desc()).limit(3).all()

    for h in hitters:
        player = db.query(Player).filter(Player.mlb_id == h.player_id).first()
        name = player.name if player else str(h.player_id)
        pb_wrc = db.query(PlayerBenchmark).filter(
            PlayerBenchmark.player_id == h.player_id,
            PlayerBenchmark.stat_name == "wrc_plus",
        ).first()
        pctile = f" ({pb_wrc.percentile}th pctile)" if pb_wrc else ""
        lines.append(
            f"Hitter: {name} — {h.pa} PA, {h.wrc_plus:.0f} wRC+{pctile}, "
            f".{int((h.woba or 0) * 1000)} wOBA"
        )

    return "\n".join(lines) if lines else "No performer data available."


def _player_context(player_id: int, season: int, db: Session) -> str:
    """Build detailed context for a specific player."""
    player = db.query(Player).filter(Player.mlb_id == player_id).first()
    if not player:
        return f"No data for player {player_id}"

    lines = [f"Player: {player.name} (#{player_id}), Team: {player.team}, Position: {player.position}"]

    benchmarks = db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id,
    ).all()

    for b in benchmarks:
        lines.append(
            f"  {b.stat_name}: {b.value:.3f} — {b.percentile}th percentile ({b.grade}), "
            f"MLB avg: {b.mlb_avg:.3f}, delta: {b.delta:+.3f}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Editorial generation via Claude API
# ---------------------------------------------------------------------------

def _call_claude(prompt: str) -> Optional[str]:
    """Call Claude API with the analyst system prompt."""
    api_key = settings.anthropic_api_key
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — returning fallback editorial")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except ImportError:
        logger.error("anthropic package not installed — pip install anthropic")
        return None
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def _extract_player_ids(body: str, db: Session) -> list[int]:
    """Extract referenced player IDs from editorial text."""
    players = db.query(Player).filter(Player.is_cubs == True).all()
    ids = []
    for p in players:
        if p.name and p.name in body:
            ids.append(p.mlb_id)
    return ids


# ---------------------------------------------------------------------------
# Editorial type 1: Daily Takeaway (post-game)
# ---------------------------------------------------------------------------

def generate_daily_takeaway(game_pk: int, db: Session) -> Optional[Editorial]:
    """Generate post-game analysis editorial."""
    game = db.query(Game).filter(Game.game_pk == game_pk).first()
    if not game or game.status != "final":
        return None

    season = game.season
    game_ctx = _game_context(game, db)
    team_ctx = _team_context(season, db)
    performers = _top_performers_context(season, db)
    divergences = _divergence_context(season, db)

    prompt = f"""Write a post-game Daily Takeaway for the Cubs.

Today's result:
{game_ctx}

Season state:
{team_ctx}

Top performers:
{performers}

Active divergence alerts:
{divergences}

Write 2-3 paragraphs analyzing tonight's game in the context of the season. Reference specific stats with percentiles. Identify the key story: a breakout, a concerning trend, or a turning point. End with a one-sentence bottom line."""

    body = _call_claude(prompt)
    if not body:
        body = _generate_fallback_daily(game, season, db)

    title = f"Daily Takeaway: {game_ctx}"

    editorial = Editorial(
        editorial_type="daily_takeaway",
        title=title,
        body=body,
        summary=body[:200] + "..." if len(body) > 200 else body,
        player_ids=json.dumps(_extract_player_ids(body, db)),
        game_pk=game_pk,
        season=season,
    )
    db.add(editorial)
    db.commit()
    db.refresh(editorial)
    logger.info(f"Generated daily takeaway for game {game_pk}")
    return editorial


def _generate_fallback_daily(game: Game, season: int, db: Session) -> str:
    """Generate a data-driven fallback when Claude API is unavailable."""
    stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
    ).first()

    is_home = game.home_team == "CHC"
    opp = game.away_team if is_home else game.home_team
    cubs_score = game.home_score if is_home else game.away_score
    opp_score = game.away_score if is_home else game.home_score
    result = "defeated" if game.cubs_won else "fell to"

    parts = [f"The Cubs {result} the {opp} {cubs_score}-{opp_score} {'at Wrigley Field' if is_home else 'on the road'}."]

    if stats:
        parts.append(
            f"Chicago moves to {stats.wins}-{stats.losses} on the season "
            f"with a run differential of {'+' if (stats.run_diff or 0) >= 0 else ''}{stats.run_diff or 0}."
        )
        if stats.pythag_wins and stats.wins:
            diff = stats.wins - stats.pythag_wins
            if abs(diff) >= 1.5:
                parts.append(
                    f"Their Pythagorean record of {stats.pythag_wins:.0f}-{stats.pythag_losses:.0f} suggests they are "
                    f"{'overperforming' if diff > 0 else 'underperforming'} by {abs(diff):.1f} wins."
                )
        if stats.team_fip and stats.team_era:
            gap = stats.team_era - stats.team_fip
            if abs(gap) >= 0.3:
                parts.append(
                    f"The team ERA ({stats.team_era:.2f}) {'exceeds' if gap > 0 else 'trails'} "
                    f"FIP ({stats.team_fip:.2f}) by {abs(gap):.2f}, "
                    f"{'suggesting regression ahead' if gap < 0 else 'indicating room for improvement'}."
                )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Editorial type 2: Weekly State (Monday overview)
# ---------------------------------------------------------------------------

def generate_weekly_state(season: int, db: Session) -> Optional[Editorial]:
    """Generate Monday weekly state-of-the-Cubs editorial."""
    team_ctx = _team_context(season, db)
    performers = _top_performers_context(season, db)
    divergences = _divergence_context(season, db)

    prompt = f"""Write a Weekly State of the Cubs editorial for Monday morning.

Season state:
{team_ctx}

Top performers:
{performers}

Active divergence alerts:
{divergences}

Write 3-4 paragraphs covering: (1) Where the Cubs stand overall with Pythagorean context, (2) Who's been elite and who's struggling with percentile grades, (3) Which divergence flags are most actionable — what's about to change. End with a forward-looking bottom line about the week ahead."""

    body = _call_claude(prompt)
    if not body:
        body = _generate_fallback_weekly(season, db)

    stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
    ).first()
    record = f"{stats.wins}-{stats.losses}" if stats else "0-0"
    title = f"Weekly State: Cubs at {record}"

    editorial = Editorial(
        editorial_type="weekly_state",
        title=title,
        body=body,
        summary=body[:200] + "..." if len(body) > 200 else body,
        player_ids=json.dumps(_extract_player_ids(body, db)),
        season=season,
    )
    db.add(editorial)
    db.commit()
    db.refresh(editorial)
    logger.info("Generated weekly state editorial")
    return editorial


def _generate_fallback_weekly(season: int, db: Session) -> str:
    stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
    ).first()

    if not stats:
        return "Not enough data to generate a weekly summary. The season data will populate after running seed scripts."

    parts = [
        f"The Cubs sit at {stats.wins}-{stats.losses} through {stats.games_played} games this season.",
    ]
    if stats.pythag_wins:
        parts.append(
            f"Their Pythagorean expectation is {stats.pythag_wins:.0f}-{stats.pythag_losses:.0f}, "
            f"based on {stats.runs_scored} runs scored and {stats.runs_allowed} allowed "
            f"(run differential: {'+' if (stats.run_diff or 0) >= 0 else ''}{stats.run_diff})."
        )
    if stats.team_fip:
        parts.append(f"The pitching staff carries a {stats.team_fip:.2f} FIP.")
    if stats.team_wrc_plus:
        parts.append(
            f"Offensively, the team wRC+ of {stats.team_wrc_plus:.0f} "
            f"{'exceeds' if stats.team_wrc_plus > 100 else 'trails'} league average (100)."
        )

    alerts = db.query(DivergenceAlert).filter(DivergenceAlert.is_active == True).count()
    if alerts:
        parts.append(f"There are {alerts} active divergence alerts worth monitoring.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Editorial type 3: Player Spotlight (triggered by divergence flags)
# ---------------------------------------------------------------------------

def generate_player_spotlight(player_id: int, season: int, db: Session) -> Optional[Editorial]:
    """Generate player spotlight editorial triggered by divergence flags."""
    player_ctx = _player_context(player_id, season, db)
    team_ctx = _team_context(season, db)

    player = db.query(Player).filter(Player.mlb_id == player_id).first()
    if not player:
        return None

    alerts = db.query(DivergenceAlert).filter(
        DivergenceAlert.player_id == player_id,
        DivergenceAlert.is_active == True,
    ).all()

    alert_lines = []
    for a in alerts:
        alert_lines.append(f"[{a.alert_type}] {a.stat1_name}: {a.stat1_value:.3f} vs {a.stat2_name}: {a.stat2_value:.3f} — {a.explanation}")

    prompt = f"""Write a Player Spotlight editorial about {player.name}.

Player data:
{player_ctx}

Active divergence alerts for this player:
{chr(10).join(alert_lines) if alert_lines else "None"}

Team context:
{team_ctx}

Write 2-3 paragraphs profiling this player's current season. Lead with the most important divergence or trend. Reference every stat with its MLB percentile and grade. Explain what the numbers mean for his future production. End with a clear verdict: is he trending up, down, or steady?"""

    body = _call_claude(prompt)
    if not body:
        body = _generate_fallback_spotlight(player, player_id, season, db)

    title = f"Player Spotlight: {player.name}"

    editorial = Editorial(
        editorial_type="player_spotlight",
        title=title,
        body=body,
        summary=body[:200] + "..." if len(body) > 200 else body,
        player_ids=json.dumps([player_id]),
        season=season,
    )
    db.add(editorial)
    db.commit()
    db.refresh(editorial)
    logger.info(f"Generated player spotlight for {player.name}")
    return editorial


def _generate_fallback_spotlight(player, player_id: int, season: int, db: Session) -> str:
    benchmarks = db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id,
    ).all()

    parts = [f"{player.name} ({player.position or 'Unknown'}) has been a key piece for the Cubs this season."]
    for b in sorted(benchmarks, key=lambda x: x.percentile or 50, reverse=True)[:4]:
        parts.append(
            f"His {b.stat_name.replace('_', ' ')} of {b.value:.3f} ranks in the "
            f"{b.percentile}th percentile ({b.grade}), compared to the MLB average of {b.mlb_avg:.3f}."
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Editorial type 4: Prediction Recap (weekly model performance)
# ---------------------------------------------------------------------------

def generate_prediction_recap(season: int, db: Session) -> Optional[Editorial]:
    """Generate weekly prediction model recap."""
    from app.services.ml_engine import get_model_status

    team_ctx = _team_context(season, db)
    model_status = get_model_status()

    game_model = model_status.get("game_outcome", {})
    trend_model = model_status.get("win_trend", {})

    prompt = f"""Write a Prediction Recap editorial reviewing the ML model performance.

Team state:
{team_ctx}

Game Outcome Model (XGBoost):
- Status: {game_model.get('status', 'not trained')}
- CV Accuracy: {game_model.get('cv_accuracy', 'N/A')}
- Training samples: {game_model.get('samples', 0)}
- Top features: {json.dumps(game_model.get('feature_importance', {}), indent=2)}

Win Trend Model (Ridge):
- Status: {trend_model.get('status', 'not trained')}
- CV MAE: {trend_model.get('cv_mae', 'N/A')} wins
- Training samples: {trend_model.get('samples', 0)}

Regression Detection: Active (z-score based, always running)

Write 2-3 paragraphs analyzing model performance. Compare accuracy to baselines (coin flip 50%, home advantage 54%). Highlight which features are driving predictions. Note any patterns the models caught or missed. Keep it accessible — explain what the numbers mean for a fan trying to understand Cubs chances."""

    body = _call_claude(prompt)
    if not body:
        body = _generate_fallback_recap(model_status, season, db)

    title = "Prediction Recap: Model Performance Review"

    editorial = Editorial(
        editorial_type="prediction_recap",
        title=title,
        body=body,
        summary=body[:200] + "..." if len(body) > 200 else body,
        player_ids=json.dumps([]),
        season=season,
    )
    db.add(editorial)
    db.commit()
    db.refresh(editorial)
    logger.info("Generated prediction recap editorial")
    return editorial


def _generate_fallback_recap(model_status: dict, season: int, db: Session) -> str:
    game = model_status.get("game_outcome", {})
    trend = model_status.get("win_trend", {})

    parts = ["This week's model performance review:"]

    if game.get("status") == "trained":
        parts.append(
            f"The Game Outcome model (XGBoost) achieved {game['cv_accuracy']:.1%} cross-validated accuracy "
            f"across {game['samples']} games — compared to the 50% coin-flip baseline and ~54% home-advantage baseline."
        )
    else:
        parts.append("The Game Outcome model is pending training — it needs sufficient historical game data.")

    if trend.get("status") == "trained":
        parts.append(
            f"The Win Trend model (Ridge regression) predicts next-10-game win totals with an average error of "
            f"±{trend['cv_mae']:.1f} wins, trained on {trend['samples']} sliding windows."
        )
    else:
        parts.append("The Win Trend model is pending — it needs 40+ games in a season to train.")

    parts.append("The Regression Detection system runs continuously, flagging stats that diverge significantly from MLB benchmarks.")

    return " ".join(parts)
