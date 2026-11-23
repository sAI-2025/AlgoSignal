// Alerts (UI-only, localStorage). No backend, no Telegram/WhatsApp — just a persisted
// list of price alerts the user has set across the app.

const ALERTS_KEY = "as.alerts";

function getAlerts() {
  try {
    const raw = localStorage.getItem(ALERTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function save(list) {
  try {
    localStorage.setItem(ALERTS_KEY, JSON.stringify(list));
  } catch {
    /* storage may be unavailable (private mode) — alerts are best-effort */
  }
}

function addAlert(symbol, targetPrice, condition) {
  const list = getAlerts();
  const alert = {
    id: Date.now().toString(),
    symbol: String(symbol).toUpperCase(),
    targetPrice: Number(targetPrice),
    condition: condition, // "above" | "below"
    createdAt: new Date().toISOString(),
    triggered: false,
  };
  list.push(alert);
  save(list);
  return alert;
}

function removeAlert(id) {
  const list = getAlerts().filter((a) => a.id !== String(id));
  save(list);
}

function clearAlerts() {
  save([]);
}

export { getAlerts, addAlert, removeAlert, clearAlerts };
