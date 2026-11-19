const byId = id => document.getElementById(id);
const names = {reference: "Reference flight", ground_effect: "Ground-effect test"};
const actions = {training: "Training", insufficient_coverage: "Sparse window", within_budget: "Within budget",
  await_next_window: "Await next window", over_budget: "Over budget", recalibrate: "Switch confirmed"};
const verdicts = {insufficient_evidence: "Too little time to validate a fit", within_budget_on_scored_windows: "Initial fit stayed within budget",
  budget_exceeded_unconfirmed: "Budget exceeded, switch unconfirmed", recalibration_confirmed: "Recalibration confirmed"};
let dataset, current;

function draw() {
  if (!current || byId("trace").hidden) return;
  const canvas = byId("chart"), width = canvas.clientWidth, height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const budget = Number(byId("budget").value), windows = current.windows;
  const max = Math.max(budget, ...windows.flatMap(w => [w.fixed_p95_ms || 0, w.p95_ms || 0])) * 1.12;
  const span = windows.at(-1).end_s;
  const x = s => 46 + s / span * (width - 66);
  const y = ms => height - 30 - ms / max * (height - 48);
  ctx.font = "12px system-ui";
  ctx.fillStyle = "#34485a";
  for (const tick of [0, max/2, max]) {
    ctx.fillText(tick.toFixed(2), 3, y(tick) + 4);
    ctx.strokeStyle = "#d1dadd"; ctx.beginPath(); ctx.moveTo(44, y(tick)); ctx.lineTo(width - 16, y(tick)); ctx.stroke();
  }
  ctx.fillText("0 s", 44, height - 6);
  ctx.textAlign = "right"; ctx.fillText(span.toFixed(1) + " s", width - 12, height - 6);
  ctx.strokeStyle = "#a34c16"; ctx.setLineDash([5,4]); ctx.beginPath();
  ctx.moveTo(44, y(budget)); ctx.lineTo(width - 16, y(budget)); ctx.stroke(); ctx.setLineDash([]);
  for (const [field, color, radius] of [["fixed_p95_ms", "#7b848a", 4.5], ["p95_ms", "#00698a", 2.7]]) {
    ctx.strokeStyle = ctx.fillStyle = color; ctx.lineWidth = 1.6;
    let previous = null;
    for (const w of windows) {
      if (w[field] === undefined) { previous = null; continue; }
      const point = [x(w.end_s), y(w[field])];
      if (previous) {ctx.beginPath();ctx.moveTo(...previous);ctx.lineTo(...point);ctx.stroke();}
      ctx.beginPath();ctx.arc(...point,radius,0,2*Math.PI);ctx.fill();
      previous = point;
    }
  }
}
function update() {
  const c = dataset[byId("flight").value];
  current = c.budgets[byId("budget").value];
  const scored = current.windows.filter(w => w.p95_ms !== undefined);
  const changes = current.windows.filter(w => w.action === "recalibrate");
  byId("source-line").textContent = [c.board, c.pairs + " shared events", c.span_s.toFixed(2) + " s",
    (c.rate_ppm >= 0 ? "+" : "") + c.rate_ppm.toFixed(2) + " ppm"].join(" · ");
  byId("outcome").textContent = verdicts[current.verdict];
  byId("explanation").textContent = changes.length ? "Confirmed after " + changes.map(w => w.confirmed_s.toFixed(1) + " s").join(" and ") + "."
    : scored.length ? scored.length + " later windows evaluated at this budget."
    : "The capture ended before a later window could be scored.";
  byId("trace").hidden = !scored.length;
  byId("details").hidden = false;
  const rows = current.windows.map(w => {
    const tr = document.createElement("tr");
    for (const value of [w.end_s.toFixed(1), w.fixed_p95_ms?.toFixed(3) ?? "—",
      w.p95_ms?.toFixed(3) ?? "—", actions[w.action]]) {
      const td = document.createElement("td"); td.textContent = value; tr.append(td);
    }
    return tr;
  });
  byId("rows").replaceChildren(...rows); draw();
}
try {
  const response = await fetch("segment-replays.json");
  if (!response.ok) throw Error();
  dataset = await response.json();
  for (const key of Object.keys(dataset)) {
    const [,time,unit] = key.split("_");
    byId("flight").add(new Option(names[key] || `HALO ${unit} · ${time}`, key));
  }
  byId("flight").value = "halo_143210_D0016";
  for (const id of ["flight","budget"]) {byId(id).disabled = false;byId(id).onchange = update;}
  update();
  new ResizeObserver(draw).observe(byId("chart"));
} catch {
  byId("outcome").textContent = "Could not load the saved replay. Reload to retry.";
}
