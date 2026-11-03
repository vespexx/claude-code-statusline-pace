#!/usr/bin/env python3
"""Claude Code status line: model, effort and the pace of the plan behind the current model, with run-out ETAs.

Output: `Opus 5.5 high | 5h pace 60/40% ETA 15:00/16:40; 7d pace 40/17% ETA Fri-08:52/Tue-08:52`
  pace    used % / elapsed % of the window
  ETA     when the window reaches 100% if the burn so far continues / when the window resets
          (`-` when the limit will not run out before the reset, `now` when it is already at 100%)
  colour  green on pace, red off pace: 5h used > max(1.5 x elapsed, 10%) or > 75%; 7d and 1mo used > elapsed + 5%

Plans: a Claude model shows the Claude 5h/7d windows (`rate_limits` on stdin). An OpenCode Go model (an id with
`opencode-go`, or `Go` / `Go Plus` in its label) shows the Go 5h/7d/1mo windows from the JSON file that
PACE_STATE_FILE names, in the shape claude-litellm-router writes:
`{"plans": {"go": {"5h": {"utilization": 0.14, "reset": <epoch>}, "7d": {...}, "1mo": {...}}}}`.
Any other model shows no windows. A long `/model` label is cut to its name, plan and token estimate.

Keep in sync with plugins/statusline-pace/hooks/register.tsx. Stdlib only, never raises.
"""
import datetime, json, math, os, re, sys, time

RED, YEL, GRN, RST = "\033[31m", "\033[33m", "\033[32m", "\033[0m"
WINDOWS = {"5h": 5 * 3600, "7d": 7 * 86400, "1mo": 30 * 86400}
RATE_KEYS = {"5h": "five_hour", "7d": "seven_day"}
TIME_FMT = {"5h": "%H:%M", "7d": "%a-%H:%M", "1mo": "%d.%m"}
PLAN_TAGS = {"Go", "Go Plus", "subscription", "free tier"}


def fmt(w, ts):
    try:
        return time.strftime(TIME_FMT[w], time.localtime(ts))
    except (OverflowError, OSError, ValueError):
        return "?"


def epoch(v):
    """resets_at as epoch seconds; also accepts an ISO-8601 string."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def eta(w, util, elapsed, now, reset):
    """Linear extrapolation: the share used per share of elapsed time stays constant."""
    if util >= 1:
        return "now"
    if util <= 0 or elapsed <= 0:
        return "-"
    at = now + (1 - util) / util * elapsed * WINDOWS[w]
    return "-" if at >= reset else fmt(w, at)


def off_pace(w, util, elapsed):
    """The 5h window may run ahead of time (1.5x, never past 75%); the long windows may lead it by 5 points."""
    if w == "5h":
        return util > max(1.5 * elapsed, 0.1) or util > 0.75
    return util > elapsed + 0.05


def window_part(w, util, reset, now):
    if not (math.isfinite(util) and math.isfinite(reset)):
        return ""
    if now >= reset:  # stale data: the window has already rolled over
        util, elapsed = 0.0, 0.0
    else:
        elapsed = min(1.0, max(0.0, 1 - (reset - now) / WINDOWS[w]))
    col = RED if off_pace(w, util, elapsed) else GRN
    return "%s%s pace %d/%d%% ETA %s/%s%s" % (col, w, math.floor(util * 100 + 1e-9), round(elapsed * 100),
                                            eta(w, util, elapsed, now, reset), fmt(w, reset) if now < reset else "now", RST)


def windows_part(wins, now):
    return "; ".join(p for p in (window_part(w, u, r, now) for w, u, r in wins) if p)


def rate_windows(rate):
    """The Claude windows from the status-line input: [(window, used share, reset epoch)]."""
    out = []
    for w, key in RATE_KEYS.items():
        try:
            r = rate[key]
            out.append((w, float(r["used_percentage"]) / 100, epoch(r["resets_at"])))
        except Exception:  # noqa: BLE001
            continue
    return out


def state_windows(state, plan):
    """A plan's windows from the state file: plans.<plan>.<window> = {utilization, reset}; `subscription` for Claude."""
    plans = state.get("plans") if isinstance(state, dict) and isinstance(state.get("plans"), dict) else {}
    src = plans.get(plan) if isinstance(plans.get(plan), dict) else {}
    if not src and plan == "claude" and isinstance(state, dict) and isinstance(state.get("subscription"), dict):
        src = state["subscription"]
    out = []
    for w in WINDOWS:
        x = src.get(w) if isinstance(src.get(w), dict) else {}
        try:
            out.append((w, float(x["utilization"]), float(x["reset"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def label_items(label):
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", label)
    return (m.group(1), [i.strip() for i in m.group(2).split(",")]) if m else (label, [])


def plan_of(model_id, label):
    """`claude`, `go` or "" (no plan with windows) for the model, by its id and its /model label."""
    s = (model_id + " " + label).lower()
    items = set(label_items(label)[1])
    if "opencode-go" in s or items & {"Go", "Go Plus"}:
        return "go"
    if "subscription" in items or any(k in s for k in ("claude", "opus", "sonnet", "haiku")):
        return "claude"
    return ""


def short_label(label):
    """`GLM5.3flash (Cloud, Go Plus, $ BEST, ≈360M out.tok/mo, limit $180 = ...)` -> `GLM5.3flash (Go Plus, ≈360M out.tok/mo)`:
    the name, the plan and the token estimate."""
    name, items = label_items(label)
    keep = [i for i in items if i in PLAN_TAGS or i.startswith("z.ai") or i.startswith("≈")]
    return name + (" (%s)" % ", ".join(keep) if keep else "")


def pace_part(rate, now):
    return windows_part(rate_windows(rate), now)


def read_state():
    path = os.environ.get("PACE_STATE_FILE")
    if not path:
        return {}
    try:
        with open(os.path.expanduser(path)) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        inp = {}
    if not isinstance(inp, dict):
        inp = {}
    model = inp.get("model") if isinstance(inp.get("model"), dict) else {}
    effort = inp.get("effort")
    effort = effort.get("level") if isinstance(effort, dict) and isinstance(effort.get("level"), str) else ""
    mid = str(model.get("id") or "")
    label = str(model.get("display_name") or mid or "?")
    segs = [short_label(label) + (" " + effort if effort else "")]
    plan = plan_of(mid, label)
    wins = []
    if plan == "claude":
        wins = rate_windows(inp.get("rate_limits") or {}) or state_windows(read_state(), "claude")
    elif plan:
        wins = state_windows(read_state(), plan)
    pace = windows_part(wins, time.time())
    if pace:
        segs.append(pace)
    sys.stdout.write(" | ".join(segs))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        sys.stdout.write("statusline error")
