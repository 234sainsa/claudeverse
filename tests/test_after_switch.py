"""After a switch: switched.json, the SessionStart and FileChanged hooks, the on-switch settings,
and reading a session's screen and transcript."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from support import Base
from claudeverse import after_switch, commands, files, hooks, on_switch, screen, switch_signal, transcript


class SignalTests(Base):
    def setUp(self):
        super().setUp()
        self.login("a1", "a@example.com")
        self.quiet(commands.cmd_save, "a")
        self.login("b1", "b@example.com")
        self.quiet(commands.cmd_save, "b")

    def hook(self, session, event="change", windows=False):
        """windows=False: the fallback that tells the model (exit 2). True: typing (recorded, not done)."""
        err = io.StringIO()
        payload = json.dumps({"session_id": session, "event": event, "file_path": str(switch_signal.path())})
        with mock.patch("sys.stdin", io.StringIO(payload)), mock.patch("sys.stderr", err), \
                mock.patch.object(after_switch, "IS_WIN", windows), \
                mock.patch.object(after_switch, "type_after_switch",
                                  lambda data, sig: self.typed.append(data["session_id"])):
            code = hooks.switched()
        return code, err.getvalue()

    typed = None

    def test_windows_types_once_per_session_and_switch(self):
        self.typed = []
        self.quiet(commands.cmd_use, "a")
        code, text = self.hook("s1", windows=True)
        # Typed /remote-control, and the model hears about its agents.
        self.assertEqual(code, 2)
        self.assertIn("may have stopped", text)
        self.assertIn("checked, one by one", text)
        self.assertEqual(self.hook("s1", windows=True), (0, ""))
        self.hook("s2", windows=True)
        self.assertEqual(self.typed, ["s1", "s2"])

    def test_session_start_creates_the_signal_file(self):
        # A session that starts while the file does not exist never hears about a switch.
        self.assertFalse(switch_signal.path().exists())
        with mock.patch("sys.stdin", io.StringIO("{}")), redirect_stdout(io.StringIO()):
            hooks.session_start()
        self.assertTrue(switch_signal.path().exists())
        self.quiet(commands.cmd_use, "a")
        self.assertEqual(files.read_json(switch_signal.path())["seq"], 1)

    def test_on_switch_config(self):
        self.assertEqual(on_switch.config()["commands"], ["/remote-control"])
        self.quiet(commands.cmd_on_switch, "add", ["/color blue"])
        self.assertEqual(on_switch.config()["commands"], ["/remote-control", "/color blue"])
        self.quiet(commands.cmd_on_switch, "set", ["/foo"])
        self.assertEqual(on_switch.config()["commands"], ["/foo"])
        self.quiet(commands.cmd_on_switch, "continue", ["off"])
        self.assertEqual(on_switch.config()["continue_text"], "")
        self.quiet(commands.cmd_on_switch, "clear", [])
        self.assertEqual(on_switch.config()["commands"], [])
        self.quiet(commands.cmd_on_switch, "reset", [])
        self.assertEqual(on_switch.config(), on_switch.DEFAULTS)

    def test_switch_writes_signal_and_wakes_each_session_once(self):
        self.quiet(commands.cmd_use, "a")
        sig = files.read_json(switch_signal.path())
        self.assertEqual((sig["seq"], sig["from"], sig["to"]), (1, "b", "a"))
        code, text = self.hook("s1")
        self.assertEqual(code, 2)
        self.assertIn("/remote-control", text)
        self.assertIn("'b' to 'a'", text)
        self.assertEqual(self.hook("s1"), (0, ""))  # same switch, second file event
        self.assertEqual(self.hook("s2")[0], 2)    # another session
        self.quiet(commands.cmd_use, "a")                 # no change: no new signal
        self.assertEqual(files.read_json(switch_signal.path())["seq"], 1)
        self.quiet(commands.cmd_use, "b")
        self.assertEqual(self.hook("s1")[0], 2)

    def test_session_start_watches_the_signal(self):
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("{}")), redirect_stdout(out):
            hooks.session_start()
        data = json.loads(out.getvalue())
        self.assertEqual(data["hookSpecificOutput"]["watchPaths"], [str(switch_signal.path())])


class ScreenAndTranscriptTests(unittest.TestCase):
    RULE = "─" * 40

    def screen(self, box, busy=False):
        lines = ["", " ▐▛███▛█   Claude Code", "", "● OK", ""]
        if busy:
            lines.append("✻ Thinking… (3s · esc to interrupt)")
        lines += [self.RULE, box, self.RULE, "  ⏵⏵ auto mode on (shift+tab to cycle)", ""]
        return lines, lines.index(box)

    def test_prompt_ready(self):
        lines, row = self.screen("❯\xa0")
        self.assertTrue(screen.prompt_ready(lines, (2, row)))
        lines, row = self.screen('❯\xa0Try "write a test for <filepath>"')   # example text: cursor at the start
        self.assertTrue(screen.prompt_ready(lines, (2, row)))
        lines, row = self.screen("❯\xa0abc")                                 # typed: cursor after the text
        self.assertFalse(screen.prompt_ready(lines, (5, row)))
        lines, row = self.screen("❯\xa0", busy=True)
        self.assertFalse(screen.prompt_ready(lines, (2, row)))
        self.assertTrue(screen.is_busy(["* Julienning…(19s · ↓ 96 tokens)", self.RULE, "❯ busy draft"]))
        self.assertFalse(screen.is_busy(["✻ Churned for 37s · done 9:51 AM", self.RULE, "❯"]))
        dialog = ["", "Remote Control", "❯ 1. Disconnect", "  2. Cancel", ""]   # a menu, not the input box
        self.assertFalse(screen.prompt_ready(dialog + [self.RULE], (0, 0)))

    def test_waiting_for_reset(self):
        lines, _ = self.screen("❯\xa0")
        self.assertFalse(screen.waiting_for_reset(lines))
        lines += ["  ⚠ Usage limit reached · limit resets 10:17am",
                  "    Continuing automatically at 10:17am · Esc to cancel"]
        self.assertTrue(screen.waiting_for_reset(lines))
        # Newer Claude Code keeps the turn open and retries (seen on 2026-11-05).
        lines, _ = self.screen("❯\xa0")
        self.assertTrue(screen.waiting_for_reset(
            lines[:5] + ["✻", "Weekly li… · Retrying in 5h (Nov 7, 6am) · attempt 1/15", ""] + lines[5:]))

    def test_remote_control_retry_dialog(self):
        dialog = ["   Remote Control", "   × Remote Control isn't connected.",
                  "  ❯ /remote-control                   Disconnect Remote Control",
                  "── To try again, choose Continue, wait about 10 seconds for Remote─Control─to─switch─off,─then",
                  "   ❯ Continue", "   Enter to select · Esc to continue"]
        self.assertTrue(screen.remote_control_says_retry(dialog))
        self.assertFalse(screen.remote_control_says_retry(["  /remote-control is active · Continue here"]))

    def write(self, records):
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        self.addCleanup(os.unlink, f.name)
        for r in records:
            f.write(json.dumps(r) + "\n")
        f.close()
        return f.name

    LIMIT = {"type": "assistant", "error": "rate_limit", "isApiErrorMessage": True,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "You've hit your limit"}]}}
    ASK = {"type": "user", "message": {"role": "user", "content": "do it"}}
    REPLY = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}}
    LOCAL = {"type": "user", "message": {"role": "user",
                                         "content": "<command-name>/remote-control</command-name>"}}

    def test_stopped_at_limit(self):
        self.assertTrue(transcript.stopped_at_limit(self.write([self.ASK, self.LIMIT, {"type": "system"}])))
        self.assertTrue(transcript.stopped_at_limit(self.write([self.ASK, self.LIMIT, self.LOCAL])))
        self.assertFalse(transcript.stopped_at_limit(self.write([self.ASK, self.LIMIT, self.ASK, self.REPLY])))
        self.assertFalse(transcript.stopped_at_limit(self.write([self.ASK, self.REPLY])))
        self.assertFalse(transcript.stopped_at_limit(None))


class WindowsCodeIsolationTests(unittest.TestCase):
    def test_the_command_line_loads_without_the_windows_console_code(self):
        # The ctypes code is loaded only when something is typed into a session (Windows).
        src = str(Path(__file__).resolve().parent.parent / "src")
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import claudeverse.cli; "
                "print(sorted(m for m in sys.modules if m.startswith('claudeverse.') "
                "and m.split('.')[1] in ('win_console', 'session_typing')))")
        r = subprocess.run([sys.executable, "-I", "-c", code, src], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
