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

    def test_persistent_change_is_validated_before_switch(self):
        report = assess(events(600, lambda t: 2_000_000 if t >= 20 else 0))
        decision, = report["decisions"]
        self.assertEqual(decision["candidate_start_s"], 20)
        self.assertEqual(decision["decision_s"], 40.0)
        self.assertEqual(report["verdict"], "recalibration_confirmed")
        self.assertEqual(decision["eligible_after_px4_ns"], str(events(401)[-1][0]))
        self.assertEqual(assess(events(99))["verdict"], "insufficient_evidence")
        self.assertEqual(report["windows"][4]["p95_ms"], 0)
        prefix = assess(events(300, lambda t: 2_000_000 if t >= 20 else 0))
        self.assertEqual(prefix["decisions"], [])

    def test_switch_block_is_charged_to_old_model(self):
        report = assess(events(500, lambda t: 2_000_000 if t >= 20 else 0))
        self.assertEqual(report["evaluation"], {"pairs": 300, "fixed_p95_ms": 2, "adaptive_p95_ms": 2})
        self.assertEqual(report["decisions"][0]["future_pairs"], 100)
        self.assertIsNone(assess([])["evaluation"]["adaptive_p95_ms"])

    def test_resets_and_recording_gaps_force_new_training(self):
        data = events(310)
        data += [(x, y-10**12) for x,y in events(310)]
        data += [(x+100*10**9, y) for x,y in events(310)]
        result = assess(data)
        self.assertEqual([e["reason"] for e in result["epochs"]],
                         ["start", "non_increasing_clock", "observation_gap"])
        self.assertEqual([e["first_pair"] for e in result["epochs"]], [1, 311, 621])
        self.assertEqual(result["scored_windows"], 3)
        self.assertEqual(result["decisions"], [])

    def test_trailing_partial_window_cannot_confirm_a_switch(self):
        shifted = lambda t: 2_000_000 if t >= 20 else 0
        for stop in (379, 399, 400):
            result = assess(events(stop, shifted))
            self.assertEqual(result["decisions"], [])
            self.assertEqual(result["windows"][-1]["action"], "await_next_window")
        self.assertEqual(assess(events(401, shifted))["decisions"][0]["decision_s"], 40)

    def test_transient_burst_does_not_move_calibration(self):
        result = assess(events(700, lambda t: 2_000_000 if 20 <= t < 30 else 0))
        self.assertEqual(result["decisions"], [])
        self.assertEqual(result["over_budget_windows"], 1)

    def test_step_at_training_boundary_is_not_fit_away(self):
        report = assess(events(400, lambda t: 2_000_000 if t >= 20 else 0))
        self.assertEqual(report["over_budget_windows"], 2)
        self.assertEqual(report["windows"][2]["p95_ms"], 2)
        self.assertEqual(assess(events(99))["scored_windows"], 0)
