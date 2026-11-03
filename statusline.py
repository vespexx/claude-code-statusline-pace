#!/usr/bin/env python3
"""Claude Code status line: model, effort and the pace of the plan behind the current model, with run-out ETAs.

Output (multi-line):
  Opus 5.5 high | Claude 5h pace 60/40% ETA 15:00/16:40 · 7d pace 40/17% ETA Fri-08:52/Tue-08:52
  Go 5h pace 14/40% ETA -/23:58 · 7d pace 45/14% ETA Wed-10:00/Mon-03:00 · 1mo pace 73/13% ETA 08.11/29.11
  z.ai 5h pace 20/30% ETA -/14:22 · 7d pace 50/10% ETA Mon-08:00/Sun-08:00

  Row 1: model+effort | Claude <windows> (always shown when any data exists)
  Rows 2..n: Go <windows>, z.ai <windows> from state file when present
  pace    used % / elapsed % of the window
  ETA     when the window reaches 100% if the burn so far continues / when the window resets
          (`-` when the limit will not run out before the reset, `now` when it is already at 100%)
  colour  green on pace, red off pace: 5h used > max(1.5 x elapsed, 10%) or > 75%; 7d and 1mo used >= 90% OR used > elapsed + 5%
  bold    the plan label (Claude/Go/z.ai) of the plan behind the selected model

Plans: Row 1 always shows the Claude windows (5h/7d from engine `rate_limits` on stdin, with fallback to
the state file `subscription`). Rows below show Go (5h/7d/1mo) and z.ai (5h/7d) windows from the state file
written by the subscription-quotas exporter (`~/.local/state/subscription-quotas/windows.json`):
`{"updated": <epoch>, "plans": {"claude": {...}, "go": {...}, "zai": {...}}}`.
A window or plan can be absent. The old router state shape `{"subscription": {...}}` still works as the
Claude fallback. OpenRouter has no pace windows (free daily request counter only), so it shows no row.
Keep in sync with plugins/statusline-pace/hooks/register.tsx: plan_of, short_label, off_pace, state_windows.
Stdlib only, never raises.
"""
import datetime, json, math, os, re, sys, time

RED, YEL, GRN, RST, BLD = "\033[31m", "\033[33m", "\033[32m", "\033[0m", "\033[1m"
WINDOWS = {"5h": 5 * 3600, "7d": 7 * 86400, "1mo": 30 * 86400}
RATE_KEYS = {"5h": "five_hour", "7d": "seven_day"}
TIME_FMT = {"5h": "%H:%M", "7d": "%a-%H:%M", "1mo": "%d.%m"}
PLAN_TAGS = {"Go", "Go Plus", "subscription", "free tier"}
STALE_THRESHOLD_S = 21600  # 6 hours

PLAN_DISPLAY = {"claude": "Claude", "go": "Go", "zai": "z.ai"}
OTHER_PLANS = ("go", "zai")


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
    """The 5h window may run ahead of time (1.5x, never past 75%); the long windows have a 90% hard cap or lead by 5pp."""
    if w == "5h":
        return util > max(1.5 * elapsed, 0.1) or util > 0.75
    return util >= 0.9 or util > elapsed + 0.05


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
    return " · ".join(p for p in (window_part(w, u, r, now) for w, u, r in wins) if p)


def rate_windows(rate):
    """The Claude windows from the status-line input: [(window, used share, reset epoch)]."""
    out = []
    for w, key in RATE_KEYS.items():
        try:
            r = rate[key]
            out.append((w, max(0.0, float(r["used_percentage"])) / 100, epoch(r["resets_at"])))
        except Exception:  # noqa: BLE001
            continue
    return out


def is_state_stale(state, now=None):
    if not isinstance(state, dict):
        return False
    updated = state.get("updated")
    if not isinstance(updated, (int, float)) or not math.isfinite(updated):
        return False
    if now is None:
        now = time.time()
    return now - updated > STALE_THRESHOLD_S


def state_windows(state, plan, now=None):
    """A plan's windows from the state file: plans.<plan>.<window> = {utilization, reset}; `subscription` for Claude.
    Stale file (updated > 6h ago) is treated as no data."""
    if not isinstance(state, dict):
        return []
    if is_state_stale(state, now):
        return []
    plans = state.get("plans") if isinstance(state.get("plans"), dict) else {}
    src = plans.get(plan) if isinstance(plans.get(plan), dict) else {}
    if not src and plan == "claude" and isinstance(state.get("subscription"), dict):
        src = state["subscription"]
    out = []
    for w in WINDOWS:
        x = src.get(w) if isinstance(src.get(w), dict) else {}
        try:
            u, r = float(x["utilization"]), float(x["reset"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(u) and math.isfinite(r):
            out.append((w, u, r))
    return out


def label_items(label):
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", label)
    return (m.group(1), [i.strip() for i in m.group(2).split(",")]) if m else (label, [])


def plan_of(model_id, label):
    """`claude`, `go`, `zai` or "" (no plan with windows) for the model, by its id and its /model label."""
    s = (model_id + " " + label).lower()
    items = set(label_items(label)[1])
    if "opencode-go" in s or items & {"Go", "Go Plus"}:
        return "go"
    # zai check before claude: "zai" in id or label item starting with "z.ai"
    if "zai" in s or any(i.startswith("z.ai") for i in items):
        return "zai"
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


def plan_row(plan, wins, current, now):
    """`<Plan> 5h pace ... · 7d pace ...`; the plan of the selected model is bold."""
    name = PLAN_DISPLAY[plan]
    return (BLD + name + RST if plan == current else name) + " " + windows_part(wins, now)


def build_rows(snap_wins, model_id, label, effort, show_model, show_context, ctx_percent, state, now):
    """Row 1: the model head, the Claude windows (stdin rate_limits, else the state file), ctx.
    Rows below: Go and z.ai from the state file, one row per plan with data."""
    current = plan_of(model_id, label)
    claude = snap_wins or state_windows(state, "claude", now)
    others = [plan_row(p, w, current, now) for p, w in ((p, state_windows(state, p, now)) for p in OTHER_PLANS) if w]
    row1 = plan_row("claude", claude, current, now) if claude else ""
    if show_context and ctx_percent is not None:
        row1 += (" " if row1 else "") + "ctx %d%%" % round(ctx_percent)
    head = short_label(label) + (" " + effort if effort else "")
    if show_model and head and (row1 or others):
        row1 = head + (" | " + row1 if row1 else "")
    return ([row1] if row1 else []) + others


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        inp = {}
    if not isinstance(inp, dict):
        inp = {}
    model = inp.get("model") if isinstance(inp.get("model"), dict) else {}
    effort_obj = inp.get("effort")
    effort = effort_obj.get("level") if isinstance(effort_obj, dict) and isinstance(effort_obj.get("level"), str) else ""
    mid = str(model.get("id") or "")
    label = str(model.get("display_name") or mid or "?")
    state = read_state()
    now = time.time()

    # Engine Claude windows
    snap_wins = rate_windows(inp.get("rate_limits") or {})

    rows = build_rows(snap_wins, mid, label, effort, True, False, None, state, now)
    sys.stdout.write("\n".join(rows) or short_label(label) + (" " + effort if effort else ""))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        sys.stdout.write("statusline error")
