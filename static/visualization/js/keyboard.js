// Keyboard shortcuts (PRD V16). A single keydown listener dispatches to workspace actions.
// Ignored while the user types in an input/textarea/select or editable element. Returns a
// detach function. Keys: ←/→ pan, Home/End jump, +/- zoom, P pin, M measure, R range,
// L markers, T table, F fullscreen, C clear tools, Esc clear.

const KEY_ACTIONS = {
  ArrowLeft: () => ({ name: "scrollBy", args: [-3] }),
  ArrowRight: () => ({ name: "scrollBy", args: [3] }),
  Home: () => ({ name: "jump", args: ["start"] }),
  End: () => ({ name: "jump", args: ["end"] }),
  "+": () => ({ name: "zoom", args: [0.8] }),
  "=": () => ({ name: "zoom", args: [0.8] }),
  "-": () => ({ name: "zoom", args: [1.25] }),
  _: () => ({ name: "zoom", args: [1.25] }),
  p: () => ({ name: "tool", args: ["pin"] }),
  m: () => ({ name: "tool", args: ["measure"] }),
  r: () => ({ name: "tool", args: ["range"] }),
  l: () => ({ name: "toggle", args: ["markers"] }),
  t: () => ({ name: "toggle", args: ["table"] }),
  f: () => ({ name: "toggle", args: ["fullscreen"] }),
  c: () => ({ name: "clear" }),
  Escape: () => ({ name: "clear" }),
};

function isTypingTarget(target) {
  if (!target) {
    return false;
  }
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable === true
  );
}

function attachKeyboard(actions) {
  const handler = (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (isTypingTarget(event.target)) {
      return;
    }
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    const build = KEY_ACTIONS[key];
    if (!build) {
      return;
    }
    const action = build();
    const fn = actions[action.name];
    if (typeof fn === "function") {
      event.preventDefault();
      fn(...action.args);
    }
  };
  document.addEventListener("keydown", handler);
  return () => document.removeEventListener("keydown", handler);
}

export { attachKeyboard };