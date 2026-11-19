import { errorPlot } from "./error-plot.mjs";
const $ = (id) => document.getElementById(id);
let worker = null;
const plot = errorPlot($("plot"), selectSample);
function selectSample(index) {
  if (!worker) return;
  $("sample").value = index;
  plot.mark(index);
  $("open-sample").hidden = true;
  worker.postMessage({ inspect: index });
}
$("sample").oninput = () => selectSample(Number($("sample").value));
function caseUrl(c) {
  return "compare.html#" + new URLSearchParams({ pair: JSON.stringify(c) });
}
function clear(text) {
  if (worker) {
    worker.terminate();
    worker = null;
  }
  $("results").hidden = true;
  $("status").textContent = text;
}
function angle(v) {
  return v === null ? "—" : v.toFixed(2) + "°";
}
function run(demo) {
  clear("");
  const px = demo ? null : $("px-file").files[0],
    ros = demo ? null : $("ros-file").files[0];
  const skew = Number($("skew").value);
  const anchor =
    !demo && $("anchored").checked
      ? { px: $("px-anchor").value, ros: $("ros-anchor").value }
      : null;
  if (!demo && (!px || !ros || (!$("common").checked && !anchor))) {
    clear("Choose both recordings and select how their clocks align.");
    return;
  }
  if (!$("skew").value.trim() || !Number.isFinite(skew) || skew < 0) {
    clear("Enter a nonnegative maximum skew.");
    return;
  }
  $("status").textContent = "Matching recorded attitudes…";
  const task = new Worker(new URL("recording-worker.mjs", import.meta.url), {
    type: "module",
  });
  worker = task;
  task.onerror = () => {
    if (worker === task)
      clear("Recording reader failed. Reload the page and try again.");
  };
  task.onmessage = ({ data }) => {
    if (worker !== task) return;
    if (data.error) {
      clear(data.error);
      return;
    }
    if (data.csv) {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(data.csv);
      a.download = "attitude-recording-rows.csv";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      return;
    }
    if (data.index !== undefined) {
      if (data.index !== Number($("sample").value)) return;
      const r = data.row;
      $("sample-info").textContent =
        "ROS sample " +
        (r.ri + 1) +
        " · header.stamp " +
        data.sourceStamp +
        " ns · nearest PX4 skew " +
        r.skewMs +
        " ms · " +
        (r.rotationDeg === null ? "outside window" : angle(r.rotationDeg));
      $("open-sample").hidden = !data.selected;
      if (data.selected) $("open-sample").href = caseUrl(data.selected);
      return;
    }
    $("results").hidden = false;
    $("status").textContent = "";
    $("source").textContent = demo
      ? "Synthetic roll-spike demo"
      : px.name + " / " + ros.name;
    const s = data.summary;
    $("coverage").textContent = s.matched + " / " + s.rosSamples;
    $("p95").textContent = angle(s.p95Deg);
    $("max").textContent = angle(s.maxDeg);
    $("detail").textContent =
      s.unmatched +
      " unmatched ROS samples · " +
      s.distinctPx4 +
      " distinct PX4 samples used out of " +
      s.px4Samples +
      " · PX4 time field: " +
      data.field +
      (data.offsetNs === null
        ? " · common clock"
        : " · subtracted " +
          data.offsetNs +
          " ns from ROS stamps for matching. Pair links retain original timestamps.");
    $("worst").hidden = !data.worst;
    if (data.worst) $("worst").href = caseUrl(data.worst);
    $("sample").max = s.rosSamples - 1;
    plot.set(data.times, data.angles, s.maxDeg);
    selectSample(data.worstIndex);
  };
  task.postMessage({ px, ros, skew, anchor });
}
$("capture").onsubmit = (e) => {
  e.preventDefault();
  run(false);
};
$("demo").onclick = () => run(true);
for (const id of [
  "px-file",
  "ros-file",
  "common",
  "anchored",
  "skew",
  "px-anchor",
  "ros-anchor",
]) {
  $(id).oninput = () => {
    if (id === "px-file" || id === "ros-file") {
      $("common").checked = $("anchored").checked = false;
      $("px-anchor").value = $("ros-anchor").value = "";
    }
    $("anchors").hidden = !$("anchored").checked;
    clear("Inputs changed. Run the comparison to update the result.");
  };
}
run(true);

$("rows-out").onclick = () => worker?.postMessage({ exportCsv: true });
