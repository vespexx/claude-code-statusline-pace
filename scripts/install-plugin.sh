#!/usr/bin/env bash
# Install the statusline-pace plugin for Claude Code (band above the prompt).
# Run this from a terminal, then open a new Claude Code session.
# Version: v0.4.1
set -euo pipefail

REPO="vespexx/claude-code-statusline-pace"
PLUGIN="statusline-pace"
TAG="v0.4.1"

echo "=== Installing ${PLUGIN} v${TAG} (band above the prompt) ==="

# Method 1: built-in marketplace install.
if claude plugin install "${PLUGIN}" --marketplace "${REPO}" 2>/dev/null; then
    echo "Installed via --marketplace. Open a new Claude Code session to see the band."
    exit 0
fi

# Method 2: add marketplace first, then install.
if claude plugin marketplace add "${REPO}" 2>/dev/null && \
   claude plugin install "${PLUGIN}"; then
    echo "Installed via marketplace add. Open a new Claude Code session to see the band."
    exit 0
fi

# Method 3: manual install from the release tarball.
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Downloading release assets for ${TAG}..."
curl -fsSL "https://github.com/${REPO}/releases/download/${TAG}/plugin.tar.gz" \
    -o "${TMPDIR}/plugin.tar.gz" 2>/dev/null || {
    echo "Error: could not download plugin.tar.gz"
    exit 1
}

# Find the Claude Code config directory.
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "${CLAUDE_DIR}/plugins"

tar xzf "${TMPDIR}/plugin.tar.gz" -C "${CLAUDE_DIR}/plugins" 2>/dev/null || {
    echo "Error: could not extract plugin.tar.gz"
    exit 1
}

echo "Installed manually to ${CLAUDE_DIR}/plugins."
echo "Open a new Claude Code session to see the band."
