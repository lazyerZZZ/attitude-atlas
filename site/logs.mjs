const $ = (id) => document.getElementById(id);
let worker = null;
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
  if (!demo && (!px || !ros || !$("common").checked)) {
    clear("Choose both recordings and confirm their common time base.");
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
      data.field;
    $("worst").hidden = !data.worst;
    if (data.worst)
      $("worst").href =
        "compare.html#" +
        new URLSearchParams({ pair: JSON.stringify(data.worst) });
    task.terminate();
    worker = null;
  };
  task.postMessage({ px, ros, skew });
}
$("capture").onsubmit = (e) => {
  e.preventDefault();
  run(false);
};
$("demo").onclick = () => run(true);
for (const id of ["px-file", "ros-file", "common", "skew"])
  $(id).oninput = () =>
    clear("Inputs changed. Run the comparison to update the result.");
run(true);
