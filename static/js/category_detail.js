/* 카테고리 상세 — 헤드라인 시계열(밴드), 3M×12M 사분면, 차원분해 multi-line. */
(function () {
  "use strict";

  // 색맹친화 팔레트 (Tableau 10 비슷)
  const PALETTE = ["#465fff", "#ef8a62", "#67a9cf", "#fdae61", "#2c7bb6", "#d7191c",
                   "#7570b3", "#1b9e77", "#e7298a"];

  function readJSON(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); }
    catch (e) { console.error("readJSON", id, e); return null; }
  }

  function sigColor(sig) {
    switch (sig) {
      case "strong_positive": return "#1d4ed8";
      case "weak_positive":   return "#3b82f6";
      case "no_change":       return "#9ca3af";
      case "weak_negative":   return "#fb923c";
      case "strong_negative": return "#dc2626";
      default:                return "#d1d5db";
    }
  }

  // ── 1. 헤드라인 시계열 + 1σ 밴드 ─────────────────────
  function initTimeseries() {
    const data = readJSON("ts-data");
    const canvas = document.getElementById("ts-chart");
    if (!data || !canvas || typeof Chart === "undefined") return;

    const datasets = [
      {
        label: "헤드라인",
        data: data.values,
        borderColor: "#465fff",
        backgroundColor: "transparent",
        borderWidth: 2,
        tension: 0.2,
        pointRadius: 2,
        pointHoverRadius: 5,
        order: 1,
      },
      {
        label: "12M 이동평균",
        data: data.rolling_mean,
        borderColor: "#9ca3af",
        borderDash: [4, 3],
        borderWidth: 1.5,
        pointRadius: 0,
        spanGaps: false,
        order: 2,
      },
      {
        label: "+1σ",
        data: data.band_upper,
        borderColor: "rgba(70, 95, 255, 0.05)",
        backgroundColor: "rgba(70, 95, 255, 0.1)",
        borderWidth: 0,
        pointRadius: 0,
        fill: "+1",
        spanGaps: false,
        order: 3,
      },
      {
        label: "-1σ",
        data: data.band_lower,
        borderColor: "rgba(70, 95, 255, 0.05)",
        backgroundColor: "transparent",
        borderWidth: 0,
        pointRadius: 0,
        fill: false,
        spanGaps: false,
        order: 4,
      },
    ];

    new Chart(canvas, {
      type: "line",
      data: { labels: data.labels, datasets },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y == null ? "—" : Number(ctx.parsed.y).toLocaleString()}` } },
        },
        scales: {
          x: { ticks: { color: "#6b7280", autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          y: { ticks: { color: "#6b7280", callback: v => Number(v).toLocaleString() }, grid: { color: "#f3f4f6" } },
        },
      },
    });
  }

  // ── 2. 단기·장기 모멘텀 시계열 (사분면 대체) ──────────
  function initTrendSeries() {
    const data = readJSON("trend-data");
    const canvas = document.getElementById("trend-chart");
    if (!data || !canvas || typeof Chart === "undefined") return;

    const datasets = [
      {
        label: "단기 모멘텀 (3M-3M, %)",
        data: data.short,
        borderColor: "#465fff",
        backgroundColor: "rgba(70,95,255,0.08)",
        borderWidth: 2,
        tension: 0.2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: false,
      },
      {
        label: "장기 모멘텀 (12M-12M, %)",
        data: data.long,
        borderColor: "#dc2626",
        backgroundColor: "rgba(220,38,38,0.06)",
        borderWidth: 2,
        borderDash: data.long_disabled ? [2, 4] : [],
        tension: 0.2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: false,
        hidden: data.long_disabled,
      },
    ];

    new Chart(canvas, {
      type: "line",
      data: { labels: data.labels, datasets },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y == null ? "—" : ctx.parsed.y.toFixed(2) + "%"}` } },
        },
        scales: {
          x: { ticks: { color: "#6b7280", autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          y: {
            title: { display: true, text: "변화율 %" },
            ticks: { color: "#6b7280", callback: v => v + "%" },
            grid: { color: ctx => ctx.tick.value === 0 ? "#9ca3af" : "#f3f4f6" },
          },
        },
      },
    });
  }

  // ── 3. 차원분해 multi-line ──────────────────────────
  function initBreakdown() {
    const data = readJSON("bd-data");
    const canvas = document.getElementById("breakdown-chart");
    if (!data || !canvas || typeof Chart === "undefined") return;

    const datasets = (data.items || []).map((it, i) => ({
      label: it.name,
      data: it.series,
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: "transparent",
      borderWidth: 1.6,
      tension: 0.2,
      pointRadius: 0,
      pointHoverRadius: 4,
      spanGaps: true,
    }));

    new Chart(canvas, {
      type: "line",
      data: { labels: data.labels_ym, datasets },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } },
          tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y == null ? "—" : Number(ctx.parsed.y).toLocaleString()}` } },
        },
        scales: {
          x: { ticks: { color: "#6b7280", autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          y: { ticks: { color: "#6b7280", callback: v => Number(v).toLocaleString() }, grid: { color: "#f3f4f6" } },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTimeseries();
    initTrendSeries();
    initBreakdown();
  });
})();
