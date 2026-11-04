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
GEMINI_LABEL = "Gemini 2.5 Pro (Cloud, ≈1M)"

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
        # New: gemini
        self.assertEqual(sl.plan_of("gemini-2.5-pro", ""), "gemini")
        self.assertEqual(sl.plan_of("", GEMINI_LABEL), "gemini")
        # gemini after openrouter: gemini via OpenRouter counts as openrouter
        self.assertEqual(sl.plan_of("openrouter-gemini-model", "Gemini (OpenRouter)"), "openrouter")
        self.assertEqual(sl.plan_of("gemini-openrouter", "Gemini"), "openrouter")

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
        self.assertEqual(len(rows), 2)  # head + Claude row
        # Row 0: head alone
        self.assertIn("Opus 5.5 high", rows[0])
        self.assertNotIn(" | ", rows[0])
        # Row 1: Claude row (no indent)
        self.assertIn("Claude", rows[1])
        self.assertIn("5h pace 60/", rows[1])
        self.assertIn("7d pace 40/", rows[1])
        # Claude label should be bold (current plan)
        self.assertIn(sl.BLD + "Claude" + sl.RST, rows[1])

    def test_claude_fallback_to_state(self):
        snap_wins = []
        state = {"subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}}}
        rows = sl.build_rows(snap_wins, "claude-sonnet-4", "Sonnet 4", "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)  # head + Claude row
        # Row 0: head
        self.assertIn("Sonnet 4", rows[0])
        # Row 1: Claude row
        self.assertIn("Claude", rows[1])
        self.assertIn("5h pace 30/", rows[1])

    def test_claude_and_go_rows(self):
        # When Claude has windows: head + Claude row + Go row
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
        self.assertEqual(len(rows), 3)  # head + Claude + Go
        # Row 0: head alone
        self.assertIn("GLM5.3flash", rows[0])
        self.assertNotIn(" | ", rows[0])
        # Row 1: Claude (not current plan, not bold)
        self.assertIn("Claude", rows[1])
        self.assertIn("5h pace 30/", rows[1])
        self.assertNotIn(sl.BLD + "Claude" + sl.RST, rows[1])
        # Row 2: Go (current plan, bold)
        self.assertIn("Go", rows[2])
        self.assertRegex(rows[2], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        self.assertIn("5h pace 14/", rows[2])
        self.assertIn("7d pace 45/", rows[2])
        self.assertIn("1mo pace 73/", rows[2])
        self.assertIn(" · ", rows[2])

    def test_no_claude_windows_go_gets_head(self):
        # When NO Claude windows but Go has windows: head + Go row
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
        self.assertEqual(len(rows), 2)  # head + Go row
        # Row 0: head alone
        self.assertIn("GLM5.3flash", rows[0])
        self.assertNotIn(" | ", rows[0])
        # Row 1: Go (current plan, bold)
        self.assertIn("Go", rows[1])
        self.assertRegex(rows[1], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        self.assertIn("5h pace 14/", rows[1])
        self.assertIn("7d pace 45/", rows[1])
        self.assertIn("1mo pace 73/", rows[1])

    def test_no_claude_windows_zai_gets_head(self):
        # When NO Claude windows but z.ai has windows: head + z.ai row
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
        self.assertEqual(len(rows), 2)  # head + z.ai row
        # Row 0: head alone
        self.assertIn("GLM5.3flash", rows[0])
        self.assertNotIn(" | ", rows[0])
        # Row 1: z.ai (current plan, bold)
        self.assertIn("z.ai", rows[1])
        self.assertRegex(rows[1], re.escape(sl.BLD) + r"z\.ai\s*" + re.escape(sl.RST))

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
        self.assertEqual(len(rows), 6)  # head + 5 plans
        # Row 0: head
        self.assertIn("GLM5.3flash", rows[0])
        self.assertNotIn(" | ", rows[0])
        # Row 1: Claude from engine
        self.assertIn("Claude", rows[1])
        # Row 2: Fable
        self.assertIn("Fable", rows[2])
        # Row 3: Go bold (current plan)
        self.assertRegex(rows[3], re.escape(sl.BLD) + r"Go\s*" + re.escape(sl.RST))
        # Row 4: z.ai not bold
        self.assertIn("z.ai", rows[4])
        self.assertNotRegex(rows[4], re.escape(sl.BLD) + r"z\.ai")
        # Row 5: OpenRouter
        self.assertIn("OpenRouter", rows[5])

    def test_no_data_show_context_false_returns_no_rows(self):
        # When no plan data at all but show_model=True and no ctx, returns empty (main() prints the head alone)
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, False, None, {}, NOW)
        self.assertEqual(rows, [])

    def test_no_data_show_context_true_shows_ctx_in_head(self):
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, True, 34, {}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("ctx 34%", rows[0])

    def test_stale_state_ignored_returns_no_rows(self):
        # Stale state ignored, no other data -> returns empty (main() prints the head alone)
        snap_wins = []
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, STALE_STATE, NOW)
        self.assertEqual(rows, [])

    def test_show_model_false_hides_head(self):
        snap_wins = [("5h", 0.3, NOW + 3600)]
        rows = sl.build_rows(snap_wins, "claude-opus-5-5", "Opus 5.5", "", False, False, None, {}, NOW)
        self.assertEqual(len(rows), 1)
        # When show_model=False and there are Claude windows, only Claude row (no head)
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
        # Output should have head on line 1, then plan rows
        lines = out.strip().split('\n')
        self.assertEqual(len(lines), 2)  # head + Claude row
        self.assertIn("Opus 5.5 high", lines[0])
        self.assertIn("ctx 45%", lines[0])
        self.assertIn("Claude", lines[1])
        self.assertIn("5h pace 60/", lines[1])
        self.assertIn("7d pace 40/", lines[1])
        self.assertIn(" · ", lines[1])

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
        self.assertEqual(len(rows), 3)  # head + Claude + Go
        row0 = rows[0]
        row1 = rows[1]  # Claude
        row2 = rows[2]  # Go
        # Row 0: head alone
        self.assertIn("GLM5.3flash", row0)
        self.assertNotIn(" | ", row0)
        # Row 1 (Claude): 5h, 7d
        self.assertIn("5h pace 60/", row1)
        self.assertIn("7d pace 40/", row1)
        # Row 2 (Go): missing 5h -> spaces, then 7d, 1mo
        self.assertIn("Go", row2)
        # The Go row should NOT have indent (new layout)
        self.assertFalse(row2.startswith(" " * 5))
        # Check alignment: Go's 7d should align with Claude's 7d
        self.assertIn("7d pace 45/", row2)
        self.assertIn("1mo pace 73/", row2)

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
        self.assertEqual(len(rows), 2)  # head + openrouter
        # Row 0: head
        self.assertIn("Model", rows[0])
        # Row 1: OpenRouter
        text = rows[1]
        # Order: 5h, 1d, 7d
        idx5h = text.index("5h pace")
        idx1d = text.index("1d pace")
        idx7d = text.index("7d pace")
        self.assertLess(idx5h, idx1d)
        self.assertLess(idx1d, idx7d)

    def test_ctx_in_head_not_at_end(self):
        snap_wins = [("5h", 0.6, NOW + 2 * 3600)]
        rows = sl.build_rows(snap_wins, "Opus 5.5", "Opus 5.5", "high", True, True, 34.7, {}, NOW)
        self.assertEqual(len(rows), 2)  # head + Claude
        # Row 0: head with ctx
        text = rows[0]
        self.assertIn("ctx 35%", text)
        self.assertNotIn(" | ", text)
        # ctx should be in head (before any plan)
        # Row 1: Claude with windows
        self.assertIn("5h pace 60/", rows[1])


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
        # Row 0: head
        self.assertTrue(plain[0].startswith("qwen-local-pool medium ctx 4%"))
        self.assertNotIn(" | ", plain[0])
        # Row 1: Claude
        self.assertTrue(plain[1].startswith("Claude"))
        # 7d pace position should be same across PLAN ROWS (skip head row 0)
        plan_rows = plain[1:]
        self.assertEqual(len({r.find("7d pace") for r in plan_rows}), 1)
        self.assertEqual(len({r.find("5h pace") for r in plan_rows if "5h pace" in r}), 1)
        # Row 3 (z.ai): no indent, 7d aligned (index 3 in plain = row 3, which is z.ai)
        self.assertTrue(plain[3].startswith("z.ai"))
        self.assertNotIn("·", plain[3])  # z.ai has no cell before 7d


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
        self.assertEqual(len(rows), 2)  # head + Claude
        plain_head = sl.re.sub(r"\x1b\[\d+m", "", rows[0])
        plain_claude = sl.re.sub(r"\x1b\[\d+m", "", rows[1])
        # Head alone
        self.assertTrue(plain_head.startswith("Opus 5.5 high ctx 4%"))
        self.assertNotIn(" | ", plain_head)
        # Claude row compact (no double spaces for alignment padding)
        self.assertTrue(plain_claude.startswith("Claude"))
        self.assertNotIn("  ", plain_claude)


class StatusAndGemini(unittest.TestCase):
    def test_gemini_plan_last_in_order(self):
        # gemini should be last in PLAN_ORDER
        snap_wins = [("5h", 0.3, NOW + 3600)]
        state = {
            "plans": {
                "fable": {"7d": {"utilization": 0.4, "reset": NOW + 4 * 86400}},
                "go": {"5h": {"utilization": 0.14, "reset": NOW + 3 * 3600}},
                "zai": {"5h": {"utilization": 0.2, "reset": NOW + 2 * 3600}},
                "openrouter": {"1d": {"utilization": 0.5, "reset": NOW + 86400}},
                "gemini": {"7d": {"utilization": 0.6, "reset": NOW + 5 * 86400}},
            },
        }
        rows = sl.build_rows(snap_wins, "gemini-2.5-pro", GEMINI_LABEL, "", True, False, None, state, NOW)
        # head + 6 plans = 7 rows
        self.assertEqual(len(rows), 7)
        # Row 6 should be Gemini (last)
        self.assertIn("Gemini", rows[6])
        # Gemini is current plan, bold
        self.assertRegex(rows[6], re.escape(sl.BLD) + r"Gemini\s*" + re.escape(sl.RST))

    def test_gemini_status_only_row(self):
        # A plan with only a status gets a row
        snap_wins = []
        state = {
            "plans": {
                "gemini": {"status": "ok"},
            },
        }
        rows = sl.build_rows(snap_wins, "gemini-2.5-pro", GEMINI_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)  # head + Gemini status row
        # Row 0: head
        self.assertIn("Gemini 2.5 Pro", rows[0])
        # Row 1: Gemini with status
        self.assertIn("Gemini", rows[1])
        self.assertIn(sl.GRN + "ok" + sl.RST, rows[1])  # green for "ok"

    def test_status_after_windows_with_dot_separator(self):
        # Status shown after windows with " · " separator
        snap_wins = [("5h", 0.3, NOW + 3600)]
        state = {
            "plans": {
                "claude": {"5h": {"utilization": 0.3, "reset": NOW + 3600}, "status": "slow 5m"},
            },
        }
        rows = sl.build_rows(snap_wins, "claude-opus-5-5", "Opus 5.5", "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)  # head + Claude
        # Row 1: Claude with status after windows
        self.assertIn("5h pace 30/", rows[1])
        self.assertIn(" · ", rows[1])
        self.assertIn(sl.YEL + "slow 5m" + sl.RST, rows[1])  # yellow for non-"ok"

    def test_status_colour_green_for_ok(self):
        snap_wins = []
        state = {"plans": {"go": {"status": "ok"}}}
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)
        self.assertIn(sl.GRN + "ok" + sl.RST, rows[1])

    def test_status_colour_yellow_for_non_ok(self):
        snap_wins = []
        state = {"plans": {"go": {"status": "slow 5m"}}}
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)
        self.assertIn(sl.YEL + "slow 5m" + sl.RST, rows[1])

    def test_status_control_chars_removed_trimmed_max_40(self):
        # Control chars removed, trimmed, max 40 chars
        snap_wins = []
        long_status = "x" * 50
        state = {"plans": {"go": {"status": "\x00slow\x1f 5m\x7f " + long_status}}}
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 2)
        # Should be trimmed to 40 chars, control chars removed
        self.assertIn("slow 5m " + "x" * 31, rows[1])  # "slow 5m " = 8 chars, 32 more = 40
        self.assertNotIn("\x00", rows[1])
        self.assertNotIn("\x1f", rows[1])
        self.assertNotIn("\x7f", rows[1])

    def test_plan_of_gemini_vs_openrouter_gemini(self):
        # Direct gemini -> gemini
        self.assertEqual(sl.plan_of("gemini-2.5-pro", ""), "gemini")
        # Gemini via OpenRouter -> openrouter (openrouter checked before gemini)
        self.assertEqual(sl.plan_of("openrouter-gemini-2.5", "Gemini (OpenRouter)"), "openrouter")
        self.assertEqual(sl.plan_of("gemini-model", "Model (OpenRouter)"), "openrouter")

    def test_single_plan_row_compact_no_double_spaces(self):
        # A single plan row (with head) should have no double spaces for alignment
        now = NOW
        rows = sl.build_rows([("5h", 0.07, now + 3 * 3600), ("7d", 0.23, now + 5 * 86400)], "claude-opus-5-5", "Opus 5.5",
                             "high", True, True, 4, {}, now)
        # 2 rows: head + 1 plan row
        self.assertEqual(len(rows), 2)
        for row in rows:
            plain = sl.re.sub(r"\x1b\[\d+m", "", row)
            self.assertNotIn("  ", plain)  # no double spaces


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


class SharedLayoutCases(unittest.TestCase):
    """The same cases run in the plugin (plugins/statusline-pace/tests/band.test.tsx): both must give the same rows.
    Times of day are masked (## / Www) so the rows do not depend on the time zone."""
    CASES = os.path.join(os.path.dirname(__file__), "..", "plugins", "statusline-pace", "tests", "layout-cases.ts")

    @staticmethod
    def mask(text):
        text = re.sub(r"\x1b\[\d+m", "", text)
        text = re.sub(r"\b(Sun|Mon|Tue|Wed|Thu|Fri|Sat)-", "Www-", text)
        text = re.sub(r"\b\d\d:\d\d\b", "##:##", text)
        return re.sub(r"\b\d\d\.\d\d\b", "##.##", text)

    def test_rows_match_fixture(self):
        with open(self.CASES, encoding="utf-8") as f:
            cases = json.loads(f.read().rsplit("\nexport default ", 1)[1])
        self.assertGreaterEqual(len(cases), 4)
        for c in cases:
            wins = [(e["kind"], e["used"], e["reset_ms"] / 1000) for e in c["engine"]]
            rows = sl.build_rows(wins, c["model_id"], c["label"], c["effort"], c["showModel"], c["showContext"],
                                 c["ctx"], c["state"] or {}, c["now_ms"] / 1000)
            with self.subTest(c["name"]):
                self.assertEqual([self.mask(r) for r in rows], c["rows"])


if __name__ == "__main__":
    unittest.main()

class Agents(unittest.TestCase):
    def test_row_counts_pairs_and_strips_prefixes(self):
        row = sl.agents_row([("worker-coder", "glm-5.3-flash"), ("Explore", None), ("Explore", None), ("worker-verifier", "claude-sonnet-5-5")])
        self.assertEqual(row, "agents coder:glm-5.3-flash, Explore:starting x2, verifier:sonnet-5-5")
        self.assertEqual(sl.agents_row([]), "")

    def test_running_subagents_from_transcripts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "sid", "subagents")
            os.makedirs(sub)
            msg = {"type": "assistant", "message": {"role": "assistant", "model": "glm-5.3-flash"}}
            with open(os.path.join(sub, "agent-a.jsonl"), "w") as f:
                f.write(json.dumps({"type": "user"}) + "\n" + json.dumps(msg) + "\n")
            with open(os.path.join(sub, "agent-a.meta.json"), "w") as f:
                json.dump({"agentType": "worker-coder"}, f)
            with open(os.path.join(sub, "agent-b.jsonl"), "w") as f:
                f.write(json.dumps({"type": "user"}) + "\n")
            old = os.path.join(sub, "agent-c.jsonl")
            with open(old, "w") as f:
                f.write(json.dumps(msg) + "\n")
            os.utime(old, (time.time() - 600, time.time() - 600))
            inp = {"transcript_path": os.path.join(d, "sid.jsonl"), "session_id": "sid"}
            self.assertEqual(sl.subagents(inp, time.time()), [("worker-coder", "glm-5.3-flash"), ("agent", None)])
            self.assertEqual(sl.subagents({}, time.time()), [])

    def test_last_line_only_while_agents_run(self):
        import subprocess
        out = subprocess.run([sys.executable, sl.__file__], input=json.dumps({"model": {"display_name": "Opus"}}),
                             capture_output=True, text=True).stdout
        self.assertNotIn("agents", out)
