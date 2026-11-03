#!/bin/sh
# Render every examples/*.json through the status line. "@NOW+3h" / "@NOW+5.8d" placeholders become real timestamps.
# A sibling <name>.state is the windows file (PACE_STATE_FILE) for that example.
dir=$(cd "$(dirname "$0")" && pwd)
for f in "$dir"/*.json; do
  python3 - "$f" "$dir/../statusline.py" <<'PY'
import os, re, subprocess, sys, tempfile, time
def ts(m):
    return str(int(time.time() + float(m.group(1)) * {"h": 3600, "d": 86400}[m.group(2)]))
def load(path):
    return re.sub(r'"@NOW\+([\d.]+)([hd])"', ts, open(path).read())
env = dict(os.environ)
env.pop("PACE_STATE_FILE", None)
state = sys.argv[1][:-len(".json")] + ".state"
if os.path.exists(state):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    tmp.write(load(state))
    tmp.close()
    env["PACE_STATE_FILE"] = tmp.name
print(subprocess.run([sys.executable, sys.argv[2]], input=load(sys.argv[1]), capture_output=True, text=True, env=env).stdout)
if "PACE_STATE_FILE" in env:
    os.unlink(env["PACE_STATE_FILE"])
PY
done
