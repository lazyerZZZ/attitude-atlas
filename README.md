# Attitude Atlas

Find the moment your ROS node and PX4 flight controller disagree. Compare two recordings, open the worst pair as synchronized aircraft views, and attach a reproducible report to a GitHub issue.

**[Try the recording demo](https://lazyerzzz.github.io/attitude-atlas/logs.html)** · [Compare one pair](https://lazyerzzz.github.io/attitude-atlas/compare.html) · [Pose explorer](https://lazyerzzz.github.io/attitude-atlas/) · [中文说明](README.zh-CN.md)

[![Synthetic recording shows a single 90-degree error and one unmatched ROS sample](media/recording-check.png)](https://lazyerzzz.github.io/attitude-atlas/logs.html)

The synthetic demo contains 22 ROS samples. With a 5 ms window, 21 match PX4 and the last one falls outside the window. The 95th percentile rounds to 0°, but ROS sample 13 has a 90° roll discrepancy. Open it to see both noses point north-east while the wings disagree.

## Compare two recordings

1. Export a PX4 attitude CSV with `ulog2csv -m vehicle_attitude flight.ulg`. During recording or bag playback, capture one ROS topic with `ros2 topic echo /odom --full-length > ros.yaml`; stop with Ctrl+C. A stamped orientation and consistent frame IDs are required. Inputs should already represent FRD in NED and FLU in geographic ENU.
2. Open Recording check and choose the files. Confirm a shared clock and epoch, or enter a measured synchronization point consisting of PX4 microseconds and ROS nanoseconds at the same instant. A single point compensates a constant offset. Split captures at clock resets and calibrate drift separately.
3. Set the maximum allowed timestamp difference. Matching selects the nearest PX4 sample for each ROS observation and picks the earlier sample on a tie. PX4 samples may be reused. Inspect the number of distinct PX4 samples, missing ROS matches and peak error alongside the nearest-rank percentile.
4. Click an observation or move the sample slider with the arrow keys. Open a matched pair in Bridge check, then choose **Copy issue report**. The CSV download includes every observed row, both source timestamps, original clock difference, matching skew and rotation error. Unmatched rows have an empty rotation error.

The browser reads up to 16 MiB per file in a local worker. The CLI takes the same files, or accepts native `.ulg` input when [pyulog](https://github.com/PX4/pyulog) provides `ulog2csv` on your PATH. This command runs the bundled synthetic example from the repository root:

```sh
node bin/check-recording.mjs site/samples/roll-spike.csv site/samples/roll-spike.yaml \
  --shared-clock --max-skew-ms 5 --rows-out rows.csv --case-out worst.json
```

Use `--max-error-deg 2 --min-coverage-pct 95` to gate CI. This demo exceeds the 2° tolerance. Exit 0 means the configured checks passed, 1 indicates a failed check or zero matches, and 2 indicates invalid inputs or an I/O failure. Export paths must be new files. For different epochs, replace `--shared-clock` with `--px4-anchor-us US --ros-anchor-ns NS` using your measured synchronization readings. Exported single-pair cases preserve the original stamps and leave cross-clock time comparison unconfirmed.

## Compare messages from your bridge

1. Paste a PX4 `vehicle_attitude` message and a ROS quaternion, PoseStamped, Odometry orientation or a single aligned TransformStamped. YAML from `ros2 topic echo --once`, JSON, and four numeric components are supported. The page retains the original numbers and displays each input norm.
2. Check your conventions. PX4 uses FRD in NED, and the ROS side assumes FLU in geographic ENU. ROS frame IDs are shown for inspection. Align arbitrary map frames and sensor mounts before interpreting the angular difference.
3. If your sample timestamps share a clock and epoch, enable the clock checkbox to see **ROS minus PX4** in milliseconds. PX4 uses the nonzero `timestamp_sample` when available, then `timestamp`. ROS uses `header.stamp`. Replacing either message clears the clock confirmation.
4. Copy a comparison link for an issue, or export JSON and reopen it with **Open case JSON**. Both include extracted attitudes, frame IDs, timestamps and clock selection. The rest of each message stays local. See [running a case in CI](#run-a-bridge-regression-in-ci).

## A 30-second frame check

1. Select **Level, facing north**. PX4 reads `[1, 0, 0, 0]` in **w, x, y, z** order.
2. Look at the ROS 2 row. It reads `[0, 0, 0.707107, 0.707107]` in **x, y, z, w** order. Its yaw is +90° because geographic ENU yaw starts at east.
3. Switch to **Level, facing east**. Now the ROS quaternion is the identity. Drag the aircraft view to inspect the nose against the compass. Orbiting the camera keeps the attitude fixed.

## Use it during development

- **Inspect a message.** Choose Quaternion, select the source convention and paste a message or four numbers. The viewer normalizes the input and displays both representations.
- **Replay recorded attitudes.** Open Replay to scrub the bundled PX4 excerpt or import a numeric, comma-separated `vehicle_attitude` CSV up to 16 MiB. Timestamps determine playback speed. Between samples the viewer shows the last recorded attitude and its age. Step forward or back one sample to inspect changes across a gap.
- **Share a bug.** Copy pose link puts the four PX4 components in the URL fragment. Anyone who opens the link sees the same physical attitude. The link contains a single pose. Imported files are processed locally.
- **Test a bridge.** Export test case downloads JSON containing both quaternions, their component orders, frame names and the expected forward unit vector in each world frame. Compare rotations allowing for the equivalent signs of a unit quaternion.

To extract the attitude topic with [pyulog](https://github.com/PX4/pyulog), run:

```sh
ulog2csv -m vehicle_attitude flight.ulg
```

Open the resulting `*_vehicle_attitude_0.csv` in Replay. Required columns are `timestamp` in microseconds and `q[0]` through `q[3]`. Reordered headers and extra numeric columns are supported. A CSV with a declared `pose_frame` must specify NED (1) on every row. [Download the example CSV](site/sample.csv).

## Frame conventions

| | Body axes | World axes | Quaternion order |
|---|---|---|---|
| PX4 vehicle attitude | Forward, right, down | North, east, down | w, x, y, z |
| ROS geographic local frame | Forward, left, up | East, north, up | x, y, z, w |

Each attitude maps a body vector into the world. With column vectors, the rotation matrices satisfy `R_ros = A · R_px4 · B`. The world basis change is `A(n,e,d) = (e,n,−d)`. The body basis change is `B(f,l,u) = (f,−l,−u)`. The sliders use PX4 intrinsic Z–Y–X yaw, pitch and roll, displayed in degrees. At vertical pitch, roll and yaw are coupled. The quaternion retains the full orientation. ROS systems with an arbitrarily oriented map or odometry frame require their own world-frame alignment.

References: [PX4 VehicleAttitude](https://docs.px4.io/main/en/msg_docs/VehicleAttitude), [PX4 frame transforms](https://github.com/PX4/px4_ros_com/blob/main/include/px4_ros_com/frame_transforms.h), [ROS REP 103](https://www.ros.org/reps/rep-0103.html).

## Run locally

The static site runs without a build or a package installation. It serves its assets locally, including [js-yaml 5.5.0](https://github.com/nodeca/js-yaml) under its [MIT notice](site/vendor/js-yaml.LICENSE).

```sh
python3 -m http.server 8000 --directory site
```

Open <http://localhost:8000>. Run the numerical tests with Node.js 18 or newer:

```sh
node --test tests/*.test.mjs
```

The tests cover frame conversion, rotation and axis errors, timestamp handling, message parsing, CSV playback, exported cases and CLI exit codes. The publishing workflow also exercises all three pages in Chrome at desktop and mobile widths. Every sample in the included recording is checked against an independent direction-cosine matrix.

## Sample data

The demo contains 187 attitude samples spanning 7.9992 seconds from the [PX4 pyulog test recording at revision 0b392f8](https://github.com/PX4/pyulog/blob/0b392f8444f843b796405b9766cc15a6dddedf62/test/sample.ulg). It takes every fourth `vehicle_attitude` sample in the first eight seconds of that topic and retains the original timestamp and quaternion. The aircraft drawing is illustrative. The recording's vehicle type and flight conditions are unspecified.

The application and original illustrations use the [MIT license](LICENSE). The bundled PX4 sample carries its [upstream BSD 3-Clause notice](site/SAMPLE-LICENSE.txt).

## Run a bridge regression in CI

In [Bridge check](https://lazyerzzz.github.io/attitude-atlas/compare.html), compare a pair and click **Export JSON**. Reuse that PX4 input when testing a new output from your ROS node:

```sh
node bin/check-case.mjs attitude-atlas-comparison.json --ros observed.yaml --max-error-deg 0.1
```

The command recomputes the smallest rotation angle. A result within the chosen tolerance exits 0, a mismatch exits 1, and invalid input exits 2. Omit `--ros` to check the stored pair, or use `--ros -` to read from stdin. A replacement message needs its own clock alignment, so its time offset is left unavailable.


Try the included [roll mismatch](examples/north-roll.json) from a clean checkout:

```sh
node bin/check-case.mjs examples/north-roll.json
```

It reports a 90° rotation error and a 0° forward-axis error. With `--max-error-deg 1` it exits 1, which makes the mismatch visible to CI.
