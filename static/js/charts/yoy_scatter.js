/* YoY 산점도 — 전년동월(x) vs 올해동월(y) + 45°선.
   TODO §C3.5 산출물.
*/
(function () {
  "use strict";

  function readJSON(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); }
    catch (e) { console.error("readJSON yoy", e); return null; }
  }

  function fmtNum(v) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function initYoYScatter() {
    const data = readJSON("yoy-data");
    const canvas = document.getElementById("yoy-chart");
    if (!data || !canvas || typeof Chart === "undefined") return;

    const points = data.points || [];
    const colors = points.map(p => p.current ? "#dc2626" : "#465fff");
    const radii  = points.map(p => p.current ? 7 : 4);

    const lineDataset = {
      label: "45°선 (전년 = 올해)",
      type: "line",
      data: [
        { x: data.axis_min, y: data.axis_min },
        { x: data.axis_max, y: data.axis_max },
      ],
      borderColor: "#9ca3af",
      borderDash: [5, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      order: 2,
    };

    new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "YoY 페어",
            data: points.map(p => ({ x: p.x, y: p.y, _ym: p.ym, _yoy: p.yoy_ym, _cur: p.current })),
            backgroundColor: colors,
            borderColor: colors,
            pointRadius: radii,
            pointHoverRadius: radii.map(r => r + 2),
            order: 1,
          },
          lineDataset,
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: true, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.datasetIndex !== 0) return `${ctx.dataset.label}`;
                const p = ctx.raw;
                const tag = p._cur ? " · 현재 기준월" : "";
                return `${p._yoy} → ${p._ym}: x=${fmtNum(p.x)}, y=${fmtNum(p.y)} ${data.unit}${tag}`;
              },
            },
          },
        },
        scales: {
          x: {
            min: data.axis_min, max: data.axis_max,
            title: { display: true, text: `전년동월 (${data.unit})` },
            ticks: { color: "#6b7280", callback: v => Number(v).toLocaleString() },
            grid: { color: "#f3f4f6" },
          },
          y: {
            min: data.axis_min, max: data.axis_max,
            title: { display: true, text: `올해동월 (${data.unit})` },
            ticks: { color: "#6b7280", callback: v => Number(v).toLocaleString() },
            grid: { color: "#f3f4f6" },
          },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", initYoYScatter);
})();
