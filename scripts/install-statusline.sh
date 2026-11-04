#!/usr/bin/env bash
# Install the statusline-pace status line script for Claude Code.
# Run this from a terminal. The script is then ready to use.
# Version: v0.4.1
set -euo pipefail

REPO="vespexx/claude-code-statusline-pace"
TAG="v0.4.1"

echo "=== Installing statusline-pace v${TAG} (status line below the prompt) ==="

DEST="$HOME/.claude/statusline-pace.py"
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

echo "Downloading statusline.py from ${TAG}..."
curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TAG}/statusline.py" -o "$TMPFILE" || {
    echo "Error: could not download statusline.py"
    exit 1
}

if [ -f "$DEST" ]; then
    echo "Backing up existing file: ${DEST}.bak"
    cp "$DEST" "${DEST}.bak"
fi

cp "$TMPFILE" "$DEST"
chmod +x "$DEST"

echo "Installed to ${DEST}."
echo ""
echo "To use it, add this to your ~/.zshrc or ~/.bashrc:"
echo ""
echo '  export CLAUDE_CODE_STATUSLINE="$HOME/.claude/statusline-pace.py"'
echo ""
echo "Then restart Claude Code."
