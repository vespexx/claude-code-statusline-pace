#!/usr/bin/env bash
# Install the statusline-pace status line for Claude Code; read it before running: curl -fsSL <url> | less
set -euo pipefail

REPO="vespexx/claude-code-statusline-pace"
TAG="v0.4.1"
CLAUDE_DIR="$HOME/.claude"
DEST="$CLAUDE_DIR/statusline-pace.py"
SETTINGS="$CLAUDE_DIR/settings.json"
TS="$(date +%Y%m%d%H%M%S)"

SNIPPET='  "statusLine": {"type": "command", "command": "python3 ~/.claude/statusline-pace.py", "refreshInterval": 60}'

print_snippet() {
    echo "Add this key to ${SETTINGS} by hand:"
    echo ""
    echo "$SNIPPET"
    echo ""
}

echo "=== Installing statusline-pace ${TAG} (status line below the prompt) ==="

mkdir -p "$CLAUDE_DIR"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
DL_FILE="$WORK_DIR/statusline.py"

echo "Downloading statusline.py from ${TAG}..."
if ! curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TAG}/statusline.py" -o "$DL_FILE"; then
    echo "Error: could not download statusline.py."
    exit 1
fi

if [ ! -s "$DL_FILE" ] || [ "$(head -c 2 "$DL_FILE")" != "#!" ]; then
    echo "Error: the downloaded file is empty or is not a script (no #! line). Nothing was installed."
    exit 1
fi

if [ -e "$DEST" ]; then
    echo "Backing up existing file to ${DEST}.bak-${TS}"
    cp "$DEST" "${DEST}.bak-${TS}"
fi

cp "$DL_FILE" "$DEST"
chmod +x "$DEST"
echo "Installed to ${DEST}."

if command -v python3 >/dev/null 2>&1; then
    if python3 -I -c '
import json, os, shutil, sys
path, ts = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    shutil.copy2(path, path + ".bak-" + ts)
    print("Backed up settings to " + path + ".bak-" + ts)
    text = open(path, encoding="utf-8").read()
    if text.strip():
        try:
            data = json.loads(text)
        except ValueError as e:
            print("Error: " + path + " is not valid JSON (" + str(e) + "). It was not changed.")
            sys.exit(2)
        if not isinstance(data, dict):
            print("Error: " + path + " is not a JSON object. It was not changed.")
            sys.exit(2)
old = data.get("statusLine")
if old is not None:
    old_cmd = old.get("command", json.dumps(old)) if isinstance(old, dict) else json.dumps(old)
    print("Existing statusLine: " + str(old_cmd))
    print("Backup: " + os.path.basename(path) + ".bak-" + ts + " (restore the old command from there)")
data["statusLine"] = {"type": "command", "command": "python3 ~/.claude/statusline-pace.py", "refreshInterval": 60}
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print("Set statusLine in " + path)
' "$SETTINGS" "$TS"; then
        :
    else
        print_snippet
    fi
else
    echo "python3 was not found, so settings.json was not changed."
    print_snippet
fi

echo "This replaces your current status line. Restart Claude Code to see it."
