from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from segment_clocks import assess


def events(count, offset=lambda t: 0):
    return [(1000 + i * 100_000_000, 10**18 + i * 100_000_000 + offset(i / 10))
            for i in range(count)]


class SegmentTests(unittest.TestCase):
    def test_rejected_candidate_explains_which_gate_failed(self):
        data = events(610, lambda t: round(max(0, t - 20) ** 2 * 1400))
        r = assess(data, candidate_limit_ms=0.001)
        window = next(w for w in r["windows"] if "candidate_checks" in w)
        self.assertFalse(window["candidate_checks"]["within_limit"])
        self.assertEqual(window["active_from_window"], 0)

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

    def test_exported_model_predicts_ros_epoch_from_px4_time(self):
        data = events(550, lambda t: int(2_000_000 + t * 35000) if t >= 20 else 0)
        d, = assess(data)["decisions"]
        px_ns, ros_ns = data[501]
        elapsed = px_ns - int(d["model_reference_px4_ns"])
        predicted = int(d["model_reference_ros_ns"]) + elapsed + round(elapsed * d["rate_ppm"] / 1e6)
        self.assertLessEqual(abs(predicted - ros_ns), 2)
        self.assertEqual((d["training_pairs"], d["validation_pairs"]), (100, 100))

    def test_trailing_partial_window_cannot_confirm_a_switch(self):
        shifted = lambda t: 2_000_000 if t >= 20 else 0
        for stop in (379, 399, 400):
            result = assess(events(stop, shifted))
            self.assertEqual(result["decisions"], [])
            self.assertEqual(result["windows"][-1]["action"], "await_next_window")
        self.assertEqual(assess(events(401, shifted))["decisions"][0]["decision_s"], 40)

    def test_headroom_policy_leaves_the_scoring_budget_unchanged(self):
        data = events(700, lambda t: 150000 if t >= 20 else 0)
        late = assess(data)
        early = assess(data, policy="headroom")
        self.assertEqual(late["decisions"], [])
        self.assertEqual(len(early["decisions"]), 1)
        self.assertEqual(early["over_budget_windows"], 0)
        self.assertEqual(early["evaluation"]["pairs"], late["evaluation"]["pairs"])
        self.assertEqual(early["windows"][2]["action"], "headroom_used")

    def test_alarm_is_judged_on_two_unseen_windows(self):
        step = lambda t: 2000000 if t >= 20 else 0
        d, = assess(events(600, step))["decisions"]
        self.assertEqual(d["followup"]["outcome"], "prevented_breach")
        d, = assess(events(480, step))["decisions"]
        self.assertEqual(d["followup"]["outcome"], "insufficient_followup")
        d, = assess(events(600, lambda t: 150000 if t >= 20 else 0), policy="headroom")["decisions"]
        self.assertEqual(d["followup"]["outcome"], "old_fit_within_budget")

    def test_unresolved_streaks_are_counted_once_and_separated_at_gaps(self):
        from segment_clocks import persistent_breaches
        sample = lambda i, act: {"epoch": 1, "index": i, "start_s": i*10, "end_s": (i+1)*10,
                                 "p95_ms": 1, "action": act}
        seq = [sample(i, "over_budget") for i in (0,1,2,4)]
        seq.extend([sample(5, "recalibrate"), sample(6, "over_budget")])
        actual = persistent_breaches(seq, 0.25)
        self.assertEqual([(e["windows"], e["outcome"]) for e in actual], [(3,"unresolved"), (2,"timely")])

    def test_paired_benchmark_hashes_original_row_numbers_and_stamps(self):
        import hashlib
        from segment_clocks import compare_policies
        data = events(301)
        result = compare_policies(data)
        h = hashlib.sha256()
        for i in range(200,300):
            x,y = data[i]
            h.update(f"{i+1},{x},{y}\n".encode("ascii"))
        self.assertEqual(result["scored_event_sha256"], h.hexdigest())
        for report in result["policies"].values():
            self.assertEqual(report["evaluation"]["pairs"], 100)

    def test_transient_burst_does_not_move_calibration(self):
        result = assess(events(700, lambda t: 2_000_000 if 20 <= t < 30 else 0))
        self.assertEqual(result["decisions"], [])
        self.assertEqual(result["over_budget_windows"], 1)

    def test_step_at_training_boundary_is_not_fit_away(self):
        report = assess(events(400, lambda t: 2_000_000 if t >= 20 else 0))
        self.assertEqual(report["over_budget_windows"], 2)
        self.assertEqual(report["windows"][2]["p95_ms"], 2)
        self.assertEqual(assess(events(99))["scored_windows"], 0)
