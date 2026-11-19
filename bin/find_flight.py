"""Rank candidate PX4 ULogs by shared, unique attitude payloads in a ROS 2 bag."""
import argparse
import json
import sqlite3
from pathlib import Path
import sys

from pair_clocks import join, read_bag, read_ulog


def identify(paths, ros, loader=read_ulog):
    results = []
    for path in paths:
        anchors, counts = join(loader(path), ros)
        span = max(a.px4_us for a in anchors) - min(a.px4_us for a in anchors) if anchors else None
        results.append({"ulog": str(path), "pairs": counts["unique_event_pairs"],
                        "span_s": span / 1e6 if span is not None else None})
    results.sort(key=lambda row: (-row["pairs"], row["ulog"]))
    best = results[0]["pairs"]
    leaders = [r["ulog"] for r in results if r["pairs"] == best and best >= 2 and r["span_s"] > 0]
    return {"candidates": results, "leading_candidate": leaders[0] if len(leaders) == 1 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("ulogs", type=Path, nargs="+")
    parser.add_argument("--topic", default="/fmu/out/vehicle_attitude")
    args = parser.parse_args()
    ros, _ = read_bag(args.bag, args.topic, "/fmu/out/timesync_status")
    paths = list(dict.fromkeys(p.resolve() for p in args.ulogs))
    report = identify(paths, ros)
    print(json.dumps(report, indent=2))
    return 0 if report["leading_candidate"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, sqlite3.Error, ValueError, KeyError, IndexError, ImportError) as error:
        sys.exit(f"Flight search: {error}")
