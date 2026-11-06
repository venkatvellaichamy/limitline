#!/usr/bin/env python3
"""Local-time labels shared by status, watch, report, and the plan cache."""
import time
from datetime import datetime


def _local(epoch):
    try:
        return datetime.fromtimestamp(int(epoch))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def day_time(epoch):
    """`Fri 09:35` in local time, or "" when the epoch is unusable."""
    stamp = _local(epoch)
    if stamp is None:
        return ""
    return "%s %s" % (time.strftime("%a", stamp.timetuple()), stamp.strftime("%H:%M"))


def month_day(epoch):
    """`Nov 5` in local time. %-d is not portable, so the day is formatted by hand."""
    stamp = _local(epoch)
    if stamp is None:
        return ""
    return "%s %d" % (time.strftime("%b", stamp.timetuple()), stamp.day)


def clock(epoch):
    stamp = _local(epoch)
    return stamp.strftime("%H:%M") if stamp else ""


def age(seconds):
    """`45m`, `114m` (minutes under 2 h), `9h`, `3d`."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        seconds = 0
    if seconds < 7200:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)
