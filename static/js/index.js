document.addEventListener("DOMContentLoaded", () => {
  const VIEW_TITLES = {
    overview: "Overview",
    offense: "Offense Analytics",
    heatmap: "Geospatial Heatmap",
    predict: "Predictions",
    ask: "Ask RideSafe",
  };
  const VALID_VIEWS = Object.keys(VIEW_TITLES);
  const VIEW_ALIASES = { map: "heatmap" };

  const searchResult = document.getElementById("search-result");
  const reportBtn = document.getElementById("report-btn");
  const heatMap = document.getElementById("heat-map");
  const monthName = document.getElementById("month-value");
  const totalValue = document.getElementById("total-value");
  const percentage = document.getElementById("percentage-value");
  const viewTitle = document.getElementById("view-title");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const sidebarBackdrop = document.getElementById("sidebar-backdrop");
  const navButtons = document.querySelectorAll(".sidebar-link[data-nav]");
  const viewPanels = document.querySelectorAll(".view-panel[data-view]");

  const api = (path) => path;

  function setSearchResultVisible(visible) {
    if (!searchResult) {
      return;
    }
    searchResult.hidden = !visible;
  }

  function notifyVizResize() {
    window.dispatchEvent(new Event("resize"));
    if (typeof Plotly !== "undefined") {
    document
      .querySelectorAll(
        "#view-offense:not([hidden]) #bar-graph .plotly-graph-div, #view-overview:not([hidden]) .donut-chart.active .plotly-graph-div, #view-predict:not([hidden]) #hour-risk-chart .plotly-graph-div, #hour-risk-chart.js-plotly-plot",
      )
      .forEach((el) => {
          try {
            Plotly.Plots.resize(el);
          } catch {
            /* plot may not be ready */
          }
        });
    }
    if (heatMap && !heatMap.closest(".view-panel")?.hidden) {
      const iframe = heatMap.querySelector("iframe");
      if (iframe) {
        try {
          iframe.contentWindow?.dispatchEvent(new Event("resize"));
        } catch {
          /* cross-origin or unloaded */
        }
        // Nudge layout after show
        const h = iframe.style.height;
        iframe.style.height = h || iframe.offsetHeight + "px";
        requestAnimationFrame(() => {
          iframe.style.height = h || "";
        });
      }
    }
  }

  function closeMobileSidebar() {
    document.body.classList.remove("sidebar-open");
    if (sidebarToggle) {
      sidebarToggle.setAttribute("aria-expanded", "false");
      sidebarToggle.setAttribute("aria-label", "Open navigation");
    }
    if (sidebarBackdrop) {
      sidebarBackdrop.hidden = true;
    }
  }

  function openMobileSidebar() {
    document.body.classList.add("sidebar-open");
    if (sidebarToggle) {
      sidebarToggle.setAttribute("aria-expanded", "true");
      sidebarToggle.setAttribute("aria-label", "Close navigation");
    }
    if (sidebarBackdrop) {
      sidebarBackdrop.hidden = false;
    }
  }

  function setView(name, { updateHistory = true } = {}) {
    const view = VALID_VIEWS.includes(name) ? name : "overview";

    viewPanels.forEach((panel) => {
      const match = panel.dataset.view === view;
      panel.hidden = !match;
      panel.classList.toggle("is-active", match);
    });

    navButtons.forEach((btn) => {
      const match = btn.dataset.nav === view;
      btn.classList.toggle("is-active", match);
      if (match) {
        btn.setAttribute("aria-current", "page");
      } else {
        btn.removeAttribute("aria-current");
      }
    });

    if (viewTitle) {
      viewTitle.textContent = VIEW_TITLES[view];
    }

    if (updateHistory) {
      const url = new URL(window.location.href);
      url.searchParams.delete("view");
      url.hash = view;
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }

    closeMobileSidebar();
    requestAnimationFrame(() => notifyVizResize());
  }

  function viewFromLocation() {
    const params = new URLSearchParams(window.location.search);
    let fromQuery = params.get("view");
    if (fromQuery && VIEW_ALIASES[fromQuery]) {
      fromQuery = VIEW_ALIASES[fromQuery];
    }
    if (fromQuery && VALID_VIEWS.includes(fromQuery)) {
      return fromQuery;
    }
    let hash = (window.location.hash || "").replace(/^#/, "");
    if (VIEW_ALIASES[hash]) {
      hash = VIEW_ALIASES[hash];
    }
    if (hash && VALID_VIEWS.includes(hash)) {
      return hash;
    }
    return "overview";
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.nav));
  });

  sidebarToggle?.addEventListener("click", () => {
    if (document.body.classList.contains("sidebar-open")) {
      closeMobileSidebar();
    } else {
      openMobileSidebar();
    }
  });

  sidebarBackdrop?.addEventListener("click", closeMobileSidebar);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) {
      closeMobileSidebar();
    }
  });

  window.addEventListener("hashchange", () => {
    setView(viewFromLocation(), { updateHistory: false });
  });

  setView(viewFromLocation(), { updateHistory: true });

  requestAnimationFrame(() => notifyVizResize());
  window.addEventListener("resize", () => {
    clearTimeout(window.__ridesafeResizeTimer);
    window.__ridesafeResizeTimer = setTimeout(() => notifyVizResize(), 150);
  });

  const donutCharts = document.querySelectorAll(".donut-chart");
  const yearPills = document.querySelectorAll(".year-pill[data-year]");
  const yearValue = document.getElementById("year-value");
  let currentYear = 2022;

  function setOverviewYear(year) {
    currentYear = year;
    donutCharts.forEach((chart) => {
      const match = Number(chart.dataset.year) === year;
      chart.classList.toggle("active", match);
    });
    yearPills.forEach((pill) => {
      const match = Number(pill.dataset.year) === year;
      pill.classList.toggle("is-active", match);
      pill.setAttribute("aria-pressed", String(match));
    });
    if (yearValue) {
      yearValue.textContent = String(year);
    }
    monthName.textContent = "—";
    totalValue.textContent = "0";
    percentage.textContent = "0%";
    document.querySelectorAll(".month-grid li").forEach((li) => {
      li.classList.remove("is-selected");
    });

    requestAnimationFrame(() => {
      notifyVizResize();
      const activeDonut = document.querySelector(
        ".donut-chart.active .plotly-graph-div",
      );
      if (activeDonut && typeof Plotly !== "undefined") {
        try {
          Plotly.Plots.resize(activeDonut);
        } catch {
          /* ignore */
        }
      }
    });
  }

  yearPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      setOverviewYear(Number(pill.dataset.year));
    });
  });

  // Legacy prev/next hooks (hidden) still work if present
  document.getElementById("left")?.addEventListener("click", () => {
    setOverviewYear(currentYear === 2022 ? 2024 : currentYear - 1);
  });
  document.getElementById("right")?.addEventListener("click", () => {
    setOverviewYear(currentYear === 2024 ? 2022 : currentYear + 1);
  });

  const monthBtns = document.getElementById("month-btns");
  const months = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
  ];

  months.forEach((month) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "month-chip";
    btn.textContent = month;
    btn.addEventListener("click", () => {
      monthBtns.querySelectorAll("li").forEach((el) => {
        el.classList.remove("is-selected");
      });
      li.classList.add("is-selected");
      fetchMonthData(currentYear, month);
    });
    li.appendChild(btn);
    monthBtns.appendChild(li);
  });

  // Default executive KPIs: January 2022 on first load
  const defaultMonthLi = monthBtns?.querySelector("li");
  if (defaultMonthLi) {
    defaultMonthLi.classList.add("is-selected");
  }
  fetchMonthData(2022, "JAN");
  loadCityInsights();

  const barangay = document.getElementById("brgy");
  const searchBox = document.getElementById("search-box");
  const resultBox = document.querySelector(".result-box");
  const suggestions = document.querySelector(".result-box ul");
  const hour = document.getElementById("hour");
  const searchBtn = document.getElementById("search");
  const barangayText = document.getElementById("brgy-value");
  const hourText = document.getElementById("hr-value");
  const percentageText = document.getElementById("percent-result");
  const insightPanel = document.getElementById("barangay-insight");
  const insightShare = document.getElementById("insight-share");
  const insightPeak = document.getElementById("insight-peak");
  const insightLowest = document.getElementById("insight-lowest");
  const insightQuarter = document.getElementById("insight-quarter");
  const insightIncidents = document.getElementById("insight-incidents");
  const insightRecs = document.getElementById("insight-recs");

  function fillRankList(listEl, rows, formatter) {
    if (!listEl) {
      return;
    }
    listEl.innerHTML = "";
    if (!rows || !rows.length) {
      const li = document.createElement("li");
      li.className = "rank-list__empty";
      li.textContent = "No data available.";
      listEl.appendChild(li);
      return;
    }
    rows.forEach((row, index) => {
      const li = document.createElement("li");
      const rank = document.createElement("span");
      rank.className = "rank-list__n";
      rank.textContent = String(index + 1);
      const body = document.createElement("div");
      body.className = "rank-list__body";
      const name = document.createElement("strong");
      name.textContent = row.barangay || "";
      const meta = document.createElement("span");
      meta.textContent = formatter(row);
      body.appendChild(name);
      body.appendChild(meta);
      li.appendChild(rank);
      li.appendChild(body);
      listEl.appendChild(li);
    });
  }

  function renderHourRiskChart(hourRisk) {
    const el = document.getElementById("hour-risk-chart");
    if (!el || !hourRisk || !hourRisk.length) {
      return;
    }
    const draw = () => {
      if (typeof Plotly === "undefined") {
        return;
      }
      const hours = hourRisk.map((row) => `${String(row.hour).padStart(2, "0")}:00`);
      const values = hourRisk.map((row) => row.avg_risk_percent);
      Plotly.newPlot(
        el,
        [
          {
            type: "bar",
            x: hours,
            y: values,
            marker: {
              color: values.map((v) =>
                v >= 55 ? "#2dd4bf" : v >= 40 ? "#5eead4" : "#1e3a5f",
              ),
            },
            hovertemplate: "%{x}<br>Avg risk: %{y:.2f}%<extra></extra>",
          },
        ],
        {
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          margin: { l: 40, r: 12, t: 12, b: 48 },
          height: 280,
          font: { color: "#94a3b8", family: "DM Sans, sans-serif" },
          xaxis: {
            tickangle: -45,
            dtick: 2,
            gridcolor: "rgba(124,205,244,0.08)",
            zeroline: false,
          },
          yaxis: {
            title: { text: "%", font: { size: 11 } },
            gridcolor: "rgba(124,205,244,0.08)",
            zeroline: false,
          },
        },
        { responsive: true, displayModeBar: false },
      );
    };
    if (typeof Plotly === "undefined") {
      setTimeout(draw, 400);
    } else {
      draw();
    }
  }

  function renderOffenseGuide(guide) {
    const intro = document.getElementById("offense-intro");
    const legal = document.getElementById("offense-legal");
    const topCallout = document.getElementById("offense-top");
    const list = document.getElementById("offense-glossary-list");
    if (!guide) {
      return;
    }
    if (intro && guide.intro) {
      intro.textContent = guide.intro;
    }
    if (legal && guide.legal_context) {
      legal.textContent = guide.legal_context;
    }
    if (topCallout) {
      if (guide.top_offense) {
        const top = guide.top_offense;
        topCallout.hidden = false;
        topCallout.textContent = `Largest category overall: ${top.chart_label} — ${top.short_label} (${Number(top.total_count).toLocaleString()} incidents).`;
      } else {
        topCallout.hidden = true;
      }
    }
    if (!list) {
      return;
    }
    list.innerHTML = "";
    (guide.items || []).forEach((item) => {
      const article = document.createElement("article");
      article.className = "offense-card";
      article.innerHTML = `
        <header class="offense-card__head">
          <span class="offense-card__badge">${item.chart_label}</span>
          <h3>${item.short_label}</h3>
        </header>
        <p class="offense-card__full">${item.offense_type}</p>
        <p class="offense-card__meta"><strong>Legal basis:</strong> ${item.legal_basis}</p>
        <p><strong>Meaning:</strong> ${item.meaning}</p>
        <p class="offense-card__insight"><strong>Insight:</strong> ${item.insight}</p>
        <p class="offense-card__counts">
          Totals — 2022: ${Number(item.by_year["2022"] || 0).toLocaleString()},
          2023: ${Number(item.by_year["2023"] || 0).toLocaleString()},
          2024: ${Number(item.by_year["2024"] || 0).toLocaleString()}
          (all years: ${Number(item.total_count || 0).toLocaleString()})
        </p>
      `;
      list.appendChild(article);
    });
  }

  async function loadCityInsights() {
    try {
      const res = await fetch(api("/api/dashboard/insights"));
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || res.statusText);
      }
      const kpis = data.city_kpis || {};
      const totalEl = document.getElementById("city-total-incidents");
      const yoyEl = document.getElementById("city-yoy");
      const peakEl = document.getElementById("city-peak-hour");
      const calmEl = document.getElementById("city-calm-hour");
      const peakHint = document.getElementById("city-peak-hour-hint");
      const calmHint = document.getElementById("city-calm-hour-hint");

      if (totalEl) {
        totalEl.textContent = Number(kpis.total_incidents || 0).toLocaleString();
      }
      if (yoyEl) {
        const yoy = kpis.yoy_change_percent;
        if (yoy == null) {
          yoyEl.textContent = "n/a";
        } else {
          const sign = yoy > 0 ? "+" : "";
          yoyEl.textContent = `${sign}${yoy}%`;
          yoyEl.classList.toggle("kpi-up", yoy > 0);
          yoyEl.classList.toggle("kpi-down", yoy < 0);
        }
      }
      if (peakEl && kpis.peak_city_hour) {
        peakEl.textContent = `${String(kpis.peak_city_hour.hour).padStart(2, "0")}:00`;
        if (peakHint) {
          peakHint.textContent = `Avg risk ${kpis.peak_city_hour.avg_risk_percent}%`;
        }
      }
      if (calmEl && kpis.calm_city_hour) {
        calmEl.textContent = `${String(kpis.calm_city_hour.hour).padStart(2, "0")}:00`;
        if (calmHint) {
          calmHint.textContent = `Avg risk ${kpis.calm_city_hour.avg_risk_percent}%`;
        }
      }

      fillRankList(
        document.getElementById("hotspot-list"),
        data.hotspots,
        (row) => `${Number(row.incident_count).toLocaleString()} incidents`,
      );
      fillRankList(
        document.getElementById("safest-list"),
        data.safest_by_volume,
        (row) => `${Number(row.incident_count).toLocaleString()} incidents`,
      );
      fillRankList(
        document.getElementById("peak-high-list"),
        data.highest_peak_risk,
        (row) =>
          `${row.peak_predicted_risk_percent}% at ${String(row.peak_hour).padStart(2, "0")}:00 (${row.risk_label})`,
      );
      fillRankList(
        document.getElementById("peak-low-list"),
        data.lowest_peak_risk,
        (row) =>
          `${row.peak_predicted_risk_percent}% at ${String(row.peak_hour).padStart(2, "0")}:00 (${row.risk_label})`,
      );
      renderHourRiskChart(data.hour_risk || []);
      renderOffenseGuide(data.offense_guide);
    } catch (error) {
      console.error("Error loading city insights: ", error);
    }
  }

  function hideBarangayInsight() {
    if (insightPanel) {
      insightPanel.hidden = true;
    }
  }

  function renderBarangayInsight(card) {
    if (!insightPanel || !card) {
      return;
    }
    if (insightShare) {
      insightShare.textContent = `${card.share_percent}% of city incidents (${Number(card.total_incidents).toLocaleString()} of ${Number(card.city_total).toLocaleString()})`;
    }
    if (insightPeak) {
      insightPeak.textContent = `${card.peak_hour}:00 · ${card.peak_percent}% (${card.peak_risk})`;
    }
    if (insightLowest) {
      insightLowest.textContent = `${card.lowest_hour}:00 · ${card.lowest_percent}% (${card.lowest_risk})`;
    }
    if (insightQuarter) {
      insightQuarter.textContent = card.peak_quarter || "n/a";
    }
    if (insightIncidents) {
      insightIncidents.textContent = Number(card.total_incidents || 0).toLocaleString();
    }
    if (insightRecs) {
      insightRecs.innerHTML = "";
      (card.recommendations || []).forEach((text) => {
        const li = document.createElement("li");
        li.textContent = text;
        insightRecs.appendChild(li);
      });
    }
    insightPanel.hidden = false;
  }

  async function fetchBarangayInsight(barangayName, hourValue) {
    try {
      const hourPart = hourValue ? hourValue.split(":")[0] : "";
      const url = api(
        `/api/dashboard/barangay-insight/${encodeURIComponent(barangayName)}${
          hourPart !== "" ? `?hour=${encodeURIComponent(hourPart)}` : ""
        }`,
      );
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || res.statusText);
      }
      renderBarangayInsight(data);
    } catch (error) {
      console.error("Error loading barangay insight: ", error);
      hideBarangayInsight();
    }
  }

  let barangayListCache = null;
  let lastReportBarangay = null;
  let lastReportHour = null;

  function hideSuggestions() {
    resultBox.hidden = true;
    suggestions.innerHTML = "";
  }

  function filterBarangays(list, input) {
    const inputClean = input.replace(/\s+/g, "");
    if (!inputClean.length) {
      return list;
    }

    return list.filter((keyword) => {
      const keywordClean = keyword.replace(/\s+/g, "");
      let matched = 0;

      for (let i = 0; i < inputClean.length; i++) {
        if (inputClean[i].toLowerCase() === keywordClean[i].toLowerCase()) {
          matched++;
        }
      }

      return matched === inputClean.length;
    });
  }

  function showSuggestions(matches) {
    if (!matches.length) {
      hideSuggestions();
      return;
    }

    resultBox.hidden = false;
    suggestions.style.overflowY = matches.length > 8 ? "scroll" : "hidden";
    suggestions.innerHTML = "";

    matches.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      li.setAttribute("role", "option");
      li.addEventListener("click", () => {
        barangay.value = item;
        hideSuggestions();
      });
      suggestions.appendChild(li);
    });
  }

  async function getBarangayListCached() {
    if (barangayListCache === null) {
      barangayListCache = await fetchBarangayList();
    }
    return barangayListCache;
  }

  searchBtn.addEventListener("click", () => {
    if (barangay.value === "" || hour.value === "hour") {
      return;
    }
    hideSuggestions();
    fetchAccidentPercentage(barangay.value, hour.value);
    setSearchResultVisible(true);
    requestAnimationFrame(() => notifyVizResize());
  });

  barangay.addEventListener("focus", async () => {
    const list = await getBarangayListCached();
    const input = barangay.value.trim();
    const matches = input.length ? filterBarangays(list, input) : list;
    showSuggestions(matches);
  });

  barangay.addEventListener("input", async () => {
    const list = await getBarangayListCached();
    const input = barangay.value;
    if (!input.length) {
      showSuggestions(list);
      return;
    }
    showSuggestions(filterBarangays(list, input));
  });

  document.addEventListener("mousedown", (e) => {
    if (!searchBox.contains(e.target)) {
      hideSuggestions();
    }
  });

  for (let i = 0; i < 24; i++) {
    const option = document.createElement("option");
    const hourFormatted = String(i).padStart(2, "0") + ":00";
    option.setAttribute("value", hourFormatted);
    option.textContent = hourFormatted;
    hour.appendChild(option);
  }

  function updateReportButtonState() {
    const ready =
      lastReportBarangay &&
      lastReportHour &&
      barangayText.textContent.trim() !== "" &&
      barangayText.textContent.trim().toLowerCase() !== "n/a";
    reportBtn.disabled = !ready;
    reportBtn.setAttribute("aria-disabled", String(!ready));
  }

  updateReportButtonState();

  reportBtn.addEventListener("click", () => {
    if (reportBtn.disabled || !lastReportBarangay) {
      return;
    }
    getSummaryReport(lastReportBarangay, lastReportHour);
  });

  async function getSummaryReport(barangayName, hourValue) {
    const params = new URLSearchParams();
    if (hourValue) {
      params.set("hour", hourValue.split(":")[0]);
    }
    const query = params.toString();
    const url = api(
      `/getSummaryReport/${encodeURIComponent(barangayName)}${query ? `?${query}` : ""}`,
    );

    const previousLabel = reportBtn.textContent;
    reportBtn.disabled = true;
    reportBtn.textContent = "Generating report…";

    try {
      const res = await fetch(url, { method: "GET" });
      if (res.ok) {
        const blob = await res.blob();
        let filename = "RideSafe_summary.pdf";
        const disposition = res.headers.get("Content-Disposition");
        if (disposition) {
          const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";\n]+)/i);
          if (match) {
            filename = decodeURIComponent(match[1].replace(/"/g, "").trim());
          }
        }
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
      } else {
        let message = res.statusText;
        try {
          const err = await res.json();
          if (err && err.error) {
            message = err.error;
          }
        } catch {
          /* ignore */
        }
        alert(`Could not generate report: ${message}`);
      }
    } catch (error) {
      console.error("Error fetching summary report: ", error);
      alert("Could not generate report. Please try again.");
    } finally {
      reportBtn.textContent = previousLabel;
      updateReportButtonState();
    }
  }

  async function fetchMonthData(year, month) {
    try {
      const response = await fetch(api("/getMonthData"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year, month }),
      });
      const monthData = await response.json();
      monthName.textContent = month;
      totalValue.textContent = monthData.totalAccidents;
      percentage.textContent = `${monthData.percentage}%`;
    } catch (error) {
      console.error("Error fetching month data: ", error);
    }
  }

  async function fetchAccidentPercentage(barangayValue, hourValue) {
    try {
      const response = await fetch(api("/predict"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          barangay: barangayValue.toUpperCase(),
          hour: hourValue,
        }),
      });

      const data = await response.json();
      barangayText.textContent = barangayValue.toUpperCase();
      hourText.textContent = `Hour: ${hourValue}`;
      if (!response.ok && data && typeof data === "object" && data.error) {
        percentageText.textContent = data.error;
        lastReportBarangay = null;
        lastReportHour = null;
        updateReportButtonState();
        hideBarangayInsight();
        return;
      }
      percentageText.textContent =
        typeof data === "string" ? data : String(data);
      lastReportBarangay = barangayValue.toUpperCase();
      lastReportHour = hourValue;
      updateReportButtonState();
      fetchBarangayInsight(barangayValue.toUpperCase(), hourValue);
    } catch (error) {
      console.error("Error fetching accident percentage: ", error);
    }
  }

  async function fetchBarangayList() {
    try {
      const response = await fetch(api("/getBarangayList"), {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Error fetcing barangay list: ", error);
      return [];
    }
  }
});
