#!/usr/bin/env python3
"""Grok plan and 7-day token text. Grok has no local quota, so this is never a percent."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def week_tokens(data):
    week = data.get("week")
    if not isinstance(week, dict):
        return None
    tokens = week.get("tokens")
    if isinstance(tokens, bool) or not isinstance(tokens, (int, float)):
        return None
    return tokens


def brief(data, long=False):
    """`SuperGrok Plus · 7d 1.2M tok`, or "" when neither fact is on disk.
    long adds the ledger cost and says it is not a quota."""
    parts = []
    plan = data.get("plan")
    if isinstance(plan, str) and plan:
        parts.append(plan)
    tokens = week_tokens(data)
    if tokens is not None:
        parts.append("7d %s tok" % short_tokens(tokens))
    if not parts:
        return ""
    if long:
        week = data.get("week") if isinstance(data.get("week"), dict) else {}
        cost = week.get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            parts.append("$%.2f at API rates" % cost)
        parts.append("not a quota")
    return " · ".join(parts)


def segment(data):
    """The status-line text: `grok SuperGrok Plus · 7d 1.2M tok`, from a reading Pharos gave."""
    text = brief(data or {})
    return ("grok " + text) if text else ""
