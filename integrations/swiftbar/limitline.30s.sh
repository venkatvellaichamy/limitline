#!/bin/bash
# SwiftBar / xbar plugin. Refresh every 30 seconds. No network.
# Point this file at the limitline checkout, or put limitline on PATH.
set -u
if [[ -x "$(dirname "$0")/../../bin/limitline" ]]; then
  BIN="$(cd "$(dirname "$0")/../.." && pwd)/bin/limitline"
else
  BIN="limitline"
fi
"$BIN" --host swiftbar
