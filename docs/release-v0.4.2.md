New `Go Free` row, directly under `Go`: the free models of OpenCode Go (`beam-free`) do not use the paid Go allowance, but they have their own limit. There is no usage API for this pool, so the row carries only a status text from the windows file (`plans.gofree.status`), like the `Gemini` row: `ok`, `blocked <model> till <time>` after a 429, or `slow <model> till <time>`. A selected `beam-free` model makes the `Go Free` label bold. Same rule in the status-line script and the plugin.

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

### B. Status line: below the prompt

Download the script:

```
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/v0.4.2/statusline.py -o ~/.claude/statusline-pace.py
chmod +x ~/.claude/statusline-pace.py
```

Then add the `statusLine` key to `~/.claude/settings.json` and restart. `statusLine` replaces the status line you have now.

For the Fable row use the env var `PACE_OAUTH=1` in the command:

```json
"command": "PACE_OAUTH=1 python3 ~/.claude/statusline-pace.py"
```

Full options and the windows file for other plans (Go, Go Free, z.ai, OpenRouter, Gemini): [README](https://github.com/vespexx/claude-code-statusline-pace#readme).
