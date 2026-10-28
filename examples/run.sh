#!/bin/sh
# Render every examples/*.json through the status line. "@NOW+3h" / "@NOW+5.8d" placeholders become real timestamps.
dir=$(cd "$(dirname "$0")" && pwd)
for f in "$dir"/*.json; do
  python3 - "$f" "$dir/../statusline.py" <<'PY'
import json, re, subprocess, sys, time
raw = open(sys.argv[1]).read()
def ts(m):
    return str(int(time.time() + float(m.group(1)) * {"h": 3600, "d": 86400}[m.group(2)]))
raw = re.sub(r'"@NOW\+([\d.]+)([hd])"', lambda m: ts(m), raw)
print(subprocess.run([sys.executable, sys.argv[2]], input=raw, capture_output=True, text=True).stdout)
PY
done
