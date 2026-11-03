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

    def test_stale_reset(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 50, "resets_at": NOW - 10}}, NOW)
        self.assertIn("5h pace 0/0% ETA -/now", out)

    def test_bad_input_skipped(self):
        self.assertEqual(sl.pace_part({"five_hour": {"used_percentage": "x"}}, NOW), "")


GO_LABEL = "GLM5.3flash (Cloud, Go Plus, $ ЛУЧШЕЕ ОТНОШЕНИЕ ЛИМИТ/ЦЕНА, ≈360M вых.ток/мес, лимит $180 = ×4.5 к $40, для проверки)"
ZAI_LABEL = "GLM5.3flash (Cloud, z.ai Lite $18, ★ ЛУЧШЕЕ ОТНОШЕНИЕ ТОКЕНОВ/КРЕДИТ, ×3 к GLM5.3, ≈146–293M ток/нед при кэше 95%)"
STATE = {"subscription": {"5h": {"utilization": 0.3, "reset": NOW + 3600}},
         "plans": {"go": {"5h": {"utilization": 0.14, "reset": NOW + 3 * 3600},
                          "7d": {"utilization": 0.45, "reset": NOW + 6 * 86400},
                          "1mo": {"utilization": 0.73, "reset": NOW + 26 * 86400}}}}


class Plans(unittest.TestCase):
    def test_plan_of(self):
        self.assertEqual(sl.plan_of("glm-5.3-flash-cloud-opencode-go-direct", ""), "go")
        self.assertEqual(sl.plan_of("", GO_LABEL), "go")
        self.assertEqual(sl.plan_of("claude-opus-5-5", "Opus 5.5"), "claude")
        self.assertEqual(sl.plan_of("", "Claude haiku (~100 tok/s, Cloud, subscription, для быстрых задач)"), "claude")
        self.assertEqual(sl.plan_of("glm-5.3-flash-cloud-zai-direct", ZAI_LABEL), "")

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

    def test_claude_falls_back_to_subscription(self):
        self.assertEqual(sl.state_windows(STATE, "claude"), [("5h", 0.3, NOW + 3600)])
        self.assertEqual(sl.state_windows({}, "go"), [])




if __name__ == "__main__":
    unittest.main()
