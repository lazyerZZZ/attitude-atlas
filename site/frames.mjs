// Hamilton quaternions use scalar-first order inside this module.
export function unit(q) {
  if (q.length !== 4 || !q.every(Number.isFinite))
    throw Error("Enter four finite numbers.");
  const scale = Math.max(...q.map(Math.abs));
  if (!scale) throw Error("A zero quaternion has no orientation.");
  const scaled = q.map((v) => v / scale);
  const length = Math.hypot(...scaled);
  return scaled.map((v) => v / length);
}

export function multiply([a, b, c, d], [e, f, g, h]) {
  return [
    a * e - b * f - c * g - d * h,
    a * f + b * e + c * h - d * g,
    a * g - b * h + c * e + d * f,
    a * h + b * g - c * f + d * e,
  ];
}

export function rotate(q, v) {
  return multiply(multiply(q, [0, ...v]), [q[0], -q[1], -q[2], -q[3]]).slice(1);
}

const world = [0, Math.SQRT1_2, Math.SQRT1_2, 0];
const body = [0, 1, 0, 0];

// Both basis changes are half turns. The same sandwich inverts the mapping.
function changeBasis(q) {
  const result = unit(multiply(multiply(world, q), body));
  return result[0] < 0 ? result.map((v) => -v) : result;
}
export function toRos(q) {
  const [w, x, y, z] = changeBasis(q);
  return [x, y, z, w];
}
export function fromRos([x, y, z, w]) {
  return changeBasis(unit([w, x, y, z]));
}

export function fromDegrees([roll, pitch, yaw]) {
  const [r, p, y] = [roll, pitch, yaw].map((v) => (v * Math.PI) / 360);
  return multiply(
    multiply(
      [Math.cos(y), 0, 0, Math.sin(y)],
      [Math.cos(p), 0, Math.sin(p), 0],
    ),
    [Math.cos(r), Math.sin(r), 0, 0],
  );
}
export function toDegrees(q) {
  const [w, x, y, z] = unit(q);
  const s = Math.max(-1, Math.min(1, 2 * (w * y - z * x)));
  const angles =
    Math.abs(s) > 1 - 1e-14
      ? [
          0,
          (Math.sign(s) * Math.PI) / 2,
          Math.atan2(2 * (w * z - x * y), 1 - 2 * (x * x + z * z)),
        ]
      : [
          Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
          Math.asin(s),
          Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)),
        ];
  return angles.map((v) => (v * 180) / Math.PI);
}
const decimal = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;
const number = (s) => (decimal.test(s.trim()) ? Number(s) : NaN);

export function readComponents(input) {
  let s = input.trim();
  if (s.startsWith("[") && s.endsWith("]")) s = s.slice(1, -1).trim();
  const parts = s.includes(",") ? s.split(",") : s.split(/\s+/);
  return parts.map(number);
}

export function parseQuaternion(input) {
  return unit(readComponents(input));
}

export function normNote(raw) {
  const norm = Math.hypot(...raw);
  if (!Number.isFinite(norm))
    return "Input norm exceeds numeric range. Display uses a unit quaternion.";
  const n = Number(norm.toPrecision(7));
  return (
    "Input norm " +
    n +
    " · distance from unit length " +
    Number(Math.abs(norm - 1).toPrecision(4))
  );
}

// Accept numeric attitude exports. Other columns are ignored.
export function parseTrack(csv) {
  const lines = csv
    .trim()
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/);
  const header = lines
    .shift()
    .split(",")
    .map((v) => v.trim().replace(/^"(.*)"$/, "$1"));
  const columns = ["timestamp", "q[0]", "q[1]", "q[2]", "q[3]"].map((k) =>
    header.indexOf(k),
  );
  if (columns.includes(-1))
    throw Error(
      "CSV needs timestamp and q[0] through q[3] from vehicle_attitude.",
    );
  const frameColumn = header.indexOf("pose_frame");
  const sampleColumn = header.indexOf("timestamp_sample");
  for (const name of [
    "timestamp",
    "timestamp_sample",
    "pose_frame",
    "q[0]",
    "q[1]",
    "q[2]",
    "q[3]",
  ]) {
    if (header.indexOf(name) !== header.lastIndexOf(name))
      throw Error("Duplicate CSV column " + name + ".");
  }
  const frames = [];
  let start, previous;
  for (const [i, line] of lines.entries()) {
    if (!line.trim()) continue;
    const fields = line.split(",");
    if (frameColumn >= 0 && number(fields[frameColumn] ?? "") !== 1)
      throw Error(
        "Line " +
          (i + 2) +
          " requires pose_frame=1 (NED) to display geographic heading.",
      );
    const [time, ...q] = columns.map((j) => number(fields[j] ?? ""));
    if (!Number.isSafeInteger(time) || time < 0 || time <= previous)
      throw Error(
        "Expected increasing microsecond timestamps on line " + (i + 2) + ".",
      );
    const sampleUs = sampleColumn < 0 ? 0 : number(fields[sampleColumn] ?? "");
    if (!Number.isSafeInteger(sampleUs) || sampleUs < 0)
      throw Error("Invalid timestamp_sample on line " + (i + 2) + ".");
    if (start === undefined) start = time;
    previous = time;
    try {
      frames.push({
        t: (time - start) / 1e6,
        timestampUs: time,
        sampleUs,
        raw: q,
        q: unit(q),
        norm: Math.hypot(...q),
      });
    } catch {
      throw Error("Invalid quaternion on line " + (i + 2) + ".");
    }
  }
  if (frames.length < 2) throw Error("Include at least two attitude samples.");
  return frames;
}
export function frameIndexAt(frames, time) {
  let lo = 0,
    hi = frames.length;
  while (lo + 1 < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (frames[mid].t <= time) lo = mid;
    else hi = mid;
  }
  return lo;
}
export function frameAt(frames, time) {
  return frames[frameIndexAt(frames, time)];
}

// A body-forward unit vector expressed in each world frame gives consumers
// a direct, sign-independent check for their bridge's output.
export function poseFixture(pose) {
  const q = unit(pose),
    [n, e, d] = rotate(q, [1, 0, 0]);
  return {
    schema: "attitude-atlas/pose-v1",
    px4: {
      body: "FRD",
      world: "NED",
      order: "wxyz",
      q,
      forward_in_world: [n, e, d],
    },
    ros: {
      body: "FLU",
      world: "ENU",
      order: "xyzw",
      q: toRos(q),
      forward_in_world: [e, n, -d],
    },
  };
}
