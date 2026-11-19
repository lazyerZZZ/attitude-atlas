"""Audit a PX4 ULog against a ROS 2 MCAP carrying the mirrored PX4 estimate."""
import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
import struct
import sys

from clock_model import clock_report


@dataclass(frozen=True)
class Anchor:
    px4_us: int
    ros_us: int
    publish_ns: int
    receive_ns: int


def signature(q):
    if len(q) != 4 or not all(math.isfinite(v) for v in q) or not any(q):
        return None
    return struct.pack("<4f", *q)


def join(px, ros):
    px_counts = Counter(k for k, _ in px)
    ros_counts = Counter(row[0] for row in ros)
    unique = {k: t for k, t in px if k and px_counts[k] == 1 and t > 0}
    anchors = [Anchor(unique[k], sample, publish, receive)
               for k, sample, publish, receive in ros
               if k in unique and ros_counts[k] == 1 and sample > 0]
    return anchors, {"ulog_samples": len(px), "bag_samples": len(ros),
                     "unique_event_pairs": len(anchors)}


def read_ulog(path):
    from pyulog import ULog
    data = ULog(path, ["vehicle_attitude"]).get_dataset("vehicle_attitude", 0).data
    quaternions = zip(*(data["q[%d]" % i] for i in range(4)))
    return [(signature(q), int(t)) for q, t in zip(quaternions, data["timestamp_sample"])]


def read_bag(path, topic):
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory
    rows = []
    with open(path, "rb") as stream:
        reader = make_reader(stream, decoder_factories=[DecoderFactory()])
        for schema, _, msg, data in reader.iter_decoded_messages(topics=[topic], log_time_order=False):
            if schema.name != "px4_msgs/msg/VehicleAttitude":
                raise ValueError(f"Unexpected schema {schema.name} on {topic}")
            rows.append((signature(data.q), data.timestamp_sample, msg.publish_time, msg.log_time))
    if not rows:
        raise ValueError(f"No VehicleAttitude samples on {topic}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ulog")
    parser.add_argument("mcap")
    parser.add_argument("--topic", default="/fmu/out/vehicle_attitude")
    args = parser.parse_args()
    anchors, report = join(read_ulog(args.ulog), read_bag(args.mcap, args.topic))
    report["sample_clock"] = clock_report([(a.px4_us * 1000, a.ros_us * 1000) for a in anchors])
    print(json.dumps(report, indent=2))
    return 0 if anchors else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ImportError, KeyError, IndexError, ValueError) as error:
        sys.exit(f"Clock audit: {error}")
