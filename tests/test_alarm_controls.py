import sys
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "examples/clock-study"), str(ROOT / "bin")]
from alarm_controls import challenge


class Controls(unittest.TestCase):
    def test_labels_cover_misses_and_false_switches_without_counting_short_runs(self):
        points = [(10**12 + i*100000000, 1) for i in range(900)]
        trials = challenge(points)
        self.assertEqual(len(trials), 28)
        self.assertTrue(all(t["outcome"] == "TN" for t in trials if t["scenario"] == "stable"))
        self.assertTrue(all(t["outcome"] == "TP" for t in trials if t["scenario"] == "positive_step"))
        self.assertTrue(any(t["outcome"] == "FP" for t in trials if t["scenario"] == "two_window_pulse"))
        self.assertTrue(any(t["outcome"] == "FN" for t in trials if t["scenario"] == "slow_rate_change"))
        self.assertEqual({t["outcome"] for t in challenge(points[:400])}, {"censored"})
