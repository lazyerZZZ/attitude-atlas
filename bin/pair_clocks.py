"""Audit a PX4 ULog against a ROS 2 bag carrying the mirrored PX4 estimate."""
import argparse
from bisect import bisect_right
from pathlib import Path
import sqlite3
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
import struct
import sys

from statistics import median

from clock_model import clock_report, percentile95


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


def attitude_rows(ulog):
    data = ulog.get_dataset("vehicle_attitude", 0).data
    quaternions = zip(*(data["q[%d]" % i] for i in range(4)))
    return [(signature(q), int(t)) for q, t in zip(quaternions, data["timestamp_sample"])]


def read_ulog(path):
    from pyulog import ULog
    return attitude_rows(ULog(str(path), ["vehicle_attitude"]))


def read_flight(path):
    from pyulog import ULog
    ulog = ULog(str(path), ["vehicle_attitude", "vehicle_land_detected"])
    states = []
    for dataset in ulog.data_list:
        if dataset.name == "vehicle_land_detected" and dataset.multi_id == 0:
            states = [(int(t), bool(value)) for t, value in
                      zip(dataset.data["timestamp"], dataset.data["landed"])]
    hitl = ulog.initial_parameters.get("SYS_HITL")
    platform = {"board": ulog.msg_info_dict.get("ver_hw"),
                "sys_hitl": int(hitl) if hitl is not None else None}
    return attitude_rows(ulog), platform, states


def overlap_report(anchors, max_gap_us=1_000_000):
    """Summarize elapsed PX4 time supported by adjacent shared observations."""
    spans = []
    first = previous = None
    for a in anchors:
        if previous is None:
            first = a
        elif not (0 < a.px4_us - previous.px4_us <= max_gap_us and a.ros_us > previous.ros_us):
            spans.append(previous.px4_us - first.px4_us)
            first = a
        previous = a
    if previous:
        spans.append(previous.px4_us - first.px4_us)
    return {"max_gap_s": max_gap_us / 1e6, "runs": len(spans),
            "longest_run_s": max(spans, default=0) / 1e6,
            "supported_s": sum(spans) / 1e6}


def matched_land_states(anchors, states):
    stamps = [t for t, _ in states]
    if any(b < a for a, b in zip(stamps, stamps[1:])):
        raise ValueError("Land-state timestamps moved backward")
    counts = {"landed": 0, "airborne": 0, "unknown": 0}
    for event in anchors:
        i = bisect_right(stamps, event.px4_us) - 1
        state = "unknown" if i < 0 else ("landed" if states[i][1] else "airborne")
        counts[state] += 1
    return counts


def read_bag(path, topic, sync_topic):
    if Path(path).suffix.lower() == ".db3":
        from sqlite_bag import read_sqlite
        return read_sqlite(path, topic, sync_topic, signature)
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory
    rows, sync = [], defaultdict(list)
    with open(path, "rb") as stream:
        reader = make_reader(stream, decoder_factories=[DecoderFactory()])
        for schema, channel, msg, data in reader.iter_decoded_messages(topics=[topic, sync_topic], log_time_order=False):
            if channel.topic == sync_topic:
                if schema.name != "px4_msgs/msg/TimesyncStatus":
                    raise ValueError(f"Unexpected schema {schema.name} on {sync_topic}")
                sync[data.source_protocol].append((data.timestamp, data.estimated_offset, data.round_trip_time))
                continue
            if schema.name != "px4_msgs/msg/VehicleAttitude":
                raise ValueError(f"Unexpected schema {schema.name} on {topic}")
            rows.append((signature(data.q), data.timestamp_sample, msg.publish_time, msg.log_time))
    if not rows:
        raise ValueError(f"No VehicleAttitude samples on {topic}")
    return rows, sync


def sync_report(groups, anchors):
    if not anchors:
        return []
    start, end = min(a.ros_us for a in anchors), max(a.ros_us for a in anchors)
    reports = []
    for protocol, samples in sorted(groups.items()):
        overlap = [(offset, rtt) for stamp, offset, rtt in samples if start <= stamp <= end]
        if not overlap:
            continue
        offsets, rtts = zip(*overlap)
        reports.append({"source_protocol": protocol, "overlap_samples": len(offsets),
                        "estimated_offset_change_us": offsets[-1] - offsets[0],
                        "median_rtt_us": median(rtts), "p95_rtt_us": percentile95(rtts)})
    return reports


def timing_report(anchors):
    report = {}
    for name, field, scale in (("sample_clock", "ros_us", 1000),
                               ("publish_clock", "publish_ns", 1),
                               ("receive_clock", "receive_ns", 1)):
        pairs = [(a.px4_us * 1000, getattr(a, field) * scale)
                 for a in anchors if getattr(a, field) > 0]
        report[name] = clock_report(pairs)
        if report[name]:
            report[name]["pairs"] = len(pairs)
    gaps = [(a.receive_ns - a.ros_us * 1000) / 1e6 for a in anchors if a.receive_ns > 0]
    report["receive_minus_sample_ms"] = (
        {"median": median(gaps), "p95": percentile95(gaps), "negative_count": sum(g < 0 for g in gaps)}
        if gaps else None)
    return report


def write_events(path, anchors, sqlite_source=False):
    with open(path, "x", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        if sqlite_source:
            writer.writerow(["px4_sample_us", "ros_sample_us", "rosbag_receive_ns"])
            writer.writerows((a.px4_us, a.ros_us, a.receive_ns) for a in anchors)
        else:
            writer.writerow(["px4_sample_us", "ros_sample_us", "mcap_publish_ns", "mcap_log_ns"])
            writer.writerows((a.px4_us, a.ros_us, a.publish_ns, a.receive_ns) for a in anchors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ulog")
    parser.add_argument("bag", help="ROS 2 .mcap or .db3 recording")
    parser.add_argument("--topic", default="/fmu/out/vehicle_attitude")
    parser.add_argument("--sync-topic", default="/fmu/out/timesync_status")
    parser.add_argument("--segment-budget-ms", type=float, help="Evaluate forward-only sample-clock recalibration")
    parser.add_argument("--segment-policy", choices=["confirmed", "headroom"], help="Select a recalibration policy")
    parser.add_argument("--window-s", type=float, help="Segmentation window in PX4 seconds (default 10)")
    parser.add_argument("--events-out", metavar="NEW.csv", help="Export exact event timestamps with units")
    args = parser.parse_args()
    if (args.window_s is not None or args.segment_policy) and args.segment_budget_ms is None:
        parser.error("Segmentation options require --segment-budget-ms")
    ros, sync = read_bag(args.bag, args.topic, args.sync_topic)
    px, platform, states = read_flight(args.ulog)
    anchors, report = join(px, ros)
    report["platform"] = platform
    report["matched_overlap"] = overlap_report(anchors)
    report["matched_land_states"] = matched_land_states(anchors, states)
    report["timesync"] = sync_report(sync, anchors)
    if args.segment_budget_ms is not None:
        from segment_clocks import assess
        report["segmentation"] = assess([(a.px4_us * 1000, a.ros_us * 1000) for a in anchors],
                                        args.segment_budget_ms, 10 if args.window_s is None else args.window_s,
                                        args.segment_policy or "confirmed")
    if any(b.px4_us <= a.px4_us for a, b in zip(anchors, anchors[1:])) and args.segment_budget_ms is not None:
        report["clock_fit_diagnostic"] = "PX4 time reversed or repeated. Inspect per-epoch segmentation."
    else:
        report.update(timing_report(anchors))
    if args.events_out and anchors:
        write_events(args.events_out, anchors, sqlite_source=Path(args.bag).suffix.lower() == ".db3")
    print(json.dumps(report, indent=2))
    return 0 if anchors else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, sqlite3.Error, ImportError, KeyError, IndexError, ValueError) as error:
        sys.exit(f"Clock audit: {error}")
