"""Reader ownership uses synthetic homes only."""
import os
import json
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


    def test_refresh_rebuilds_pharos_lines_without_provider_reads(self):
        now = int(time.time())
        (self.path / 'config').write_text('reader = "pharos"\n')
        usage = {'version': 1, 'generated_at': now - 120, 'plans': [
            {'provider': 'xai-plan', 'source': 'live', 'windows': [{'used_pct': 42}]}],
            'hosts': {'hosts': [{'name': 'studio', 'free_pct': 82, 'reachable': True}]}}
        (self.path / 'usage.json').write_text(json.dumps(usage))
        summary = self.path / 'summary.json'
        summary.write_text(json.dumps({'today': {'running': 2}, 'jobs': [{'name': 'build'}]}))
        cache = self.path / 'cache/limitline'
        cache.mkdir(parents=True)
        names = ('grok.line', 'jobs.line', 'fleet.line', 'machines.line', 'machines.json')
        for name in names:
            (cache / name).write_text('stale')
        cli = refresh._cli()
        with patch.dict(os.environ, {'LIMITLINE_PHAROS_SUMMARY': str(summary)}), patch.object(refresh, '_cli', return_value=cli), patch.object(cli, 'run_provider', side_effect=AssertionError('provider read')):
            refresh.main([])
        assert all((cache / name).read_text() != 'stale' for name in names)
        assert '42%' in (cache / 'grok.line').read_text()
        assert 'build' in (cache / 'jobs.line').read_text()
        assert '2 run' in (cache / 'fleet.line').read_text()
        assert json.loads((cache / 'machines.json').read_text())['observed_at'] == now - 120
        assert 'studio' in (cache / 'machines.line').read_text()
        # Forced Pharos mode with missing files must not fall back to provider reads.
        (self.path / 'usage.json').unlink()
        with patch.object(refresh, '_cli', return_value=cli), patch.object(cli, 'run_provider', side_effect=AssertionError('provider read')) as provider:
            refresh.main([])
            provider.assert_not_called()

    def test_plan_age_comes_from_pharos(self):
        import fivelines
        now = int(time.time())
        cache = self.path / 'cache/limitline'
        cache.mkdir(parents=True)
        line = cache / 'grok.line'
        line.write_text('cursor+grok 42%\n42 0 live\n')
        os.utime(line, (now - 3600,) * 2)
        usage = {'generated_at': now - 120, 'age': 120, 'plans': [
            {'provider': 'xai-plan', 'source': 'live', 'windows': [{'used_pct': 42}]}]}
        cell = fivelines.cursor_cell(now, usage)
        assert cell.used == 42
        usage['plans'][0].update(stale=True, observed_at=now - 600)
        cell = fivelines.cursor_cell(now, usage)
        assert cell.age == 600
        del usage['plans'][0]['observed_at']
        assert fivelines.cursor_cell(now, usage).age == 120
        # usage.json itself is old: the plan is unknown even though grok.line was just written;
        # the used line's note carries usage.json's age (`Pharos usage unavailable · 1h old`).
        usage.update(stale=True, age=3600, generated_at=now - 3600)
        os.utime(line, (now, now))
        cell = fivelines.cursor_cell(now, usage)
        assert cell.used is None and cell.held

    def test_pharos_refresh_never_runs_a_reader(self):
        """Pharos mode: refresh rebuilds every derived line from usage.json and never loads
        limitline's own readers (cli.load_all runs the provider commands)."""
        now = int(time.time())
        (self.path / 'config').write_text('reader = "pharos"\n')
        (self.path / 'usage.json').write_text(json.dumps({'version': 1, 'generated_at': now - 30, 'plans': [
            {'provider': 'xai-plan', 'source': 'live', 'observed_at': now - 300, 'windows': [{'used_pct': 37}]}]}))
        with patch.object(refresh, '_cli', side_effect=AssertionError('limitline reader loaded')):
            refresh.main([])
        assert 'cursor+grok 37%' in (self.path / 'cache/limitline/grok.line').read_text()

    def run_line(self, usage=None, config='reader = "pharos"\n'):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        home = self.path / '.pharos'
        home.mkdir(exist_ok=True)
        path = home / 'usage.json'
        if usage is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps(usage))
        (self.path / 'config').write_text(config)
        env = dict(os.environ, LIMITLINE_PHAROS_HOME=str(home), LIMITLINE_PHAROS_USAGE=str(path),
                   LIMITLINE_REFRESH='0', LIMITLINE_CODEX='1', NO_COLOR='1', LIMITLINE_NOW=str(self.now))
        return subprocess.run([str(root / 'bin/limitline')], input='{"model":{"display_name":"Opus"}}',
                              text=True, env=env, check=True, capture_output=True).stdout

    now = 1762056000

    def test_stale_codex_plan_is_unknown_with_its_age_on_line_one(self):
        fresh = {'version': 1, 'generated_at': self.now - 60, 'plans': [
            {'provider': 'codex', 'source': 'live', 'observed_at': self.now - 120, 'stale': False,
             'windows': [{'name': '5h', 'used_pct': 100, 'resets_at': self.now + 3600},
                         {'name': '7d', 'used_pct': 18, 'resets_at': self.now + 86400}]}]}
        line = self.run_line(fresh)
        assert 'codex 5h' in line and '18%' in line and 'codex ?' not in line, line
        # Tonight: a 94-minute-old reading, not marked stale, said 17% / 5%.
        old = json.loads(json.dumps(fresh))
        old['plans'][0].update(observed_at=self.now - 94 * 60, windows=[
            {'name': '5h', 'used_pct': 17, 'resets_at': self.now + 3600}, {'name': '7d', 'used_pct': 5, 'resets_at': self.now + 86400}])
        line = self.run_line(old)
        assert 'codex ? · 1h old' in line, line
        assert '17' not in line and '5%' not in line, line
        old['plans'][0].update(observed_at=self.now - 600, stale=True)
        assert 'codex ? · 10m old' in self.run_line(old)

    def test_missing_usage_says_pharos_unavailable(self):
        line = self.run_line(None)
        assert 'Pharos usage unavailable' in line, line

    def test_install_keeps_display_job(self):
        with patch.object(reader, 'is_pharos', return_value=True), patch.object(refresher, 'supported', return_value=True), patch.object(refresher, 'data_dir', return_value=str(self.path / 'data')), patch.object(refresher, 'run') as run:
            run.return_value.returncode = 0
            assert refresher.install() == 0
            assert schedule.install() == 0
            assert run.call_count == 2
            assert (self.path / (refresher.LABEL + '.plist')).exists()


    def test_remove_jobs(self):
        tmp_path = self.path
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.dict(os.environ, {'LIMITLINE_LAUNCH_AGENTS': str(tmp_path)}), patch.object(refresher, 'run') as run:
            for label in ('dev.limitline.refresh', 'com.limitline.refresh'):
                (tmp_path / (label + '.plist')).write_text('original')
            reader.remove_jobs(dry_run=True)
            assert 'bootout' in output.getvalue()
            assert len(list(tmp_path.glob('*.plist'))) == 2
            reader.remove_jobs()
            assert len(list(tmp_path.glob('*.bak'))) == 1
            assert (tmp_path / 'dev.limitline.refresh.plist').exists()
            assert all(p.read_text() == 'original' for p in tmp_path.glob('*.bak'))
            assert run.call_count == 1
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
        for label in ('dev.limitline.refresh', 'com.limitline.refresh'):
            (self.path / (label + '.plist')).write_text('original')
        out = subprocess.run([str(root / 'bin/limitline'), 'doctor'], input='', text=True, env=env, check=True, capture_output=True).stdout
        assert 'redundant refresh job: ' + str(self.path / 'com.limitline.refresh.plist') in out
        assert 'redundant refresh job: ' + str(self.path / 'dev.limitline.refresh.plist') not in out
        out = subprocess.run([str(root / 'bin/limitline'), 'uninstall', '--refresh-jobs', '--dry-run'], text=True, env=env, check=True, capture_output=True).stdout
        assert 'bootout' in out and '.bak' in out
        assert len(list(self.path.glob('*.plist'))) == 2
