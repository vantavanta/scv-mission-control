# SCV Mission Control v2

Master dashboard for monitoring all Vanta Fund projects, infrastructure, and operations.

## Quick Start

```bash
git clone https://github.com/vantavanta/scv-mission-control.git
cd scv-mission-control
bash serve.sh
```

Open `http://localhost:8888` on your Mac, or `http://<your-mac-ip>:8888` from any LAN device.

## What It Shows

| Section | Description |
|---------|-------------|
| **Agent Status** | SCV active/idle/error, current task, model |
| **Projects** | All 9 projects with status (LIVE/IN PROGRESS/PLANNED), phase, next action, health |
| **Infrastructure** | Dynamic AWS/local nodes with bankroll, errors, disk, memory, uptime, cities |
| **Work Tracker** | Kanban board: TODO / IN PROGRESS / DONE with assignee tags |
| **Cron Jobs** | Scheduled tasks with project association and run status |
| **Activity Log** | Filterable event feed with per-project tags |

## Dynamic — Just Add to the JSON

Everything renders from `scv-status.json`. To add a new AWS instance or project, just add it to the JSON — no code changes needed.

## Status Writer (for SCV)

Import and use the Python API:

```python
from scv_status_writer import SCVStatus

scv = SCVStatus()

# Heartbeat (most common operation)
scv.heartbeat({
    "aws1": {"status": "healthy", "bankroll_usd": 566, "last_log_minutes": 1, "errors_24h": 0},
    "aws2": {"status": "healthy", "bankroll_usd": 665, "last_log_minutes": 2},
})
scv.go_idle()
scv.save()

# Update a project
scv.update_project("storm-chaser-us", health="healthy", phase="v2.1.0 — monitoring")
scv.save()

# Add activity
scv.log("Morning scan found 3 edges", log_type="cron", project="storm-chaser-us")
scv.save()

# Add new infrastructure (when spinning up AWS3, etc.)
scv.add_infra("aws3", name="AWS3", label="Asia Bot", ip="1.2.3.4",
              infra_type="aws", cities=["Tokyo", "Sydney", "Singapore"])
scv.save()

# Add new project
scv.add_project("new-strategy", name="New Strategy", proj_type="bot", status="planned",
                phase="Concept", next_action="Define parameters")
scv.save()

# Manage work items
scv.add_work_item("Build data pipeline", project="storm-oracle", assignee="zach")
scv.complete_work_item("w7")
scv.save()
```

Or use the CLI:

```bash
python3 scv_status_writer.py heartbeat --aws1-bankroll 566 --aws2-bankroll 665
python3 scv_status_writer.py log --type cron --project storm-chaser-us --msg "Scan done"
python3 scv_status_writer.py agent --status active --task "Running check"
python3 scv_status_writer.py infra --id aws1 --bankroll 580 --errors 0
python3 scv_status_writer.py project --id storm-chaser-us --health healthy
python3 scv_status_writer.py work --add "New task" --project storm-chaser-us --assignee scv
python3 scv_status_writer.py work --complete w7
```

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard (single file, zero dependencies) |
| `scv-status.json` | Data file read by dashboard, written by SCV |
| `scv_status_writer.py` | Python API + CLI for SCV to write status |
| `serve.sh` | One-liner to start the server |

## Architecture

```
Dashboard (browser) ←── polls every 10s ──→ scv-status.json ←── writes ──→ SCV agent
```

SCV writes the JSON during heartbeats and task execution. The dashboard polls it. Zero coupling — add new projects or infrastructure by editing the JSON.
