"""Render the public transfer study from the verified result file."""
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def rows(entries):
    parts = []
    for label, seconds, comparison in entries:
        old, new = (comparison["policies"][name] for name in ("confirmed", "headroom"))
        n = new["evaluation"]["pairs"]
        def p95(report):
            value = report["evaluation"]["adaptive_p95_ms"]
            return f"{value:.3f}" if value is not None else "—"
        parts.append(f"<tr><th scope='row'>{escape(label)}</th><td>{seconds:.2f}</td><td>{n:,}</td>"
                     f"<td>{p95(old)}</td><td>{p95(new)}</td></tr>")
    return ("<div class='table-scroll'><table><thead><tr><th>Recording</th><th>Span (s)</th>"
            "<th>Scored events</th><th>Confirmed P95 (ms)</th><th>Headroom P95 (ms)</th></tr></thead>"
            "<tbody>" + "".join(parts) + "</tbody></table></div>")


def render(data):
    cases = data["paired"]
    native = [(name, case["matched_span_s"], case["comparison"]) for name, case in cases.items()]
    extended = [(name, r["span_s"], r["comparison"]) for name, case in cases.items() for r in case["bag_exchange_replay"]]
    g = data["ground_effect"]["policies"]
    d = data["dds"]
    c = data["labeled_counts"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calibration on unseen recordings · Attitude Atlas</title>
<link rel="stylesheet" href="style.css"><link rel="stylesheet" href="segments.css">
<style>.table-scroll {{overflow-x:auto}} .table-scroll th:first-child {{text-align:left}}
.table-scroll th:last-child,.table-scroll td:last-child {{text-align:right}} .table-scroll th {{vertical-align:bottom}}
.replay details {{margin:1.4rem 0}} .replay details summary {{cursor:pointer}}</style>
</head><body><header><div class="bar"><a class="brand" href="./">Attitude Atlas</a>
<nav><a href="segments.html">Window replay</a></nav></div></header><main class="replay">
<h1>Calibration on unseen recordings</h1>
<p>Should the clock checker act before the error budget is spent? Both policies score the same events.
Confirmed starts testing a replacement at 0.25 ms. Headroom starts at 0.125 ms. Both wait for evidence in a later window.</p>
<h2>Ground-effect target</h2>
<p>On the original development recording, P95 fell from <strong>{g['confirmed']['evaluation']['adaptive_p95_ms']:.3f} to
{g['headroom']['evaluation']['adaptive_p95_ms']:.3f} ms</strong> over {g['headroom']['evaluation']['pairs']:,} scored
events. The number outside the 0.25 ms budget fell from {g['confirmed']['over_budget_pairs']} to {g['headroom']['over_budget_pairs']}.</p>
<h2>Held-out VOXL 2 flights</h2>
<p>Six additional ULog and ROS 2 bag pairs shared {sum(x['unique_event_pairs'] for x in cases.values()):,} unique attitudes.
D0012 had 114 seconds between the first and last shared event, with enough interruptions that no later window could be scored.</p>
{rows(native)}
<h2>Five- and ten-minute clock exchanges</h2>
<p>The two longest ROS 2 bags continued recording synchronization messages outside the ULog overlap.
For each message, we reconstruct local return time from the reported remote time, observed offset and half the round-trip time.
During native coverage, {cases['115317_D0015']['bag_exchange_replay'][0]['bracketed']} and {cases['122204_D0015']['bag_exchange_replay'][0]['bracketed']} exchanges respectively
could be checked against neighboring native events. Both bracket checks had a P95 absolute difference of 0.0035 ms. The rest of each trace has only exchange evidence.</p>
{rows(extended)}
<details><summary>Which early switches helped?</summary>
<p>On the five-minute trace, three of five early switches prevented a budget breach on at least one of the next two eligible windows.
For the other two switches the previous fit stayed within budget throughout that follow-up.
On the ten-minute trace, one of four switches prevented a breach and the other three had a previous fit still within budget.
These counts use the retired fit on the same future observations.</p></details>
<h2>False alarms and missed changes</h2>
<p>Known-label controls keep the recorded sampling schedule and replace ROS time with a specified clock signal.
At two onset times we tested stable clocks, short pulses, sustained steps and changes in rate. Detection had a 40-second deadline.
Each policy had {c['headroom']['censored']} trials with insufficient coverage.</p>
<div class="table-scroll"><table><thead><tr><th>Policy</th><th>False alarms / negatives</th><th>Misses / positives</th></tr></thead>
<tbody><tr><th>Confirmed</th><td>{c['confirmed']['FP']} / {c['confirmed']['FP'] + c['confirmed']['TN']}</td><td>{c['confirmed']['FN']} / {c['confirmed']['FN'] + c['confirmed']['TP']}</td></tr>
<tr><th>Headroom</th><td>{c['headroom']['FP']} / {c['headroom']['FP'] + c['headroom']['TN']}</td><td>{c['headroom'].get('FN', 0)} / {c['headroom']['TP'] + c['headroom'].get('FN',0)}</td></tr></tbody></table></div>
<p>Two-window pulses caused the false alarms. The confirmed policy missed slow +8 ppm changes by the deadline.
The original recordings have no independent labels for physical clock changes.</p>
<h2>Third-board timing resolution</h2>
<p>A separate PX4_FMU_V6C ULog contains {d['exchanges']} onboard DDS exchanges across {d['span_s']:.1f} s;
the land detector reported airborne at {d['airborne_exchanges']} exchanges. Half the RTT exceeded the budget at every exchange.
Neither policy confirmed a replacement on this series. This session has no verified companion bag.</p>
<p><a href="https://github.com/lazyerZZZ/attitude-atlas/blob/main/examples/clock-study/TRANSFER.md">Reproduction guide and source files</a></p>
</main></body></html>"""


if __name__ == "__main__":
    data = json.loads((HERE / "transfer-results.json").read_text())
    print(render(data))
