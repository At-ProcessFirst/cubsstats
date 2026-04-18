"""
Live context service — fetches structured Cubs data from MLB Stats API.

Shared between The Booth (text format for Claude) and the REST API
(/api/team/live-context endpoint). Uses a 5-minute in-memory cache.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Shared 5-minute cache
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 minutes

# Team abbreviation map for standings
_TEAM_ABBR = {
    "Chicago Cubs": "CHC", "Milwaukee Brewers": "MIL", "St. Louis Cardinals": "STL",
    "Cincinnati Reds": "CIN", "Pittsburgh Pirates": "PIT",
}


def get_live_context_data() -> dict:
    """Fetch structured live Cubs data from MLB Stats API, cached 5 minutes."""
    now = time.time()
    if _cache["data"] and now - _cache["timestamp"] < CACHE_TTL:
        return _cache["data"]

    data = _fetch_all()
    _cache["data"] = data
    _cache["timestamp"] = now
    return data


def _fetch_all() -> dict:
    """Make all MLB API calls and return structured data."""
    from app.services.ingestion import mlb_api_get, fetch_schedule, pull_cubs_roster

    ct = timezone(timedelta(hours=-5))
    today = datetime.now(ct).date()

    result = {
        "date": today.isoformat(),
        "standings": [],
        "injuries": [],
        "team_leaders": {},
        "transactions": [],
        "streak": {"type": "W", "count": 0},
        "today": None,
    }

    # 1. NL Central standings
    try:
        data = mlb_api_get("/standings", {
            "leagueId": "104", "season": today.year,
            "standingsTypes": "regularSeason", "hydrate": "team,division",
        })
        for rec in data.get("records", []):
            div = rec.get("division", {}).get("name", "")
            if "Central" in div:
                for tr in rec.get("teamRecords", []):
                    team_name = tr.get("team", {}).get("name", "")
                    abbrev = _TEAM_ABBR.get(team_name, team_name[:3].upper())
                    streak = tr.get("streak", {})
                    entry = {
                        "team": team_name,
                        "abbrev": abbrev,
                        "wins": tr.get("wins", 0),
                        "losses": tr.get("losses", 0),
                        "games_back": tr.get("gamesBack", "-"),
                        "win_pct": float(tr.get("winningPercentage", 0)),
                    }
                    result["standings"].append(entry)
                    # Extract Cubs streak
                    if abbrev == "CHC":
                        stype = streak.get("streakType", "")
                        snum = streak.get("streakNumber", 0)
                        result["streak"] = {
                            "type": "W" if stype == "wins" else "L",
                            "count": snum,
                        }
    except Exception as e:
        logger.debug(f"Standings fetch failed: {e}")

    # 2. Today's game
    try:
        games = fetch_schedule(today, today, team_id=112)
        if games:
            g = games[0]
            home_team = g.get("teams", {}).get("home", {})
            away_team = g.get("teams", {}).get("away", {})
            home_name = home_team.get("team", {}).get("name", "")
            away_name = away_team.get("team", {}).get("name", "")
            is_cubs_home = "Cubs" in home_name
            opp_name = away_name if is_cubs_home else home_name

            home_starter = home_team.get("probablePitcher", {})
            away_starter = away_team.get("probablePitcher", {})

            home_score = home_team.get("score")
            away_score = away_team.get("score")
            cubs_score = home_score if is_cubs_home else away_score
            opp_score = away_score if is_cubs_home else home_score

            result["today"] = {
                "game_pk": g.get("gamePk"),
                "opponent": opp_name,
                "is_home": is_cubs_home,
                "status": g.get("status", {}).get("detailedState", "Scheduled"),
                "game_time": g.get("gameDate", ""),
                "day_night": g.get("dayNight", "night"),
                "cubs_score": cubs_score,
                "opp_score": opp_score,
                "home_starter": {
                    "id": home_starter.get("id"),
                    "name": home_starter.get("fullName", "TBD"),
                } if home_starter else {"id": None, "name": "TBD"},
                "away_starter": {
                    "id": away_starter.get("id"),
                    "name": away_starter.get("fullName", "TBD"),
                } if away_starter else {"id": None, "name": "TBD"},
            }
    except Exception as e:
        logger.debug(f"Schedule fetch failed: {e}")

    # 3. Injuries / IL
    try:
        data = mlb_api_get("/injuries", {"teamId": 112})
        for inj in data.get("injuries", []):
            result["injuries"].append({
                "player_name": inj.get("player", {}).get("fullName", "?"),
                "description": inj.get("description", ""),
                "injury_type": inj.get("injuryType", ""),
                "date": (inj.get("date") or "")[:10],
            })
    except Exception as e:
        logger.debug(f"Injuries fetch failed: {e}")

    # 4. Team leaders
    try:
        for cat, label in [
            ("homeRuns", "HR"), ("battingAverage", "AVG"),
            ("earnedRunAverage", "ERA"), ("wins", "W"),
        ]:
            leaders_data = mlb_api_get("/teams/112/leaders", {
                "leaderCategories": cat, "season": today.year, "limit": 5,
            })
            leaders = []
            for lg in leaders_data.get("teamLeaders", []):
                for leader in lg.get("leaders", []):
                    leaders.append({
                        "name": leader.get("person", {}).get("fullName", "?"),
                        "value": leader.get("value", "?"),
                    })
            if leaders:
                result["team_leaders"][label] = leaders
    except Exception as e:
        logger.debug(f"Team leaders fetch failed: {e}")

    # 5. Recent transactions
    try:
        data = mlb_api_get("/transactions", {
            "teamId": 112,
            "startDate": (today - timedelta(days=14)).isoformat(),
            "endDate": today.isoformat(),
        })
        for t in data.get("transactions", [])[:10]:
            desc = t.get("description", "")
            dt = (t.get("date") or "")[:10]
            if desc:
                result["transactions"].append({"date": dt, "description": desc})
    except Exception as e:
        logger.debug(f"Transactions fetch failed: {e}")

    return result


def format_for_booth(data: dict) -> str:
    """Convert structured live context data into text for Claude's system prompt."""
    parts = []
    today = data.get("date", "")

    # Standings
    if data.get("standings"):
        lines = []
        for s in data["standings"]:
            lines.append(f"- {s['team']}: {s['wins']}-{s['losses']} (GB: {s['games_back']})")
        parts.append(f"## NL CENTRAL STANDINGS ({today})\n" + "\n".join(lines))

    # Today's game
    game = data.get("today")
    if game:
        prefix = "vs" if game["is_home"] else "@"
        parts.append(
            f"## TODAY'S GAME ({today})\n"
            f"Cubs {prefix} {game['opponent']} — {game['status']}\n"
            f"Game time: {game['game_time']}\n"
            f"Starters: {game['home_starter']['name']} vs {game['away_starter']['name']}"
        )
    else:
        parts.append(f"## TODAY ({today})\nNo Cubs game scheduled today.")

    # Injuries
    if data.get("injuries"):
        lines = [f"- {i['player_name']}: {i['description']} ({i['injury_type']}, since {i['date']})"
                 for i in data["injuries"]]
        parts.append("## CUBS INJURED LIST (current)\n" + "\n".join(lines))

    # Team leaders
    for label, leaders in data.get("team_leaders", {}).items():
        lines = [f"- {l['name']}: {l['value']}" for l in leaders]
        parts.append(f"## CUBS LEADERS — {label} ({today[:4]})\n" + "\n".join(lines))

    # Transactions
    if data.get("transactions"):
        lines = [f"- {t['date']}: {t['description']}" for t in data["transactions"]]
        parts.append("## RECENT CUBS TRANSACTIONS (last 14 days)\n" + "\n".join(lines))

    return "\n\n".join(parts)
