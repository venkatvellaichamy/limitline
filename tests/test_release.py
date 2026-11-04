"""Release tooling: scripts/version.py and lib/release.py (version, update, channel)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))
import release  # noqa: E402
import version as ver  # noqa: E402


class VersionScript(unittest.TestCase):
    def test_files_agree_and_have_notes(self):
        self.assertEqual(ver.check(), 0)
        self.assertEqual(len(set(ver.found().values())), 1)

    def test_a_tag_must_match(self):
        self.assertEqual(ver.check("9.9.9"), 1)

    def test_channels_and_order(self):
        self.assertEqual(ver.channel("0.13.0"), "stable")
        self.assertEqual(ver.channel("0.13.0-beta.2"), "beta")
        order = ["0.12.1", "0.13.0-alpha.1", "0.13.0-beta.1", "0.13.0-beta.2", "0.13.0-rc.1", "0.13.0", "0.13.1"]
        self.assertEqual(sorted(order, key=ver.key), order)
        self.assertIsNone(ver.key("0.13"))

    def test_beta_never_moves_back(self):
        newer = lambda a, b: ver.main(["newer", a, b])
        self.assertEqual(newer("0.13.0-beta.1", "0.12.1"), 0)
        self.assertEqual(newer("0.12.2", "0.13.0-beta.1"), 1, "a stable hotfix leaves beta ahead")
        self.assertEqual(newer("0.13.0", ""), 0, "no beta branch yet")

    def test_notes(self):
        self.assertTrue(ver.notes(ver.found()["bin/limitline"]), "the current version has release notes")


class ReleaseCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def known(self, location, ref=None):
        source = {"source": "github", "repo": release.REPO}
        if ref is not None:
            source["ref"] = ref
        path = Path(self.tmp.name) / "known.json"
        path.write_text(json.dumps({"limitline": {"source": source, "installLocation": str(location)}}))
        os.environ["LIMITLINE_KNOWN_MARKETPLACES"] = str(path)

    def test_channel_names(self):
        self.assertEqual(release.channel_of("stable"), "stable")
        self.assertEqual(release.channel_of("beta"), "beta")
        self.assertEqual(release.channel_of("main"), "dev")
        self.assertEqual(release.channel_of(""), "dev")

    def test_install_ref_only_counts_for_the_install_itself(self):
        os.environ["LIMITLINE_ROOT"] = str(ROOT)
        self.known(ROOT, "stable")
        self.assertEqual(release.marketplace_ref(), "stable")
        self.known(Path(self.tmp.name), "stable")
        self.assertIsNone(release.marketplace_ref(), "a development checkout is not the install")

    def test_unknown_channel_is_refused(self):
        self.assertEqual(release.main(["channel", "nightly"]), 2)

    def test_cli_version_runs(self):
        out = subprocess.run([str(ROOT / "bin" / "limitline"), "version"], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=20)
        self.assertEqual(out.returncode, 0)
        self.assertIn("limitline " + ver.found()["bin/limitline"], out.stdout)


if __name__ == "__main__":
    unittest.main()
