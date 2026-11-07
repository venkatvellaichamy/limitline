"""The Cursor plan row and the Grok-labelled xAI plan row, from fixture Pharos usage files.
Synthetic homes only; no network."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "pharos"
sys.path.insert(0, str(ROOT / "lib"))
import xaiplan

NOW = "1762056000"  # 60 s after the fixtures' generated_at


class CursorAndGrokRows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(home),
            "TZ": "UTC",
            "NO_COLOR": "1",
            "LIMITLINE_NOW": NOW,
            "XDG_CACHE_HOME": str(home / "cache"),
            "LIMITLINE_PHAROS_HOME": str(home / "pharos"),
            "LIMITLINE_CONFIG": str(home / "config"),
            "LIMITLINE_CLAUDE_SNAPSHOT": str(home / "no-claude.json"),
            "LIMITLINE_XAI_PLAN": str(home / "no-xai-plan.json"),
            "LIMITLINE_GROK_LOG": str(home / "no-unified.jsonl"),
        }

    def run_bin(self, usage, *args):
        env = dict(self.env, LIMITLINE_PHAROS_USAGE=str(FIX / usage))
        proc = subprocess.run([str(ROOT / "bin" / "limitline"), *args], env=env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def status_rows(self, usage):
        text = self.run_bin(usage, "status")
        table = text.split("\n\n")[0].splitlines()[1:]
        return {re.split(r"\s+", line, 1)[0]: re.split(r"\s+", line, 1)[1] for line in table if line.strip()}

    def test_both_entries_show_cursor_and_grok_rows(self):
        rows = self.status_rows("usage-cursor-and-grok.json")
        self.assertEqual(rows.get("cursor"), "month 42%")
        self.assertTrue(rows.get("Grok", "").startswith("74% · resets Fri 05:22 · SuperGrok Plus · live"), rows)
        self.assertNotIn("cursor+grok", rows)
        host = self.run_bin("usage-cursor-and-grok.json", "--host", "prompt")
        self.assertIn("cursor month 42%", host)
        self.assertIn("Grok 74% · Fri 05:22", host)
        self.assertNotIn("cursor+grok", host)

    def test_older_pharos_grok_only(self):
        rows = self.status_rows("usage-grok-only.json")
        self.assertNotIn("cursor", rows)
        self.assertTrue(rows.get("Grok", "").startswith("74% · resets Fri 05:22"), rows)
        host = self.run_bin("usage-grok-only.json", "--host", "prompt")
        self.assertIn("Grok 74% · Fri 05:22", host)
        self.assertNotIn("cursor", host)


class Merge(unittest.TestCase):
    PLAN = {"key": "cursor+grok", "provider": "xai-plan", "label": "cursor+grok", "source": "live",
            "windows": [{"name": "week", "used_pct": 74}]}

    def test_measured_cursor_row_stays(self):
        cursor = {"provider": "cursor", "source": "live", "windows": [{"name": "month", "used_pct": 42}]}
        grok = {"provider": "grok", "source": "usage.json", "week": {"tokens": 1200}, "windows": []}
        out = xaiplan.merge([cursor, grok, dict(self.PLAN)])
        self.assertEqual([r["provider"] for r in out], ["cursor", "xai-plan"])
        self.assertEqual(out[1]["grok_week"], {"tokens": 1200})
        self.assertEqual(xaiplan.label(out[1]), "Grok")
        self.assertEqual(xaiplan.label(out[0]), "cursor")

    def test_cursor_estimate_folds_into_plan(self):
        estimate = {"provider": "cursor", "source": "estimate", "windows": [{"name": "7d", "used_pct": 11, "estimate": True}]}
        out = xaiplan.merge([estimate, dict(self.PLAN)])
        self.assertEqual([r["provider"] for r in out], ["xai-plan"])

    def test_grok_line_keeps_its_parse_prefix(self):
        text, flags = xaiplan.line_fields(dict(self.PLAN, observed_at=0, age=0))
        self.assertTrue(text.startswith("cursor+grok 74%"), text)
        self.assertEqual(flags, "74 0 live")


if __name__ == "__main__":
    unittest.main()
