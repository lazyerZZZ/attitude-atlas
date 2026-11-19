import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  unit,
  rotate,
  toRos,
  fromRos,
  fromDegrees,
  toDegrees,
  parseQuaternion,
  parseTrack,
  frameAt,
} from "../site/frames.mjs";

const close = (a, b, tol = 1e-9) =>
  a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < tol, a + " vs " + b));
const same = (a, b) =>
  assert.ok(
    Math.abs(Math.abs(a.reduce((s, v, i) => s + v * b[i], 0)) - 1) < 1e-10,
  );
test("North, east and right-wing-down match physical axes", () => {
  close(toRos([1, 0, 0, 0]), [0, 0, Math.SQRT1_2, Math.SQRT1_2]);
  close(toRos(fromDegrees([0, 0, 90])), [0, 0, 0, 1]);
  close(rotate(fromDegrees([90, 0, 0]), [0, 1, 0]), [0, 0, 1]);
  close(rotate(fromDegrees([0, 90, 0]), [1, 0, 0]), [0, 0, -1]);
});
test("Euler round trips at both pitch singularities and across a grid of poses", () => {
  for (const r of [-170, -40, 0, 25, 160])
    for (const p of [-90, -89.99, -8, 0, 24, 89.99, 90])
      for (const y of [-135, -12, 0, 90, 175]) {
        const q = fromDegrees([r, p, y]);
        same(q, fromDegrees(toDegrees(q)));
        same(q, fromRos(toRos(q)));
      }
});
test("component parsing and normalization handle pasted arrays and extreme magnitudes", () => {
  close(parseQuaternion(" [ 1e30, 0, 0, 0 ] "), [1, 0, 0, 0]);
  close(parseQuaternion("0 0 .1 0"), [0, 0, 1, 0]);
  close(unit([1e308, 1e308, 1e308, 1e308]), [0.5, 0.5, 0.5, 0.5]);
  for (const s of [
    "1,2,,4",
    "0 0 0 0",
    "1,2,3",
    "0 0 1 Infinity",
    "[1 0 0 0",
    "1 0 0 0 extra",
  ])
    assert.throws(() => parseQuaternion(s));
});
const sample = readFileSync(
  new URL("../site/sample.csv", import.meta.url),
  "utf8",
);
test("all real PX4 samples agree with an independent direction-cosine matrix", () => {
  const track = parseTrack(sample);
  assert.ok(track.length > 100);
  for (const {
    q: [w, x, y, z],
  } of track) {
    // Columns of R_NED<-FRD from the scalar-first Hamilton matrix.
    const columns = [
      [1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)],
      [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)],
      [2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)],
    ];
    const [rx, ry, rz, rw] = toRos([w, x, y, z]);
    columns.forEach(([n, e, d], i) => {
      const basis = [0, 0, 0];
      basis[i] = 1;
      const sign = i === 0 ? 1 : -1;
      close(rotate([rw, rx, ry, rz], basis), [sign * e, sign * n, -sign * d]);
    });
  }
});
test("track import preserves source timing and selects the last observed sample", () => {
  const track = parseTrack(
    "q[2],timestamp,q[1],q[0],q[3]\r\n0,1000,0,1,0\r\n0,51000,0,0,1\r\n",
  );
  assert.equal(track[1].t, 0.05);
  assert.equal(frameAt(track, 0.049), track[0]);
  assert.equal(frameAt(track, 0.05), track[1]);
  const header = "timestamp,q[0],q[1],q[2],q[3]\n";
  for (const tail of [
    "",
    "100,1,0,0,0",
    "10,1,0,0,0\n10,1,0,0,0",
    "1,1,0,0,0\n2,0,,1,0",
    "1,1,0,0,0\n-1,1,0,0,0",
  ])
    assert.throws(() => parseTrack(header + tail));
  assert.throws(() => parseTrack("wrong\n1\n2"));
});
test("exported fixture identifies orders and north-facing forward vectors", async () => {
  const { poseFixture } = await import("../site/frames.mjs");
  const fixture = poseFixture([3, 0, 0, 0]);
  close(fixture.px4.q, [1, 0, 0, 0]);
  close(fixture.px4.forward_in_world, [1, 0, 0]);
  close(fixture.ros.forward_in_world, [0, 1, 0]);
  assert.equal(fixture.ros.order, "xyzw");
  assert.equal(fixture.schema, "attitude-atlas/pose-v1");
});
test("replay enforces the declared world frame on every row and retains input norms", () => {
  const rows = "timestamp,pose_frame,q[0],q[1],q[2],q[3]\n0,1,1,0,0,0\n";
  for (const frame of ["", "0", "2", "NaN"]) {
    assert.throws(() => parseTrack(rows + "1000," + frame + ",1,0,0,0"), /Line 3.*NED/);
  }
  assert.equal(parseTrack(rows + "1000,1,100,0,0,0")[1].norm,100);
});
