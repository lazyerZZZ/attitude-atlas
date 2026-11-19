"""Find candidate overlapping files when ROS 2 recorded PX4 odometry instead of attitude."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import struct

from pair_clocks import read_ulog, signature
from sqlite_bag import byte_order


def bag_keys(path, topic):
    counts = Counter()
    query = """SELECT type, serialization_format, data FROM messages JOIN topics ON topic_id=topics.id
               WHERE name=?"""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for schema, fmt, data in db.execute(query, (topic,)):
            if schema != "px4_msgs/msg/VehicleOdometry" or fmt != "cdr":
                raise ValueError(f"Expected recorded CDR VehicleOdometry on {topic} in {path.name}")
            # Bee-Nav's fixed layout has timestamp, sample time, pose frame, position[3], q[4].
            order = byte_order(data, (120,))
            key = signature(struct.unpack_from(order + "4f", data, 36))
            if key:
                counts[key] += 1
    return counts


def screen(folder, topic):
    index = defaultdict(list)
    bags = sorted(folder.rglob("*.db3"))
    logs = sorted(folder.rglob("*.ulg"))
    used = 0
    for path in bags:
        keys = bag_keys(path, topic)
        used += bool(keys)
        for key, count in keys.items():
            if count == 1:
                index[key].append(path)
    candidates = []
    for path in logs:
        keys = Counter(key for key, _ in read_ulog(path) if key)
        shared = Counter(bag for key, count in keys.items() if count == 1 for bag in index.get(key, ()))
        for bag, count in shared.most_common():
            candidates.append({"ulog": str(path.relative_to(folder)), "bag": str(bag.relative_to(folder)),
                               "shared_unique_quaternions": count})
    return {"ulogs": len(logs), "bags": len(bags), "bags_with_odometry": used,
            "comparisons": used * len(logs), "candidates": candidates}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--topic", default="/fmu/out/vehicle_odometry")
    args = parser.parse_args()
    try:
        print(json.dumps(screen(args.folder, args.topic), indent=2))
    except (OSError, ValueError, sqlite3.Error, ImportError, IndexError, KeyError) as exc:
        parser.exit(2, f"Odometry screening: {exc}\n")
