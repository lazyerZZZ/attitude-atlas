import {
  fromDegrees,
  toDegrees,
  toRos,
  fromRos,
  parseQuaternion, normNote,
  parseTrack,
  frameAt,
  poseFixture,
} from "./frames.mjs";
import {readMessage} from "./messages.mjs";
import { attitudeScene } from "./scene.mjs";

const $ = (id) => document.getElementById(id);
const scene = attitudeScene($("aircraft"));
const poses = {
  bank: [18, 8, 15],
  north: [0, 0, 0],
  east: [0, 0, 90],
  vertical: [0, 90, 0],
};
let q = fromDegrees(poses.bank),
  mode = "angles",
  timer;
const sliderNames = ["Roll", "Pitch", "Yaw"];
const sliders = sliderNames.map((name, i) => {
  const limit = i === 1 ? 90 : 180,
    row = document.createElement("div");
  row.className = "range";
  row.innerHTML =
    '<label for="slider-' +
    i +
    '">' +
    name +
    '<output></output></label><input type="range" id="slider-' +
    i +
    '" step="0.1" min="' +
    -limit +
    '" max="' +
    limit +
    '">';
  $("sliders").append(row);
  return row.querySelector("input");
});
const formatNumber = (v) => (Math.abs(v) < 0.0000005 ? 0 : v).toFixed(6);
function readout(id, order, values) {
  const dl = $(id + "-values");
  if (!dl.children.length) {
    for (const letter of order) {
      const cell = document.createElement("div"),
        key = document.createElement("dt");
      key.textContent = letter;
      cell.append(key, document.createElement("dd"));
      dl.append(cell);
    }
  }
  values.forEach(
    (v, i) => (dl.children[i].lastChild.textContent = formatNumber(v)),
  );
}
function render(value, angles = toDegrees(value)) {
  q = value;
  sliders.forEach((s, i) => {
    s.value = angles[i];
    s.parentNode.querySelector("output").value =
      Number(Number(s.value).toFixed(1)) + "°";
  });
  readout("px4", "wxyz", q);
  readout("ros", "xyzw", toRos(q));
  scene.pose(q);
}
function applyPreset() {
  const angles = poses[$("preset").value];
  render(fromDegrees(angles), angles);
}
$("preset").onchange = applyPreset;
sliders.forEach(
  (s) =>
    (s.oninput = () => {
      const angles = sliders.map((s) => Number(s.value));
      $("preset").value = "custom";
      render(fromDegrees(angles), angles);
    }),
);
$("axes").onchange = () => scene.axes($("axes").checked);
$("reset-view").onclick = () => scene.reset();
$("aircraft").onkeydown = (e) => {
  const step = {
    ArrowLeft: [-0.13, 0],
    ArrowRight: [0.13, 0],
    ArrowUp: [0, 0.12],
    ArrowDown: [0, -0.12],
  }[e.key];
  if (step) {
    e.preventDefault();
    scene.orbit(...step);
  }
};
function notice(message) {
  clearTimeout(timer);
  $("notice").textContent = message;
  timer = setTimeout(() => ($("notice").textContent = ""), 2700);
}
async function copy(value, message) {
  try {
    await navigator.clipboard.writeText(value);
    notice(message);
  } catch {
    window.prompt("Select and copy this value", value);
  }
}
$("export").onclick = () => {
  const blob = new Blob([JSON.stringify(poseFixture(q), null, 2) + "\n"], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "attitude-atlas-pose.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};
function formatted(values) {
  return "[" + values.map(formatNumber).join(", ") + "]";
}
document.querySelectorAll("[data-copy]").forEach(
  (b) =>
    (b.onclick = () => {
      const px4 = b.dataset.copy === "px4";
      copy(
        formatted(px4 ? q : toRos(q)),
        px4 ? "PX4 quaternion copied" : "ROS quaternion copied",
      );
    }),
);
$("share").onclick = () => {
  const url = new URL(location.href);
  url.hash = "q=" + q.map((v) => Number(v.toPrecision(12))).join(",");
  copy(url.href, "Pose link copied");
};
$("apply").onclick = () => {
  try {
    const {raw, q:values} = readMessage($("input").value,$("format").value);
    $("input-norm").textContent = normNote(raw);
    $("preset").value = "custom";
    render($("format").value === "px4" ? values : fromRos(values));
    $("error").textContent = "";
    notice("Attitude updated");
  } catch (e) {
    $("input-norm").textContent = "";
    $("error").textContent = e.message;
  }
};
let hasDraft = false;
$("input").oninput = () => {
  hasDraft = true;
  $("input-norm").textContent = $("error").textContent = "";
};
$("format").onchange = () => {
  if (!hasDraft) $("input").value = formatted($("format").value === "px4" ? q : toRos(q));
  $("input-norm").textContent = $("error").textContent = "";
};

let track = [],
  position = 0,
  animation = null,
  sample = true,
  loadId = 0;
function setPlayLabel() {
  $("play").textContent =
    animation !== null ? "Pause" : sample ? "Play sample" : "Play track";
}
function stop() {
  if (animation !== null) cancelAnimationFrame(animation);
  animation = null;
  setPlayLabel();
}
function seek(t) {
  position = t;
  $("timeline").value = t;
  $("clock").value = t.toFixed(2) + " / " + track.at(-1).t.toFixed(2) + " s";
  $("preset").value = "custom";
  const frame = frameAt(track, t);
  $("track-norm").textContent = "Sample norm " + Number(frame.norm.toPrecision(7));
  render(frame.q);
}
function installTrack(frames, name, isSample) {
  stop();
  track = frames;
  sample = isSample;
  position = 0;
  $("track-name").textContent = name;
  $("timeline").max = track.at(-1).t;
  $("play").disabled = $("timeline").disabled = false;
  $("error").textContent = "";
  setPlayLabel();
  if (mode === "track") seek(0);
}
function startLoading() {
  stop();
  $("play").disabled = $("timeline").disabled = true;
  $("error").textContent = "";
  return ++loadId;
}
function loadFailed(id,message) {
  if(id !== loadId)return;
  $("play").disabled = $("timeline").disabled = !track.length;
  $("error").textContent=message+(track.length ? " Current track: "+$("track-name").textContent+"." : "");
}
async function loadSample() {
  const id = startLoading();
  try {
    const response = await fetch("sample.csv");
    if (!response.ok) throw Error("Sample could not be loaded.");
    const frames = parseTrack(await response.text());
    if (id === loadId) installTrack(frames, "PX4 sample log", true);
  } catch {
    loadFailed(id, "Sample unavailable. Open a vehicle_attitude CSV to replay it.");
  }
}
$("play").onclick = () => {
  if (animation !== null) {
    stop();
    return;
  }
  const end = track.at(-1).t;
  if (position >= end) seek(0);
  const origin = performance.now() - position * 1000;
  function tick(now) {
    seek(Math.min(end, (now - origin) / 1000));
    if (position >= end) stop();
    else animation = requestAnimationFrame(tick);
  }
  animation = requestAnimationFrame(tick);
  setPlayLabel();
};
$("timeline").oninput = () => {
  stop();
  seek(Number($("timeline").value));
};
$("use-sample").onclick = loadSample;
$("open-file").onclick = () => $("file").click();
$("file").onchange = async () => {
  const file = $("file").files[0];
  if (!file) return;
  const id = startLoading();
  try {
    if (file.size > 16 * 1024 * 1024)
      throw Error("Choose a CSV smaller than 16 MiB.");
    const frames = parseTrack(await file.text());
    if (id === loadId) installTrack(frames, file.name, false);
  } catch (e) {
    loadFailed(id,e.message);
  }
  $("file").value = "";
};
document.querySelectorAll("[data-mode]").forEach(
  (button) =>
    (button.onclick = () => {
      if (mode === button.dataset.mode) return;
      stop();
      mode = button.dataset.mode;
      $("error").textContent = "";
      document.querySelectorAll("[data-mode]").forEach((b) => {
        const active = b.dataset.mode === mode;
        $(b.dataset.mode).hidden = !active;
        b.setAttribute("aria-pressed", active);
      });
      if (mode === "paste" && !hasDraft)
        $("input").value = formatted(
          $("format").value === "px4" ? q : toRos(q),
        );
      if (mode === "track") {
        if (track.length) seek(position);
        else loadSample();
      }
    }),
);
function readLink() {
  if (!location.hash.startsWith("#q=")) return false;
  try {
    const pose = parseQuaternion(decodeURIComponent(location.hash.slice(3)));
    stop();
    $("preset").value = "custom";
    render(pose);
    return true;
  } catch {
    $("error").textContent =
      "Invalid pose link. Choose an example or enter four quaternion components.";
    return false;
  }
}
window.addEventListener("hashchange", readLink);
if (!readLink()) applyPreset();
