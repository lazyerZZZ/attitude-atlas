# When to switch clock calibration

Compare a ULog and a ROS 2 recording with a 0.25 ms residual budget. The calibration only affects this offline analysis.

```sh
python -m pip install -r examples/clock-study/requirements.txt
python bin/pair_clocks.py flight.ulg flight.mcap --segment-budget-ms 0.25 --segment-policy all
python bin/segment_clocks.py matched-events.csv --compare-all
```

Look at the number of scored pairs, pooled absolute-error P95, switch count and clock continuity together. A larger ROS interval than PX4 interval between the same two events can expose a forward timestamp jump. Receive and publish times belong to different stages of recording.

## Why the 328-second replay regressed

The two original policies changed both the threshold for nominating a model and the ceiling for accepting it. Replaying the same 3,084 exchanges with each combination isolated their effects.

| Nomination (ms) | Acceptance (ms) | Pooled P95 (ms) |
|---:|---:|---:|
| 0.250 | 0.250 | 0.632 |
| 0.125 | 0.250 | 0.636 |
| 0.250 | 0.125 | 1.129 |
| 0.125 | 0.125 | 1.129 |

At 30–40 s the old fit scored 1.533 ms and its candidate scored 0.137 ms. The 0.125 ms ceiling rejected it. The next window reached 2.365 ms before the policy replaced the fit near 50 s. At 80–90 s another candidate scored 0.131 ms. Both would pass the 0.25 ms budget and the twofold improvement check. P95 here pools individual events. Counting over-budget windows alone gives a different ranking.

The adaptive policy uses a half-budget nomination threshold. In each of two full eligible windows it compares the median signed residual in the first and second halves of the **samples**. Each median change must exceed one sixteenth of the budget in the direction of the current median residual. A level shift can qualify when the median stays over the full budget on the same side for three windows. Either path also requires out-of-sample candidate P95 within the full budget and at most half the old P95. Only later samples use the replacement. Parameters were set using ground effect and VOXL development data before replaying the Delft outcomes. The rule is opt-in.

## Independent flight records

The four consecutive `vb_001` through `vb_004` sessions come from *All Eyes, no IMU* by Stroobants, Hagenaars, Bohté and de Croon. The ULogs identify a Holybro Kakute H7 Mini and have HITL disabled. The pairer matches float32 quaternions that occur once in each source, checks all twelve wrong-flight combinations and reads PX4 land state at matched times. The archive is CC BY-NC 4.0. This repository publishes measurements and fetch instructions. [Versioned original dataset](https://doi.org/10.4121/8244b196-373e-4211-9e05-994e37656490.v1)

```sh
python examples/clock-study/fetch_delft.py /tmp/delft
python examples/clock-study/replay_delft.py /tmp/delft --check
```

The downloader reads approximately 1 GB of the 64.8 GB archive and verifies every original member by SHA-256 and CRC. Use `--case vb_002` on both commands for one 314-second sample. The report includes the longest runs in which both clocks advance by at most one second between matches. Whole-record scores include forward jumps. A separate run diagnostic shows how much data an explicit clock restart would consume in training and incomplete windows.

Each Delft schedule also gets a stable clock, one-window and signed two-window pulses, persistent ±0.6 ms steps, and +8 and +40 ppm rate changes. Every trial runs at six onset phases. All three policies see the same synthetic ROS timestamps and real PX4 sample schedule. False positives and negatives refer to these injected labels. The sign of real hardware drift and the whole-flight P95 measurements come directly from the matched files. [Measured public comparison](https://lazyerzzz.github.io/attitude-atlas/adaptive.html)

## Reproduce the earlier hardware comparisons

```sh
python examples/clock-study/fetch_transfer.py /tmp/atlas-study
python examples/clock-study/replay_adaptive.py /tmp/atlas-study/original /tmp/atlas-study/halo --check
python examples/clock-study/adaptive_transfer.py /tmp/atlas-study/halo --check
```

The 328 s and 603 s VOXL series use reconstructed synchronization exchanges and have 98.40 and 79.05 s of independently bracketed native coverage. The ground-effect and Delft scores use only paired native events. On the 603 s exchange series the early policy retains the lowest P95 at 0.156 ms, compared with 0.260 ms for adaptive. [Replay inputs and previous policies](TRANSFER.md)
