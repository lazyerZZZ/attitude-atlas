# Reproduce the two flight-clock audits

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

Pass a ROS 2 MCAP containing CDR messages with embedded ROS message definitions and an instance-0 PX4 `vehicle_attitude` ULog. Use `--topic` for a namespaced mirror of `px4_msgs/msg/VehicleAttitude`. The optional `--sync-topic` on the audit selects `px4_msgs/msg/TimesyncStatus`. Split bags should be analyzed one MCAP part at a time. Independent ROS odometry belongs in [Recording check](https://lazyerzzz.github.io/attitude-atlas/logs.html) after frame and clock alignment.

Flight search ranks all supplied candidates. A leading candidate requires at least two unique payload matches spanning positive time and a sole leader. Inspect the span and match count before treating a candidate as a flight pair. A stationary repeated quaternion is ambiguous, so it cannot establish event identity. The audit saves exact integer timestamps to a new CSV file. Retain the original units when using these columns in another tool.

## Replay the published results

[Run the GitHub Actions replay](https://github.com/lazyerZZZ/attitude-atlas/actions/workflows/clock-study.yml), or download the four paths in [sources.json](sources.json) from the [pinned source data](https://github.com/BioMorphic-Intelligence-Lab/manipulator_assisted_landing/tree/488db55fa1d7b541b5287bd4faeeb33a91b6d533/data). Keep their directory structure under a local checkout. The source captures are credited to Martijn Brummelhuis and the BioMorphic Intelligence Lab. [Upstream license](https://github.com/BioMorphic-Intelligence-Lab/manipulator_assisted_landing/blob/488db55fa1d7b541b5287bd4faeeb33a91b6d533/LICENSE).

```sh
python examples/clock-study/reproduce.py /path/to/manipulator_assisted_landing --check
```

This verifies the four SHA-256 digests, recomputes [the published metrics](results.json), and swaps the bags to check that both cross-flight comparisons return zero shared events. Omit `--check` to print the reports. To redraw the figure, export each pair with `--events-out`, install matplotlib, and run `python examples/clock-study/plot.py reference.csv ground-effect.csv offsets.png`.

## Read a clock report

* **Pairing** uses identical, finite, nonzero four-component float32 payloads that occur exactly once on each side. No timestamp tolerance is used. Different logging rates, capture boundaries, duplicates and invalid samples affect the count.
* **Sample clock** uses the nonzero `timestamp_sample` of the matched event on each side. Timestamps are subtracted as integers before fitting. Positive ppm means ROS time gained microseconds per elapsed PX4 second. The end-to-end offset change uses the first and last matched events.
* **Clock windows** divide the matched span into four equal durations. The slope within each interval helps expose changing rates. A backward timestamp flags the affected clock for inspection. Split at clock restarts before interpreting a rate.
* **Holdout** fits a mean offset and a least-squares line on the first two thirds of events, then measures absolute residuals on the remaining third. P95 uses nearest rank. The browser’s two-point interpolation uses the anchors you supply and applies only between them. Its accuracy depends on how those points were measured.
* **Recorder timing** compares MCAP publish and log time separately with PX4. Interpret receive-minus-sample in milliseconds only when the bag and the translated ROS payload timestamps share an epoch. That observed difference includes sampling, translation and delivery effects.
* **Timesync** groups the reported round-trip times and estimated offsets by protocol over the matched ROS interval. RTT is in microseconds. Missing status messages leave an empty list.

For two-point matching with `check-recording.mjs`, use PX4 sample microseconds and the corresponding ROS-clock nanoseconds for each endpoint. The `ros_sample_us` field in the event CSV is in microseconds, so multiply it by 1000 using integer arithmetic. Apply a calibration to another topic only after establishing that it uses that same clock mapping. A header stamped at callback time can have different timing behavior.
