import { GUIDE_PAGES, HUB_ORDER, LIST_ICONS, LIST_ORDER, QUICK_LISTS } from "./catalog.js";
import { entriesForRegion, filterEntries, listEntries, optionsForEntries, relatedEntries, resolveEntry, searchEntries } from "./data-store.js";
import { t } from "./i18n.js";
import { buildSevenMapUrl, getSevenMapBaseUrl } from "./map-links.js";
import { buildRouteUrl, routeForEntry, routeForHub, routeForList, routeForPage, routeForSearch } from "./router.js";
import { state } from "./state.js";
import { escapeHtml, escapeHtmlWithBreaks, formatCount, formatDateTime, kvRows, titleCase } from "./utils.js";
import {
  button,
  empty,
  entryListLabel,
  entryCard,
  guideCard,
  hubMeta,
  icon,
  listCard,
  listMeta,
  pageId,
  pageMeta,
  pageText,
  primaryList,
  regionLabel,
  routeSubtitle,
  routeTitle,
  stat,
  text,
} from "./render-kit.js";

const LIST_PAGE_SIZE = 180;
const SEARCH_PAGE_SIZE = 120;

function resolveRenderLimit(routeLimit, fallback) {
  const parsed = Number.parseInt(routeLimit, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(fallback, parsed);
}

function entriesShownLabel(shown, total) {
  return `${formatCount(shown)} / ${formatCount(total)} ${escapeHtml(t(state.language, "labels.entriesShown"))}`;
}

function copy(en, fr) {
  return state.language === "fr" ? fr : en;
}

function isRecipeCollectionEntry(entry) {
  return entry?.kind === "recipe" || (entry?.lists || []).includes("recipes");
}

function homeFeatured(store, key) {
  return (store.manifest.featured?.[key] || [])
    .map((ref) => store.entryById.get(ref.id))
    .filter(Boolean)
    .map((entry) => entryCard(store, entry))
    .join("");
}

function homeListSection(store, listId, eyebrow) {
  const entries = listEntries(store, listId).slice(0, 6);
  if (!entries.length) return "";
  const title = listMeta(store, listId)?.title?.[state.language] || titleCase(listId);
  return `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h3>${escapeHtml(title)}</h3></div><div class="entry-card-actions">${button(buildRouteUrl(routeForList(state.language, listId)), t(state.language, "actions.seeAll"))}</div></div><div class="entry-grid">${entries.map((entry) => entryCard(store, entry)).join("")}</div></section>`;
}

function commandDeckCard(store, listId) {
  const meta = listMeta(store, listId);
  if (!meta) return "";
  const preview = listEntries(store, listId).slice(0, 3);
  const title = meta.title?.[state.language] || titleCase(listId);
  const hubTitle = hubMeta(store, meta.hub)?.title?.[state.language] || titleCase(meta.hub || "");
  const media = preview
    .map((entry) => {
      const src = entry.image || entry.icon;
      return `<span class="command-card-preview-item">${src ? `<img src="${src}" alt="" loading="lazy" />` : `<span class="entry-card-icon">${icon(LIST_ICONS[listId] || "world")}</span>`}</span>`;
    })
    .join("");
  return `<article class="command-card"><div class="command-card-head"><div><p class="eyebrow">${escapeHtml(hubTitle)}</p><h4>${escapeHtml(title)}</h4></div><span class="tag">${formatCount(meta.count || 0)} ${escapeHtml(t(state.language, "labels.entries"))}</span></div><p class="command-card-text">${escapeHtml(meta.description?.[state.language] || "")}</p><div class="command-card-preview">${media}</div><div class="entry-card-actions">${button(buildRouteUrl(routeForList(state.language, listId)), t(state.language, "actions.open"))}</div></article>`;
}

function homeCommandDeck(store) {
  const order = ["characters", "weapons", "costumes", "buffs", "debuffs", "recipes", "quests", "bosses"];
  const cards = order.filter((id) => (listMeta(store, id)?.count || 0) > 0).map((id) => commandDeckCard(store, id));
  if (!cards.length) return "";
  return `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Codex coverage", "Couverture du codex"))}</p><h3>${escapeHtml(copy("Core game categories", "Categories principales"))}</h3></div><span class="tag">${formatCount(cards.length)} ${escapeHtml(t(state.language, "labels.sections"))}</span></div><div class="command-card-grid">${cards.join("")}</div></section>`;
}

function activeQuickLists(store) {
  return QUICK_LISTS.filter((id) => (listMeta(store, id)?.count || 0) > 0);
}

function listsForHub(store, hubId) {
  return Object.entries(store.manifest.lists || {})
    .filter(([, meta]) => meta.hub === hubId && (meta.count || 0) > 0)
    .map(([id]) => id)
    .sort((a, b) => {
      const indexA = LIST_ORDER.indexOf(a);
      const indexB = LIST_ORDER.indexOf(b);
      if (indexA !== indexB) {
        return (indexA < 0 ? Number.MAX_SAFE_INTEGER : indexA) - (indexB < 0 ? Number.MAX_SAFE_INTEGER : indexB);
      }
      return a.localeCompare(b);
    });
}

function hubTotals(store, hubId) {
  return listsForHub(store, hubId).reduce(
    (totals, listId) => {
      const meta = listMeta(store, listId);
      totals.count += meta?.count || 0;
      totals.mapLinkedCount += meta?.mapLinkedCount || 0;
      return totals;
    },
    { count: 0, mapLinkedCount: 0 },
  );
}

function selectableLists(store) {
  return Object.keys(store.manifest.lists || {})
    .filter((id) => (listMeta(store, id)?.count || 0) > 0)
    .sort((a, b) => {
      const indexA = LIST_ORDER.indexOf(a);
      const indexB = LIST_ORDER.indexOf(b);
      if (indexA !== indexB) {
        return (indexA < 0 ? Number.MAX_SAFE_INTEGER : indexA) - (indexB < 0 ? Number.MAX_SAFE_INTEGER : indexB);
      }
      return a.localeCompare(b);
    });
}

function homeActionLists(store) {
  const preferred = ["characters", "weapons", "costumes", "buffs", "debuffs", "quests", "bosses", "recipes"];
  return preferred.filter((id) => (listMeta(store, id)?.count || 0) > 0).slice(0, 6);
}

function hubIconName(hubId) {
  if (hubId === "regions") return "world";
  if (hubId === "resources") return "leaf";
  if (hubId === "heroes") return "user";
  if (hubId === "creatures") return "spark";
  return "compass";
}

function renderCoverageBlock(store, hubId) {
  const meta = hubMeta(store, hubId);
  const listIds = listsForHub(store, hubId);
  if (!meta || !listIds.length) return "";
  return `<article class="panel-inner coverage-block"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.coverage"))}</p><h4>${escapeHtml(meta.title?.[state.language] || titleCase(hubId))}</h4></div><span class="tag">${formatCount(listIds.length)} ${escapeHtml(t(state.language, "labels.sections"))}</span></div><p class="workspace-subtitle">${escapeHtml(meta.description?.[state.language] || "")}</p><div class="coverage-grid">${listIds.map((id) => listCard(store, id)).join("")}</div></article>`;
}

function renderHubCoverage(store) {
  return HUB_ORDER.map((hubId) => renderCoverageBlock(store, hubId)).filter(Boolean).join("");
}

function renderSiblingLists(store, listId) {
  const meta = listMeta(store, listId);
  const hubId = meta?.hub || "";
  const siblings = hubId ? listsForHub(store, hubId).filter((id) => id !== listId) : [];
  if (!siblings.length) return "";
  return `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.relatedCollections"))}</p><h3>${escapeHtml(t(state.language, "home.relatedLists"))}</h3></div></div><div class="coverage-grid">${siblings.slice(0, 4).map((id) => listCard(store, id)).join("")}</div></section>`;
}

function alternateName(entry) {
  const current = text(entry, "name");
  const other = state.language === "fr" ? entry.locale?.en?.name : entry.locale?.fr?.name;
  if (!other || other === current) return "";
  return other;
}

function relationRow(store, row, fallbackList = "items") {
  const linked = store.entryById.get(`item:${row.itemId}`) || null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const title = linked ? text(linked, "name") : row.itemId;
  const meta = linked ? entryListLabel(store, linked) : fallbackList;
  const media = linked?.icon || linked?.image || "";
  const wrapper = href ? "a" : "div";
  return `<article class="detail-media-row"><${wrapper} class="detail-media-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-media-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(meta)}</span></span><span class="tag detail-media-qty">x${escapeHtml(row.count)}</span></${wrapper}></article>`;
}

function relationCard(store, row, fallbackList = "items") {
  const linked = store.entryById.get(`item:${row.itemId}`) || null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const title = linked ? text(linked, "name") : row.itemId;
  const meta = linked ? entryListLabel(store, linked) : fallbackList;
  const media = linked?.icon || linked?.image || "";
  const wrapper = href ? "a" : "div";
  return `<article class="detail-mini-card recipe-formula-card"><${wrapper} class="detail-mini-card-link recipe-formula-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-mini-card-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-mini-card-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(meta)}</span></span><span class="tag detail-mini-card-qty">x${escapeHtml(row.count)}</span></${wrapper}></article>`;
}

function relationSection(store, entry, key, label, fallbackList = "items") {
  const rows = entry.fields?.[key] || [];
  if (!rows.length) return "";
  const content =
    entry.kind === "recipe"
      ? `<div class="detail-card-grid recipe-formula-grid">${rows.map((row) => relationCard(store, row, fallbackList)).join("")}</div>`
      : `<div class="detail-media-list">${rows.map((row) => relationRow(store, row, fallbackList)).join("")}</div>`;
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.details"))}</p><h4>${escapeHtml(label)}</h4></div><span class="tag">${formatCount(rows.length)}</span></div>${content}</article></section>`;
}

function recipeVariantSummary(store, variant, key, fallbackList = "items") {
  return (variant?.[key] || [])
    .map((row) => {
      const linked = store.entryById.get(`item:${row.itemId}`) || null;
      const title = linked ? text(linked, "name") : row.itemId || fallbackList;
      return `${title} x${row.count}`;
    })
    .join(", ");
}

function recipeVariantSection(store, entry) {
  const variants = entry.fields?.variants || [];
  if (entry.kind !== "recipe" || variants.length < 2) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Craft variants", "Variantes de craft"))}</p><h4>${escapeHtml(copy("Recipe variants", "Variantes de recette"))}</h4></div><span class="tag">${formatCount(variants.length)}</span></div><div class="detail-card-grid recipe-variant-grid">${variants
    .map((variant, index) => {
      const chips = [
        variant.functionType ? detailTag(titleCase(variant.functionType), "context") : "",
        variant.showRewardLevel ? detailTag(`${copy("Lv.", "Niv.")} ${formatCount(variant.showRewardLevel)}`) : "",
        variant.contentsLevel ? detailTag(`${copy("Tier", "Palier")} ${formatCount(variant.contentsLevel)}`) : "",
        variant.priority ? detailTag(`${copy("Order", "Ordre")} ${formatCount(variant.priority)}`) : "",
      ]
        .filter(Boolean)
        .join("");
      const ingredients = recipeVariantSummary(store, variant, "materials");
      const rewards = recipeVariantSummary(store, variant, "rewards");
      return `<article class="detail-mini-card recipe-variant-card"><div class="detail-mini-card-copy"><strong>${escapeHtml(`${copy("Variant", "Variante")} ${index + 1}`)}</strong><span>${escapeHtml(ingredients || copy("No ingredient data", "Pas de donnees d'ingredients"))}</span>${rewards ? `<span>${escapeHtml(rewards)}</span>` : ""}</div>${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}</article>`;
    })
    .join("")}</div></article></section>`;
}

function acquisitionKindLabel(kind) {
  if (kind === "dungeon") return copy("Dungeon reward", "Recompense de donjon");
  if (kind === "monster") return copy("Monster drop", "Butin de monstre");
  if (kind === "quest") return copy("Quest reward", "Recompense de quete");
  if (kind === "recipe") return copy("Craft source", "Source de craft");
  if (kind === "event") return copy("Event reward", "Recompense d'evenement");
  return copy("Acquisition", "Obtention");
}

function detailTag(label, tone = "") {
  if (!label) return "";
  return `<span class="tag tag-detail${tone ? ` tag-detail-${tone}` : ""}">${escapeHtml(label)}</span>`;
}

function formatDropPercent(value) {
  return new Intl.NumberFormat(state.language === "fr" ? "fr-FR" : "en-US", {
    maximumFractionDigits: Number(value) % 1 === 0 ? 0 : Number(value) < 1 ? 2 : 1,
    minimumFractionDigits: Number(value) > 0 && Number(value) < 1 ? 2 : 0,
  }).format(Number(value));
}

function parseLevelIndex(value) {
  const match = String(value || "").match(/level[_-]?(\d+)/i);
  return match ? Number.parseInt(match[1], 10) || 0 : 0;
}

function worldLevelLabel(value) {
  const level = parseLevelIndex(value);
  if (!level) return "";
  return copy(`World Lv. ${level}`, `Niveau du monde ${level}`);
}

function normalizeStageToken(value, sourceKind = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const level = parseLevelIndex(raw);
  if (!level) return raw;
  if (sourceKind === "dungeon") {
    return copy(`Difficulty ${level}`, `Difficulte ${level}`);
  }
  return worldLevelLabel(raw);
}

function normalizeSourceContextText(value, sourceKind = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return raw.replace(/Level[_-]?(\d+)/gi, (_, level) => normalizeStageToken(`level_${level}`, sourceKind));
}

function lootStageLabel(row) {
  if (row?.sourceKind === "dungeon" || row?.kind === "dungeon") {
    return normalizeStageToken(row?.difficulty?.[state.language] || row?.difficulty?.en || row?.standardLevel || "", "dungeon");
  }
  return worldLevelLabel(row?.standardLevel);
}

function acquisitionRateLabel(row) {
  if (row?.rateMode === "guaranteed") return copy("Guaranteed", "Garanti");
  if (Number.isFinite(Number(row?.rateDisplayPct)) && Number(row.rateDisplayPct) > 0) {
    return `${copy("Drop", "Drop")} ${formatDropPercent(row.rateDisplayPct)}%`;
  }
  if (row?.rateMode === "weight" && Number(row?.rateRaw) > 0) {
    if (Number(row?.rateWeightTotal) > 0) {
      return `${copy("Weight", "Poids")} ${formatCount(row.rateRaw)} / ${formatCount(row.rateWeightTotal)}`;
    }
    return `${copy("Weight", "Poids")} ${formatCount(row.rateRaw)}`;
  }
  return "";
}

function acquisitionGroupRateLabel(row) {
  return "";
}

function lootRateLabel(row) {
  if (row?.rateMode === "guaranteed") return copy("Guaranteed", "Garanti");
  if (Number.isFinite(Number(row?.rateDisplayPct)) && Number(row.rateDisplayPct) > 0) {
    return `${formatDropPercent(row.rateDisplayPct)}%`;
  }
  if (row?.rateMode === "weight" && Number(row?.rateRaw) > 0 && Number(row?.rateWeightTotal) > 0) {
    return `${copy("Weight", "Poids")} ${formatCount(row.rateRaw)} / ${formatCount(row.rateWeightTotal)}`;
  }
  return "";
}

function rowStageOrder(row) {
  const explicitLevel = parseLevelIndex(row?.standardLevel);
  if (explicitLevel) return explicitLevel;
  const difficulty = String(row?.difficulty?.en || row?.difficulty?.[state.language] || "").toLowerCase();
  if (!difficulty) return 0;
  if (difficulty.includes("easy") || difficulty.includes("facile")) return 1;
  if (difficulty.includes("normal")) return 2;
  if (difficulty.includes("hard") || difficulty.includes("difficile")) return 3;
  if (difficulty.includes("nightmare") || difficulty.includes("cauchemar")) return 4;
  if (difficulty.includes("infernal") || difficulty.includes("hell")) return 5;
  return 0;
}

function rowRateScore(row) {
  if (row?.rateMode === "guaranteed") return 1000000;
  if (Number.isFinite(Number(row?.rateDisplayPct)) && Number(row.rateDisplayPct) > 0) {
    return Number(row.rateDisplayPct);
  }
  if (row?.rateMode === "weight" && Number(row?.rateRaw) > 0 && Number(row?.rateWeightTotal) > 0) {
    return Number(row.rateRaw) / Number(row.rateWeightTotal);
  }
  return 0;
}

function contextKindOrder(kind) {
  if (kind === "monster") return 0;
  if (kind === "dungeon") return 1;
  if (kind === "quest") return 2;
  if (kind === "recipe") return 3;
  if (kind === "event") return 4;
  return 9;
}

function contextRowTitle(row) {
  return row?.name?.[state.language] || row?.name?.en || row?.sourceId || "";
}

function compareContextRows(a, b) {
  const rateDiff = rowRateScore(b) - rowRateScore(a);
  if (Math.abs(rateDiff) > 0.0001) return rateDiff;
  const powerDiff = Number(b?.recommendedPower || 0) - Number(a?.recommendedPower || 0);
  if (powerDiff) return powerDiff;
  return contextRowTitle(a).localeCompare(contextRowTitle(b), state.language === "fr" ? "fr" : "en");
}

function compareContextGroups(a, b) {
  const kindDiff = contextKindOrder(a.sourceKind) - contextKindOrder(b.sourceKind);
  if (kindDiff) return kindDiff;
  const stageDiff = Number(a.stageOrder || 0) - Number(b.stageOrder || 0);
  if (stageDiff) return stageDiff;
  return String(a.label || "").localeCompare(String(b.label || ""), state.language === "fr" ? "fr" : "en");
}

function buildContextGroups(rows, fallbackLabel) {
  const groups = [];
  const byKey = new Map();
  rows.forEach((row) => {
    const label = lootStageLabel(row) || fallbackLabel(row);
    const sourceKind = row?.sourceKind || row?.kind || "";
    const key = `${sourceKind || "source"}:${label}`;
    let group = byKey.get(key);
    if (!group) {
      group = {
        key,
        label,
        sourceKind,
        recommendedPower: 0,
        stageOrder: rowStageOrder(row),
        rows: [],
      };
      byKey.set(key, group);
      groups.push(group);
    }
    group.rows.push(row);
    group.recommendedPower = Math.max(group.recommendedPower || 0, Number(row?.recommendedPower) || 0);
    group.stageOrder = Math.max(group.stageOrder || 0, rowStageOrder(row));
  });
  groups.forEach((group) => {
    group.rows.sort(compareContextRows);
  });
  return groups.sort(compareContextGroups);
}

function acquisitionSectionNote(groups) {
  const sourceKinds = [...new Set(groups.map((group) => group.sourceKind).filter(Boolean))];
  if (sourceKinds.length === 1 && sourceKinds[0] === "monster") {
    return copy(
      "Item sources change with world level. Choose one world level above to narrow the acquisition list.",
      "Les sources de cet objet changent selon le niveau du monde. Choisis un niveau du monde ci-dessus pour filtrer la liste.",
    );
  }
  if (sourceKinds.length === 1 && sourceKinds[0] === "dungeon") {
    return copy(
      "Item sources change with dungeon difficulty. Choose one difficulty above to narrow the acquisition list.",
      "Les sources de cet objet changent selon la difficulte du donjon. Choisis une difficulte ci-dessus pour filtrer la liste.",
    );
  }
  if (sourceKinds.length === 1 && sourceKinds[0] === "quest") {
    return copy(
      "This item is also awarded directly through quest progression.",
      "Cet objet est aussi accorde directement via la progression des quetes.",
    );
  }
  if (sourceKinds.length === 1 && sourceKinds[0] === "recipe") {
    return copy(
      "This item is crafted through one or more recipes.",
      "Cet objet se fabrique via une ou plusieurs recettes.",
    );
  }
  return copy(
    "Choose a source context above to focus the acquisition list on one stage or source family.",
    "Choisis un contexte de source ci-dessus pour te concentrer sur un niveau ou une famille de sources.",
  );
}

function acquisitionCard(store, row) {
  const linked = row.relatedEntryId ? store.entryById.get(row.relatedEntryId) : null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const media = row.image || row.icon || linked?.image || linked?.icon || "";
  const title = contextRowTitle(row);
  const subtitle = row.subtitle?.[state.language] || row.subtitle?.en || "";
  const bossName = row.bossName?.[state.language] || row.bossName?.en || "";
  const unlockQuest = row.unlockQuest?.[state.language] || row.unlockQuest?.en || "";
  const grade = row.grade?.[state.language] || row.grade?.en || "";
  const conditionType = row.conditionType?.[state.language] || row.conditionType?.en || "";
  const titleLower = title.toLowerCase();
  const bossChip = bossName && !titleLower.includes(bossName.toLowerCase()) ? `${copy("Boss", "Boss")}: ${bossName}` : "";
  const countChip = lootCountLabel(row);
  const conditionChip = conditionType ? `${copy("Condition", "Condition")} ${conditionType}${row.conditionValue ? ` ${formatCount(row.conditionValue)}` : ""}` : "";
  const chips = [
    { label: bossChip, tone: "context" },
    { label: grade, tone: "" },
    { label: row.recommendedPower ? `${copy("BP", "PC")} ${formatCount(row.recommendedPower)}` : "", tone: "power" },
    { label: row.qualityMax ? `${copy("Quality", "Qualite")} ${formatCount(row.qualityMax)}` : "", tone: "" },
    { label: lootRateLabel(row) || acquisitionRateLabel(row), tone: "rate" },
    { label: conditionChip, tone: "" },
    { label: unlockQuest ? `${copy("Unlock", "Deblocage")}: ${unlockQuest}` : "", tone: "" },
    { label: countChip, tone: "" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  const wrapper = href ? "a" : "div";
  return `<article class="detail-mini-card acquisition-card"><${wrapper} class="detail-mini-card-link acquisition-card-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-mini-card-thumb acquisition-card-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon(row.kind === "recipe" ? "anvil" : row.kind === "quest" ? "scroll" : row.kind === "event" ? "star" : row.kind === "monster" ? "fang" : "gate")}</span><span class="detail-mini-card-copy acquisition-card-copy"><strong>${escapeHtml(title)}</strong>${subtitle ? `<span>${escapeHtml(subtitle)}</span>` : ""}</span>${chips ? `<div class="detail-chip-row detail-chip-row-rich acquisition-card-chips">${chips}</div>` : ""}</${wrapper}></article>`;
}

function itemAcquisitionSection(store, entry) {
  if (entry.kind !== "item") return "";
  const rows = entry.fields?.acquisitionSources || [];
  if (!rows.length) return "";
  const groups = buildContextGroups(rows, (row) => acquisitionKindLabel(row.kind));
  const selectedGroupKey = activeLootGroupKey(groups);
  const visibleGroups = groups.length > 1 ? groups.filter((group) => group.key === selectedGroupKey) : groups;
  const note = acquisitionSectionNote(groups);
  const selector =
    groups.length > 1
      ? `<div class="loot-toolbar"><div class="loot-stage-picker"><span class="loot-stage-label">${escapeHtml(lootFilterLabel(groups))}</span><div class="loot-stage-tabs">${groups
          .map(
            (group) =>
              `<a class="chip loot-stage-chip ${group.key === selectedGroupKey ? "is-active" : ""}" href="${buildRouteUrl({ ...state.route, stage: group.key })}" data-nav="true" ${group.key === selectedGroupKey ? 'aria-current="true"' : ""}>${escapeHtml(group.label)}</a>`,
          )
          .join("")}</div></div></div>`
      : "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("How to get it", "Comment l'obtenir"))}</p><h4>${escapeHtml(copy("Acquisition sources", "Sources d'obtention"))}</h4>${note ? `<p class="workspace-subtitle loot-section-note">${escapeHtml(note)}</p>` : ""}</div><span class="tag">${formatCount(rows.length)}</span></div>${selector}<div class="loot-group-stack">${visibleGroups
    .map((group) => {
      const groupChips = [
        detailTag(lootGroupEyebrow(group), "context"),
        group.recommendedPower ? detailTag(`${copy("BP", "PC")} ${formatCount(group.recommendedPower)}`, "power") : "",
        detailTag(`${formatCount(group.rows.length)} ${copy("sources", "sources")}`),
      ]
        .filter(Boolean)
        .join("");
      return `<section class="loot-group"><div class="loot-group-head"><div><p class="eyebrow">${escapeHtml(lootGroupEyebrow(group))}</p><h5>${escapeHtml(group.label)}</h5></div><div class="detail-chip-row detail-chip-row-rich">${groupChips}</div></div><div class="detail-card-grid acquisition-card-grid">${group.rows.map((row) => acquisitionCard(store, row)).join("")}</div></section>`;
    })
    .join("")}</div></article></section>`;
}

function itemDisassemblySection(store, entry) {
  if (entry.kind !== "item") return "";
  const disassembly = entry.fields?.disassembly || null;
  const outputs = disassembly?.outputs || [];
  if (!outputs.length) return "";
  const currencies = disassembly?.currencies || [];
  const currencyMarkup = currencies.length
    ? `<div class="detail-chip-row detail-chip-row-rich">${currencies
        .map((row) =>
          detailTag(
            `${row.currencyId} ${lootCountLabel(row)}${lootRateLabel(row) ? ` - ${lootRateLabel(row)}` : ""}`.trim(),
            "context",
          ),
        )
        .join("")}</div>`
    : "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Recycle", "Recyclage"))}</p><h4>${escapeHtml(copy("Recycle output", "Rendement de recyclage"))}</h4><p class="workspace-subtitle loot-section-note">${escapeHtml(itemDisassemblyNote(disassembly))}</p></div><span class="tag">${formatCount(outputs.length)}</span></div><div class="detail-card-grid loot-card-grid">${outputs.map((row) => recyclingCard(store, row)).join("")}</div>${currencyMarkup}</article></section>`;
}

function recyclingSourceCard(store, row) {
  const rarityLabel = row.rarity?.label?.[state.language] || "";
  const chips = [
    { label: rarityLabel, tone: "" },
    { label: lootRateLabel(row), tone: "rate" },
    { label: lootCountLabel(row), tone: "" },
    { label: recyclingLevelCurveLabel(row), tone: "context" },
    { label: row.sourceCount ? `${formatCount(row.sourceCount)} ${copy("items", "objets")}` : "", tone: "context" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  const samples = (row.sampleItems || [])
    .slice(0, 4)
    .map((sample) => {
      const linked = sample.itemId ? store.entryById.get(`item:${sample.itemId}`) : null;
      const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
      const wrapper = href ? "a" : "div";
      const media = sample.icon || linked?.icon || linked?.image || "";
      const name = linked ? text(linked, "name") : sample.name?.[state.language] || sample.name?.en || sample.itemId;
      return `<${wrapper} class="recycle-source-sample" ${href ? `href="${href}" data-nav="true"` : ""}>${media ? `<span class="recycle-source-sample-thumb"><img src="${media}" alt="" loading="lazy" /></span>` : ""}<span>${escapeHtml(name)}</span></${wrapper}>`;
    })
    .join("");
  return `<article class="detail-mini-card recycle-source-card"><div class="detail-mini-card-copy recycle-source-copy"><strong>${escapeHtml(row.label?.[state.language] || row.label?.en || "")}</strong><span>${escapeHtml(copy("Obtained by recycling this gear family.", "Obtenable en recyclant cette famille d'equipement."))}</span></div>${chips ? `<div class="detail-chip-row detail-chip-row-rich loot-card-chips">${chips}</div>` : ""}${samples ? `<div class="recycle-source-sample-grid">${samples}</div>` : ""}</article>`;
}

function itemRecycledFromSection(store, entry) {
  if (entry.kind !== "item") return "";
  const rows = entry.fields?.recycledFrom || [];
  if (!rows.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Reverse recycling", "Recyclage inverse"))}</p><h4>${escapeHtml(copy("Obtained by recycling", "Obtenable en recyclant"))}</h4><p class="workspace-subtitle loot-section-note">${escapeHtml(copy("These are the item families that can be dismantled into this material or fragment.", "Voici les familles d'equipement qui peuvent etre recyclees pour obtenir ce materiau ou ce fragment."))}</p></div><span class="tag">${formatCount(rows.length)}</span></div><div class="detail-card-grid recycle-source-grid">${rows.map((row) => recyclingSourceCard(store, row)).join("")}</div></article></section>`;
}

function equipmentGrowthEffectCard(row) {
  const slotLabel = row.slotType === "main" ? copy("Main stat", "Stat principal") : copy("Sub stat", "Stat secondaire");
  const chips = [
    { label: slotLabel, tone: "context" },
    { label: row.value?.[state.language] || row.value?.en || "", tone: "rate" },
    { label: row.growthSummary?.[state.language] ? `${copy("Growth", "Progression")} ${row.growthSummary[state.language]}` : "", tone: "" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  return `<article class="detail-mini-card equipment-effect-card"><div class="equipment-effect-head"><span class="detail-media-thumb detail-mini-card-thumb equipment-effect-thumb">${row.icon ? `<img src="${row.icon}" alt="" loading="lazy" />` : icon("spark")}</span><div class="detail-mini-card-copy"><strong>${escapeHtml(row.label?.[state.language] || row.label?.en || row.id || "")}</strong><span>${escapeHtml(copy("Base equipment stat", "Stat d'equipement de base"))}</span></div></div>${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}</article>`;
}

function equipmentOptionCard(row) {
  const tierLabel =
    row.tierMin && row.tierMax
      ? row.tierMin === row.tierMax
        ? `${copy("Tier", "Palier")} ${formatCount(row.tierMin)}`
        : `${copy("Tiers", "Paliers")} ${formatCount(row.tierMin)}-${formatCount(row.tierMax)}`
      : "";
  const chips = [
    { label: row.range?.[state.language] || row.range?.en || "", tone: "rate" },
    { label: row.optionRatePct ? `${formatDropPercent(row.optionRatePct)}% ${copy("pool", "pool")}` : "", tone: "context" },
    { label: tierLabel, tone: "" },
    { label: row.stepValue?.[state.language] ? `${copy("Step", "Palier")} ${row.stepValue[state.language]}` : "", tone: "" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  return `<article class="detail-mini-card equipment-effect-card"><div class="equipment-effect-head"><span class="detail-media-thumb detail-mini-card-thumb equipment-effect-thumb">${row.icon ? `<img src="${row.icon}" alt="" loading="lazy" />` : icon("spark")}</span><div class="detail-mini-card-copy"><strong>${escapeHtml(row.label?.[state.language] || row.label?.en || row.abilityId || "")}</strong><span>${escapeHtml(copy("Possible random effect", "Effet aleatoire possible"))}</span></div></div>${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}</article>`;
}

function equipmentPassiveCard(row) {
  const activeLevel = (row.levels || []).find((level) => Number(level.level) === Number(row.level)) || null;
  const rollChips = (row.rolls || [])
    .map((roll) => detailTag(`${copy("Lv.", "Niv.")} ${formatCount(roll.level)} / ${formatDropPercent(roll.grantChancePct)}%`, Number(roll.level) === Number(row.level) ? "rate" : "context"))
    .join("");
  const levelRows = (row.levels || [])
    .map((level) => {
      const description = level.description?.[state.language] || level.description?.en || "";
      if (!description) return "";
      return `<div class="passive-level-row"><span class="tag tag-detail tag-detail-context">${escapeHtml(`${copy("Lv.", "Niv.")} ${formatCount(level.level)}`)}</span><span>${escapeHtml(description)}</span></div>`;
    })
    .filter(Boolean)
    .join("");
  const chips = [
    { label: row.grantChancePct ? `${formatDropPercent(row.grantChancePct)}% ${copy("grant", "attribution")}` : "", tone: "rate" },
    { label: row.level ? `${copy("Lv.", "Niv.")} ${formatCount(row.level)}/${formatCount(row.maxLevel || row.level)}` : "", tone: "context" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  return `<article class="detail-mini-card equipment-effect-card equipment-passive-card"><div class="equipment-effect-head"><span class="detail-media-thumb detail-mini-card-thumb equipment-effect-thumb">${row.icon ? `<img src="${row.icon}" alt="" loading="lazy" />` : icon("spark")}</span><div class="detail-mini-card-copy"><strong>${escapeHtml(row.name?.[state.language] || row.name?.en || row.id || "")}</strong><span>${escapeHtml(activeLevel?.description?.[state.language] || row.description?.[state.language] || row.description?.en || "")}</span></div></div>${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}${rollChips ? `<div class="detail-chip-row detail-chip-row-rich passive-roll-row">${rollChips}</div>` : ""}${levelRows ? `<div class="passive-level-list">${levelRows}</div>` : ""}</article>`;
}

function itemEquipmentEffectsSection(entry) {
  if (entry.kind !== "item") return "";
  const growthEffects = entry.fields?.equipmentGrowthEffects || [];
  const optionPools = entry.fields?.equipmentOptionPools || [];
  const passives = entry.fields?.equipmentPassives || [];
  if (!growthEffects.length && !optionPools.length && !passives.length) return "";
  const blocks = [];
  if (growthEffects.length) {
    blocks.push(`<div class="equipment-effect-block"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Fixed stats", "Stats fixes"))}</p><h5>${escapeHtml(copy("Base stat effects", "Effets de base"))}</h5></div><span class="tag">${formatCount(growthEffects.length)}</span></div><div class="detail-card-grid equipment-effect-grid">${growthEffects.map((row) => equipmentGrowthEffectCard(row)).join("")}</div></div>`);
  }
  if (optionPools.length) {
    blocks.push(
      optionPools
        .map((pool) => `<div class="equipment-effect-block"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Random options", "Options aleatoires"))}</p><h5>${escapeHtml(copy("Option pool", "Pool d'effets"))}</h5></div><span class="tag">${escapeHtml(`x${formatCount(pool.slotCount || 1)}`)}</span></div><div class="detail-card-grid equipment-effect-grid">${(pool.rows || []).map((row) => equipmentOptionCard(row)).join("")}</div></div>`)
        .join(""),
    );
  }
  if (passives.length) {
    blocks.push(`<div class="equipment-effect-block"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Unique passives", "Passifs uniques"))}</p><h5>${escapeHtml(copy("Passive effects", "Effets passifs"))}</h5></div><span class="tag">${formatCount(passives.length)}</span></div><div class="detail-card-grid equipment-effect-grid">${passives.map((row) => equipmentPassiveCard(row)).join("")}</div></div>`);
  }
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Equipment effects", "Effets d'equipement"))}</p><h4>${escapeHtml(copy("Stats, rolls, and passives", "Stats, rolls et passifs"))}</h4></div><span class="tag">${formatCount(growthEffects.length + passives.length + optionPools.reduce((sum, pool) => sum + ((pool.rows || []).length || 0), 0))}</span></div><div class="equipment-effect-stack">${blocks.join("")}</div></article></section>`;
}

function setBonusTitle(bonus) {
  const raw = bonus.name?.[state.language] || bonus.name?.en || "";
  if (bonus.type === "passive") {
    return raw || copy("Passive bonus", "Bonus passif");
  }
  if (!raw || /^set\s+\d+/i.test(raw) || /^epset/i.test(raw)) {
    return copy("Stat bonus", "Bonus de stats");
  }
  return raw;
}

function groupSetPieceEntries(store, set) {
  const groups = new Map();
  for (const itemId of set.pieceIds || []) {
    const piece = store.entryById.get(`item:${itemId}`);
    if (!piece) continue;
    const key = piece.class || piece.fields?.itemDivision || piece.fields?.itemDetailType || piece.id;
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, { key, piece, variants: [piece] });
      continue;
    }
    existing.variants.push(piece);
    if ((piece.rarity?.rank || 0) > (existing.piece?.rarity?.rank || 0)) {
      existing.piece = piece;
    }
  }
  return [...groups.values()].sort((a, b) => String(a.key || "").localeCompare(String(b.key || ""), state.language === "fr" ? "fr" : "en"));
}

function equipmentSetBonusSection(store, entry) {
  if (entry.kind !== "item") return "";
  const sets = entry.fields?.equipmentSets || [];
  if (!sets.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Set bonuses", "Bonus de set"))}</p><h4>${escapeHtml(copy("Active equipment set", "Set d'equipement"))}</h4></div><span class="tag">${formatCount(sets.length)}</span></div><div class="equipment-set-stack">${sets
    .map((set) => {
      const pieceGroups = groupSetPieceEntries(store, set);
      const pieceMarkup = pieceGroups.length
        ? `<div class="detail-card-grid equipment-set-piece-grid">${pieceGroups
            .map(
              (group) =>
                `<a class="detail-mini-card-link equipment-set-piece" href="${buildRouteUrl(routeForEntry(state.language, group.piece))}" data-nav="true"><span class="detail-media-thumb detail-mini-card-thumb">${group.piece.icon ? `<img src="${group.piece.icon}" alt="" loading="lazy" />` : icon("shield")}</span><span class="detail-mini-card-copy"><strong>${escapeHtml(group.key)}</strong><span>${escapeHtml(text(group.piece, "name"))}</span>${group.variants.length > 1 ? `<span>${escapeHtml(`${formatCount(group.variants.length)} ${copy("variants", "variantes")}`)}</span>` : ""}</span></a>`,
            )
            .join("")}</div>`
        : "";
      const bonusMarkup = (set.bonuses || [])
        .map(
          (bonus) => `<article class="detail-mini-card equipment-set-bonus-card"><div class="equipment-effect-head"><span class="detail-media-thumb detail-mini-card-thumb equipment-effect-thumb">${bonus.icon ? `<img src="${bonus.icon}" alt="" loading="lazy" />` : icon("spark")}</span><div class="detail-mini-card-copy"><strong>${escapeHtml(`${formatCount(bonus.partsCount)} ${copy("pieces", "pieces")}`)}</strong><span>${escapeHtml(setBonusTitle(bonus))}</span></div></div><div class="detail-chip-row detail-chip-row-rich">${detailTag(bonus.type === "passive" ? copy("Passive effect", "Effet passif") : copy("Stat effect", "Effet de stats"), bonus.type === "passive" ? "rate" : "context")}${bonus.passiveLevel ? detailTag(`${copy("Lv.", "Niv.")} ${formatCount(bonus.passiveLevel)}`, "context") : ""}</div><p class="skill-card-text">${escapeHtmlWithBreaks(bonus.description?.[state.language] || bonus.description?.en || "")}</p></article>`,
        )
        .join("");
      return `<section class="equipment-set-card"><div class="style-head"><div class="detail-media-thumb detail-media-thumb-large">${set.icon ? `<img src="${set.icon}" alt="" loading="lazy" />` : entry.icon ? `<img src="${entry.icon}" alt="" loading="lazy" />` : icon("shield")}</div><div class="style-copy"><p class="eyebrow">${escapeHtml(copy("Set", "Set"))}</p><h4>${escapeHtml(set.name?.[state.language] || set.name?.en || "")}</h4><div class="detail-chip-row">${detailTag(`${formatCount(set.totalParts || 0)} ${copy("pieces", "pieces")}`, "context")}${detailTag(`${formatCount((set.bonuses || []).length)} ${copy("bonuses", "bonus")}`, "")}${pieceGroups.length ? detailTag(`${formatCount(pieceGroups.length)} ${copy("slots", "emplacements")}`, "") : ""}</div></div></div>${bonusMarkup ? `<div class="detail-card-grid equipment-set-bonus-grid">${bonusMarkup}</div>` : ""}${pieceMarkup}</section>`;
    })
    .join("")}</div></article></section>`;
}

function lootSourceTypeLabel(row) {
  if (row?.dropSourceType === "first-drop") return copy("First drop", "Premier butin");
  if (row?.dropSourceType === "catch-drop") return copy("Capture drop", "Butin de capture");
  if (row?.sourceKind === "dungeon") return copy("Dungeon reward", "Butin de donjon");
  return copy("Direct drop", "Drop direct");
}

function lootCountLabel(row) {
  if (!row?.minCount && !row?.maxCount) return "";
  return `x${row.minCount || row.maxCount || 0}${row.maxCount && row.maxCount !== row.minCount ? `-${row.maxCount}` : ""}`;
}

function recyclingLevelCurveLabel(row) {
  const curve = row?.levelCurve || null;
  if (!curve) return "";
  const start = Number(curve.multiplierStart || curve.multiplierMin || 0);
  const end = Number(curve.multiplierEnd || curve.multiplierMax || 0);
  if (!(start > 0) && !(end > 0)) return "";
  return `${copy("Lv. 0-100", "Niv. 0-100")} x${formatDropPercent(start || end)}-${formatDropPercent(end || start)}`;
}

function itemDisassemblyNote(disassembly) {
  if (disassembly?.hasLevelScaling) {
    return copy(
      "Some recycling outputs scale with item level. The cards show the base yield and the level curve used by the game.",
      "Certaines sorties de recyclage evoluent avec le niveau de l'objet. Les cartes affichent le rendement de base et la courbe de niveau utilisee par le jeu.",
    );
  }
  return copy(
    "These are the outputs defined by the game's recycling table for this item grade.",
    "Voici les sorties definies par la table de recyclage du jeu pour cette rarete d'objet.",
  );
}

function recyclingCard(store, row) {
  const linked = row.itemId ? store.entryById.get(`item:${row.itemId}`) : null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const wrapper = href ? "a" : "div";
  const media = row.icon || linked?.icon || linked?.image || "";
  const title = linked ? text(linked, "name") : row.name?.[state.language] || row.name?.en || row.itemId;
  const itemMeta = linked ? entryListLabel(store, linked) : row.classification || copy("Item", "Objet");
  const chips = [
    { label: lootRateLabel(row), tone: "rate" },
    { label: lootCountLabel(row), tone: "" },
    { label: recyclingLevelCurveLabel(row), tone: "context" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  return `<article class="detail-mini-card loot-card"><${wrapper} class="detail-mini-card-link loot-card-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-mini-card-thumb loot-card-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-mini-card-copy loot-card-copy"><strong>${escapeHtml(title)}</strong>${itemMeta ? `<span>${escapeHtml(itemMeta)}</span>` : ""}</span>${chips ? `<div class="detail-chip-row detail-chip-row-rich loot-card-chips">${chips}</div>` : ""}</${wrapper}></article>`;
}

function groupLootRows(rows) {
  return buildContextGroups(rows, (row) => lootSourceTypeLabel(row));
}

function lootGroupEyebrow(group) {
  if (group.sourceKind === "dungeon") return copy("Dungeon difficulty", "Difficulte du donjon");
  if (group.sourceKind === "monster") return copy("World level", "Niveau du monde");
  if (group.sourceKind === "quest") return copy("Quest reward", "Recompense de quete");
  if (group.sourceKind === "recipe") return copy("Craft source", "Source de craft");
  return copy("Loot source", "Source de butin");
}

function lootSectionNote(entry, groups) {
  const sourceKinds = [...new Set(groups.map((group) => group.sourceKind).filter(Boolean))];
  if (sourceKinds.length === 1 && sourceKinds[0] === "dungeon") {
    return copy(
      "Loot changes with dungeon difficulty. Each block below shows the rates for one difficulty.",
      "Le butin change selon la difficulte du donjon. Chaque bloc ci-dessous affiche les taux pour une difficulte.",
    );
  }
  if (sourceKinds.length === 1 && sourceKinds[0] === "monster") {
    return copy(
      "Loot changes with world level. Each block below shows the rates for one world level.",
      "Le butin change selon le niveau du monde. Chaque bloc ci-dessous affiche les taux pour un niveau du monde.",
    );
  }
  if (entry.kind === "boss") {
    return copy(
      "This boss mixes multiple loot sources. Rates are grouped by source context below.",
      "Ce boss melange plusieurs sources de butin. Les taux sont groupes par contexte ci-dessous.",
    );
  }
  return copy(
    "Rates are grouped by the source context available in the extracted game data.",
    "Les taux sont groupes selon le contexte de source disponible dans les donnees du jeu.",
  );
}

function lootFilterLabel(groups) {
  const sourceKinds = [...new Set(groups.map((group) => group.sourceKind).filter(Boolean))];
  if (sourceKinds.length === 1 && sourceKinds[0] === "dungeon") return copy("Difficulty", "Difficulte");
  if (sourceKinds.length === 1 && sourceKinds[0] === "monster") return copy("World level", "Niveau du monde");
  if (sourceKinds.length === 1 && sourceKinds[0] === "quest") return copy("Quest", "Quete");
  if (sourceKinds.length === 1 && sourceKinds[0] === "recipe") return copy("Recipe", "Recette");
  return copy("Source", "Source");
}

function activeLootGroupKey(groups) {
  const selected = state.route.stage || "";
  if (selected && groups.some((group) => group.key === selected)) return selected;
  return groups[0]?.key || "";
}

function lootRow(store, row) {
  const linked = row.itemId ? store.entryById.get(`item:${row.itemId}`) : null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const wrapper = href ? "a" : "div";
  const media = row.icon || linked?.icon || linked?.image || "";
  const title = linked ? text(linked, "name") : row.name?.[state.language] || row.name?.en || row.itemId;
  const sourceName = normalizeSourceContextText(row.sourceName?.[state.language] || row.sourceName?.en || "", row.sourceKind);
  const sourceSubtitle = normalizeSourceContextText(row.sourceSubtitle?.[state.language] || row.sourceSubtitle?.en || "", row.sourceKind);
  const itemMeta = linked ? entryListLabel(store, linked) : row.classification || copy("Item", "Objet");
  const chips = [
    {
      label: row.dropSourceType && row.dropSourceType !== "monster-drop" && row.dropSourceType !== "" ? lootSourceTypeLabel(row) : "",
      tone: "context",
    },
    { label: lootRateLabel(row), tone: "rate" },
    { label: row.qualityMax ? `${copy("Quality", "Qualite")} ${formatCount(row.qualityMax)}` : "", tone: "" },
    { label: lootCountLabel(row), tone: "" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  const metaLine = [sourceName, sourceSubtitle].filter(Boolean).join(" · ");
  return `<article class="detail-media-row detail-source-row"><${wrapper} class="detail-media-link detail-source-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-source-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-media-copy"><strong>${escapeHtml(title)}</strong>${metaLine ? `<span class="detail-source-kicker">${escapeHtml(metaLine)}</span>` : ""}${itemMeta ? `<span class="detail-source-subtitle">${escapeHtml(itemMeta)}</span>` : ""}${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}</span></${wrapper}></article>`;
}

function lootCard(store, row) {
  const linked = row.itemId ? store.entryById.get(`item:${row.itemId}`) : null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const wrapper = href ? "a" : "div";
  const media = row.icon || linked?.icon || linked?.image || "";
  const title = linked ? text(linked, "name") : row.name?.[state.language] || row.name?.en || row.itemId;
  const sourceName = normalizeSourceContextText(row.sourceName?.[state.language] || row.sourceName?.en || "", row.sourceKind);
  const sourceSubtitle = normalizeSourceContextText(row.sourceSubtitle?.[state.language] || row.sourceSubtitle?.en || "", row.sourceKind);
  const itemMeta = linked ? entryListLabel(store, linked) : row.classification || copy("Item", "Objet");
  const chips = [
    {
      label: row.dropSourceType && row.dropSourceType !== "monster-drop" && row.dropSourceType !== "" ? lootSourceTypeLabel(row) : "",
      tone: "context",
    },
    { label: lootRateLabel(row), tone: "rate" },
    { label: row.qualityMax ? `${copy("Quality", "Qualite")} ${formatCount(row.qualityMax)}` : "", tone: "" },
    { label: lootCountLabel(row), tone: "" },
  ]
    .filter((item) => item.label)
    .map((item) => detailTag(item.label, item.tone))
    .join("");
  const metaLine = [sourceName, sourceSubtitle].filter(Boolean).join(" · ");
  return `<article class="detail-mini-card loot-card"><${wrapper} class="detail-mini-card-link loot-card-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-mini-card-thumb loot-card-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-mini-card-copy loot-card-copy"><strong>${escapeHtml(title)}</strong>${itemMeta ? `<span>${escapeHtml(itemMeta)}</span>` : ""}${metaLine ? `<span class="detail-source-kicker loot-card-source">${escapeHtml(metaLine)}</span>` : ""}</span>${chips ? `<div class="detail-chip-row detail-chip-row-rich loot-card-chips">${chips}</div>` : ""}</${wrapper}></article>`;
}

function monsterLootSection(store, entry) {
  if (!["monster", "boss"].includes(entry.kind)) return "";
  const rows = entry.fields?.lootDrops || [];
  if (!rows.length) return "";
  const groups = groupLootRows(rows);
  const selectedGroupKey = activeLootGroupKey(groups);
  const visibleGroups = groups.length > 1 ? groups.filter((group) => group.key === selectedGroupKey) : groups;
  const note = lootSectionNote(entry, groups);
  const selector =
    groups.length > 1
      ? `<div class="loot-toolbar"><div class="loot-stage-picker"><span class="loot-stage-label">${escapeHtml(lootFilterLabel(groups))}</span><div class="loot-stage-tabs">${groups
          .map(
            (group) =>
              `<a class="chip loot-stage-chip ${group.key === selectedGroupKey ? "is-active" : ""}" href="${buildRouteUrl({ ...state.route, stage: group.key })}" data-nav="true" ${group.key === selectedGroupKey ? 'aria-current="true"' : ""}>${escapeHtml(group.label)}</a>`,
          )
          .join("")}</div></div></div>`
      : "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Combat rewards", "Recompenses de combat"))}</p><h4>${escapeHtml(copy("Loot table", "Table de butin"))}</h4>${note ? `<p class="workspace-subtitle loot-section-note">${escapeHtml(note)}</p>` : ""}</div><span class="tag">${formatCount(rows.length)}</span></div>${selector}<div class="loot-group-stack">${visibleGroups
    .map((group) => {
      const groupChips = [
        detailTag(lootGroupEyebrow(group), "context"),
        group.recommendedPower ? detailTag(`${copy("BP", "PC")} ${formatCount(group.recommendedPower)}`, "power") : "",
      ]
        .filter(Boolean)
        .join("");
      return `<section class="loot-group"><div class="loot-group-head"><div><p class="eyebrow">${escapeHtml(lootGroupEyebrow(group))}</p><h5>${escapeHtml(group.label)}</h5></div><div class="detail-chip-row detail-chip-row-rich">${groupChips}</div></div><div class="detail-card-grid loot-card-grid">${group.rows.map((row) => lootCard(store, row)).join("")}</div></section>`;
    })
    .join("")}</div></article></section>`;
}

function recipeRewardFocusSection(store, entry) {
  if (entry.kind !== "recipe") return "";
  const rewardRows = entry.fields?.rewards || [];
  if (!rewardRows.length) return "";
  const rewardRow = rewardRows.find((row) => row.itemId === entry.fields?.rewardItemId) || rewardRows[0];
  const linkedEntry = rewardRow?.itemId ? store.entryById.get(`item:${rewardRow.itemId}`) : null;
  const summary = linkedEntry ? text(linkedEntry, "description") || text(linkedEntry, "summary") : text(entry, "description") || text(entry, "summary");
  const chips = [
    linkedEntry ? detailTag(entryListLabel(store, linkedEntry), "context") : "",
    linkedEntry?.rarity?.label?.[state.language] ? detailTag(linkedEntry.rarity.label[state.language], "rate") : "",
    entry.fields?.functionType ? detailTag(titleCase(entry.fields.functionType), "") : "",
    entry.fields?.showRewardLevel ? detailTag(`${copy("Reward Lv.", "Niv. recompense")} ${formatCount(entry.fields.showRewardLevel)}`, "") : "",
    entry.fields?.contentsLevel ? detailTag(`${copy("Tier", "Palier")} ${formatCount(entry.fields.contentsLevel)}`, "context") : "",
    linkedEntry?.stats?.equipmentEffectCount ? detailTag(`${formatCount(linkedEntry.stats.equipmentEffectCount)} ${copy("effects", "effets")}`, "") : "",
    linkedEntry?.stats?.setCount ? detailTag(`${formatCount(linkedEntry.stats.setCount)} ${copy("set", "set")}`, "") : "",
  ]
    .filter(Boolean)
    .join("");
  const actions = linkedEntry
    ? `${button(buildRouteUrl(routeForEntry(state.language, linkedEntry)), copy("Open result item", "Ouvrir l'objet final"), true)}${
        linkedEntry.stats?.equipmentEffectCount || linkedEntry.stats?.setCount
          ? button(buildRouteUrl({ ...routeForEntry(state.language, linkedEntry), tab: "effects" }), copy("View effects", "Voir les effets"))
          : ""
      }`
    : "";
  const rewardCards = rewardRows
    .map((row) => {
      const linked = row.itemId ? store.entryById.get(`item:${row.itemId}`) : null;
      const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
      const wrapper = href ? "a" : "div";
      const media = linked?.icon || linked?.image || "";
      const title = linked ? text(linked, "name") : row.itemId;
      const subline = linked ? entryListLabel(store, linked) : copy("Reward", "Recompense");
      return `<article class="detail-mini-card recipe-outcome-card"><${wrapper} class="detail-mini-card-link recipe-outcome-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-mini-card-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-mini-card-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(subline)}</span><span>${escapeHtml(`x${row.count}`)}</span></span></${wrapper}></article>`;
    })
    .join("");
  return `<section class="page-section"><article class="panel-inner detail-section-card recipe-focus-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Craft outcome", "Resultat du craft"))}</p><h4>${escapeHtml(copy("What this engraving gives you", "Ce que cette gravure debloque"))}</h4></div><span class="tag">${formatCount(rewardRows.length)}</span></div><div class="recipe-focus-layout"><div class="recipe-focus-copy">${linkedEntry?.icon ? `<span class="detail-media-thumb detail-media-thumb-large recipe-focus-thumb"><img src="${linkedEntry.icon}" alt="" loading="lazy" /></span>` : `<span class="detail-media-thumb detail-media-thumb-large recipe-focus-thumb">${icon("shield")}</span>`}<div class="recipe-focus-text"><strong>${escapeHtml(linkedEntry ? text(linkedEntry, "name") : text(entry, "name"))}</strong>${summary ? `<p class="skill-card-text">${escapeHtmlWithBreaks(summary)}</p>` : ""}${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}${actions ? `<div class="entry-card-actions">${actions}</div>` : ""}</div></div>${rewardCards ? `<div class="detail-card-grid recipe-outcome-grid">${rewardCards}</div>` : ""}</div></article></section>`;
}

function showcaseSection(store, items, eyebrow, title) {
  if (!items.length) return "";
  return `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h3>${escapeHtml(title)}</h3></div><span class="tag">${formatCount(items.length)}</span></div><div class="entry-grid entry-grid-tight">${items.map((item) => entryCard(store, item)).join("")}</div></section>`;
}

function itemSpecSection(entry) {
  if (entry.kind !== "item") return "";
  const sellValue =
    entry.fields?.sellCostValue && entry.fields?.sellCostType
      ? `${formatCount(entry.fields.sellCostValue)} ${entry.fields.sellCostType}`
      : entry.fields?.sellCostValue
        ? formatCount(entry.fields.sellCostValue)
        : "";
  const rows = {
    [copy("Type", "Type")]: entry.fields?.itemDetailType || "",
    [copy("Division", "Division")]: entry.fields?.itemDivision || "",
    [copy("Battle type", "Type de combat")]: entry.fields?.battleType || "",
    [copy("Element", "Element")]: entry.fields?.element || "",
    [copy("Reinforce max", "Renfort max")]: entry.fields?.reinforceMax ? `+${entry.fields.reinforceMax}` : "",
    [copy("Promotion group", "Groupe de promotion")]: entry.fields?.promotionGroup || "",
    [copy("EXP group", "Groupe EXP")]: entry.fields?.expGroup || "",
    [copy("Sell value", "Valeur de vente")]: sellValue,
    [copy("Max use", "Utilisations max")]: entry.fields?.maxUseCount || "",
    [copy("Models", "Modeles")]: entry.fields?.equipModels || [],
  };
  const markup = kvRows(rows);
  if (!markup) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Equipment data", "Donnees d'equipement"))}</p><h4>${escapeHtml(copy("Loadout profile", "Profil d'equipement"))}</h4></div></div><div class="detail-list">${markup}</div></article></section>`;
}

function itemFunctionSection(entry) {
  if (entry.kind !== "item") return "";
  const rows = entry.fields?.useFunctions || [];
  if (!rows.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Gameplay hooks", "Usage en jeu"))}</p><h4>${escapeHtml(copy("Use functions", "Fonctions d'utilisation"))}</h4></div><span class="tag">${formatCount(rows.length)}</span></div><div class="detail-chip-row">${rows
    .map((row) => [row.type, row.subType, row.value].filter(Boolean).join(" / "))
    .filter(Boolean)
    .map((label) => `<span class="tag">${escapeHtml(label)}</span>`)
    .join("")}</div></article></section>`;
}

function relatedCollections(store, entry, allRelated) {
  const consumed = new Set();
  const sections = [];
  const push = (items, eyebrow, title, limit = 8) => {
    const visible = items.slice(0, limit);
    if (!visible.length) return;
    visible.forEach((item) => consumed.add(item.id));
    sections.push(showcaseSection(store, visible, eyebrow, title));
  };

  if (primaryList(entry) === "characters") {
    push(
      allRelated.filter((item) => ["buffs", "debuffs"].includes(primaryList(item))),
      copy("Combat links", "Liens de combat"),
      copy("Applied buffs & debuffs", "Buffs & debuffs appliques"),
    );
  }

  if (entry.kind === "item") {
    push(
      allRelated.filter((item) => primaryList(item) === "characters"),
      copy("Roster links", "Liens de roster"),
      copy("Used by heroes", "Utilisee par les heros"),
    );
    push(
      allRelated.filter((item) => primaryList(item) === "costumes"),
      copy("Cosmetic links", "Liens cosmetiques"),
      copy("Linked costumes", "Costumes lies"),
    );
    push(
      allRelated.filter((item) => isRecipeCollectionEntry(item)),
      copy("Craft routes", "Pistes de craft"),
      copy("Related recipes", "Recettes liees"),
    );
  }

  if (entry.kind === "effect") {
    push(
      allRelated.filter((item) => primaryList(item) === "characters"),
      copy("Roster links", "Liens de roster"),
      copy("Known users", "Personnages lies"),
    );
  }

  return { markup: sections.join(""), consumedIds: consumed };
}

function equipmentSection(store, entry) {
  const rows = entry.fields?.defaultEquipment || [];
  if (!rows.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.category"))}</p><h4>${escapeHtml(t(state.language, "labels.defaultEquipment"))}</h4></div><span class="tag">${formatCount(rows.length)}</span></div><div class="detail-media-list">${rows
    .map((row) => {
      const linked = store.entryById.get(`item:${row.itemId}`) || null;
      const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
      const media = row.icon || linked?.icon || "";
      const type = row.type?.[state.language] || row.type?.en || "";
      const wrapper = href ? "a" : "div";
      return `<article class="detail-media-row"><${wrapper} class="detail-media-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("blade")}</span><span class="detail-media-copy"><strong>${escapeHtml(row.name?.[state.language] || row.name?.en || row.itemId)}</strong><span>${escapeHtml(type)}</span></span></${wrapper}></article>`;
    })
    .join("")}</div></article></section>`;
}

function profileSection(entry) {
  const rows = entry.fields?.profile || [];
  if (!rows.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.details"))}</p><h4>${escapeHtml(t(state.language, "labels.profile"))}</h4></div></div><div class="detail-list">${rows
    .map(
      (row) =>
        `<div class="detail-row"><span>${escapeHtml(row.label?.[state.language] || row.label?.en || row.id)}</span><span>${escapeHtml(row.value?.[state.language] || row.value?.en || "")}</span></div>`,
    )
    .join("")}</div></article></section>`;
}

function baseStatsSection(entry) {
  const rows = entry.fields?.baseStats || [];
  if (!rows.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Combat profile", "Profil de combat"))}</p><h4>${escapeHtml(copy("Base stats", "Statistiques de base"))}</h4></div></div><div class="detail-list">${rows
    .map(
      (row) =>
        `<div class="detail-row"><span>${escapeHtml(row.label?.[state.language] || row.label?.en || row.id)}</span><span>${escapeHtml(row.value?.[state.language] || row.value?.en || "")}</span></div>`,
    )
    .join("")}</div></article></section>`;
}

function potentialItemCard(store, item) {
  if (!item) return "";
  const linked = item.itemId ? store.entryById.get(`item:${item.itemId}`) : null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const wrapper = href ? "a" : "div";
  const title = item.name?.[state.language] || item.name?.en || item.itemId;
  const description = item.description?.[state.language] || item.description?.en || "";
  return `<article class="progression-card"><${wrapper} class="progression-card-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb detail-media-thumb-large">${item.icon ? `<img src="${item.icon}" alt="" loading="lazy" />` : icon("star")}</span><div class="progression-card-copy"><p class="eyebrow">${escapeHtml(copy("Potential material", "Materiau de potentiel"))}</p><h4>${escapeHtml(title)}</h4>${description ? `<p class="skill-card-text">${escapeHtmlWithBreaks(description)}</p>` : ""}</div></${wrapper}></article>`;
}

function commonMasteryNodeCard(node) {
  const title = node.title?.[state.language] || node.title?.en || "";
  return `<article class="mastery-node mastery-node-shared"><div class="mastery-node-head"><div class="detail-media-thumb">${node.icon ? `<img src="${node.icon}" alt="" loading="lazy" />` : icon("star")}</div><div class="style-copy"><p class="eyebrow">${escapeHtml(copy("Shared mastery", "Maitrise partagee"))}</p><h4>${escapeHtml(title)}</h4><div class="detail-chip-row"><span class="tag">Lv. ${escapeHtml(String(node.index || 0))}</span>${node.expValue ? `<span class="tag">${escapeHtml(`${formatCount(node.expValue)} XP`)}</span>` : ""}${node.currencyCost ? `<span class="tag">${escapeHtml(`${formatCount(node.currencyCost)} G`)}</span>` : ""}</div></div></div>${node.abilities?.length ? `<div class="mastery-bonus-list">${node.abilities.map((bonus) => masteryBonusRow(bonus)).join("")}</div>` : ""}</article>`;
}

function commonMasterySection(store, entry) {
  const track = entry.fields?.commonMastery || {};
  const groups = track.groups || [];
  if (!groups.length) return "";
  const potentialMarkup = potentialItemCard(store, entry.fields?.potentialItem);
  const activationMaterials = entry.fields?.masteryActivationMaterials || [];
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Hero progression", "Progression du heros"))}</p><h4>${escapeHtml(copy("Gravure & shared mastery", "Gravure & maitrise partagee"))}</h4></div><div class="detail-chip-row"><span class="tag">${formatCount(track.totalNodes || 0)} ${escapeHtml(copy("nodes", "noeuds"))}</span><span class="tag">${formatCount(track.totalCurrency || 0)} G</span></div></div>${potentialMarkup}${activationMaterials.length ? `<div class="detail-media-list">${activationMaterials.map((row) => masteryMaterialRow(store, row)).join("")}</div>` : ""}<div class="shared-mastery-grid">${groups
    .map(
      (group) =>
        `<article class="mastery-group mastery-group-shared"><div class="mastery-group-head"><div class="style-copy"><p class="eyebrow">${escapeHtml(copy("Stage", "Palier"))}</p><h4>${escapeHtml(group.label?.[state.language] || group.label?.en || "")}</h4><div class="detail-chip-row">${group.expValue ? `<span class="tag">${escapeHtml(`${formatCount(group.expValue)} XP`)}</span>` : ""}${group.currencyCost ? `<span class="tag">${escapeHtml(`${formatCount(group.currencyCost)} G`)}</span>` : ""}</div></div></div><div class="mastery-node-grid">${(group.nodes || []).map((node) => commonMasteryNodeCard(node)).join("")}</div></article>`,
    )
    .join("")}</div></article></section>`;
}

function masteryMaterialRow(store, row) {
  const linked = store.entryById.get(`item:${row.itemId}`) || null;
  const href = linked ? buildRouteUrl(routeForEntry(state.language, linked)) : "";
  const wrapper = href ? "a" : "div";
  const media = row.icon || linked?.icon || linked?.image || "";
  const label = row.name?.[state.language] || row.name?.en || row.itemId;
  return `<article class="detail-media-row detail-media-row-compact"><${wrapper} class="detail-media-link" ${href ? `href="${href}" data-nav="true"` : ""}><span class="detail-media-thumb">${media ? `<img src="${media}" alt="" loading="lazy" />` : icon("bag")}</span><span class="detail-media-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(t(state.language, "labels.materialsNeeded"))}</span></span><span class="tag detail-media-qty">x${escapeHtml(row.count)}</span></${wrapper}></article>`;
}

function masteryBonusRow(bonus) {
  const label = bonus.label?.[state.language] || bonus.label?.en || bonus.id;
  const value = bonus.value?.[state.language] || bonus.value?.en || "";
  return `<div class="mastery-bonus"><span class="mastery-bonus-icon">${bonus.icon ? `<img src="${bonus.icon}" alt="" loading="lazy" />` : icon("star")}</span><span class="mastery-bonus-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></span></div>`;
}

function masteryMilestoneCard(milestone) {
  return `<article class="variant-card mastery-milestone"><div class="variant-card-head"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.milestones"))}</p><strong>${escapeHtml(`#${milestone.index}`)}</strong></div><span class="tag">${escapeHtml(`${formatCount(milestone.expValue)} XP`)}</span></div><div class="mastery-bonus-list">${(milestone.abilities || []).map((bonus) => masteryBonusRow(bonus)).join("")}</div></article>`;
}

function masteryNodeCard(store, node) {
  const title = node.title?.[state.language] || node.title?.en || "";
  const label = node.label?.[state.language] || node.label?.en || "";
  const condition = node.applyCondition?.[state.language] || node.applyCondition?.en || "";
  const description = node.description?.[state.language] || node.description?.en || "";
  return `<article class="mastery-node"><div class="mastery-node-head"><div class="detail-media-thumb">${node.icon ? `<img src="${node.icon}" alt="" loading="lazy" />` : icon("star")}</div><div class="style-copy"><p class="eyebrow">${escapeHtml(label)}</p><h4>${escapeHtml(title)}</h4>${condition ? `<div class="detail-chip-row"><span class="tag">${escapeHtml(condition)}</span>${node.grade ? `<span class="tag">${escapeHtml(`G${node.grade}`)}</span>` : ""}</div>` : ""}</div></div>${description ? `<p class="skill-card-text">${escapeHtmlWithBreaks(description)}</p>` : ""}${node.abilities?.length ? `<div class="mastery-bonus-list">${node.abilities.map((bonus) => masteryBonusRow(bonus)).join("")}</div>` : ""}${node.materials?.length ? `<div class="detail-media-list mastery-material-list">${node.materials.map((row) => masteryMaterialRow(store, row)).join("")}</div>` : ""}</article>`;
}

function masteryTrackSection(store, track) {
  const groups = track?.groups || [];
  if (!groups.length) return "";
  return `<div class="style-mastery"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.mastery"))}</p><h4>${escapeHtml(track.label?.[state.language] || track.label?.en || t(state.language, "labels.mastery"))}</h4></div><span class="tag">${formatCount(groups.length)} ${escapeHtml(t(state.language, "labels.masteryTiers"))}</span></div><div class="mastery-group-stack">${groups
    .map((group) => {
      const milestones = group.milestones || [];
      return `<article class="mastery-group"><div class="mastery-group-head">${group.cover ? `<div class="mastery-group-cover"><img src="${group.cover}" alt="" loading="lazy" /></div>` : `<div class="mastery-group-cover mastery-group-cover-fallback">${icon("shield")}</div>`}<div class="style-copy"><p class="eyebrow">${escapeHtml(t(state.language, "labels.masteryTiers"))}</p><h4>${escapeHtml(group.label?.[state.language] || group.label?.en || "")}</h4><div class="detail-chip-row">${group.expValue ? `<span class="tag">${escapeHtml(`${formatCount(group.expValue)} XP`)}</span>` : ""}${group.currencyCost ? `<span class="tag">${escapeHtml(`${formatCount(group.currencyCost)} G`)}</span>` : ""}</div></div></div><div class="mastery-node-grid">${(group.nodes || []).map((node) => masteryNodeCard(store, node)).join("")}</div>${milestones.length ? `<div class="mastery-milestone-grid">${milestones.map((milestone) => masteryMilestoneCard(milestone)).join("")}</div>` : ""}</article>`;
    })
    .join("")}</div></div>`;
}

function entryHeroStats(entry) {
  const cards = [];
  if (entry.stats?.weaponStyleCount) {
    cards.push(stat(t(state.language, "labels.weaponStyle"), formatCount(entry.stats.weaponStyleCount), t(state.language, "labels.weaponStyle")));
  }
  if (entry.stats?.skillCount) {
    cards.push(stat(t(state.language, "labels.skillCount"), formatCount(entry.stats.skillCount), t(state.language, "labels.effects")));
  }
  if (entry.stats?.dropCount) {
    cards.push(stat(copy("Drops", "Butins"), formatCount(entry.stats.dropCount), copy("Tracked direct loot rows for this enemy.", "Lignes de butin direct suivies pour cet ennemi.")));
  }
  if (entry.stats?.masteryNodeCount) {
    cards.push(stat(copy("Mastery nodes", "Noeuds de maitrise"), formatCount(entry.stats.masteryNodeCount), copy("Shared progression extracted from hero tables.", "Progression partagee extraite des tables heros.")));
  }
  if (entry.stats?.potentialLevelCount) {
    cards.push(stat(copy("Potential levels", "Niveaux de potentiel"), formatCount(entry.stats.potentialLevelCount), copy("Weapon-style upgrades tracked for this hero.", "Ameliorations par style d'arme suivies pour ce heros.")));
  }
  if (entry.stats?.costumeCount) {
    cards.push(stat(t(state.language, "labels.costumeCount"), formatCount(entry.stats.costumeCount), t(state.language, "labels.costumes")));
  }
  if (entry.stats?.ingredientCount) {
    cards.push(stat(t(state.language, "labels.ingredientCount"), formatCount(entry.stats.ingredientCount), t(state.language, "labels.ingredients")));
  }
  if (entry.stats?.rewardCount) {
    cards.push(stat(t(state.language, "labels.rewardCount"), formatCount(entry.stats.rewardCount), t(state.language, "labels.rewards")));
  }
  if (entry.stats?.variantCount) {
    cards.push(stat(t(state.language, "labels.variantCount"), formatCount(entry.stats.variantCount), t(state.language, "labels.effects")));
  }
  if (entry.stats?.equipmentEffectCount && cards.length < 3) {
    cards.push(
      stat(
        copy("Effects", "Effets"),
        formatCount(entry.stats.equipmentEffectCount),
        copy("Tracked fixed stats, option pools, and passive effects.", "Stats fixes, pools d'effets et passifs suivis."),
      ),
    );
  }
  if (entry.stats?.recycledFromCount && cards.length < 3) {
    cards.push(
      stat(
        copy("Recycle sources", "Sources de recyclage"),
        formatCount(entry.stats.recycledFromCount),
        copy("Gear families that can be dismantled into this item.", "Familles d'equipement qui peuvent produire cet objet."),
      ),
    );
  }
  if (entry.stats?.setCount && cards.length < 3) {
    cards.push(
      stat(
        copy("Set bonuses", "Bonus de set"),
        formatCount(entry.stats.setCount),
        copy("Tracked equipment set data for this item.", "Donnees de set d'equipement suivies pour cet objet."),
      ),
    );
  }
  if (entry.stats?.disassemblyCount && cards.length < 3) {
    cards.push(
      stat(
        copy("Recycle", "Recyclage"),
        formatCount(entry.stats.disassemblyCount),
        copy("Tracked outputs when this item is recycled.", "Sorties suivies quand cet objet est recycle."),
      ),
    );
  }
  if (entry.stats?.acquisitionCount && cards.length < 3) {
    cards.push(
      stat(
        copy("Acquisition", "Obtention"),
        formatCount(entry.stats.acquisitionCount),
        copy("Tracked non-map ways to get this entry.", "Sources d'obtention hors carte suivies pour cette fiche."),
      ),
    );
  }
  if (entry.stats?.pointCount && cards.length < 3) {
    cards.push(stat(t(state.language, "labels.pointCount"), formatCount(entry.stats.pointCount), t(state.language, "labels.mapLinked")));
  }
  return cards.length ? `<div class="grid-3 compact-grid detail-stat-strip">${cards.slice(0, 3).join("")}</div>` : "";
}

function skillEffectRow(effect) {
  if (effect.kind === "attack") {
    const scaling = (effect.scaling || [])
      .map((row) => `<span class="tag">${escapeHtml(`${row.label?.[state.language] || row.label?.en || row.id} ${row.value?.[state.language] || row.value?.en || ""}`)}</span>`)
      .join("");
    const chips = [
      effect.damageType ? `<span class="tag">${escapeHtml(effect.damageType)}</span>` : "",
      effect.element ? `<span class="tag">${escapeHtml(effect.element)}</span>` : "",
      effect.target ? `<span class="tag">${escapeHtml(effect.target)}</span>` : "",
      effect.area ? `<span class="tag">${escapeHtml(effect.area)}</span>` : "",
      effect.chargeElement ? `<span class="tag">${escapeHtml(`+${effect.chargeElement}`)} ${escapeHtml(copy("element", "element"))}</span>` : "",
    ]
      .filter(Boolean)
      .join("");
    return `<div class="skill-effect-row"><div class="skill-effect-head"><p class="eyebrow">${escapeHtml(copy("Attack phase", "Phase offensive"))}</p><strong>${escapeHtml(`${copy("Phase", "Phase")} ${effect.phase || 0}`)}</strong></div>${scaling ? `<div class="detail-chip-row">${scaling}</div>` : ""}${chips ? `<div class="detail-chip-row">${chips}</div>` : ""}</div>`;
  }
  if (effect.kind === "buff") {
    const chips = [
      effect.side ? `<span class="tag">${escapeHtml(effect.side === "debuffs" ? copy("Debuff", "Debuff") : copy("Buff", "Buff"))}</span>` : "",
      effect.actorState ? `<span class="tag">${escapeHtml(effect.actorState)}</span>` : "",
      effect.durationSeconds ? `<span class="tag">${escapeHtml(`${effect.durationSeconds}s`)}</span>` : "",
      effect.count ? `<span class="tag">${escapeHtml(`x${effect.count}`)}</span>` : "",
    ]
      .filter(Boolean)
      .join("");
    return `<div class="skill-effect-row"><div class="skill-effect-head"><p class="eyebrow">${escapeHtml(copy("Applied effect", "Effet applique"))}</p><strong>${escapeHtml(effect.name?.[state.language] || effect.name?.en || effect.buffId)}</strong></div>${effect.description?.[state.language] || effect.description?.en ? `<p class="skill-card-text">${escapeHtmlWithBreaks(effect.description?.[state.language] || effect.description?.en || "")}</p>` : ""}${chips ? `<div class="detail-chip-row">${chips}</div>` : ""}</div>`;
  }
  return "";
}

function potentialLevelCard(level) {
  const changedSlots = (level.changedSlots || []).map((slot) => `<span class="tag">${escapeHtml(slot?.[state.language] || slot?.en || "")}</span>`).join("");
  return `<article class="variant-card potential-card"><div class="variant-card-head"><div><p class="eyebrow">${escapeHtml(copy("Potential", "Potentiel"))}</p><strong>${escapeHtml(`Lv. ${level.level}`)}</strong></div></div><p class="skill-card-text">${escapeHtmlWithBreaks(level.description?.[state.language] || level.description?.en || "")}</p>${changedSlots ? `<div class="detail-chip-row">${changedSlots}</div>` : ""}${level.bonuses?.length ? `<div class="mastery-bonus-list">${level.bonuses.map((bonus) => masteryBonusRow(bonus)).join("")}</div>` : ""}</article>`;
}

function potentialTrackSection(style) {
  const levels = style.potentialLevels || [];
  if (!levels.length) return "";
  return `<div class="style-potential"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Potential upgrades", "Ameliorations de potentiel"))}</p><h4>${escapeHtml(copy("Weapon growth track", "Paliers du style d'arme"))}</h4></div><span class="tag">${formatCount(levels.length)} ${escapeHtml(copy("levels", "niveaux"))}</span></div><div class="potential-grid">${levels.map((level) => potentialLevelCard(level)).join("")}</div></div>`;
}

function skillCard(skill) {
  const chips = [
    skill.category ? `<span class="tag">${escapeHtml(skill.category)}</span>` : "",
    skill.function ? `<span class="tag">${escapeHtml(skill.function)}</span>` : "",
    skill.useType ? `<span class="tag">${escapeHtml(skill.useType)}</span>` : "",
    skill.damageType ? `<span class="tag">${escapeHtml(skill.damageType)}</span>` : "",
    skill.target ? `<span class="tag">${escapeHtml(skill.target)}</span>` : "",
    skill.range ? `<span class="tag">${escapeHtml(`${skill.range} ${t(state.language, "labels.rangeUnit")}`)}</span>` : "",
    skill.coolTime ? `<span class="tag">${escapeHtml(`${copy("CD", "CD")} ${skill.coolTime}s`)}</span>` : "",
    skill.chargeTime ? `<span class="tag">${escapeHtml(`${copy("Charge", "Charge")} ${skill.chargeTime}s`)}</span>` : "",
    skill.staminaCost ? `<span class="tag">${escapeHtml(`${copy("Stamina", "Endurance")} ${skill.staminaCost}`)}</span>` : "",
    skill.hpCost ? `<span class="tag">${escapeHtml(`${copy("HP", "PV")} ${skill.hpCost}`)}</span>` : "",
    skill.keyInputType ? `<span class="tag">${escapeHtml(skill.keyInputType)}</span>` : "",
  ]
    .filter(Boolean)
    .join("");
  const effectMarkup = (skill.effects || []).map((effect) => skillEffectRow(effect)).filter(Boolean).join("");
  return `<article class="skill-card"><div class="skill-card-head"><div class="skill-card-title"><span class="detail-media-thumb skill-card-icon">${skill.icon ? `<img src="${skill.icon}" alt="" loading="lazy" />` : icon("spark")}</span><div><p class="eyebrow">${escapeHtml(skill.slot?.[state.language] || skill.slot?.en || "")}</p><strong>${escapeHtml(skill.name?.[state.language] || skill.name?.en || skill.id)}</strong></div></div></div><p class="skill-card-text">${escapeHtmlWithBreaks(skill.description?.[state.language] || skill.description?.en || t(state.language, "labels.noDescription"))}</p>${skill.subDescription?.[state.language] || skill.subDescription?.en ? `<p class="skill-card-text skill-card-subtext">${escapeHtmlWithBreaks(skill.subDescription?.[state.language] || skill.subDescription?.en || "")}</p>` : ""}${chips ? `<div class="detail-chip-row">${chips}</div>` : ""}${effectMarkup ? `<div class="skill-effect-list">${effectMarkup}</div>` : ""}</article>`;
}

function activeStylePayload(entry) {
  const styles = entry.fields?.weaponStyles || [];
  const selected = state.route.style || "";
  return styles.find((style) => style.id === selected) || styles[0] || null;
}

function detailTabMarkup(entry, tabs, activeTab) {
  if (tabs.length < 2) return "";
  return `<div class="detail-tab-bar">${tabs
    .map(
      (tab) =>
        `<a class="chip detail-tab-link ${tab.id === activeTab ? "is-active" : ""}" href="${buildRouteUrl({ ...state.route, tab: tab.id })}" data-nav="true" ${tab.id === activeTab ? 'aria-current="true"' : ""}>${escapeHtml(tab.label)}</a>`,
    )
    .join("")}</div>`;
}

function styleSelectorMarkup(entry, activeStyleId) {
  const styles = entry.fields?.weaponStyles || [];
  if (styles.length < 2) return "";
  return `<div class="loot-toolbar detail-style-toolbar"><div class="loot-stage-picker"><span class="loot-stage-label">${escapeHtml(copy("Weapon style", "Style d'arme"))}</span><div class="loot-stage-tabs">${styles
    .map(
      (style) =>
        `<a class="chip loot-stage-chip ${style.id === activeStyleId ? "is-active" : ""}" href="${buildRouteUrl({ ...state.route, tab: "styles", style: style.id })}" data-nav="true" ${style.id === activeStyleId ? 'aria-current="true"' : ""}>${escapeHtml(style.label?.[state.language] || style.label?.en || style.id)}</a>`,
    )
    .join("")}</div></div></div>`;
}

function styleLinkedWeaponPanel(store, linkedEntry) {
  if (!linkedEntry) return "";
  const chips = [
    linkedEntry.rarity?.label?.[state.language] ? detailTag(linkedEntry.rarity.label[state.language], "rate") : "",
    linkedEntry.class ? detailTag(linkedEntry.class, "context") : "",
    linkedEntry.fields?.equipmentSets?.length ? detailTag(`${formatCount(linkedEntry.fields.equipmentSets.length)} ${copy("set", "set")}`, "") : "",
  ]
    .filter(Boolean)
    .join("");
  return `<section class="page-section"><article class="panel-inner detail-section-card compact-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Linked weapon", "Arme liee"))}</p><h4>${escapeHtml(text(linkedEntry, "name"))}</h4></div><div class="entry-card-actions">${button(buildRouteUrl(routeForEntry(state.language, linkedEntry)), t(state.language, "actions.openWeapon"))}</div></div><div class="style-linked-weapon">${linkedEntry.icon ? `<span class="detail-media-thumb detail-media-thumb-large"><img src="${linkedEntry.icon}" alt="" loading="lazy" /></span>` : `<span class="detail-media-thumb detail-media-thumb-large">${icon("blade")}</span>`}<div class="style-linked-weapon-copy"><p class="skill-card-text">${escapeHtml(text(linkedEntry, "summary") || text(linkedEntry, "description"))}</p>${chips ? `<div class="detail-chip-row detail-chip-row-rich">${chips}</div>` : ""}</div></div></article></section>${itemEquipmentEffectsSection(linkedEntry)}${equipmentSetBonusSection(store, linkedEntry)}`;
}

function weaponStyleSection(store, entry) {
  const styles = entry.fields?.weaponStyles || [];
  if (!styles.length) return "";
  const activeStyle = activeStylePayload(entry);
  if (!activeStyle) return "";
  const linked = activeStyle.itemId ? store.entryById.get(`item:${activeStyle.itemId}`) : null;
  const chips = [
    activeStyle.element?.[state.language] ? `<span class="tag">${escapeHtml(activeStyle.element[state.language])}</span>` : "",
    activeStyle.role?.[state.language] ? `<span class="tag">${escapeHtml(activeStyle.role[state.language])}</span>` : "",
  ]
    .filter(Boolean)
    .join("");
  const masteryMarkup = activeStyle.mastery?.groups?.length ? masteryTrackSection(store, activeStyle.mastery) : "";
  const potentialMarkup = activeStyle.potentialLevels?.length ? potentialTrackSection(activeStyle) : "";
  return `<section class="page-section">${styleSelectorMarkup(entry, activeStyle.id)}<article class="panel-inner detail-section-card style-card compact-section-card"><div class="style-head"><div class="detail-media-thumb detail-media-thumb-large">${activeStyle.icon ? `<img src="${activeStyle.icon}" alt="" loading="lazy" />` : icon("blade")}</div><div class="style-copy"><p class="eyebrow">${escapeHtml(t(state.language, "labels.weaponStyle"))}</p><h4>${escapeHtml(activeStyle.label?.[state.language] || activeStyle.label?.en || "")}</h4>${chips ? `<div class="detail-chip-row">${chips}</div>` : ""}</div></div><div class="skill-grid">${(activeStyle.skills || []).map((skill) => skillCard(skill)).join("")}</div>${potentialMarkup}${masteryMarkup}</article>${styleLinkedWeaponPanel(store, linked)}</section>`;
}

function effectVariantSection(store, entry) {
  const variants = entry.fields?.variants || [];
  if (!variants.length) return "";
  return `<section class="page-section"><article class="panel-inner detail-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.details"))}</p><h4>${escapeHtml(t(state.language, "labels.variants"))}</h4></div><span class="tag">${formatCount(variants.length)}</span></div><div class="variant-grid">${variants
    .map((variant) => {
      const chips = [
        variant.applyType ? `<span class="tag">${escapeHtml(variant.applyType)}</span>` : "",
        variant.detailType ? `<span class="tag">${escapeHtml(variant.detailType)}</span>` : "",
        variant.actorState ? `<span class="tag">${escapeHtml(variant.actorState)}</span>` : "",
        variant.ableType ? `<span class="tag">${escapeHtml(variant.ableType)}</span>` : "",
        ...(variant.blocks || []).map((label) => `<span class="tag">${escapeHtml(label?.[state.language] || label?.en || "")}</span>`),
        ...(variant.stackFlags || []).map((value) => `<span class="tag">${escapeHtml(value)}</span>`),
        variant.deleteType ? `<span class="tag">${escapeHtml(variant.deleteType)}</span>` : "",
      ]
        .filter(Boolean)
        .join("");
      const statChanges = (variant.statChanges || []).map((bonus) => masteryBonusRow(bonus)).join("");
      const damageHooks = (variant.damageHooks || [])
        .map((row) => `<span class="tag">${escapeHtml([row.trigger, row.rule, row.value].filter(Boolean).join(" "))}</span>`)
        .join("");
      const tickEffects = (variant.tickEffects || [])
        .map((row) => `<span class="tag">${escapeHtml(`${row.behaviorId || copy("Tick", "Tick")} ${row.intervalSeconds || 0}s`)}</span>`)
        .join("");
      const material = variant.material ? masteryMaterialRow(store, variant.material) : "";
      return `<article class="variant-card"><div class="variant-card-head"><div><p class="eyebrow">${escapeHtml(variant.type || "")}</p><strong>${escapeHtml(variant.id)}</strong></div></div><p class="skill-card-text">${escapeHtmlWithBreaks(variant.description?.[state.language] || variant.description?.en || t(state.language, "labels.noDescription"))}</p>${chips ? `<div class="detail-chip-row">${chips}</div>` : ""}${statChanges ? `<div class="mastery-bonus-list">${statChanges}</div>` : ""}${damageHooks ? `<div class="detail-chip-row">${damageHooks}</div>` : ""}${tickEffects ? `<div class="detail-chip-row">${tickEffects}</div>` : ""}${material ? `<div class="detail-media-list">${material}</div>` : ""}</article>`;
    })
    .join("")}</div></article></section>`;
}

function entryContextSections(store, entry) {
  return [
    recipeRewardFocusSection(store, entry),
    relationSection(store, entry, "materials", t(state.language, "labels.ingredients")),
    relationSection(store, entry, "rewards", t(state.language, "labels.rewards")),
    itemAcquisitionSection(store, entry),
    itemRecycledFromSection(store, entry),
    itemDisassemblySection(store, entry),
    monsterLootSection(store, entry),
    itemSpecSection(entry),
    itemFunctionSection(entry),
    itemEquipmentEffectsSection(entry),
    equipmentSection(store, entry),
    commonMasterySection(store, entry),
    baseStatsSection(entry),
    profileSection(entry),
    weaponStyleSection(store, entry),
    effectVariantSection(store, entry),
  ]
    .filter(Boolean)
    .join("");
}

function bossCategorySummary(entry) {
  const categories = entry.fields?.bossCategories || [];
  const labels = categories
    .map((value) => {
      if (value === "field") return copy("World boss", "Boss de terrain");
      if (value === "dungeon") return copy("Dungeon boss", "Boss de donjon");
      if (value === "challenge") return copy("Boss challenge", "Defi boss");
      return "";
    })
    .filter(Boolean);
  return labels.join(", ");
}

function entryLootScalingLabel(entry) {
  const rows = entry.fields?.lootDrops || [];
  const sourceKinds = [...new Set(rows.map((row) => row?.sourceKind).filter(Boolean))];
  if (sourceKinds.length === 1 && sourceKinds[0] === "dungeon") {
    return copy("Varies by dungeon difficulty", "Varie selon la difficulte du donjon");
  }
  if (sourceKinds.length === 1 && sourceKinds[0] === "monster") {
    return copy("Varies by world level", "Varie selon le niveau du monde");
  }
  if (sourceKinds.length > 1) {
    return copy("Varies by source context", "Varie selon le contexte de source");
  }
  return "";
}

function regionSection(store, title, items, route) {
  if (!items.length) return "";
  return `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.region"))}</p><h3>${escapeHtml(title)}</h3></div><div class="entry-card-actions">${button(buildRouteUrl(route), t(state.language, "actions.seeAll"))}</div></div><div class="entry-grid">${items.slice(0, 6).map((entry) => entryCard(store, entry)).join("")}</div></section>`;
}

function systemsHubListSection(store, eyebrow, title, summary, listIds) {
  const visible = listIds.filter((id) => (listMeta(store, id)?.count || 0) > 0);
  if (!visible.length) return "";
  const total = visible.reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
  return `<section class="page-section"><article class="panel-inner systems-section-card"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h3>${escapeHtml(title)}</h3>${summary ? `<p class="workspace-subtitle systems-section-text">${escapeHtml(summary)}</p>` : ""}</div><span class="tag">${formatCount(total)} ${escapeHtml(t(state.language, "labels.entries"))}</span></div><div class="coverage-grid systems-coverage-grid">${visible.map((id) => listCard(store, id)).join("")}</div></article></section>`;
}

function systemsSpotlightEntries(store, listIds, limit = 8, perList = 2) {
  const seen = new Set();
  const entries = [];
  listIds.forEach((id) => {
    listEntries(store, id)
      .slice(0, perList)
      .forEach((entry) => {
        if (entry && !seen.has(entry.id) && entries.length < limit) {
          seen.add(entry.id);
          entries.push(entry);
        }
      });
  });
  return entries;
}

function renderSystemsHub(store, route, meta, listIds, totals) {
  const travelLists = ["waypoints", "portals", "puzzles", "fishing-spots"];
  const progressionLists = ["quests", "main-quests", "side-quests", "hidden-quests", "stella-quests", "unlocks"];
  const challengeLists = ["boss-challenges", "dungeon-bosses", "field-bosses"];
  const spotlight = systemsSpotlightEntries(store, ["waypoints", "portals", "unlocks", "quests", "puzzles"], 10, 2);
  const travelCount = travelLists.reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
  const progressionCount = progressionLists.reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
  const challengeCount = challengeLists.reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
  const actionButtons = [
    (listMeta(store, "quests")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "quests")), listMeta(store, "quests")?.title?.[state.language] || titleCase("quests"), true) : "",
    (listMeta(store, "waypoints")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "waypoints")), listMeta(store, "waypoints")?.title?.[state.language] || titleCase("waypoints")) : "",
    (listMeta(store, "unlocks")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "unlocks")), listMeta(store, "unlocks")?.title?.[state.language] || titleCase("unlocks")) : "",
  ]
    .filter(Boolean)
    .join("");
  return `<section class="page-section"><div class="detail-hero-card detail-hero-card-hub detail-hero-card-systems"><div class="detail-hero-head"><div><p class="eyebrow">${escapeHtml(copy("World systems", "Systemes du monde"))}</p><h3>${escapeHtml(meta.title?.[state.language] || titleCase(route.kind))}</h3><p class="hero-text">${escapeHtml(copy("Fast travel, portals, puzzles, quest flow and unlock gates gathered in one cleaner command view.", "Teleporteurs, portails, enigmes, progression de quetes et conditions de deblocage rassembles dans une vue plus claire."))}</p></div></div><div class="entry-card-actions">${actionButtons}</div><div class="grid-3 compact-grid">${stat(copy("Traversal", "Deplacement"), formatCount(travelCount), copy("Waypoints, portals, puzzle routes and world traversal hooks.", "Teleporteurs, portails, parcours d'enigmes et points de deplacement."))}${stat(copy("Progression", "Progression"), formatCount(progressionCount), copy("Quest lines, hidden tasks and unlock conditions linked to the world.", "Quetes, variantes cachees et conditions de deblocage liees au monde."))}${stat(copy("Challenge loops", "Boucles de defi"), formatCount(challengeCount), copy("Boss challenge, dungeon boss and field boss routes connected to these systems.", "Defi boss, boss de donjon et boss de terrain relies a ces systemes."))}</div></div></section><section class="page-section"><div class="grid-3 compact-grid">${stat(t(state.language, "labels.sections"), formatCount(listIds.length), t(state.language, "home.coverageTitle"))}${stat(t(state.language, "labels.entries"), formatCount(totals.count), t(state.language, "copy.currentCoverage"))}${stat(t(state.language, "labels.mapLinked"), formatCount(totals.mapLinkedCount), t(state.language, "labels.mapCoverage"))}</div></section>${systemsHubListSection(
    store,
    copy("Traversal", "Navigation"),
    copy("Travel and traversal", "Deplacement et traversal"),
    copy("Open the systems that move you through the world first: teleports, portal chains and puzzle routes.", "Accede d'abord aux systemes qui te font circuler dans le monde : teleporteurs, chaines de portails et routes d'enigmes."),
    travelLists,
  )}${systemsHubListSection(
    store,
    copy("Progression", "Progression"),
    copy("Quests and unlock gates", "Quetes et deblocages"),
    copy("Follow the main quest flow, side chains, hidden quests and the exact unlock conditions tied to them.", "Suis la progression principale, les quetes annexes, les quetes cachees et les conditions de deblocage qui vont avec."),
    progressionLists,
  )}${systemsHubListSection(
    store,
    copy("Challenge", "Defi"),
    copy("Boss loops tied to progression", "Boucles boss liees a la progression"),
    copy("These challenge tracks are not separate from progression: they are where the codex sends you when a system opens into a boss route.", "Ces pistes de defi ne sont pas separees de la progression : le codex y renvoie quand un systeme ouvre sur une route de boss."),
    challengeLists,
  )}${spotlight.length ? `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(copy("Useful shortcuts", "Raccourcis utiles"))}</p><h3>${escapeHtml(copy("Open a concrete route", "Ouvrir une route concrete"))}</h3><p class="workspace-subtitle systems-section-text">${escapeHtml(copy("A few ready-to-open entries from the system lists above.", "Quelques entrees directement exploitables tirees des listes systeme ci-dessus."))}</p></div><span class="tag">${formatCount(spotlight.length)}</span></div><div class="entry-grid">${spotlight.map((entry) => entryCard(store, entry)).join("")}</div></section>` : ""}`;
}

export function heroMarkup(store, route) {
  if (route.view === "home") {
    const actionButtons = homeActionLists(store)
      .map((id, index) => button(buildRouteUrl(routeForList(state.language, id)), listMeta(store, id)?.title?.[state.language] || titleCase(id), index === 0))
      .join("");
    return `<div class="hero-copy"><p class="eyebrow">${escapeHtml(t(state.language, "copy.gameTitle"))}</p><h1 id="heroTitle">${escapeHtml(t(state.language, "home.title"))}</h1><p class="hero-text">${escapeHtml(t(state.language, "home.body"))}</p><div class="hero-actions">${actionButtons}${button(buildRouteUrl(routeForSearch(state.language)), t(state.language, "nav.search"))}${button(getSevenMapBaseUrl(), t(state.language, "actions.openSevenMap"), false, true)}</div></div><div class="hero-grid">${stat(t(state.language, "labels.entries"), formatCount(store.manifest.counts.entries), t(state.language, "copy.heroRecordsBody"))}${stat(t(state.language, "labels.sections"), formatCount(selectableLists(store).length), t(state.language, "copy.heroSectionsBody"))}${stat(t(state.language, "labels.languages"), "EN / FR", t(state.language, "copy.heroLanguagesBody"))}</div>`;
  }
  if (route.view === "list" && route.kind) {
    const meta = listMeta(store, route.kind);
    const hubId = meta?.hub || "";
    const hubTitle = hubMeta(store, hubId)?.title?.[state.language] || titleCase(hubId);
    const base = listEntries(store, route.kind);
    const opts = optionsForEntries(base);
    const mapSource = base.find((entry) => entry.mapRef?.type);
    const scopeCount = opts.regions.length || opts.classifications.length || opts.rarity.length;
    const scopeLabel = opts.regions.length ? t(state.language, "labels.regions") : opts.classifications.length ? copy("Classes", "Classes") : t(state.language, "labels.rarity");
    const scopeBody = opts.regions.length
      ? copy("Regional coverage available in this collection.", "Couverture regionale disponible dans cette collection.")
      : opts.classifications.length
        ? copy("Distinct record families represented in this collection.", "Familles de fiches distinctes representees dans cette collection.")
        : copy("Rarity bands represented in this collection.", "Paliers de rarete representes dans cette collection.");
    const actions = [
      button(buildRouteUrl(routeForSearch(state.language, { kind: route.kind })), t(state.language, "nav.search"), true),
      hubId ? button(buildRouteUrl(routeForHub(state.language, hubId)), hubTitle) : "",
      mapSource
        ? button(
            buildSevenMapUrl({
              language: state.language,
              type: mapSource.mapRef.type,
              region: route.region || mapSource.mapRef.regionIds?.[0] || "",
              focus: "fit",
              open: "filters",
            }),
            t(state.language, "actions.openMap"),
            false,
            true,
          )
        : "",
    ]
      .filter(Boolean)
      .join("");
    return `<div class="hero-copy"><p class="eyebrow">${escapeHtml(hubTitle)}</p><h1 id="heroTitle">${escapeHtml(routeTitle(store, route))}</h1><p class="hero-text">${escapeHtml(routeSubtitle(store, route))}</p><div class="hero-actions">${actions}</div></div><div class="hero-grid">${stat(t(state.language, "labels.entries"), formatCount(meta?.count || base.length), copy("Full generated coverage for this collection.", "Couverture complete generee pour cette collection."))}${stat(t(state.language, "labels.mapLinked"), formatCount(meta?.mapLinkedCount || base.filter((entry) => entry.mapRef).length), copy("Entries that open straight into SevenMap.", "Fiches qui ouvrent directement SevenMap."))}${scopeCount ? stat(scopeLabel, formatCount(scopeCount), scopeBody) : stat(t(state.language, "labels.generatedAt"), formatDateTime(store.manifest.generatedAt, state.language) || "-", t(state.language, "copy.heroGeneratedBody"))}</div>`;
  }
  if (route.view === "hub" && route.kind === "systems") {
    const travelCount = ["waypoints", "portals", "puzzles", "fishing-spots"].reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
    const progressionCount = ["quests", "main-quests", "side-quests", "hidden-quests", "stella-quests", "unlocks"].reduce((sum, id) => sum + (listMeta(store, id)?.count || 0), 0);
    const actions = [
      (listMeta(store, "quests")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "quests")), listMeta(store, "quests")?.title?.[state.language] || titleCase("quests"), true) : "",
      (listMeta(store, "waypoints")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "waypoints")), listMeta(store, "waypoints")?.title?.[state.language] || titleCase("waypoints")) : "",
      (listMeta(store, "unlocks")?.count || 0) > 0 ? button(buildRouteUrl(routeForList(state.language, "unlocks")), listMeta(store, "unlocks")?.title?.[state.language] || titleCase("unlocks")) : "",
    ]
      .filter(Boolean)
      .join("");
    return `<div class="hero-copy"><p class="eyebrow">${escapeHtml(copy("System control", "Controle systeme"))}</p><h1 id="heroTitle">${escapeHtml(routeTitle(store, route))}</h1><p class="hero-text">${escapeHtml(copy("Use this hub to jump straight into traversal, quest progression, portal chains, puzzle routes and exact unlock gates.", "Utilise ce hub pour ouvrir directement les routes de deplacement, les quetes, les chaines de portails, les parcours d'enigmes et les conditions de deblocage."))}</p><div class="hero-actions">${actions}</div></div><div class="hero-grid">${stat(copy("Traversal", "Deplacement"), formatCount(travelCount), copy("Waypoints, portals and traversal hooks.", "Teleporteurs, portails et points de circulation."))}${stat(copy("Progression", "Progression"), formatCount(progressionCount), copy("Quest flow and unlock gates tied to the world.", "Flux de quetes et portes de deblocage liees au monde."))}${stat(t(state.language, "labels.mapLinked"), formatCount(hubTotals(store, "systems").mapLinkedCount), copy("System entries with direct SevenMap links.", "Entrees systeme avec lien direct vers SevenMap."))}</div>`;
  }
  const entry = resolveEntry(store, route);
  return `<div class="hero-copy"><p class="eyebrow">${escapeHtml(route.view)}</p><h1 id="heroTitle">${escapeHtml(routeTitle(store, route))}</h1><p class="hero-text">${escapeHtml(routeSubtitle(store, route))}</p></div><div class="hero-grid">${stat(t(state.language, "labels.language"), state.language.toUpperCase(), t(state.language, "copy.heroLanguageBody"))}${stat(t(state.language, "labels.generatedAt"), formatDateTime(store.manifest.generatedAt, state.language) || "-", t(state.language, "copy.heroGeneratedBody"))}${entry ? stat(t(state.language, "labels.mapLinked"), entry.mapRef ? t(state.language, "labels.yes") : t(state.language, "labels.no"), t(state.language, "copy.heroMapLinkedBody")) : stat(t(state.language, "labels.sections"), formatCount(selectableLists(store).length), t(state.language, "copy.heroStructuredBody"))}</div>`;
}

export function renderHome(store) {
  return `<section class="page-section"><div class="grid-3">${stat(t(state.language, "labels.entries"), formatCount(store.manifest.counts.entries), t(state.language, "copy.homeEntriesBody"))}${stat(t(state.language, "labels.sections"), formatCount(selectableLists(store).length), t(state.language, "copy.homeSectionsBody"))}${stat(t(state.language, "labels.languages"), "EN / FR", t(state.language, "copy.homeLanguagesBody"))}</div></section>${homeCommandDeck(store)}<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredHubs"))}</p><h3>${escapeHtml(t(state.language, "home.featuredHubs"))}</h3></div></div><div class="guide-grid">${HUB_ORDER.map((id) => `<article class="guide-card guide-card-strong"><div class="guide-card-head"><span class="card-icon">${icon(hubIconName(id))}</span><div><p class="eyebrow">${escapeHtml(t(state.language, "copy.listHubEyebrow"))}</p><strong>${escapeHtml(hubMeta(store, id)?.title?.[state.language] || id)}</strong></div></div><p>${escapeHtml(hubMeta(store, id)?.description?.[state.language] || "")}</p><div class="card-meta-row"><span class="tag">${formatCount(hubTotals(store, id).count)} ${escapeHtml(t(state.language, "labels.entries"))}</span><span class="tag">${formatCount(listsForHub(store, id).length)} ${escapeHtml(t(state.language, "labels.sections"))}</span></div><div class="entry-card-actions">${button(buildRouteUrl(routeForHub(state.language, id)), t(state.language, "actions.exploreHub"))}</div></article>`).join("")}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredLists"))}</p><h3>${escapeHtml(t(state.language, "home.featuredLists"))}</h3></div></div><div class="guide-grid">${activeQuickLists(store).map((id) => listCard(store, id)).join("")}</div></section>${homeListSection(store, "characters", t(state.language, "home.featuredHeroes"))}${homeListSection(store, "weapons", t(state.language, "home.featuredCombat"))}${homeListSection(store, "engravings", t(state.language, "home.featuredCombat"))}${homeListSection(store, "buffs", t(state.language, "home.featuredCombat"))}${homeListSection(store, "bosses", copy("Field bosses", "Boss de terrain"))}${homeListSection(store, "quests", copy("Quest tracking", "Suivi de quetes"))}<section class="page-section"><div class="page-heading"><div><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.coverage"))}</p><h3>${escapeHtml(t(state.language, "home.coverageTitle"))}</h3></div><p class="workspace-subtitle">${escapeHtml(t(state.language, "home.coverageBody"))}</p></div></div><div class="coverage-stack">${renderHubCoverage(store)}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredRegions"))}</p><h3>${escapeHtml(t(state.language, "home.featuredRegions"))}</h3></div></div><div class="entry-grid">${homeFeatured(store, "regions")}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredMaterials"))}</p><h3>${escapeHtml(t(state.language, "home.featuredMaterials"))}</h3></div></div><div class="entry-grid">${homeFeatured(store, "materials")}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredPets"))}</p><h3>${escapeHtml(t(state.language, "home.featuredPets"))}</h3></div></div><div class="entry-grid">${homeFeatured(store, "pets")}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredSystems"))}</p><h3>${escapeHtml(t(state.language, "home.featuredSystems"))}</h3></div></div><div class="entry-grid">${homeFeatured(store, "systems")}</div></section><section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "home.featuredGuides"))}</p><h3>${escapeHtml(t(state.language, "home.featuredGuides"))}</h3></div></div><div class="guide-grid">${GUIDE_PAGES.map((id) => guideCard(id)).join("")}</div></section>`;
}

export function renderHub(store, route) {
  const meta = hubMeta(store, route.kind);
  if (!meta) return empty(t(state.language, "filters.noResults"));
  const listIds = listsForHub(store, route.kind);
  const totals = hubTotals(store, route.kind);
  if (route.kind === "systems") {
    return renderSystemsHub(store, route, meta, listIds, totals);
  }
  const spotlight = [...new Set((meta.lists || []).flatMap((id) => listEntries(store, id).slice(0, 2)))];
  const openHubButton = listIds.length ? button(buildRouteUrl(routeForList(state.language, listIds[0])), t(state.language, "actions.openHub")) : "";
  return `<section class="page-section"><div class="detail-hero-card detail-hero-card-hub"><div class="detail-hero-head"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.coverage"))}</p><h3>${escapeHtml(meta.title?.[state.language] || titleCase(route.kind))}</h3><p class="hero-text">${escapeHtml(meta.description?.[state.language] || "")}</p></div></div><div class="entry-card-actions">${button(buildRouteUrl(routeForSearch(state.language, { kind: route.kind })), t(state.language, "nav.search"))}${openHubButton}</div><div class="grid-3 compact-grid">${stat(t(state.language, "labels.sections"), formatCount(listIds.length), t(state.language, "home.coverageTitle"))}${stat(t(state.language, "labels.entries"), formatCount(totals.count), t(state.language, "copy.currentCoverage"))}${stat(t(state.language, "labels.mapLinked"), formatCount(totals.mapLinkedCount), t(state.language, "labels.mapCoverage"))}</div></div></section><section class="page-section"><div class="coverage-grid">${listIds.map((id) => listCard(store, id)).join("")}</div></section><section class="page-section"><div class="entry-grid">${spotlight.map((entry) => entryCard(store, entry)).join("")}</div></section>`;
}

export function renderList(store, route) {
  const base = listEntries(store, route.kind);
  const entries = filterEntries(base, route);
  const limit = resolveRenderLimit(route.limit, LIST_PAGE_SIZE);
  const visibleEntries = entries.slice(0, limit);
  const opts = optionsForEntries(base);
  const mapSource = entries.find((entry) => entry.mapRef?.type);
  const activeFilters = [
    route.q ? detailTag(`${copy("Query", "Requete")} ${route.q}`, "rate") : "",
    route.region ? detailTag(regionLabel(store, route.region), "context") : "",
    route.rarity ? detailTag(route.rarity, "") : "",
    route.classification ? detailTag(route.classification, "") : "",
  ]
    .filter(Boolean)
    .join("");
  const showMoreHref =
    visibleEntries.length < entries.length
      ? buildRouteUrl({ ...route, limit: String(Math.min(entries.length, limit + LIST_PAGE_SIZE)) })
      : "";
  const mapButton = mapSource ? button(buildSevenMapUrl({ language: state.language, type: mapSource.mapRef.type, region: route.region || mapSource.mapRef.regionIds?.[0] || "", focus: "fit", open: "filters" }), t(state.language, "actions.openMap"), false, true) : "";
  return `<section class="page-section"><div class="filter-bar"><input id="listSearchInput" class="list-filter-input" type="search" value="${escapeHtml(route.q || "")}" placeholder="${escapeHtml(t(state.language, "filters.searchInList"))}" /><select id="listRegionSelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allRegions"))}</option>${opts.regions.map((id) => `<option value="${escapeHtml(id)}" ${route.region === id ? "selected" : ""}>${escapeHtml(regionLabel(store, id))}</option>`).join("")}</select><select id="listRaritySelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allRarity"))}</option>${opts.rarity.map((id) => `<option value="${escapeHtml(id)}" ${route.rarity === id ? "selected" : ""}>${escapeHtml(id)}</option>`).join("")}</select>${opts.classifications.length ? `<select id="listClassSelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allClasses"))}</option>${opts.classifications.map((id) => `<option value="${escapeHtml(id)}" ${route.classification === id ? "selected" : ""}>${escapeHtml(id)}</option>`).join("")}</select>` : ""}</div><div class="page-toolbar"><span class="result-count">${entriesShownLabel(visibleEntries.length, entries.length)}</span><div class="entry-card-actions">${mapButton}${showMoreHref ? button(showMoreHref, t(state.language, "actions.showMore")) : ""}${route.q || route.region || route.rarity || route.classification ? button(buildRouteUrl(routeForList(state.language, route.kind)), t(state.language, "actions.clearFilters")) : ""}</div></div>${activeFilters ? `<div class="detail-chip-row detail-chip-row-rich list-active-filter-row">${activeFilters}</div>` : ""}${entries.length ? `<div class="entry-grid">${visibleEntries.map((entry) => entryCard(store, entry)).join("")}</div>` : empty(t(state.language, "filters.noResults"), listMeta(store, route.kind)?.description?.[state.language] || "")}</section>${renderSiblingLists(store, route.kind)}`;
}

export function renderRegion(store, region) {
  const all = entriesForRegion(store, region);
  const regionId = region.regionIds?.[0] || "";
  const gathering = all.filter((entry) => ["gathering", "mining", "mastery"].includes(primaryList(entry)));
  const waypoints = all.filter((entry) => primaryList(entry) === "waypoints");
  const pets = all.filter((entry) => primaryList(entry) === "pets");
  const bosses = all.filter((entry) => primaryList(entry) === "bosses");
  return `<section class="page-section"><div class="detail-hero-card detail-hero-card-region"><div class="detail-hero-head"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.region"))}</p><h3>${escapeHtml(text(region, "name"))}</h3><p class="hero-text">${escapeHtml(text(region, "summary"))}</p></div></div><div class="entry-card-actions">${button(buildSevenMapUrl({ language: state.language, region: regionId, regions: region.regionIds || [], focus: "fit", open: "filters" }), t(state.language, "actions.openMap"), true, true)}${button(buildRouteUrl(routeForSearch(state.language, { region: regionId })), t(state.language, "nav.search"))}</div><div class="grid-3 compact-grid">${stat(t(state.language, "labels.pointCount"), formatCount(region.stats?.pointCount || 0), t(state.language, "copy.regionPointsBody"))}${stat(t(state.language, "labels.sections"), formatCount(Object.keys(region.stats?.typeCounts || {}).length), t(state.language, "copy.regionSystemsBody"))}${stat(t(state.language, "labels.entries"), formatCount(all.length), t(state.language, "copy.regionEntriesBody"))}</div></div></section><section class="page-section"><div class="guide-grid">${listCard(store, "gathering", { region: regionId })}${listCard(store, "pets", { region: regionId })}${listCard(store, "bosses", { region: regionId })}${listCard(store, "waypoints", { region: regionId })}</div></section>${regionSection(store, t(state.language, "copy.regionGathering"), gathering, routeForSearch(state.language, { region: regionId, kind: "gathering" }))}${regionSection(store, listMeta(store, "waypoints")?.title?.[state.language] || titleCase("waypoints"), waypoints, routeForList(state.language, "waypoints", { region: regionId }))}${regionSection(store, listMeta(store, "pets")?.title?.[state.language] || titleCase("pets"), pets, routeForList(state.language, "pets", { region: regionId }))}${regionSection(store, listMeta(store, "bosses")?.title?.[state.language] || titleCase("bosses"), bosses, routeForList(state.language, "bosses", { region: regionId }))}`;
}

export function renderEntry(store, entry) {
  const isRecipeEntry = entry.kind === "recipe";
  const allRelated = relatedEntries(store, entry);
  const costumeEntries = primaryList(entry) === "characters" ? allRelated.filter((item) => primaryList(item) === "costumes").slice(0, 8) : [];
  const costumeIds = new Set(costumeEntries.map((item) => item.id));
  const groupedRelations = relatedCollections(store, entry, allRelated.filter((item) => !costumeIds.has(item.id)));
  const related = allRelated.filter((item) => !costumeIds.has(item.id) && !groupedRelations.consumedIds.has(item.id)).slice(0, 18);
  const displayLists = entry.lists?.includes("recipes") && (entry.lists?.length || 0) > 1 ? entry.lists.filter((id) => id !== "recipes") : entry.lists || [];
  const mapTarget = entry.mapRef ? entry : related.find((item) => item.mapRef) || null;
  const heroImage = entry.image || "";
  const heroIcon = entry.icon || "";
  const altName = alternateName(entry);
  const heroVisual =
    heroImage || heroIcon
      ? `<div class="detail-hero-media">${heroImage ? `<img src="${heroImage}" alt="" loading="lazy" />` : `<img src="${heroIcon}" alt="" loading="lazy" />`}${heroImage && heroIcon && heroImage !== heroIcon ? `<span class="detail-hero-badge"><img src="${heroIcon}" alt="" loading="lazy" /></span>` : ""}</div>`
      : `<div class="entry-card-icon entry-card-icon-large">${icon(primaryList(entry) === "pets" ? "paw" : primaryList(entry) === "bosses" ? "crown" : primaryList(entry) === "engravings" ? "star" : isRecipeCollectionEntry(entry) ? "anvil" : primaryList(entry) === "buffs" ? "star" : primaryList(entry) === "debuffs" ? "fang" : primaryList(entry) === "characters" ? "user" : "world")}</div>`;
  const referenceRows = {
    [copy("Category", "Categorie")]: displayLists.map((id) => listMeta(store, id)?.title?.[state.language] || titleCase(id)).join(", "),
    [t(state.language, "labels.classification")]: entry.class,
    [t(state.language, "labels.rarity")]: entry.rarity?.label?.[state.language],
    [copy("Set", "Set")]: entry.kind === "item" ? (entry.fields?.equipmentSets || []).map((set) => set.name?.[state.language] || set.name?.en || "").filter(Boolean).join(", ") : "",
    [state.language === "fr" ? t(state.language, "labels.englishName") : t(state.language, "labels.frenchName")]: altName,
    [t(state.language, "labels.regions")]: (entry.regions || []).join(", "),
    [t(state.language, "labels.pointCount")]: entry.stats?.pointCount ? formatCount(entry.stats.pointCount) : "",
    [t(state.language, "labels.recipeCount")]: entry.stats?.recipeCount ? formatCount(entry.stats.recipeCount) : "",
    [t(state.language, "labels.characterCount")]: entry.stats?.characterCount ? formatCount(entry.stats.characterCount) : "",
    [t(state.language, "labels.costumeCount")]: entry.stats?.costumeCount ? formatCount(entry.stats.costumeCount) : "",
    [copy("Acquisition", "Obtention")]: entry.stats?.acquisitionCount ? formatCount(entry.stats.acquisitionCount) : "",
    [copy("Drops", "Butins")]: entry.stats?.dropCount ? formatCount(entry.stats.dropCount) : "",
    [t(state.language, "labels.skillCount")]: entry.stats?.skillCount ? formatCount(entry.stats.skillCount) : "",
    [t(state.language, "labels.variantCount")]: entry.stats?.variantCount ? formatCount(entry.stats.variantCount) : "",
  };
  const contextRows = {
    [t(state.language, "labels.kind")]: titleCase(entry.kind),
    [copy("Boss type", "Type de boss")]: entry.kind === "boss" ? bossCategorySummary(entry) : "",
    [copy("Loot scaling", "Variation du butin")]: entry.kind === "boss" || entry.kind === "monster" ? entryLootScalingLabel(entry) : "",
    [t(state.language, "labels.type")]: entry.fields?.recipeTypeLabel?.[state.language] || entry.fields?.recipeTypeLabel?.en || titleCase(entry.fields?.recipeType || entry.fields?.effectGroup || ""),
    [t(state.language, "labels.function")]: titleCase(entry.fields?.functionType || ""),
    [t(state.language, "labels.character")]: entry.fields?.heroName?.[state.language] || "",
    [t(state.language, "labels.applyType")]: (entry.fields?.applyTypes || []).map((value) => titleCase(value)).join(", "),
    [t(state.language, "labels.actorState")]: (entry.fields?.actorStates || []).map((value) => titleCase(value)).join(", "),
  };
  const mapButtons = mapTarget?.mapRef
    ? button(
        buildSevenMapUrl({
          language: state.language,
          pointId: mapTarget.mapRef.preferredPointId,
          entrySlug: mapTarget.slug,
          type: mapTarget.mapRef.type,
          focus: "point",
          open: "details",
        }),
        t(state.language, "actions.openMap"),
        true,
        true,
      ) +
      button(
        buildSevenMapUrl({
          language: state.language,
          entrySlug: mapTarget.slug,
          region: mapTarget.mapRef.regionIds?.[0] || "",
          regions: mapTarget.mapRef.regionIds || [],
          type: mapTarget.mapRef.type,
          subcategory: mapTarget.mapRef.subcategory,
          resourceItemId: mapTarget.mapRef.resourceItemId,
          petItemId: mapTarget.mapRef.petItemId,
          actorTid: mapTarget.mapRef.actorTid,
          monCatchTid: mapTarget.mapRef.monCatchTid,
          focus: "fit",
          open: "filters",
        }),
        t(state.language, "actions.showAll"),
        false,
        true,
      )
    : "";
  const heroChips = [
    `<span class="tag">${escapeHtml(listMeta(store, primaryList(entry))?.title?.[state.language] || entry.kind)}</span>`,
    entry.rarity?.label?.[state.language] ? `<span class="tag">${escapeHtml(entry.rarity.label[state.language])}</span>` : "",
    entry.class ? `<span class="tag">${escapeHtml(entry.class)}</span>` : "",
    altName ? `<span class="tag tag-accent">${escapeHtml(`${state.language === "fr" ? "EN" : "FR"}: ${altName}`)}</span>` : "",
  ]
    .filter(Boolean)
    .join("");
  const heroStats = entryHeroStats(entry);
  const heroCardClasses = [
    "detail-hero-card",
    primaryList(entry) === "characters" ? "detail-hero-card-character" : "",
    isRecipeEntry ? "detail-hero-card-recipe" : "",
    entry.kind === "item" ? "detail-hero-card-item" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const summaryColumns = `<section class="page-section detail-columns"><div class="detail-column panel-inner compact-section-card"><h4>${escapeHtml(copy("Overview", "Apercu"))}</h4><div class="detail-list">${kvRows(referenceRows)}</div></div><div class="detail-column panel-inner compact-section-card"><h4>${escapeHtml(copy("Gameplay", "Gameplay"))}</h4><div class="detail-list">${kvRows(contextRows)}</div></div></section>`;
  const relatedMarkup = related.length ? `<section class="page-section"><div class="page-heading"><div><p class="eyebrow">${escapeHtml(t(state.language, "labels.related"))}</p><h3>${escapeHtml(t(state.language, "labels.related"))}</h3></div></div><div class="entry-grid">${related.map((item) => entryCard(store, item)).join("")}</div></section>` : "";

  let detailBody = `${summaryColumns}${costumeEntries.length ? showcaseSection(store, costumeEntries, t(state.language, "labels.costumes"), t(state.language, "labels.costumes")) : ""}${groupedRelations.markup}${recipeVariantSection(store, entry)}${entryContextSections(store, entry)}${relatedMarkup}`;

  if (entry.kind === "item") {
    const itemTabs = [
      {
        id: "overview",
        label: copy("Overview", "Apercu"),
        markup: `${summaryColumns}${itemSpecSection(entry)}${itemFunctionSection(entry)}`,
      },
      {
        id: "obtain",
        label: copy("Obtain", "Obtention"),
        markup: `${itemAcquisitionSection(store, entry)}${itemRecycledFromSection(store, entry)}${itemDisassemblySection(store, entry)}`,
      },
      {
        id: "effects",
        label: copy("Effects", "Effets"),
        markup: `${itemEquipmentEffectsSection(entry)}${equipmentSetBonusSection(store, entry)}`,
      },
      {
        id: "links",
        label: copy("Links", "Liens"),
        markup: `${groupedRelations.markup}${relatedMarkup}`,
      },
    ].filter((tab) => tab.markup);
    const activeTab = itemTabs.find((tab) => tab.id === state.route.tab)?.id || itemTabs[0]?.id || "overview";
    detailBody = `${detailTabMarkup(entry, itemTabs, activeTab)}${itemTabs.find((tab) => tab.id === activeTab)?.markup || ""}`;
  } else if (entry.kind === "character") {
    const characterTabs = [
      {
        id: "styles",
        label: copy("Styles", "Styles"),
        markup: weaponStyleSection(store, entry),
      },
      {
        id: "overview",
        label: copy("Overview", "Apercu"),
        markup: `${summaryColumns}${equipmentSection(store, entry)}${baseStatsSection(entry)}${profileSection(entry)}${commonMasterySection(store, entry)}${costumeEntries.length ? showcaseSection(store, costumeEntries, t(state.language, "labels.costumes"), t(state.language, "labels.costumes")) : ""}`,
      },
      {
        id: "links",
        label: copy("Links", "Liens"),
        markup: `${groupedRelations.markup}${relatedMarkup}`,
      },
    ].filter((tab) => tab.markup);
    const activeTab = characterTabs.find((tab) => tab.id === state.route.tab)?.id || "styles";
    detailBody = `${detailTabMarkup(entry, characterTabs, activeTab)}${characterTabs.find((tab) => tab.id === activeTab)?.markup || ""}`;
  }

  return `<section class="page-section"><div class="${heroCardClasses}"><div class="detail-hero-head">${heroVisual}<div class="detail-hero-content"><div class="detail-hero-copy"><p class="eyebrow">${escapeHtml(listMeta(store, primaryList(entry))?.title?.[state.language] || entry.kind)}</p><h3>${escapeHtml(text(entry, "name"))}</h3>${heroChips ? `<div class="detail-chip-row">${heroChips}</div>` : ""}<p class="hero-text">${escapeHtmlWithBreaks(text(entry, "description") || text(entry, "summary") || t(state.language, "labels.noDescription"))}</p></div>${heroStats}<div class="entry-card-actions">${mapButtons}</div></div></div></div></section>${detailBody}`;
}

export function renderSearch(store, route) {
  const hasFilters = !!(route.q || route.kind || route.region || route.rarity);
  if (!hasFilters) return `<section class="page-section"><article class="feature-card"><p class="eyebrow">${escapeHtml(t(state.language, "search.title"))}</p><strong>${escapeHtml(t(state.language, "search.landingTitle"))}</strong><p>${escapeHtml(t(state.language, "search.landingBody"))}</p></article></section><section class="page-section"><div class="guide-grid">${activeQuickLists(store).map((id) => listCard(store, id)).join("")}</div></section>`;
  const matches = searchEntries(store, route);
  const limit = resolveRenderLimit(route.limit, SEARCH_PAGE_SIZE);
  const results = matches.slice(0, limit);
  const showMoreHref =
    results.length < matches.length
      ? buildRouteUrl({ ...route, limit: String(Math.min(matches.length, limit + SEARCH_PAGE_SIZE)) })
      : "";
  return `<section class="page-section"><div class="filter-bar"><input id="searchPageInput" class="list-filter-input" type="search" value="${escapeHtml(route.q || "")}" placeholder="${escapeHtml(t(state.language, "filters.searchEverywhere"))}" /><select id="searchListSelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allCategories"))}</option>${selectableLists(store).map((id) => `<option value="${escapeHtml(id)}" ${route.kind === id ? "selected" : ""}>${escapeHtml(listMeta(store, id)?.title?.[state.language] || id)}</option>`).join("")}</select><select id="searchRegionSelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allRegions"))}</option>${[...store.regionById.keys()].map((id) => `<option value="${escapeHtml(id)}" ${route.region === id ? "selected" : ""}>${escapeHtml(regionLabel(store, id))}</option>`).join("")}</select><select id="searchRaritySelect" class="list-filter-select"><option value="">${escapeHtml(t(state.language, "filters.allRarity"))}</option>${["grade1", "grade2", "grade3", "grade4", "grade5"].map((id) => `<option value="${id}" ${route.rarity === id ? "selected" : ""}>${id}</option>`).join("")}</select></div><div class="page-toolbar"><span class="result-count">${entriesShownLabel(results.length, matches.length)}</span><div class="entry-card-actions">${showMoreHref ? button(showMoreHref, t(state.language, "actions.showMore")) : ""}${button(buildRouteUrl(routeForSearch(state.language)), t(state.language, "actions.clearFilters"))}</div></div>${results.length ? `<div class="entry-grid">${results.map((entry) => entryCard(store, entry)).join("")}</div>` : empty(t(state.language, "filters.noResults"), t(state.language, "labels.searchHint"))}</section>`;
}

export function renderPageView(store, route) {
  const id = pageId(route);
  const body = pageMeta(id).body?.[state.language] || pageMeta(id).body?.en || [];
  const bullets = pageMeta(id).bullets?.[state.language] || pageMeta(id).bullets?.en || [];
  return `<section class="page-section"><article class="feature-card"><p class="eyebrow">${escapeHtml(pageText(id, "eyebrow"))}</p><strong>${escapeHtml(pageText(id, "title"))}</strong>${body.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}</article></section><section class="page-section"><div class="grid-3">${stat(t(state.language, "labels.entries"), formatCount(store.manifest.counts.entries), t(state.language, "copy.routePointingBody"))}${stat(t(state.language, "labels.sections"), formatCount(Object.keys(store.manifest.lists || {}).length), t(state.language, "copy.routeListBody"))}${stat(t(state.language, "labels.generatedAt"), formatDateTime(store.manifest.generatedAt, state.language) || "-", t(state.language, "copy.routeTimestampBody"))}</div></section>${bullets.length ? `<section class="page-section"><article class="feature-card"><ul class="guide-bullets">${bullets.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul></article></section>` : ""}<section class="page-section"><div class="guide-grid">${GUIDE_PAGES.filter((page) => page !== id).map((page) => guideCard(page)).join("")}</div></section>`;
}
