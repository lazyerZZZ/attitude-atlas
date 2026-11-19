import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from pair_clocks import Anchor, join, signature, timing_report, sync_report


class EventTests(unittest.TestCase):
    def test_repeated_events_are_ambiguous_on_either_side(self):
        px = [(b"a", 1), (b"a", 2), (b"b", 3), (b"c", 4)]
        ros = [(k, 99, 100, 101) for k in (b"a", b"b", b"b", b"c")]
        rows, counts = join(px, ros)
        self.assertEqual([r.px4_us for r in rows], [4])
        self.assertEqual(counts["unique_event_pairs"], 1)

    def test_receipt_and_sample_timestamps_have_different_evidence(self):
        anchors = [Anchor(i * 1000, i * 1000, 0, i * 1000000 + i - 3) for i in range(1, 10)]
        report = timing_report(anchors)
        self.assertIsNone(report["publish_clock"])
        self.assertEqual(report["sample_clock"]["rate_ppm"], 0)
        self.assertAlmostEqual(report["receive_clock"]["rate_ppm"], 1)
        self.assertEqual(report["receive_minus_sample_ms"]["negative_count"], 2)

    def test_timesync_filters_window_and_keeps_protocols_separate(self):
        anchors = [Anchor(1, 10, 0, 0), Anchor(2, 20, 0, 0)]
        groups = {2: [(1, -500, 9), (10, -50, 2), (20, -53, 4)], 1: [(13, 30, 7)]}
        a, b = sync_report(groups, anchors)
        self.assertEqual((a["source_protocol"], a["median_rtt_us"]), (1, 7))
        self.assertEqual((b["overlap_samples"], b["estimated_offset_change_us"]), (2, -3))

    def test_only_finite_nonzero_payloads(self):
        self.assertIsNone(signature([0] * 4))
        self.assertIsNone(signature([float("nan"), 0, 0, 0]))
        self.assertNotEqual(signature([1, 0, 0, 0]), signature([-1, 0, 0, 0]))
