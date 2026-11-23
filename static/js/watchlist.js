// Watchlist (UI-only, localStorage). No backend, no alerts — just a persisted set of
// NSE symbols the user has starred across the app.

const WATCHLIST_KEY = "as.watchlist";

function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function save(list) {
  try {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
  } catch {
    /* storage may be unavailable (private mode) — watchlist is best-effort */
  }
}

function isWatchlisted(code) {
  return getWatchlist().includes(String(code));
}

function toggle(code) {
  const c = String(code);
  const list = getWatchlist();
  const i = list.indexOf(c);
  if (i >= 0) {
    list.splice(i, 1);
  } else {
    list.push(c);
  }
  save(list);
  return list.includes(c);
}

export { getWatchlist, isWatchlisted, toggle };
