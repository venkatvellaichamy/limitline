"""Reader ownership uses synthetic homes only."""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
import unittest
import tempfile
import contextlib
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import reader
import pharos_view
import refresh
import refresher
import schedule


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'HOME': self.tmp.name, 'LIMITLINE_PHAROS_USAGE': str(self.path / 'usage.json'), 'LIMITLINE_CONFIG': str(self.path / 'config'), 'LIMITLINE_LAUNCH_AGENTS': self.tmp.name, 'XDG_CACHE_HOME': str(self.path / 'cache')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_detection(self):
        tmp_path = self.path
        usage = tmp_path / 'usage.json'
        cfg = tmp_path / 'config'
        with patch.dict(os.environ, {'LIMITLINE_PHAROS_USAGE': str(usage), 'LIMITLINE_CONFIG': str(cfg)}, clear=False):
            assert not reader.is_pharos()
            usage.write_text('{}')
            assert reader.is_pharos()
            os.utime(usage, (time.time() - 1000,) * 2)
            assert not reader.is_pharos()
            cfg.write_text('reader = "pharos"\n')
            assert reader.is_pharos()
            cfg.write_text('reader = "limitline"\n')
            assert not reader.is_pharos()
            cfg.write_text('reader_freshness = 2000\n')
            assert reader.is_pharos()


    def test_refresh_noop(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(reader, 'is_pharos', return_value=True), patch.object(refresh, 'write_grok') as write:
            refresh.main(['--force', '--verbose'])
            write.assert_not_called()
            assert 'Pharos' in output.getvalue()


    def test_install_skips_jobs(self):
        with patch.object(reader, 'is_pharos', return_value=True), patch.object(refresher, 'run') as run:
            assert refresher.install() == 0
            assert schedule.install() == 0
            run.assert_not_called()


    def test_remove_jobs(self):
        tmp_path = self.path
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.dict(os.environ, {'LIMITLINE_LAUNCH_AGENTS': str(tmp_path)}), patch.object(refresher, 'run') as run:
            for label in reader.LABELS:
                (tmp_path / (label + '.plist')).write_text('original')
            reader.remove_jobs(dry_run=True)
            assert 'bootout' in output.getvalue()
            assert len(list(tmp_path.glob('*.plist'))) == 2
            reader.remove_jobs()
            assert len(list(tmp_path.glob('*.bak'))) == 2
            assert all(p.read_text() == 'original' for p in tmp_path.glob('*.bak'))
            assert run.call_count == 2
    def test_stale_refresh_preserves_fallback(self):
        with patch.object(reader, 'is_pharos', return_value=False), patch.object(refresh, 'write_grok') as write:
            refresh.main([])
            write.assert_called_once()

    def test_statusline_never_writes_pharos_and_doctor_names_jobs(self):
        import json
        import subprocess
        root = Path(__file__).resolve().parents[1]
        home = self.path / '.pharos'
        home.mkdir()
        usage = home / 'usage.json'
        usage.write_text(json.dumps({'version': 1, 'generated_at': int(time.time()), 'plans': []}))
        os.environ['LIMITLINE_PHAROS_USAGE'] = str(usage)
        os.environ['LIMITLINE_PHAROS_HOME'] = str(home)
        before = {p.name: p.read_bytes() for p in home.iterdir()}
        env = dict(os.environ, LIMITLINE_REFRESH='1')
        subprocess.run([str(root / 'bin/limitline')], input='{"rate_limits":{"five_hour":{"used_percentage":44}}}', text=True, env=env, check=True, capture_output=True)
        assert {p.name: p.read_bytes() for p in home.iterdir()} == before
        assert not (self.path / 'cache/limitline/refresh.lock').exists()
        assert not pharos_view.relay(str(usage))
        for label in reader.LABELS:
            (self.path / (label + '.plist')).write_text('original')
        out = subprocess.run([str(root / 'bin/limitline'), 'doctor'], input='', text=True, env=env, check=True, capture_output=True).stdout
        for label in reader.LABELS:
            assert label in out
        out = subprocess.run([str(root / 'bin/limitline'), 'uninstall', '--refresh-jobs', '--dry-run'], text=True, env=env, check=True, capture_output=True).stdout
        assert 'bootout' in out and '.bak' in out
        assert len(list(self.path.glob('*.plist'))) == 2
