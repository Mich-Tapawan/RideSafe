document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("toggle-btn");
  const barGraph = document.getElementById("bar-graph");
  const heatMap = document.getElementById("heat-map");
  const searchResult = document.getElementById("search-result");
  const reportBtn = document.getElementById("report-btn");

  const monthName = document.getElementById("month-value");
  const totalValue = document.getElementById("total-value");
  const percentage = document.getElementById("percentage-value");

  const api = (path) => path;

  function setSearchResultVisible(visible) {
    searchResult.hidden = !visible;
  }

  function notifyVizResize() {
    window.dispatchEvent(new Event("resize"));
    if (typeof Plotly === "undefined") {
      return;
    }
    document
      .querySelectorAll(
        "#bar-graph:not([hidden]) .plotly-graph-div, #heat-map:not([hidden]) .plotly-graph-div, .donut-chart.active .plotly-graph-div",
      )
      .forEach((el) => {
        try {
          Plotly.Plots.resize(el);
        } catch {
          /* plot may not be ready */
        }
      });
  }

  requestAnimationFrame(() => notifyVizResize());
  window.addEventListener("resize", () => {
    clearTimeout(window.__ridesafeResizeTimer);
    window.__ridesafeResizeTimer = setTimeout(() => notifyVizResize(), 150);
  });

  toggleBtn.addEventListener("click", () => {
    const showingBar = toggleBtn.dataset.view === "bar";
    if (showingBar) {
      toggleBtn.dataset.view = "heat";
      toggleBtn.textContent = "View bar graph";
      barGraph.setAttribute("hidden", "");
      heatMap.removeAttribute("hidden");
    } else {
      toggleBtn.dataset.view = "bar";
      toggleBtn.textContent = "View heat map";
      barGraph.removeAttribute("hidden");
      heatMap.setAttribute("hidden", "");
    }
    setSearchResultVisible(false);
    requestAnimationFrame(() => notifyVizResize());
  });

  const donutCharts = document.querySelectorAll(".donut-chart");
  const toggleYearBtns = document.querySelectorAll(".toggle-year-btns");
  const yearValue = document.getElementById("year-value");
  let currentYear = 2022;

  toggleYearBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const direction = btn.id;
      if (direction === "left") {
        currentYear = currentYear === 2022 ? 2024 : currentYear - 1;
      } else {
        currentYear = currentYear === 2024 ? 2022 : currentYear + 1;
      }

      donutCharts.forEach((chart) => chart.classList.remove("active"));

      if (currentYear === 2022) {
        donutCharts[0].classList.add("active");
      } else if (currentYear === 2023) {
        donutCharts[1].classList.add("active");
      } else {
        donutCharts[2].classList.add("active");
      }

      yearValue.textContent = String(currentYear);
      monthName.textContent = "n/a";
      totalValue.textContent = "0";
      percentage.textContent = "0%";

      // Trigger Plotly to recalculate dimensions
      requestAnimationFrame(() => {
        notifyVizResize();
        Plotly.Plots.resize(
          document.querySelector(".donut-chart.active .plotly-graph-div"),
        );
      });
    });
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

  const colors = ["#EBEB55", "#D4D700", "#55A630", "#007F5F"];
  let colorCount = 0;

  months.forEach((month) => {
    const li = document.createElement("li");
    const p = document.createElement("p");
    const div = document.createElement("div");

    p.textContent = month;

    if (colorCount < 3) {
      div.style.backgroundColor = colors[0];
    } else if (colorCount < 6) {
      div.style.backgroundColor = colors[1];
    } else if (colorCount < 9) {
      div.style.backgroundColor = colors[2];
    } else {
      div.style.backgroundColor = colors[3];
    }

    colorCount += 1;

    li.appendChild(p);
    li.appendChild(div);

    li.addEventListener("click", () => {
      fetchMonthData(currentYear, month);
    });

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
    barGraph.setAttribute("hidden", "");
    heatMap.setAttribute("hidden", "");
    setSearchResultVisible(true);
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
