// S0 shell behavior: freshness chip (Fetcher coverage) + Ctrl-K company search.
// Runs on every page; requires session auth (cookie/CSRF via same-origin fetch).

(function () {
  var FRESHNESS_KEY = "as.freshness";
  var REFRESH_MS = 60000;

  var freshnessEl = document.getElementById("as-freshness");
  var lastFreshness = null;

  function fmtFreshness(coverage) {
    var latest = coverage.latest_candle;
    var n = coverage.with_data;
    var total = coverage.companies;
    if (!latest) {
      return "No data · " + n + "/" + total;
    }
    var parts = latest.split("-");
    var label = parts[2] + " " + monthName(Number(parts[1])) + " " + parts[0];
    return label + " · " + n + "/" + total;
  }

  function monthName(m) {
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1] || "";
  }

  async function refreshFreshness() {
    if (!freshnessEl) {
      return;
    }
    try {
      var response = await fetch("/api/v1/fetcher/coverage/", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        freshnessEl.textContent = "Data: —";
        return;
      }
      var coverage = await response.json();
      freshnessEl.textContent = fmtFreshness(coverage);
      freshnessEl.title = "Last stored candle · universe coverage · source: server";
      lastFreshness = coverage;
    } catch (e) {
      freshnessEl.textContent = "Data: —";
    }
  }

  // ---- Ctrl-K company search (Explorer) ----
  var SEARCH_KEY = "as.search";
  var dialog = null;
  var input = null;
  var resultsList = null;
  var debounceTimer = null;

  function ensureDialog() {
    if (dialog) {
      return;
    }
    dialog = document.createElement("div");
    dialog.className =
      "modal fade position-fixed";
    dialog.setAttribute("tabindex", "-1");
    dialog.setAttribute("aria-hidden", "true");
    dialog.innerHTML =
      '<div class="modal-dialog modal-dialog-centered modal-lg">' +
      '<div class="modal-content shadow">' +
      '<div class="modal-header border-0">' +
      '<h5 class="modal-title fw-semibold">Company search</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
      '</div>' +
      '<div class="modal-body py-3">' +
      '<div class="input-group mb-3">' +
      '<span class="input-group-text"><i class="bi bi-search"></i></span>' +
      '<input type="search" id="as-search-input" class="form-control" placeholder="Name or NSE code (e.g. Reliance, INFY)" aria-label="Company search">' +
      '</div>' +
      '<div id="as-search-results" class="list-group list-group-flush small"></div>' +
      '<div id="as-search-empty" class="text-muted small mt-2 d-none">No companies match.</div>' +
      '</div>' +
      '<div class="modal-footer border-0">' +
      '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>' +
      '</div>' +
      '</div>' +
      '</div>';
    document.body.appendChild(dialog);
    input = dialog.querySelector("#as-search-input");
    resultsList = dialog.querySelector("#as-search-results");

    var bsModal = new bootstrap.Modal(dialog);

    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        runSearch(input.value.trim());
      }, 150);
    });

    dialog.addEventListener("shown.bs.modal", function () {
      input.focus();
      resultsList.innerHTML = "";
      document.getElementById("as-search-empty").classList.add("d-none");
    });

    dialog.addEventListener("hidden.bs.modal", function () {
      resultsList.innerHTML = "";
      document.getElementById("as-search-empty").classList.add("d-none");
      input.value = "";
      clearTimeout(debounceTimer);
    });

    return bsModal;
  }

  async function runSearch(query) {
    if (!query) {
      resultsList.innerHTML = "";
      document.getElementById("as-search-empty").classList.add("d-none");
      return;
    }
    try {
      var params = new URLSearchParams({ q: query, limit: 10 });
      var response = await fetch("/api/v1/explorer/search/?" + params.toString(), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("Search failed (" + response.status + ")");
      }
      var data = await response.json();
      renderResults(data.results || []);
    } catch (e) {
      resultsList.innerHTML =
        '<div class="list-group-item text-danger small">Search unavailable.</div>';
      document.getElementById("as-search-empty").classList.add("d-none");
    }
  }

  function renderResults(results) {
    resultsList.innerHTML = "";
    var empty = document.getElementById("as-search-empty");
    if (!results || !results.length) {
      empty.classList.remove("d-none");
      return;
    }
    empty.classList.add("d-none");
    results.forEach(function (r) {
      var item = document.createElement("a");
      item.href = "/companies/" + encodeURIComponent(r.nse_code) + "/";
      item.className = "list-group-item list-group-item-action py-2";
      item.innerHTML =
        '<div class="d-flex justify-content-between align-items-center">' +
        '<div>' +
        '<div class="fw-semibold">' + escapeHtml(r.company_name || r.nse_code) + "</div>" +
        '<div class="text-truncate" style="max-width:180px">' +
        escapeHtml(r.nse_code) +
        (r.sector ? " · " + escapeHtml(r.sector) : "") +
        "</div>" +
        '</div>' +
        '<i class="bi bi-chevron-right text-muted"></i>' +
        "</div>";
      resultsList.appendChild(item);
    });
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function openSearch() {
    var bsModal = ensureDialog();
    bsModal.show();
  }

  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "k") {
      event.preventDefault();
      openSearch();
    }
  });

  var searchBtn = document.querySelector("[data-search-toggle]");
  if (searchBtn) {
    searchBtn.addEventListener("click", openSearch);
  }

  // Freshness poll loop.
  var freshnessTimer = null;
  function startFreshness() {
    refreshFreshness();
    if (freshnessTimer) {
      clearInterval(freshnessTimer);
    }
    freshnessTimer = setInterval(refreshFreshness, REFRESH_MS);
  }

  if (freshnessEl) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", startFreshness);
    } else {
      startFreshness();
    }
  }
})();
