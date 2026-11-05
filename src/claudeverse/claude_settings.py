"""Claude Code's settings.json: claudeverse's status line and hooks (install, uninstall), and the
cleanup of what older versions left there.

An entry is ours when its command line contains "claudeverse"; everything else is left alone.
"""
from __future__ import annotations

from . import files, on_switch, paths, state, switch_signal

OUR_HOOK_EVENTS = ("StopFailure", "SessionStart", "FileChanged")


def load() -> dict:
    return files.read_json(paths.settings_path(), {}) or {}


def save(s: dict) -> None:
    files.backup("settings", files.read_json(paths.settings_path()))
    files.write_json(paths.settings_path(), s)


def is_ours(command) -> bool:
    return isinstance(command, str) and "claudeverse" in command


def statusline_installed() -> bool:
    return is_ours((load().get("statusLine") or {}).get("command"))


def drop_old_api_key_helper() -> None:
    """Older versions could point Claude Code at an API key (apiKeyHelper). Take it out."""
    s = load()
    if is_ours(s.get("apiKeyHelper")):
        del s["apiKeyHelper"]
        save(s)


def _our_hooks(cmd: str) -> dict:
    return {
        "StopFailure": {"matcher": "rate_limit",
                        "hooks": [{"type": "command", "command": f"{cmd} hook-stop-failure"}]},
        # Gives every new session the signal file to watch.
        "SessionStart": {"hooks": [{"type": "command", "command": f"{cmd} hook-session-start"}]},
        # Runs in every session after a switch (even when idle): types the on-switch commands.
        # asyncRewake is for systems where typing is not supported (exit 2 = tell the model).
        "FileChanged": {"matcher": switch_signal.path().name,
                        "hooks": [{"type": "command", "command": f"{cmd} hook-switched",
                                   "async": True, "asyncRewake": True,
                                   "timeout": int(on_switch.DEFAULTS["wait_sec"]) + 60}]},
    }


def install() -> bool:
    """Add our status line and hooks (once). Returns True when the status line that was there
    before keeps showing after ours."""
    s = load()
    cmd = paths.self_command()
    with state.edit() as st:
        line = s.get("statusLine") or {}
        if not is_ours(line.get("command")):
            if line.get("command"):
                st["statusline_then"] = line["command"]  # keep showing the old status line after ours
            s["statusLine"] = {"type": "command", "command": f"{cmd} statusline", "padding": line.get("padding", 0)}
        hooks = s.setdefault("hooks", {})
        for event, group in _our_hooks(cmd).items():
            groups = hooks.setdefault(event, [])
            if not any(is_ours(h.get("command")) for g in groups for h in g.get("hooks", [])):
                groups.append(group)
        if is_ours(s.get("apiKeyHelper")):
            del s["apiKeyHelper"]  # left by an older version (API keys are not used any more)
        save(s)
    switch_signal.ensure_exists()
    return bool(st.get("statusline_then"))


def uninstall() -> None:
    """Take our status line and hooks out again, and put the earlier status line back."""
    s = load()
    with state.edit() as st:
        if is_ours((s.get("statusLine") or {}).get("command")):
            if st.get("statusline_then"):
                s["statusLine"] = {"type": "command", "command": st.pop("statusline_then")}
            else:
                del s["statusLine"]
        for event in OUR_HOOK_EVENTS:
            groups = (s.get("hooks") or {}).get(event) or []
            groups = [g for g in groups if not any(is_ours(h.get("command")) for h in g.get("hooks", []))]
            if groups:
                s["hooks"][event] = groups
            elif "hooks" in s:
                s["hooks"].pop(event, None)
        if "hooks" in s and not s["hooks"]:
            del s["hooks"]
        if is_ours(s.get("apiKeyHelper")):
            del s["apiKeyHelper"]  # left by an older version
        save(s)
