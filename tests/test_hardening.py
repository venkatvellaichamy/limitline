"""0.14.0 display hardening: the display stays honest when Pharos's files are bad.

Synthetic files in a temp dir only (LIMITLINE_PHAROS_HOME, XDG_CACHE_HOME); nothing here
reads the real ~/.pharos. One test per case in ROADMAP.md "0.14.0 — Display hardening".
"""

import builtins
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "tests"))
import fivelines  # noqa: E402
import pharos_view  # noqa: E402
import test_fivelines  # noqa: E402  (not `from ... import FiveLines`: that would run its tests twice)

NOW, plain = test_fivelines.NOW, test_fivelines.plain

# The status line must redraw in about 50 ms on a Mac; CI raises it like tests/run.sh does.
BUDGET_MS = max(50, int(os.environ.get("LIMITLINE_SPEED_MS") or 50))


class Hardening(unittest.TestCase):
    # The same synthetic Pharos home and cache as test_fivelines (a temp dir per test).
    setUp = test_fivelines.FiveLines.setUp
    tearDown = test_fivelines.FiveLines.tearDown
    write_usage = test_fivelines.FiveLines.write_usage
    summary = test_fivelines.FiveLines.summary

    def used(self, **kw):
        return plain(fivelines.build(now=NOW, **kw))[0]

    def age_grok_line(self, seconds):
        when = NOW - seconds
        os.utime(self.cache / "grok.line", (when, when))

    # ---- Pharos files missing ---------------------------------------------------------

    def test_pharos_files_missing_says_not_running(self):
        (self.pharos / "usage.json").unlink()
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines, ["used  ✻ claude 7d ███▌░ · pharos not running"],
                         "Claude's own line still works and the gap is named")
        shutil.rmtree(self.pharos)
        self.assertEqual(plain(fivelines.build(now=NOW)), ["used  ✻ claude 7d ███▌░"],
                         "without Pharos installed at all, Claude only and no complaint")

    # ---- Old reading ------------------------------------------------------------------

    def test_old_reading_shows_age_never_an_old_percent(self):
        self.usage["generated_at"] = NOW - 3600
        self.usage["plans"][0]["observed_at"] = NOW - 3600
        self.usage["hosts"]["observed_at"] = NOW - 3600
        self.usage["plans"].append({"provider": "codex", "observed_at": NOW - 3600, "windows": [
            {"name": "7d", "used_pct": 33, "resets_at": NOW + 86400}]})
        self.write_usage()
        for key in ("LL_CODEX5", "LL_CODEX5_RESET", "LL_CODEX7", "LL_CODEX7_RESET"):
            del os.environ[key]
        self.age_grok_line(3600)
        lines = plain(fivelines.build(now=NOW))
        used = lines[0]
        self.assertIn("✻ claude 7d ███▌░", used, "Claude comes from this session's own input")
        self.assertIn("codex 7d — 1h ago", used)
        self.assertIn("cursor+grok — 1h ago", used)
        self.assertIn("gemini — 1h ago", used)
        self.assertTrue(used.endswith(" · 1h old"), used)
        self.assertNotIn("33", used)
        self.assertNotIn("81", used)
        rest = used.split("◎", 1)[1]
        self.assertFalse(set(rest) & set("█▉▊▋▌▍▎▏"), "no bar drawn from an old reading: " + rest)
        self.assertEqual(lines[-1], "hosts — 1h ago", "old host numbers are not shown as current")

    def test_old_claude_cache_is_not_current(self):
        for key in ("LL_CLAUDE7", "LL_CLAUDE7_RESET"):
            del os.environ[key]
        (self.cache / "claude.json").write_text(json.dumps({"observed_at": NOW - 2 * 3600, "windows": [
            {"name": "7d", "used_pct": 70, "resets_at": NOW + 86400}]}))
        self.assertIn("✻ claude 7d — 2h ago", self.used())

    # ---- Reset time already passed ------------------------------------------------------

    def test_reset_passed_says_so(self):
        os.environ["LL_CODEX5_RESET"] = str(NOW - 10)
        self.usage["plans"][0]["windows"][3]["resets_at"] = NOW - 60  # argon
        self.write_usage()
        line = self.used()
        self.assertIn("codex 5h reset, no newer reading · 7d ███▌░", line)
        self.assertIn("argon reset, no newer reading", line)
        self.assertNotIn("100", line)
        narrow = self.used(columns=fivelines.width(line) - 1)
        self.assertIn("codex 5h reset · 7d", narrow, "the short form when space is tight")

    def test_reset_passed_from_pharos_codex_plan(self):
        for key in ("LL_CODEX5", "LL_CODEX5_RESET", "LL_CODEX7", "LL_CODEX7_RESET"):
            del os.environ[key]
        self.usage["plans"].append({"provider": "codex", "observed_at": NOW - 60, "windows": [
            {"name": "5h", "used_pct": 99, "resets_at": NOW - 5},
            {"name": "7d", "used_pct": 69, "resets_at": NOW + 4 * 86400}]})
        self.write_usage()
        self.assertIn("codex 5h reset, no newer reading · 7d ███▌░", self.used())

    # ---- Partial or invalid JSON --------------------------------------------------------

    def test_partial_fields_show_a_dash(self):
        windows = self.usage["plans"][0]["windows"]
        windows[2]["used_pct"] = "n/a"   # claude+gpt
        windows[3]["used_pct"] = True    # argon: a bool is not a percent
        self.usage["plans"].append({"provider": "codex", "observed_at": NOW - 60, "windows": "garbage"})
        self.usage["hosts"]["hosts"][0]["free_pct"] = "?"
        self.usage["hosts"]["hosts"][0]["load_pct"] = float("nan")
        self.write_usage()
        today = dict(dict.fromkeys(fivelines.KEYS, 0), done="lots", running=1)
        (self.pharos / "summary.json").write_text(json.dumps(
            {"generated_at": NOW, "today": today, "older": ["not", "a", "dict"], "oldest_open": "h"}))
        os.environ["LL_ANIMATE"] = "off"
        lines = plain(fivelines.build(now=NOW))
        self.assertIn("claude+gpt —", lines[0])
        self.assertIn("argon —", lines[0])
        self.assertIn("gemini ░░░░░", lines[0], "the good bucket still shows")
        self.assertTrue(lines[1].startswith("today ▶ 1 running │ ✓ — done"), lines[1])
        self.assertEqual(lines[-1], "hosts studio — │ laptop 49% · 45% │ backup offline")

    def test_truncated_usage_never_guesses(self):
        (self.pharos / "usage.json").write_text('{"version": 1, "generated_at": %d, "plans": [{"provider": "antig' % NOW)
        self.summary(today={"done": 1})
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines[0], "used  ✻ claude 7d ███▌░ · pharos usage.json unreadable")
        self.assertTrue(lines[1].startswith("today"), "a bad usage.json does not blank the job lines")

    def test_bad_summary_does_not_blank_other_lines(self):
        (self.pharos / "summary.json").write_text(json.dumps({"generated_at": NOW, "today": {"done": 1}, "older": 7, "oldest_open": [1]}))
        lines = plain(fivelines.build(now=NOW))
        self.assertTrue(lines[0].startswith("used"))
        self.assertTrue(any(line.startswith("today") for line in lines))
        self.assertTrue(lines[-1].startswith("hosts"))

    # ---- Unknown fields or a newer format -------------------------------------------------

    def test_unknown_fields_ignored(self):
        self.usage["shiny_new_block"] = {"x": 1}
        self.usage["plans"][0]["windows"][0]["burn_rate"] = 3
        self.usage["plans"][0]["sparkle"] = True
        self.write_usage()
        self.assertIn("agy gemini ░░░░░ · claude+gpt ▍░░░░ · argon █████", self.used())

    def test_newer_format_is_named_not_drawn(self):
        self.usage["version"] = 2
        self.write_usage()
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines[0], "used  ✻ claude 7d ███▌░ · pharos format v2 is newer than this limitline")
        self.assertFalse(any(line.startswith("hosts") for line in lines), "no numbers from a format it cannot read")
        self.assertIsNone(pharos_view.read_usage(now=NOW), "the caches for line 1 skip it too")
        (self.pharos / "summary.json").write_text(json.dumps({"version": 3, "generated_at": NOW, "today": {"done": 4}}))
        self.usage["version"] = 1
        self.write_usage()
        lines = plain(fivelines.build(now=NOW))
        self.assertIn("today — pharos summary format v3 is newer than this limitline", lines)

    # ---- Clock skew ------------------------------------------------------------------------

    def test_future_readings_are_not_fresh(self):
        self.usage["generated_at"] = NOW + 3600
        self.usage["plans"][0]["observed_at"] = NOW + 3600
        self.write_usage()
        self.age_grok_line(-3600)
        line = self.used()
        self.assertIn("gemini —", line)
        self.assertIn("cursor+grok —", line)
        self.assertNotIn("ago", line, "no negative ages")
        self.assertTrue(line.endswith(" · pharos clock ahead"), line)
        self.assertNotIn("81", line)
        self.assertNotIn("1m", line)
        usage = pharos_view.read_usage(now=NOW)
        self.assertTrue(usage["stale"], "pharos_view does not call a future reading fresh either")

    def test_small_skew_is_tolerated(self):
        self.usage["generated_at"] = NOW + 30
        self.usage["plans"][0]["observed_at"] = NOW + 30
        self.write_usage()
        self.age_grok_line(-30)
        line = self.used()
        self.assertIn("cursor+grok ████░", line)
        self.assertIn("argon █████", line)
        self.assertNotIn("ahead", line)

    def test_future_event_and_summary_are_not_today(self):
        self.summary(today={"done": 2}, generated=NOW + 6 * 3600)
        lines = plain(fivelines.build(now=NOW))
        self.assertFalse(any(line.startswith("today") for line in lines), "a summary from the future is not today's")
        self.summary(today={"done": 2})
        folder = self.pharos / "events"
        folder.mkdir()
        with (folder / time.strftime("%Y-%m-%d", time.localtime(NOW))).with_suffix(".jsonl").open("w") as handle:
            handle.write(json.dumps({"ts": NOW + 3600, "kind": "run.status", "data": {"status": "merged", "repo": "x"}}) + "\n")
        today = [line for line in plain(fivelines.build(now=NOW)) if line.startswith("today")][0]
        self.assertNotIn("merged", today)

    def test_age_label_never_negative(self):
        self.assertEqual(fivelines.age_label(-500), "0m")

    # ---- Narrow terminal ---------------------------------------------------------------------

    def test_narrow_drops_lowest_priority_segment_first(self):
        self.summary(today={"running": 1, "done": 5, "need_you": 3, "failed": 2},
                     older={"need_you": 4, "failed": 1}, oldest={"id": "h", "repo": "pharos-reviews", "age_hours": 150})
        os.environ["LL_ANIMATE"] = "off"
        for columns in (70, 50, 40, 30):
            lines = plain(fivelines.build(now=NOW, columns=columns))
            for line in lines:
                self.assertLessEqual(fivelines.width(line), columns, f"{columns}: {line}")
            self.assertTrue(lines[0].startswith("used  ✻ claude 7d"), "Claude is never dropped")
        at50 = plain(fivelines.build(now=NOW, columns=50))[0]
        self.assertNotIn("agy", at50, "agy goes first")
        self.assertIn("codex", at50, "codex outranks cursor+grok and agy")

    # ---- Slow disk ---------------------------------------------------------------------------

    def test_slow_disk_render_stays_under_budget(self):
        self.summary(today={"running": 1, "done": 1})
        (self.pharos / "usage-report.json").write_text(json.dumps({"daily": {}}))
        real_open = builtins.open

        def slow_open(*args, **kwargs):
            time.sleep(0.006)  # every file read costs 6 ms
            return real_open(*args, **kwargs)

        fivelines.open = slow_open
        try:
            fivelines.build(now=NOW, columns=80)  # warm up imports
            start = time.perf_counter()
            fivelines.build(now=NOW, columns=80)
            took = (time.perf_counter() - start) * 1000
        finally:
            del fivelines.open
        self.assertLess(took, BUDGET_MS, f"render took {took:.0f} ms on a slow disk")

    def test_fifo_in_place_of_a_file_never_blocks(self):
        (self.pharos / "usage.json").unlink()
        os.mkfifo(self.pharos / "usage.json")
        os.mkfifo(self.pharos / "summary.json")
        env = dict(os.environ, LIMITLINE_NOW=str(NOW))
        start = time.perf_counter()
        try:
            out = subprocess.run([sys.executable, str(ROOT / "lib" / "fivelines.py")], env=env,
                                 capture_output=True, text=True, timeout=5).stdout
        except subprocess.TimeoutExpired:
            self.fail("the status line blocked on a FIFO")
        self.assertLess((time.perf_counter() - start) * 1000, 1000)
        self.assertIn("claude 7d", out)


if __name__ == "__main__":
    unittest.main()
