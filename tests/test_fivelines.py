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
        (self.cache / "antigravity.json").write_text(json.dumps({"observed_at": NOW - 60, "buckets": [
            {"group": "Gemini Models", "resets_at": NOW + 3 * 86400, "used_pct": 0, "window": "weekly"},
            {"group": "Gemini Models", "resets_at": NOW + 3600, "used_pct": 0, "window": "5h"},
            {"group": "Claude and GPT models", "resets_at": NOW + 3 * 86400, "used_pct": 7, "window": "weekly"},
            {"group": "Gemini 4 Argon", "resets_at": NOW + 3 * 86400, "used_pct": 100, "window": "weekly"},
        ]}))
        (self.cache / "machines.json").write_text(json.dumps({"hosts": [
            {"name": "studio", "free_pct": 82, "load_pct": 22, "reachable": True},
            {"name": "laptop", "free_pct": 49, "load_pct": 45, "reachable": True},
            {"name": "backup", "reachable": False},
        ]}))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def state(self, id_, status, started, **extra):
        folder = self.pharos / "runs" / id_
        folder.mkdir()
        (folder / "state.json").write_text(json.dumps({"id": id_, "status": status, "started_at": started, "repo": "/r/pharos", **extra}))

    def test_left_is_remaining_in_fixed_order_with_marks(self):
        left = plain(fivelines.build(now=NOW))[0]
        self.assertTrue(left.startswith("left  ✻ claude 7d 30%"), left)
        order = [left.index(word) for word in ("claude", "◎ codex", "⬡ cursor+grok", "✦ agy")]
        self.assertEqual(order, sorted(order))
        self.assertIn("codex 5h 1% →18:00 · 7d 31%", left)
        self.assertIn("cursor+grok 19% →Thu 23:22", left)
        self.assertIn("agy gemini 100% · claude+gpt 93% · argon 0% →", left)
        self.assertNotIn("gemini app", left.lower())

    def test_reset_only_shown_at_25_or_less(self):
        left = plain(fivelines.build(now=NOW))[0]
        self.assertNotIn("claude 7d 30% →", left)
        self.assertNotIn("7d 31% →", left)

    def test_colours_at_10_and_25(self):
        self.assertEqual(fivelines.left_code(10), "31")
        self.assertEqual(fivelines.left_code(11), "33")
        self.assertEqual(fivelines.left_code(25), "33")
        self.assertEqual(fivelines.left_code(26), "")
        os.environ["LL_COLOR"] = "1"
        left = fivelines.build(now=NOW)[0]
        self.assertIn("\x1b[31m1%\x1b[0m", left)
        self.assertIn("\x1b[33m19%\x1b[0m", left)

    def test_missing_reading_is_a_dash_not_a_number(self):
        for key in ("LL_CODEX5", "LL_CODEX5_RESET", "LL_CODEX7", "LL_CODEX7_RESET"):
            del os.environ[key]
        os.environ["LL_CODEX_CACHE"] = str(Path(self.tmp.name) / "none")
        (self.cache / "antigravity.json").unlink()
        left = plain(fivelines.build(now=NOW))[0]
        self.assertIn("◎ codex 7d —", left)
        self.assertIn("✦ agy gemini —", left)

    def test_expired_window_is_not_shown_as_left(self):
        os.environ["LL_CODEX5_RESET"] = str(NOW - 10)
        left = plain(fivelines.build(now=NOW))[0]
        self.assertNotIn("5h 1%", left)

    def test_marks_none(self):
        os.environ["LL_MARKS"] = "none"
        left = plain(fivelines.build(now=NOW))[0]
        self.assertNotIn("✻", left)
        self.assertTrue(left.startswith("left  claude 7d 30%"))

    def test_today_and_older_from_states(self):
        self.state("a", "running", TODAY)
        self.state("b", "merged", TODAY)
        self.state("c", "awaiting-verify", TODAY, commits=["x"])
        self.state("d", "awaiting-verify", TODAY, commits=[])
        self.state("e", "failed", TODAY, retried_by="f")
        self.state("f", "running", TODAY, retry_of="e")
        self.state("g", "paused-quota", TODAY)
        self.state("h", "verify-failed", YESTERDAY, commits=["x"])
        self.state("i", "done", YESTERDAY)
        lines = plain(fivelines.build(now=NOW))
        self.assertEqual(lines[1], "today ▶ 2 running │ ✓ 2 done │ ✋ 1 need you │ ✗ 0 failed · ↻ 1 retried │ ⏸ 1 waiting on limit")
        self.assertEqual(lines[2], "older ✋ 1 need you │ oldest 1d (pharos)")

    def test_older_hidden_when_empty(self):
        self.state("a", "done", YESTERDAY)
        self.state("b", "running", TODAY)
        lines = plain(fivelines.build(now=NOW))
        self.assertTrue(lines[1].startswith("today"))
        self.assertTrue(lines[2].startswith("hosts"))

    def test_summary_json_preferred_when_fresh(self):
        self.state("a", "running", TODAY)
        summary = {"generated_at": NOW, "today": dict.fromkeys(fivelines.KEYS, 0), "older": dict.fromkeys(fivelines.KEYS, 0), "oldest_open": None}
        summary["today"]["done"] = 9
        path = self.pharos / "summary.json"
        path.write_text(json.dumps(summary))
        os.utime(path, (NOW, NOW))
        self.assertIn("✓ 9 done", plain(fivelines.build(now=NOW))[1])
        os.utime(path, (NOW - 3600, NOW - 3600))
        self.assertIn("▶ 1 running", plain(fivelines.build(now=NOW))[1])

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
        (self.cache / "machines.json").write_text("{not json")
        (self.cache / "antigravity.json").write_text("[]")
        (self.pharos / "runs" / "bad").mkdir()
        (self.pharos / "runs" / "bad" / "state.json").write_text("{")
        lines = fivelines.build(now=NOW)
        self.assertTrue(lines[0])


if __name__ == "__main__":
    unittest.main()
