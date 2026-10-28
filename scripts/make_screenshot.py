#!/usr/bin/env python3
"""Regenerate docs/statusline.svg and docs/statusline.png from examples/*.json (needs Google Chrome for the PNG).

Run from the repo root: python3 scripts/make_screenshot.py
"""
import html, os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
COLS = {"31": "#ff6b6b", "32": "#6bdc8b", "33": "#f5c451"}
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def tspans(line):
    res, cur = [], "#e6e6e6"
    for tok in re.split(r"(\x1b\[\d+m)", line):
        m = re.match(r"\x1b\[(\d+)m", tok)
        if m:
            cur = COLS.get(m.group(1), "#e6e6e6")
        elif tok:
            res.append('<tspan fill="%s">%s</tspan>' % (cur, html.escape(tok)))
    return "".join(res)


def main():
    out = subprocess.run(["sh", os.path.join(ROOT, "examples", "run.sh")], capture_output=True, text=True, check=True).stdout
    rows = [l for l in out.splitlines() if l]
    h = 70 + 34 * len(rows)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="%d"><rect width="1300" height="%d" rx="10" fill="#1e1f22"/>'
           '<circle cx="24" cy="22" r="6" fill="#ff5f56"/><circle cx="44" cy="22" r="6" fill="#ffbd2e"/><circle cx="64" cy="22" r="6" fill="#27c93f"/>' % (h, h)]
    for i, r in enumerate(rows):
        svg.append('<text x="24" y="%d" font-family="Menlo,Monaco,monospace" font-size="17" xml:space="preserve">%s</text>' % (70 + 34 * i, tspans(r)))
    svg.append("</svg>")
    docs = os.path.join(ROOT, "docs")
    open(os.path.join(docs, "statusline.svg"), "w").write("".join(svg))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                    "--window-size=1300,%d" % h, "--screenshot=" + os.path.join(docs, "statusline.png"),
                    "file://" + os.path.abspath(os.path.join(docs, "statusline.svg"))], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
