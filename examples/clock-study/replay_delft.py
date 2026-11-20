"""Validate clock calibration on native attitude events in the TU Delft flight records."""
import argparse
import json
from pathlib import Path
import zlib

from replay_adaptive import HERE, summary
from pair_clocks import join, matched_land_states, overlap_report, read_bag, read_flight
from clock_model import clock_report


def member(root, entry):
    path = root / entry["path"]
    if path.stat().st_size != entry["bytes"]:
        raise ValueError(f"Incorrect file size: {path.name}")
    crc = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            crc = zlib.crc32(block, crc)
    if f"{crc:08x}" != entry["crc32"]:
        raise ValueError(f"Unexpected file contents: {path.name}")
    return path


def replay(root, cases):
    flights, logs, bags = {}, {}, {}
    for name, entries in cases.items():
        px, board, states = read_flight(member(root, entries["ulg"]))
        ros, _ = read_bag(member(root, entries["mcap"]), "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
        anchors, counts = join(px, ros)
        if not anchors:
            raise ValueError(f"No matching attitude samples in {name}")
        pairs = [(a.px4_us * 1000, a.ros_us * 1000) for a in anchors]
        drift = clock_report(pairs)
        flights[name] = {**board, **counts, "land_states": matched_land_states(anchors, states),
                         "overlap": overlap_report(anchors), "rate_ppm": drift["rate_ppm"],
                         "endpoint_offset_change_ms": drift.get("offset_change_ms"),
                         "comparison": summary(pairs)}
        logs[name], bags[name] = px, ros
    negatives = {}
    for name, px in logs.items():
        for other, ros in bags.items():
            if name != other:
                wrong, _ = join(px, ros)
                negatives[f"{name}/{other}"] = len(wrong)
                if wrong:
                    raise ValueError(f"Cross-flight match in {name}/{other}")
    return {"flights": flights, "wrong_flight_matches": negatives}


if __name__ == "__main__":
    cases = json.loads((HERE / "delft-sources.json").read_text())["captures"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--case", choices=cases)
    args = parser.parse_args()
    print(json.dumps(replay(args.data, {args.case: cases[args.case]} if args.case else cases), indent=2))
