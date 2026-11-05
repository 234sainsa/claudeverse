"""What claudeverse puts into Claude Code: the status line, and settings.json (install, uninstall)."""
import io
import json
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from support import Base
from claudeverse import claude_settings, commands, files, paths, profiles, state, statusline


class ReloginTests(Base):
    def test_login_inside_claude_code_is_kept_in_the_profile(self):
        self.login("a1", "a@example.com")
        self.quiet(commands.cmd_save, "a")
        self.login("a2", "a@example.com")  # the login expired; /login in Claude Code, same account
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("{}")), redirect_stdout(out):
            statusline.run()
        self.assertEqual(profiles.load_secret("a")["claudeAiOauth"], self.live()["claudeAiOauth"])

    def test_statusline_warns_before_the_login_expires(self):
        self.login("a1", "a@example.com")
        self.quiet(commands.cmd_save, "a")
        meta = profiles.load_meta("a")
        meta["loginExpiresAt"] = int((time.time() + 86400) * 1000)
        profiles.save_profile("a", meta, profiles.load_secret("a"))
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("{}")), redirect_stdout(out), \
                mock.patch.object(profiles, "sync_back", lambda: "a"):
            statusline.run()
        self.assertIn("ログインの期限", out.getvalue())


class StatusLineTests(Base):
    def test_statusline_shows_usage_in_words(self):
        self.login("a1", "a@example.com")
        self.quiet(commands.cmd_save, "a")
        data = {"rate_limits": {"seven_day": {"used_percentage": 94, "resets_at": time.time() + 3 * 86400}}}
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(data))), redirect_stdout(out):
            statusline.run()
        self.assertRegex(out.getvalue(), r"^\[a\] 1週間 94%\(\d{1,2}/\d{1,2} \d{1,2}:\d\d\)")


class InstallTests(Base):
    def test_install_keeps_existing_status_line_and_hooks(self):
        files.write_json(paths.settings_path(), {
            "statusLine": {"type": "command", "command": "my-line"},
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]},
            "theme": "dark"})
        self.quiet(commands.cmd_install)
        self.quiet(commands.cmd_install)  # twice: no duplicates
        s = claude_settings.load()
        self.assertEqual(s["statusLine"]["command"], "claudeverse statusline")
        self.assertEqual(len(s["hooks"]["StopFailure"]), 1)
        self.assertEqual(len(s["hooks"]["SessionStart"]), 1)
        fc = s["hooks"]["FileChanged"][0]
        self.assertEqual(fc["matcher"], "switched.json")
        self.assertTrue(fc["hooks"][0]["async"] and fc["hooks"][0]["asyncRewake"])
        self.assertEqual(state.load()["statusline_then"], "my-line")
        self.quiet(commands.cmd_uninstall)
        s = claude_settings.load()
        self.assertEqual(s["statusLine"]["command"], "my-line")
        self.assertEqual(s["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]})
        self.assertEqual(s["theme"], "dark")


if __name__ == "__main__":
    unittest.main()
