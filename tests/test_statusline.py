import json, os, re, sys, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import statusline as sl

NOW = 1_800_000_000.0


class Eta(unittest.TestCase):
    def test_on_formula(self):  # 60% used after 40% of 5h elapsed -> 100% after 1h20m more
        self.assertEqual(sl.eta("5h", 0.6, 0.4, NOW, NOW + 3 * 3600), sl.fmt("5h", NOW + 4800))

    def test_zero_use(self):
        self.assertEqual(sl.eta("5h", 0.0, 0.4, NOW, NOW + 3600), "-")

    def test_safe_before_reset(self):
        self.assertEqual(sl.eta("5h", 0.05, 0.6, NOW, NOW + 3600), "-")

    def test_full(self):
        self.assertEqual(sl.eta("5h", 1.2, 0.5, NOW, NOW + 3600), "now")

    def test_iso_reset(self):
        self.assertEqual(sl.epoch("2027-01-15T08:00:00Z"), 1800000000.0)

    def test_full_without_elapsed(self):
        self.assertEqual(sl.eta("5h", 1.0, 0.0, NOW, NOW + 5 * 3600), "now")

    def test_almost_full_not_rounded_up(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 99.6, "resets_at": NOW + 9000}}, NOW)
        self.assertIn("5h pace 99/", out)

    def test_iso_end_to_end(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 60, "resets_at": "2027-01-15T08:00:00Z"}}, 1800000000.0 - 3 * 3600)
        self.assertIn("5h pace 60/40%", out)

    def test_integer_percent_not_off_by_one(self):
        for pct in (29, 57, 58):
            out = sl.pace_part({"five_hour": {"used_percentage": pct, "resets_at": NOW + 9000}}, NOW)
            self.assertIn("5h pace %d/" % pct, out)

    def test_colours(self):  # green on pace, red off pace
        rl = lambda u, r: {"five_hour": {"used_percentage": u, "resets_at": NOW + r}}
        self.assertTrue(sl.pace_part(rl(60, 3 * 3600), NOW).startswith(sl.GRN))   # 60% at 40% elapsed: under 1.5x
        self.assertTrue(sl.pace_part(rl(65, 3 * 3600), NOW).startswith(sl.RED))   # over 1.5x elapsed
        self.assertTrue(sl.pace_part(rl(80, 600), NOW).startswith(sl.RED))        # over the 75% cap
        self.assertTrue(sl.pace_part(rl(5, 3600), NOW).startswith(sl.GRN))
        self.assertTrue(sl.pace_part(rl(100, 3600), NOW).startswith(sl.RED))
        self.assertTrue(sl.pace_part(rl(50, -10), NOW).startswith(sl.GRN))

    def test_long_windows_off_pace(self):
        self.assertFalse(sl.off_pace("7d", 0.45, 0.42))
        self.assertTrue(sl.off_pace("7d", 0.48, 0.42))
        self.assertTrue(sl.off_pace("1mo", 0.73, 0.13))
        # New hard cap 90%
        self.assertTrue(sl.off_pace("7d", 0.92, 0.95))
        self.assertFalse(sl.off_pace("7d", 0.88, 0.95))
        self.assertTrue(sl.off_pace("1mo", 0.91, 0.5))
        # 0.89 > 0.5 + 0.05 = 0.55, so off-pace (lead by 5pp rule still applies below 90%)
        self.assertTrue(sl.off_pace("1mo", 0.89, 0.5))
        self.assertFalse(sl.off_pace("1mo", 0.54, 0.5))

    def test_1d_off_pace_same_as_long_windows(self):
        self.assertFalse(sl.off_pace("1d", 0.45, 0.42))
        self.assertTrue(sl.off_pace("1d", 0.48, 0.42))
        self.assertTrue(sl.off_pace("1d", 0.92, 0.95))
        self.assertFalse(sl.off_pace("1d", 0.88, 0.95))

    def test_stale_reset(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 50, "resets_at": NOW - 10}}, NOW)
        self.assertIn("5h pace 0/0% ETA -/now", out)

    def test_bad_input_skipped(self):
        self.assertEqual(sl.pace_part({"five_hour": {"used_percentage": "x"}}, NOW), "")

    def test_fmt_1d_returns_hhmm(self):
        # 1d uses HH:MM like 5h
        ms = time.mktime(time.strptime("2027-01-15 14:30", "%Y-%m-%d %H:%M"))
        self.assertEqual(sl.fmt("1d", ms), "14:30")

    def test_fmt_7d_uses_fixed_english_weekday(self):
        # Use a timestamp that produces a known weekday in local time
        # Just verify the format uses English 3-letter weekdays (not locale-dependent)
        ms = 1800271920  # 2027-01-15 08:52:00 UTC
        out = sl.fmt("7d", ms)
        self.assertRegex(out, r"^(Sun|Mon|Tue|Wed|Thu|Fri|Sat)-\d{2}:\d{2}$")


GO_LABEL = "GLM5.3flash (Cloud, Go Plus, $ ЛУЧШЕЕ ОТНОШЕНИЕ ЛИМИТ/ЦЕНА, ≈360M вых.ток/мес, лимит $180 = ×4.5 к $40, для проверки)"
ZAI_LABEL = "GLM5.3flash (Cloud, z.ai Lite $18, ★ ЛУЧШЕЕ ОТНОШЕНИЕ ТОКЕНОВ/КРЕДИТ, ×3 к GLM5.3, ≈146–293M ток/нед при кэше 95%)"
FABLE_LABEL = "Model (Fable, Cloud, ≈500M)"
OPENROUTER_LABEL = "Model (OpenRouter, free)"

STATE = {
    "subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}},
    "plans": {
        "fable": {"7d": {"utilization": 0.4, "reset": NOW + 4 * 86400}},
        "go": {
            "5h": {"utilization": 0.14, "reset": NOW + 3 * 3600},
            "7d": {"utilization": 0.45, "reset": NOW + 6 * 86400},
            "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400},
        },
        "zai": {
            "5h": {"utilization": 0.2, "reset": NOW + 2 * 3600},
            "7d": {"utilization": 0.5, "reset": NOW + 4 * 86400},
        },
        "openrouter": {
            "1d": {"utilization": 0.5, "reset": NOW + 86400},
            "7d": {"utilization": 0.3, "reset": NOW + 4 * 86400},
        },
    },
}

STALE_STATE = {
    "updated": NOW - 7 * 3600,  # 7 hours ago
    "plans": {
        "go": {"5h": {"utilization": 0.14, "reset": NOW + 3 * 3600}},
    },
}


class Plans(unittest.TestCase):
    def test_plan_of(self):
        self.assertEqual(sl.plan_of("glm-5.3-flash-cloud-opencode-go-direct", ""), "go")
        self.assertEqual(sl.plan_of("", GO_LABEL), "go")
        self.assertEqual(sl.plan_of("claude-opus-5-5", "Opus 5.5"), "claude")
        self.assertEqual(sl.plan_of("", "Claude haiku (~100 tok/s, Cloud, subscription, для быстрых задач)"), "claude")
        self.assertEqual(sl.plan_of("glm-5.3-flash-cloud-zai-direct", ZAI_LABEL), "zai")
        self.assertEqual(sl.plan_of("", "GLM (z.ai Lite $18)"), "zai")
        self.assertEqual(sl.plan_of("GLM (Go Plus, z.ai)", "GLM (Go Plus, z.ai)"), "go")  # Go checked first
        self.assertEqual(sl.plan_of("gpt-4", ""), "")
        # New: fable and openrouter
        self.assertEqual(sl.plan_of("fable-model-v1", ""), "fable")
        self.assertEqual(sl.plan_of("", "Model (Fable, Cloud)"), "fable")
        self.assertEqual(sl.plan_of("claude-fable-model", "Claude Fable (Fable)"), "fable")  # fable before claude
        self.assertEqual(sl.plan_of("openrouter-model-v1", ""), "openrouter")
        self.assertEqual(sl.plan_of("", "Model (OpenRouter, free)"), "openrouter")
        self.assertEqual(sl.plan_of("claude-openrouter-model", "Claude (OpenRouter)"), "openrouter")  # openrouter before claude

    def test_short_label(self):
        self.assertEqual(sl.short_label(GO_LABEL), "GLM5.3flash (Go Plus, ≈360M вых.ток/мес)")
        self.assertEqual(sl.short_label(ZAI_LABEL), "GLM5.3flash (z.ai Lite $18, ≈146–293M ток/нед при кэше 95%)")
        self.assertEqual(sl.short_label("Opus 5.5 (default)"), "Opus 5.5")
        self.assertEqual(sl.short_label("Opus"), "Opus")
        self.assertEqual(sl.short_label(FABLE_LABEL), "Model (Fable, ≈500M)")
        self.assertEqual(sl.short_label(OPENROUTER_LABEL), "Model (OpenRouter)")

    def test_fable_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "fable"), NOW)
        self.assertIn("7d pace 40/", out)

    def test_go_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "go"), NOW)
        self.assertIn("5h pace 14/40%", out)
        self.assertIn("7d pace 45/14%", out)
        self.assertIn("1mo pace 73/13%", out)
        self.assertTrue(out.startswith(sl.GRN))                 # 5h on pace
        self.assertIn(sl.RED + "1mo pace", out)                  # 73% used at 13% of the month
        self.assertIn(" · ", out)
        self.assertNotIn("; ", out)

    def test_zai_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "zai"), NOW)
        self.assertIn("5h pace 20/", out)
        self.assertIn("7d pace 50/", out)
        self.assertIn(" · ", out)

    def test_openrouter_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "openrouter"), NOW)
        self.assertIn("1d pace 50/", out)
        self.assertIn("7d pace 30/", out)
        self.assertIn(" · ", out)

    def test_claude_falls_back_to_subscription(self):
        self.assertEqual(sl.state_windows(STATE, "claude"), [("5h", 0.3, NOW + 3600)])
        self.assertEqual(sl.state_windows({}, "go"), [])

    def test_stale_state_ignored(self):
        self.assertEqual(sl.state_windows(STALE_STATE, "go", NOW), [])
        # No updated key -> uses data (old router shape)
        old_shape = {"subscription": {"5h": {"utilization": 0.6, "reset": NOW + 3600}}}
        self.assertEqual(sl.state_windows(old_shape, "claude", NOW), [("5h", 0.6, NOW + 3600)])

    def test_empty_claude_plan_falls_back_to_subscription(self):
        now = time.time()
        state = {"plans": {"claude": {}}, "subscription": {"5h": {"utilization": 0.2, "reset": now + 60}}}
        self.assertEqual(len(sl.state_windows(state, "claude", now)), 1)


class BuildRows(unittest.TestCase):
    def test_claude_only_engine_windows(self):
        snap_wins = [("5h", 0.6, NOW + 2 * 3600), ("7d", 0.4, NOW + 4 * 86400)]
        rows = sl.build_rows(snap_wins, "claude-opus-5-5", "Opus 5.5", "high", True, False, None, {}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("Opus 5.5 high", rows[0])
        self.assertIn("Claude", rows[0])
        self.assertIn("5h pace 60/", rows[0])
        self.assertIn("7d pace 40/", rows[0])
        # Claude label should be bold (padded)
        self.assertIn(sl.BLD + "Claude" + sl.RST, rows[0])

    def test_claude_fallback_to_state(self):
        snap_wins = []
        state = {"subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}}}
        rows = sl.build_rows(snap_wins, "claude-sonnet-4", "Sonnet 4", "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("Claude", rows[0])
        self.assertIn("5h pace 30/", rows[0])

    def test_claude_and_go_rows(self):
        # When Claude has windows: 2 rows (Claude with head, Go indented)
        snap_wins = [("5h", 0.3, NOW + 3600)]
        state = {
            "plans": {
                "go": {
                    "5h": {"utilization": 0.14, "reset": NOW + 3 * 3600},
                    "7d": {"utilization": 0.45, "reset": NOW + 6 * 86400},
                    "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400},
                },
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)
        # Row 1: head + Claude
        self.assertIn("GLM5.3flash", rows[0])
        self.assertIn("Claude", rows[0])
        self.assertIn("5h pace 30/", rows[0])
        # Row 2: Go indented
        self.assertIn("Go", rows[1])
        # Go is current plan, bold (with padding) - check for bold start before "Go" and reset after
        self.assertRegex(rows[1], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        self.assertIn("5h pace 14/", rows[1])
        self.assertIn("7d pace 45/", rows[1])
        self.assertIn("1mo pace 73/", rows[1])
        self.assertIn(" · ", rows[1])

    def test_no_claude_windows_go_gets_head(self):
        # When NO Claude windows but Go has windows: 1 row (head + Go)
        snap_wins = []
        state = {
            "plans": {
                "go": {
                    "5h": {"utilization": 0.14, "reset": NOW + 3 * 3600},
                    "7d": {"utilization": 0.45, "reset": NOW + 6 * 86400},
                    "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400},
                },
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 1)
        # Single row: head + Go
        self.assertIn("GLM5.3flash", rows[0])
        self.assertIn("Go", rows[0])
        # Go is current plan, bold (with padding)
        self.assertRegex(rows[0], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        self.assertIn("5h pace 14/", rows[0])
        self.assertIn("7d pace 45/", rows[0])
        self.assertIn("1mo pace 73/", rows[0])

    def test_no_claude_windows_zai_gets_head(self):
        # When NO Claude windows but z.ai has windows: 1 row (head + z.ai)
        snap_wins = []
        state = {
            "plans": {
                "zai": {
                    "5h": {"utilization": 0.2, "reset": NOW + 2 * 3600},
                    "7d": {"utilization": 0.5, "reset": NOW + 4 * 86400},
                },
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-zai-direct", ZAI_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("z.ai", rows[0])
        self.assertRegex(rows[0], re.escape(sl.BLD) + r"z\.ai\s*" + re.escape(sl.RST))

    def test_all_five_plans_go_current(self):
        snap_wins = [("5h", 0.3, NOW + 3600)]
        state = {
            "plans": {
                "fable": {"7d": {"utilization": 0.4, "reset": NOW + 4 * 86400}},
                "go": {"5h": {"utilization": 0.14, "reset": NOW + 3 * 3600}},
                "zai": {"5h": {"utilization": 0.2, "reset": NOW + 2 * 3600}},
                "openrouter": {"1d": {"utilization": 0.5, "reset": NOW + 86400}},
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 5)
        # Row 1: Claude from engine
        self.assertIn("Claude", rows[0])
        # Row 2: Fable
        self.assertIn("Fable", rows[1])
        # Row 3: Go bold (with padding)
        self.assertRegex(rows[2], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        # Row 4: z.ai not bold
        self.assertIn("z.ai", rows[3])
        # Check z.ai is not bold (no BLD before it or RST after it in the label position)
        self.assertNotRegex(rows[3], re.escape(sl.BLD) + r"z\.ai")
        # Row 5: OpenRouter
        self.assertIn("OpenRouter", rows[4])

    def test_no_data_show_context_false_returns_no_rows(self):
        # When no plan data at all but show_model=True, returns head
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, False, None, {}, NOW)
        self.assertEqual(rows, [])  # no plan data and no ctx: no rows; main() prints the head alone

    def test_no_data_show_context_true_shows_ctx_in_head(self):
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, True, 34, {}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("ctx 34%", rows[0])

    def test_stale_state_ignored_returns_no_rows(self):
        # Stale state ignored, no other data -> returns head (show_model=True)
        snap_wins = []
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, STALE_STATE, NOW)
        self.assertEqual(rows, [])  # no plan data and no ctx: no rows; main() prints the head alone

    def test_show_model_false_hides_head(self):
        snap_wins = [("5h", 0.3, NOW + 3600)]
        rows = sl.build_rows(snap_wins, "claude-opus-5-5", "Opus 5.5", "", False, False, None, {}, NOW)
        self.assertEqual(len(rows), 1)
        # When show_model=False and there are Claude windows, row starts with bold "Claude" (no head, no separator)
        self.assertIn(sl.BLD + "Claude" + sl.RST, rows[0])
        self.assertIn("5h pace 30/", rows[0])

    def test_main_output_format(self):
        # Test the full main() flow via subprocess-like call
        import io, json
        inp = {
            "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
            "effort": {"level": "high"},
            "rate_limits": {
                "five_hour": {"used_percentage": 60, "resets_at": NOW + 3 * 3600},
                "seven_day": {"used_percentage": 40, "resets_at": NOW + 4 * 86400},
            },
            "context_window": {"used_percentage": 45},
        }
        stdin = io.StringIO(json.dumps(inp))
        stdout = io.StringIO()
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = stdin, stdout
        try:
            sl.main()
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        out = stdout.getvalue()
        self.assertIn("Opus 5.5 high", out)
        self.assertIn("ctx 45%", out)
        self.assertIn("Claude", out)
        self.assertIn("5h pace 60/", out)
        self.assertIn("7d pace 40/", out)
        self.assertIn(" · ", out)

    def test_aligned_columns_with_missing_kind(self):
        # Claude has 5h and 7d; Go has only 7d and 1mo (missing 5h)
        snap_wins = [("5h", 0.6, NOW + 2 * 3600), ("7d", 0.4, NOW + 4 * 86400)]
        state = {
            "plans": {
                "go": {
                    "7d": {"utilization": 0.45, "reset": NOW + 5 * 86400},
                    "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400},
                },
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)
        row0 = rows[0]
        row1 = rows[1]
        # Both rows should have same column structure
        # Row 1 (Claude): 5h, 7d
        self.assertIn("5h pace 60/", row0)
        self.assertIn("7d pace 40/", row0)
        # Row 2 (Go): missing 5h -> spaces, then 7d, 1mo
        self.assertIn("Go", row1)
        # The Go row should have indent matching head prefix length
        head_prefix = "GLM5.3flash (Go Plus, ≈360M вых.ток/мес) | "
        self.assertTrue(row1.startswith(" " * len(head_prefix)))
        # Check alignment: Go's 7d should align with Claude's 7d
        self.assertIn("7d pace 45/", row1)
        self.assertIn("1mo pace 73/", row1)

    def test_1d_kind_appears_between_5h_and_7d(self):
        snap_wins = []
        state = {
            "plans": {
                "openrouter": {
                    "5h": {"utilization": 0.1, "reset": NOW + 3600},
                    "1d": {"utilization": 0.5, "reset": NOW + 86400},
                    "7d": {"utilization": 0.3, "reset": NOW + 4 * 86400},
                },
            },
        }
        rows = sl.build_rows(snap_wins, "model (OpenRouter)", OPENROUTER_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 1)
        text = rows[0]
        # Order: 5h, 1d, 7d
        idx5h = text.index("5h pace")
        idx1d = text.index("1d pace")
        idx7d = text.index("7d pace")
        self.assertLess(idx5h, idx1d)
        self.assertLess(idx1d, idx7d)

    def test_ctx_in_head_not_at_end(self):
        snap_wins = [("5h", 0.6, NOW + 2 * 3600)]
        rows = sl.build_rows(snap_wins, "Opus 5.5", "Opus 5.5", "high", True, True, 34.7, {}, NOW)
        self.assertEqual(len(rows), 1)
        text = rows[0]
        # ctx should be in head (before the | separator)
        ctx_pos = text.index("ctx 35%")
        sep_pos = text.index(" | ")
        self.assertLess(ctx_pos, sep_pos)


class BadInput(unittest.TestCase):
    def test_nan_window_dropped_returns_no_rows(self):
        # NaN window dropped, no plan data -> returns head (show_model=True)
        state = {"plans": {"go": {"5h": {"utilization": float("nan"), "reset": 1}}}}
        self.assertEqual(sl.state_windows(state, "go"), [])
        rows = sl.build_rows([], "", "Opus", "", True, False, None, state, time.time())
        self.assertEqual(rows, [])  # no plan data and no ctx: no rows; main() prints the head alone

    def test_negative_used_clamped(self):
        rate = {"five_hour": {"used_percentage": -5, "resets_at": time.time() + 3600}}
        self.assertEqual(sl.rate_windows(rate)[0][1], 0.0)


class Alignment(unittest.TestCase):
    def test_columns_line_up_across_rows(self):
        now = NOW
        state = {"plans": {
            "go": {"5h": {"utilization": 0.0, "reset": now + 4 * 3600}, "7d": {"utilization": 1.0, "reset": now + 4 * 86400},
                   "1mo": {"utilization": 1.0, "reset": now + 25 * 86400}},
            "zai": {"7d": {"utilization": 0.93, "reset": now + 2 * 86400}},
            "openrouter": {"1d": {"utilization": 0.2, "reset": now + 10 * 3600}, "7d": {"utilization": 0.0, "reset": now + 5 * 86400}},
        }}
        rows = sl.build_rows([("5h", 0.07, now + 3 * 3600), ("7d", 0.23, now + 5 * 86400)], "qwen-local-pool", "qwen-local-pool",
                             "medium", True, True, 4, state, now)
        plain = [sl.re.sub(r"\x1b\[\d+m", "", r) for r in rows]
        self.assertTrue(plain[0].startswith("qwen-local-pool medium ctx 4% | Claude     5h pace 7/"))
        self.assertEqual(len({r.find("7d pace") for r in plain}), 1)
        self.assertEqual(len({r.find("5h pace") for r in plain if "5h pace" in r}), 1)
        self.assertTrue(plain[2].startswith(" " * len("qwen-local-pool medium ctx 4% | ") + "z.ai       "))
        self.assertNotIn("·", plain[2])  # z.ai has no cell before 7d


USAGE = {
    "five_hour": {"utilization": 15.0, "resets_at": "2026-11-04T11:00:00.110743+00:00"},
    "seven_day": {"utilization": 24.0, "resets_at": "2026-11-10T05:00:00.110770+00:00"},
    "seven_day_opus": None,
    "limits": [
        {"kind": "session", "percent": 15, "resets_at": "2026-11-04T11:00:00+00:00", "scope": None},
        {"kind": "weekly_scoped", "percent": 31, "resets_at": "2026-11-10T05:00:00.111041+00:00",
         "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None}},
    ],
}


class CompactSingleRow(unittest.TestCase):
    def test_one_row_has_no_alignment_padding(self):
        now = NOW
        rows = sl.build_rows([("5h", 0.07, now + 3 * 3600), ("7d", 0.23, now + 5 * 86400)], "claude-opus-5-5", "Opus 5.5",
                             "high", True, True, 4, {}, now)
        plain = sl.re.sub(r"\x1b\[\d+m", "", rows[0])
        self.assertEqual(len(rows), 1)
        self.assertTrue(plain.startswith("Opus 5.5 high ctx 4% | Claude 5h pace 7/"))
        self.assertNotIn("  ", plain)


class Weekday(unittest.TestCase):
    def test_7d_weekday_matches_the_date(self):
        ts = time.mktime((2027, 1, 15, 8, 52, 0, 0, 0, -1))  # a Friday, local time
        self.assertEqual(sl.fmt("7d", ts), "Fri-08:52")


class OAuth(unittest.TestCase):
    def test_plans_from_usage_endpoint(self):
        p = sl.oauth_plans(USAGE)
        self.assertEqual(sorted(p), ["claude", "fable"])
        self.assertEqual(p["claude"]["5h"]["utilization"], 0.15)
        self.assertEqual(p["fable"]["7d"]["utilization"], 0.31)

    def test_junk_gives_no_plans(self):
        self.assertEqual(sl.oauth_plans(None), {})
        self.assertEqual(sl.oauth_plans({"five_hour": {"utilization": "x"}, "limits": "no"}), {})

    def test_merge_over_stale_file(self):
        now = 1793800000.0
        stale = {"updated": now - 30000, "plans": {"go": {"7d": {"utilization": 0.5, "reset": now + 3600}}}}
        state = sl.merge_state(stale, sl.oauth_plans(USAGE), now)
        self.assertEqual(sl.state_windows(state, "go", now), [])
        self.assertEqual(sl.state_windows(state, "fable", now)[0][1], 0.31)

    def _run(self, answer, now, cache=None):
        import io, tempfile
        d = tempfile.mkdtemp()
        saved = (sl.OAUTH_CACHE, sl.oauth_token, sl.urllib.request.build_opener)
        sl.OAUTH_CACHE = os.path.join(d, "c.json")
        if cache is not None:
            with open(sl.OAUTH_CACHE, "w") as f:
                json.dump(cache, f)
        sl.oauth_token = lambda: "test-token"

        class Opener:
            def open(self, req, timeout=3):
                if isinstance(answer, Exception):
                    raise answer
                return io.BytesIO(json.dumps(answer).encode())
        sl.urllib.request.build_opener = lambda *h: Opener()
        os.environ["PACE_OAUTH"] = "1"
        try:
            plans = sl.read_oauth(now)
            with open(sl.OAUTH_CACHE) as f:
                raw = f.read()
            mode = os.stat(sl.OAUTH_CACHE).st_mode & 0o777
            return plans, raw, mode
        finally:
            os.environ.pop("PACE_OAUTH", None)
            sl.OAUTH_CACHE, sl.oauth_token, sl.urllib.request.build_opener = saved

    def test_fresh_answer_cached_without_token(self):
        plans, raw, mode = self._run(USAGE, 1000.0)
        self.assertEqual(plans["fable"]["7d"]["utilization"], 0.31)
        self.assertNotIn("test-token", raw)
        self.assertEqual(mode, 0o600)

    def test_failure_keeps_last_good_plans_with_their_age(self):
        good = sl.oauth_plans(USAGE)
        plans, raw, _ = self._run(OSError("down"), 2000.0, {"at": 1000.0, "got": 1000.0, "plans": good})
        self.assertEqual(plans, good)
        self.assertEqual(json.loads(raw)["got"], 1000.0)

    def test_empty_answer_does_not_erase_plans(self):
        good = sl.oauth_plans(USAGE)
        plans, _, _ = self._run({}, 2000.0, {"at": 1000.0, "got": 1000.0, "plans": good})
        self.assertEqual(plans, good)

    def test_old_plans_expire(self):
        good = sl.oauth_plans(USAGE)
        plans, _, _ = self._run(OSError("down"), 1000.0 + sl.STALE_THRESHOLD_S + 1, {"at": 1000.0, "got": 1000.0, "plans": good})
        self.assertEqual(plans, {})

    def test_off_by_default(self):
        os.environ.pop("PACE_OAUTH", None)
        self.assertEqual(sl.read_oauth(time.time()), {})


if __name__ == "__main__":
    unittest.main()