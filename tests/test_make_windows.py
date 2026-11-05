import contextlib, datetime, io, json, os, subprocess, sys, tempfile, time, unittest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import make_windows as mw


def run(*argv):
    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mw.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class MakeWindows(unittest.TestCase):
    def test_example_to_stdout(self):
        before = time.time()
        code, out, _ = run("--plan", "go", "5h=14%@2026-11-04T18:00", "7d=0.45@2026-11-09T03:00", "--plan", "gemini", "status=ok")
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertGreaterEqual(d["updated"], int(before))
        go = d["plans"]["go"]
        self.assertAlmostEqual(go["5h"]["utilization"], 0.14)
        self.assertEqual(go["7d"]["utilization"], 0.45)
        self.assertEqual(go["5h"]["reset"], datetime.datetime(2026, 11, 4, 18, 0).timestamp())  # naive = local
        self.assertEqual(d["plans"]["gemini"], {"status": "ok"})

    def test_gofree_status(self):
        code, out, _ = run("--plan", "gofree", "status=ok")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["plans"], {"gofree": {"status": "ok"}})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.json")
            code, out, _ = run("--plan", "gofree", "status=ok", "-o", path)
            self.assertEqual((code, out), (0, ""))
            with open(path) as f:
                self.assertEqual(json.load(f)["plans"], {"gofree": {"status": "ok"}})
        code, out, err = run("--plan", "gofree-x", "status=ok")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_reset_forms(self):
        self.assertEqual(mw.parse_reset("1800000000"), 1800000000.0)
        self.assertEqual(mw.parse_reset("2027-01-15T08:00:00Z"), 1800000000.0)
        self.assertEqual(mw.parse_reset("2027-01-15T10:00:00+02:00"), 1800000000.0)

    def test_dash_means_stdout(self):
        code, out, _ = run("--plan", "gemini", "status=ok", "-o", "-")
        self.assertEqual((code, json.loads(out)["plans"]["gemini"]["status"]), (0, "ok"))

    def test_file_written_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.json")
            code, out, _ = run("--plan", "zai", "1mo=5%@0", "-o", path)
            self.assertEqual((code, out), (0, ""))
            self.assertEqual(os.listdir(d), ["w.json"])  # no temp file left
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["plans"]["zai"]["1mo"], {"utilization": 0.05, "reset": 0.0})

    def test_output_is_read_by_statusline(self):
        sys.path.insert(0, ROOT)
        import statusline as sl
        code, out, _ = run("--plan", "go", "5h=14%%@%d" % (time.time() + 3 * 3600), "--plan", "gemini", "status=ok")
        rows = sl.build_rows([], "x", "x (Go)", "", True, False, None, json.loads(out), time.time())
        self.assertIn("Go", rows[1])
        self.assertIn("Gemini", rows[2])

    def test_bad_input_exits_2_with_one_line(self):
        bad = [
            ["--plan", "go", "9h=1%@0"],
            ["--plan", "go", "5h=150%@0"],
            ["--plan", "go", "5h=abc@0"],
            ["--plan", "go", "5h=10%"],
            ["--plan", "go", "5h=10%@never"],
            ["--plan", "nope", "status=ok"],
            ["--plan", "go"],
            ["5h=10%@0"],
            [],
            ["--plan", "go", "status"],
            ["--plan", "gemini", "status=ok", "-o"],
        ]
        for argv in bad:
            with self.subTest(argv=argv):
                code, out, err = run(*argv)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(len(err.strip().splitlines()), 1)

    def test_unwritable_path_exits_2(self):
        code, _, err = run("--plan", "gemini", "status=ok", "-o", "/nonexistent-dir/x.json")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_cli(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "make_windows.py"), "--plan", "gemini", "status=ok"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["plans"], {"gemini": {"status": "ok"}})


if __name__ == "__main__":
    unittest.main()
