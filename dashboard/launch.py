"""One-at-a-time launcher for demo issues; the dashboard only shows it with RED2FIX_ENABLE_LAUNCH=1."""

import json
import os
import subprocess
import time


def demo_issues(root):
    return sorted(int(p.stem) for p in (root / "demo" / "issues").glob("*.md") if p.stem.isdigit())


def running_pid(lock):
    """PID of the launched run if it is still alive, else None."""
    try:
        pid = int(lock.read_text())
    except (FileNotFoundError, ValueError):
        return None
    try:
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return None  # our child, and it just exited (reaping it, or it stays a zombie that looks alive)
    except ChildProcessError:
        pass  # not our child, e.g. launched before a dashboard restart
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    return pid


def start(n, root):
    """Run scripts/run_local.sh <n> detached, logging to out/<n>/run.log. Returns the PID."""
    if n not in demo_issues(root):
        raise ValueError(f"no demo issue {n}")
    out = root / "out"
    lock = out / ".launch.lock"
    if running_pid(lock):
        raise RuntimeError("a run is already in progress")
    run_dir = out / str(n)
    run_dir.mkdir(parents=True, exist_ok=True)
    # Show the run as queued while the image builds; the agent clears these when it starts.
    (run_dir / "result.json").unlink(missing_ok=True)
    (run_dir / "events.jsonl").write_text(json.dumps({"t": time.time(), "ev": "phase", "name": "QUEUED"}) + "\n")
    with open(run_dir / "run.log", "w") as log:
        proc = subprocess.Popen([str(root / "scripts" / "run_local.sh"), str(n)], cwd=root,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    lock.write_text(str(proc.pid))
    return proc.pid
