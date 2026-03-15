# SCV Mission Control — Monitoring Dashboard

Real-time monitoring dashboard for the OpenClaw SCV agent. Displays agent status, AWS bot health, cron job status, and an activity log.

## Quick Start

```bash
cd scv-dashboard
chmod +x serve.sh
./serve.sh
```

This starts a Python HTTP server on port 8888. Open http://localhost:8888 from your Mac, or http://<your-local-ip>:8888 from any device on the LAN.

To find your Mac's local IP:
```bash
ipconfig getifaddr en0
```

## Files

| File | Purpose |
|---|---|
| `index.html` | Complete dashboard — single HTML file, no build step |
| `scv-status.json` | Status data file (demo data included, SCV overwrites this) |
| `scv_status_writer.py` | Python helper for SCV to write status data |
| `serve.sh` | One-liner to start the dashboard server |

## How it Works

1. The dashboard loads `scv-status.json` on startup
2. It polls for updates every 10 seconds
3. SCV writes to `scv-status.json` during heartbeat checks via `scv_status_writer.py`
4. The dashboard automatically reflects new data — no restart needed

## Connecting SCV

### Option 1: Use the Python helper during heartbeat

```python
from scv_status_writer import heartbeat_ok

# In your heartbeat function:
heartbeat_ok(
    aws1_status="healthy",
    aws2_status="healthy",
    aws1_bankroll=566,
    aws2_bankroll=665,
)
```

### Option 2: CLI for cron or manual updates

```bash
# Write a heartbeat
python3 scv_status_writer.py --heartbeat --aws1-bankroll 566 --aws2-bankroll 665

# Mark agent as active with a task
python3 scv_status_writer.py --agent-status active --task "Running morning scan on AWS1"

# Log an error
python3 scv_status_writer.py --log-type alert --log-msg "AWS1 screen crashed" --log-severity critical

# Mark agent idle after task completes
python3 scv_status_writer.py --agent-status idle
```

### Option 3: Write JSON directly

SCV can write `scv-status.json` directly. See the file for the expected schema. The dashboard handles any valid JSON matching the schema — missing fields are gracefully ignored.

## Dashboard Features

- **Dark theme** optimized for monitoring
- **Auto-refresh** every 10 seconds with connection status indicator
- **Responsive** — works on desktop and mobile
- **Agent status** with animated pulse indicators (active/idle/error)
- **AWS bot health** cards with city tags, bankroll, and log freshness
- **Cron job table** with schedule, last run, status, and next run
- **Activity log** with color-coded severity and event types
- **Central Time** display throughout (America/Chicago)
- **No dependencies** — pure HTML + CSS + JS in a single file

## Customization

- **Poll interval**: Change `POLL_INTERVAL` in the `<script>` section of `index.html` (default: 10000ms)
- **Status file path**: Change `STATUS_FILE` if serving from a different directory
- **Colors**: All colors are defined as CSS custom properties at the top of the `<style>` block
