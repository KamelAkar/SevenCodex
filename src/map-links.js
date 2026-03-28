function ensureTrailingSlash(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.endsWith("/") ? text : `${text}/`;
}

function normalizeParamValues(value) {
  if (Array.isArray(value)) {
    return [...new Set(value.map((entry) => String(entry || "").trim()).filter(Boolean))];
  }
  const text = String(value || "").trim();
  return text ? [text] : [];
}

function appendParam(params, key, value) {
  const values = normalizeParamValues(value);
  if (!values.length) return;
  params.set(key, values.join(","));
}

function isLocalDevHost() {
  if (typeof window === "undefined") return false;
  const hostname = String(window.location?.hostname || "").trim().toLowerCase();
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function isRootServedApp() {
  if (typeof window === "undefined") return false;
  const path = String(window.location?.pathname || "/").replace(/\/index\.html?$/i, "/");
  return path === "/";
}

function getLocalDevSiblingBaseUrl(portDelta, fallbackHref) {
  if (!isLocalDevHost() || !isRootServedApp()) return ensureTrailingSlash(fallbackHref);
  const currentPort = Number(window.location?.port || "");
  if (!Number.isFinite(currentPort) || currentPort <= 0) return ensureTrailingSlash(fallbackHref);
  const targetPort = currentPort + portDelta;
  if (targetPort <= 0) return ensureTrailingSlash(fallbackHref);
  return ensureTrailingSlash(`${window.location.protocol}//${window.location.hostname}:${targetPort}/`);
}

export function getSevenMapBaseUrl() {
  const globalValue = String(window.SEVENMAP_BASE_URL || "").trim();
  if (globalValue) return ensureTrailingSlash(new URL(globalValue, window.location.href).href);
  const meta = document.querySelector('meta[name="sevenmap-base"]');
  const content = String(meta?.content || "").trim();
  const resolved = ensureTrailingSlash(new URL(content || "../SevenMap/site/", window.location.href).href);
  return getLocalDevSiblingBaseUrl(-1, resolved);
}

export function buildSevenMapUrl(target = {}) {
  const url = new URL(getSevenMapBaseUrl(), window.location.href);
  const params = url.searchParams;
  params.set("view", "map");
  appendParam(params, "lang", target.language);
  appendParam(params, "point", target.pointId);
  appendParam(params, "pointIds", target.pointIds);
  appendParam(params, "entry", target.entrySlug);
  appendParam(params, "region", target.region);
  appendParam(params, "regions", target.regions);
  appendParam(params, "type", target.type);
  appendParam(params, "types", target.types);
  appendParam(params, "subcategory", target.subcategories || target.subcategory);
  appendParam(params, "resourceItemId", target.resourceItemIds || target.resourceItemId);
  appendParam(params, "petItemId", target.petItemIds || target.petItemId);
  appendParam(params, "actorTid", target.actorTids || target.actorTid);
  appendParam(params, "monCatchTid", target.monCatchTids || target.monCatchTid);
  appendParam(params, "query", target.query);
  appendParam(params, "focus", target.focus);
  appendParam(params, "open", target.open);
  return url.toString();
}

function mapFilterTarget(entry, language) {
  const mapRef = entry?.mapRef;
  if (!mapRef) return null;
  const pointIds = ["pet", "mining"].includes(String(mapRef.type || "").trim()) ? mapRef.pointIds || [] : [];
  return {
    language,
    pointIds,
    entrySlug: entry.slug,
    region: mapRef.regionIds?.[0] || mapRef.regions?.[0] || "",
    regions: mapRef.regionIds || [],
    type: mapRef.type,
    subcategory: mapRef.subcategory,
    resourceItemId: mapRef.resourceItemId,
    petItemId: mapRef.petItemId,
    actorTid: mapRef.actorTid,
    monCatchTid: mapRef.monCatchTid,
    focus: "fit",
    open: "filters",
  };
}

function mapPointTarget(entry, language) {
  const mapRef = entry?.mapRef;
  if (!mapRef?.preferredPointId) return null;
  return {
    language,
    pointId: mapRef.preferredPointId,
    entrySlug: entry.slug,
    type: mapRef.type,
    focus: "point",
    open: "details",
  };
}

function shouldPreferFilteredView(entry) {
  const mapRef = entry?.mapRef;
  if (!mapRef) return false;
  const pointCount = Array.isArray(mapRef.pointIds) ? mapRef.pointIds.filter(Boolean).length : 0;
  if (pointCount > 1) return true;
  return Boolean(mapRef.subcategory || mapRef.resourceItemId || mapRef.petItemId || mapRef.actorTid || mapRef.monCatchTid);
}

export function buildMapActions(entry, language) {
  const mapRef = entry?.mapRef;
  if (!mapRef) return null;
  const filterTarget = mapFilterTarget(entry, language);
  const pointTarget = mapPointTarget(entry, language);
  const preferFilter = shouldPreferFilteredView(entry);
  const primaryTarget = (preferFilter ? filterTarget : pointTarget) || filterTarget || pointTarget;
  const secondaryTarget = primaryTarget === pointTarget ? filterTarget : null;
  const actions = [];
  if (primaryTarget) {
    actions.push({
      label: language === "fr" ? "Ouvrir sur la carte" : "Open on Map",
      href: buildSevenMapUrl(primaryTarget),
    });
  }
  if (secondaryTarget) {
    actions.push({
      label: language === "fr" ? "Voir tous les emplacements" : "Show all locations",
      href: buildSevenMapUrl(secondaryTarget),
    });
  }
  return actions;
}
