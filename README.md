# claude-code-statusline-pace

A Claude Code status line that shows how fast you burn your subscription limits and **when the 5-hour and 7-day windows will run out**.

![status line](docs/statusline.png)

```
Opus high | 5h pace 60/40% ETA 13:42/15:22; 7d pace 40/17% ETA Fri-07:34/Tue-07:34
```

| Part | Meaning |
| --- | --- |
| `Opus high` | model name and effort level |
| `5h` / `7d` | the rate-limit window |
| `pace 60/40%` | used share of the limit / elapsed share of the window |
| `ETA 13:42/15:22` | when the limit hits 100% at the current burn / when the window resets |
| `ETA -/14:22` | at the current burn the limit will not run out before the reset |

**How the ETA is computed.** Linear extrapolation: the used share per elapsed share of the window stays constant,
so `eta = now + (1 - used) / used * elapsed_time`. No history is stored; it is recomputed from the numbers Claude Code passes on
every refresh. Colours: green = safe (the limit will not run out before the reset), yellow = will run out before the reset, red = already at 100%.

## Install

Needs Python 3 (stdlib only) and a Claude subscription (Pro/Max): `rate_limits` is only present in the status-line input for those plans, and only after the first API response of a session. Without it the line shows just the model (`Opus high`); that is expected, not a broken install.

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

macOS/Linux. On Windows use `python`/`py` and an absolute path instead of `~` in `command`.

## Try it without Claude Code

Needs a clone of this repo (the one-file install has no `examples/`):

```bash
git clone https://github.com/vespexx/claude-code-statusline-pace && cd claude-code-statusline-pace
examples/run.sh   # renders examples/*.json with timestamps relative to now
```

Or feed your own input; `resets_at` must be a near-future epoch (a 5h window resets within 5 hours):

```bash
echo "{\"model\":{\"display_name\":\"Opus\"},\"rate_limits\":{\"five_hour\":{\"used_percentage\":60,\"resets_at\":$(( $(date +%s) + 10800 ))}}}" | python3 statusline.py
```

Input fields used: `model.display_name`, `effort.level`, `rate_limits.five_hour|seven_day.{used_percentage,resets_at}` (epoch seconds or an ISO-8601 string).
Missing fields are skipped; the script never raises, so a bad input cannot blank your status bar.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Notes

- The ETA is a straight-line estimate: a burst at the start of a window makes it pessimistic, an idle start optimistic.
- Times are in the local time zone of the machine running Claude Code.

## License

MIT
