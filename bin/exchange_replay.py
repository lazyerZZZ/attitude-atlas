"""Compare the bag's reconstructed local exchange times with actual native-log anchors."""
from bisect import bisect_right
from collections import defaultdict
from contextlib import closing
import sqlite3
from statistics import median

from clock_model import percentile95
from segment_clocks import compare_policies
from sqlite_bag import decode_timesync


def bracket_errors(pairs, anchors):
    xs = [a.px4_us * 1000 for a in anchors]
    ys = [a.ros_us * 1000 for a in anchors]
    if any(b <= a for a, b in zip(xs, xs[1:])) or any(b <= a for a, b in zip(ys, ys[1:])):
        raise ValueError("Native anchor clocks must increase within a comparison epoch")
    residuals = []
    for x, y in pairs:
        i = bisect_right(xs, x) - 1
        if i >= 0 and x == xs[i]:
            residuals.append((y - ys[i]) / 1e6)
        elif 0 <= i < len(xs) - 1 and xs[i+1] - xs[i] <= 10**9:
            predicted_delta = (x - xs[i]) * (ys[i+1] - ys[i]) / (xs[i+1] - xs[i])
            residuals.append(((y - ys[i]) - predicted_delta) / 1e6)
    return residuals


def bag_exchange_replay(path, anchors, topic="/fmu/out/timesync_status", budget_ms=0.25, window_s=10.0):
    groups = defaultdict(list)
    query = """SELECT type, serialization_format, data FROM messages m JOIN topics t ON m.topic_id=t.id
               WHERE t.name=? ORDER BY m.id"""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for schema, encoding, data in db.execute(query, (topic,)):
            if schema != "px4_msgs/msg/TimesyncStatus" or encoding != "cdr":
                raise ValueError("Expected CDR TimesyncStatus on selected topic")
            stamp, protocol, remote, observed, _, rtt = decode_timesync(data)
            # observed = local midpoint - remote. Add half RTT to approximate local return time.
            local = (remote + observed) * 1000 + rtt * 500
            if remote > 0 and stamp > 0 and local > 0:
                groups[protocol].append((local, stamp * 1000))
    reports = []
    for protocol, pairs in sorted(groups.items()):
        errors = bracket_errors(pairs, anchors)
        reports.append({"source_protocol": protocol, "exchanges": len(pairs),
                        "span_s": (pairs[-1][0] - pairs[0][0]) / 1e9,
                        "bracketed": len(errors), "bracket_median_ms": median(errors) if errors else None,
                        "bracket_p95_abs_ms": percentile95(list(map(abs, errors))) if errors else None,
                        "comparison": compare_policies(pairs, budget_ms, window_s)})
    return reports
