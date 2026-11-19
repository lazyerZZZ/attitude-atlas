"""Audit local and remote clock observations in onboard PX4 DDS timesync exchanges."""
import argparse
from bisect import bisect_right
import json
from statistics import median

from clock_model import percentile95
from segment_clocks import compare_policies


def exchanges(data):
    pairs, rtts, stamps = [], [], []
    for protocol, remote, offset, rtt, stamp in zip(*(data[field] for field in
            ("source_protocol", "remote_timestamp", "observed_offset", "round_trip_time", "timestamp"))):
        remote, offset = int(remote), int(offset)
        if int(protocol) != 2 or remote <= 0 or remote + offset <= 0:
            continue
        # PX4 defines observed_offset as local exchange midpoint minus remote time.
        pairs.append(((remote + offset) * 1000, remote * 1000))
        rtts.append(int(rtt))
        stamps.append(int(stamp))
    return pairs, rtts, stamps


def exchange_resolution(pairs, rtts, budget_ms):
    # The midpoint approximation has one half RTT of one-sided timing uncertainty.
    offsets = [(peer - local) / 1e6 for local, peer in
               [(x - pairs[0][0], y - pairs[0][1]) for x, y in pairs]]
    jumps = [abs(b - a) for a, b in zip(offsets, offsets[1:])]
    radii = [v / 2000 for v in rtts]
    return {"half_rtt_exceeds_budget": sum(radius > budget_ms for radius in radii),
            "max_adjacent_offset_change_ms": max(jumps, default=None),
            "adjacent_changes_beyond_rtt_and_budget": sum(
                j > a + b + budget_ms for j, a, b in zip(jumps, radii, radii[1:]))}


def audit(path, budget_ms=0.25, window_s=10.0):
    from pyulog import ULog
    ulog = ULog(str(path), ["timesync_status", "vehicle_land_detected"])
    status = next((d for d in ulog.data_list if d.name == "timesync_status" and d.multi_id == 0), None)
    if status is None:
        raise ValueError("ULog has no instance-0 timesync_status")
    pairs, rtts, stamps = exchanges(status.data)
    if not pairs:
        raise ValueError("No usable DDS clock exchanges in ULog")
    land = next((d.data for d in ulog.data_list if d.name == "vehicle_land_detected" and d.multi_id == 0), {})
    changes = [int(t) for t in land.get("timestamp", [])]
    airborne = unknown = 0
    for stamp in stamps:
        i = bisect_right(changes, stamp) - 1
        unknown += i < 0
        airborne += i >= 0 and not bool(land["landed"][i])
    return {"evidence": "onboard_dds_exchange", "board": ulog.msg_info_dict.get("ver_hw"),
            "sys_hitl": int(ulog.initial_parameters["SYS_HITL"]) if "SYS_HITL" in ulog.initial_parameters else None,
            "exchanges": len(pairs), "airborne_exchanges": airborne, "unknown_land_state": unknown,
            "span_s": (stamps[-1] - stamps[0]) / 1e6, "median_rtt_us": median(rtts),
            "p95_rtt_us": percentile95(rtts), "resolution": exchange_resolution(pairs, rtts, budget_ms), "comparison": compare_policies(pairs, budget_ms, window_s)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ulog")
    parser.add_argument("--budget-ms", type=float, default=0.25)
    parser.add_argument("--window-s", type=float, default=10)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.ulog, args.budget_ms, args.window_s), indent=2))
    except (ValueError, OSError, KeyError, ImportError) as exc:
        parser.exit(2, f"DDS audit: {exc}\n")
