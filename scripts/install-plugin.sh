#!/usr/bin/env bash
# Install the statusline-pace plugin for Claude Code; read it before running: curl -fsSL <url> | less
set -euo pipefail

REPO="vespexx/claude-code-statusline-pace"
PLUGIN="statusline-pace"
PLUGIN_ID="statusline-pace@statusline-pace"
TAG="v0.4.1"

command -v claude >/dev/null 2>&1 || { echo "Error: the 'claude' CLI is not on PATH. Install Claude Code first."; exit 1; }

echo "=== Installing ${PLUGIN} ${TAG} (band above the prompt) ==="

# Method 1: built-in marketplace install.
echo "Trying: claude plugin install ${PLUGIN} --marketplace ${REPO} (this form needs a recent Claude Code)."
if claude plugin install "${PLUGIN}" --marketplace "${REPO}"; then
    echo "Installed via --marketplace."
    echo "Open a new Claude Code session to see the band."
    exit 0
fi

echo "Method 1 failed. This is expected on older Claude Code versions. Falling back to: marketplace add, then install ${PLUGIN_ID}."

# Method 2: add the marketplace first, then install by plugin id.
claude plugin marketplace add "${REPO}"
claude plugin install "${PLUGIN_ID}"

echo "Installed via marketplace add."
echo "Open a new Claude Code session to see the band."
