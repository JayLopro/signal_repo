/* 메인 대시보드 — Chart.js 레이더 + Leaflet Choropleth + Top N 토글
   decisions.md §4 (레이더 매핑), §5-2 (Choropleth + 6축 레이더 + TopN).
*/
(function () {
  "use strict";

  // ── 시그널 색 (색맹친화 RdBu 5단계) ─────────────────────
  function scoreColor(score) {
    if (score === null || score === undefined || Number.isNaN(score)) return "#e5e7eb";
    if (score <= -1.5) return "#b2182b";
    if (score <= -0.5) return "#ef8a62";
    if (score <   0.5) return "#f7f7f7";
    if (score <   1.5) return "#67a9cf";
    return "#2166ac";
  }
  function scoreLabel(score) {
    if (score === null || score === undefined) return "표본 부족";
    if (score <= -1.5) return "강한 부정";
    if (score <= -0.5) return "약한 부정";
    if (score <   0.5) return "변화 없음";
    if (score <   1.5) return "약한 긍정";
    return "강한 긍정";
  }

  function readJSON(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); }
    catch (e) { console.error("readJSON failed:", id, e); return null; }
  }

  // ── 6축 레이더 ─────────────────────────────────────────
  function initRadar() {
    const data = readJSON("radar-data");
    const canvas = document.getElementById("radar-chart");
    if (!data || !canvas || typeof Chart === "undefined") return;

    const values    = data.values || [];
    const insuffMap = data.insufficient || [];
    const pointColors = insuffMap.map(i => i ? "#9ca3af" : "#2563eb");

    new Chart(canvas, {
      type: "radar",
      data: {
        labels: data.labels || [],
        datasets: [{
          label: "신호 강도",
          data: values,
          fill: true,
          backgroundColor: "rgba(70, 95, 255, 0.15)",
          borderColor: "#465fff",
          borderWidth: 2,
          pointBackgroundColor: pointColors,
          pointRadius: 4,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const insuf = insuffMap[ctx.dataIndex];
                return insuf
                  ? `${ctx.label}: 표본 부족`
                  : `${ctx.label}: ${ctx.formattedValue} (${scoreLabel(ctx.parsed.r)})`;
              },
            },
          },
        },
        scales: {
          r: {
            suggestedMin: -2, suggestedMax: 2,
            ticks: { stepSize: 1, color: "#6b7280" },
            pointLabels: { font: { size: 11 }, color: "#374151" },
            grid: { color: "#e5e7eb" },
            angleLines: { color: "#e5e7eb" },
          },
        },
      },
    });
  }

  // ── Choropleth (TopoJSON → GeoJSON 변환 + 8자리 코드 정규화) ─
  function normalizeCd(code) {
    // background.json은 10자리(`...00`), CSV는 8자리. 8자리 표준 (decisions.md §2)
    let s = String(code);
    if (s.length === 10 && s.endsWith("00")) s = s.substring(0, 8);
    return s;
  }

  function initMap() {
    const data = readJSON("choropleth-data");
    const mapEl = document.getElementById("choro-map");
    if (!data || !mapEl || typeof L === "undefined" || typeof topojson === "undefined") return;

    const topoUrl = mapEl.dataset.topojsonUrl || "/geo/admdong/";
    fetch(topoUrl)
      .then(r => r.json())
      .then(topo => {
        const objKey = Object.keys(topo.objects)[0];
        const geo = topojson.feature(topo, topo.objects[objKey]);

        const map = L.map(mapEl, { zoomControl: true, attributionControl: false });
        const layer = L.geoJSON(geo, {
          style: (feat) => {
            const cd = normalizeCd(feat.properties["행정동코드"]);
            const entry = data[cd];
            const score = entry ? entry.score : null;
            return {
              fillColor: scoreColor(score),
              weight: 1,
              color: "#4b5563",
              fillOpacity: score === null ? 0.45 : 0.78,
              dashArray: score === null ? "3 3" : "",
            };
          },
          onEachFeature: (feat, l) => {
            const cd = normalizeCd(feat.properties["행정동코드"]);
            const entry = data[cd] || { score: null, n: 0, nm: feat.properties["읍면동명"] };
            const nm = entry.nm || feat.properties["읍면동명"];
            const scoreTxt = entry.score === null ? "—" : entry.score.toFixed(2);
            l.bindTooltip(
              `<b>${nm}</b><br/>종합 점수: ${scoreTxt} (${scoreLabel(entry.score)})<br/>유효 카테고리: ${entry.n}/6`,
              { className: "signal-tooltip", sticky: true }
            );
          },
        }).addTo(map);
        map.fitBounds(layer.getBounds(), { padding: [10, 10] });
      })
      .catch(err => {
        console.error("Choropleth fetch failed:", err);
        mapEl.innerHTML = '<div class="flex h-full items-center justify-center text-sm text-gray-400">지도 로드 실패</div>';
      });
  }

  // ── TopN 5/10 토글 ─────────────────────────────────────
  function initTopNToggle() {
    const btns = document.querySelectorAll(".topn-toggle");
    const rows = document.querySelectorAll(".topn-row");
    const label = document.getElementById("top-n-label");
    btns.forEach(b => b.addEventListener("click", () => {
      const n = parseInt(b.dataset.topn, 10);
      btns.forEach(x => {
        x.classList.remove("bg-brand-50", "text-brand-700", "font-semibold");
      });
      b.classList.add("bg-brand-50", "text-brand-700", "font-semibold");
      rows.forEach(r => {
        const rank = parseInt(r.dataset.rank, 10);
        r.style.display = rank <= n ? "" : "none";
      });
      if (label) label.textContent = n;
    }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initRadar();
    initMap();
    initTopNToggle();
  });
})();
