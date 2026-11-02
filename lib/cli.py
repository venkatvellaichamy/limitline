#!/usr/bin/env python3
"""limitline status, host lines, preview, doctor, and config."""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDERS = ("claude", "codex", "cursor", "grok", "gemini")


def run_provider(name):
    path = os.path.join(ROOT, "providers", name)
    try:
        proc = subprocess.run([path], capture_output=True, timeout=2, env=os.environ.copy())
        data = json.loads(proc.stdout.decode() or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("provider", name)
    data.setdefault("windows", [])
    data.setdefault("source", "none")
    data.setdefault("stale", False)
    return data


def window_text(window):
    name = window.get("name") or "limit"
    used = window.get("used_pct")
    text = name
    if isinstance(used, (int, float)) and not isinstance(used, bool):
        text += " %d%%" % int(used + 0.5)
    machines = window.get("machines")
    if isinstance(machines, int) and machines > 1:
        text += " ×%d" % machines
    return text


def load_lib(name):
    import importlib.util
    path = os.path.join(ROOT, "lib", name + ".py")
    spec = importlib.util.spec_from_file_location("limitline_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def prepare(rows):
    sync_dir = os.environ.get("LIMITLINE_SYNC_DIR")
    if not sync_dir:
        return rows
    try:
        sync = load_lib("sync")
        for row in rows:
            sync.publish(sync_dir, row.get("provider") or "tool", row)
        return sync.merge_rows(rows, sync_dir)
    except Exception:
        return rows


def provider_brief(data):
    windows = data.get("windows") or []
    if not windows:
        if data.get("provider") == "grok" and data.get("source") == "usage.json":
            return "session tokens only"
        if data.get("source") == "none":
            return "no local quota"
        return "no window"
    parts = [window_text(item) for item in windows if isinstance(item, dict)]
    text = " · ".join(parts)
    if data.get("stale"):
        text += " stale"
    return text


def load_all():
    return [run_provider(name) for name in PROVIDERS]


def cmd_status():
    rows = prepare(load_all())
    print("%-8s %s" % ("tool", "limits"))
    for row in rows:
        print("%-8s %s" % (row.get("provider"), provider_brief(row)))


def cmd_host(kind):
    rows = prepare(load_all())
    if kind == "json":
        json.dump(rows, sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
        return
    if kind == "swiftbar":
        title = "limits"
        for row in rows:
            if row.get("provider") == "claude" and row.get("windows"):
                title = window_text(row["windows"][0])
                break
        print(title)
        print("---")
        for row in rows:
            print("%s  %s" % (row.get("provider"), provider_brief(row)))
        return
    parts = []
    for row in rows:
        if not row.get("windows"):
            continue
        parts.append("%s %s" % (row.get("provider"), provider_brief(row)))
    print(" | ".join(parts))


def cmd_preview():
    sample = (
        '{"model":{"display_name":"Opus 5.5"},'
        '"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120},'
        '"seven_day":{"used_percentage":38,"resets_at":1762419600}},'
        '"context_window":{"used_percentage":41}}'
    )
    binary = os.path.join(ROOT, "bin", "limitline")
    for theme in ("minimal", "ascii", "powerline", "pill", "emoji", "mono"):
        env = os.environ.copy()
        env.update({
            "LIMITLINE_THEME": theme,
            "LIMITLINE_NOW": "1762056000",
            "LIMITLINE_CONFIG": "/dev/null",
            "LIMITLINE_CODEX": "0",
            "LIMITLINE_GIT": "0",
            "LIMITLINE_PACE": "0",
            "LIMITLINE_SPARK": "0",
            "LIMITLINE_NUDGES": "0",
            "LIMITLINE_FRESH": "0",
            "LIMITLINE_VALUE": "0",
            "LIMITLINE_VITALS": "0",
            "LIMITLINE_ALERTS": "off",
            "NO_COLOR": "1",
            "TZ": "UTC",
        })
        env.pop("LIMITLINE_SYNC_DIR", None)
        proc = subprocess.run([binary], input=sample.encode(), capture_output=True, env=env)
        print("## %s" % theme)
        sys.stdout.write(proc.stdout.decode())


def cmd_doctor():
    for tool in ("jq", "python3", "awk", "git"):
        found = shutil.which(tool)
        print("%s: %s" % (tool, "yes" if found else "no"))
    raw = ""
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
    if not raw.strip():
        print("stdin: no status payload")
        return
    try:
        data = json.loads(raw)
    except Exception:
        print("stdin: not json")
        return
    paths = [
        "model.display_name",
        "context_window.used_percentage",
        "rate_limits.five_hour.used_percentage",
        "rate_limits.seven_day.used_percentage",
        "rate_limits.spend_limit.used_percentage",
        "cost.total_cost_usd",
        "workspace.current_dir",
        "workspace.repo",
        "pr.number",
        "output_style.name",
        "prompt_cache.warm",
        "vim.mode",
        "session_id",
    ]
    print("fields:")
    for path in paths:
        cur = data
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        print("  %s %s" % (path, "present" if ok and cur is not None else "absent"))


def cmd_config():
    print("# ~/.config/limitline/config.toml")
    print('theme = "minimal"')
    print("bar_width = 5")
    print("lines = 1")
    print("auto_compact = 95")
    print("auto_compact_warn = 80")
    print('segments = ["model", "style", "context", "limits", "burn", "cost", "git", "pr", "cache", "vim"]')
    print("# session and other-tool segments stay off on the Claude Code line")
    print("# pace, spark, nudges, fresh, value, and vitals are off until set")
    print('# pace = "on"')
    print('# spark = "on"')
    print('# nudges = "on"')
    print('# fresh = "on"')
    print('# value = "on"')
    print('# vitals = "on"')
    print('# alerts = "off"')
    print('# quiet = "22-7"')
    print('# sync_dir = ""')
    print("# themes: minimal, powerline, ascii, pill, emoji, mono")
    print("# LIMITLINE_ASCII=1 forces the ascii theme. NO_COLOR disables ANSI.")


def cmd_report(markdown):
    try:
        rows = prepare(load_all())
        sys.stdout.write(load_lib("report").render(rows, markdown=markdown))
    except Exception:
        sys.stdout.write("limitline report\n\nusage\n  no local windows yet\n")


def cmd_watch():
    import time
    once = os.environ.get("LIMITLINE_WATCH_ONCE") == "1" or not sys.stdout.isatty()
    try:
        watch = load_lib("watch")
    except Exception:
        return
    while True:
        try:
            rows = prepare(load_all())
            text = watch.frame(rows)
        except Exception:
            text = "limitline watch\n"
        if sys.stdout.isatty() and not once:
            sys.stdout.write("\033[H\033[2J")
        sys.stdout.write(text)
        sys.stdout.flush()
        if once:
            return
        time.sleep(5)


def cmd_theme():
    cmd_preview()
    print('Set one with theme = "pill" or LIMITLINE_THEME=pill')


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: limitline status | --host NAME | preview | doctor | config | report | watch | theme")
        return
    cmd = argv[0]
    if cmd == "status":
        cmd_status()
    elif cmd == "--host":
        kind = argv[1] if len(argv) > 1 else "prompt"
        cmd_host(kind)
    elif cmd == "preview":
        cmd_preview()
    elif cmd == "doctor":
        cmd_doctor()
    elif cmd == "config":
        cmd_config()
    elif cmd == "report":
        cmd_report("--md" in argv[1:])
    elif cmd == "watch":
        cmd_watch()
    elif cmd == "theme":
        cmd_theme()
    else:
        print("usage: limitline status | --host NAME | preview | doctor | config | report | watch | theme")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        sys.exit(0)
