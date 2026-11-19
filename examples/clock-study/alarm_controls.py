"""Exercise known changes on the exact PX4 sampling schedule of a held-out recording."""
from segment_clocks import assess


def challenge(pairs, budget_ms=0.25, window_s=10):
    """Synthetic ROS times only. Use a complete local evaluation horizon for each trial."""
    if not pairs:
        return []
    start = pairs[0][0]
    elapsed = [(x - start) for x, _ in pairs]
    if any(b <= a for a, b in zip(elapsed, elapsed[1:])):
        raise ValueError("Split PX4 restarts before generating timing controls")
    # Constant 10 ppm plus deterministic bounded jitter of at most 20 microseconds.
    nominal = [10**18 + t + round(t / 100000) + (i % 9 - 4) * 5000 for i, t in enumerate(elapsed)]
    trials = []
    for onset in (3 * window_s, 3.5 * window_s):
        deadline = onset + 4 * window_s
        for kind in ("stable", "one_window_pulse", "two_window_pulse", "positive_step", "negative_step", "rate_change", "slow_rate_change"):
            def change(t):
                after = t / 1e9 - onset
                if after < 0 or kind == "stable":
                    return 0
                if kind in ("rate_change", "slow_rate_change"):
                    ppm = 40 if kind == "rate_change" else 8
                    return round(after * ppm * 1000)
                if kind.endswith("pulse"):
                    length = window_s if kind == "one_window_pulse" else 2 * window_s
                    return 600000 if after < length else 0
                return -600000 if kind == "negative_step" else 600000

            trial = [(x, y + change(t)) for (x, _), y, t in zip(pairs, nominal, elapsed)]
            for policy in ("confirmed", "headroom"):
                result = assess(trial, budget_ms, window_s, policy)
                monitored = {w["index"] for w in result["windows"] if "p95_ms" in w}
                required = set(range(2, int(deadline // window_s) + 1))
                complete = (len(result["epochs"]) == 1 and elapsed[-1] >= deadline * 1e9
                            and required.issubset(monitored))
                positive = kind in ("positive_step", "negative_step", "rate_change", "slow_rate_change")
                alerts = [d["decision_s"] for d in result["decisions"] if d["decision_s"] <= deadline]
                detected = any(t >= onset for t in alerts)
                outcome = "censored"
                if complete:
                    if positive:
                        outcome = "TP" if detected else "FN"
                    else:
                        outcome = "FP" if alerts else "TN"
                trials.append({"policy": policy, "scenario": kind, "onset_s": onset,
                               "deadline_s": deadline, "outcome": outcome, "alarm_times_s": alerts,
                               "pre_onset_alarms": sum(t < onset for t in alerts)})
    return trials
