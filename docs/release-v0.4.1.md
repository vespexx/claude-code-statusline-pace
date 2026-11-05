Pace colours: red only for a window whose limit is used up (ETA now); off pace is yellow; on pace is green, and on-pace cells in a row with a used-up window have no colour. Same rule in the status-line script and the plugin.

---

## Install

### A. Plugin: band above the prompt

Needs Claude Code 2.1.311 or later (plugin mods). At the prompt of a Claude Code session:

```
/plugin install statusline-pace --marketplace vespexx/claude-code-statusline-pace
```

Answer `y`, pick a scope (user — for yourself). If your Claude Code does not know `--marketplace`:

```
claude plugin marketplace add vespexx/claude-code-statusline-pace && claude plugin install statusline-pace@statusline-pace
```

**Open a new Claude Code session** after installing: a running session does not pick up the plugin.

Or run the one-line installer:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/main/scripts/install-plugin.sh | bash
```

### B. Status line: below the prompt

Run the one-line installer — it downloads `statusline.py`, installs it to `~/.claude/` and sets `statusLine` in `~/.claude/settings.json` (it backs up both files first):

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/main/scripts/install-statusline.sh | bash
```

Restart Claude Code. `statusLine` replaces the status line you have now; restore your previous command from the `settings.json.bak-<timestamp>` file the installer prints.

For the Fable row use the env var `PACE_OAUTH=1` in the command:

```json
"command": "PACE_OAUTH=1 python3 ~/.claude/statusline-pace.py"
```

Or download the script manually:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/v0.4.1/statusline.py -o ~/.claude/statusline-pace.py
chmod +x ~/.claude/statusline-pace.py
```

Then add the `statusLine` key to `~/.claude/settings.json` and restart.

Full options and the windows file for other plans (Go, z.ai, OpenRouter, Gemini): [README](https://github.com/vespexx/claude-code-statusline-pace#readme).
