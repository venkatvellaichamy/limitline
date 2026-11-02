#!/usr/bin/env python3
"""Read limitline's local config file. No network."""
import os


def config_path():
    override = os.environ.get("LIMITLINE_CONFIG")
    if override is not None:
        return override
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    toml = os.path.join(base, "limitline", "config.toml")
    if os.path.isfile(toml):
        return toml
    return os.path.join(base, "limitline", "config")


def values():
    path = config_path()
    found = {}
    if not path or not os.path.isfile(path):
        return found
    try:
        handle = open(path)
    except OSError:
        return found
    with handle:
        for line in handle:
            raw = line.split("#", 1)[0].strip()
            if not raw or "=" not in raw:
                continue
            key, val = raw.split("=", 1)
            key = "".join(key.split())
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            if key:
                found[key] = val
    return found


def parse_list(raw):
    text = (raw or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    items = []
    for piece in text.split(","):
        item = piece.strip().strip('"').strip("'")
        if item:
            items.append(item)
    return items


def setting(name, env, default=""):
    if os.environ.get(env) not in (None, ""):
        return os.environ.get(env)
    return values().get(name, default)
