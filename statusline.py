#!/usr/bin/env python3
"""Claude Code status line: model, effort and the pace of the plan behind the current model, with run-out ETAs.

Output (multi-line, aligned columns):
  qwen-local-pool medium ctx 4% | Claude 5h pace 7/28% ETA -/14:00 · 1d pace 12/28% ETA -/14:00 · 7d pace 23/16% ETA Sun-02:48/Tue-08:00
                                Go     5h pace 0/10% ETA -/14:53 · 7d pace 100/33% ETA now/Mon-03:00 · 1mo pace 100/16% ETA now/29.11
                                z.ai                               7d pace 93/65% ETA Wed-18:34/Fri-21:53

Row 1: model+effort[ ctx N%] | <plan> <windows> (plan of selected model is bold)
Rows 2..n: other plans from state file, one row per plan with data
pace    used % / elapsed % of the window
ETA     when the window reaches 100% if the burn so far continues / when the window resets
          (`-` when the limit will not run out before the reset, `now` when it is already at 100%)
colour  green on pace, red off pace: 5h used > max(1.5 x elapsed, 10%) or > 75%; 1d/7d/1mo used >= 90% OR used > elapsed + 5%
bold    the plan label (Claude/Fable/Go/z.ai/OpenRouter) of the plan behind the selected model

Plans (row order): claude, fable, go, zai, openrouter.
Claude windows from engine `rate_limits` on stdin (5h/7d), fallback to state file `plans.claude` or old `subscription`.
All other plans only from state file `plans.<plan>`.
plan_of/plan_of: 'fable' when id/label contains "fable" (before claude check), 'openrouter' when contains "openrouter" (before claude).
Kind order: 5h, 1d, 7d, 1mo. 1d length 86400s, format HH:MM like 5h. Off-pace rule for 1d = long-window rule.
State file: `{"updated": <epoch>, "plans": {"claude": {...}, "fable": {...}, "go": {...}, "zai": {...}, "openrouter": {...}}}`.
A window or plan can be absent. Old router shape `{"subscription": {...}}` still works as Claude fallback.
Stale file (updated > 6h ago) ignored. NaN filtered, negative clamped.
Stdlib only, never raises.
"""
import datetime, json, math, os, re, sys, time, urllib.request

RED, YEL, GRN, RST, BLD = "\033[31m", "\033[33m", "\033[32m", "\033[0m", "\033[1m"
WINDOWS = {"5h": 5 * 3600, "1d": 86400, "7d": 7 * 86400, "1mo": 30 * 86400}
RATE_KEYS = {"5h": "five_hour", "7d": "seven_day"}
TIME_FMT = {"5h": "%H:%M", "1d": "%H:%M", "7d": "%a-%H:%M", "1mo": "%d.%m"}
PLAN_TAGS = {"Go", "Go Plus", "subscription", "free tier", "Fable", "OpenRouter"}
STALE_THRESHOLD_S = 21600  # 6 hours

PLAN_DISPLAY = {"claude": "Claude", "fable": "Fable", "go": "Go", "zai": "z.ai", "openrouter": "OpenRouter"}
PLAN_ORDER = ("claude", "fable", "go", "zai", "openrouter")
KIND_ORDER = ("5h", "1d", "7d", "1mo")
WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def fmt(w, ts):
    try:
        if w in ("5h", "1d"):
            return time.strftime("%H:%M", time.localtime(ts))
        if w == "7d":
            d = time.localtime(ts)
            return f"{WEEK[(d.tm_wday + 1) % 7]}-{d.tm_hour:02d}:{d.tm_min:02d}"
        # 1mo
        return time.strftime("%d.%m", time.localtime(ts))
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
    """The 5h window may run ahead of time (1.5x, never past 75%); the long windows (1d/7d/1mo) have a 90% hard cap or lead by 5pp."""
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
    """A plan's windows from the state file: plans.<plan>.<window> = {utilization, reset}; `subscription` for Claude fallback.
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
    for w in KIND_ORDER:
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
    """`claude`, `fable`, `go`, `zai`, `openrouter` or "" (no plan with windows) for the model, by its id and its /model label."""
    s = (model_id + " " + label).lower()
    items = set(label_items(label)[1])
    # fable check before claude
    if "fable" in s or "Fable" in items:
        return "fable"
    # openrouter check before claude
    if "openrouter" in s or "OpenRouter" in items:
        return "openrouter"
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


def oauth_plans(body):
    """Anthropic's subscription usage endpoint (the data /usage shows) -> plans in the windows-file shape: `five_hour` /
    `seven_day` -> claude 5h/7d; each `limits[]` entry of kind `weekly_scoped` (e.g. Fable) -> a plan named after the model."""
    out = {}

    def put(plan, kind, percent, resets_at):
        try:
            reset = datetime.datetime.fromisoformat(str(resets_at).replace("Z", "+00:00")).timestamp()
            u = float(percent)
        except (TypeError, ValueError):
            return
        if isinstance(percent, (int, float)) and math.isfinite(u):
            out.setdefault(plan, {})[kind] = {"utilization": max(0.0, u) / 100, "reset": reset}

    if not isinstance(body, dict):
        return out
    for key, kind in (("five_hour", "5h"), ("seven_day", "7d")):
        if isinstance(body.get(key), dict):
            put("claude", kind, body[key].get("utilization"), body[key].get("resets_at"))
    for lim in body.get("limits") if isinstance(body.get("limits"), list) else []:
        if not isinstance(lim, dict) or lim.get("kind") != "weekly_scoped":
            continue
        name = ((lim.get("scope") or {}).get("model") or {}).get("display_name")
        if isinstance(name, str):
            put(name.lower(), "7d", lim.get("percent"), lim.get("resets_at"))
    return out


def merge_state(file, oauth, now):
    """The windows file with the endpoint's plans laid over it; a stale file keeps no plans of its own."""
    if not oauth:
        return file
    f = file if isinstance(file, dict) and not is_state_stale(file, now) else {}
    plans = f.get("plans") if isinstance(f.get("plans"), dict) else {}
    return dict(f, updated=now, plans=dict(plans, **oauth))


OAUTH_CACHE = os.path.expanduser("~/.cache/statusline-pace/oauth-usage.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def oauth_token():
    """Claude Code's own login: the macOS keychain item, else ~/.claude/.credentials.json. Never printed or stored."""
    raw = ""
    if sys.platform == "darwin":
        import subprocess
        raw = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                             capture_output=True, text=True, timeout=3).stdout
    if not raw:
        with open(os.path.expanduser("~/.claude/.credentials.json")) as f:
            raw = f.read()
    return json.loads(raw)["claudeAiOauth"]["accessToken"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # the token goes to api.anthropic.com and nowhere else
        return None


def read_oauth(now):
    """Opt-in (PACE_OAUTH=1): the endpoint at most every 5 minutes. Only the parsed plans are cached (OAUTH_CACHE,
    mode 600), never the token. A failed or empty answer keeps the last good plans and their age."""
    if os.environ.get("PACE_OAUTH") != "1":
        return {}
    cache = {}
    try:
        with open(OAUTH_CACHE) as f:
            cache = json.load(f)
    except Exception:  # noqa: BLE001
        pass
    plans = cache.get("plans") if isinstance(cache.get("plans"), dict) else {}
    try:  # the last good plans count only while younger than the stale limit
        last = plans if now - float(cache.get("got", 0)) <= STALE_THRESHOLD_S else {}
        if now - float(cache.get("at", 0)) < 300:
            return last
    except (TypeError, ValueError):
        last = {}
    fresh = {}
    try:
        req = urllib.request.Request(USAGE_URL, headers={"Authorization": "Bearer " + oauth_token(),
                                                         "anthropic-beta": "oauth-2025-04-20"})
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=3) as r:
            fresh = oauth_plans(json.load(r))
    except Exception:  # noqa: BLE001
        pass
    try:
        os.makedirs(os.path.dirname(OAUTH_CACHE), exist_ok=True)
        fd = os.open(OAUTH_CACHE + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:  # a failure is retried in 5 minutes, but the old plans keep their old age
            json.dump({"at": now, "plans": fresh or plans, "got": now if fresh else cache.get("got", 0)}, f)
        os.replace(OAUTH_CACHE + ".tmp", OAUTH_CACHE)
    except Exception:  # noqa: BLE001
        pass
    return fresh or last


def build_rows(snap_wins, model_id, label, effort, show_model, show_context, ctx_percent, state, now):
    """The aligned rows (mirrors the plugin's bandRows). Row 1 starts with the head (`<model> <effort> ctx N%` + " | "),
    later rows are indented to the same column. Each row: the plan label padded to the longest one, then one column per
    kind (5h, 1d, 7d, 1mo) that any row has, each as wide as its longest cell. A gap of 3 before every column but the
    first: " · " when the row has this cell and an earlier one, else spaces. Claude windows come from stdin, else the
    file; the other plans only from the file."""
    current = plan_of(model_id, label)
    plans = [(p, w) for p, w in ((p, snap_wins if p == "claude" and snap_wins else state_windows(state, p, now))
                                 for p in PLAN_ORDER) if w]
    ctx = " ctx %d%%" % round(ctx_percent) if show_context and ctx_percent is not None else ""
    short = short_label(label)
    head = short + (" " + effort if effort else "") + ctx if show_model and short else ""
    if not plans:
        return [head] if head and ctx else []
    cells = [{w: window_part(w, u, r, now) for w, u, r in wins} for _, wins in plans]
    kinds = [k for k in KIND_ORDER if any(k in c for c in cells)]
    width = {k: max(visible_len(c.get(k, "")) for c in cells) for k in kinds}
    label_w = max(len(PLAN_DISPLAY[p]) for p, _ in plans)
    prefix = head + " | " if head else ""
    rows = []
    for i, ((plan, _), c) in enumerate(zip(plans, cells)):
        name = PLAN_DISPLAY[plan]
        row = (prefix if i == 0 else " " * len(prefix)) + (BLD + name + RST if plan == current else name)
        row += " " * (label_w - len(name) + 1)
        seen = False
        for ki, k in enumerate(kinds):
            cell = c.get(k, "")
            if ki:
                row += " · " if cell and seen else "   "
            row += cell + " " * (width[k] - visible_len(cell))
            seen = seen or bool(cell)
        rows.append(row.rstrip())
    return rows


def visible_len(text):
    return len(re.sub(r"\x1b\[\d+m", "", text))


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
    state = merge_state(read_state(), read_oauth(time.time()), time.time())
    now = time.time()

    # Engine Claude windows
    snap_wins = rate_windows(inp.get("rate_limits") or {})

    # Context window percentage from stdin
    ctx_percent = None
    ctx_obj = inp.get("context_window")
    if isinstance(ctx_obj, dict) and isinstance(ctx_obj.get("used_percentage"), (int, float)):
        val = float(ctx_obj["used_percentage"])
        if math.isfinite(val):
            ctx_percent = val

    rows = build_rows(snap_wins, mid, label, effort, True, True, ctx_percent, state, now)
    sys.stdout.write("\n".join(rows) or (short_label(label) + (" " + effort if effort else "")))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        sys.stdout.write("statusline error")
