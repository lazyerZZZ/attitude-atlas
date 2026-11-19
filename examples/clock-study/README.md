# Reproduce the flight-clock audits

The reference flight supplied 935 unambiguous events across 77.10 seconds. The ground-effect test supplied 3,123 across 256.90 seconds. In each case the ROS 2 topic mirrors the flight controller’s own estimate. The same event gives us two sample timestamps and two recorder timestamps. [Read the plotted case study](https://lazyerzzz.github.io/attitude-atlas/clock-study.html).

## Run it on your logs

From the Attitude Atlas repository root, set up the optional offline tools once.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r examples/clock-study/requirements.txt
python bin/find_flight.py capture.mcap logs/*.ulg
python bin/pair_clocks.py selected.ulg capture.mcap --events-out events.csv
```

Pass an instance-0 PX4 `vehicle_attitude` ULog and a ROS 2 bag. MCAP uses embedded ROS message definitions. The rosbag2 SQLite reader supports CDR1 VehicleAttitude and TimesyncStatus with the layouts used in the HALO archives. SQLite supplies a recording timestamp and leaves MCAP publish-time statistics unavailable. Use `--topic` for a namespaced mirror of `px4_msgs/msg/VehicleAttitude`. The optional `--sync-topic` on the audit selects `px4_msgs/msg/TimesyncStatus`. Analyze each split bag file separately. Independent ROS odometry belongs in [Recording check](https://lazyerzzz.github.io/attitude-atlas/logs.html) after frame and clock alignment.

Flight search ranks all supplied candidates. A leading candidate requires at least two unique payload matches spanning positive time and a sole leader. Inspect the span and match count before treating a candidate as a flight pair. A stationary repeated quaternion is ambiguous, so it cannot establish event identity. The audit saves exact integer timestamps to a new CSV file. Retain the original units when using these columns in another tool.

## Replay the published results

[Run the GitHub Actions replay](https://github.com/lazyerZZZ/attitude-atlas/actions/workflows/clock-study.yml), or download the four paths in [sources.json](sources.json) from the [pinned source data](https://github.com/BioMorphic-Intelligence-Lab/manipulator_assisted_landing/tree/488db55fa1d7b541b5287bd4faeeb33a91b6d533/data). Keep their directory structure under a local checkout. The source captures are credited to Martijn Brummelhuis and the BioMorphic Intelligence Lab. [Upstream license](https://github.com/BioMorphic-Intelligence-Lab/manipulator_assisted_landing/blob/488db55fa1d7b541b5287bd4faeeb33a91b6d533/LICENSE).

```sh
python examples/clock-study/reproduce.py /path/to/manipulator_assisted_landing --check
```

This verifies the four SHA-256 digests, recomputes [the published metrics](results.json), and swaps the bags to check that both cross-flight comparisons return zero shared events. Omit `--check` to print the reports. To redraw the figure, export each pair with `--events-out`, install matplotlib, and run `python examples/clock-study/plot.py reference.csv ground-effect.csv offsets.png`.

## Cross-hardware replay and automatic segmentation

The [HALO archive](https://github.com/zafarb-21/HALO_ARCHIVAL_TOOL/tree/61a28f574a86f73c6cd8032350098132e63599c0/archives) supplies seven verified pairs from the October 2 three- and four-aircraft recording sessions. Three aircraft IDs report `MODALAI_VOXL2`, `SYS_HITL=0` and airborne matched events. Each selected SQLite bag contributes one overlapping ULog. Copies and alternate truncations of a flight can tie in the candidate search. The [manifest](halo-sources.json) identifies the exact files used.

Use both checkouts, or run the GitHub Actions replay above. It checks 18 file digests, 9 paired reports and all 72 off-diagonal combinations. Every off-diagonal combination returned zero unique events. [Published results](hardware-results.json) · [Explore the windows](https://lazyerzzz.github.io/attitude-atlas/segments.html).

```sh
python examples/clock-study/compare_hardware.py /data/manipulator_assisted_landing /data/HALO_ARCHIVAL_TOOL --check
python bin/pair_clocks.py flight.ulg capture.db3 --segment-budget-ms 0.25 --window-s 10
python bin/segment_clocks.py events.csv --budget-ms 0.25 --window-s 10
```

The default is an engineering example. Choose the error budget for your own downstream time matching. Each window needs at least eight matched events spanning 70% of its duration. Two eligible windows establish an affine baseline. The first over-budget window fits a candidate. A second consecutive over-budget window must show that the candidate meets the budget and at least halves the old P95 error. The first observation in the next window confirms closure and activates the switch. Missing coverage interrupts candidate confirmation. A clock reversal, repeat or gap of at least one window starts a new epoch.

Fixed and adaptive evaluation use the same later events. The original fit restarts at each mandatory epoch boundary in both policies. Changing the budget changes when the adaptive model can switch. The candidate validation window is charged to the old model. An exceeded budget can remain unconfirmed, and a short session can end before either policy is evaluated. These decisions are offline recommendations from mirrored sample timestamps.

Each confirmed model supplies a rate and an integer reference pair. To estimate ROS time for a subsequent PX4 timestamp, subtract `model_reference_px4_ns` as an integer to obtain elapsed nanoseconds. Add that elapsed time and `round(elapsed_ns * rate_ppm / 1e6)` to `model_reference_ros_ns`. Convert epoch strings to integers before doing arithmetic. Decisions and window times use seconds since the start of their own epoch. The two `eligible_after_*` fields identify the observation at which confirmation became available.

The longest HALO overlap lasted 49.59 s (+14.71 ppm). Its scored P95 was 0.109 ms under both policies. Six shorter overlaps had no scored windows at the default duration. The original long ground-effect recording confirmed two switches; pooled adaptive P95 was still 0.299 ms against a 0.25 ms budget. Comparing these installations also changes capture length, firmware and the timestamp path. Hardware oscillator behavior would require an independent timing reference.

We also screened a [Pixhawk 6C project](https://github.com/Dorten8/MasterThesisDrone/tree/4f3adf0db3348d9fae4617e29941ea8635895d27/dev_logs/flights). Its May 14 ULog `20_45_31.ulg` (4,337 attitudes) and May 19 rectangle-flight MCAP (7,344 attitudes) returned zero shared events. The table reports measurements only for verified pairs.

## Read a clock report

* **Pairing** uses identical, finite, nonzero four-component float32 payloads that occur exactly once on each side. No timestamp tolerance is used. Different logging rates, capture boundaries, duplicates and invalid samples affect the count.
* **Sample clock** uses the nonzero `timestamp_sample` of the matched event on each side. Timestamps are subtracted as integers before fitting. Positive ppm means ROS time gained microseconds per elapsed PX4 second. The end-to-end offset change uses the first and last matched events.
* **Clock windows** divide the matched span into four equal durations. The slope within each interval helps expose changing rates. A backward timestamp flags the affected clock for inspection. Split at clock restarts before interpreting a rate.
* **Holdout** fits a mean offset and a least-squares line on the first two thirds of events, then measures absolute residuals on the remaining third. P95 uses nearest rank. The browser’s two-point interpolation uses the anchors you supply and applies only between them. Its accuracy depends on how those points were measured.
* **Recorder timing** compares MCAP publish and log time separately with PX4. Interpret receive-minus-sample in milliseconds only when the bag and the translated ROS payload timestamps share an epoch. That observed difference includes sampling, translation and delivery effects.
* **Timesync** groups the reported round-trip times and estimated offsets by protocol over the matched ROS interval. RTT is in microseconds. Missing status messages leave an empty list.

For two-point matching with `check-recording.mjs`, use PX4 sample microseconds and the corresponding ROS-clock nanoseconds for each endpoint. The `ros_sample_us` field in the event CSV is in microseconds, so multiply it by 1000 using integer arithmetic. Apply a calibration to another topic only after establishing that it uses that same clock mapping. A header stamped at callback time can have different timing behavior.
