import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from exchange_replay import bracket_errors
from pair_clocks import Anchor, clock_continuity


class BracketTests(unittest.TestCase):
    def test_forward_ros_jump_splits_dual_clock_coverage(self):
        anchors = [Anchor(x, y, 0, 0) for x, y in [(1, 2), (11, 12), (21, 3000022), (31, 3000032)]]
        result = clock_continuity(anchors)
        self.assertEqual([r["pairs"] for r in result["runs"]], [2, 2])
        self.assertEqual(result["largest_adjacent_change"]["offset_change_us"], 3000000)
        self.assertEqual(result["largest_adjacent_change"]["ending_pair"], 3)
        self.assertIsNone(clock_continuity([])["largest_adjacent_change"])

    def test_epoch_precision_no_extrapolation_no_interpolation_across_holes(self):
        base = 1700000000000000
        anchors = [Anchor(t, base+t, 0, 0) for t in (1,1001,2000001)]
        pairs = [(x, base*1000+x+1) for x in (0,1000,501000,1000000000,2000001000,3000000000)]
        self.assertEqual(bracket_errors(pairs, anchors), [.000001,.000001,.000001])
