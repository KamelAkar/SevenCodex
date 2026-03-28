import { compactList, normalizeText } from "./utils.js";

const DATA_FILES = [
  "./data/manifest.json",
  "./data/regions.json",
  "./data/entries-resources.json",
  "./data/entries-heroes.json",
  "./data/entries-creatures.json",
  "./data/entries-systems.json",
  "./data/search-index.json",
];

let cache = null;

function flattenSearchTerms(value) {
  if (Array.isArray(value)) {
    return value.flatMap((nested) => flattenSearchTerms(nested));
  }
  if (value && typeof value === "object") {
    return Object.values(value).flatMap((nested) => flattenSearchTerms(nested));
  }
  const text = String(value || "").trim();
  return text ? [text] : [];
}

function sortableIndex(value) {
  if (value === null || value === undefined || value === "") return Number.MAX_SAFE_INTEGER;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : Number.MAX_SAFE_INTEGER;
}

function listSorter(a, b) {
  const sortA = sortableIndex(a?.sortIndex);
  const sortB = sortableIndex(b?.sortIndex);
  if (sortA !== sortB) return sortA - sortB;
  const rarityA = Number(a?.rarity?.rank) || 0;
  const rarityB = Number(b?.rarity?.rank) || 0;
  if (rarityA !== rarityB) return rarityB - rarityA;
  const mapA = a.mapRef?.pointIds?.length || 0;
  const mapB = b.mapRef?.pointIds?.length || 0;
  if (mapB !== mapA) return mapB - mapA;
  const nameA = a.locale?.en?.name || "";
  const nameB = b.locale?.en?.name || "";
  return nameA.localeCompare(nameB);
}

const POINT_ENTRY_PRIORITY = {
  pet: 90,
  monster: 88,
  boss: 86,
  waypoint: 84,
  portal: 82,
  puzzle: 80,
  "fishing-spot": 78,
  node: 76,
  item: 64,
  unlock: 40,
  recipe: 24,
  region: 0,
};

function pointEntryScore(entry) {
  const kind = String(entry?.kind || "").trim();
  const priority = POINT_ENTRY_PRIORITY[kind] ?? 16;
  const pointCount = entry?.mapRef?.pointIds?.length || 0;
  return priority * 10000 - Math.min(pointCount, 9999);
}

function scoreSearch(doc, query) {
  const q = normalizeText(query);
  if (!q) return 1;
  const titleEn = doc.titleEnNorm || normalizeText(doc.titleEn);
  const titleFr = doc.titleFrNorm || normalizeText(doc.titleFr);
  const haystack = doc.searchTextNorm || normalizeText(doc.searchText);
  if (titleEn === q || titleFr === q) return 100;
  if (titleEn.startsWith(q) || titleFr.startsWith(q)) return 85;
  if (titleEn.includes(q) || titleFr.includes(q)) return 70;
  if (haystack.includes(q)) return 40;
  return 0;
}

export async function loadCodexData() {
  if (cache) return cache;
  const [manifest, regions, resources, heroes, creatures, systems, searchIndex] = await Promise.all(
    DATA_FILES.map((url) =>
      fetch(url).then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load ${url}: ${response.status}`);
        }
        return response.json();
      }),
    ),
  );

  const entries = [...regions, ...resources, ...heroes, ...creatures, ...systems];
  const entryById = new Map();
  const entryBySlug = new Map();
  const pointToEntry = new Map();
  const listIndex = new Map();
  const regionBySlug = new Map();
  const regionById = new Map();

  for (const entry of entries) {
    const extraSearchTerms = flattenSearchTerms(entry.fields?.searchTerms);
    entry._searchBlob = normalizeText(
      [
        entry.locale?.en?.name,
        entry.locale?.fr?.name,
        entry.locale?.en?.summary,
        entry.locale?.fr?.summary,
        entry.locale?.en?.description,
        entry.locale?.fr?.description,
        ...(entry.regions || []),
        ...(entry.aliasSlugs || []),
        ...extraSearchTerms,
        JSON.stringify(entry.sourceIds || {}),
      ].join(" "),
    );
    entry._classNorm = normalizeText(entry.class);
    entryById.set(entry.id, entry);
    entryBySlug.set(`${entry.kind}:${entry.slug}`, entry);
    for (const aliasSlug of entry.aliasSlugs || []) {
      const aliasKey = `${entry.kind}:${aliasSlug}`;
      if (!entryBySlug.has(aliasKey)) {
        entryBySlug.set(aliasKey, entry);
      }
    }
    if (entry.kind === "region") {
      regionBySlug.set(entry.slug, entry);
      for (const regionId of entry.regionIds || []) {
        regionById.set(regionId, entry);
      }
    }
    for (const pointId of entry.mapRef?.pointIds || []) {
      const current = pointToEntry.get(pointId);
      if (!current || pointEntryScore(entry) > pointEntryScore(current)) {
        pointToEntry.set(pointId, entry);
      }
    }
    for (const listId of entry.lists || []) {
      const bucket = listIndex.get(listId) || [];
      bucket.push(entry);
      listIndex.set(listId, bucket);
    }
  }

  for (const [listId, bucket] of listIndex.entries()) {
    listIndex.set(listId, [...bucket].sort(listSorter));
  }

  const searchById = new Map(searchIndex.map((doc) => [doc.id, doc]));

  cache = {
    manifest,
    entries,
    entryById,
    entryBySlug,
    pointToEntry,
    listIndex,
    regionBySlug,
    regionById,
    searchIndex,
    searchById,
    searchCache: new Map(),
  };
  return cache;
}

export function resolveEntry(store, route) {
  if (route.pointId && store.pointToEntry.has(route.pointId)) {
    return store.pointToEntry.get(route.pointId);
  }
  if (route.view === "region") {
    return store.regionBySlug.get(route.slug || "") || null;
  }
  if (route.slug) {
    if (route.kind && store.entryBySlug.has(`${route.kind}:${route.slug}`)) {
      return store.entryBySlug.get(`${route.kind}:${route.slug}`);
    }
    for (const [key, entry] of store.entryBySlug.entries()) {
      if (key.endsWith(`:${route.slug}`)) {
        return entry;
      }
    }
  }
  return null;
}

export function listEntries(store, listId) {
  return store.listIndex.get(listId) || [];
}

export function filterEntries(entries, route) {
  const query = normalizeText(route.q);
  return entries.filter((entry) => {
    if (route.region && !(entry.regionIds || []).includes(route.region) && !(entry.regions || []).includes(route.region)) {
      return false;
    }
    if (route.rarity && entry.rarity?.grade !== route.rarity) {
      return false;
    }
    if (route.classification && (entry._classNorm || normalizeText(entry.class)) !== normalizeText(route.classification)) {
      return false;
    }
    if (!query) {
      return true;
    }
    const extraSearchTerms = flattenSearchTerms(entry.fields?.searchTerms);
    const haystack = entry._searchBlob || normalizeText(
      [
        entry.locale?.en?.name,
        entry.locale?.fr?.name,
        entry.locale?.en?.summary,
        entry.locale?.fr?.summary,
        entry.locale?.en?.description,
        entry.locale?.fr?.description,
        ...(entry.regions || []),
        ...(entry.aliasSlugs || []),
        ...extraSearchTerms,
        JSON.stringify(entry.sourceIds || {}),
      ].join(" "),
    );
    return haystack.includes(query);
  });
}

export function searchEntries(store, route) {
  const query = normalizeText(route.q || "");
  const region = route.region || "";
  const rarity = route.rarity || "";
  const scope = route.kind || "";
  const limit = Number.isFinite(Number(route.limit)) ? Math.max(0, Number(route.limit)) : 0;
  const cacheKey = JSON.stringify({ query, region, rarity, scope, limit });
  if (store.searchCache?.has(cacheKey)) {
    return store.searchCache.get(cacheKey);
  }

  const buckets = new Map([
    [100, []],
    [85, []],
    [70, []],
    [40, []],
    [1, []],
  ]);

  for (const doc of store.searchIndex) {
    const score = scoreSearch(doc, query);
    if (!query && !region && !rarity && !scope) continue;
    if (query && score <= 0) continue;
    if (scope && !(doc.lists || []).includes(scope) && doc.kind !== scope) continue;
    if (region && !(doc.regionIds || []).includes(region) && !(doc.regions || []).includes(region)) continue;
    if (rarity && doc.rarityGrade !== rarity) continue;
    buckets.get(score)?.push(doc);
  }

  const orderedDocs = [];
  for (const score of [100, 85, 70, 40, 1]) {
    const bucket = buckets.get(score) || [];
    bucket.sort((a, b) => {
      const sortA = sortableIndex(a.sortIndex);
      const sortB = sortableIndex(b.sortIndex);
      return (
        Number(b.mapLinked) - Number(a.mapLinked) ||
        sortA - sortB ||
        Number(b.rarityRank || 0) - Number(a.rarityRank || 0) ||
        String(a.titleEn || "").localeCompare(String(b.titleEn || ""))
      );
    });
    for (const doc of bucket) {
      const entry = store.entryById.get(doc.id);
      if (!entry) continue;
      orderedDocs.push(entry);
      if (limit && orderedDocs.length >= limit) {
        const results = compactList(orderedDocs);
        if (store.searchCache.size > 80) {
          const firstKey = store.searchCache.keys().next().value;
          store.searchCache.delete(firstKey);
        }
        store.searchCache.set(cacheKey, results);
        return results;
      }
    }
  }

  const results = compactList(orderedDocs);
  if (store.searchCache.size > 80) {
    const firstKey = store.searchCache.keys().next().value;
    store.searchCache.delete(firstKey);
  }
  store.searchCache.set(cacheKey, results);
  return results;
}

export function entriesForRegion(store, regionEntry) {
  const name = regionEntry?.locale?.en?.name || "";
  const regionIds = regionEntry?.regionIds || [];
  return store.entries
    .filter((entry) => {
      if (entry.id === regionEntry.id || entry.kind === "region") return false;
      if (regionIds.some((regionId) => (entry.regionIds || []).includes(regionId))) return true;
      return (entry.regions || []).includes(name);
    })
    .sort(listSorter);
}

export function relatedEntries(store, entry) {
  return compactList((entry.related || []).map((id) => store.entryById.get(id)).filter(Boolean));
}

export function optionsForEntries(entries) {
  return {
    regions: compactList(entries.flatMap((entry) => entry.regionIds || [])),
    rarity: compactList(entries.map((entry) => entry.rarity?.grade).filter(Boolean)),
    classifications: compactList(entries.map((entry) => entry.class).filter(Boolean)),
  };
}
