"""What a running session gets after a switch: what is typed into it (Windows), and what the
model is told.
"""
from __future__ import annotations

import time

from . import IS_WIN, files, on_switch, transcript, usage


def respond(data: dict, sig: dict):
    """Handle switch `sig` for the session of hook input `data`.

    Returns the notice for the model (the hook sends it with exit code 2, asyncRewake), or None
    when the session needs no notice."""
    if IS_WIN:
        stopped = False
        try:
            stopped = type_after_switch(data, sig)
        except Exception as e:  # never fail the hook
            files.log_event(f"on-switch error: {type(e).__name__}: {e}")
        if stopped:
            return None  # the continue text already asked about stopped subagents
        return notice_after_typing(sig)  # the model hears about its agents
    return notice(sig)


def notice_after_typing(sig: dict) -> str:
    """Windows, for a session that was not stopped at the limit: /remote-control was typed in, but
    the model still has to hear about its agents."""
    return (
        f"claudeverse (a hook the user installed): the login switched from '{sig.get('from')}' to "
        f"'{sig.get('to')}' at {usage.fmt_time(sig.get('at'))}; /remote-control was typed in. Subagents and background "
        "agents that were running during the switch may have stopped. The user set up this hook so that each of "
        "them is checked, one by one, and every one that stopped is started again.")


def notice(sig: dict) -> str:
    # Written as a notice, not as orders: models rightly ignore orders that show up in tool output.
    return (
        f"claudeverse (a hook the user installed): the login switched from '{sig.get('from')}' to "
        f"'{sig.get('to')}' at {usage.fmt_time(sig.get('at'))}. Remote Control has likely disconnected; only the user "
        "can reconnect it (/remote-control). Subagents and background agents that were running during the "
        "switch may have stopped. The user set up this hook to hear about Remote Control, and so that each "
        "agent is checked, one by one, and every one that stopped is started again.")


def type_after_switch(data: dict, sig: dict) -> bool:
    """Windows: type the on-switch commands into this session, and the continue text when it had
    stopped at the limit.

    Returns True when the session had stopped at the limit (it got the continue text, which also
    asks about stopped subagents)."""
    from . import session_typing, win_console  # Windows only (ctypes)

    cfg = on_switch.config()
    session = str(data.get("session_id") or "?")[:8]
    commands = list(cfg.get("commands") or [])
    resume = cfg.get("continue_text") or ""
    if not commands and not resume:
        return False
    pid = win_console.find_claude_pid()
    if not pid:
        files.log_event(f"on-switch session={session}: claude.exe not found among the parent processes")
        return False
    deadline = time.time() + float(cfg.get("wait_sec") or 600)
    # A session stopped at the old login's limit waits for that limit to reset. Cancel the wait
    # (Esc) and send the continue text, so it goes on with the new login now.
    stopped = False
    if resume:
        stopped = session_typing.limit_wait_on_screen(pid)
        if stopped:
            # Cancel the wait first: while it lasts, typed commands would only be queued.
            session_typing.cancel_limit_wait(pid, session)
        stopped = stopped or transcript.stopped_at_limit(data.get("transcript_path"))
    todo = commands + ([resume] if stopped else [])
    for i, text in enumerate(todo):
        for attempt in range(3):
            if not session_typing.type_one(pid, text, deadline, session, cancel_wait=(i == len(commands))):
                return stopped
            if not text.strip().startswith("/remote-control"):
                time.sleep(2.0)
                break
            if not session_typing.remote_control_asked_retry(pid, deadline):
                break
            # Remote Control still held the old account's connection. The dialog says: choose
            # Continue (done), wait about 10 seconds, then run /remote-control again.
            files.log_event(f"on-switch session={session}: Remote Control asked to retry; waiting")
            time.sleep(12.0)
    return stopped
