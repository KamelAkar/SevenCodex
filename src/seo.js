import { resolveEntry } from "./data-store.js";
import { t } from "./i18n.js";
import { buildRouteUrl, routeForEntry, routeForHome, routeForHub, routeForList, routeForPage, routeForRegion, routeForSearch } from "./router.js";
import { state } from "./state.js";
import { hubMeta, listMeta, pageId, pageText, primaryList, renderBreadcrumbs, routeSubtitle, routeTitle, text } from "./render-kit.js";

const SITE_NAME = "SevenCodex";
const SITE_AUTHOR = "Ravnow";
const SITE_URL = "https://sevencodex.com/";
const SITE_OG_IMAGE = "/assets/og-card.svg";

const SITE_SUMMARY = {
  en: "SevenCodex is the bilingual wiki companion for Seven Deadly Sins: Origin, with structured game data, search, and direct links into SevenMap.",
  fr: "SevenCodex est le wiki compagnon bilingue de Seven Deadly Sins: Origin, avec donnees structurees, recherche et liens directs vers SevenMap.",
};

function trimText(value, max = 180) {
  const textValue = String(value || "").replace(/\s+/g, " ").trim();
  if (!textValue) return "";
  if (textValue.length <= max) return textValue;
  return `${textValue.slice(0, max - 1).trimEnd()}…`;
}

function localeTag(language) {
  return language === "fr" ? "fr_FR" : "en_US";
}

function creatorSchema() {
  return {
    "@type": "Person",
    name: SITE_AUTHOR,
  };
}

function ensureHeadNode(tagName, predicate, attributes = {}) {
  let node = [...document.head.querySelectorAll(tagName)].find(predicate) || null;
  if (!node) {
    node = document.createElement(tagName);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    document.head.appendChild(node);
  }
  return node;
}

function setMetaName(name, content) {
  const node = ensureHeadNode("meta", (candidate) => candidate.getAttribute("name") === name, { name });
  node.setAttribute("content", content);
}

function setMetaProperty(property, content) {
  const node = ensureHeadNode("meta", (candidate) => candidate.getAttribute("property") === property, { property });
  node.setAttribute("content", content);
}

function setLink(rel, href, extra = {}) {
  const node = ensureHeadNode(
    "link",
    (candidate) => candidate.getAttribute("rel") === rel && Object.entries(extra).every(([key, value]) => candidate.getAttribute(key) === value),
    { rel, ...extra },
  );
  node.setAttribute("href", href);
}

function absoluteAssetUrl(path) {
  return new URL(path, SITE_URL).toString();
}

function sanitizeRoute(route) {
  return {
    ...route,
    pointId: "",
    limit: "",
    stage: "",
    tab: "",
    style: "",
  };
}

function canonicalRoute(store, route) {
  const language = route.lang || state.language || "en";
  if (route.view === "search") {
    return routeForSearch(language);
  }
  if (route.view === "list") {
    if (route.q || route.region || route.rarity || route.classification) {
      return routeForList(language, route.kind);
    }
    return sanitizeRoute(routeForList(language, route.kind, { region: route.region || "", rarity: route.rarity || "", classification: route.classification || "" }));
  }
  if (route.view === "entry") {
    const entry = resolveEntry(store, route);
    return sanitizeRoute(entry ? routeForEntry(language, entry) : route);
  }
  if (route.view === "region") {
    return sanitizeRoute(routeForRegion(language, route.slug || ""));
  }
  if (route.view === "hub") {
    return sanitizeRoute(routeForHub(language, route.kind));
  }
  if (route.view === "page") {
    return sanitizeRoute(routeForPage(language, pageId(route)));
  }
  return sanitizeRoute(routeForHome(language));
}

function routeUrl(route) {
  const url = new URL(buildRouteUrl(route), SITE_URL);
  if (url.pathname.endsWith("/index.html")) {
    url.pathname = url.pathname.slice(0, -"/index.html".length) || "/";
  }
  return url.toString();
}

function routeScopeLabel(store, route, entry) {
  if (entry) {
    const listId = primaryList(entry);
    return listMeta(store, listId)?.title?.[state.language] || route.kind || entry.kind || "";
  }
  if (route.view === "home" || route.view === "search") return "";
  if (route.view === "hub") return hubMeta(store, route.kind)?.title?.[state.language] || route.kind || "";
  if (route.view === "list") return listMeta(store, route.kind)?.title?.[state.language] || route.kind || "";
  if (route.view === "page") return pageText(pageId(route), "title");
  return route.kind || route.view || "";
}

function seoTitle(store, route, entry) {
  const currentTitle = routeTitle(store, route);
  if (route.view === "home") {
    return "SevenCodex | 7DS Origin Wiki, Atlas & SevenMap Companion";
  }
  const scope = routeScopeLabel(store, route, entry);
  if (scope && scope !== currentTitle) {
    return `${currentTitle} | ${scope} | ${SITE_NAME}`;
  }
  return `${currentTitle} | ${SITE_NAME}`;
}

function seoDescription(store, route, entry) {
  if (route.view === "home") {
    return SITE_SUMMARY[state.language] || SITE_SUMMARY.en;
  }
  if (route.view === "search" && route.q) {
    return trimText(`${t(state.language, "search.title")}: ${route.q}. ${SITE_SUMMARY[state.language] || SITE_SUMMARY.en}`, 190);
  }
  if (entry) {
    return trimText(text(entry, "summary") || text(entry, "description") || `${text(entry, "name")} reference page in ${SITE_NAME}.`, 190);
  }
  return trimText(routeSubtitle(store, route) || SITE_SUMMARY[state.language] || SITE_SUMMARY.en, 190);
}

function seoKeywords(store, route, entry) {
  const keywords = new Set([SITE_NAME, "Seven Deadly Sins: Origin", "SevenMap"]);
  const add = (value) => {
    const textValue = String(value || "").trim();
    if (textValue) keywords.add(textValue);
  };
  add(routeTitle(store, route));
  add(routeScopeLabel(store, route, entry));
  if (entry) {
    add(entry.locale?.en?.name);
    add(entry.locale?.fr?.name);
    add(entry.kind);
    (entry.lists || []).slice(0, 4).forEach((listId) => add(listMeta(store, listId)?.title?.[state.language] || listId));
    (entry.regions || []).slice(0, 4).forEach(add);
  }
  if (route.kind) add(route.kind);
  if (route.q) add(route.q);
  return [...keywords].slice(0, 14).join(", ");
}

function indexPolicy(route) {
  const shouldIndex = !(
    route.view === "search" ||
    (route.view === "list" && (route.q || route.region || route.rarity || route.classification || route.limit))
  );
  return shouldIndex ? "index,follow,max-image-preview:large" : "noindex,follow,max-image-preview:large";
}

function breadcrumbSchema(store, route) {
  const items = renderBreadcrumbs(store, route).map((crumb, index) => ({
    "@type": "ListItem",
    position: index + 1,
    name: crumb.label,
    item: routeUrl(canonicalRoute(store, crumb.route)),
  }));
  return {
    "@type": "BreadcrumbList",
    itemListElement: items,
  };
}

function pageSchema(store, route, entry, canonical, title, description) {
  const schemaType =
    route.view === "entry"
      ? "Article"
      : route.view === "list" || route.view === "hub" || route.view === "search"
        ? "CollectionPage"
        : "WebPage";
  const schema = {
    "@type": schemaType,
    name: title,
    headline: title,
    description,
    url: canonical,
    inLanguage: state.language,
    isPartOf: { "@id": `${routeUrl(routeForHome(state.language))}#website` },
    author: creatorSchema(),
    creator: creatorSchema(),
  };
  if (entry) {
    schema.about = {
      "@type": "Thing",
      name: text(entry, "name"),
    };
  }
  return schema;
}

function websiteSchema() {
  const homeUrl = routeUrl(routeForHome(state.language));
  return {
    "@type": "WebSite",
    "@id": `${homeUrl}#website`,
    url: homeUrl,
    name: SITE_NAME,
    description: SITE_SUMMARY[state.language] || SITE_SUMMARY.en,
    inLanguage: ["en", "fr"],
    author: creatorSchema(),
    creator: creatorSchema(),
    potentialAction: {
      "@type": "SearchAction",
      target: routeUrl(routeForSearch(state.language, { q: "{search_term_string}" })),
      "query-input": "required name=search_term_string",
    },
  };
}

function syncStructuredData(store, route, entry, canonical, title, description) {
  const node = document.getElementById("structuredData");
  if (!node) return;
  const payload = {
    "@context": "https://schema.org",
    "@graph": [websiteSchema(), pageSchema(store, route, entry, canonical, title, description), breadcrumbSchema(store, route)],
  };
  node.textContent = JSON.stringify(payload);
}

export function syncSeo(store, route) {
  if (!store) return;
  const entry = resolveEntry(store, route);
  const canonical = routeUrl(canonicalRoute(store, route));
  const title = seoTitle(store, route, entry);
  const description = seoDescription(store, route, entry);
  const robots = indexPolicy(route);
  const socialImage = absoluteAssetUrl(SITE_OG_IMAGE);

  document.title = title;
  setMetaName("description", description);
  setMetaName("keywords", seoKeywords(store, route, entry));
  setMetaName("author", SITE_AUTHOR);
  setMetaName("creator", SITE_AUTHOR);
  setMetaName("robots", robots);
  setMetaName("googlebot", robots);

  setMetaProperty("og:site_name", SITE_NAME);
  setMetaProperty("og:type", route.view === "entry" ? "article" : "website");
  setMetaProperty("og:title", title);
  setMetaProperty("og:description", description);
  setMetaProperty("og:url", canonical);
  setMetaProperty("og:locale", localeTag(state.language));
  setMetaProperty("og:image", socialImage);
  setMetaProperty("og:image:type", "image/svg+xml");
  setMetaProperty("og:image:alt", `${SITE_NAME} social card`);

  setMetaName("twitter:card", "summary_large_image");
  setMetaName("twitter:title", title);
  setMetaName("twitter:description", description);
  setMetaName("twitter:image", socialImage);

  setLink("canonical", canonical);
  setLink("alternate", routeUrl(canonicalRoute(store, { ...route, lang: "en" })), { hreflang: "en" });
  setLink("alternate", routeUrl(canonicalRoute(store, { ...route, lang: "fr" })), { hreflang: "fr" });
  setLink("alternate", routeUrl(canonicalRoute(store, { ...route, lang: "en" })), { hreflang: "x-default" });

  syncStructuredData(store, route, entry, canonical, title, description);
}
