// S0 app shell behavior: persisted theme (light/dark/system) and sidebar collapse.
// Runs on every page; no backend dependency. Charts re-theme themselves via the
// existing MutationObserver in chartWorkspace.js that watches data-bs-theme.

(function () {
  var root = document.documentElement;
  var THEME_KEY = "as.theme";
  var SIDEBAR_KEY = "as.sidebarCollapsed";
  var themes = ["light", "dark", "system"];
  var themeIcons = { light: "bi-sun", dark: "bi-moon", system: "bi-circle-half" };

  function currentTheme() {
    try {
      return localStorage.getItem(THEME_KEY) || "system";
    } catch (e) {
      return "system";
    }
  }

  function applyTheme(theme) {
    var dark =
      theme === "dark" ||
      (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-bs-theme", dark ? "dark" : "light");
    var btn = document.querySelector("[data-theme-toggle]");
    var icon = btn && btn.querySelector("i");
    if (icon) {
      icon.className = "bi " + themeIcons[theme];
    }
  }

  function cycleTheme() {
    var next = themes[(themes.indexOf(currentTheme()) + 1) % themes.length];
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (e) {}
    applyTheme(next);
  }

  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (currentTheme() === "system") {
      applyTheme("system");
    }
  });

  var themeBtn = document.querySelector("[data-theme-toggle]");
  if (themeBtn) {
    themeBtn.addEventListener("click", cycleTheme);
  }

  var sidebarBtn = document.querySelector("[data-sidebar-toggle]");
  var sidebar = document.querySelector(".as-sidebar");
  var shell = document.querySelector(".as-shell");
  if (sidebarBtn && shell && sidebar) {
    var collapsed = localStorage.getItem(SIDEBAR_KEY) === "1";
    shell.classList.toggle("as-sidebar-collapsed", collapsed);
    sidebarBtn.setAttribute("aria-pressed", collapsed);
    sidebarBtn.addEventListener("click", function () {
      var next = !shell.classList.contains("as-sidebar-collapsed");
      shell.classList.toggle("as-sidebar-collapsed", next);
      sidebarBtn.setAttribute("aria-pressed", next);
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      } catch (e) {}
    });
  }

  applyTheme(currentTheme());
})();