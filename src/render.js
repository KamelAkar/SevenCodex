import { resolveEntry, searchEntries } from "./data-store.js";
import { t } from "./i18n.js";
import { buildSevenMapUrl } from "./map-links.js";
import { state } from "./state.js";
import { escapeHtml, formatCount, kvRows } from "./utils.js";
import { buildRouteUrl } from "./router.js";
import {
  pageId,
  pageText,
  renderBreadcrumbs as breadcrumbTrail,
  renderSuggestions,
  renderTopNav as topNavMarkup,
  routeTitle,
  routeSubtitle,
  stat,
  text,
  entryListLabel,
  empty,
} from "./render-kit.js";
import { heroMarkup, renderEntry, renderHome, renderHub, renderList, renderPageView, renderRegion, renderSearch } from "./render-content.js";

export function renderApp() {
  if (!state.data) return;
  renderLanguageControls();
  renderTopNav();
  renderHero();
  renderPage();
  renderInspector();
  renderSearchSummary();
  renderSearchSuggestions();
  syncPanels();
  syncSearchInput();
}

export function renderLanguageControls() {
  document.querySelectorAll(".lang-btn").forEach((buttonNode) => buttonNode.classList.toggle("is-active", buttonNode.dataset.lang === state.language));
  document.documentElement.lang = state.language;
  document.title = `SevenCodex | ${routeTitle(state.data, state.route)}`;
  const languagePill = document.getElementById("languagePill");
  if (languagePill) languagePill.textContent = state.language.toUpperCase();
  const openMapLink = document.getElementById("openMapLink");
  const footerMapLink = document.getElementById("footerMapLink");
  const mapHref = buildSevenMapUrl({ language: state.language });
  if (openMapLink) openMapLink.href = mapHref;
  if (footerMapLink) footerMapLink.href = mapHref;
}

export function renderTopNav() {
  const node = document.getElementById("topNav");
  if (node && state.data) node.innerHTML = topNavMarkup(state.data);
}

export function renderHero() {
  const node = document.querySelector(".hero");
  if (!node || !state.data) return;
  const compactViews = new Set(["entry", "region"]);
  if (compactViews.has(state.route.view)) {
    node.hidden = true;
    node.style.display = "none";
    node.setAttribute("aria-hidden", "true");
    node.innerHTML = "";
    return;
  }
  node.hidden = false;
  node.style.display = "";
  node.removeAttribute("aria-hidden");
  node.innerHTML = heroMarkup(state.data, state.route);
}

export function renderPage() {
  const titleNode = document.getElementById("pageTitle");
  const subtitleNode = document.getElementById("pageSubtitle");
  const pillNode = document.getElementById("viewPill");
  const bodyNode = document.getElementById("pageBody");
  const breadcrumbsNode = document.getElementById("breadcrumbs");
  if (!titleNode || !pillNode || !bodyNode || !state.data) return;
  titleNode.textContent = routeTitle(state.data, state.route);
  pillNode.textContent = routeTitle(state.data, state.route);
  if (subtitleNode) subtitleNode.textContent = routeSubtitle(state.data, state.route);
  if (breadcrumbsNode) {
    breadcrumbsNode.innerHTML = breadcrumbTrail(state.data, state.route)
      .map((crumb, index, all) =>
        index === all.length - 1
          ? `<span class="breadcrumb-item is-current" aria-current="page">${escapeHtml(crumb.label)}</span>`
          : `<a class="breadcrumb-item" href="${buildRouteUrl(crumb.route)}" data-nav="true">${escapeHtml(crumb.label)}</a>`,
      )
      .join("");
  }
  let markup = "";
  if (state.route.view === "home") markup = renderHome(state.data);
  if (state.route.view === "hub") markup = renderHub(state.data, state.route);
  if (state.route.view === "list") markup = renderList(state.data, state.route);
  if (state.route.view === "region") {
    const entry = resolveEntry(state.data, state.route);
    markup = entry ? renderRegion(state.data, entry) : empty(t(state.language, "filters.noResults"));
  }
  if (state.route.view === "entry") {
    const entry = resolveEntry(state.data, state.route);
    markup = entry ? renderEntry(state.data, entry) : empty(t(state.language, "filters.noResults"));
  }
  if (state.route.view === "search") markup = renderSearch(state.data, state.route);
  if (state.route.view === "page") markup = renderPageView(state.data, state.route);
  bodyNode.innerHTML = markup || renderHome(state.data);
}

export function renderInspector() {
  const node = document.getElementById("inspectorBody");
  if (!node || !state.data) return;
  const current = resolveEntry(state.data, state.route);
  node.innerHTML = `<div class="detail-list">${kvRows({
    [t(state.language, "inspector.view")]: state.route.view,
    [t(state.language, "inspector.kind")]: state.route.kind || "",
    [t(state.language, "inspector.slug")]: state.route.slug || "",
    [t(state.language, "inspector.query")]: state.route.q || "",
    [t(state.language, "inspector.selection")]: current ? text(current, "name") : state.route.view === "page" ? pageText(pageId(state.route), "title") : "",
  })}</div>${current ? `<article class="stat-card"><span class="stat-label">${escapeHtml(entryListLabel(state.data, current))}</span><strong>${escapeHtml(text(current, "name"))}</strong><p>${escapeHtml(text(current, "summary") || text(current, "description"))}</p></article>` : stat(t(state.language, "labels.entries"), formatCount(state.data.manifest.counts.entries), t(state.language, "home.summary"))}`;
}

export function renderSearchSummary() {
  const node = document.getElementById("searchSummary");
  if (!node || !state.data) return;
  const count = state.route.view === "search" ? searchEntries(state.data, state.route).length : 0;
  node.innerHTML = `${stat(t(state.language, "labels.entries"), formatCount(state.data.manifest.counts.entries), t(state.language, "copy.currentCoverage"))}${stat(
    t(state.language, "filters.searchResults"),
    formatCount(count),
    state.route.q ? t(state.language, "copy.searchQueryLabel", { query: state.route.q }) : t(state.language, "copy.searchPrompt"),
  )}`;
}

export function renderSearchSuggestions() {
  const node = document.getElementById("searchSuggestions");
  const query = String(state.pendingQuery || "").trim();
  if (!node || !state.data || !state.suggestionsOpen || query.length < 2) {
    if (node) {
      node.hidden = true;
      node.innerHTML = "";
    }
    return;
  }
  node.hidden = false;
  node.innerHTML = renderSuggestions(state.data, query);
}

export function syncPanels() {
  const sidebar = document.getElementById("sidebar");
  const inspector = document.getElementById("inspector");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const inspectorToggle = document.getElementById("inspectorToggle");
  const backdrop = document.getElementById("panelBackdrop");
  const topbar = document.querySelector(".topbar");
  const mobileViewport = window.matchMedia("(max-width: 1200px)").matches;
  const overlayPanelsOpen = state.inspectorOpen || (mobileViewport && !!sidebar && state.sidebarOpen);
  if (sidebar) sidebar.classList.toggle("is-open", state.sidebarOpen);
  if (inspector) inspector.classList.toggle("is-open", state.inspectorOpen);
  if (sidebarToggle) sidebarToggle.setAttribute("aria-expanded", String(state.sidebarOpen));
  if (inspectorToggle) inspectorToggle.setAttribute("aria-expanded", String(state.inspectorOpen));
  if (topbar) {
    const offset = Math.max(96, Math.round(topbar.getBoundingClientRect().bottom + 10));
    document.documentElement.style.setProperty("--mobile-panel-top", `${offset}px`);
  }
  if (backdrop) {
    backdrop.hidden = !overlayPanelsOpen;
    backdrop.setAttribute("aria-hidden", String(!overlayPanelsOpen));
  }
  document.body.classList.toggle("has-open-panel", overlayPanelsOpen);
}

export function syncSearchInput() {
  const input = document.getElementById("searchInput");
  const clearButton = document.getElementById("clearSearchBtn");
  if (!input) return;
  const value = state.pendingQuery || "";
  if (input.value !== value) input.value = value;
  input.setAttribute("aria-expanded", String(state.suggestionsOpen && value.trim().length >= 2));
  input.setAttribute("aria-activedescendant", state.suggestionIndex >= 0 ? `searchSuggestion-${state.suggestionIndex}` : "");
  if (clearButton) clearButton.hidden = !value.trim();
}

export function renderLoading() {
  const node = document.getElementById("pageBody");
  if (node) node.innerHTML = empty(t(state.language, "shell.loading"));
}

export function renderError(message) {
  const node = document.getElementById("pageBody");
  if (node) node.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t(state.language, "shell.dataError"))}</strong><p>${escapeHtml(message || "")}</p></div>`;
}
