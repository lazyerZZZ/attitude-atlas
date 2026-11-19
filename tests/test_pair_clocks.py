import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from pair_clocks import join, signature


class EventTests(unittest.TestCase):
    def test_repeated_events_are_ambiguous_on_either_side(self):
        px = [(b"a", 1), (b"a", 2), (b"b", 3), (b"c", 4)]
        ros = [(k, 99, 100, 101) for k in (b"a", b"b", b"b", b"c")]
        rows, counts = join(px, ros)
        self.assertEqual([r.px4_us for r in rows], [4])
        self.assertEqual(counts["unique_event_pairs"], 1)

    def test_only_finite_nonzero_payloads(self):
        self.assertIsNone(signature([0] * 4))
        self.assertIsNone(signature([float("nan"), 0, 0, 0]))
        self.assertNotEqual(signature([1, 0, 0, 0]), signature([-1, 0, 0, 0]))
