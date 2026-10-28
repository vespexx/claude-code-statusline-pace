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

    def test_colours(self):
        rl = lambda u, r: {"five_hour": {"used_percentage": u, "resets_at": NOW + r}}
        self.assertTrue(sl.pace_part(rl(60, 3 * 3600), NOW).startswith(sl.YEL))
        self.assertTrue(sl.pace_part(rl(5, 3600), NOW).startswith(sl.GRN))
        self.assertTrue(sl.pace_part(rl(100, 3600), NOW).startswith(sl.RED))
        self.assertTrue(sl.pace_part(rl(50, -10), NOW).startswith(sl.GRN))

    def test_stale_reset(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 50, "resets_at": NOW - 10}}, NOW)
        self.assertIn("5h pace 0/0% ETA -/now", out)

    def test_bad_input_skipped(self):
        self.assertEqual(sl.pace_part({"five_hour": {"used_percentage": "x"}}, NOW), "")


if __name__ == "__main__":
    unittest.main()
