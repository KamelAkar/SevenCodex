import { loadCodexData } from "./data-store.js";
import { DEFAULT_LANGUAGE, getLocale } from "./i18n.js";
import { getSevenMapBaseUrl } from "./map-links.js";
import { navigate, parseRoute, routeForSearch } from "./router.js";
import { loadState, saveState, state } from "./state.js";
import {
  renderApp,
  renderError,
  renderLoading,
  renderSearchSuggestions,
  renderSearchSummary,
  renderInspector,
  syncPanels,
  syncSearchInput,
} from "./render.js";

const MOBILE_MEDIA_QUERY = "(max-width: 1200px)";
const SEARCH_SUGGESTION_DEBOUNCE_MS = 70;
const FILTER_INPUT_DEBOUNCE_MS = 120;

let lastMobileViewport = false;
let suggestionTimer = 0;
let routeQueryTimer = 0;
let autoLoadObserver = null;

function isMobileViewport() {
  return window.matchMedia(MOBILE_MEDIA_QUERY).matches;
}

function resolveLocaleValue(locale, key) {
  return String(key || "")
    .split(".")
    .reduce((acc, part) => acc?.[part], locale);
}

function syncStaticTranslations() {
  const current = getLocale(state.language);
  document.documentElement.lang = state.language;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    const value = resolveLocaleValue(current, key);
    if (typeof value === "string") {
      node.textContent = value;
    }
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    const key = node.getAttribute("data-i18n-placeholder");
    const value = resolveLocaleValue(current, key);
    if (typeof value === "string") {
      node.setAttribute("placeholder", value);
    }
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    const key = node.getAttribute("data-i18n-aria-label");
    const value = resolveLocaleValue(current, key);
    if (typeof value === "string") {
      node.setAttribute("aria-label", value);
    }
  });

  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    const key = node.getAttribute("data-i18n-title");
    const value = resolveLocaleValue(current, key);
    if (typeof value === "string") {
      node.setAttribute("title", value);
    }
  });
}

function normalizeRoute(route) {
  return {
    ...route,
    lang: state.language || DEFAULT_LANGUAGE,
    view: route.view || "home",
  };
}

function syncRouteFromLocation() {
  const route = parseRoute(window.location);
  if (route.lang) {
    state.language = route.lang;
  }
  state.route = normalizeRoute(route);
  state.pendingQuery = state.route.q || "";
}

function updateRoute(nextRoute, options = {}) {
  state.route = normalizeRoute(nextRoute);
  state.pendingQuery = state.route.q || "";
  navigate(state.route, options);
  renderUi();
}

function setLanguage(language) {
  if (!getLocale(language)) return;
  state.language = language;
  state.route = normalizeRoute({ ...state.route, lang: language });
  saveState();
  navigate(state.route, { replace: true });
  hydrate();
}

function setSearchQuery(value) {
  state.pendingQuery = value;
  state.suggestionsOpen = !!value.trim();
  state.suggestionIndex = -1;
  syncSearchInput();
  window.clearTimeout(suggestionTimer);
  suggestionTimer = window.setTimeout(() => {
    renderSearchSuggestions();
  }, SEARCH_SUGGESTION_DEBOUNCE_MS);
}

function scheduleRouteQueryUpdate(nextQuery) {
  window.clearTimeout(routeQueryTimer);
  routeQueryTimer = window.setTimeout(() => {
    updateRoute({ ...state.route, q: nextQuery, limit: "" }, { replace: true });
  }, FILTER_INPUT_DEBOUNCE_MS);
}

function togglePanel(panel) {
  if (panel === "sidebar") {
    state.sidebarOpen = !state.sidebarOpen;
    if (isMobileViewport() && state.sidebarOpen) state.inspectorOpen = false;
  }
  if (panel === "inspector") {
    state.inspectorOpen = !state.inspectorOpen;
    if (isMobileViewport() && state.inspectorOpen) state.sidebarOpen = false;
  }
  saveState();
  syncPanels();
}

function hydrate() {
  syncStaticTranslations();
  renderUi();
}

function disconnectAutoLoadObserver() {
  if (autoLoadObserver) {
    autoLoadObserver.disconnect();
    autoLoadObserver = null;
  }
}

function syncAutoLoadObserver() {
  disconnectAutoLoadObserver();
  const sentinel = document.getElementById("autoLoadSentinel");
  if (!sentinel || typeof window.IntersectionObserver !== "function") return;
  const nextLimit = Number.parseInt(sentinel.dataset.nextLimit || "", 10);
  if (!Number.isFinite(nextLimit) || nextLimit <= 0) return;
  autoLoadObserver = new window.IntersectionObserver(
    (entries) => {
      const isVisible = entries.some((entry) => entry.isIntersecting);
      if (!isVisible) return;
      disconnectAutoLoadObserver();
      if (String(state.route.limit || "") === String(nextLimit)) return;
      updateRoute({ ...state.route, limit: String(nextLimit) }, { replace: true });
    },
    {
      rootMargin: "0px 0px 320px 0px",
      threshold: 0.01,
    },
  );
  autoLoadObserver.observe(sentinel);
}

function renderUi() {
  renderApp();
  window.requestAnimationFrame(() => {
    syncAutoLoadObserver();
  });
}

function submitSearch(query) {
  window.clearTimeout(routeQueryTimer);
  window.clearTimeout(suggestionTimer);
  updateRoute(routeForSearch(state.language, { q: query.trim() }));
  state.pendingQuery = query.trim();
  state.suggestionsOpen = false;
  state.suggestionIndex = -1;
  syncSearchInput();
}

function suggestionLinks() {
  return [...document.querySelectorAll(".search-suggestion[data-suggestion-index]")];
}

function syncSuggestionFocus() {
  const suggestions = suggestionLinks();
  suggestions.forEach((node, index) => {
    const active = index === state.suggestionIndex;
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-selected", String(active));
  });
  syncSearchInput();
}

function moveSuggestion(step) {
  const suggestions = suggestionLinks();
  if (!suggestions.length) return;
  if (!state.suggestionsOpen) state.suggestionsOpen = true;
  const nextIndex = state.suggestionIndex < 0 ? (step > 0 ? 0 : suggestions.length - 1) : (state.suggestionIndex + step + suggestions.length) % suggestions.length;
  state.suggestionIndex = nextIndex;
  syncSuggestionFocus();
  suggestions[nextIndex]?.scrollIntoView({ block: "nearest" });
}

function openActiveSuggestion() {
  const active = suggestionLinks()[state.suggestionIndex];
  if (!active) return false;
  active.click();
  return true;
}

function applyMobileDefaults() {
  if (isMobileViewport()) {
    state.sidebarOpen = false;
    state.inspectorOpen = false;
  }
}

function handleResponsivePanels() {
  const mobile = isMobileViewport();
  if (mobile && !lastMobileViewport) {
    applyMobileDefaults();
    saveState();
    syncPanels();
  }
  lastMobileViewport = mobile;
}

function resolveMapLinkUrl(href) {
  const targetUrl = new URL(String(href || ""), window.location.href);
  if (String(targetUrl.searchParams.get("view") || "").toLowerCase() !== "map") return null;
  const mapUrl = new URL(getSevenMapBaseUrl(), window.location.href);
  mapUrl.search = targetUrl.searchParams.toString();
  return mapUrl;
}

function bindEvents() {
  window.addEventListener("popstate", () => {
    syncRouteFromLocation();
    renderUi();
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag !== "input" && activeTag !== "textarea" && activeTag !== "select") {
        event.preventDefault();
        document.getElementById("searchInput")?.focus();
      }
    }
    if (event.key === "Escape") {
      state.sidebarOpen = false;
      state.inspectorOpen = false;
      state.suggestionsOpen = false;
      state.suggestionIndex = -1;
      saveState();
      syncPanels();
      renderSearchSuggestions();
      syncSearchInput();
    }
  });

  window.matchMedia(MOBILE_MEDIA_QUERY).addEventListener("change", handleResponsivePanels);
  window.addEventListener("resize", handleResponsivePanels);

  document.addEventListener("click", (event) => {
    const anchor = event.target.closest("a[href]");
    if (anchor) {
      const mapUrl = resolveMapLinkUrl(anchor.getAttribute("href"));
      if (mapUrl) {
        event.preventDefault();
        if (anchor.target === "_blank") {
          window.open(mapUrl.toString(), "_blank", "noopener,noreferrer");
        } else {
          window.location.assign(mapUrl.toString());
        }
        return;
      }
    }

    const langButton = event.target.closest("[data-lang]");
    if (langButton) {
      setLanguage(langButton.dataset.lang);
      return;
    }

    const routeLink = event.target.closest("a[data-nav='true']");
    if (routeLink) {
      const href = routeLink.getAttribute("href");
      if (href) {
        event.preventDefault();
        const url = new URL(href, window.location.href);
        state.route = normalizeRoute(parseRoute(url));
        state.pendingQuery = state.route.q || "";
        navigate(state.route);
        renderUi();
      }
      return;
    }

    if (!event.target.closest(".search-stack")) {
      state.suggestionsOpen = false;
      state.suggestionIndex = -1;
      renderSearchSuggestions();
      syncSearchInput();
    }
  });

  document.getElementById("sidebarToggle")?.addEventListener("click", () => togglePanel("sidebar"));
  document.getElementById("inspectorToggle")?.addEventListener("click", () => togglePanel("inspector"));
  document.getElementById("panelBackdrop")?.addEventListener("click", () => {
    state.sidebarOpen = false;
    state.inspectorOpen = false;
    saveState();
    syncPanels();
  });

  document.getElementById("searchInput")?.addEventListener("input", (event) => {
    setSearchQuery(event.target.value);
  });
  document.getElementById("searchInput")?.addEventListener("focus", () => {
    state.suggestionsOpen = !!state.pendingQuery.trim();
    state.suggestionIndex = -1;
    window.clearTimeout(suggestionTimer);
    renderSearchSuggestions();
    syncSearchInput();
  });
  document.getElementById("searchInput")?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveSuggestion(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveSuggestion(-1);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (openActiveSuggestion()) return;
      submitSearch(event.currentTarget.value || "");
      return;
    }
    if (event.key === "Escape") {
      state.suggestionsOpen = false;
      state.suggestionIndex = -1;
      renderSearchSuggestions();
      syncSearchInput();
    }
  });
  document.getElementById("globalSearchForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch(document.getElementById("searchInput")?.value || "");
  });

  document.getElementById("clearSearchBtn")?.addEventListener("click", () => {
    window.clearTimeout(routeQueryTimer);
    window.clearTimeout(suggestionTimer);
    state.pendingQuery = "";
    state.suggestionsOpen = false;
    state.suggestionIndex = -1;
    const input = document.getElementById("searchInput");
    if (input) input.value = "";
    if (state.route.view === "search" || state.route.view === "list") {
      updateRoute({ ...state.route, q: "", limit: "" }, { replace: true });
    } else {
      renderSearchSuggestions();
      syncSearchInput();
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target.id === "listSearchInput") {
      scheduleRouteQueryUpdate(event.target.value);
      return;
    }
    if (event.target.id === "searchPageInput") {
      scheduleRouteQueryUpdate(event.target.value);
    }
  });

  document.addEventListener("change", (event) => {
    if (event.target.id === "listRegionSelect" || event.target.id === "searchRegionSelect") {
      updateRoute({ ...state.route, region: event.target.value, limit: "" }, { replace: true });
      return;
    }
    if (event.target.id === "listRaritySelect" || event.target.id === "searchRaritySelect") {
      updateRoute({ ...state.route, rarity: event.target.value, limit: "" }, { replace: true });
      return;
    }
    if (event.target.id === "listClassSelect") {
      updateRoute({ ...state.route, classification: event.target.value, limit: "" }, { replace: true });
      return;
    }
    if (event.target.id === "searchListSelect") {
      updateRoute({ ...state.route, kind: event.target.value, limit: "" }, { replace: true });
      return;
    }
  });
}

async function boot() {
  loadState();
  applyMobileDefaults();
  lastMobileViewport = isMobileViewport();
  syncRouteFromLocation();
  if (!state.route.lang) {
    state.language = state.language || DEFAULT_LANGUAGE;
    state.route.lang = state.language;
  }
  syncStaticTranslations();
  bindEvents();
  renderLoading();
  try {
    state.data = await loadCodexData();
    renderUi();
  } catch (error) {
    renderError(error.message);
    renderInspector();
    renderSearchSummary();
  }
}

boot();
