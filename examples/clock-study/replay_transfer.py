"""Evaluate frozen clock policies on new paired flights and an onboard-exchange session."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from reproduce import HERE, verified_file
from alarm_controls import challenge
from check_dds_clock import audit
from exchange_replay import bag_exchange_replay
from pair_clocks import join, matched_land_states, overlap_report, read_bag, read_flight, timing_report
from segment_clocks import compare_policies


def record_case(ulog, bag, bag_path):
    px, platform, states = ulog
    anchors, counts = join(px, bag)
    if not anchors:
        raise ValueError("Selected recordings share no unique events")
    with sqlite3.connect(bag_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        lo, hi = db.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages").fetchone()
    pairs = [(a.px4_us * 1000, a.ros_us * 1000) for a in anchors]
    clock = timing_report(anchors)["sample_clock"]
    controls = challenge(pairs)
    exchange = bag_exchange_replay(bag_path, anchors) if (hi - lo) >= 180e9 else []
    return {**platform, **counts, "bag_exchange_replay": exchange, "bag_span_s": (hi - lo) / 1e9, "matched_span_s": clock["span_s"],
            "rate_ppm": clock["rate_ppm"], "overlap": overlap_report(anchors),
            "land_states": matched_land_states(anchors, states), "comparison": compare_policies(pairs),
            "controls": controls}


def replay(original, halo, dds, selected=None):
    manifests = json.loads((HERE / "holdout-sources.json").read_text())
    result = {"paired": {}}
    ulgs, bags = {}, {}
    for name, files in manifests["halo"]["captures"].items():
        if selected and selected != name:
            continue
        ulog = read_flight(verified_file(halo, files["ulg"]))
        path = verified_file(halo, files["db3"])
        bag, _ = read_bag(path, "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
        result["paired"][name] = record_case(ulog, bag, path)
        ulgs[name], bags[name] = ulog[0], bag
    negatives = 0
    for name, px in ulgs.items():
        for other, bag in bags.items():
            if other != name:
                if join(px, bag)[0]:
                    raise ValueError(f"Off-diagonal pairing {name} and {other} shared events")
                negatives += 1
    result["cross_pair_controls"] = negatives
    if not selected or selected == "dds":
        files = manifests["dds"]["captures"]["v6c_session"]
        result["dds"] = audit(verified_file(dds, files["ulg"]))
    if not selected or selected == "ground_effect":
        files = json.loads((HERE / "sources.json").read_text())["captures"]["ground_effect"]
        px, _, _ = read_flight(verified_file(original, files["ulg"]))
        bag, _ = read_bag(verified_file(original, files["mcap"]), "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
        anchors, _ = join(px, bag)
        result["ground_effect"] = compare_policies([(a.px4_us * 1000, a.ros_us * 1000) for a in anchors])
    if selected and selected not in result["paired"] and selected not in ("dds", "ground_effect"):
        raise ValueError(f"Unknown case {selected}")
    result["labeled_counts"] = {policy: dict(Counter(
        trial["outcome"] for case in result["paired"].values() for trial in case["controls"]
        if trial["policy"] == policy)) for policy in ("confirmed", "headroom")}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "halo", "dds"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--case", help="Reproduce one named recording")
    args = parser.parse_args()
    print(json.dumps(replay(args.original, args.halo, args.dds, args.case), indent=2))
