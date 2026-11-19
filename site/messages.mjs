import {load, CORE_SCHEMA} from "./vendor/js-yaml-5.5.0.mjs";
import {unit, readComponents, multiply, rotate, toRos, fromRos} from "./frames.mjs";

// Extract the attitude block explicitly. Positions, covariances and reset
// quaternions often contain equally plausible-looking numbers.
export function readMessage(text, system) {
  if (text.length > 65536) throw Error("Paste one message under 64 KiB.");
  const input = text.trim().replace(/(?:^|\n)---\s*$/, "").trim();
  let value;
  if (!input.includes(":") && !input.startsWith("- ") && !input.startsWith("---")) {
    value = readComponents(input);
  } else {
    try { value = load(input, {schema: CORE_SCHEMA, maxAliases: 0, maxDepth: 32}); }
    catch { throw Error("Paste one YAML or JSON message with numeric orientation fields."); }
  }
  if (!value || typeof value !== "object") throw Error("Paste four numbers or a supported message.");
  const isPx4 = system === "px4";
  let raw, source, stampNs = null, stampField = "", world = "", child = "";
  if (Array.isArray(value)) {
    raw = value;
    source = raw;
  } else if (isPx4) {
    if ("pose_frame" in value && value.pose_frame !== 1)
      throw Error("Geographic heading requires pose_frame=1 (NED). Align this world frame first.");
    raw = value.q;
    source = {q:raw};
    if ("pose_frame" in value) source.pose_frame = 1;
    for (const key of ["timestamp_sample","timestamp"]) {
      if (!(key in value)) continue;
      const n = value[key];
      if (!Number.isSafeInteger(n) || n < 0) throw Error("Invalid PX4 microsecond timestamp.");
      if (!n) continue;
      source[key] = n;
      stampNs = BigInt(n)*1000n;
      stampField = key;
      break;
    }
  } else {
    if (value.orientation_covariance?.[0] === -1) throw Error("The message marks its orientation as unavailable.");
    const orientation = value.pose?.pose?.orientation ?? value.pose?.orientation ?? value.orientation ?? value;
    raw = ["x","y","z","w"].map(k => orientation?.[k]);
    source = {orientation:Object.fromEntries(["x","y","z","w"].map((k,i)=>[k,raw[i]]))};
    world = value.header?.frame_id ?? "";
    child = value.child_frame_id ?? "";
    if ([world,child].some(id=>typeof id !== "string" || id.length > 256)) throw Error("Invalid ROS frame ID.");
    if (world) source.header = {frame_id:world};
    if (child) source.child_frame_id = child;
    const stamp = value.header?.stamp;
    if (stamp !== undefined) {
      if (!Number.isSafeInteger(stamp?.sec) || !Number.isInteger(stamp?.nanosec) ||
          stamp.nanosec < 0 || stamp.nanosec >= 1e9) throw Error("ROS stamp requires integer sec and nanosec in [0, 10⁹).");
      source.header = {...source.header, stamp:{sec:stamp.sec,nanosec:stamp.nanosec}};
      if (stamp.sec || stamp.nanosec) {
        stampNs = BigInt(stamp.sec)*1000000000n + BigInt(stamp.nanosec);
        stampField = "header.stamp";
      }
    }
  }
  if (!Array.isArray(raw)) throw Error("Expected a PX4 q array containing w, x, y, z.");
  return {raw, q:unit(raw), source, stampNs, stampField, world, child};
}

export function compareAttitudes(px4, ros, sharedClock=false) {
  const expected = toRos(px4.q), observed = ros.q;
  const [x,y,z,w] = expected;
  const relative = multiply([w,-x,-y,-z],[observed[3],...observed.slice(0,3)]);
  const degrees = 180 / Math.PI;
  const rotationDeg = 2*degrees*Math.atan2(Math.hypot(...relative.slice(1)), Math.abs(relative[0]));
  const [fx,fy,fz] = rotate(relative,[1,0,0]);
  const forwardDeg = degrees*Math.atan2(Math.hypot(fy,fz),fx);
  const timeOffsetMs = sharedClock && px4.stampNs !== null && ros.stampNs !== null
    ? Number(ros.stampNs - px4.stampNs)/1e6 : null;
  return {expected, observed, observedPx4:fromRos(observed), rotationDeg, forwardDeg, timeOffsetMs};
}
