"""The switch: make a saved profile the login Claude Code uses, and tell running sessions.
"""
from __future__ import annotations

from . import Error, claude_settings, credentials, files, profiles, switch_signal


def switch_to(name: str, why: str = "manual") -> None:
    """Make `name` the login Claude Code uses. Call with the Lock held."""
    meta = profiles.load_meta(name)
    if meta.get("kind") == "apikey":
        raise Error(f"'{name}' is an API key saved by an older claudeverse; API keys are not used any more "
                    f"(delete it: claudeverse remove {name})")
    before = profiles.current_profile()
    profiles.sync_back()
    secret = profiles.load_secret(name)
    if not secret.get("claudeAiOauth"):
        raise Error(f"profile '{name}' has no saved login")
    credentials.replace_live_login(secret["claudeAiOauth"], secret.get("oauthAccount"))
    claude_settings.drop_old_api_key_helper()
    files.log_event(f"switch to={name} why={why}")
    if before != name:
        switch_signal.announce(before, name, why)
