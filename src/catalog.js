export const HUB_ORDER = ["regions", "resources", "heroes", "creatures", "systems"];

export const QUICK_LISTS = ["characters", "weapons", "armor", "engravings", "buffs", "debuffs", "recipes", "bosses", "quests"];

export const LIST_ORDER = [
  "regions",
  "waypoints",
  "fishing-spots",
  "materials",
  "gathering",
  "mining",
  "mastery",
  "characters",
  "weapons",
  "equipment",
  "armor",
  "costumes",
  "accessories",
  "buffs",
  "debuffs",
  "items",
  "engravings",
  "recipes",
  "binding-recipes",
  "cooking-recipes",
  "production-recipes",
  "pets",
  "ground-mounts",
  "flying-mounts",
  "glider-pets",
  "monsters",
  "bosses",
  "field-bosses",
  "dungeon-bosses",
  "boss-challenges",
  "fish",
  "quests",
  "main-quests",
  "side-quests",
  "hidden-quests",
  "stella-quests",
  "portals",
  "puzzles",
  "unlocks",
  "npcs",
  "avatars",
];

export const GUIDE_PAGES = ["about", "methodology", "sources", "versioning"];

export const HUB_ICONS = {
  regions: "world",
  resources: "leaf",
  heroes: "user",
  creatures: "spark",
  systems: "compass",
};

export const LIST_ICONS = {
  regions: "world",
  waypoints: "pin",
  "fishing-spots": "hook",
  materials: "gem",
  gathering: "leaf",
  mining: "pick",
  mastery: "star",
  characters: "user",
  weapons: "blade",
  equipment: "shield",
  armor: "shield",
  costumes: "spark",
  accessories: "gem",
  buffs: "star",
  debuffs: "fang",
  items: "bag",
  engravings: "star",
  recipes: "anvil",
  "binding-recipes": "anvil",
  "cooking-recipes": "scroll",
  "production-recipes": "anvil",
  pets: "paw",
  "ground-mounts": "paw",
  "flying-mounts": "spark",
  "glider-pets": "spark",
  monsters: "fang",
  bosses: "crown",
  "field-bosses": "crown",
  "dungeon-bosses": "crown",
  "boss-challenges": "crown",
  fish: "fish",
  quests: "scroll",
  "main-quests": "scroll",
  "side-quests": "scroll",
  "hidden-quests": "scroll",
  "stella-quests": "scroll",
  portals: "gate",
  puzzles: "grid",
  unlocks: "key",
  npcs: "user",
  avatars: "user",
};

export const PAGE_ICONS = {
  about: "world",
  methodology: "compass",
  sources: "bag",
  versioning: "spark",
};

export const PAGE_META = {
  about: {
    eyebrow: {
      en: "Companion product",
      fr: "Produit compagnon",
    },
    title: {
      en: "What SevenCodex is for",
      fr: "À quoi sert SevenCodex",
    },
    summary: {
      en: "A bilingual static-first wiki built beside SevenMap, tuned for fast lookup, category browsing, and map-aware reference pages.",
      fr: "Un wiki bilingue static-first construit à côté de SevenMap, pensé pour la recherche rapide, la navigation par catégories et des fiches liées à la carte.",
    },
    body: {
      en: [
        "SevenCodex is the reference layer for systems that are broader than a single map marker: materials, recipes, monsters, portals, unlock conditions, region overviews, and progression-facing lookup pages.",
        "The site is generated from local exports and existing SevenMap data, so it can be rebuilt after updates without turning into a manually maintained info dump.",
      ],
      fr: [
        "SevenCodex est la couche de référence pour les systèmes qui dépassent un simple marqueur de carte : matériaux, recettes, monstres, portails, conditions de déblocage, vues régionales et pages de progression.",
        "Le site est généré à partir des exports locaux et des données existantes de SevenMap afin de pouvoir être reconstruit après les mises à jour, sans devenir un dépôt d'informations maintenu à la main.",
      ],
    },
    bullets: {
      en: [
        "Static hosting compatible and deployable next to SevenMap.",
        "English and French labels are first-class across chrome and generated content.",
        "Map-linked records open the relevant SevenMap view directly when a map contract exists.",
      ],
      fr: [
        "Compatible avec l'hébergement statique et déployable à côté de SevenMap.",
        "Les libellés anglais et français sont traités comme des langues de premier plan dans l'interface et les contenus générés.",
        "Les fiches liées à la carte ouvrent directement la vue SevenMap pertinente quand un contrat de carte existe.",
      ],
    },
  },
  methodology: {
    eyebrow: {
      en: "Generation model",
      fr: "Modèle de génération",
    },
    title: {
      en: "How the codex is built",
      fr: "Comment le codex est construit",
    },
    summary: {
      en: "The codex normalizes map data, localized tables, recipes, travel systems, creature records, and unlock rules into a shared entity envelope.",
      fr: "Le codex normalise les données de carte, les tables localisées, les recettes, les systèmes de voyage, les créatures et les règles de déblocage dans une enveloppe d'entité commune.",
    },
    body: {
      en: [
        "The generator reads curated SevenMap map points and multiple game tables, resolves English and French text through the existing resource resolver, and emits split JSON files for static consumption.",
        "Entries are grouped into hubs and list pages so the UI can stay modular while the data pipeline continues to expand into new systems later.",
      ],
      fr: [
        "Le générateur lit les points de carte curés de SevenMap et plusieurs tables du jeu, résout les textes anglais et français via le resource resolver existant, puis produit des fichiers JSON séparés pour une consommation statique.",
        "Les entrées sont regroupées en hubs et en listes afin que l'interface reste modulaire pendant que la pipeline de données s'étend à d'autres systèmes.",
      ],
    },
    bullets: {
      en: [
        "Generated entities share stable ids, slugs, locale blocks, sources, related links, and optional `mapRef` contracts.",
        "Search uses a generated bilingual index instead of scraping raw tables at runtime.",
        "Icons are copied into codex-local generated assets so the site remains portable.",
      ],
      fr: [
        "Les entités générées partagent des ids stables, des slugs, des blocs de langue, des sources, des liens associés et des contrats `mapRef` optionnels.",
        "La recherche s'appuie sur un index bilingue généré plutôt que sur une lecture brute des tables au runtime.",
        "Les icônes sont copiées dans des assets générés propres au codex afin que le site reste portable.",
      ],
    },
  },
  sources: {
    eyebrow: {
      en: "Mined data",
      fr: "Données exploitées",
    },
    title: {
      en: "Current data sources",
      fr: "Sources de données actuelles",
    },
    summary: {
      en: "This milestone already uses SevenMap's curated points plus item, pet, monster, portal, puzzle, waypoint, fishing, recipe, and unlock-condition tables.",
      fr: "Ce jalon utilise déjà les points curés de SevenMap ainsi que les tables d'objets, familiers, monstres, portails, énigmes, téléporteurs, pêche, recettes et conditions de déblocage.",
    },
    body: {
      en: [
        "The strongest map-linked domains come from SevenMap's curated `site/data/map_data.json`, while reference-heavy systems come from exported text tables under the game's `Content/TextDatas/CData` tree.",
        "The source footprint is intentionally documented so future passes can add NPCs, quests, equipment, and regional landmarks without breaking the current contract.",
      ],
      fr: [
        "Les domaines les mieux liés à la carte proviennent du `site/data/map_data.json` curé par SevenMap, tandis que les systèmes de référence proviennent des tables de texte exportées sous `Content/TextDatas/CData` du jeu.",
        "L'empreinte des sources est documentée volontairement afin que de futures passes puissent ajouter PNJ, quêtes, équipements et repères régionaux sans casser le contrat actuel.",
      ],
    },
    bullets: {
      en: [
        "Map points: curated and full SevenMap datasets.",
        "Tables: `PetDataInfo`, `MonsterActorTable`, `FishingZoneActorTable`, `PortalTable`, `PuzzleTable`, `AreaOpenCondition*`, `BindingRecipeTable`, `CookingRecipeTable`, `ProductionRecipeTable`, and `ItemTable*`.",
        "Assets: SevenMap icons plus copied game exports under the codex `assets/generated` directory.",
      ],
      fr: [
        "Points de carte : datasets SevenMap curés et complets.",
        "Tables : `PetDataInfo`, `MonsterActorTable`, `FishingZoneActorTable`, `PortalTable`, `PuzzleTable`, `AreaOpenCondition*`, `BindingRecipeTable`, `CookingRecipeTable`, `ProductionRecipeTable` et `ItemTable*`.",
        "Assets : icônes SevenMap plus exports du jeu copiés dans le répertoire `assets/generated` du codex.",
      ],
    },
  },
  versioning: {
    eyebrow: {
      en: "Update workflow",
      fr: "Workflow de mise à jour",
    },
    title: {
      en: "Rebuild and extension path",
      fr: "Reconstruction et extension",
    },
    summary: {
      en: "SevenCodex is meant to be rerun after game updates, not manually patched entry by entry.",
      fr: "SevenCodex est conçu pour être relancé après les mises à jour du jeu, pas pour être corrigé fiche par fiche à la main.",
    },
    body: {
      en: [
        "The current generator command is `python scripts/build_codex_data.py` from the SevenCodex repository root. That command refreshes the JSON datasets and copies any referenced generated assets.",
        "The UI is intentionally split into route, data-store, render, and style modules so new categories can be added without turning the codex into a single large file.",
      ],
      fr: [
        "La commande actuelle du générateur est `python scripts/build_codex_data.py` depuis la racine du dépôt SevenCodex. Cette commande régénère les jeux de données JSON et copie les assets générés référencés.",
        "L'interface est volontairement découpée en modules de route, data-store, rendu et styles afin de permettre l'ajout de nouvelles catégories sans transformer le codex en fichier monolithique.",
      ],
    },
    bullets: {
      en: [
        "Future passes can enrich icons, NPC coverage, quest relationships, and stronger region storytelling without changing the static deployment model.",
        "SevenMap and SevenCodex share a deep-link contract instead of a shared runtime, which keeps both apps deployable on their own.",
        "Generated timestamps and source-table references are surfaced in the UI to make each build auditable.",
      ],
      fr: [
        "Les prochaines passes pourront enrichir les icônes, la couverture PNJ, les relations de quête et le storytelling régional sans changer le modèle de déploiement statique.",
        "SevenMap et SevenCodex partagent un contrat de deep-link au lieu d'un runtime commun, ce qui permet de déployer les deux applications séparément.",
        "Les horodatages de génération et les références de tables source sont affichés dans l'interface afin que chaque build reste auditable.",
      ],
    },
  },
};
