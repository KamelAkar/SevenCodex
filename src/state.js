import { DEFAULT_LANGUAGE } from "./i18n.js";

const STORAGE_KEY = "sevencodex:v2:ui";

export const state = {
  language: DEFAULT_LANGUAGE,
  sidebarOpen: false,
  inspectorOpen: false,
  route: { lang: DEFAULT_LANGUAGE, view: "home" },
  data: null,
  pendingQuery: "",
  suggestionsOpen: false,
  suggestionIndex: -1,
};

export function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed.language) state.language = parsed.language;
    if (typeof parsed.sidebarOpen === "boolean") state.sidebarOpen = parsed.sidebarOpen;
    if (typeof parsed.inspectorOpen === "boolean") state.inspectorOpen = parsed.inspectorOpen;
  } catch (_) {
    // Ignore storage failures.
  }
}

export function saveState() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        language: state.language,
        sidebarOpen: state.sidebarOpen,
        inspectorOpen: state.inspectorOpen,
      }),
    );
  } catch (_) {
    // Ignore storage failures.
  }
}
