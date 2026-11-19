import test from "node:test";
import assert from "node:assert/strict";
import { readMessage, compareAttitudes } from "../site/messages.mjs";
import { fromDegrees, toRos } from "../site/frames.mjs";

const msg = (v, system) => readMessage(JSON.stringify(v), system);
const near = (a, b, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) < eps, a + " vs " + b);
const identity = msg([1, 0, 0, 0], "px4");
test("90 degrees of roll leaves forward error zero", () => {
  const r = compareAttitudes(identity, msg([0.5, 0.5, 0.5, 0.5], "ros"));
  near(r.rotationDeg, 90);
  near(r.forwardDeg, 0);
});
test("relative angle handles sign, tiny rotations and half turns", () => {
  for (const yaw of [0, 0.0000001, 90, 179.999999, 180]) {
    const ros = toRos(fromDegrees([0, 0, yaw])).map((v) => -v);
    const r = compareAttitudes(identity, msg(ros, "ros"));
    near(r.rotationDeg, yaw);
    near(r.forwardDeg, yaw);
  }
});
test("reads ros2 echo sequences and nested odometry without mixing position and attitude", () => {
  const p = readMessage(
    "timestamp: 8888888\ntimestamp_sample: 1234567\nq:\n- 100\n- 0\n- 0\n- 0\ndelta_q_reset: [0,0,0,1]\n---\n",
    "px4",
  );
  const s = readMessage(
    "header:\n  stamp: {sec: 1, nanosec: 254567001}\n  frame_id: map\nchild_frame_id: base_link\npose:\n  pose:\n    position: {x: 0, y: 0, z: 0}\n    orientation: {w: 1, z: 0, x: 0, y: 0}\n",
    "ros",
  );
  assert.deepEqual(p.q, [1, 0, 0, 0]);
  assert.equal(p.raw[0], 100);
  assert.equal(s.world, "map");
  assert.equal(s.child, "base_link");
  assert.equal(compareAttitudes(p, s).timeOffsetMs, null);
  near(compareAttitudes(p, s, true).timeOffsetMs, 20.000001);
  assert.deepEqual(msg(s.source, "ros"), s);
  assert.deepEqual(msg(p.source, "px4"), p);
});
test("rejects unknown frames, zero quaternions, ambiguous or incomplete messages", () => {
  for (const txt of [
    "pose_frame: 2\nq: [1,0,0,0]",
    "q: [0,0,0,0]",
    "q: [1,0,0,0]\n---\nq: [0,0,0,1]",
    "q: [1,0,0,0]\nq: [0,0,0,1]",
  ])
    assert.throws(() => readMessage(txt, "px4"));
  for (const txt of [
    "x: 1\ny: 0",
    "header: {stamp: {sec: 1, nanosec: 1000000000}}\norientation: {x: 0,y: 0,z: 0,w: 1}",
    "orientation_covariance: [-1]\norientation: {x: 0, y: 0, z: 0, w: 1}",
  ])
    assert.throws(() => readMessage(txt, "ros"));
});
test("case snapshots retain numeric evidence and omit unrelated telemetry", async () => {
  const { comparisonCase, openCase } = await import("../site/cases.mjs");
  const px4 = msg(
    { q: [32, 0, 0, 0], timestamp_sample: 12, position: [55, 22, 1] },
    "px4",
  );
  const ros = msg(
    {
      orientation: { x: 0, y: 0, z: 0, w: 1 },
      child_frame_id: "base_link",
      private_note: "omit",
    },
    "ros",
  );
  const snapshot = comparisonCase(px4, ros, false);
  const restored = openCase(JSON.parse(JSON.stringify(snapshot)));
  assert.deepEqual(restored, { px4, ros, sharedClock: false });
  assert.doesNotMatch(JSON.stringify(snapshot), /position|private_note/);
  assert.throws(() => openCase({ ...snapshot, sharedClock: "true" }));
});
test("clock offsets require usable timestamps and preserve signed nanoseconds", () => {
  const ros = msg(
    {
      header: { stamp: { sec: 1, nanosec: 1 } },
      orientation: { x: 0, y: 0, z: 0, w: 1 },
    },
    "ros",
  );
  const fallback = msg(
    { q: [1, 0, 0, 0], timestamp_sample: 0, timestamp: 1000002 },
    "px4",
  );
  assert.equal(fallback.stampField, "timestamp");
  assert.equal(compareAttitudes(fallback, ros, true).timeOffsetMs, -0.001999);
  assert.equal(compareAttitudes(fallback, ros, false).timeOffsetMs, null);
  const zero = msg(
    { q: [1, 0, 0, 0], timestamp_sample: 0, timestamp: 0 },
    "px4",
  );
  assert.equal(compareAttitudes(zero, ros, true).timeOffsetMs, null);
});
test("body-axis diagnostics distinguish roll, pitch and yaw errors with equal magnitude", () => {
  for (const [angles, expected] of [
    [
      [90, 0, 0],
      [0, 90, 90],
    ],
    [
      [0, 90, 0],
      [90, 0, 90],
    ],
    [
      [0, 0, 90],
      [90, 90, 0],
    ],
  ]) {
    const ros = msg(toRos(fromDegrees(angles)), "ros");
    const r = compareAttitudes(identity, ros);
    Object.values(r.bodyAxisErrorsDeg).forEach((angle, i) =>
      near(angle, expected[i]),
    );
    near(r.rotationDeg, 90);
  }
});
test("TF capture preserves parent, child and rotation and rejects ambiguous trees", () => {
  const t = {
    header: { frame_id: "enu", stamp: { sec: 2, nanosec: 0 } },
    child_frame_id: "base_link",
    transform: {
      translation: { x: 300 },
      rotation: { x: 0, y: 0, z: 0, w: 1 },
    },
  };
  for (const doc of [t, { transforms: [t] }]) {
    const m = readMessage(JSON.stringify(doc), "ros");
    assert.deepEqual(m.raw, [0, 0, 0, 1]);
    assert.equal(m.child, "base_link");
    assert.equal(m.world, "enu");
    assert.equal(m.stampNs, 2000000000n);
    assert.ok(!JSON.stringify(m.source).includes("translation"));
  }
  assert.throws(
    () => readMessage(JSON.stringify({ transforms: [t, t] }), "ros"),
    /Select one/,
  );
});
