# claude-code-statusline-pace

A Claude Code status line that shows how fast you burn your subscription limits and **when the plan windows will run out**.

![status line](docs/statusline.png)

```
Opus high | Claude 5h pace 60/40% ETA 15:00/16:40 · 7d pace 40/17% ETA Fri-08:52/Tue-08:52
Go 5h pace 14/40% ETA -/23:58 · 7d pace 45/14% ETA Wed-10:00/Mon-03:00 · 1mo pace 73/13% ETA 08.11/29.11
z.ai 5h pace 20/30% ETA -/14:22 · 7d pace 50/10% ETA Mon-08:00/Sun-08:00
```

The screenshot stacks several cases, one per selected model: Opus (Claude only), a GLM model on the Go plan
(Claude row, then the Go and z.ai rows from the windows file), an exhausted 5h window, and Sonnet. In a real
session you see one block: the Claude row, plus one row per other plan that has data. Times are illustrative.

| Part | Meaning |
| --- | --- |
| `Opus high` | model name and effort level |
| `GLM5.3flash (Go Plus, ≈360M out.tok/mo)` | a long `/model` label is cut to the name, the plan tag and the token estimate; other items in the parentheses are dropped |
| `5h` / `7d` / `1mo` | the rate-limit window |
| `pace 60/40%` | used share of the limit / elapsed share of the window |
| `ETA 15:00/16:40` | when the limit hits 100% at the current burn / when the window resets |
| `ETA now/16:40` | the limit is already at 100% (red) |
| `ETA -/14:22` | at the current burn the limit will not run out before the reset |
| ` · ` | separator between windows |
| ` | ` | separator between the model head and the Claude windows (row 1 only) |
| red / green | off-pace (red) or on-pace (green) |
| **bold** | the plan label (Claude/Go/z.ai) of the plan behind the selected model |

**How the ETA is computed.** Linear extrapolation: the used share per elapsed share of the window stays constant,
so `eta = now + (1 - used) / used * elapsed_time`. No history is stored; it is recomputed from the numbers the router or the engine passes on every refresh.

**Off-pace rules** (the same thresholds a pace-aware model router uses to stop sending work to a plan):
- **5h**: red when used > `max(1.5 × elapsed, 10%)` or used > 75%.
- **7d / 1mo**: red when used ≥ 90% **or** used > elapsed + 5%.
- Everything else is green.

## Install

### As a plugin (one command, no settings edit)

At the prompt of a Claude Code session in a terminal:

```
/plugin install statusline-pace --marketplace vespexx/claude-code-statusline-pace
```

Answer `y` to add the marketplace, then pick a scope (user scope loads it in every session). A pace band appears **above the prompt**: the model and effort, the plan's pace windows and the run-out ETAs — drawn by the plugin itself, with no `statusLine` setting and no Python.

From a shell:
```
claude plugin marketplace add vespexx/claude-code-statusline-pace && claude plugin install statusline-pace@statusline-pace
```

Remove it: `/plugin uninstall statusline-pace`.

The plugin needs a recent Claude Code (it uses the mods API, early access; tested on 2.1.311). It shows rate-limit figures for:
- **Claude** (Pro/Max subscription): 5h and 7d windows from the engine's `rate_limits` on stdin, with a fallback to the state file `subscription`.
- **OpenCode Go** (Go / Go Plus): 5h, 7d, and 1mo windows from the state file `plans.go`.
- **z.ai** (GLM via z.ai): 5h and 7d windows from the state file `plans.zai`.
- The Claude row is shown whatever model is selected; the plan label of the selected model is bold.

**Without a windows file** (`stateFile` empty, the default) you get the Claude row only, with no error. The Go and
z.ai rows need a JSON file in the shape shown under [Windows file for Go and z.ai](#windows-file-for-go-and-zai); no
exporter for it is published here, so you write it yourself from the vendors' usage APIs (or leave it off).

**Important:** after installing or updating the plugin, **open a new Claude Code session** — long-lived sessions do not pick up reinstalled plugin rendering.

### Multiple band plugins above the prompt

Only one plugin can answer the `ui.render { component: "AbovePrompt" }` hook *without* calling `next(e)`. If a plugin above yours in the chain (alphabetical order within the `user` tier) answers instead of wrapping `next(e)`, the plugins below it never draw.

The `statusline-pace` plugin **always wraps `next(e)`** so other bands beneath it can coexist. If you do not see the pace band, check whether another plugin (e.g. `quote-reply`) sits above it alphabetically and answers without `next(e)`. Example: the upstream issue [vakovalskii/quote-reply#1](https://github.com/vakovalskii/quote-reply/issues/1) tracks fixing `quote-reply` to call `next(e)`.

The chain order within the `user` tier is alphabetical by plugin name, e.g. `paste-preview` → `quote-reply` → `statusline-pace`. To find the plugin that takes the band, disable the other above-prompt plugins one at a time (`/plugin disable <name>`), open a new session, and see when the pace band comes back.

### The plain status line (any Claude Code, needs Python 3)

Needs Python 3 (stdlib only). It reads the same data sources as the plugin and prints one or more lines to the status bar (Claude Code shows multi-line status line output).

```bash
curl -fsSL https://raw.githubusercontent.com/vespexx/claude-code-statusline-pace/main/statusline.py -o ~/.claude/statusline-pace.py
```

Merge this key into your existing `~/.claude/settings.json` (do not replace the file), then restart Claude Code. `statusLine` is a single setting: it **replaces any status line you already have**; to go back, restore your previous `command` (or delete the key). `refreshInterval` (seconds) keeps the ETA current while you are idle:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline-pace.py",
    "refreshInterval": 60
  }
}
```

macOS/Linux. On Windows use `python` (or `py`) and a forward-slash absolute path, e.g. `"command": "python C:/Users/you/.claude/statusline-pace.py"`.

### Plugin configuration

The plugin accepts these user-configurable options (set via `/plugin configure statusline-pace` or in `pluginConfigs` in `settings.json`):

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `showModel` | boolean | `true` | Show the model name and effort at the start of the band. |
| `showContext` | boolean | `false` | Show the context-window fill (`ctx 34%`) after the windows on row 1. |
| `stateFile` | string | `""` | Path to the subscription-quotas exporter state file (`windows.json`) for the OpenCode Go windows (`plans.go`), z.ai windows (`plans.zai`), and the Claude subscription fallback (`subscription` / `plans.claude`). `~/` expands to `$HOME`. Empty = off. |

Example `settings.json` snippet with a windows file:
```json
{
  "pluginConfigs": {
    "statusline-pace@statusline-pace": {
      "options": {
        "showModel": true,
        "showContext": false,
        "stateFile": "~/.local/state/subscription-quotas/windows.json"
      }
    }
  }
}
```

### Windows file for Go and z.ai

The OpenCode Go windows (5h / 7d / 1mo) and z.ai windows (5h / 7d) come from a JSON file that some other tool keeps fresh. The author uses a private exporter (a launchd job, every 5 minutes, not published) that polls the vendor usage APIs and writes `~/.local/state/subscription-quotas/windows.json`; any tool that writes the same shape works. The file shape:
```json
{
  "updated": <epoch seconds>,
  "plans": {
    "claude": {"5h": {"utilization": 0.38, "reset": <epoch>}, "7d": {...}},
    "go": {"5h": {...}, "7d": {...}, "1mo": {...}},
    "zai": {"5h": {...}, "7d": {...}}
  }
}
```
A window or plan can be absent. The old router state shape `{"subscription": {"5h": {...}, "7d": {...}}}` still works as the Claude fallback (the plugin and the plain status line both accept it). The plugin reads that file via the `stateFile` option; the plain `statusline.py` in this repo reads the same file via `PACE_STATE_FILE` env var.

**Stale file handling:** when the state has a numeric top-level `updated` and `now - updated > 21600` s (6 hours), the plans from the file are ignored (treated as no data). No `updated` key → the data is used (old router shape).

## Try it without Claude Code

Needs a clone of this repo (the one-file install has no `examples/`):

```bash
git clone https://github.com/vespexx/claude-code-statusline-pace && cd claude-code-statusline-pace
examples/run.sh   # renders examples/*.json with timestamps relative to now; a sibling <name>.state is used as the windows file
```

Or feed your own input; `resets_at` must be a near-future epoch (a 5h window resets within 5 hours):

```bash
echo "{\"model\":{\"display_name\":\"Opus\"},\"rate_limits\":{\"five_hour\":{\"used_percentage\":60,\"resets_at\":$(( $(date +%s) + 10800 ))}}}" | python3 statusline.py
```

Input fields used: `model.display_name`, `effort.level`, `rate_limits.five_hour|seven_day.{used_percentage,resets_at}` (epoch seconds or an ISO-8601 string).
Missing fields are skipped; the script never raises, so a bad input cannot blank your status bar.

The screenshot is regenerated by `python3 scripts/make_screenshot.py` (needs Google Chrome).

## Tests

```bash
python3 -m unittest discover -s tests
```

For the plugin:
```bash
claude plugin test plugins/statusline-pace
claude plugin validate plugins/statusline-pace
```

## Notes

- OpenRouter is not shown: it has no pace windows (only a free daily request counter).
- The ETA is a straight-line estimate: a burst at the start of a window makes it pessimistic, an idle start optimistic.
- Times are in the local time zone of the machine running Claude Code.
- The band wraps to two rows when it does not fit on one line (`flexWrap: wrap`).

## License

MIT