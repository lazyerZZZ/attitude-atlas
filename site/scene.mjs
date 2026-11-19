import { rotate } from "./frames.mjs";

// Aircraft geometry is defined in body FRD. Faces are projected after rotation.
const faces = [];
const add = (points, color) => faces.push({ points, color });
function loft(stations, colors) {
  const rings = stations.map(([x, r, h, z]) =>
    Array.from({ length: 8 }, (_, i) => {
      const a = ((i + 0.5) * Math.PI) / 4;
      return [x, r * Math.cos(a), z + h * Math.sin(a)];
    }),
  );
  rings.slice(1).forEach((ring, j) =>
    ring.forEach((p, i) => {
      const k = (i + 1) % ring.length;
      add([rings[j][i], rings[j][k], ring[k], p], colors[j][i] ?? colors[j][0]);
    }),
  );
}
const hull = [
  "#8296ae",
  "#667c99",
  "#748ba6",
  "#9bacbe",
  "#d9e7ec",
  "#f9ffff",
  "#e5eff3",
  "#b2c6d3",
];
const blaze = [
  "#b6452a",
  "#aa4127",
  "#b9502d",
  "#e26235",
  "#f5884d",
  "#ffab72",
  "#ff995c",
  "#ed793e",
];
loft(
  [
    [-2.45, 0.045, 0.055, 0],
    [-0.8, 0.26, 0.24, 0],
    [0.82, 0.34, 0.34, 0],
    [1.55, 0.24, 0.23, 0.025],
    [2.05, 0.025, 0.025, 0.07],
  ],
  [hull, hull, hull, blaze],
);
loft(
  [
    [-0.25, 0.04, 0.02, -0.21],
    [0.48, 0.22, 0.18, -0.26],
    [1.21, 0.14, 0.05, -0.23],
  ],
  [
    [
      "#2c475c",
      "#2b435b",
      "#24425b",
      "#375b72",
      "#52778b",
      "#83aabb",
      "#577e91",
      "#3d617a",
    ],
    [
      "#2c475c",
      "#2b435b",
      "#24425b",
      "#375b72",
      "#52778b",
      "#83aabb",
      "#577e91",
      "#3d617a",
    ],
  ],
);

function foil(stations, top, underside) {
  for (const side of [-1, 1]) {
    stations.slice(1).forEach(([y2, front2, back2, z2], i) => {
      const [y, front, back, z] = stations[i];
      const edge = (x, s, h) => [x, side * s, h];
      const a = edge(front, y, z),
        b = edge(front2, y2, z2),
        c = edge(back2, y2, z2 + 0.04),
        d = edge(back, y, z + 0.04);
      const ridge = edge(front * 0.65 + back * 0.35, y, z - 0.09);
      const tip = edge(front2 * 0.65 + back2 * 0.35, y2, z2 - 0.06);
      add([a, b, tip, ridge], top[i][0]);
      add([ridge, tip, c, d], top[i][1]);
      add([a, b, c, d], underside[i]);
    });
  }
}
foil(
  [
    [0.1, 0.8, -0.59, -0.04],
    [2.9, 0.22, -0.69, -0.19],
    [3.28, 0.15, -0.68, -0.22],
    [3.72, 0.06, -0.58, -0.28],
  ],
  [
    ["#e9f4f9", "#c6dbe6"],
    ["#4f86b4", "#326893"],
    ["#ff9963", "#ed774a"],
  ],
  ["#95aabb", "#36688d", "#cc663f"],
);
foil(
  [
    [0.05, -1.53, -2.22, -0.01],
    [1.32, -1.94, -2.42, -0.1],
  ],
  [["#e3edf4", "#a9c2d5"]],
  ["#899eb7"],
);
add(
  [
    [-1.48, 0, -0.09],
    [-2.04, 0, -0.91],
    [-2.35, 0, -0.9],
    [-2.29, 0, 0],
  ],
  "#386889",
);
add(
  [
    [-1.96, 0, -0.78],
    [-2.04, 0, -0.91],
    [-2.35, 0, -0.9],
    [-2.34, 0, -0.78],
  ],
  "#ff9a67",
);

export function attitudeScene(canvas, onOrbit) {
  const ctx = canvas.getContext("2d");
  let az = 0.84,
    el = 0.55,
    q = [1, 0, 0, 0],
    axes = true,
    pointer = null;
  function draw() {
    const w = canvas.clientWidth,
      h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(w*dpr)) canvas.width = Math.round(w*dpr);
    if (canvas.height !== Math.round(h*dpr)) canvas.height = Math.round(h*dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0,0,w,h);
    const scale = Math.min(w / 10.6, h / 8.2);
    const cx = w / 2,
      cy = h * 0.45;
    const ca = Math.cos(az),
      sa = Math.sin(az),
      ce = Math.cos(el),
      se = Math.sin(el);
    const project = ([n, e, d]) => [
      cx + scale * (-sa * n + ca * e),
      cy + scale * (se * (ca * n + sa * e) + ce * d),
      ce * (ca * n + sa * e) - se * d,
    ];
    const at = (angle, r, z) => [Math.cos(angle) * r, Math.sin(angle) * r, z];
    function path(points, stroke, fill, weight = 1) {
      ctx.beginPath();
      points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (fill) {
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();
      }
      if (stroke) {
        ctx.lineWidth = weight;
        ctx.strokeStyle = stroke;
        ctx.stroke();
      }
    }
    const ground = 1.25;
    for (let i = -10; i <= 10; i++) {
      path(
        [
          [i, -12, ground],
          [i, 12, ground],
        ].map(project),
        "#c5d9e2",
      );
      path(
        [
          [-12, i, ground],
          [12, i, ground],
        ].map(project),
        "#c5d9e2",
      );
    }
    path(
      Array.from({ length: 121 }, (_, i) =>
        project(at((i * Math.PI) / 60, 4.12, ground)),
      ),
      "#8ba7b9",
      null,
      1.4,
    );
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "bold 13px system-ui";
    for (let i = 0; i < 72; i++) {
      const a = (i * Math.PI) / 36;
      path(
        [
          project(at(a, i % 6 ? 4.04 : 3.91, ground)),
          project(at(a, 4.12, ground)),
        ],
        "#7f9cb0",
      );
      if (i % 18 === 0) {
        ctx.fillStyle = "#385974";
        const [x, y] = project(at(a, 4.43, ground));
        ctx.fillText(["N", "E", "S", "W"][i / 18], x, y);
      }
    }
    const polys = faces.map((f) => {
      const world = f.points.map((v) => rotate(q, v));
      const points = world.map(project);
      return {
        points,
        world,
        color: f.color,
        depth: points.reduce((s, p) => s + p[2], 0) / points.length,
      };
    });
    ctx.save();
    ctx.globalAlpha = 0.11;
    ctx.beginPath();
    // Use a single composited shadow to keep the silhouette legible.
    for (const poly of polys) {
      const pts = poly.world.map(([n, e]) =>
        project([n + 0.15, e + 0.12, ground]),
      );
      const area = pts.reduce((s, p, i) => {
        const u = pts[(i + 1) % pts.length];
        return s + p[0] * u[1] - u[0] * p[1];
      }, 0);
      if (area < 0) pts.reverse();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
    }
    ctx.fillStyle = "#24476a";
    ctx.fill();
    ctx.restore();
    polys.sort((a, b) => a.depth - b.depth);
    polys.forEach((f) => path(f.points, "#536f8170", f.color, 0.65));
    if (axes) {
      const colors = ["#ac3d22", "#19624c", "#344eaa"];
      [
        [3.05, 0, 0],
        [0, 4.0, 0],
        [0, 0, 1.77],
      ].forEach((v, i) => {
        const end = project(rotate(q, v)),
          base = project([0, 0, 0]);
        ctx.setLineDash([4, 3]);
        path([base, end], colors[i], null, 1.5);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.arc(end[0], end[1], 8, 0, 2 * Math.PI);
        ctx.fillStyle = colors[i];
        ctx.fill();
        ctx.fillStyle = "white";
        ctx.font = "bold 10px system-ui";
        ctx.fillText("FRD"[i], end[0], end[1]);
      });
    }
  }
  canvas.onpointerdown = (e) => {
    pointer = [e.clientX, e.clientY];
    canvas.setPointerCapture(e.pointerId);
  };
  canvas.onpointermove = (e) => {
    if (!pointer) return;
    az -= (e.clientX - pointer[0]) * 0.009;
    el = Math.max(0.15, Math.min(1.52, el + (e.clientY - pointer[1]) * 0.008));
    pointer = [e.clientX, e.clientY];
    draw();
    onOrbit?.(az,el);
  };
  canvas.onlostpointercapture = () => {
    pointer = null;
  };
  new ResizeObserver(draw).observe(canvas);
  return {
    pose(value) {
      q = value;
      draw();
    },
    axes(value) {
      axes = value;
      draw();
    },
    reset() {
      az = 0.84;
      el = 0.55;
      draw();
    },
    camera(azimuth,elevation) { az=azimuth; el=elevation; draw(); },
    orbit(dx, dy) {
      az += dx;
      el = Math.max(0.15, Math.min(1.52, el + dy));
      draw();
      onOrbit?.(az,el);
    },
  };
}
