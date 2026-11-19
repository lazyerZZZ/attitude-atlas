from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from segment_clocks import assess


def events(count, offset=lambda t: 0):
    return [(1000 + i * 100_000_000, 10**18 + i * 100_000_000 + offset(i / 10))
            for i in range(count)]


class SegmentTests(unittest.TestCase):
    def test_known_rate_scores_only_future_blocks(self):
        report = assess(events(510, lambda s: int(s * 40000)))
        self.assertEqual(report["scored_windows"], 3)
        self.assertEqual(report["over_budget_windows"], 0)
        self.assertEqual(report["windows"][-1]["action"], "insufficient_coverage")

    def test_step_at_training_boundary_is_not_fit_away(self):
        report = assess(events(400, lambda t: 2_000_000 if t >= 20 else 0))
        self.assertEqual(report["over_budget_windows"], 2)
        self.assertEqual(report["windows"][2]["p95_ms"], 2)
        self.assertEqual(assess(events(99))["scored_windows"], 0)
