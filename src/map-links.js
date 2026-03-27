function ensureTrailingSlash(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.endsWith("/") ? text : `${text}/`;
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
  if (target.language) params.set("lang", target.language);
  if (target.pointId) params.set("point", target.pointId);
  if (target.entrySlug) params.set("entry", target.entrySlug);
  if (target.region) params.set("region", target.region);
  if (target.regions?.length) params.set("regions", target.regions.join(","));
  if (target.type) params.set("type", target.type);
  if (target.types?.length) params.set("types", target.types.join(","));
  if (target.subcategory) params.set("subcategory", target.subcategory);
  if (target.resourceItemId) params.set("resourceItemId", target.resourceItemId);
  if (target.petItemId) params.set("petItemId", target.petItemId);
  if (target.actorTid) params.set("actorTid", target.actorTid);
  if (target.monCatchTid) params.set("monCatchTid", target.monCatchTid);
  if (target.query) params.set("query", target.query);
  if (target.focus) params.set("focus", target.focus);
  if (target.open) params.set("open", target.open);
  return url.toString();
}

export function buildMapActions(entry, language) {
  const mapRef = entry?.mapRef;
  if (!mapRef) return null;
  const actions = [];
  if (mapRef.preferredPointId) {
    actions.push({
      label: language === "fr" ? "Ouvrir sur la carte" : "Open on Map",
      href: buildSevenMapUrl({
        language,
        pointId: mapRef.preferredPointId,
        entrySlug: entry.slug,
        type: mapRef.type,
        focus: "point",
        open: "details",
      }),
    });
  }
  actions.push({
    label: language === "fr" ? "Voir tous les emplacements" : "Show all locations",
    href: buildSevenMapUrl({
      language,
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
    }),
  });
  return actions;
}
