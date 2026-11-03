import os, sys, time, unittest
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

    def test_stale_reset(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 50, "resets_at": NOW - 10}}, NOW)
        self.assertIn("5h pace 0/0% ETA -/now", out)

    def test_bad_input_skipped(self):
        self.assertEqual(sl.pace_part({"five_hour": {"used_percentage": "x"}}, NOW), "")


GO_LABEL = "GLM5.3flash (Cloud, Go Plus, $ ЛУЧШЕЕ ОТНОШЕНИЕ ЛИМИТ/ЦЕНА, ≈360M вых.ток/мес, лимит $180 = ×4.5 к $40, для проверки)"
ZAI_LABEL = "GLM5.3flash (Cloud, z.ai Lite $18, ★ ЛУЧШЕЕ ОТНОШЕНИЕ ТОКЕНОВ/КРЕДИТ, ×3 к GLM5.3, ≈146–293M ток/нед при кэше 95%)"
STATE = {
    "subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}},
    "plans": {
        "go": {
            "5h": {"utilization": 0.14, "reset": NOW + 3 * 3600},
            "7d": {"utilization": 0.45, "reset": NOW + 6 * 86400},
            "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400},
        },
        "zai": {
            "5h": {"utilization": 0.2, "reset": NOW + 2 * 3600},
            "7d": {"utilization": 0.5, "reset": NOW + 4 * 86400},
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

    def test_short_label(self):
        self.assertEqual(sl.short_label(GO_LABEL), "GLM5.3flash (Go Plus, ≈360M вых.ток/мес)")
        self.assertEqual(sl.short_label(ZAI_LABEL), "GLM5.3flash (z.ai Lite $18, ≈146–293M ток/нед при кэше 95%)")
        self.assertEqual(sl.short_label("Opus 5.5 (default)"), "Opus 5.5")
        self.assertEqual(sl.short_label("Opus"), "Opus")

    def test_go_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "go"), NOW)
        self.assertIn("5h pace 14/40%", out)
        self.assertIn("7d pace 45/14%", out)
        self.assertIn("1mo pace 73/13%", out)
        self.assertTrue(out.startswith(sl.GRN))                 # 5h on pace
        self.assertIn(sl.RED + "1mo pace", out)                  # 73% used at 13% of the month
        # Separator is now " · "
        self.assertIn(" · ", out)
        self.assertNotIn("; ", out)

    def test_zai_windows_from_state(self):
        out = sl.windows_part(sl.state_windows(STATE, "zai"), NOW)
        self.assertIn("5h pace 20/", out)
        self.assertIn("7d pace 50/", out)
        self.assertIn(" · ", out)

    def test_claude_falls_back_to_subscription(self):
        self.assertEqual(sl.state_windows(STATE, "claude"), [("5h", 0.3, NOW + 3600)])
        self.assertEqual(sl.state_windows({}, "go"), [])

    def test_stale_state_ignored(self):
        self.assertEqual(sl.state_windows(STALE_STATE, "go", NOW), [])
        # No updated key -> uses data (old router shape)
        old_shape = {"subscription": {"5h": {"utilization": 0.6, "reset": NOW + 3600}}}
        self.assertEqual(sl.state_windows(old_shape, "claude", NOW), [("5h", 0.6, NOW + 3600)])


class BuildRows(unittest.TestCase):
    def test_claude_only_engine_windows(self):
        snap_wins = [("5h", 0.6, NOW + 2 * 3600), ("7d", 0.4, NOW + 4 * 86400)]
        rows = sl.build_rows(snap_wins, "claude-opus-5-5", "Opus 5.5", "high", True, False, None, {}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("Opus 5.5 high", rows[0])
        self.assertIn("Claude", rows[0])
        self.assertIn("5h pace 60/", rows[0])
        self.assertIn("7d pace 40/", rows[0])
        # Claude label should be bold
        self.assertIn(sl.BLD + "Claude" + sl.RST, rows[0])

    def test_claude_fallback_to_state(self):
        snap_wins = []
        state = {"subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}}}
        rows = sl.build_rows(snap_wins, "claude-sonnet-4", "Sonnet 4", "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("Claude", rows[0])
        self.assertIn("5h pace 30/", rows[0])

    def test_claude_and_go_rows(self):
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
        self.assertEqual(len(rows), 2)
        # Row 1: head only (no Claude windows, but row 2 exists)
        self.assertIn("GLM5.3flash", rows[0])
        self.assertNotIn("Claude", rows[0])
        # Row 2: Go (bold because current plan)
        self.assertIn(sl.BLD + "Go" + sl.RST, rows[1])
        self.assertIn("5h pace 14/", rows[1])
        self.assertIn("7d pace 45/", rows[1])
        self.assertIn("1mo pace 73/", rows[1])
        # Go separator is " · "
        self.assertIn(" · ", rows[1])

    def test_claude_and_zai_rows(self):
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
        self.assertEqual(len(rows), 2)
        self.assertIn("z.ai", rows[1])
        self.assertIn(sl.BLD + "z.ai" + sl.RST, rows[1])

    def test_all_three_plans_go_current(self):
        snap_wins = [("5h", 0.3, NOW + 3600)]
        state = {
            "plans": {
                "go": {"5h": {"utilization": 0.14, "reset": NOW + 3 * 3600}},
                "zai": {"5h": {"utilization": 0.2, "reset": NOW + 2 * 3600}},
            },
        }
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, state, NOW)
        self.assertEqual(len(rows), 3)
        # Row 1: Claude from engine
        self.assertIn("Claude", rows[0])
        # Row 2: Go bold
        self.assertIn(sl.BLD + "Go" + sl.RST, rows[1])
        # Row 3: z.ai not bold
        self.assertIn("z.ai", rows[2])
        self.assertNotIn(sl.BLD + "z.ai" + sl.RST, rows[2])

    def test_no_data_show_context_false_empty(self):
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, False, None, {}, NOW)
        self.assertEqual(len(rows), 0)

    def test_no_data_show_context_true_shows_ctx(self):
        snap_wins = []
        rows = sl.build_rows(snap_wins, "gpt-4", "GPT-4", "", True, True, 34, {}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("ctx 34%", rows[0])

    def test_stale_state_ignored_in_rows(self):
        snap_wins = []
        rows = sl.build_rows(snap_wins, "glm-5.3-flash-cloud-opencode-go-direct", GO_LABEL, "", True, False, None, STALE_STATE, NOW)
        self.assertEqual(len(rows), 0)

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
        self.assertIn("Claude", out)
        self.assertIn("5h pace 60/", out)
        self.assertIn("7d pace 40/", out)
        self.assertIn(" · ", out)


if __name__ == "__main__":
    unittest.main()