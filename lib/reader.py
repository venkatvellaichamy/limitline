"""Select the usage reader without running a provider or writing Pharos files."""
import math
import os
import stat
import config
import pharos_view

LABELS = ('dev.limitline.refresh', 'com.limitline.refresh')
NOTE = 'Pharos is the usage reader; limitline refresh skipped.'


def is_pharos():
    settings = config.values()
    mode = settings.get('reader', 'auto').lower()
    if mode in ('pharos', 'limitline'):
        return mode == 'pharos'
    try:
        freshness = float(settings.get('reader_freshness', 900))
        if not math.isfinite(freshness) or freshness < 0:
            freshness = 900
        info = os.stat(pharos_view.usage_path())
        age = pharos_view.now_epoch() - info.st_mtime
        return stat.S_ISREG(info.st_mode) and -pharos_view.SKEW_S <= age <= freshness
    except (OSError, ValueError):
        return False


def redundant_jobs():
    import refresher
    return [os.path.join(refresher.agents_dir(), label + '.plist') for label in LABELS
            if os.path.isfile(os.path.join(refresher.agents_dir(), label + '.plist'))]


def remove_jobs(dry_run=False):
    import refresher
    for path in redundant_jobs():
        backup = path + '.bak'
        number = 1
        while os.path.lexists(backup):
            backup = path + '.%d.bak' % number
            number += 1
        print('launchctl bootout %s %s' % (refresher.domain(), path))
        print('rename %s -> %s' % (path, backup))
        if not dry_run:
            refresher.run(['bootout', refresher.domain(), path])
            os.rename(path, backup)
    return 0


def display_fields():
    """Read Pharos directly so a no-op refresh cannot leave legacy layouts empty."""
    import fleet
    import jobs
    import machines
    import xaiplan
    import grokline
    usage = pharos_view.read_usage()
    rows = pharos_view.plan_rows(usage) if usage else []
    text, flags = '', ''
    for row in rows:
        if row.get('provider') == xaiplan.PROVIDER:
            text, flags = xaiplan.line_fields(row)
    if not text:
        row = next((r for r in rows if r.get('provider') == 'grok'), None)
        text = grokline.segment(row) if row else ''
    return {'fleet': fleet.segment_text(), 'machines': machines.format_hosts(pharos_view.hosts(usage), long=False),
            'grok': text, 'flags': flags, 'jobs': jobs.segment()}


if __name__ == '__main__':
    for key, value in display_fields().items():
        print(key + ' ' + str(value or '').replace('\n', ' '))
