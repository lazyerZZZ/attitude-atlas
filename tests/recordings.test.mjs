import test from "node:test";
import assert from "node:assert/strict";
import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
} from "../site/recordings.mjs";
export const px =
  "timestamp,timestamp_sample,q[0],q[1],q[2],q[3]\n1002000,1000000,1,0,0,0\n1022000,1020000,1,0,0,0";
const doc = (ns, q = "0.5, y: 0.5, z: 0.5, w: 0.5") =>
  "header: {stamp: {sec: 1, nanosec: " +
  ns +
  "}, frame_id: enu}\norientation: {x: " +
  q +
  "}\n---\n";
test("time join handles ties, reused samples, an inclusive boundary and unmatched samples", () => {
  const p = readPx4Recording(px);
  assert.equal(p.field, "timestamp_sample");
  const ros = readRosRecording(
    [0, 10000000, 30000000, 40000000].map((ns) => doc(ns)).join(""),
  );
  const r = matchRecording(p.rows, ros, 10);
  assert.deepEqual(
    r.rows.map((x) => [x.pi, x.skewMs, x.rotationDeg]),
    [
      [0, 0, 90],
      [0, 10, 90],
      [1, 10, 90],
      [1, 20, null],
    ],
  );
  assert.equal(r.matched, 3);
  assert.equal(r.unmatched, 1);
});
test("capture parser rejects clock resets, missing timestamps and frame changes", () => {
  const a = doc(0);
  assert.throws(() => readRosRecording(a + a), /increase/);
  assert.throws(
    () => readRosRecording(a + doc(1).replace("enu", "other")),
    /Frame IDs/,
  );
  assert.throws(
    () => readRosRecording("x: 0\ny: 0\nz: 0\nw: 1"),
    /header.stamp/,
  );
  assert.equal(
    readPx4Recording(px.replace("1022000,1020000", "1022000,0")).field,
    "timestamp",
  );
  assert.throws(() => matchRecording([], [], NaN), /skew/);
});
test("demo exposes one large error although its 95th percentile is near zero", async () => {
  const { readFileSync } = await import("node:fs");
  const { recordingSummary, sampleCase } = await import(
    "../site/recordings.mjs"
  );
  const { openCase } = await import("../site/cases.mjs");
  const p = readPx4Recording(
    readFileSync(
      new URL("../site/samples/roll-spike.csv", import.meta.url),
      "utf8",
    ),
  );
  const r = readRosRecording(
    readFileSync(
      new URL("../site/samples/roll-spike.yaml", import.meta.url),
      "utf8",
    ),
  );
  const matches = matchRecording(p.rows, r, 5),
    s = recordingSummary(matches, p.rows, r);
  assert.equal(s.matched, 21);
  assert.equal(s.unmatched, 1);
  assert.equal(s.distinctPx4, 21);
  assert.ok(s.p95Deg < 1e-9);
  assert.ok(Math.abs(s.maxDeg - 90) < 1e-9);
  assert.equal(matches.worst.ri, 12);
  assert.equal(
    openCase(sampleCase(matches.worst, p.rows, r)).ros.stampNs,
    1241500000n,
  );
});
