#!/usr/bin/env python3
"""Estimate an API-equivalent dollar value from local cost or token fields."""
import json, os, sys

# Public list prices used only as an estimate. The status line says so.
RATES = {
    "opus": (5.0, 25.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
    "default": (3.0, 15.0),
}


def family(name):
    text = str(name or "").lower()
    for key in ("opus", "sonnet", "haiku"):
        if key in text:
            return key
    return "default"


def money(amount):
    if amount >= 10:
        return "$%d" % int(amount + 0.5)
    if abs(amount - int(amount)) < 0.001:
        return "$%d" % int(amount)
    return "$%.2f" % amount


def add_tokens(total, obj, model_name):
    if not isinstance(obj, dict):
        return total
    inn = obj.get("input_tokens")
    out = obj.get("output_tokens")
    if not isinstance(inn, (int, float)) and not isinstance(out, (int, float)):
        return total
    if isinstance(inn, bool):
        inn = 0
    if isinstance(out, bool):
        out = 0
    rate_in, rate_out = RATES[family(obj.get("model") or model_name)]
    inn = float(inn or 0)
    out = float(out or 0)
    return total + (inn / 1000000.0) * rate_in + (out / 1000000.0) * rate_out


def direct_cost(data):
    for key in ("week_usd", "week_cost_usd", "total_cost", "totalCost", "cost_usd"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def estimate(data):
    if not isinstance(data, dict):
        return None
    cost = direct_cost(data)
    if cost is not None:
        return cost
    total = add_tokens(0.0, data, data.get("model"))
    models = data.get("models")
    if isinstance(models, dict):
        for name, obj in models.items():
            if isinstance(obj, dict) and direct_cost(obj) is not None:
                total += direct_cost(obj)
            else:
                total = add_tokens(total, obj, name)
    return total if total > 0 else None


def load():
    path = os.environ.get("LIMITLINE_VALUE_FILE")
    if not path:
        path = os.path.join(os.path.expanduser("~"), ".claude", "stats-cache.json")
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path) as handle:
            return json.load(handle)
    except Exception:
        return None


def render():
    amount = estimate(load())
    if amount is None or amount <= 0:
        return ""
    return "≈ %s of value this week" % money(amount)


def main():
    text = render()
    if text:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
