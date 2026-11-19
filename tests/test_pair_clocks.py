import csv
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from pair_clocks import Anchor, join, signature, timing_report, sync_report, write_events


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

    def test_export_round_trips_epoch_nanoseconds_without_overwriting(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "events.csv"
            data = [Anchor(10001, 20000, 1756198346213437154, 1756198346213437199)]
            write_events(path, data)
            with path.open() as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(int(row["mcap_log_ns"]), data[0].receive_ns)
            with self.assertRaises(FileExistsError):
                write_events(path, [])

    def test_hardware_state_uses_latest_report_before_each_event(self):
        from pair_clocks import matched_land_states
        anchors = [Anchor(t, t, 0, 0) for t in (1, 2, 4, 9)]
        self.assertEqual(matched_land_states(anchors, [(2, True), (4, False)]),
                         {"unknown": 1, "landed": 1, "airborne": 2})

    def test_sqlite_export_carries_only_recorded_clocks(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "events.csv"
            write_events(path, [Anchor(3, 4, 0, 6001)], sqlite_source=True)
            with path.open() as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row, {"px4_sample_us": "3", "ros_sample_us": "4", "rosbag_receive_ns": "6001"})

    def test_unobserved_gaps_do_not_count_as_supported_overlap(self):
        from pair_clocks import overlap_report
        rows = [Anchor(t, t, 0, 0) for t in (10, 500010, 4000000, 4500000, 5000000)]
        report = overlap_report(rows)
        self.assertEqual((report["runs"], report["longest_run_s"], report["supported_s"]), (2, 1, 1.5))
        self.assertEqual(overlap_report([])["runs"], 0)

    def test_only_finite_nonzero_payloads(self):
        self.assertIsNone(signature([0] * 4))
        self.assertIsNone(signature([float("nan"), 0, 0, 0]))
        self.assertNotEqual(signature([1, 0, 0, 0]), signature([-1, 0, 0, 0]))
