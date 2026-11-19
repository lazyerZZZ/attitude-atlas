"""Read recorded VehicleAttitude events from a rosbag2 SQLite CDR file."""
from contextlib import closing
from pathlib import Path
import sqlite3
import struct


def byte_order(data, sizes):
    if len(data) not in sizes or data[:2] not in (b"\0\0", b"\0\1"):
        raise ValueError("Unsupported CDR encoding or PX4 message layout")
    return "<" if data[1] == 1 else ">"


def read_sqlite(path, topic, sync_topic):
    from pair_clocks import signature
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    rows = []
    with closing(sqlite3.connect(uri, uri=True)) as db:
        query = """SELECT t.type, t.serialization_format, m.timestamp, m.data
                   FROM messages m JOIN topics t ON t.id = m.topic_id
                   WHERE t.name = ? ORDER BY m.id"""
        for schema, fmt, receive_ns, data in db.execute(query, (topic,)):
            if schema != "px4_msgs/msg/VehicleAttitude" or fmt != "cdr":
                raise ValueError(f"Expected CDR VehicleAttitude on {topic}")
            order = byte_order(data, (53, 56))
            sample, *q = struct.unpack_from(order + "Q4f", data, 12)
            rows.append((signature(q), sample, 0, receive_ns))
    if not rows:
        raise ValueError(f"No VehicleAttitude samples on {topic}")
    return rows, {}
