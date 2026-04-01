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
  }

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
  const resultBox = document.querySelector(".result-box");
  const suggestions = document.querySelector(".result-box ul");
  const hour = document.getElementById("hour");
  const searchBtn = document.getElementById("search");
  const barangayText = document.getElementById("brgy-value");
  const hourText = document.getElementById("hr-value");
  const percentageText = document.getElementById("percent-result");

  searchBtn.addEventListener("click", () => {
    if (barangay.value === "" || hour.value === "hour") {
      return;
    }
    fetchAccidentPercentage(barangay.value, hour.value);
    barGraph.setAttribute("hidden", "");
    heatMap.setAttribute("hidden", "");
    setSearchResultVisible(true);
  });

  barangay.addEventListener("keyup", async () => {
    const barangayList = await fetchBarangayList();
    resultBox.hidden = false;
    let result = [];
    const input = barangay.value;
    const inputClean = input.replace(/\s+/g, "");

    if (input.length) {
      suggestions.style.overflowY = "scroll";
      result = barangayList.filter((keyword) => {
        let matched = 0;
        const keywordClean = keyword.replace(/\s+/g, "");

        for (let i = 0; i < inputClean.length; i++) {
          if (inputClean[i].toLowerCase() === keywordClean[i].toLowerCase()) {
            matched++;
          }
        }

        return matched === inputClean.length ? keyword : null;
      });
      if (result.length === 0) {
        suggestions.style.overflowY = "hidden";
      }
    } else {
      suggestions.style.overflowY = "hidden";
      resultBox.hidden = true;
    }
    displaySuggestions(result);
  });

  function displaySuggestions(result) {
    suggestions.innerHTML = "";
    result.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      li.setAttribute("role", "option");
      li.addEventListener("click", () => {
        barangay.value = item;
        resultBox.hidden = true;
      });
      suggestions.appendChild(li);
    });
  }

  for (let i = 0; i < 24; i++) {
    const option = document.createElement("option");
    const hourFormatted = String(i).padStart(2, "0") + ":00";
    option.setAttribute("value", hourFormatted);
    option.textContent = hourFormatted;
    hour.appendChild(option);
  }

  reportBtn.addEventListener("click", () => {
    getSummaryReport(barangayText.textContent);
  });

  async function getSummaryReport(barangayName) {
    try {
      const res = await fetch(
        api(`/getSummaryReport/${encodeURIComponent(barangayName)}`),
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        },
      );
      if (res.ok) {
        const blob = await res.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "summary_report.pdf";
        link.click();
        URL.revokeObjectURL(link.href);
      } else {
        console.error("Error fetching summary report:", res.statusText);
      }
    } catch (error) {
      console.error("Error fetching summary report: ", error);
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
        return;
      }
      percentageText.textContent =
        typeof data === "string" ? data : String(data);
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
