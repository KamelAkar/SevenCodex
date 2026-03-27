# SevenCodex Architecture

## Goal

SevenCodex is a static-first bilingual codex/wiki companion for Seven Deadly Sins: Origin.
It lives next to SevenMap, not inside the map UI, and shares the same product family:

- generated data, static hosting compatibility, native ES modules
- English and French as first-class UI languages
- deep links between map and codex
- reusable page renderers instead of hand-authored one-off pages

## Folder layout

Preferred repository shape:

- `SevenCodex/`: deployable static site root
- `SevenCodex/src/`: route handling, rendering, search, i18n, UI modules
- `SevenCodex/styles/`: codex design system and page-specific CSS
- `SevenCodex/data/`: generated codex JSON outputs
- `SevenCodex/assets/`: copied icons, imagery, and static visual assets
- `SevenCodex/scripts/`: codex extraction and generation pipeline
- `SevenCodex/docs/`: architecture, pipeline, and integration notes
- `SevenMap/site/`: sibling map app consumed through a deep-link contract

## Route model

SevenCodex currently uses a static-host-friendly query route model.
Labels are localized; slugs stay stable and technical.

Examples:

- `index.html?lang=en&view=home`
- `index.html?lang=fr&view=search&q=iron`
- `index.html?lang=en&view=hub&kind=resources`
- `index.html?lang=en&view=list&kind=materials`
- `index.html?lang=en&view=region&slug=liones`
- `index.html?lang=en&view=entry&kind=item&slug=item-101010011-iron-ore`
- `index.html?lang=en&view=entry&kind=pet&slug=pet-140100002-baby-giant-bird`
- `index.html?lang=en&view=page&kind=methodology`

Additional query parameters carry transient filter state:

- `q`
- `region`
- `rarity`
- `classification`
- `point`
- `limit`

## Page types

SevenCodex should render a small set of reusable page types:

- home page
- category hub
- searchable list page
- entity detail page
- region overview page
- system guide page
- methodology/about page

The content model should make each of these renderers data-driven.

## Information architecture

Primary navigation:

- Home
- Regions
- Resources
- Creatures
- Systems
- Search
- Open SevenMap

Core V1 domains:

- Regions
- Materials
- Gathering
- Mining
- Mastery
- Pets
- Monsters
- Bosses
- Fishing spots and fish
- Portals
- Puzzles / board objects
- Open conditions
- Warp points
- Viewpoints
- Campfires
- Recipes / crafting when extraction quality is sufficient

## Shared entity envelope

Generated entity records should use a stable normalized envelope:

```json
{
  "id": "string",
  "kind": "material",
  "subkind": "gathering",
  "slug": "102030102-activated-sea-grapes",
  "locale": {
    "en": {
      "name": "Activated Sea Grapes",
      "summary": "",
      "description": ""
    },
    "fr": {
      "name": "Raisins de mer actives",
      "summary": "",
      "description": ""
    }
  },
  "labels": {
    "category": {
      "en": "Materials",
      "fr": "Materiaux"
    },
    "subcategory": {
      "en": "Gathering",
      "fr": "Collecte"
    }
  },
  "icon": "",
  "image": "",
  "rarity": {
    "grade": "grade3",
    "rank": 3,
    "color": "blue",
    "hex": "#4a8dff"
  },
  "class": "",
  "tags": [],
  "regionRefs": [],
  "mapRef": {},
  "related": [],
  "sourceTables": [],
  "sourceIds": {},
  "stats": {}
}
```

## Region record

Each region record should expose:

- region id and slug
- localized names
- summary copy
- counts by major category
- featured map-linked entries
- related systems
- quick links into SevenMap

## Search document

Search should be generated, not inferred at runtime from raw tables.
Each search document should include:

- route target
- entity kind and subkind
- English and French names
- aliases / internal identifiers
- descriptions
- category and region labels
- facet fields
- quick action targets, including map deep links when available

Search must normalize accents and match both English and French tokens.

## Bilingual model

Every user-facing label should be localized.

Rules:

- UI labels come from static translation dictionaries
- content labels come from generated localized entity fields
- missing French content should be explicit in generated data
- route slugs stay stable even when localized labels differ

Recommended entity locale structure:

- `locale.en.name`
- `locale.en.summary`
- `locale.en.description`
- `locale.fr.name`
- `locale.fr.summary`
- `locale.fr.description`

## SevenMap integration contract

Codex detail pages should link to SevenMap when the entity is mappable.
SevenMap detail panels should link back to SevenCodex when a codex entity exists.

Recommended codex-side `mapRef` shape:

```json
{
  "pointIds": [],
  "regionIds": [],
  "type": "gathering",
  "subcategory": "kudzu-vine",
  "resourceItemId": "101020101",
  "petItemId": "",
  "actorTid": "",
  "monCatchTid": "",
  "preferredPointId": ""
}
```

Recommended SevenMap deep-link query model:

- `?region=C01-LIONES`
- `?type=gathering&subcategory=kudzu-vine`
- `?type=pet&petItemId=123456789`
- `?pointId=deff0834d9a15f09`

Local development keeps relative-path defaults for deployment but also supports the common split-port setup:

- SevenMap on `http://127.0.0.1:8080/`
- SevenCodex on `http://127.0.0.1:8081/`

That localhost fallback only activates when each app is being served from its own root path, so repo-root same-origin hosting still uses the sibling-folder URLs.

Map-side codex back-link metadata:

- `codexId`
- `codexKind`
- `codexSlug`

## Data sources

Primary sources currently identified:

- `../SevenMap/site/data/map_data.json`
- `../SevenMap/site/data/map_data_full.json`
- `CatchDataTable.json`
- `PetDataInfo.json`
- `FishingZoneActorTable.json`
- `PortalTable.json`
- `PuzzleTable.json`
- `AreaOpenConditionTable.json`
- `AreaOpenConditionGroupTable.json`
- `BindingRecipeTable.json`
- `CookingRecipeTable.json`
- `AvatarTable.json`
- `ActorDataTable.json`
- `ActorModelTable.json`
- `BoardObjectTable.json`
- `FieldBossTable.json`
- `FishTable.json`
- `ItemTable*.json`
- `Quest*.json`
- `NPCActorTable.json`
- zone spawn tables under `Zone/**/spawn/*.json`
- reusable map and UI assets under `../SevenMap/site/assets/` and `Content/UI/UI_Resourse`

## Assumptions

- Static hosting remains the deployment target for both products.
- Generated JSON is preferred over hand-authored content wherever source tables exist.
- SevenMap remains deployable and stable while SevenCodex evolves beside it.
- The first serious milestone prioritizes breadth across major systems over exhaustive quest/NPC coverage.

## Known gaps to fill during implementation

- finalize the exact generated JSON file layout under `SevenCodex/data/`
- document the concrete script entrypoint and rerun command
- confirm the final SevenMap deep-link parser and detail-panel backlink behavior
- validate which monster and NPC tables are parse-safe without special preprocessing
- add browser QA notes once the first local codex build is wired
