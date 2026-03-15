#!/usr/bin/env python3
"""
SCV Status Writer
=================
This script is called by the SCV agent during heartbeat checks to write
the scv-status.json file that the dashboard reads.

Usage:
    python3 scv_status_writer.py

Or import and call write_status() from your heartbeat script:

    from scv_status_writer import write_status
    write_status(
        agent_status="active",
        current_task="Running heartbeat check on AWS1",
        model="openai-codex/gpt-5.4",
        aws1_status="healthy",
        aws1_log_stale_min=1,
        aws1_bankroll=566,
        aws2_status="healthy",
        aws2_log_stale_min=2,
        aws2_bankroll=665,
        aws2_screen_alive=True,
    )

The JSON file is written atomically (write to tmp, then rename) to avoid
the dashboard reading a half-written file.
"""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

# Central Time offset (CT = UTC-5 in CDT, UTC-6 in CST)
# Adjust based on DST — or use pytz/zoneinfo if available
CT = timezone(timedelta(hours=-5))  # CDT (March-November)

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scv-status.json")

# Default city lists
AWS1_CITIES = ["Dallas", "NYC", "Chicago", "Seattle", "Atlanta"]
AWS2_CITIES = ["London", "Paris", "Sao Paulo", "Wellington", "Toronto", "Ankara", "Seoul"]


def now_ct():
    """Current time in Central Time as ISO string."""
    return datetime.now(CT).isoformat()


def read_existing():
    """Read existing status file, return dict or empty dict."""
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def append_log(existing_data, log_type, message, severity="info"):
    """Append a log entry to the activity log, keeping last 50 entries."""
    logs = existing_data.get("activity_log", [])
    logs.insert(0, {
        "timestamp": now_ct(),
        "type": log_type,
        "message": message,
        "severity": severity,
    })
    return logs[:50]  # Keep last 50


def write_status(
    # Agent
    agent_status="idle",
    current_task=None,
    model="openai-codex/gpt-5.4",
    session_id=None,
    # AWS1
    aws1_status="healthy",
    aws1_log_stale_min=0,
    aws1_bankroll=0,
    aws1_errors=0,
    # AWS2
    aws2_status="healthy",
    aws2_log_stale_min=0,
    aws2_bankroll=0,
    aws2_screen_alive=True,
    aws2_errors=0,
    # Cron (pass list of dicts, or None to keep existing)
    cron_jobs=None,
    # Log entry to add (optional)
    log_type=None,
    log_message=None,
    log_severity="info",
):
    """Write the scv-status.json file atomically."""
    existing = read_existing()
    now = now_ct()

    # Build agent section
    agent = {
        "status": agent_status,
        "current_task": current_task,
        "last_activity": now if agent_status == "active" else (
            existing.get("agent", {}).get("last_activity", now)
        ),
        "model": model,
        "session_id": session_id or existing.get("agent", {}).get("session_id", "scv-auto"),
    }

    # Build AWS sections
    aws1 = {
        "status": aws1_status,
        "last_log_update": now,
        "log_stale_minutes": aws1_log_stale_min,
        "cities": AWS1_CITIES,
        "bankroll_usd": aws1_bankroll,
        "bot_script": "intraday_watch.py",
        "errors_recent": aws1_errors,
    }

    aws2 = {
        "status": aws2_status,
        "last_log_update": now,
        "log_stale_minutes": aws2_log_stale_min,
        "screen_alive": aws2_screen_alive,
        "cities": AWS2_CITIES,
        "bankroll_usd": aws2_bankroll,
        "bot_script": "intl_watch.py",
        "errors_recent": aws2_errors,
    }

    # Cron: keep existing or use provided
    if cron_jobs is None:
        cron_jobs = existing.get("cron_jobs", [])

    # Activity log
    activity_log = existing.get("activity_log", [])
    if log_type and log_message:
        activity_log = append_log(existing, log_type, log_message, log_severity)

    data = {
        "updated_at": now,
        "agent": agent,
        "aws1": aws1,
        "aws2": aws2,
        "cron_jobs": cron_jobs,
        "activity_log": activity_log,
    }

    # Atomic write: write to temp file, then rename
    dir_name = os.path.dirname(STATUS_FILE)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, STATUS_FILE)
    except Exception:
        # Clean up temp file if rename fails
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return data


def heartbeat_ok(aws1_status, aws2_status, aws1_bankroll, aws2_bankroll):
    """Convenience: write a heartbeat status and log entry."""
    total = aws1_bankroll + aws2_bankroll
    msg = f"HEARTBEAT OK | AWS1: {aws1_status} | AWS2: {aws2_status} | Bankroll: ${total:,.0f}"
    severity = "info"
    if aws1_status != "healthy" or aws2_status != "healthy":
        severity = "warning"

    return write_status(
        agent_status="active",
        current_task="Running heartbeat check",
        aws1_status=aws1_status,
        aws1_bankroll=aws1_bankroll,
        aws2_status=aws2_status,
        aws2_bankroll=aws2_bankroll,
        log_type="heartbeat",
        log_message=msg,
        log_severity=severity,
    )


# ── CLI usage ───────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Write SCV status JSON")
    parser.add_argument("--agent-status", default="idle", choices=["active", "idle", "error"])
    parser.add_argument("--task", default=None, help="Current task description")
    parser.add_argument("--model", default="openai-codex/gpt-5.4")
    parser.add_argument("--aws1-status", default="healthy", choices=["healthy", "warning", "critical"])
    parser.add_argument("--aws1-bankroll", type=float, default=566)
    parser.add_argument("--aws1-stale", type=int, default=0, help="AWS1 log staleness in minutes")
    parser.add_argument("--aws2-status", default="healthy", choices=["healthy", "warning", "critical"])
    parser.add_argument("--aws2-bankroll", type=float, default=665)
    parser.add_argument("--aws2-stale", type=int, default=0, help="AWS2 log staleness in minutes")
    parser.add_argument("--aws2-screen", action="store_true", default=True)
    parser.add_argument("--no-aws2-screen", dest="aws2_screen", action="store_false")
    parser.add_argument("--log-type", default=None, help="Log entry type")
    parser.add_argument("--log-msg", default=None, help="Log entry message")
    parser.add_argument("--log-severity", default="info", choices=["info", "warning", "critical"])
    parser.add_argument("--heartbeat", action="store_true", help="Write a heartbeat entry")

    args = parser.parse_args()

    if args.heartbeat:
        data = heartbeat_ok(args.aws1_status, args.aws2_status, args.aws1_bankroll, args.aws2_bankroll)
        print(f"Heartbeat written to {STATUS_FILE}")
    else:
        data = write_status(
            agent_status=args.agent_status,
            current_task=args.task,
            model=args.model,
            aws1_status=args.aws1_status,
            aws1_log_stale_min=args.aws1_stale,
            aws1_bankroll=args.aws1_bankroll,
            aws2_status=args.aws2_status,
            aws2_log_stale_min=args.aws2_stale,
            aws2_bankroll=args.aws2_bankroll,
            aws2_screen_alive=args.aws2_screen,
            log_type=args.log_type,
            log_message=args.log_msg,
            log_severity=args.log_severity,
        )
        print(f"Status written to {STATUS_FILE}")
