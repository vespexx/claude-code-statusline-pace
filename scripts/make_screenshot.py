#!/usr/bin/env python3
"""Regenerate the README pictures (docs/*.svg and docs/*.png; the PNG needs Google Chrome).

Two layouts x two cases, all drawn from statusline.py (the plugin draws the same rows; tests/layout-cases.json holds both
to that): the plugin band above the prompt and the plain status line below it, for a Max $100 plan with no windows file
(examples/max-100: Claude and Fable rows) and for a full windows file with running sub-agents (examples/all-plans). The frame around the rows (a
dim chat line, the prompt box) is a mock of the Claude Code screen; the times are relative to the moment of the run.

Run from the repo root: python3 scripts/make_screenshot.py
"""
import html, json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
COLS = {"31": "#ff6b6b", "32": "#6bdc8b", "33": "#f5c451"}
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CASES = {"max-100": "max-100", "all-plans": "all-plans"}
LINE, CHAR = 30, 10.3


def tspans(line, base="#e6e6e6"):
    res, cur, weight = [], base, "normal"
    for tok in re.split(r"(\x1b\[\d+m)", line):
        m = re.match(r"\x1b\[(\d+)m", tok)
        if m and m.group(1) == "1":
            weight = "bold"
        elif m:
            cur, weight = COLS.get(m.group(1), base), "normal"
        elif tok:
            res.append('<tspan fill="%s" font-weight="%s">%s</tspan>' % (cur, weight, html.escape(tok)))
    return "".join(res)


def load(path):
    ts = lambda m: str(int(time.time() + float(m.group(1)) * {"h": 3600, "d": 86400}[m.group(2)]))
    return re.sub(r'"@NOW\+([\d.]+)([hd])"', ts, open(path).read())


AGENTS = {"all-plans": [("worker-coder", "glm-5.3-flash"), ("worker-explorer", None), ("worker-explorer", None)]}


def rows_of(name):
    """The status-line output for examples/<name>.json with examples/<name>.state as the windows file, and the running
    sub-agents of AGENTS[name] as fresh transcripts in a temporary session folder."""
    env = dict(os.environ)
    env.pop("PACE_OAUTH", None)
    with tempfile.TemporaryDirectory() as d:
        state = os.path.join(d, "windows.json")
        with open(state, "w") as f:
            f.write(load(os.path.join(ROOT, "examples", name + ".state")))
        env["PACE_STATE_FILE"] = state
        sub = os.path.join(d, "sid", "subagents")
        os.makedirs(sub)
        for i, (kind, model) in enumerate(AGENTS.get(name, [])):
            with open(os.path.join(sub, "agent-%d.jsonl" % i), "w") as f:
                f.write(json.dumps({"message": {"role": "assistant", "model": model}} if model else {"type": "user"}) + "\n")
            with open(os.path.join(sub, "agent-%d.meta.json" % i), "w") as f:
                json.dump({"agentType": kind}, f)
        inp = json.loads(load(os.path.join(ROOT, "examples", name + ".json")))
        inp.update(transcript_path=os.path.join(d, "sid.jsonl"), session_id="sid")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "statusline.py")], input=json.dumps(inp),
                             capture_output=True, text=True, env=env, check=True).stdout
    return out.splitlines()


def picture(rows, above):
    """A mock Claude Code screen: a chat line, then the rows above the prompt box (plugin) or below it (status line)."""
    width = max(len(re.sub(r"\x1b\[\d+m", "", r)) for r in rows)
    w = max(900, 60 + int(CHAR * width))
    lines = [("text", "\x1b[2m● Done: the tests pass.\x1b[0m"), ("gap", "")]
    band = [("text", r) for r in rows]
    prompt = [("box", "")]
    lines += (band + prompt) if above else (prompt + band)
    h = 50 + LINE * (len(lines) + 1)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect width="%d" height="%d" rx="10" fill="#1e1f22"/>'
           '<circle cx="24" cy="22" r="6" fill="#ff5f56"/><circle cx="44" cy="22" r="6" fill="#ffbd2e"/>'
           '<circle cx="64" cy="22" r="6" fill="#27c93f"/>' % (w, h, w, h)]
    y = 64
    for kind, r in lines:
        if kind == "box":
            y += 6
            svg.append('<rect x="18" y="%d" width="%d" height="%d" rx="6" fill="none" stroke="#6b6b6b"/>' % (y - 20, w - 36, LINE + 6))
            svg.append('<text x="30" y="%d" font-family="Menlo,Monaco,monospace" font-size="17" fill="#e6e6e6">&gt; '
                       '<tspan fill="#7a7a7a">Try "fix the failing test"</tspan></text>' % (y + 2))
            y += LINE + 12
        elif kind == "text":
            dim = r.startswith("\x1b[2m")
            svg.append('<text x="24" y="%d" font-family="Menlo,Monaco,monospace" font-size="17" xml:space="preserve">%s</text>'
                       % (y, tspans(r.replace("\x1b[2m", ""), "#8a8a8a" if dim else "#e6e6e6")))
            y += LINE
        else:
            y += LINE // 2
    svg.append("</svg>")
    return "".join(svg), w, h


def main():
    docs = os.path.join(ROOT, "docs")
    for case in CASES:
        rows = rows_of(case)
        for layout, above in (("plugin", True), ("statusline", False)):
            svg, w, h = picture(rows, above)
            base = os.path.join(docs, "%s-%s" % (layout, case))
            open(base + ".svg", "w").write(svg)
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                            "--window-size=%d,%d" % (w, h), "--screenshot=" + base + ".png", "file://" + os.path.abspath(base + ".svg")],
                           capture_output=True)
            print("\n".join(re.sub(r"\x1b\[\d+m", "", r) for r in rows) if above else "", end="\n" if above else "")


if __name__ == "__main__":
    sys.exit(main())
