"""The background watcher (`claudeverse auto-check`): near the limit, it asks Anthropic for the
real numbers every minute and switches when the account in use is used up.

Claude Code does not end the turn at the usage limit (it waits: "Retrying in 5h"), so no hook
tells claudeverse about it, and the status line does not run again while it waits.
"""
from __future__ import annotations

import subprocess
import time

from . import Error, IS_WIN, auto_switch, files, paths, state

WATCH_FROM = 90.0      # percent: the status line starts the watcher when the account in use is this high
WATCH_EVERY = 60       # seconds between two usage checks of the watcher
WATCH_FOR = 30 * 60    # seconds the watcher keeps going after the status line last saw high usage


def start() -> None:
    """Run the watcher (`claudeverse auto-check`) in the background."""
    cmd = f"{paths.self_command()} auto-check"
    kw = dict(shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not IS_WIN:
        subprocess.Popen(cmd, start_new_session=True, **kw)
        return
    no_window, new_group, breakaway = 0x08000000, 0x00000200, 0x01000000
    try:
        # Out of Claude Code's job, so it keeps running after the status line command ends.
        subprocess.Popen(cmd, creationflags=no_window | new_group | breakaway, **kw)
    except OSError:
        subprocess.Popen(cmd, creationflags=no_window | new_group, **kw)


def watch_if_near_limit(windows) -> None:
    """Called by the status line with the usage of the account in use.

    Near the limit, keep a watcher running that asks Anthropic for the real numbers every minute."""
    a = state.load()["auto"]
    if not a.get("enabled", True) or not windows:
        return
    if not any(w["pct"] >= min(auto_switch.current_threshold(), WATCH_FROM) for w in windows):
        return
    now = time.time()
    with state.edit() as st:
        a = st["auto"]
        a["watch_until"] = int(now + WATCH_FOR)
        alive = now - float(a.get("watch_alive") or 0) < 2 * WATCH_EVERY + 30
        if not alive:
            a["watch_alive"] = int(now)  # so that the next render does not start a second one
    if not alive:
        files.log_event("watcher started (the account in use is near its limit)")
        start()


def run() -> None:
    """`auto-check`: check the usage every minute until the status line stops seeing high usage."""
    while True:
        a = state.load()["auto"]
        if not a.get("enabled", True) or time.time() > float(a.get("watch_until") or 0):
            return
        with state.edit() as st:
            st["auto"]["watch_alive"] = int(time.time())
        try:
            auto_switch.switch_if_at_limit()
        except Error as e:
            files.log_event(f"automatic switch failed: {e}")
        time.sleep(WATCH_EVERY)
