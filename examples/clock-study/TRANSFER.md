# Calibration transfer study

[Open the measured comparison](https://lazyerzzz.github.io/attitude-atlas/transfer.html) · [Inspect every switch and labeled trial](transfer-results.json) · [Replay on GitHub Actions](https://github.com/lazyerZZZ/attitude-atlas/actions/workflows/transfer-study.yml).

## Run on your recordings

Install the [clock-study dependencies](requirements.txt) in a Python virtual environment. To compare the original policy with the optional headroom policy on the exact same observations, run this command from the repository root.

```sh
python bin/pair_clocks.py flight.ulg capture.db3 --segment-budget-ms 0.25 --segment-policy both --exchange-replay
```

For MCAP, omit `--exchange-replay`. To inspect the full window chronology and reusable model parameters, pass `--segment-policy headroom`. An existing matched-event CSV works with `python bin/segment_clocks.py events.csv --compare-policies`.

Confirmed remains the default. With a 0.25 ms budget, headroom starts considering a replacement at 0.125 ms. The current model must exceed this trigger in two consecutive eligible windows. The replacement is fitted on the first window and must meet the trigger and at least halve the old error on the second. Activation waits for the first event in the next window. In both policies training, timing units, the 10 s windows and the **0.25 ms scoring budget** stay the same. Each comparison fingerprints the ordinal and the original timestamp pair of every scored event.

## What transferred?

The ground-effect flight was used to develop the policy. Its P95 dropped from **0.299 to 0.185 ms** on the same 2,795 later events. Over-budget events dropped from 338 to zero. The four headroom activations occurred at 80.09, 130.00, 190.05 and 250.10 seconds. The last had insufficient follow-up to judge its benefit. The policy implementation was committed before replaying either policy on the new held-out series.

Six additional [HALO flight pairs](https://github.com/zafarb-21/HALO_ARCHIVAL_TOOL/tree/61a28f574a86f73c6cd8032350098132e63599c0/archives) yielded 9,038 unique shared attitudes. Each pair contained airborne events. All 30 off-diagonal combinations returned zero. September D0012 spans 114.00 s between matching endpoints but its longest run with at most a 1 s gap is 20.80 s. Its P95 is unavailable. The longest continuous native match is 98.40 s on October D0015. On the native holdouts, all five headroom switches with a complete two-window follow-up prevented at least one breach that the retired fit would have produced. One September flight still had headroom P95 of 0.359 ms.

The **328.45 s and 602.80 s VOXL 2 exchange traces** use all recorded synchronization messages in the two long bags. The respective native ULog overlaps are 98.40 and 79.05 s. Local exchange return time is approximated as `remote_timestamp + observed_offset + round_trip_time / 2`, using integer nanoseconds; ROS time is the bag message’s payload timestamp. The sign and midpoint convention follow the [PX4 timesync calculation](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/src/lib/timesync/Timesync.cpp). Both HALO series reported protocol ID 0 (unknown); the replay preserves that ID. Within overlap, the ROS stamp at each reconstructed local time is compared with neighboring native anchor pairs at most 1 s apart. The two checks covered 984 and 790 exchanges with P95 absolute differences of 0.0035 ms. Outside overlap the bag supplies the only clock evidence. These residuals test internal consistency and carry transport and timestamp-conversion effects.

Headroom improved pooled exchange P95 from **0.260 to 0.156 ms** in the longer session. It regressed from **0.632 to 1.129 ms** in the shorter one, despite fewer over-budget windows. Pooled P95 counts individual events, so fewer failing windows can coexist with larger errors. The completed-window rule, tighter candidate acceptance and alarm timings are visible in the per-policy report.

## How false alarms and misses are counted

On original flight data, each switch keeps its retired model for scoring on the next two consecutive eligible windows of that segment. The report distinguishes a prevented breach, an introduced breach, an old fit that stayed within budget, a remaining breach, and insufficient follow-up. A separate list records consecutive over-budget runs and whether they received a switch on time. These are operational checks. Physical change-point labels are unavailable.

For a known-label test, the six recordings supply their actual PX4 sample schedules. Only ROS timestamps are synthesized: a 10 ppm clock with bounded deterministic jitter up to 20 µs. Each trial starts at 30 or 35 s and allows 40 s for detection. Stable clocks and one- or two-window 0.6 ms pulses are negatives for a **persistent** change. Positive cases are permanent ±0.6 ms steps and +8 or +40 ppm changes in rate. Both policies are evaluated on the same schedules. Trials with inadequate evaluation coverage are censored.

| Policy | False alarms / 24 negative trials | Misses / 32 positive trials | Censored |
| --- | ---: | ---: | ---: |
| Confirmed | 4 | 8 | 28 |
| Headroom | 4 | 0 | 28 |

All four false alarms per policy came from two-window pulses. Confirmed missed the slow rate changes by the deadline. These trial counts describe the specific deterministic scenarios; they do not estimate population error rates.

## Third-board evidence and candidate screening

A [separate Pixhawk 6C project](https://github.com/Dorten8/MasterThesisDrone/tree/4f3adf0db3348d9fae4617e29941ea8635895d27/dev_logs/flights) provides 818 **onboard DDS exchanges** spanning 815.72 s. For these protocol-2 observations we compare reconstructed local midpoint time with the peer timestamp. The land detector reported airborne at 43 exchanges. Half the round-trip time exceeded 0.25 ms at all 818 exchanges. Both policies left a sustained over-budget run unresolved. No independently verified ROS bag accompanies this test, and this session cannot establish a physical false-negative rate. Analyze other ULogs with `python bin/check_dds_clock.py flight.ulg`.

We also screened the 34 ULogs and 58 ROS 2 SQLite bags in the [TU Delft Bee-Nav archive, version 1](https://doi.org/10.4121/a0217a20-0443-48b2-8a04-9609ac267029.v1). Its Cyberzoo bags record PX4 vehicle odometry. None of the 1,972 file combinations shared a four-component quaternion unique in both the ROS odometry and the ULog attitude stream, so this archive supplied no direct clock benchmark. To repeat this specific search, extract the published archive and run `python bin/screen_odometry.py /path/to/article_data`. A hit in this cross-topic screen is a candidate for further verification.

## Reproduce published results

The [input manifest](holdout-sources.json) pins individual files and hashes, including the Git LFS content digest of the ten-minute bag. The downloader verifies file content before parsing it. The published report contains aggregate timing measurements and test outcomes.

```sh
python examples/clock-study/fetch_transfer.py /tmp/atlas-study
python examples/clock-study/replay_transfer.py /tmp/atlas-study/original /tmp/atlas-study/halo /tmp/atlas-study/dds --check
```

Use `--case 115317_D0015`, `--case dds` or `--case ground_effect` for an individual check after downloading the corresponding inputs. Recompute the web page with `python examples/clock-study/render_transfer.py > site/transfer.html`.
