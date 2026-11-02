#!/bin/bash
# SwiftBar / xbar plugin. Refresh every 30 seconds. No network.
# Point this file at the limitline checkout, or put limitline on PATH.
set -u
if [[ -x "$(dirname "$0")/../../bin/limitline" ]]; then
  BIN="$(cd "$(dirname "$0")/../.." && pwd)/bin/limitline"
else
  BIN="limitline"
fi
# Refresh writes the fleet and machine caches. It can ssh, so it stays off the status line.
nohup "$BIN" refresh >/dev/null 2>&1 &
"$BIN" --host swiftbar
