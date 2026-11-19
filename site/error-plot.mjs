// Render individual observations at their recorded times. Coincident x pixels
// are overplotted, retaining the vertical positions of short error spikes.
export function errorPlot(canvas, select) {
  const ctx = canvas.getContext("2d");
  let times = [],
    angles = [],
    peak = 1,
    index = 0;
  const left = 48,
    right = 14,
    top = 12,
    bottom = 26;
  function draw() {
    const width = canvas.clientWidth,
      height = canvas.clientHeight;
    if (!width || !height || !times.length) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const w = width - left - right,
      h = height - top - bottom;
    const xmax = times.at(-1) || 1;
    const x = (i) => left + (w * times[i]) / xmax,
      y = (a) => top + h * (1 - a / peak);
    ctx.font = "12px system-ui";
    ctx.fillStyle = "#42596d";
    for (const v of [0, peak / 2, peak]) {
      ctx.fillText(Number(v.toFixed(2)) + "°", 2, y(v) + 3);
      ctx.fillStyle = "#ccdbe1";
      ctx.fillRect(left, y(v), w, 1);
      ctx.fillStyle = "#42596d";
    }
    ctx.fillText("0 s", left, height - 4);
    ctx.textAlign = "right";
    ctx.fillText(
      Number(times.at(-1).toFixed(4)) + " s",
      width - right,
      height - 4,
    );
    ctx.textAlign = "left";
    ctx.fillStyle = "#7f92a1";
    ctx.fillRect(x(index), top, 1, h);
    for (let i = 0; i < times.length; i++) {
      if (Number.isNaN(angles[i])) {
        ctx.fillStyle = "#ac491d";
        ctx.fillRect(x(i) - 1, y(0) + 4, 3, 4);
      } else {
        ctx.fillStyle = "#195e82";
        ctx.fillRect(x(i) - 1.5, y(angles[i]) - 1.5, 3, 3);
      }
    }
  }
  canvas.onclick = (e) => {
    if (!times.length) return;
    const t =
      ((e.clientX - canvas.getBoundingClientRect().left - left) /
        (canvas.clientWidth - left - right)) *
      (times.at(-1) || 1);
    let lo = 0,
      hi = times.length - 1;
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (times[mid] < t) lo = mid + 1;
      else hi = mid;
    }
    select(
      lo && Math.abs(times[lo - 1] - t) <= Math.abs(times[lo] - t)
        ? lo - 1
        : lo,
    );
  };
  new ResizeObserver(draw).observe(canvas);
  return {
    set(t, a, max) {
      times = t;
      angles = a;
      peak = Math.max(1, max || 0);
      index = 0;
      draw();
    },
    mark(i) {
      index = i;
      draw();
    },
  };
}
