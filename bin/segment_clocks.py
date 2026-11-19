"""Check a PX4/ROS sample clock mapping against an error budget using later events."""
import argparse
import csv
from itertools import groupby
import json
import math
from pathlib import Path
import sys

from clock_model import fit, percentile95, relative_times


def read_events(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = ("px4_sample_us", "ros_sample_us")
        if not set(fields).issubset(reader.fieldnames or ()):
            raise ValueError("Expected px4_sample_us and ros_sample_us in the event CSV")
        pairs = []
        for index, row in enumerate(reader, start=2):
            values = [row.get(k) for k in fields]
            if not all(v and v.isascii() and v.isdecimal() and int(v) > 0 for v in values):
                raise ValueError(f"Invalid positive integer timestamp at CSV row {index}")
            pairs.append(tuple(int(v) * 1000 for v in values))
    return pairs


def errors_ms(model, events):
    origin, slope = model
    return [abs(y - (origin + slope * x)) / 1e6 for x, y in events]


def assess(pairs, budget_ms=0.25, window_s=10.0):
    if not all(math.isfinite(x) and x > 0 for x in (budget_ms, window_s)) or round(window_s * 1e9) < 1:
        raise ValueError("Use a finite positive budget and window")
    width = round(window_s * 1e9)
    boundaries = [(0, "start")] if pairs else []
    for i, ((x0, y0), (x1, y1)) in enumerate(zip(pairs, pairs[1:]), start=1):
        if x1 <= x0 or y1 <= y0:
            boundaries.append((i, "non_increasing_clock"))
        elif x1 - x0 >= width:
            boundaries.append((i, "observation_gap"))
    epochs, windows, decisions = [], [], []
    fixed_errors, adaptive_errors = [], []
    for serial, (start, reason) in enumerate(boundaries):
        stop = boundaries[serial + 1][0] if serial + 1 < len(boundaries) else len(pairs)
        block, changes, fixed, adaptive = assess_epoch(pairs[start:stop], budget_ms, width)
        epoch = serial + 1
        epochs.append({"epoch": epoch, "first_pair": start + 1, "pairs": stop - start, "reason": reason})
        windows.extend(dict(w, epoch=epoch) for w in block)
        decisions.extend(dict(d, epoch=epoch) for d in changes)
        fixed_errors.extend(fixed)
        adaptive_errors.extend(adaptive)
    scored = [w for w in windows if "p95_ms" in w]
    comparison = {"pairs": len(adaptive_errors),
                  "fixed_p95_ms": percentile95(fixed_errors) if fixed_errors else None,
                  "adaptive_p95_ms": percentile95(adaptive_errors) if adaptive_errors else None}
    return {"epochs": epochs, "evaluation": comparison, "budget_ms": budget_ms, "window_s": window_s,
            "windows": windows, "decisions": decisions, "scored_windows": len(scored),
            "over_budget_windows": sum(w["p95_ms"] > budget_ms for w in scored)}


def assess_epoch(pairs, budget_ms, width):
    windows = []
    history = []
    model = None
    candidate = None
    baseline = None
    fixed_errors, adaptive_errors = [], []
    decisions = []
    relative = relative_times(pairs) if pairs else []
    for index, group in groupby(relative, key=lambda p: p[0] // width):
        events = list(group)
        item = {"index": index, "start_s": events[0][0] / 1e9, "end_s": events[-1][0] / 1e9,
                "pairs": len(events)}
        windows.append(item)
        if len(events) < 8 or events[-1][0] - events[0][0] < width * 0.7:
            candidate = None
            if model is None:
                history.clear()
            item["action"] = "insufficient_coverage"
            continue
        if model is None:
            history.append(events)
            item["action"] = "training"
            if len(history) == 2:
                model = baseline = fit(history[0] + history[1])
            continue
        fixed_errors.extend(errors_ms(baseline, events))
        errors = errors_ms(model, events)
        adaptive_errors.extend(errors)
        residual = percentile95(errors)
        if decisions:
            decisions[-1]["future_pairs"] += len(events)
        item.update(p95_ms=residual, action="within_budget")
        if residual <= budget_ms:
            candidate = None
            continue
        item["action"] = "over_budget"
        if candidate and candidate[0] == index - 1:
            _, previous, trial = candidate
            trial_error = percentile95(errors_ms(trial, events))
            item["candidate_p95_ms"] = trial_error
            if trial_error <= budget_ms and trial_error <= residual / 2:
                model = trial
                item["action"] = "recalibrate"
                decisions.append({"candidate_start_s": previous[0][0] / 1e9,
                                  "decision_s": item["end_s"], "future_pairs": 0, "old_p95_ms": residual,
                                  "candidate_p95_ms": trial_error, "rate_ppm": trial[1] * 1e6})
                candidate = None
                continue
        candidate = (index, events, fit(events))
    return windows, decisions, fixed_errors, adaptive_errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events")
    parser.add_argument("--budget-ms", type=float, default=0.25)
    parser.add_argument("--window-s", type=float, default=10)
    args = parser.parse_args()
    print(json.dumps(assess(read_events(args.events), args.budget_ms, args.window_s), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(f"Clock segmentation: {exc}")
