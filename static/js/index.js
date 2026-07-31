document.addEventListener("DOMContentLoaded", () => {
  const VIEW_TITLES = {
    overview: "Overview",
    offense: "Offense Analytics",
    map: "Map & Predictions",
    ask: "Ask RideSafe",
  };
  const VALID_VIEWS = Object.keys(VIEW_TITLES);

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
          "#view-offense:not([hidden]) #bar-graph .plotly-graph-div, #view-overview:not([hidden]) .donut-chart.active .plotly-graph-div",
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
    const fromQuery = params.get("view");
    if (fromQuery && VALID_VIEWS.includes(fromQuery)) {
      return fromQuery;
    }
    const hash = (window.location.hash || "").replace(/^#/, "");
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

  const barangay = document.getElementById("brgy");
  const searchBox = document.getElementById("search-box");
  const resultBox = document.querySelector(".result-box");
  const suggestions = document.querySelector(".result-box ul");
  const hour = document.getElementById("hour");
  const searchBtn = document.getElementById("search");
  const barangayText = document.getElementById("brgy-value");
  const hourText = document.getElementById("hr-value");
  const percentageText = document.getElementById("percent-result");

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
        return;
      }
      percentageText.textContent =
        typeof data === "string" ? data : String(data);
      lastReportBarangay = barangayValue.toUpperCase();
      lastReportHour = hourValue;
      updateReportButtonState();
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
