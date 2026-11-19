from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from check_dds_clock import exchanges


class ExchangeTests(unittest.TestCase):
    def test_filters_protocol_and_uses_signed_midpoint_offset(self):
        epoch = 1800000000000000
        data = {"source_protocol": [2, 1, 2, 2], "remote_timestamp": [epoch, epoch, 0, epoch+1],
                "observed_offset": [50-epoch, 0, 1, -epoch-100],
                "round_trip_time": [90,80,10,5], "timestamp": [200,300,400,500]}
        pairs, rtt, stamps = exchanges(data)
        self.assertEqual((pairs, rtt, stamps), ([(50000, epoch*1000)], [90], [200]))
