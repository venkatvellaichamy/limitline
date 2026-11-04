"""lib/fivelines.py: lines 2-5 of the five-line status line."""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import fivelines  # noqa: E402

NOW = int(datetime(2026, 11, 3, 17, 0, 0).timestamp())
TODAY = datetime(2026, 11, 3, 9, 0, 0).timestamp()
YESTERDAY = datetime(2026, 11, 2, 9, 0, 0).timestamp()
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(lines):
    return [ANSI.sub("", line) for line in lines]


class FiveLines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.cache = base / "cache" / "limitline"
        self.cache.mkdir(parents=True)
        self.pharos = base / "pharos"
        (self.pharos / "runs").mkdir(parents=True)
        self.saved = dict(os.environ)
        for key in list(os.environ):
            if key.startswith("LL_") or key.startswith("LIMITLINE_"):
                del os.environ[key]
        os.environ.update({
            "XDG_CACHE_HOME": str(base / "cache"),
            "LIMITLINE_PHAROS_HOME": str(self.pharos),
            "LL_COLOR": "0",
            "LL_CLAUDE7": "70", "LL_CLAUDE7_RESET": str(NOW + 11 * 3600),
            "LL_CODEX5": "99", "LL_CODEX5_RESET": str(NOW + 3600),
            "LL_CODEX7": "69", "LL_CODEX7_RESET": str(NOW + 4 * 86400),
        })
        (self.cache / "grok.line").write_text("cursor+grok 81% · Thu 23:22 · grok 7d 39.8M tok\n81 0 live\n")
        os.utime(self.cache / "grok.line", (NOW - 60, NOW - 60))  # written a minute before NOW
        # What Pharos measured (`pharos usage`). limitline only draws it.
        self.usage = {"version": 1, "generated_at": NOW - 60, "plans": [
            {"provider": "antigravity", "observed_at": NOW - 60, "stale": False, "windows": [
                {"group": "Gemini Models", "resets_at": NOW + 3 * 86400, "used_pct": 0, "window": "weekly"},
                {"group": "Gemini Models", "resets_at": NOW + 3600, "used_pct": 0, "window": "5h"},
                {"group": "Claude and GPT models", "resets_at": NOW + 3 * 86400, "used_pct": 7, "window": "weekly"},
                {"group": "Gemini 4 Argon", "resets_at": NOW + 3 * 86400, "used_pct": 100, "window": "weekly"},
            ]}],
            "hosts": {"observed_at": NOW - 60, "hosts": [
                {"name": "studio", "free_pct": 82, "load_pct": 22, "reachable": True},
                {"name": "laptop", "free_pct": 49, "load_pct": 45, "reachable": True},
                {"name": "backup", "reachable": False},
            ]}}
        self.write_usage()

    def write_usage(self):
        (self.pharos / "usage.json").write_text(json.dumps(self.usage))

    def summary(self, today=None, older=None, oldest=None, generated=NOW):
        data = {"generated_at": generated, "today": dict(dict.fromkeys(("running", "done", "need_you", "failed", "retried", "waiting_limit"), 0), **(today or {})),
                "older": dict(dict.fromkeys(("running", "done", "need_you", "failed", "retried", "waiting_limit"), 0), **(older or {})), "oldest_open": oldest}
        (self.pharos / "summary.json").write_text(json.dumps(data))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def state(self, id_, status, started, **extra):
        folder = self.pharos / "runs" / id_
        folder.mkdir()
        (folder / "state.json").write_text(json.dumps({"id": id_, "status": status, "started_at": started, "repo": "/r/pharos", **extra}))

    def test_used_bars_in_fixed_order_with_marks(self):
        line = plain(fivelines.build(now=NOW))[0]
        self.assertTrue(line.startswith("used  ✻ claude 7d ███▌░"), line)
        order = [line.index(word) for word in ("claude", "◎ codex", "⬡ cursor+grok", "✦ agy")]
        self.assertEqual(order, sorted(order))
        self.assertIn("codex 5h █████ →18:00 · 7d ███▌░", line)
        self.assertIn("cursor+grok ████░ →Thu 23:22", line)
        self.assertIn("agy gemini ░░░░░ · claude+gpt ▍░░░░ · argon █████ →", line)
        self.assertNotIn("left", line)
        self.assertNotIn("gemini app", line.lower())

    def test_every_plan_reads_the_same_way(self):
        """Antigravity used to look backwards next to the others; now all bars fill as they are used."""
        filled, empty = fivelines.used_bar(0)
        self.assertEqual((filled, empty), ("", "░░░░░"))
        self.assertEqual(fivelines.used_bar(100), ("█████", ""))
        self.assertEqual(fivelines.used_bar(70), ("███▌", "░"))
        self.assertNotEqual(fivelines.used_bar(70), fivelines.used_bar(82), "70% and 82% look different")
        self.assertEqual(fivelines.used_bar(50, ascii=True), ("###", "--"))
        for used in range(0, 101):
            filled, empty = fivelines.used_bar(used)
            self.assertEqual(len(filled) + len(empty), 5)

    def test_number_modes(self):
        os.environ["LL_PLAN_NUMBERS"] = "on"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d ███▌░ 70%", line)
        self.assertIn("argon █████ 100%", line)
        os.environ["LL_PLAN_VIEW"] = "none"
        os.environ["LL_PLAN_NUMBERS"] = "off"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("agy gemini 0% · claude+gpt 7% · argon 100% →", line, "none always shows numbers")

    def test_gauge_with_numbers(self):
        os.environ.update({"LL_PLAN_VIEW": "gauge", "LL_PLAN_NUMBERS": "on"})
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d ▆ 70%", line)
        self.assertIn("cursor+grok ▇ 81%", line)
        self.assertIn("agy gemini ▁ 0% · claude+gpt ▁ 7% · argon █ 100%", line)

    def test_dots(self):
        os.environ["LL_PLAN_VIEW"] = "dots"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d ◕", line)
        self.assertIn("agy gemini ○ · claude+gpt ○ · argon ●", line)

    def test_trend_from_pharos_daily_with_live_today(self):
        (self.pharos / "usage-report.json").write_text(json.dumps({"daily": {
            "claude": {"7d": [None, None, 10, 25, 40, 55, 60]},
            "antigravity": {"argon": [None, None, None, None, None, 100, 100]}}}))
        self.usage["plans"][0]["windows"][3]["id"] = "argon"
        self.write_usage()
        os.environ["LL_PLAN_VIEW"] = "trend"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d ··▁▂▄▅▆", line, "no reading is a dot; today is the live 70%, not 60")
        self.assertIn("argon ·····██", line)
        self.assertIn("codex 5h ·······", line.replace("█", "·"), "no series: dots, then today's level")

    def test_cap_mark_over_cap_and_pace(self):
        self.usage["plans"].append({"key": "claude", "provider": "claude", "cap_pct": 60, "windows": []})
        self.write_usage()
        os.environ["LL_PLAN_VIEW"] = "cap"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d █████│▋░░ over cap", line, "the cap comes from Pharos (60 here: after 5 of 8 cells)")
        self.assertIn("7d █████▌│░░ ▲", line, "codex 69% with 3 of 7 days gone: ahead of pace")
        self.assertIn("argon ██████│██ over cap", line)
        self.assertIn("claude+gpt ▌░░░░░│░░", line, "default cap 75 when Pharos gives none")
        cell = fivelines.Cell("7d", 55, reset=NOW + 4 * 86400)
        self.assertTrue(cell.pace_ahead(NOW), "55% used with 3 of 7 days (43%) gone is ahead of pace")
        self.assertFalse(fivelines.Cell("7d", 30, reset=NOW + 4 * 86400).pace_ahead(NOW))

    def test_left_inverts_the_number_not_the_meaning(self):
        os.environ.update({"LL_PLAN_SHOW": "left", "LL_PLAN_VIEW": "gauge", "LL_PLAN_NUMBERS": "on", "LL_COLOR": "1"})
        raw = fivelines.build(now=NOW)[0]
        line = plain([raw])[0]
        self.assertTrue(line.startswith("left  ✻ claude 7d ▃ 30%"), line)
        self.assertIn("argon ▁ 0%", line)
        self.assertIn("gemini █ 100%", line)
        self.assertIn("\x1b[31m▁\x1b[0m", raw, "spent argon stays red in left mode")

    def test_every_view_handles_every_value(self):
        for view in fivelines.VIEWS:
            for show in ("used", "left"):
                os.environ.update({"LL_PLAN_VIEW": view, "LL_PLAN_SHOW": show})
                style = fivelines.Style()
                for used in (0, 0.4, 12.5, 49.9, 50, 74.9, 75, 80, 80.1, 99.6, 100):
                    cell = fivelines.Cell("7d", used, reset=NOW + 3600)
                    cell.trend = [None, 0, used, None, 100, 50, used]
                    self.assertTrue(cell.text(style, NOW))

    def test_resets_always_behind_the_flag(self):
        os.environ["LL_PLAN_RESETS"] = "always"
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("claude 7d ███▌░ →Wed 04:00", line, "Claude at 70% still shows when it refills")
        self.assertIn("codex 5h █████ →18:00 · 7d ███▌░ →Sat 17:00", line)
        self.assertIn("gemini ░░░░░ →Fri 17:00", line, "even an unused window says when it refills")

    def test_resets_dropped_first_when_narrow(self):
        os.environ["LL_PLAN_RESETS"] = "always"
        line = plain(fivelines.build(now=NOW, columns=110))[0]
        self.assertNotIn("→", line)
        self.assertIn("claude 7d ███▌░", line)

    def test_reset_only_shown_at_the_cap_by_default(self):
        line = plain(fivelines.build(now=NOW))[0]
        self.assertNotIn("claude 7d ███▌░ →", line)
        self.assertNotIn("7d ███▌░ →", line)

    def test_colours_match_line_one(self):
        self.assertEqual(fivelines.used_code(49), "32")
        self.assertEqual(fivelines.used_code(50), "33")
        self.assertEqual(fivelines.used_code(80), "33")
        self.assertEqual(fivelines.used_code(81), "31")
        os.environ["LL_COLOR"] = "1"
        line = fivelines.build(now=NOW)[0]
        self.assertIn("\x1b[31m█████\x1b[0m", line)
        self.assertIn("\x1b[33m███▌\x1b[0m", line)

    def test_narrow_terminal_uses_short_bars(self):
        line = plain(fivelines.build(now=NOW, columns=60))[0]
        self.assertIn("claude 7d ██▏", line)

    def test_missing_reading_is_a_dash_not_a_number(self):
        for key in ("LL_CODEX5", "LL_CODEX5_RESET", "LL_CODEX7", "LL_CODEX7_RESET"):
            del os.environ[key]
        os.environ["LL_CODEX_CACHE"] = str(Path(self.tmp.name) / "none")
        self.usage["plans"] = []
        self.write_usage()
        left = plain(fivelines.build(now=NOW))[0]
        self.assertIn("◎ codex 7d —", left)
        self.assertIn("✦ agy gemini —", left)

    def test_expired_window_says_it_reset(self):
        # 0.14.0: the old 99% is never shown, and the gap is named instead of hidden.
        os.environ["LL_CODEX5_RESET"] = str(NOW - 10)
        line = plain(fivelines.build(now=NOW))[0]
        self.assertIn("codex 5h reset, no newer reading", line)
        self.assertNotIn("█████ →18:00", line)

    def test_marks_none(self):
        os.environ["LL_MARKS"] = "none"
        left = plain(fivelines.build(now=NOW))[0]
        self.assertNotIn("✻", left)
        self.assertTrue(left.startswith("used  claude 7d ███▌░"))

    def test_today_and_older_from_pharos_summary(self):
        os.environ["LL_ANIMATE"] = "off"
        self.summary(today={"running": 2, "done": 2, "need_you": 1, "retried": 1, "waiting_limit": 1},
                     older={"need_you": 1}, oldest={"id": "h", "repo": "pharos", "age_hours": 32})
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines[1], "today ▶ 2 running │ ✓ 2 done │ ✋ 1 need you │ ✗ 0 failed · ↻ 1 retried │ ⏸ 1 waiting on limit")
        self.assertEqual(lines[2], "older ✋ 1 need you │ oldest 1d (pharos)")

    def test_attention_counts_and_reason(self):
        self.summary(today={"working": 2, "blocked": 1, "need_you": 1})
        path = self.pharos / "summary.json"
        data = json.loads(path.read_text())
        data["recent"] = [{"state": "working", "owner": "agent", "reason": "busy"},
                          {"state": "blocked", "owner": "you", "reason": "ready to merge (PR #40)"}]
        path.write_text(json.dumps(data))
        line = plain(fivelines.build(now=NOW))[1]
        self.assertIn("⚙ 2 working", line)
        self.assertIn("⛔ 1 blocked: ready to merge (PR #40)", line)
        os.environ["LL_JOBS_DETAIL"] = "counts"
        self.assertNotIn("ready to merge", plain(fivelines.build(now=NOW))[1])
        os.environ["LL_JOBS_DETAIL"] = "reason"
        self.assertNotIn("ready to merge", plain(fivelines.build(now=NOW, columns=len(line) - 1))[1])
        os.environ["LL_COLOR"] = "1"
        self.assertIn("\x1b[33m⛔ 1 blocked", fivelines.build(now=NOW)[1])

    def test_attention_reason_is_bounded_and_handles_bad_rows(self):
        self.summary(today={"need_you": 1}, older={"blocked": 1})
        path = self.pharos / "summary.json"
        data = json.loads(path.read_text())
        data["recent"] = [None, {"owner": "agent", "state": "working", "reason": "busy"},
                          {"owner": "you", "state": "need_you", "reason": "x" * 100},
                          {"owner": "you", "state": "blocked", "reason": "approve access"}]
        path.write_text(json.dumps(data))
        lines = plain(fivelines.build(now=NOW))
        self.assertIn("✋ 1 need you: " + "x" * 79 + "…", lines[1])
        self.assertIn("⛔ 1 blocked: approve access", lines[2])
        data["recent"] = "invalid"
        path.write_text(json.dumps(data))
        self.assertNotIn(":", plain(fivelines.build(now=NOW))[1])

    def test_older_hidden_when_empty(self):
        self.summary(today={"running": 1})
        lines = plain(fivelines.build(now=NOW))
        self.assertTrue(lines[1].startswith("today"))
        self.assertTrue(lines[2].startswith("hosts"))

    def test_yesterdays_summary_is_not_shown_as_today(self):
        self.summary(today={"done": 9}, generated=NOW - 86400)
        lines = plain(fivelines.build(now=NOW))
        self.assertFalse(any(line.startswith("today") for line in lines))

    def test_without_pharos_only_claude(self):
        # Pharos not installed (no home). With a home but no usage.json, see test_hardening.
        import shutil
        shutil.rmtree(self.pharos)
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines, ["used  ✻ claude 7d ███▌░"])

    def test_stale_pharos_usage_shows_dashes_for_agy(self):
        self.usage["generated_at"] = NOW - 3600
        self.write_usage()
        self.assertIn("✦ agy gemini —", plain(fivelines.build(now=NOW))[0])

    # ---- live feel: spinner, event note, change highlight, stale age --------------------

    def event(self, kind, data, ts, subject="s"):
        folder = self.pharos / "events"
        folder.mkdir(exist_ok=True)
        path = folder / (datetime.fromtimestamp(ts).strftime("%Y-%m-%d") + ".jsonl")
        with path.open("a") as handle:
            handle.write(json.dumps({"id": 1, "ts": ts, "kind": kind, "subject": subject, "data": data}) + "\n")

    def test_spinner_turns_only_while_running(self):
        self.summary(today={"running": 1})
        frames = {plain(fivelines.build(now=NOW + 2 * i))[1].split()[1] for i in range(4)}
        self.assertEqual(frames, set("◐◓◑◒"))
        self.summary(today={"running": 0})
        self.assertEqual(plain(fivelines.build(now=NOW))[1].split()[1], "▶")
        os.environ["LL_ANIMATE"] = "off"
        self.summary(today={"running": 1})
        self.assertEqual(plain(fivelines.build(now=NOW))[1].split()[1], "▶")

    def test_event_note_for_30_seconds(self):
        self.summary(today={"done": 1})
        self.event("run.status", {"status": "merged", "repo": "pharos"}, NOW - 5)
        self.assertTrue(plain(fivelines.build(now=NOW))[1].endswith(" · ✓ pharos merged"))
        self.assertFalse(plain(fivelines.build(now=NOW + 40))[1].endswith("merged"))

    def test_event_texts(self):
        self.assertEqual(fivelines.event_text({"kind": "usage.threshold", "data": {"plan": "claude", "window": "7d", "threshold": 75}}), "⚠ claude 7d 75% used")
        self.assertEqual(fivelines.event_text({"kind": "host.offline", "data": {"host": "mini"}}), "mini offline")
        self.assertIsNone(fivelines.event_text({"kind": "usage.changed", "data": {}}), "routine moves are not announced")

    def test_changed_number_is_bold_briefly(self):
        os.environ["LL_COLOR"] = "1"
        fivelines.build(now=NOW)
        os.environ["LL_CLAUDE7"] = "75"
        self.assertIn("\x1b[1;33m███▊", fivelines.build(now=NOW + 5)[0], "a moved number is bold (and keeps its colour)")
        self.assertNotIn("\x1b[1;", fivelines.build(now=NOW + 30)[0], "then plain again")

    def test_old_pharos_reading_says_its_age(self):
        self.usage["generated_at"] = NOW - 600
        self.write_usage()
        self.assertTrue(plain(fivelines.build(now=NOW))[0].endswith(" · 10m old"))

    def test_hosts_use_nicknames_and_offline(self):
        hosts = plain(fivelines.build(now=NOW))[-1]
        self.assertEqual(hosts, "hosts studio 82% mem free · 22% cpu │ laptop 49% · 45% │ backup offline")

    def test_narrow_drops_resets_then_agy_3p(self):
        wide = plain(fivelines.build(now=NOW))[0]
        mid = plain(fivelines.build(now=NOW, columns=fivelines.width(wide) - 1))[0]
        self.assertNotIn("→", mid)
        self.assertIn("claude+gpt", mid)
        narrow = plain(fivelines.build(now=NOW, columns=fivelines.width(mid) - 1))[0]
        self.assertNotIn("claude+gpt", narrow)

    def test_never_fails(self):
        (self.pharos / "usage.json").write_text("{not json")
        (self.pharos / "summary.json").write_text("[]")
        lines = fivelines.build(now=NOW)
        self.assertTrue(lines[0])


if __name__ == "__main__":
    unittest.main()
