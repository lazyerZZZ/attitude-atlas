import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from find_flight import identify


class FlightSearchTests(unittest.TestCase):
    def test_inconclusive_on_tie_and_single_event(self):
        ros = [(b'a', 1, 2, 3), (b'b', 2, 3, 4)]
        candidates = {'first': [(b'a', 1), (b'b', 2)], 'copy': [(b'a', 1), (b'b', 2)],
                      'other': [(b'b', 3)]}
        self.assertIsNone(identify(candidates, ros, candidates.get)["leading_candidate"])
        self.assertIsNone(identify(['other'], ros, candidates.get)["leading_candidate"])
        result = identify(['other', 'first'], ros, candidates.get)
        self.assertEqual(result["leading_candidate"], "first")
        self.assertEqual([r["pairs"] for r in result["candidates"]], [2, 1])
