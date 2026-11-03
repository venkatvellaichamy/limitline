#!/usr/bin/env python3
"""limitline status, host lines, preview, doctor, and config."""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDERS = ("claude", "codex", "cursor", "grok", "gemini", "xai-plan")


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
        text += " %s%d%%" % ("~" if window.get("estimate") else "", int(used + 0.5))
        if window.get("estimate"):
            text += " estimate"
    elif window.get("usd") is not None:
        try:
            text += " $%.2f" % float(window["usd"])
        except (TypeError, ValueError):
            pass
    machines = window.get("machines")
    if isinstance(machines, int) and machines > 1:
        text += " ×%d" % machines
    return text


def label(row):
    return load_lib("xaiplan").label(row)


def reset_text(row, window):
    """Gemini only logs `Resets in 4h0m` once, so its reset is shown as a fixed
    local moment, `resets Fri 09:35`, rather than a countdown."""
    if row.get("provider") != "gemini" or window.get("resets_at") is None:
        return ""
    when = load_lib("timefmt").day_time(window.get("resets_at"))
    return (" · resets " + when) if when else ""


def constraint(row):
    best = None
    for window in row.get("windows") or []:
        if not isinstance(window, dict):
            continue
        used = window.get("used_pct")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        best = used if best is None else max(best, used)
    return best


def is_estimate(row):
    return row.get("source") == "estimate" or any(
        isinstance(item, dict) and item.get("estimate") for item in (row.get("windows") or []))


def sort_rows(rows):
    # Measured windows first, then estimates, then tools with no window.
    def key(row):
        used = constraint(row)
        name = row.get("provider") or ""
        if used is None:
            return (2, 0, name)
        if is_estimate(row):
            return (1, -used, name)
        return (0, -used, name)
    return sorted(rows, key=key)


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
    if data.get("provider") == "xai-plan":
        return load_lib("xaiplan").brief(data) or "no reading"
    windows = data.get("windows") or []
    if not windows:
        if data.get("provider") == "codex" and data.get("observed_at"):
            age = load_lib("timefmt").age(now_epoch() - int(data["observed_at"]))
            return "no current window (last reading %s ago)" % age
        if data.get("provider") == "grok":
            text = load_lib("grokline").brief(data)
            if text:
                return text
            if data.get("source") == "usage.json":
                return "session tokens only"
        if data.get("source") == "none":
            return "no local quota"
        return "no window"
    parts = [window_text(item) + reset_text(data, item) for item in windows if isinstance(item, dict)]
    text = " · ".join(parts)
    if data.get("stale"):
        text += " stale"
    return text


def short_tokens(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "?"
    if value >= 1e6:
        return "%.1fM" % (value / 1e6)
    if value >= 1e3:
        return "%dk" % int(value / 1e3 + 0.5)
    return "%d" % int(value)


def now_epoch():
    import time
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def status_brief(data):
    if data.get("provider") == "xai-plan":
        return load_lib("xaiplan").brief(data, long=True) or "no reading"
    if data.get("provider") == "grok" and not data.get("windows"):
        text = load_lib("grokline").brief(data, long=True)
        if text:
            return text
    text = provider_brief(data)
    for window in data.get("windows") or []:
        if isinstance(window, dict) and window.get("estimate") and window.get("tokens") is not None:
            text += " (%s of %s tokens)" % (short_tokens(window.get("tokens")), short_tokens(window.get("budget")))
            break
    return text


def load_all():
    rows = [run_provider(name) for name in PROVIDERS]
    rows = load_lib("xaiplan").merge(rows)
    extra = run_provider("spend")
    if extra.get("source") not in (None, "none") and extra.get("windows"):
        rows.append(extra)
    return sort_rows(rows)


OLDER_LIMIT = 12


def cockpit_blocks(swiftbar=False):
    blocks = []
    older_lines = []
    try:
        fleet = load_lib("fleet")
        now = fleet.now_epoch()
        window = fleet.window_seconds()
        states = fleet.collect()
        recent, older = fleet.split_recent(states, now=now, window=window)
        summary = fleet.format_segment(fleet.summarize(recent))
        runs = fleet.run_lines(recent, now=now, swiftbar=swiftbar)
        if older:
            older_lines.append("%s, last active over %s ago" % (fleet.older_summary(older), fleet.window_label(window)))
            shown = fleet.run_lines(older[-OLDER_LIMIT:], now=now, swiftbar=swiftbar)
            older_lines.extend(shown)
            if len(older) > OLDER_LIMIT:
                older_lines.append("+%d more" % (len(older) - OLDER_LIMIT))
    except Exception:
        summary = ""
        runs = []
    try:
        machines = load_lib("machines")
        host_line = machines.status_text()
    except Exception:
        host_line = ""
    try:
        jobs = load_lib("jobs")
        found = jobs.load()
        job_lines = []
        if found:
            job_lines.append("jobs: " + jobs.summary(found))
            job_lines.extend(jobs.detail_lines(found))
    except Exception:
        job_lines = []
    if summary:
        blocks.append(("Fleet", [summary]))
    if job_lines:
        blocks.append(("Jobs", job_lines))
    if host_line:
        blocks.append(("Machines", [host_line]))
    if runs:
        blocks.append(("Runs", runs))
    if older_lines:
        blocks.append(("Older", older_lines))
    return blocks


def record_history(rows):
    try:
        load_lib("history").record(rows)
    except Exception:
        pass


def cmd_status():
    rows = prepare(load_all())
    record_history(rows)
    width = max([8] + [len(label(row)) for row in rows])
    print("%-*s %s" % (width, "tool", "limits"))
    for row in rows:
        print("%-*s %s" % (width, label(row), status_brief(row)))
    for title, lines in cockpit_blocks():
        print("")
        print(title)
        for line in lines:
            print(line)


def cmd_host(kind):
    rows = prepare(load_all())
    if kind == "json":
        json.dump(rows, sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
        return
    if kind == "swiftbar":
        title = "limits"
        for row in rows:
            if row.get("windows"):
                title = window_text(row["windows"][0])
                break
        print(title)
        print("---")
        for row in rows:
            print("%s  %s" % (label(row), provider_brief(row)))
        for title_name, lines in cockpit_blocks(swiftbar=True):
            print("---")
            print(title_name)
            for line in lines:
                print(line)
        return
    parts = []
    for row in rows:
        if not row.get("windows"):
            continue
        parts.append("%s %s" % (label(row), provider_brief(row)))
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


def on_value(raw):
    return str(raw or "").strip().lower() in ("1", "on", "true", "yes")


def cache_age(path):
    import time
    try:
        return int(time.time() - os.path.getmtime(path))
    except OSError:
        return None


def ttl_setting(config, name, env):
    try:
        return int(float(config.setting(name, env, "180")))
    except (TypeError, ValueError):
        return 180


def segment_enabled(config, name, env):
    if os.environ.get(env) not in (None, ""):
        return on_value(os.environ.get(env)), "env %s" % env
    seg = config.values().get("segments", "")
    if name in config.parse_list(seg):
        return True, "segments"
    raw = config.values().get(name)
    if raw is not None:
        return on_value(raw), "config %s = %s" % (name, raw)
    return False, "off by default"


def fleet_doctor():
    """Which fleet sources exist here, and why a segment would be empty."""
    lines = []
    why = {}
    config = load_lib("config")
    fleet = load_lib("fleet")
    machines = load_lib("machines")
    refresher = load_lib("refresher")
    cache = machines.cache_dir()

    remote = str(os.environ.get("CLAUDE_CODE_REMOTE") or "").strip().lower() not in ("", "0", "false", "no")
    lines.append("session: %s" % ("cloud-hosted (local Macs are not reachable; use sync_dir snapshots)" if remote else "local"))

    fleet_on, fleet_why = segment_enabled(config, "fleet", "LIMITLINE_FLEET")
    mach_on, mach_why = segment_enabled(config, "machines", "LIMITLINE_MACHINES")
    lines.append("fleet segment: %s (%s)" % ("on" if fleet_on else "off", fleet_why))
    lines.append("machines segment: %s (%s)" % ("on" if mach_on else "off", mach_why))

    root = fleet.pharos_runs_root()
    states = fleet.load_states(root)
    window = fleet.window_seconds()
    if states:
        recent, older = fleet.split_recent(states, window=window)
        lines.append("pharos runs: %d (%d within %s, %d older)" % (len(states), len(recent), fleet.window_label(window) if window else "all", len(older)))
    else:
        found = fleet.from_ps(fleet.read_ps())
        lines.append("pharos runs: none; process scan sees %d agent process%s" % (len(found), "" if len(found) == 1 else "es"))

    fleet_ttl = ttl_setting(config, "fleet_ttl", "LIMITLINE_FLEET_TTL")
    fleet_file = os.environ.get("LIMITLINE_FLEET_LINE") or os.path.join(cache, "fleet.line")
    age = cache_age(fleet_file)
    text = ""
    if age is not None:
        try:
            text = open(fleet_file).readline().strip()
        except OSError:
            text = ""
    if age is None:
        lines.append("fleet cache: missing")
    else:
        lines.append("fleet cache: %ds old, ttl %ds%s" % (age, fleet_ttl, "" if age <= fleet_ttl else " (stale, hidden)"))

    hosts = machines.resolve_hosts()
    if "LIMITLINE_HOSTS" in os.environ:
        host_src = "LIMITLINE_HOSTS"
    elif config.values().get("hosts"):
        host_src = "config hosts"
    elif hosts:
        host_src = "~/.pharos/machines.json"
    else:
        host_src = "none"
    lines.append("hosts: %s (%s)" % (", ".join(item["name"] for item in hosts) or "none", host_src))
    for item in hosts:
        if item["ssh"] in ("local", "localhost") or item["name"] in ("local", "localhost"):
            continue
        key = any(os.path.isfile(os.path.join(os.path.expanduser("~"), ".ssh", name)) for name in ("id_ed25519", "id_ecdsa", "id_rsa"))
        lines.append("  %s: ssh BatchMode with key%s" % (item["name"], "" if key else " (no default key in ~/.ssh)"))
        break
    mach_ttl = ttl_setting(config, "machines_ttl", "LIMITLINE_MACHINES_TTL")
    mach_file = machines.json_path()
    mage = cache_age(mach_file)
    data = machines.read_cache(ttl=10 ** 9) or {}
    if mage is None:
        lines.append("machines cache: missing")
    else:
        rows = [row for row in data.get("hosts") or [] if isinstance(row, dict)]
        bits = []
        for row in rows:
            state = "ok" if row.get("reachable") else "unreachable"
            if row.get("via"):
                state += " via " + str(row.get("via"))
            bits.append("%s %s" % (row.get("name"), state))
        lines.append("machines cache: %ds old, ttl %ds%s; %s" % (mage, mach_ttl, "" if mage <= mach_ttl else " (stale, hidden)", ", ".join(bits) or "no hosts"))

    xai = load_lib("xaiplan")
    plan_age = cache_age(xai.cache_path())
    if plan_age is None:
        lines.append("cursor+grok plan cache: missing (limitline set xai-plan PCT); Cursor shows a token estimate")
    else:
        row = xai.read()
        state = "hidden, older than 7 days" if not xai.present(row) else ("stale" if row.get("stale") else "fresh")
        lines.append("cursor+grok plan cache: %ds old, %s" % (plan_age, state))
    jobs = load_lib("jobs")
    if os.path.isdir(jobs.jobs_dir()):
        every = jobs.load(every=True)
        lines.append("jobs: %d reported, %d shown" % (len(every), len(jobs.load())))
    else:
        lines.append("jobs: none reported (limitline job update NAME ...)")

    state, detail = refresher.status()
    lines.append("refresher: %s (%s)" % (state, detail))

    sync_dir = config.setting("sync_dir", "LIMITLINE_SYNC_DIR", "")
    if not sync_dir:
        lines.append("sync_dir: not set")
    elif not os.path.isdir(sync_dir):
        lines.append("sync_dir: set but the folder does not exist here")
    else:
        others = []
        for name in sorted(os.listdir(sync_dir)):
            if os.path.isdir(os.path.join(sync_dir, name, "cockpit")):
                others.append(name)
        lines.append("sync_dir: %d machine%s publishing fleet snapshots" % (len(others), "" if len(others) == 1 else "s"))

    if not fleet_on:
        why["fleet"] = "the segment is off; set fleet = \"on\""
    elif age is None:
        why["fleet"] = "no cache yet; run limitline refresh or install-refresher"
    elif age > fleet_ttl:
        why["fleet"] = "cache older than fleet_ttl; install-refresher keeps it fresh"
    elif not text:
        if states:
            why["fleet"] = "no run active or finished within fleet_window"
        else:
            why["fleet"] = "no Pharos runs, no agent processes, and no fresh sync_dir snapshot"
    if not mach_on:
        why["machines"] = "the segment is off; set machines = \"on\""
    elif not hosts and not data.get("hosts"):
        why["machines"] = "no hosts; set hosts = [\"mini=user@host\", \"laptop=local\"] or sync_dir"
    elif mage is None:
        why["machines"] = "no cache yet; run limitline refresh or install-refresher"
    elif mage > mach_ttl:
        why["machines"] = "cache older than machines_ttl; install-refresher keeps it fresh"
    if why:
        lines.append("empty segments:")
        for name in ("fleet", "machines"):
            if name in why:
                lines.append("  %s: %s" % (name, why[name]))
    return lines


def cmd_doctor():
    for tool in ("jq", "python3", "awk", "git"):
        found = shutil.which(tool)
        print("%s: %s" % (tool, "yes" if found else "no"))
    try:
        for line in fleet_doctor():
            print(line)
    except Exception as exc:
        print("fleet sources: check failed (%s)" % exc.__class__.__name__)
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
    print("# fleet and machines stay off on the Claude Code line until named")
    print('# fleet = "on"')
    print('# machines = "on"')
    print('# hosts = ["mini", "worker-1"]')
    print("# ssh_timeout = 2")
    print("# mem_free_warn = 15")
    print('# fleet_window = "12h"')
    print("# fleet_ttl = 180")
    print("# machines_ttl = 180")
    print("# Cursor and Grok share one xAI plan. limitline set xai-plan 69 --resets \"2026-11-05 09:00\"")
    print("# writes its percent; without it Cursor shows a token estimate against this budget")
    print("# cursor_week_tokens = 1000000")
    print("# grok plan and 7-day tokens stay off on the Claude Code line until named")
    print('# grok = "on"')
    print("# background jobs reported with limitline job update; shown unless jobs = \"off\"")
    print('# jobs = "on"')
    print("# jobs_ttl = 600")
    print("# themes: minimal, powerline, ascii, pill, emoji, mono")
    print("# LIMITLINE_ASCII=1 forces the ascii theme. NO_COLOR disables ANSI.")


def cmd_report(markdown, week=False):
    if week:
        try:
            sys.stdout.write(load_lib("history").render_week(markdown=markdown))
        except Exception:
            sys.stdout.write("limitline weekly report\n\nno local history yet\n")
        return
    try:
        rows = prepare(load_all())
        sys.stdout.write(load_lib("report").render(rows, markdown=markdown))
    except Exception:
        sys.stdout.write("limitline report\n\nusage\n  no local windows yet\n")


def watch_header():
    try:
        watch = load_lib("watch")
        rows = prepare(load_all())
        extra = []
        for title, lines in cockpit_blocks():
            # Runs and jobs are the selectable list in the interactive view.
            if title in ("Runs", "Jobs", "Older"):
                continue
            extra.append(title)
            extra.extend(lines)
        return watch.frame(rows, extra)
    except Exception:
        return "limitline watch\n"


def cmd_watch():
    import time
    once = os.environ.get("LIMITLINE_WATCH_ONCE") == "1" or not sys.stdout.isatty()
    if os.environ.get("LIMITLINE_WATCH_KEYS") is not None or (not once and sys.stdin.isatty()):
        load_lib("tui").main(watch_header)
        return
    try:
        watch = load_lib("watch")
    except Exception:
        return
    while True:
        try:
            rows = prepare(load_all())
            extra = []
            for title, lines in cockpit_blocks():
                extra.append(title)
                extra.extend(lines)
            text = watch.frame(rows, extra)
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


USAGE = ("usage: limitline status | --host NAME | preview | doctor | config | report | watch | theme | refresh"
         " | history [--days N] | report [--week] [--md] | set xai-plan PCT [--resets \"YYYY-MM-DD HH:MM\"] [--plan NAME] | job update|list|rm"
         " | install-refresher | uninstall-refresher")


def parse_local(text):
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(text.strip(), fmt).timestamp())
        except ValueError:
            continue
    raise ValueError("--resets takes \"YYYY-MM-DD HH:MM\" in local time")


def refresh_plan_line():
    """Rewrite grok.line now, so the status line shows a new reading at once."""
    try:
        load_lib("refresh").write_grok()
    except Exception:
        pass


def cmd_set(args):
    if not args or args[0] != "xai-plan":
        print("usage: limitline set xai-plan PCT [--resets \"YYYY-MM-DD HH:MM\"] [--plan NAME]", file=sys.stderr)
        return 2
    rest = args[1:]
    pct = None
    resets = None
    plan = None
    i = 0
    try:
        while i < len(rest):
            item = rest[i]
            if item in ("--resets", "--plan"):
                if i + 1 >= len(rest):
                    raise ValueError("%s needs a value" % item)
                if item == "--resets":
                    resets = parse_local(rest[i + 1])
                else:
                    plan = rest[i + 1]
                i += 2
                continue
            if pct is not None:
                raise ValueError("unexpected %s" % item)
            pct = float(item.rstrip("%"))
            i += 1
    except ValueError as exc:
        print("limitline set: %s" % exc, file=sys.stderr)
        return 2
    if pct is None or pct != pct or pct < 0 or pct > 100:
        print("limitline set: PCT must be a number from 0 to 100", file=sys.stderr)
        return 2
    xai = load_lib("xaiplan")
    value = int(pct) if pct.is_integer() else round(pct, 1)
    xai.write(value, resets_at=resets, plan=plan, source="manual")
    refresh_plan_line()
    row = xai.read()
    print("%s %s" % (xai.LABEL, xai.brief(row, long=True) or "saved"))
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
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
        cmd_report("--md" in argv[1:], week="--week" in argv[1:])
    elif cmd == "history":
        sys.exit(load_lib("history").main(argv[1:]) or 0)
    elif cmd == "watch":
        cmd_watch()
    elif cmd == "theme":
        cmd_theme()
    elif cmd in ("install-refresher", "uninstall-refresher"):
        code = load_lib("refresher").main(["install" if cmd.startswith("install") else "uninstall"])
        sys.exit(code or 0)
    elif cmd == "set":
        sys.exit(cmd_set(argv[1:]) or 0)
    elif cmd == "job":
        sys.exit(load_lib("jobs").main(argv[1:]) or 0)
    elif cmd == "refresh":
        try:
            load_lib("refresh").main()
        except Exception:
            return
    else:
        print(USAGE)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        sys.exit(0)
