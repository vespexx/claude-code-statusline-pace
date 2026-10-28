#!/usr/bin/env python3
"""Claude Code status line: model, effort and subscription pace with a run-out ETA for the 5h and 7d windows.

Output: `Opus high | 5h pace 7/5% ETA 16:08/17:00; 7d pace 40/17% ETA Fri-14:15/Tue-08:00`
  pace   used % / elapsed % of the window
  ETA    when the window reaches 100% if the burn so far continues / when the window resets
         (`-` when the limit will not run out before the reset)

Reads the status-line JSON on stdin (model, effort, rate_limits). Stdlib only, never raises.
"""
import datetime, json, math, sys, time

DIM, RED, GRN, RST = "\033[2m", "\033[31m", "\033[32m", "\033[0m"
WINDOWS = {"5h": 5 * 3600, "7d": 7 * 86400}
RATE_KEYS = {"5h": "five_hour", "7d": "seven_day"}
TIME_FMT = {"5h": "%H:%M", "7d": "%a-%H:%M"}


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
    if util <= 0 or elapsed <= 0:
        return "-"
    if util >= 1:
        return "now"
    at = now + (1 - util) / util * elapsed * WINDOWS[w]
    return "-" if at >= reset else fmt(w, at)


def pace_part(rate, now):
    parts = []
    for w, length in WINDOWS.items():
        try:
            r = rate[RATE_KEYS[w]]
            util, reset = float(r["used_percentage"]) / 100, epoch(r["resets_at"])
        except Exception:  # noqa: BLE001
            continue
        if not (math.isfinite(util) and math.isfinite(reset)):
            continue
        if now >= reset:  # stale data: the window has already rolled over
            util, elapsed = 0.0, 0.0
        else:
            elapsed = min(1.0, max(0.0, 1 - (reset - now) / length))
        out = eta(w, util, elapsed, now, reset)
        col = DIM if out == "-" else RED if util >= 1 else GRN
        parts.append("%s%s pace %d/%d%% ETA %s/%s%s" % (col, w, round(util * 100), round(elapsed * 100), out,
                                                       fmt(w, reset) if now < reset else "now", RST))
    return "; ".join(parts)


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
    segs = [str(model.get("display_name") or model.get("id") or "?") + (" " + effort if effort else "")]
    pace = pace_part(inp.get("rate_limits") or {}, time.time())
    if pace:
        segs.append(pace)
    sys.stdout.write(" | ".join(segs))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        sys.stdout.write("statusline error")
