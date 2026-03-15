#!/usr/bin/env python3
"""
SCV Status Writer v2
====================
Writes scv-status.json for the SCV Mission Control v2 dashboard.
Supports dynamic projects, dynamic infrastructure, work items, and activity logs.

Usage (import):
    from scv_status_writer import SCVStatus

    scv = SCVStatus()

    # Update agent status
    scv.set_agent("active", "Running heartbeat check")

    # Update infrastructure health
    scv.update_infra("aws1", status="healthy", last_log_minutes=1, bankroll_usd=566, errors_24h=0)
    scv.update_infra("aws2", status="healthy", last_log_minutes=2, bankroll_usd=665)

    # Update project status
    scv.update_project("storm-chaser-us", health="healthy", phase="Deployed — v2.1.0 running")

    # Add activity log entry
    scv.log("Heartbeat OK | All systems healthy", log_type="heartbeat", project="openclaw-overseer")

    # Add/update work items
    scv.add_work_item("Monitor v2.1.0 metrics", project="storm-chaser-us", assignee="scv")
    scv.complete_work_item("w7")

    # Add new infrastructure (when you spin up AWS3, etc.)
    scv.add_infra("aws3", name="AWS3", label="New Bot Server", ip="1.2.3.4",
                  infra_type="aws", cities=["Tokyo", "Sydney"])

    # Add new project
    scv.add_project("new-bot", name="New Bot", proj_type="bot", status="planned",
                    phase="Concept phase", next_action="Define strategy")

    # Write everything to disk
    scv.save()

Usage (CLI):
    python3 scv_status_writer.py heartbeat --aws1-bankroll 566 --aws2-bankroll 665
    python3 scv_status_writer.py log --type cron --project storm-chaser-us --msg "Morning scan done"
    python3 scv_status_writer.py agent --status active --task "Running morning scan"
    python3 scv_status_writer.py infra --id aws1 --bankroll 580 --errors 0 --last-log 1
    python3 scv_status_writer.py project --id storm-chaser-us --health healthy --phase "v2.1.0 running"
    python3 scv_status_writer.py work --add "Deploy new feature" --project storm-chaser-us --assignee scv
    python3 scv_status_writer.py work --complete w7
"""

import json
import os
import tempfile
import hashlib
from datetime import datetime, timezone, timedelta

# Central Time (CDT = UTC-5, CST = UTC-6)
CT = timezone(timedelta(hours=-5))  # CDT (March-November)

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scv-status.json")


def now_ct():
    """Current time in Central Time as ISO string."""
    return datetime.now(CT).isoformat()


def make_id(text):
    """Generate a short ID from text."""
    return "w" + hashlib.md5(text.encode()).hexdigest()[:6]


class SCVStatus:
    """Read-modify-write interface for scv-status.json."""

    def __init__(self, path=None):
        self.path = path or STATUS_FILE
        self.data = self._read()

    def _read(self):
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._default()

    def _default(self):
        return {
            "updated_at": now_ct(),
            "agent": {
                "status": "idle",
                "current_task": None,
                "last_activity": now_ct(),
                "model": "openai-codex/gpt-5.4",
                "session_id": "scv-auto",
            },
            "projects": [],
            "infrastructure": [],
            "work_items": [],
            "cron_jobs": [],
            "activity_log": [],
        }

    # ── Agent ──────────────────────────────────────

    def set_agent(self, status, task=None, project=None, model=None, session_id=None):
        """Set agent status: 'active', 'idle', or 'error'.
        
        Args:
            status: 'active', 'idle', or 'error'
            task: Current task description
            project: Project ID this task belongs to (e.g. 'storm-chaser-us')
            model: Override model name
            session_id: Override session ID
        """
        agent = self.data.setdefault("agent", {})
        agent["status"] = status
        
        if task:
            agent["current_task"] = task
            agent["last_task"] = task  # Always save as last_task too
        elif status == "idle":
            # When going idle, keep last_task but clear current_task
            if agent.get("current_task"):
                agent["last_task"] = agent["current_task"]
            agent["current_task"] = None
        
        if project is not None:
            agent["current_project"] = project
        
        if status == "active":
            agent["last_activity"] = now_ct()
        if model:
            agent["model"] = model
        if session_id:
            agent["session_id"] = session_id
        return self

    # ── Infrastructure ─────────────────────────────

    def update_infra(self, infra_id, **kwargs):
        """
        Update an infrastructure node's metrics.
        
        kwargs can include:
            status, last_log_minutes, bankroll_usd, errors_24h,
            uptime, disk_pct, memory_pct, bot_script, screen_alive
        """
        infra_list = self.data.setdefault("infrastructure", [])
        node = next((n for n in infra_list if n["id"] == infra_id), None)
        if not node:
            print(f"[WARN] Infrastructure '{infra_id}' not found. Use add_infra() first.")
            return self

        # Top-level fields
        if "status" in kwargs:
            node["status"] = kwargs.pop("status")

        # Everything else goes in metrics
        metrics = node.setdefault("metrics", {})
        for key, val in kwargs.items():
            metrics[key] = val

        return self

    def add_infra(self, infra_id, name, label, ip, infra_type="aws",
                  status="healthy", cities=None, projects=None, **metrics):
        """Add a new infrastructure node."""
        infra_list = self.data.setdefault("infrastructure", [])

        # Don't duplicate
        if any(n["id"] == infra_id for n in infra_list):
            print(f"[WARN] Infrastructure '{infra_id}' already exists. Use update_infra().")
            return self

        node = {
            "id": infra_id,
            "name": name,
            "label": label,
            "type": infra_type,
            "ip": ip,
            "status": status,
            "metrics": metrics,
            "cities": cities or [],
            "projects": projects or [],
        }
        infra_list.append(node)
        return self

    def remove_infra(self, infra_id):
        """Remove an infrastructure node."""
        infra_list = self.data.setdefault("infrastructure", [])
        self.data["infrastructure"] = [n for n in infra_list if n["id"] != infra_id]
        return self

    # ── Projects ───────────────────────────────────

    def update_project(self, project_id, **kwargs):
        """
        Update a project's fields.
        
        kwargs can include:
            status, phase, next_action, health, last_activity, infra, repo
        """
        projects = self.data.setdefault("projects", [])
        proj = next((p for p in projects if p["id"] == project_id), None)
        if not proj:
            print(f"[WARN] Project '{project_id}' not found. Use add_project() first.")
            return self

        for key, val in kwargs.items():
            proj[key] = val

        if "last_activity" not in kwargs:
            proj["last_activity"] = now_ct()

        return self

    def add_project(self, project_id, name, proj_type="bot", status="planned",
                    phase="", next_action="", repo=None, infra=None, health=None):
        """Add a new project."""
        projects = self.data.setdefault("projects", [])

        if any(p["id"] == project_id for p in projects):
            print(f"[WARN] Project '{project_id}' already exists. Use update_project().")
            return self

        proj = {
            "id": project_id,
            "name": name,
            "type": proj_type,
            "status": status,
            "repo": repo,
            "infra": infra or [],
            "phase": phase,
            "next_action": next_action,
            "last_activity": now_ct(),
            "health": health,
        }
        projects.append(proj)
        return self

    def remove_project(self, project_id):
        """Remove a project."""
        projects = self.data.setdefault("projects", [])
        self.data["projects"] = [p for p in projects if p["id"] != project_id]
        return self

    # ── Work Items ─────────────────────────────────

    def add_work_item(self, description, project=None, assignee="scv", status="todo"):
        """Add a work item. Returns the generated ID."""
        items = self.data.setdefault("work_items", [])
        item_id = make_id(description + now_ct())
        items.append({
            "id": item_id,
            "description": description,
            "project": project,
            "assignee": assignee,
            "status": status,
            "created": now_ct(),
        })
        return item_id

    def update_work_item(self, item_id, **kwargs):
        """Update a work item's fields (status, description, assignee, etc.)."""
        items = self.data.setdefault("work_items", [])
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            print(f"[WARN] Work item '{item_id}' not found.")
            return self
        for key, val in kwargs.items():
            item[key] = val
        return self

    def complete_work_item(self, item_id):
        """Mark a work item as done."""
        return self.update_work_item(item_id, status="done")

    def remove_work_item(self, item_id):
        """Remove a work item."""
        items = self.data.setdefault("work_items", [])
        self.data["work_items"] = [i for i in items if i["id"] != item_id]
        return self

    # ── Cron Jobs ──────────────────────────────────

    def update_cron(self, name, **kwargs):
        """Update a cron job by name."""
        jobs = self.data.setdefault("cron_jobs", [])
        job = next((j for j in jobs if j["name"] == name), None)
        if not job:
            print(f"[WARN] Cron job '{name}' not found.")
            return self
        for key, val in kwargs.items():
            job[key] = val
        return self

    def add_cron(self, name, schedule, project=None, status="ok"):
        """Add a new cron job."""
        jobs = self.data.setdefault("cron_jobs", [])
        if any(j["name"] == name for j in jobs):
            return self.update_cron(name, schedule=schedule, project=project, status=status)
        jobs.append({
            "name": name,
            "project": project,
            "schedule": schedule,
            "last_run": None,
            "status": status,
            "next_run": None,
        })
        return self

    # ── Activity Log ───────────────────────────────

    def log(self, message, log_type="info", project=None, severity="info"):
        """Add an activity log entry. Keeps last 100 entries."""
        logs = self.data.setdefault("activity_log", [])
        logs.insert(0, {
            "timestamp": now_ct(),
            "type": log_type,
            "project": project,
            "message": message,
            "severity": severity,
        })
        self.data["activity_log"] = logs[:100]
        return self

    # ── Convenience Methods ────────────────────────

    def heartbeat(self, infra_updates=None):
        """
        Run a standard heartbeat: mark agent active, update infra, log result.
        
        infra_updates: dict of {infra_id: {metric: value, ...}}
        Example:
            scv.heartbeat({
                "aws1": {"status": "healthy", "bankroll_usd": 566, "last_log_minutes": 1, "errors_24h": 0},
                "aws2": {"status": "healthy", "bankroll_usd": 665, "last_log_minutes": 2},
            })
        """
        self.set_agent("active", "Running heartbeat check", project="openclaw-overseer")

        if infra_updates:
            for infra_id, metrics in infra_updates.items():
                self.update_infra(infra_id, **metrics)

        # Build summary
        total_bankroll = sum(
            n.get("metrics", {}).get("bankroll_usd", 0)
            for n in self.data.get("infrastructure", [])
        )
        statuses = []
        for n in self.data.get("infrastructure", []):
            if n.get("metrics", {}).get("bankroll_usd"):
                statuses.append(f"{n['name']}: {n['status']}")

        msg = f"HEARTBEAT OK | {' | '.join(statuses)} | Bankroll: ${total_bankroll:,.0f}"
        severity = "info"
        if any(n["status"] != "healthy" for n in self.data.get("infrastructure", [])):
            severity = "warning"

        self.log(msg, log_type="heartbeat", project="openclaw-overseer", severity=severity)
        return self

    def go_idle(self):
        """Mark agent as idle."""
        self.set_agent("idle")
        return self

    # ── Save ───────────────────────────────────────

    def save(self):
        """Write to disk atomically."""
        self.data["updated_at"] = now_ct()

        dir_name = os.path.dirname(self.path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return self


# ── CLI ────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SCV Status Writer v2")
    sub = parser.add_subparsers(dest="command")

    # heartbeat
    hb = sub.add_parser("heartbeat", help="Write a heartbeat entry")
    hb.add_argument("--aws1-status", default="healthy")
    hb.add_argument("--aws1-bankroll", type=float, default=None)
    hb.add_argument("--aws1-stale", type=int, default=None)
    hb.add_argument("--aws1-errors", type=int, default=None)
    hb.add_argument("--aws2-status", default="healthy")
    hb.add_argument("--aws2-bankroll", type=float, default=None)
    hb.add_argument("--aws2-stale", type=int, default=None)
    hb.add_argument("--aws2-errors", type=int, default=None)

    # log
    lg = sub.add_parser("log", help="Add activity log entry")
    lg.add_argument("--type", default="info")
    lg.add_argument("--project", default=None)
    lg.add_argument("--msg", required=True)
    lg.add_argument("--severity", default="info")

    # agent
    ag = sub.add_parser("agent", help="Set agent status")
    ag.add_argument("--status", required=True, choices=["active", "idle", "error"])
    ag.add_argument("--task", default=None)

    # infra
    inf = sub.add_parser("infra", help="Update infrastructure metrics")
    inf.add_argument("--id", required=True)
    inf.add_argument("--status", default=None)
    inf.add_argument("--bankroll", type=float, default=None)
    inf.add_argument("--last-log", type=int, default=None)
    inf.add_argument("--errors", type=int, default=None)
    inf.add_argument("--disk", type=int, default=None)
    inf.add_argument("--memory", type=int, default=None)

    # project
    proj = sub.add_parser("project", help="Update project")
    proj.add_argument("--id", required=True)
    proj.add_argument("--status", default=None)
    proj.add_argument("--health", default=None)
    proj.add_argument("--phase", default=None)
    proj.add_argument("--next-action", default=None)

    # work
    wrk = sub.add_parser("work", help="Manage work items")
    wrk.add_argument("--add", default=None, help="Add new work item (description)")
    wrk.add_argument("--complete", default=None, help="Complete work item by ID")
    wrk.add_argument("--project", default=None)
    wrk.add_argument("--assignee", default="scv")

    args = parser.parse_args()
    scv = SCVStatus()

    if args.command == "heartbeat":
        updates = {}
        aws1 = {}
        if args.aws1_status:
            aws1["status"] = args.aws1_status
        if args.aws1_bankroll is not None:
            aws1["bankroll_usd"] = args.aws1_bankroll
        if args.aws1_stale is not None:
            aws1["last_log_minutes"] = args.aws1_stale
        if args.aws1_errors is not None:
            aws1["errors_24h"] = args.aws1_errors
        if aws1:
            updates["aws1"] = aws1

        aws2 = {}
        if args.aws2_status:
            aws2["status"] = args.aws2_status
        if args.aws2_bankroll is not None:
            aws2["bankroll_usd"] = args.aws2_bankroll
        if args.aws2_stale is not None:
            aws2["last_log_minutes"] = args.aws2_stale
        if args.aws2_errors is not None:
            aws2["errors_24h"] = args.aws2_errors
        if aws2:
            updates["aws2"] = aws2

        scv.heartbeat(updates)
        scv.go_idle()
        scv.save()
        print("Heartbeat written.")

    elif args.command == "log":
        scv.log(args.msg, log_type=args.type, project=args.project, severity=args.severity)
        scv.save()
        print("Log entry added.")

    elif args.command == "agent":
        scv.set_agent(args.status, args.task)
        scv.save()
        print(f"Agent set to {args.status}.")

    elif args.command == "infra":
        kwargs = {}
        if args.status:
            kwargs["status"] = args.status
        if args.bankroll is not None:
            kwargs["bankroll_usd"] = args.bankroll
        if args.last_log is not None:
            kwargs["last_log_minutes"] = args.last_log
        if args.errors is not None:
            kwargs["errors_24h"] = args.errors
        if args.disk is not None:
            kwargs["disk_pct"] = args.disk
        if args.memory is not None:
            kwargs["memory_pct"] = args.memory
        scv.update_infra(args.id, **kwargs)
        scv.save()
        print(f"Infrastructure '{args.id}' updated.")

    elif args.command == "project":
        kwargs = {}
        if args.status:
            kwargs["status"] = args.status
        if args.health:
            kwargs["health"] = args.health
        if args.phase:
            kwargs["phase"] = args.phase
        if args.next_action:
            kwargs["next_action"] = args.next_action
        scv.update_project(args.id, **kwargs)
        scv.save()
        print(f"Project '{args.id}' updated.")

    elif args.command == "work":
        if args.add:
            item_id = scv.add_work_item(args.add, project=args.project, assignee=args.assignee)
            scv.save()
            print(f"Work item added: {item_id}")
        elif args.complete:
            scv.complete_work_item(args.complete)
            scv.save()
            print(f"Work item '{args.complete}' completed.")
        else:
            print("Use --add or --complete")

    else:
        parser.print_help()
