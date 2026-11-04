#!/usr/bin/env python3
"""`limitline history` and `limitline report --week`: Pharos's weekly usage report, shown.

Pharos keeps the history (`pharos usage --report`) and writes the same numbers to
~/.pharos/usage-report.json every 2 minutes. limitline keeps no plan history of its
own; the 5h/7d sparklines on the Claude Code line use only the status line's own input.
"""
import json, os, sys

BLOCKS = "▁▂▃▄▅▆▇█"


def report_path():
    home = os.environ.get("LIMITLINE_PHAROS_HOME") or os.path.join(os.path.expanduser("~"), ".pharos")
    return os.environ.get("LIMITLINE_PHAROS_REPORT") or os.path.join(home, "usage-report.json")


def read_report():
    try:
        with open(report_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("plans"), list) else None


def spark(weeks):
    out = ""
    for week in weeks:
        pct = week.get("peak_pct") if isinstance(week, dict) else None
        if not isinstance(pct, (int, float)):
            continue
        out += BLOCKS[min(len(BLOCKS) - 1, int(max(0, pct) / 100 * (len(BLOCKS) - 1) + 0.5))]
    return out


def plan_line(plan):
    weeks = plan.get("weeks") or []
    text = "%-12s %s  avg peak %d%% · %d at limit · %d over 75%%" % (
        plan.get("plan"), spark(weeks[-12:]), int(plan.get("avg_peak_pct") or 0),
        int(plan.get("weeks_at_limit") or 0), int(plan.get("weeks_over_cap") or 0))
    if isinstance(plan.get("unused_month"), (int, float)):
        text += " · $%d/month unused" % int(plan["unused_month"])
    return text


NO_REPORT = "no usage history from Pharos yet (it builds up from `pharos usage --refresh`)\n"


def render_history(report=None):
    report = read_report() if report is None else report
    if not report or not report.get("plans"):
        return "limitline history\n\n" + NO_REPORT
    lines = ["limitline history (weekly peaks from Pharos, since %s)" % report.get("since"), ""]
    lines += [plan_line(plan) for plan in report["plans"]]
    return "\n".join(lines) + "\n"


def render_week(markdown=False, report=None):
    report = read_report() if report is None else report
    title = "# limitline weekly report" if markdown else "limitline weekly report"
    if not report or not report.get("plans"):
        return title + "\n\n" + NO_REPORT
    lines = [title, ""]
    for plan in report["plans"]:
        weeks = plan.get("weeks") or []
        last = weeks[-1] if weeks else {}
        text = "%s: this week's peak %s%%, %d weeks at the limit of %d measured" % (
            plan.get("plan"), int(last.get("peak_pct") or 0), int(plan.get("weeks_at_limit") or 0), int(plan.get("weeks_measured") or 0))
        lines.append(("- " + text) if markdown else text)
    return "\n".join(lines) + "\n"


def main(argv):
    sys.stdout.write(render_history())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
