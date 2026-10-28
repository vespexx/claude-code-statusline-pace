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
        self.assertEqual(sl.epoch("2027-01-15T08:00:00Z"), 1799990400.0)

    def test_stale_reset(self):
        out = sl.pace_part({"five_hour": {"used_percentage": 50, "resets_at": NOW - 10}}, NOW)
        self.assertIn("5h pace 0/0% ETA -/now", out)

    def test_bad_input_skipped(self):
        self.assertEqual(sl.pace_part({"five_hour": {"used_percentage": "x"}}, NOW), "")


if __name__ == "__main__":
    unittest.main()
