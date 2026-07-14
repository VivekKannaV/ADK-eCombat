#!/usr/bin/env python
"""print_session_history.py — Admin/debug script to replay a conversation from PostgreSQL.

Usage
-----
    python scripts/print_session_history.py <session_id> [--limit N] [--json]

Examples
--------
    # Pretty-print the last 100 turns for a session
    python scripts/print_session_history.py abc-123

    # Limit to 20 turns
    python scripts/print_session_history.py abc-123 --limit 20

    # Output raw JSON (useful for piping into jq)
    python scripts/print_session_history.py abc-123 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timezone

# ---------------------------------------------------------------------------
# Bootstrap path so the script works when run from the project root without
# installing the package.
# ---------------------------------------------------------------------------
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ---------------------------------------------------------------------------
# Load .env before importing any service module (settings reads it at import
# time, but loading it here is an extra safety net for script usage).
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore[import]

    load_dotenv(_project_root / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on real env vars

from eCombat.src.services.session_history_service import SessionHistoryService  # noqa: E402


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_ROLE_COLOURS = {
    "user":      "\033[94m",   # blue
    "assistant": "\033[92m",   # green
    "tool":      "\033[93m",   # yellow
    "system":    "\033[90m",   # dark grey
}
_RESET = "\033[0m"


def _colour(role: str, text: str, use_colour: bool) -> str:
    if not use_colour:
        return text
    colour = _ROLE_COLOURS.get(role, "")
    return f"{colour}{text}{_RESET}"


def _format_timestamp(ts: object) -> str:
    """Return an ISO-8601 string in UTC, regardless of psycopg2 type."""
    if ts is None:
        return "—"
    try:
        # datetime with tzinfo
        return ts.astimezone(timezone.utc).isoformat()  # type: ignore[union-attr]
    except AttributeError:
        return str(ts)


def print_session(session_id: str, limit: int, as_json: bool) -> None:
    turns = SessionHistoryService.get_history(session_id, limit=limit)

    if not turns:
        print(f"No conversation turns found for session '{session_id}'.", file=sys.stderr)
        sys.exit(1)

    if as_json:
        # Make timestamps JSON-serialisable
        for t in turns:
            if "timestamp" in t and not isinstance(t["timestamp"], str):
                t["timestamp"] = _format_timestamp(t["timestamp"])
        print(json.dumps(turns, indent=2, default=str))
        return

    use_colour = sys.stdout.isatty()
    separator = "─" * 72

    print(separator)
    print(f"  Session : {session_id}")
    print(f"  Turns   : {len(turns)}")
    print(separator)

    for turn in turns:
        role      = turn.get("role", "?")
        user_id   = turn.get("user_id") or ""
        content   = turn.get("content", "")
        ts        = _format_timestamp(turn.get("timestamp"))
        tool_info = turn.get("tool_calls")

        header = f"[{role.upper()}]"
        if user_id:
            header += f"  user_id={user_id}"
        header += f"  @ {ts}"

        print(_colour(role, header, use_colour))
        print(content)
        if tool_info:
            print(_colour(role, "  tool_calls: " + json.dumps(tool_info, default=str), use_colour))
        print()

    print(separator)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print the conversation history for a given session from PostgreSQL."
    )
    parser.add_argument("session_id", help="Session ID to look up")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of turns to display (default: 100)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )

    args = parser.parse_args()
    print_session(args.session_id, limit=args.limit, as_json=args.as_json)


if __name__ == "__main__":
    main()
