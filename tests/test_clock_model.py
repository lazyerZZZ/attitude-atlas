import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from clock_model import clock_report


class RateTests(unittest.TestCase):
    def test_signed_rates_at_unix_epoch(self):
        for ppm in (-40, 0, 40):
            samples = [(i * 10**9, 1756222547166587000 + i * (10**9 + ppm * 1000))
                       for i in range(100)]
            self.assertAlmostEqual(clock_report(samples)["rate_ppm"], ppm)
            self.assertAlmostEqual(clock_report(samples)["offset_change_ms"], 99 * ppm / 1000)

    def test_late_clock_step_stays_in_holdout(self):
        pairs = [(i * 10**9, i * 10**9 + (10**7 if i >= 6 else 0)) for i in range(9)]
        result = clock_report(pairs)["holdout"]
        self.assertEqual(result["training_pairs"], 6)
        self.assertEqual(result["affine"]["p95_abs_ms"], 10)
        self.assertEqual(result["constant"]["median_abs_ms"], 10)
        self.assertIsNone(clock_report(pairs[:5])["holdout"])

    def test_windows_expose_rate_changes_and_sparse_coverage(self):
        pairs = [(x, x + max(0, x - 500_000) // 10) for x in (0, 100, 700_000, 800_000, 1000_000)]
        windows = clock_report(pairs)["windows"]
        self.assertEqual([w["pairs"] for w in windows], [2, 0, 1, 2])
        self.assertIsNone(windows[2]["rate_ppm"])
        self.assertAlmostEqual(windows[-1]["rate_ppm"], 100000)

    def test_discontinuity_is_not_silently_sorted(self):
        with self.assertRaisesRegex(ValueError, "split"):
            clock_report([(100, 123), (50, 234)])
