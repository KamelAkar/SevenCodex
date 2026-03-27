import { DEFAULT_LANGUAGE } from "./i18n.js";

function legacyHashRoute(hash) {
  const value = String(hash || "").replace(/^#\/?/, "");
  const parts = value.split("/").filter(Boolean);
  if (parts[0] === "category") return { view: "hub", kind: parts[1] || "regions" };
  if (parts[0] === "page") return { view: "page", kind: parts[1] || "about" };
  if (parts[0] === "search") return { view: "search" };
  return { view: "home" };
}

export function parseRoute(location = window.location) {
  const params = new URLSearchParams(location.search || "");
  const fallback = legacyHashRoute(location.hash);
  const view = params.get("view") || fallback.view || "home";
  const pageKind = params.get("page") || params.get("kind") || fallback.kind || "";
  return {
    lang: params.get("lang") || DEFAULT_LANGUAGE,
    view,
    kind: params.get("kind") || params.get("list") || fallback.kind || "",
    slug: params.get("slug") || "",
    pointId: params.get("point") || "",
    q: params.get("q") || params.get("query") || "",
    region: params.get("region") || "",
    rarity: params.get("rarity") || "",
    classification: params.get("class") || "",
    limit: params.get("limit") || "",
    stage: params.get("stage") || "",
    tab: params.get("tab") || "",
    style: params.get("style") || "",
    page: pageKind,
  };
}

export function buildRouteUrl(route = {}) {
  const url = new URL(window.location.href);
  url.hash = "";
  url.search = "";
  const params = url.searchParams;
  const view = route.view || "home";
  params.set("lang", route.lang || DEFAULT_LANGUAGE);
  params.set("view", view);
  if (route.kind) params.set("kind", route.kind);
  if (route.slug) params.set("slug", route.slug);
  if (route.pointId) params.set("point", route.pointId);
  if (route.q) params.set("q", route.q);
  if (route.region) params.set("region", route.region);
  if (route.rarity) params.set("rarity", route.rarity);
  if (route.classification) params.set("class", route.classification);
  if (route.limit) params.set("limit", route.limit);
  if (route.stage) params.set("stage", route.stage);
  if (route.tab) params.set("tab", route.tab);
  if (route.style) params.set("style", route.style);
  if (view === "page") {
    params.set("kind", route.kind || route.page || "about");
  }
  if (view === "search" && !route.q && !route.kind && !route.region && !route.rarity && !route.classification) {
    params.delete("kind");
    params.delete("region");
    params.delete("rarity");
    params.delete("class");
    params.delete("limit");
    params.delete("stage");
    params.delete("tab");
    params.delete("style");
  }
  if (view === "home") {
    params.delete("kind");
    params.delete("slug");
    params.delete("point");
    params.delete("q");
    params.delete("region");
    params.delete("rarity");
    params.delete("class");
    params.delete("limit");
    params.delete("stage");
    params.delete("tab");
    params.delete("style");
  }
  return `${url.pathname}${url.search}`;
}

export function navigate(route, { replace = false } = {}) {
  const href = buildRouteUrl(route);
  if (replace) {
    window.history.replaceState({}, "", href);
  } else {
    window.history.pushState({}, "", href);
  }
}

export function routeForHome(lang) {
  return { lang, view: "home" };
}

export function routeForHub(lang, kind) {
  return { lang, view: "hub", kind };
}

export function routeForList(lang, kind, extra = {}) {
  return { lang, view: "list", kind, ...extra };
}

export function routeForPage(lang, kind) {
  return { lang, view: "page", kind };
}

export function routeForRegion(lang, slug) {
  return { lang, view: "region", slug };
}

export function routeForSearch(lang, extra = {}) {
  return { lang, view: "search", ...extra };
}

export function routeForEntry(lang, entry) {
  if (entry.kind === "region") return routeForRegion(lang, entry.slug);
  return {
    lang,
    view: "entry",
    kind: entry.kind,
    slug: entry.slug,
    pointId: entry.mapRef?.preferredPointId || "",
  };
}
