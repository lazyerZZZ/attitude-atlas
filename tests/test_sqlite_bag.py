from pathlib import Path
import sqlite3
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from pair_clocks import read_bag, signature


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture #1.db3"
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE topics(id INTEGER, name TEXT, type TEXT, serialization_format TEXT);
            CREATE TABLE messages(id INTEGER PRIMARY KEY, topic_id INTEGER, timestamp INTEGER, data BLOB);
            INSERT INTO topics VALUES(1,'att','px4_msgs/msg/VehicleAttitude','cdr');
        """)

    def test_both_endiannesses_and_missing_publish_time(self):
        for order, header in (("<", b"\0\1\0\0"), (">", b"\0\0\0\0")):
            data = header + struct.pack(order + "QQ8fB", 8, 7, 1,0,0,0,1,0,0,0,0)
            self.db.execute("INSERT INTO messages(topic_id,timestamp,data) VALUES(1,?,?)", (9000000011, data))
        self.db.execute("INSERT INTO topics VALUES(2,'sync','px4_msgs/msg/TimesyncStatus','cdr')")
        payload = b"\0\1\0\0" + struct.pack("<QB7xQqqI", 512, 2, 599, -88, -77, 932)
        self.db.execute("INSERT INTO messages(topic_id,timestamp,data) VALUES(2,60,?)", (payload,))
        self.db.commit()
        rows, sync = read_bag(self.path, "att", "sync")
        self.assertEqual(sync[2], [(512, -77, 932)])
        self.assertEqual(rows, [(signature([1,0,0,0]), 7, 0, 9000000011)] * 2)
