Pace colours: red only for a window whose limit is used up (ETA now); off pace is yellow; on pace is green, and on-pace cells in a row with a used-up window have no colour. Same rule in the status-line script and the plugin.

---

## Install

### A. Plugin: band above the prompt

Needs Claude Code 2.1.311 or later (plugin mods).

**Option 1: ask your AI.** Paste this text into Claude Code or another AI agent that can run shell commands:

```
Install the Claude Code plugin statusline-pace. Run these two commands in a shell, one after the other:

claude plugin marketplace add vespexx/claude-code-statusline-pace
claude plugin install statusline-pace@statusline-pace

If a command fails, show me the error and stop. When both commands succeed, tell me to open a new Claude Code session.
```

**Option 2: install it yourself.** Run the one-line installer:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/main/scripts/install-plugin.sh | bash
```

Or, at the prompt of a Claude Code session:

```
/plugin install statusline-pace --marketplace vespexx/claude-code-statusline-pace
```

Answer `y` to add the marketplace, then pick a scope (user scope loads it in every session). If your Claude Code does
not know `--marketplace`, run this from a shell:

```
claude plugin marketplace add vespexx/claude-code-statusline-pace && claude plugin install statusline-pace@statusline-pace
```

**Open a new Claude Code session** after installing: a running session does not pick up the plugin.

### B. Status line: below the prompt

Needs Python 3 (stdlib only). The status line **replaces the status line you have now**.

**Option 1: ask your AI.** Paste this text into Claude Code or another AI agent that can run shell commands:

```
Install the Claude Code status line statusline-pace. Do these steps in order:

1. Download https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/v0.4.1/statusline.py to ~/.claude/statusline-pace.py.
2. Make ~/.claude/statusline-pace.py executable.
3. If ~/.claude/settings.json exists, copy it to a backup file next to it.
4. Merge this key into ~/.claude/settings.json. Keep all other keys. Do not replace the file. If the file does not exist, create it with this key only:
   "statusLine": {"type": "command", "command": "python3 ~/.claude/statusline-pace.py", "refreshInterval": 60}
5. Tell me the backup path and the old statusLine value, if there was one.
6. Tell me to restart Claude Code.
```

**Option 2: install it yourself.** Run the one-line installer:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/main/scripts/install-statusline.sh | bash
```

The installer downloads `statusline.py` and installs it to `~/.claude/statusline-pace.py`. Then it sets `statusLine` in
`~/.claude/settings.json`. It backs up both files first. To go back, restore your previous `command` from the
`settings.json.bak-<timestamp>` file that the installer prints.

Or download the script manually:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/v0.4.1/statusline.py -o ~/.claude/statusline-pace.py
chmod +x ~/.claude/statusline-pace.py
```

The settings key: do this step only for a manual install, or when the installer prints "Add this key to ... by hand".
Merge this key into your `~/.claude/settings.json` (do not replace the file). `refreshInterval` (seconds) keeps the
ETA current while you are idle:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline-pace.py",
    "refreshInterval": 60
  }
}
```

**Restart Claude Code** after installing.

For the Fable row, put the env var `PACE_OAUTH=1` in the command:

```json
"command": "PACE_OAUTH=1 python3 ~/.claude/statusline-pace.py"
```

Full options and the windows file for other plans (Go, z.ai, OpenRouter, Gemini): [README](https://github.com/vespexx/claude-code-statusline-pace#readme).
