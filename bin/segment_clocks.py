"""Check a PX4/ROS sample clock mapping against an error budget using later events."""
import argparse
import csv
import hashlib
from itertools import groupby
import json
import math
from pathlib import Path
from statistics import median
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


def residual_shape(model, events):
    """Signed median level and half-window change, in milliseconds."""
    origin, slope = model
    signed = [(y - origin - slope * x) / 1e6 for x, y in events]
    middle = len(signed) // 2
    return median(signed), median(signed[middle:]) - median(signed[:middle])


def persistent_breaches(windows, budget):
    """Group consecutive over-budget windows in one epoch, stopping at each switch."""
    episodes = []
    run = []
    for window in [*windows, None]:
        eligible = window is not None and window.get("p95_ms", 0) > budget
        adjacent = run and eligible and run[-1]["epoch"] == window["epoch"] and run[-1]["index"] + 1 == window["index"]
        if run and (not adjacent or run[-1]["action"] == "recalibrate"):
            if len(run) >= 2:
                final = run[-1]
                confirmed = final["action"] == "recalibrate"
                episodes.append({"epoch": final["epoch"], "start_s": run[0]["start_s"],
                                 "last_s": final["end_s"], "windows": len(run),
                                 "outcome": ("timely" if len(run) == 2 else "late") if confirmed else
                                            ("awaiting_closure" if final["action"] == "await_next_window" else "unresolved")})
            run = []
        if eligible:
            run.append(window)
    return episodes


def assess(pairs, budget_ms=0.25, window_s=10.0, policy="confirmed", *, candidate_limit_ms=None):
    if policy not in ("confirmed", "headroom", "adaptive"):
        raise ValueError("Unknown clock policy")
    if not all(math.isfinite(x) and x > 0 for x in (budget_ms, window_s)) or round(window_s * 1e9) < 1:
        raise ValueError("Use a finite positive budget and window")
    if candidate_limit_ms is not None and not (math.isfinite(candidate_limit_ms) and candidate_limit_ms > 0):
        raise ValueError("Candidate validation limit must be finite and positive")
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
        block, changes, fixed, adaptive = assess_epoch(pairs[start:stop], budget_ms, width, policy, candidate_limit_ms)
        epoch = serial + 1
        epochs.append({"epoch": epoch, "first_pair": start + 1, "pairs": stop - start, "reason": reason})
        windows.extend(dict(w, epoch=epoch, first_pair=start + w["first_pair"]) for w in block)
        decisions.extend(dict(d, epoch=epoch) for d in changes)
        fixed_errors.extend(fixed)
        adaptive_errors.extend(adaptive)
    scored = [w for w in windows if "p95_ms" in w]
    comparison = {"pairs": len(adaptive_errors),
                  "fixed_p95_ms": percentile95(fixed_errors) if fixed_errors else None,
                  "adaptive_p95_ms": percentile95(adaptive_errors) if adaptive_errors else None}
    if decisions:
        verdict = "recalibration_confirmed"
    elif not scored:
        verdict = "insufficient_evidence"
    elif any(w["p95_ms"] > budget_ms for w in scored):
        verdict = "budget_exceeded_unconfirmed"
    else:
        verdict = "within_budget_on_scored_windows"
    return {"policy": policy, "persistent_breaches": persistent_breaches(windows, budget_ms), "verdict": verdict, "epochs": epochs, "evaluation": comparison, "budget_ms": budget_ms, "window_s": window_s,
            "windows": windows, "decisions": decisions, "scored_windows": len(scored),
            "over_budget_windows": sum(w["p95_ms"] > budget_ms for w in scored)}


def audit_switch(decision, old, events, index, budget, new_p95):
    audit = decision["followup"]
    if len(audit["windows"]) >= 2 or index != audit["first_window"] + len(audit["windows"]):
        return
    old_p95 = percentile95(errors_ms(old, events))
    audit["windows"].append({"old_p95_ms": old_p95, "new_p95_ms": new_p95})
    if len(audit["windows"]) == 2:
        windows = audit["windows"]
        if any(w["old_p95_ms"] <= budget < w["new_p95_ms"] for w in windows):
            audit["outcome"] = "introduced_breach"
        elif any(w["new_p95_ms"] <= budget < w["old_p95_ms"] for w in windows):
            audit["outcome"] = "prevented_breach"
        elif all(w["old_p95_ms"] <= budget for w in windows):
            audit["outcome"] = "old_fit_within_budget"
        else:
            audit["outcome"] = "breach_remained"


def assess_epoch(pairs, budget_ms, width, policy, candidate_limit_ms):
    trigger = budget_ms / 2 if policy in ("headroom", "adaptive") else budget_ms
    limit = (budget_ms if policy == "adaptive" else trigger) if candidate_limit_ms is None else candidate_limit_ms
    level_run = 0
    windows = []
    history = []
    model = None
    candidate = None
    baseline = None
    fixed_errors, adaptive_errors = [], []
    decisions = []
    retired = None
    active_window = 0
    relative = relative_times(pairs) if pairs else []
    consumed = 0
    for index, group in groupby(relative, key=lambda p: p[0] // width):
        events = list(group)
        consumed += len(events)
        item = {"index": index, "start_s": events[0][0] / 1e9, "end_s": events[-1][0] / 1e9,
                "pairs": len(events), "first_pair": consumed - len(events) + 1}
        windows.append(item)
        if len(events) < 8 or events[-1][0] - events[0][0] < width * 0.7:
            candidate = None
            level_run = 0
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
        fixed = errors_ms(baseline, events)
        fixed_errors.extend(fixed)
        item["fixed_p95_ms"] = percentile95(fixed)
        errors = errors_ms(model, events)
        adaptive_errors.extend(errors)
        residual = percentile95(errors)
        if decisions:
            decisions[-1]["future_pairs"] += len(events)
            audit_switch(decisions[-1], retired, events, index, budget_ms, residual)
        item.update(active_from_window=active_window, p95_ms=residual, over_budget_pairs=sum(e > budget_ms for e in errors), action="within_budget")
        if policy == "adaptive":
            level, change = residual_shape(model, events)
            direction = 1 if level > budget_ms else -1 if level < -budget_ms else 0
            level_run = level_run + direction if level_run * direction > 0 else direction
        if residual <= trigger:
            candidate = None
            continue
        item["action"] = "over_budget" if residual > budget_ms else "headroom_used"
        if candidate and candidate[0] == index - 1:
            _, previous, trial = candidate
            trial_error = percentile95(errors_ms(trial, events))
            item["candidate_p95_ms"] = trial_error
            item["candidate_checks"] = {"within_limit": trial_error <= limit,
                                        "halves_error": trial_error <= residual / 2}
            if policy == "adaptive":
                _, prior_change = residual_shape(model, previous)
                # Both completed windows must move away from zero in the same direction.
                sign = 1 if level > 0 else -1
                trending = min(sign * prior_change, sign * change) > budget_ms / 16
                item["switch_evidence"] = ("persistent_rate" if trending else
                                           "persistent_level" if abs(level_run) >= 3 else "await_persistence")
                item["candidate_checks"]["persistent"] = trending or abs(level_run) >= 3
            if all(item["candidate_checks"].values()):
                if consumed == len(pairs):
                    item["action"] = "await_next_window"
                    continue
                next_px, next_ros = pairs[consumed]
                decision_s = (next_px - pairs[0][0]) / 1e9
                item["confirmed_s"] = decision_s
                retired, model = model, trial
                active_window = index + 1
                level_run = 0
                last_x = previous[-1][0]
                ref_px = pairs[0][0] + last_x
                ref_ros = pairs[0][1] + last_x + round(trial[0] + trial[1] * last_x)
                item["action"] = "recalibrate"
                decisions.append({"candidate_start_s": previous[0][0] / 1e9,
                                  "eligible_after_px4_ns": str(next_px),
                                  "eligible_after_ros_ns": str(next_ros),
                                  "followup": {"first_window": index + 1, "windows": [], "outcome": "insufficient_followup"},
                                  "decision_s": decision_s, "future_pairs": 0, "old_p95_ms": residual,
                                  "candidate_p95_ms": trial_error, "rate_ppm": trial[1] * 1e6,
                                  "model_reference_px4_ns": str(ref_px), "model_reference_ros_ns": str(ref_ros),
                                  "training_pairs": len(previous), "validation_pairs": len(events)})
                candidate = None
                continue
        candidate = (index, events, fit(events))
    return windows, decisions, fixed_errors, adaptive_errors


def compare_policies(pairs, budget_ms=0.25, window_s=10.0):
    reports = {}
    shared = None
    for policy in ("confirmed", "headroom"):
        report = assess(pairs, budget_ms, window_s, policy)
        digest = hashlib.sha256()
        scored = [w for w in report["windows"] if "p95_ms" in w]
        for w in scored:
            first = w["first_pair"] - 1
            for i in range(first, first + w["pairs"]):
                x, y = pairs[i]
                digest.update(f"{i+1},{x},{y}\n".encode("ascii"))
        fingerprint = digest.hexdigest()
        if shared is not None and shared != fingerprint:
            raise ValueError("Policies scored different events")
        shared = fingerprint
        reports[policy] = {"evaluation": report["evaluation"], "scored_windows": len(scored),
                           "over_budget_pairs": sum(w["over_budget_pairs"] for w in scored),
                           "over_budget_windows": report["over_budget_windows"],
                           "switches": [{"epoch": d["epoch"], "at_s": d["decision_s"],
                                         "followup": d["followup"]["outcome"]} for d in report["decisions"]],
                           "persistent_breaches": report["persistent_breaches"]}
    return {"budget_ms": budget_ms, "window_s": window_s, "scored_event_sha256": shared, "policies": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events")
    parser.add_argument("--budget-ms", type=float, default=0.25)
    parser.add_argument("--window-s", type=float, default=10)
    parser.add_argument("--policy", choices=["confirmed", "headroom"], default="confirmed")
    parser.add_argument("--compare-policies", action="store_true", help="Score both policies on identical events")
    args = parser.parse_args()
    pairs = read_events(args.events)
    result = (compare_policies(pairs, args.budget_ms, args.window_s) if args.compare_policies else
              assess(pairs, args.budget_ms, args.window_s, args.policy))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(f"Clock segmentation: {exc}")
