#!/usr/bin/env python3
"""Build a windows file for statusline.py (PACE_STATE_FILE).

Usage:
  make_windows.py --plan go 5h=14%@2026-11-04T18:00 7d=45%@2026-11-09T03:00 --plan gemini status=ok -o PATH

Each --plan NAME takes items KIND=VALUE@RESET (KIND: 5h, 1d, 7d, 1mo; VALUE: `14%` or `0.14`; RESET: ISO-8601, naive
= local time, or epoch seconds) and `status=TEXT`. Output: {"updated": <now s>, "plans": {...}}. No -o or `-o -` = stdout.
A bad input gives exit code 2 and a one-line message. Stdlib only.
"""
import argparse, datetime, json, math, os, sys, time

KINDS = ("5h", "1d", "7d", "1mo")
PLANS = ("claude", "fable", "go", "gofree", "zai", "openrouter", "gemini")


class BadInput(Exception):
    pass


def parse_value(text):
    try:
        v = float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except ValueError:
        raise BadInput("bad value %r (use 14%% or 0.14)" % text)
    if not math.isfinite(v) or not 0 <= v <= 1:
        raise BadInput("value %r is outside 0..1" % text)
    return v


def parse_reset(text):
    try:
        v = float(text)
        if not math.isfinite(v):
            raise ValueError
        return v
    except ValueError:
        pass
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()  # naive = local time
    except ValueError:
        raise BadInput("bad reset %r (use ISO-8601 or epoch seconds)" % text)


def parse_item(item):
    key, sep, rest = item.partition("=")
    if not sep:
        raise BadInput("bad item %r (use KIND=VALUE@RESET or status=TEXT)" % item)
    if key == "status":
        return key, rest
    if key not in KINDS:
        raise BadInput("unknown kind %r (use %s)" % (key, ", ".join(KINDS)))
    value, at, reset = rest.partition("@")
    if not at:
        raise BadInput("item %r has no @RESET" % item)
    return key, {"utilization": parse_value(value), "reset": parse_reset(reset)}


def build(groups, now):
    plans = {}
    for name, items in groups:
        if name not in PLANS:
            raise BadInput("unknown plan %r (use %s)" % (name, ", ".join(PLANS)))
        if not items:
            raise BadInput("plan %r has no items" % name)
        plans[name] = dict(parse_item(i) for i in items)
    if not plans:
        raise BadInput("no --plan given")
    return {"updated": int(now), "plans": plans}


def split_args(argv):
    """[--plan NAME item...]... -> ([(name, [items])], output path or None)."""
    groups, out, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "--output"):
            if i + 1 >= len(argv):
                raise BadInput("%s needs a path" % a)
            out, i = argv[i + 1], i + 2
        elif a == "--plan":
            if i + 1 >= len(argv):
                raise BadInput("--plan needs a name")
            groups.append((argv[i + 1], []))
            i += 2
        elif groups:
            groups[-1][1].append(a)
            i += 1
        else:
            raise BadInput("item %r comes before any --plan" % a)
    return groups, out


def write_atomic(path, text):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv in (["-h"], ["--help"]):
        sys.stdout.write(__doc__)
        return 0
    try:
        groups, out = split_args(argv)
        text = json.dumps(build(groups, time.time()), indent=2) + "\n"
        if out in (None, "-"):
            sys.stdout.write(text)
        else:
            try:
                write_atomic(os.path.expanduser(out), text)
            except OSError as e:
                raise BadInput("cannot write %s: %s" % (out, e.strerror or e))
    except BadInput as e:
        sys.stderr.write("make_windows: %s\n" % e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
