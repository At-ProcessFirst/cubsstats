"""
The Booth — Natural language query engine for Cubs baseball data.

Two-call Claude pattern:
  1. User question → Claude generates SQL query plan (validated)
  2. Execute queries → Claude narrates results in analyst voice
"""

import json
import logging
import os
import re
import time
from collections import defaultdict
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiting: {ip: [(timestamp, ...),]}
_rate_limits = defaultdict(list)
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 3600  # 1 hour

# Load system prompt
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "booth_system_prompt.txt")
try:
    with open(_PROMPT_PATH, "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a baseball analyst. Answer questions about Cubs stats."
    logger.warning(f"booth_system_prompt.txt not found at {_PROMPT_PATH}")

# Dangerous SQL patterns
_FORBIDDEN_SQL = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|TRUNCATE|EXEC|EXECUTE)\b',
    re.IGNORECASE
)

NARRATION_SYSTEM = """You are The Booth — a sharp Cubs analyst on a broadcast.
Given raw database query results, write a conversational 2-3 sentence answer.
Use specific numbers. Be confident and concise. No markdown formatting.
If data is empty, say so honestly — don't make up numbers."""


def check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    # Clean old entries
    _rate_limits[client_ip] = [
        t for t in _rate_limits[client_ip] if now - t < RATE_LIMIT_WINDOW
    ]
    if len(_rate_limits[client_ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limits[client_ip].append(now)
    return True


def _validate_sql(sql: str) -> bool:
    """Reject any SQL that isn't a pure SELECT."""
    if _FORBIDDEN_SQL.search(sql):
        return False
    # Must start with SELECT (after stripping whitespace)
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return False
    return True


def _call_claude(system: str, messages: list, max_tokens: int = 1500) -> Optional[str]:
    """Call Anthropic API. Returns response text or None."""
    api_key = settings.anthropic_api_key
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def ask(question: str, db: Session, conversation_history: list = None) -> dict:
    """Process a natural language question about Cubs baseball.

    Returns: { answer, data, sources, error }
    """
    if not question or len(question) > 500:
        return {"answer": None, "error": "Question must be 1-500 characters.", "data": None, "sources": []}

    # Step 1: Get SQL query plan from Claude
    messages = []
    if conversation_history:
        messages.extend(conversation_history[-6:])  # Last 3 exchanges max
    messages.append({"role": "user", "content": question})

    plan_response = _call_claude(SYSTEM_PROMPT, messages)
    if not plan_response:
        return {
            "answer": "The Booth is temporarily unavailable. Try again in a moment.",
            "error": "api_unavailable",
            "data": None,
            "sources": [],
        }

    # Parse JSON from Claude's response
    try:
        # Extract JSON from response (Claude may wrap it in markdown)
        json_match = re.search(r'\{[\s\S]*\}', plan_response)
        if not json_match:
            raise ValueError("No JSON found in response")
        plan = json.loads(json_match.group())
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse Claude plan: {e}")
        # Fall back to treating the entire response as the answer
        return {
            "answer": plan_response,
            "data": None,
            "sources": [],
        }

    queries = plan.get("queries", [])
    if not queries:
        return {
            "answer": plan.get("reasoning", "I couldn't formulate a query for that question."),
            "data": None,
            "sources": [],
        }

    # Step 2: Validate and execute queries
    all_results = []
    sources = []

    for q in queries[:3]:  # Max 3 queries per question
        sql = q.get("sql", "")
        desc = q.get("description", "")

        if not _validate_sql(sql):
            logger.warning(f"Rejected unsafe SQL: {sql[:100]}")
            continue

        # Ensure LIMIT exists
        if "LIMIT" not in sql.upper():
            sql += " LIMIT 50"

        try:
            result = db.execute(text(sql))
            rows = [dict(row._mapping) for row in result.fetchall()]
            all_results.append({"description": desc, "rows": rows, "sql": sql})
            # Extract table names for source attribution
            tables = re.findall(r'FROM\s+(\w+)', sql, re.IGNORECASE)
            tables += re.findall(r'JOIN\s+(\w+)', sql, re.IGNORECASE)
            sources.extend(set(tables))
        except Exception as e:
            logger.warning(f"SQL execution failed: {e}")
            all_results.append({"description": desc, "rows": [], "error": str(e)})

    if not all_results or all(not r.get("rows") for r in all_results):
        return {
            "answer": "No matching data found. The database covers Cubs data from 2015-present.",
            "data": None,
            "sources": list(set(sources)),
        }

    # Step 3: Narrate results with second Claude call
    results_text = json.dumps(all_results, indent=2, default=str)
    narration_prompt = plan.get("narrative_prompt", f"Answer this question based on the data: {question}")

    narration = _call_claude(
        NARRATION_SYSTEM,
        [{"role": "user", "content": f"Question: {question}\n\nQuery results:\n{results_text}\n\n{narration_prompt}"}],
        max_tokens=500,
    )

    # Build response
    answer = narration or f"Here's what I found: {json.dumps(all_results[0].get('rows', [])[:5], default=str)}"

    # Flatten data for frontend table display
    table_data = None
    for r in all_results:
        if r.get("rows"):
            table_data = r["rows"][:20]  # Max 20 rows for display
            break

    return {
        "answer": answer,
        "data": table_data,
        "sources": list(set(sources)),
    }
