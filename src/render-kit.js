import { GUIDE_PAGES, HUB_ICONS, HUB_ORDER, LIST_ICONS, PAGE_ICONS, PAGE_META, QUICK_LISTS } from "./catalog.js";
import { resolveEntry, searchEntries } from "./data-store.js";
import { t } from "./i18n.js";
import { buildMapActions } from "./map-links.js";
import { buildRouteUrl, routeForEntry, routeForHome, routeForHub, routeForList, routeForPage, routeForSearch } from "./router.js";
import { state } from "./state.js";
import { escapeHtml, formatCount, joinChips, titleCase } from "./utils.js";

const ICONS = {
  world: "M12 2C7 2 3 6 3 11s4 9 9 9 9-4 9-9-4-9-9-9",
  leaf: "M20 4C10 4 4 10.2 4 18.2c0 1 .8 1.8 1.8 1.8 5.6 0 9.7-2.1 12.3-6.2C19.8 10.8 20 4 20 4",
  spark: "m12 2 1.7 5.2H19l-4.3 3.1 1.7 5.2L12 12.4 7.6 15.5l1.7-5.2L5 7.2h5.3z",
  compass: "M12 3a9 9 0 1 0 9 9 9 9 0 0 0-9-9m3.7 5.3-1.8 5.4-5.4 1.8 1.8-5.4z",
  gem: "m12 3 4.5 4.2L12 21 7.5 7.2zM7 8h10",
  bag: "M7 7V6a5 5 0 0 1 10 0v1h2v12H5V7zm2 0h6V6a3 3 0 0 0-6 0z",
  anvil: "M5 6h6V4H5zm8 0h6V4h-6zm-9 3h18v2h-2v2c0 3.9-2.7 7.2-6.3 8l1.1 2H8.2l1.1-2C5.7 20.2 3 16.9 3 13V11H1V9z",
  paw: "M7.5 11.5c-1.1 0-2-.9-2-2s.9-2.4 2-2.4 2 1.3 2 2.4-.9 2-2 2m4-2.5c0-1.3.9-2.4 2-2.4s2 1.1 2 2.4c0 1.1-.9 2-2 2s-2-.9-2-2",
  crown: "M4 7 8 11l4-6 4 6 4-4-2 11H6z",
  hook: "M9 3v4c0 1.7 1.3 3 3 3h1c1.7 0 3 1.3 3 3 0 1.3-.8 2.4-1.9 2.8l-1.4.6C10 17.3 8 20.3 8 23h2",
  pin: "M12 3a5 5 0 0 0-5 5c0 4 5 10 5 10s5-6 5-10a5 5 0 0 0-5-5",
  gate: "M5 5h14v14H5zm3 2v10h8V7zm2 3h4v2h-4z",
  grid: "M4 4h7v7H4zm9 0h7v7h-7zM4 13h7v7H4zm9 0h7v7h-7z",
  key: "M15 3a5 5 0 0 0-4.7 6.8L3 17v4h4l1.5-1.5V17H11l2.1-2.1A5 5 0 1 0 15 3",
  pick: "M18.8 2.6 21.4 5l-5.7 5.7 2.4 2.4-1.4 1.4-2.4-2.4-3.2 3.2v6.1h-2v-4.1l-4.1 4.1-1.4-1.4 4.1-4.1H3.6v-2h6.1l3.2-3.2-2.4-2.4L11.9 7l2.4 2.4z",
  star: "m12 3 2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.6 7.2 18l.9-5.4L4.2 8.7l5.4-.8z",
  fang: "M8 4h8v4.3c0 1.9-.5 3.8-1.6 5.4L12 17.3l-2.4-3.6A9.7 9.7 0 0 1 8 8.3zm2 2v2.5c0 1.1.3 2.2.9 3.1l1.1 1.7 1.1-1.7c.6-.9.9-2 .9-3.1V6z",
  blade: "M18.4 3.6 20.4 5.6 14 12l-2 6 6-2 6.4-6.4 2 2-7.1 7.1L10 22l4.3-9.3z",
  shield: "M12 3 19 6v5c0 4.7-2.8 8.8-7 10-4.2-1.2-7-5.3-7-10V6z",
  scroll: "M7 3h8a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H9a4 4 0 0 0 4-4V7a4 4 0 0 0-4-4m0 0a4 4 0 0 0-4 4v10a4 4 0 0 0 4 4",
  fish: "M3 12c2.8-3.8 6.3-5.7 10.5-5.7 2.6 0 4.8.5 6.5 1.5-1.6 1.2-2.4 2.6-2.4 4.2s.8 3 2.4 4.2c-1.7 1-3.9 1.5-6.5 1.5C9.3 17.7 5.8 15.8 3 12m8-1.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3",
  user: "M12 12a4.5 4.5 0 1 0-4.5-4.5A4.5 4.5 0 0 0 12 12m0 2c-4.3 0-7.8 2.2-8.8 5.5h17.6C19.8 16.2 16.3 14 12 14",
};

const MOJIBAKE_HINTS = ["Ãƒ", "Ã¢â‚¬", "Ã‚"];
const REPAIRED_PAGES = new Map();

function repairMojibakeString(value) {
  const text = String(value ?? "");
  if (!MOJIBAKE_HINTS.some((hint) => text.includes(hint))) return text;
  try {
    const bytes = Uint8Array.from([...text].map((char) => char.charCodeAt(0) & 0xff));
    const repaired = new TextDecoder("utf-8").decode(bytes);
    return repaired.includes("\ufffd") ? text : repaired;
  } catch {
    return text;
  }
}

function deepRepair(node) {
  if (typeof node === "string") return repairMojibakeString(node);
  if (Array.isArray(node)) return node.map((value) => deepRepair(value));
  if (!node || typeof node !== "object") return node;
  return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, deepRepair(value)]));
}

export const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ICONS.world}"></path></svg>`;
export const text = (entry, field) => entry?.locale?.[state.language]?.[field] || entry?.locale?.en?.[field] || "";
export const listMeta = (store, id) => store?.manifest?.lists?.[id] || null;
export const hubMeta = (store, id) => store?.manifest?.hubs?.[id] || null;
export const pageMeta = (id) => {
  const resolved = PAGE_META[id] || PAGE_META.about;
  const cacheKey = id || "about";
  if (!REPAIRED_PAGES.has(cacheKey)) {
    REPAIRED_PAGES.set(cacheKey, deepRepair(resolved));
  }
  return REPAIRED_PAGES.get(cacheKey);
};
export const pageText = (id, key) => pageMeta(id)?.[key]?.[state.language] || pageMeta(id)?.[key]?.en || "";
export const pageId = (route) => route.kind || route.page || "about";
export const primaryList = (entry) => entry?.lists?.[0] || "";
export const regionLabel = (store, id) => text(store.regionById?.get(id), "name") || id;
export const entryListLabel = (store, entry) => listMeta(store, primaryList(entry))?.title?.[state.language] || titleCase(primaryList(entry) || entry.kind);
const rarityCardClass = (entry) => (entry?.rarity?.grade ? `entry-card-has-rarity rarity-${entry.rarity.grade}` : "");

function secondaryLocaleName(entry) {
  const primary = text(entry, "name");
  const secondary = state.language === "fr" ? entry?.locale?.en?.name : entry?.locale?.fr?.name;
  return secondary && secondary !== primary ? secondary : "";
}

function cardSummary(entry) {
  return text(entry, "description") || text(entry, "summary") || "";
}

export function routeTitle(store, route) {
  if (route.view === "home") return t(state.language, "labels.home");
  if (route.view === "page") return pageText(pageId(route), "title");
  if (route.view === "hub") return hubMeta(store, route.kind)?.title?.[state.language] || titleCase(route.kind);
  if (route.view === "list") return listMeta(store, route.kind)?.title?.[state.language] || titleCase(route.kind);
  if (route.view === "search") return t(state.language, "search.title");
  const entry = resolveEntry(store, route);
  return entry ? text(entry, "name") : titleCase(route.slug || route.kind || route.view);
}

export function routeSubtitle(store, route) {
  if (route.view === "home") return t(state.language, "home.summary");
  if (route.view === "page") return pageText(pageId(route), "summary");
  if (route.view === "hub") return hubMeta(store, route.kind)?.description?.[state.language] || "";
  if (route.view === "list") return listMeta(store, route.kind)?.description?.[state.language] || "";
  if (route.view === "search") return t(state.language, "search.landingBody");
  const entry = resolveEntry(store, route);
  return entry ? text(entry, "summary") || text(entry, "description") : "";
}

export function navLink(route, label, meta, active, iconName, variant = "") {
  const classes = ["category-item", variant, active ? "is-active" : ""].filter(Boolean).join(" ");
  return `<a class="${classes}" href="${buildRouteUrl(route)}" data-nav="true" ${active ? 'aria-current="page"' : ""}><span class="category-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(meta || "")}</span></span><span class="tag icon-tag">${icon(iconName)}</span></a>`;
}

export function button(href, label, accent = false, external = false) {
  return `<a class="button ${accent ? "button-primary" : "button-secondary"}" href="${href}" ${external ? 'target="_blank" rel="noopener noreferrer"' : 'data-nav="true"'}>${escapeHtml(label)}</a>`;
}

export function stat(label, value, body) {
  return `<article class="stat-card"><span class="stat-label">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(body)}</p></article>`;
}

export function empty(title, body = "") {
  return `<div class="empty-state"><strong>${escapeHtml(title)}</strong>${body ? `<p>${escapeHtml(body)}</p>` : ""}</div>`;
}

export function guideCard(id) {
  return `<article class="guide-card"><div class="guide-card-head"><span class="card-icon">${icon(PAGE_ICONS[id] || "world")}</span><div><p class="eyebrow">${escapeHtml(pageText(id, "eyebrow"))}</p><strong>${escapeHtml(pageText(id, "title"))}</strong></div></div><p>${escapeHtml(pageText(id, "summary"))}</p><div class="entry-card-actions">${button(buildRouteUrl(routeForPage(state.language, id)), t(state.language, "actions.openGuide"))}</div></article>`;
}

export function listCard(store, id, extra = {}) {
  const meta = listMeta(store, id);
  if (!meta) return "";
  const hubTitle = hubMeta(store, meta.hub)?.title?.[state.language] || titleCase(meta.hub || "");
  return `<article class="guide-card"><div class="guide-card-head"><span class="card-icon">${icon(LIST_ICONS[id] || "world")}</span><div><p class="eyebrow">${escapeHtml(hubTitle)}</p><strong>${escapeHtml(meta.title?.[state.language] || id)}</strong></div></div><p>${escapeHtml(meta.description?.[state.language] || "")}</p><div class="card-meta-row"><span class="tag">${formatCount(meta.count || 0)} ${escapeHtml(t(state.language, "labels.entries"))}</span><span class="tag">${formatCount(meta.mapLinkedCount || 0)} ${escapeHtml(t(state.language, "labels.mapLinked"))}</span></div><div class="entry-card-actions">${button(buildRouteUrl(routeForList(state.language, id, extra)), t(state.language, "actions.open"))}</div></article>`;
}

export function entryCard(store, entry) {
  if (!entry) return "";
  const mapAction = (buildMapActions(entry, state.language) || [])[0];
  const media = entry.image || entry.icon;
  const iconName = LIST_ICONS[primaryList(entry)] || HUB_ICONS[primaryList(entry)] || "world";
  const mapLabel = state.language === "fr" ? "Carte" : "Map";
  const rarityLabel = entry.rarity?.label?.[state.language] || "";
  const secondaryName = secondaryLocaleName(entry);
  const summary = cardSummary(entry);
  return `<article class="entry-card ${rarityCardClass(entry)}"><div class="entry-card-head entry-card-head-portrait"><div class="entry-card-media">${media ? `<img src="${media}" alt="" loading="lazy" />` : `<span class="entry-card-icon entry-card-icon-large">${icon(iconName)}</span>`}</div><div class="entry-card-copy"><span class="entry-card-kicker">${escapeHtml(entryListLabel(store, entry))}</span><strong>${escapeHtml(text(entry, "name"))}</strong>${secondaryName ? `<span class="entry-dual-name">${escapeHtml(`${state.language === "fr" ? "EN" : "FR"}: ${secondaryName}`)}</span>` : ""}</div>${summary ? `<p class="entry-card-text">${escapeHtml(summary)}</p>` : ""}</div><div class="entry-card-meta">${rarityLabel ? `<span class="tag tag-rarity">${escapeHtml(rarityLabel)}</span>` : ""}${joinChips((entry.regions || []).slice(0, 2))}${entry.mapRef ? `<span class="tag tag-accent">${escapeHtml(t(state.language, "labels.mapLinked"))}</span>` : ""}</div><div class="entry-card-actions">${button(buildRouteUrl(routeForEntry(state.language, entry)), t(state.language, "actions.open"))}${mapAction ? button(mapAction.href, mapLabel, false, true) : ""}</div></article>`;
}

export function renderSidebarNav(store) {
  return [
    navLink(routeForHome(state.language), t(state.language, "nav.home"), t(state.language, "home.summary"), state.route.view === "home", "world"),
    navLink(routeForSearch(state.language), t(state.language, "nav.search"), t(state.language, "labels.searchHint"), state.route.view === "search", "compass"),
    ...HUB_ORDER.map((id) => navLink(routeForHub(state.language, id), hubMeta(store, id)?.title?.[state.language] || id, hubMeta(store, id)?.description?.[state.language] || "", state.route.view === "hub" && state.route.kind === id, HUB_ICONS[id])),
  ].join("");
}

export function renderTopNav(store) {
  const topItems = [
    { kind: "home", id: "home", icon: "world" },
    { kind: "list", id: "characters", icon: LIST_ICONS.characters },
    { kind: "list", id: "weapons", icon: LIST_ICONS.weapons },
    { kind: "list", id: "armor", icon: LIST_ICONS.armor },
    { kind: "list", id: "engravings", icon: LIST_ICONS.engravings },
    { kind: "hub", id: "creatures", icon: HUB_ICONS.creatures },
    { kind: "list", id: "buffs", icon: LIST_ICONS.buffs },
    { kind: "list", id: "debuffs", icon: LIST_ICONS.debuffs },
    { kind: "hub", id: "resources", icon: HUB_ICONS.resources },
    { kind: "list", id: "items", icon: LIST_ICONS.items },
    { kind: "list", id: "recipes", icon: LIST_ICONS.recipes },
    { kind: "hub", id: "systems", icon: HUB_ICONS.systems },
  ];
  return topItems
    .filter((item) => {
      if (item.kind === "home") return true;
      if (item.kind === "hub") {
        return (hubMeta(store, item.id)?.lists || []).some((listId) => (listMeta(store, listId)?.count || 0) > 0);
      }
      return (listMeta(store, item.id)?.count || 0) > 0;
    })
    .map((item) => {
      if (item.kind === "home") {
        return navLink(routeForHome(state.language), t(state.language, "nav.home"), "", state.route.view === "home", item.icon);
      }
      if (item.kind === "hub") {
        return navLink(
          routeForHub(state.language, item.id),
          hubMeta(store, item.id)?.title?.[state.language] || item.id,
          "",
          state.route.view === "hub" && state.route.kind === item.id,
          item.icon,
          "category-item-hub",
        );
      }
      return navLink(
        routeForList(state.language, item.id),
        listMeta(store, item.id)?.title?.[state.language] || item.id,
        "",
        state.route.view === "list" && state.route.kind === item.id,
        item.icon,
        "category-item-collection",
      );
    })
    .join("");
}

export function renderQuickLinks(store) {
  return QUICK_LISTS.filter((id) => (listMeta(store, id)?.count || 0) > 0)
    .map((id) => navLink(routeForList(state.language, id), listMeta(store, id)?.title?.[state.language] || id, `${formatCount(listMeta(store, id)?.count || 0)} ${t(state.language, "labels.entries")}`, state.route.view === "list" && state.route.kind === id, LIST_ICONS[id]))
    .join("");
}

export function renderGuideLinks() {
  return GUIDE_PAGES.map((id) => navLink(routeForPage(state.language, id), pageText(id, "title"), pageText(id, "summary"), state.route.view === "page" && pageId(state.route) === id, PAGE_ICONS[id])).join("");
}

export function renderSuggestions(store, query) {
  const results = searchEntries(store, { q: query, limit: 8 });
  return results.length
    ? `<div class="search-suggestions-head"><strong>${escapeHtml(t(state.language, "search.suggestions"))}</strong><a href="${buildRouteUrl(routeForSearch(state.language, { q: query }))}" data-nav="true">${escapeHtml(t(state.language, "filters.searchResults"))}</a></div><div class="search-suggestion-list">${results.map((entry, index) => `<a id="searchSuggestion-${index}" class="search-suggestion ${state.suggestionIndex === index ? "is-active" : ""}" href="${buildRouteUrl(routeForEntry(state.language, entry))}" data-nav="true" data-suggestion-index="${index}" role="option" aria-selected="${state.suggestionIndex === index ? "true" : "false"}"><span class="search-suggestion-icon">${entry.image || entry.icon ? `<img src="${entry.image || entry.icon}" alt="" loading="lazy" />` : icon(LIST_ICONS[primaryList(entry)] || "world")}</span><span class="search-suggestion-copy"><strong>${escapeHtml(text(entry, "name"))}</strong><span>${escapeHtml(entryListLabel(store, entry))}</span></span></a>`).join("")}</div>`
    : empty(t(state.language, "filters.noSuggestions"));
}

export function renderBreadcrumbs(store, route) {
  const crumbs = [{ label: t(state.language, "nav.home"), route: routeForHome(state.language) }];
  if (route.view === "home") {
    return crumbs;
  }
  if (route.view === "search") {
    crumbs.push({ label: t(state.language, "search.title"), route: routeForSearch(state.language, route) });
    return crumbs;
  }
  if (route.view === "page") {
    crumbs.push({ label: pageText(pageId(route), "title"), route: routeForPage(state.language, pageId(route)) });
    return crumbs;
  }
  if (route.view === "hub" && route.kind) {
    crumbs.push({ label: hubMeta(store, route.kind)?.title?.[state.language] || titleCase(route.kind), route: routeForHub(state.language, route.kind) });
    return crumbs;
  }
  if ((route.view === "list" || route.view === "entry" || route.view === "region") && route.kind) {
    const listId = route.view === "entry" ? primaryList(resolveEntry(store, route) || {}) : route.kind;
    const hubId = listMeta(store, listId)?.hub || "";
    if (hubId) {
      crumbs.push({ label: hubMeta(store, hubId)?.title?.[state.language] || titleCase(hubId), route: routeForHub(state.language, hubId) });
    }
    if (listId) {
      crumbs.push({ label: listMeta(store, listId)?.title?.[state.language] || titleCase(listId), route: routeForList(state.language, listId) });
    }
  }
  if (route.view === "region") {
    const region = resolveEntry(store, route);
    if (region) crumbs.push({ label: text(region, "name"), route: routeForEntry(state.language, region) });
    return crumbs;
  }
  if (route.view === "entry") {
    const entry = resolveEntry(store, route);
    if (entry) {
      const regionId = entry.regionIds?.[0];
      const region = regionId ? store.regionById?.get(regionId) : null;
      if (region) crumbs.push({ label: text(region, "name"), route: routeForEntry(state.language, region) });
      crumbs.push({ label: text(entry, "name"), route: routeForEntry(state.language, entry) });
    }
  }
  return crumbs;
}
