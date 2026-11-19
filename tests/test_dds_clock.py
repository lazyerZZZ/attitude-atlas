from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from check_dds_clock import exchanges


class ExchangeTests(unittest.TestCase):
    def test_change_exceeding_two_round_trip_bounds_is_visible(self):
        from check_dds_clock import exchange_resolution
        r = exchange_resolution([(0,0),(1000000,2000000),(2000000,4000000)], [100,100,2000], .25)
        self.assertEqual(r["half_rtt_exceeds_budget"], 1)
        self.assertEqual(r["adjacent_changes_beyond_rtt_and_budget"], 1)

    def test_filters_protocol_and_uses_signed_midpoint_offset(self):
        epoch = 1800000000000000
        data = {"source_protocol": [2, 1, 2, 2], "remote_timestamp": [epoch, epoch, 0, epoch+1],
                "observed_offset": [50-epoch, 0, 1, -epoch-100],
                "round_trip_time": [90,80,10,5], "timestamp": [200,300,400,500]}
        pairs, rtt, stamps = exchanges(data)
        self.assertEqual((pairs, rtt, stamps), ([(50000, epoch*1000)], [90], [200]))
