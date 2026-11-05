#!/usr/bin/env python3
"""limitline statusline: pick, order, and preview status-line items, like Codex /statusline.

    limitline statusline list                       every item, its Codex id, and the presets
    limitline statusline preview [KEY=VALUE ...]    the line as configured (or with changes, unsaved)
    limitline statusline set KEY=VALUE ...          write the changes to the config file
    limitline statusline --clear                    back to the default line (keeps `lines`)

KEY is line1 ... line9 (comma-separated item ids, in order), preset, or colors (on/off).
`lineN=none` drops that line of a preset; `lineN=` removes the key. Item ids are limitline's
or Codex's (current-dir, git-branch, ...). Every write keeps the other settings and comments
and saves the previous file as <file>.bak. No network.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import config  # noqa: E402

# (limitline id, Codex /statusline ids, what it shows, where the data comes from)
ITEMS = [
    ("dir", "current-dir", "the folder name (dir_style = \"home\": ~/path)", "workspace.current_dir"),
    ("project", "project, project-name", "the repository's name when it differs from the folder", "git rev-parse; else workspace.project_dir"),
    ("git", "git-branch", "branch, * when dirty, ↑ahead ↓behind", "git in workspace.current_dir"),
    ("model", "model-with-reasoning (with effort)", "model name", "model.display_name"),
    ("effort", "reasoning", "reasoning effort (effort high)", "effort.level"),
    ("style", "-", "output style when not default", "output_style.name"),
    ("ctx", "context-remaining, context-used, context-window-size", "context used, and tokens left", "context_window.*"),
    ("5h", "five-hour-limit", "5-hour limit used, refill time", "rate_limits.five_hour"),
    ("7d", "weekly-limit", "7-day limit used, refill time", "rate_limits.seven_day"),
    ("spend", "-", "spend limit used", "rate_limits.spend_limit"),
    ("tokens", "used-tokens, total-input-tokens, total-output-tokens", "tokens in the context: 322k in · 2.4k out", "context_window.total_input_tokens, total_output_tokens"),
    ("cost", "estimated-thread-cost", "session cost, duration, lines changed", "cost.*"),
    ("vitals", "-", "session age · lines · cost (takes the cost slot)", "cost.*, context_window.auto_compact_count"),
    ("session", "session-id", "first 6 characters of the session id", "session_id"),
    ("title", "thread-title", "the session's name or AI title", "session_name"),
    ("version", "codex-version", "Claude Code version", "version"),
    ("app", "app-name", "Claude Code", "constant: this status line only runs in Claude Code"),
    ("pr", "-", "open PR and review state", "pr.*"),
    ("cache", "-", "cache cold: <cause>", "prompt_cache"),
    ("vim", "-", "vim mode", "vim.mode"),
    ("burn", "-", "pace ~1h35m until the 5h limit", "local 5h history"),
    ("pace", "-", "ahead of / under pace", "rate_limits"),
    ("spark", "-", "5h and 7d sparklines", "local history"),
    ("codex", "-", "Codex 5h and 7d", "Pharos usage.json"),
    ("grok", "-", "Cursor + Grok plan", "limitline refresh"),
    ("jobs", "-", "Pharos jobs", "Pharos summary.json"),
    ("fleet", "-", "Pharos open work", "Pharos summary.json"),
    ("machines", "-", "hosts' free memory", "Pharos"),
    ("nudge", "-", "a hint when a limit or the context is high", "local"),
    ("value", "-", "estimated value this week", "local"),
    ("used", "-", "whole line: what each plan has used", "Pharos usage.json"),
    ("today", "-", "whole line: today's jobs", "Pharos summary.json"),
    ("older", "-", "whole line: open jobs from the last 7 days", "Pharos summary.json"),
    ("hosts", "-", "whole line: hosts", "Pharos usage.json"),
]

UNAVAILABLE = {
    "run-state": "Claude Code's status-line input has no running/idle state",
    "task-progress": "Claude Code's status-line input has no task list or progress",
    "thread-credits": "Claude Code has no credit balance; `spend` shows a spend limit when there is one",
    "total-tokens": "use `tokens`",
}

ALIASES = {
    "current-dir": "dir", "folder": "dir",
    "project-name": "project",
    "git-branch": "git",
    "reasoning": "effort",
    "context": "ctx", "context-remaining": "ctx", "context-used": "ctx", "context-window-size": "ctx",
    "five-hour-limit": "5h", "weekly-limit": "7d",
    "used-tokens": "tokens", "total-input-tokens": "tokens", "total-output-tokens": "tokens",
    "estimated-thread-cost": "cost",
    "session-id": "session",
    "thread-title": "title",
    "codex-version": "version",
    "app-name": "app",
    "sparklines": "spark", "nudges": "nudge", "others": "codex", "limits": "limits",
    "xai": "grok", "xai-plan": "grok", "cursor+grok": "grok", "plan": "grok",
}

PRESETS = [
    ("minimal", "line1: dir, git, model, ctx"),
    ("default", "line1: dir, project, git, model, ctx, style, 5h, 7d, spend, burn, cost, jobs, pr, cache, vim, codex"),
    ("full", "line1: dir, project, git, model, effort, style, ctx, tokens, cost / line2: 5h, 7d, spend, codex, grok, jobs, pr, cache, vim, title, version, session"),
    ("pharos", "line1: dir, project, git, model, ctx, style, cost, pr, cache, vim / line2-5: used, today, older, hosts"),
]

COLOR_KEYS = ("colors", "color", "colour", "colours")
LINE_KEYS = tuple("line%d" % n for n in range(1, 10))
# `lines` (how many lines, e.g. 5 for the Pharos view) is the user's, not an item choice.
CLEAR_KEYS = ("preset", "segments") + LINE_KEYS + COLOR_KEYS


class Usage(Exception):
    pass


def known_ids():
    return {item[0] for item in ITEMS} | {"limits"}


def resolve(item):
    """A limitline id for ITEM (Codex ids map to their limitline id), or raise Usage."""
    name = item.strip().strip("\"'").lower()
    if name in UNAVAILABLE:
        raise Usage("%s is not available in Claude Code: %s" % (name, UNAVAILABLE[name]))
    if name == "model-with-reasoning":
        return ["model", "effort"]
    name = ALIASES.get(name, name)
    if name not in known_ids():
        raise Usage("unknown item %r; `limitline statusline list` shows them all" % item)
    return [name]


def toml_list(items):
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def parse_changes(args):
    """KEY=VALUE arguments -> {key: rendered TOML value or None (remove)}."""
    changes = {}
    for arg in args:
        if "=" not in arg:
            raise Usage("expected KEY=VALUE, got %r" % arg)
        key, value = arg.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in LINE_KEYS:
            if value == "":
                changes[key] = None
            elif value.strip("[] ").lower() in ("", "none", "-"):
                changes[key] = "[]"
            else:
                ids = []
                for piece in config.parse_list(value):
                    for one in resolve(piece):
                        if one not in ids:
                            ids.append(one)
                changes[key] = toml_list(ids)
        elif key == "preset":
            if value == "":
                changes[key] = None
            elif value not in [p[0] for p in PRESETS]:
                raise Usage("unknown preset %r (minimal, default, full, pharos)" % value)
            else:
                changes[key] = json.dumps(value)
        elif key in COLOR_KEYS:
            flag = value.lower()
            if flag in ("on", "1", "true", "yes"):
                changes["colors"] = '"on"'
            elif flag in ("off", "0", "false", "no"):
                changes["colors"] = '"off"'
            else:
                raise Usage("colors is on or off")
        else:
            raise Usage("unknown key %r (line1 ... line9, preset, colors)" % key)
    return changes


def key_of(line):
    raw = line.split("#", 1)[0]
    if "=" not in raw:
        return None
    return "".join(raw.split("=", 1)[0].split()).lower() or None


def apply(lines, changes, remove=()):
    """Edit config lines in place: change or drop managed keys, keep everything else."""
    pending = dict(changes)
    out = []
    for line in lines:
        key = key_of(line)
        if key in COLOR_KEYS:
            key_name = "colors"
        else:
            key_name = key
        if key_name in remove or key in remove:
            continue
        if key_name in changes:
            if key_name in pending:
                value = pending.pop(key_name)
                if value is not None:
                    out.append("%s = %s\n" % (key_name, value))
            continue  # a later duplicate of a changed key is dropped
        out.append(line if line.endswith("\n") else line + "\n")
    for key in sorted(pending, key=lambda k: (k != "colors", k != "preset", k)):
        if pending[key] is not None:
            out.append("%s = %s\n" % (key, pending[key]))
    return out


def target_path():
    path = config.config_path()
    if not path or path == os.devnull:
        raise Usage("LIMITLINE_CONFIG points at %s; set it to a file to save changes" % (path or "nothing"))
    if os.environ.get("LIMITLINE_CONFIG") is None and not os.path.exists(path):
        # No config yet: start config.toml, not the older key=value `config`.
        path = os.path.join(os.path.dirname(path), "config.toml")
    # A symlinked config (dotfiles) is edited where it lives; the link stays.
    return os.path.realpath(path)


def write_config(changes, remove=()):
    path = target_path()
    old = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            old = handle.read()
    new = "".join(apply(old.splitlines(True), changes, remove))
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    if os.path.isfile(path):
        with open(path + ".bak", "w", encoding="utf-8") as handle:
            handle.write(old)
    fd, tmp = tempfile.mkstemp(prefix=".limitline-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(new)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def sample_payload(now):
    return {
        "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
        "effort": {"level": "high"},
        "version": "2.1.317",
        "session_id": "abcdef12-preview",
        "session_name": "statusline preview",
        "workspace": {"current_dir": os.getcwd()},
        "context_window": {"used_percentage": 32, "context_window_size": 1000000,
                           "total_input_tokens": 322000, "total_output_tokens": 2400},
        "cost": {"total_cost_usd": 4.2, "total_duration_ms": 7800000,
                 "total_lines_added": 1312, "total_lines_removed": 40},
        "rate_limits": {"five_hour": {"used_percentage": 62, "resets_at": now + 6120},
                        "seven_day": {"used_percentage": 38, "resets_at": now + 363600}},
    }


def preview(changes):
    """Render the status line with a sample session in this folder. Writes no file."""
    path = config.config_path()
    current = ""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    text = "".join(apply(current.splitlines(True), changes))
    now = int(os.environ.get("LIMITLINE_NOW") or time.time())
    with tempfile.TemporaryDirectory(prefix="limitline-preview-") as tmp:
        cfg = os.path.join(tmp, "config.toml")
        with open(cfg, "w", encoding="utf-8") as handle:
            handle.write(text)
        env = os.environ.copy()
        env.update({"LIMITLINE_CONFIG": cfg, "LIMITLINE_PREVIEW": "1", "LIMITLINE_REFRESH": "0",
                    "LIMITLINE_ALERTS": "off", "LIMITLINE_NOW": str(now), "TMPDIR": tmp})
        proc = subprocess.run([os.path.join(ROOT, "bin", "limitline")],
                              input=json.dumps(sample_payload(now)).encode(),
                              capture_output=True, env=env)
    sys.stdout.write(proc.stdout.decode("utf-8", "replace"))


def cmd_list():
    width = max(len(item[0]) for item in ITEMS)
    print("%-*s  %-40s  %s" % (width, "item", "codex", "shows (source)"))
    for ident, codex, shows, source in ITEMS:
        print("%-*s  %-40s  %s (%s)" % (width, ident, codex, shows, source))
    print()
    print("not available in Claude Code:")
    for ident, why in UNAVAILABLE.items():
        if ident != "total-tokens":
            print("  %-15s not available: %s" % (ident, why))
    print()
    print("presets:")
    for name, lines in PRESETS:
        print("  %-8s %s" % (name, lines))
    values = config.values()
    current = ["%s = %s" % (k, values[k]) for k in ("preset",) + LINE_KEYS + COLOR_KEYS + ("segments", "lines") if k in values]
    print()
    print("current (%s):" % config.config_path())
    for line in current or ["  default line"]:
        print("  " + line.strip())


USAGE = """usage: limitline statusline list
       limitline statusline preview [line1=dir,git,model,ctx] [preset=full] [colors=off]
       limitline statusline set line1=dir,git,model,ctx [line2=...] [preset=NAME] [colors=on|off]
       limitline statusline --clear"""


def main(argv):
    try:
        if not argv or argv[0] in ("-h", "--help", "help"):
            print(USAGE)
            return 0 if argv else 2
        cmd, rest = argv[0], argv[1:]
        if cmd == "list":
            cmd_list()
            return 0
        if cmd == "preview":
            preview(parse_changes(rest))
            return 0
        if cmd == "set":
            if not rest:
                raise Usage("set needs KEY=VALUE")
            changes = parse_changes(rest)
            path = write_config(changes)
            print("saved %s (previous file: %s.bak)" % (path, path))
            preview({})
            return 0
        if cmd in ("--clear", "clear"):
            path = write_config({}, remove=CLEAR_KEYS)
            print("cleared preset, line1-9, segments and colors in %s (previous file: %s.bak)" % (path, path))
            preview({})
            return 0
        raise Usage("unknown command %r" % cmd)
    except Usage as exc:
        print("limitline statusline: %s" % exc, file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
