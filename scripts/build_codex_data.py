#!/usr/bin/env python3
"""
Build SevenCodex data from SevenMap outputs and FModel exports.

The script keeps the codex static-first:
- normalized JSON is generated under data/
- referenced icons are copied into assets/generated/
- the codex can be deployed without the local extraction toolchain
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from resource_resolver import ResourceResolver, repair_mojibake


ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_ROOT = ROOT.parent
SEVENMAP_ROOT = DOCUMENTS_ROOT / "SevenMap"
FEXPORT_ROOT = DOCUMENTS_ROOT / "FModel" / "Output" / "Exports" / "SevenDeadlySins"
TEXTDATA_DIR = FEXPORT_ROOT / "Content" / "TextDatas" / "CData"
LOCALIZATION_DIR = FEXPORT_ROOT / "Content" / "Localization" / "Game"
SITE_ROOT = SEVENMAP_ROOT / "site"
SITE_DATA_DIR = SITE_ROOT / "data"
SITE_ASSETS_DIR = SITE_ROOT / "assets"
CODEX_ROOT = ROOT
CODEX_DATA_DIR = CODEX_ROOT / "data"
CODEX_ASSETS_DIR = CODEX_ROOT / "assets"
GENERATED_ASSETS_DIR = CODEX_ASSETS_DIR / "generated"
BUFF_ICON_REMOTE_BASE = "https://gacha-road-project.vercel.app/images/7dsOrigin/Buff/"

IMAGE_ASSET_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg", ".svg"}
PACKAGE_ASSET_SUFFIXES = {".uasset"}

MAP_DATA_PATH = SITE_DATA_DIR / "map_data.json"
MAP_DATA_FULL_PATH = SITE_DATA_DIR / "map_data_full.json"
CLOUDFLARE_MAX_ASSET_BYTES = 25 * 1024 * 1024
SITE_URL = "https://sevencodex.com/"
GUIDE_PAGE_IDS = ["about", "methodology", "sources", "versioning"]

REGION_LABELS_FR = {
    "Liones": "Liones",
    "Pernes": "Pernes",
    "Fairy King's Forest": "For\u00eat du Roi des F\u00e9es",
    "Baste Desert": "D\u00e9sert de Baste",
    "Vanya": "Vanya",
    "Solgres": "Solgales",
    "Ferzen": "Ferzen",
    "Wind Cove Waters": "Eaux de la crique venteuse",
    "Dragon's Grave": "Tombe du dragon",
    "Farewell Island": "\u00cele des adieux",
    "Sand Valley": "Vall\u00e9e des sables",
    "Silent Desert": "D\u00e9sert silencieux",
    "Desert of Memories": "D\u00e9sert des souvenirs",
    "Liones Northern Front": "Front nord de Liones",
    "Sealed Domain": "Domaine scell\u00e9",
}

HUBS = {
    "regions": {
        "title": {"en": "Regions", "fr": "Regions"},
        "description": {
            "en": "World areas, travel anchors, and map-linked regional browsing.",
            "fr": "Zones du monde, points de voyage et navigation r\u00e9gionale li\u00e9e \u00e0 la carte.",
        },
        "lists": ["regions", "waypoints", "fishing-spots", "field-bosses"],
    },
    "resources": {
        "title": {"en": "Resources", "fr": "Ressources"},
        "description": {
            "en": "Materials, field nodes, ingredients, and crafting-driven item references.",
            "fr": "Mat\u00e9riaux, noeuds de terrain, ingr\u00e9dients et r\u00e9f\u00e9rences d'objets li\u00e9es \u00e0 l'artisanat.",
        },
        "lists": [
            "materials",
            "gathering",
            "mining",
            "mastery",
            "items",
            "engravings",
            "recipes",
            "binding-recipes",
            "cooking-recipes",
            "production-recipes",
        ],
    },
    "heroes": {
        "title": {"en": "Heroes", "fr": "Heros"},
        "description": {
            "en": "Playable characters, gear sets, costumes, and combat-facing effects.",
            "fr": "Personnages jouables, ensembles d'equipement, costumes et effets orientes combat.",
        },
        "lists": [
            "characters",
            "weapons",
            "equipment",
            "armor",
            "costumes",
            "accessories",
            "avatars",
            "buffs",
            "debuffs",
        ],
    },
    "creatures": {
        "title": {"en": "Creatures", "fr": "Creatures"},
        "description": {
            "en": "Pets, monsters, field bosses, dungeon bosses, boss challenges, and fish references.",
            "fr": "Familiers, monstres, boss de terrain, boss de donjon, defis boss et references liees a la peche.",
        },
        "lists": ["pets", "ground-mounts", "flying-mounts", "glider-pets", "monsters", "field-bosses", "dungeon-bosses", "boss-challenges", "fish", "fishing-spots"],
    },
    "systems": {
        "title": {"en": "Systems", "fr": "Syst\u00e8mes"},
        "description": {
            "en": "Traversal, puzzles, unlock conditions, and supporting systems.",
            "fr": "Travers\u00e9e, \u00e9nigmes, conditions de d\u00e9blocage et syst\u00e8mes de support.",
        },
        "lists": ["portals", "puzzles", "unlocks", "waypoints", "npcs", "avatars", "quests", "main-quests", "side-quests", "hidden-quests", "stella-quests"],
    },
}

LISTS = {
    "regions": {
        "hub": "regions",
        "kind": "region",
        "title": {"en": "Regions", "fr": "Regions"},
        "description": {
            "en": "Regional overview pages built from tracked map coverage.",
            "fr": "Pages de vue d'ensemble r\u00e9gionale construites \u00e0 partir de la couverture cartographique.",
        },
    },
    "materials": {
        "hub": "resources",
        "kind": "item",
        "title": {"en": "Materials", "fr": "Mat\u00e9riaux"},
        "description": {
            "en": "Crafting ingredients and map-linked material sources.",
            "fr": "Ingr\u00e9dients d'artisanat et sources de mat\u00e9riaux li\u00e9es \u00e0 la carte.",
        },
    },
    "gathering": {
        "hub": "resources",
        "kind": "node",
        "title": {"en": "Gathering", "fr": "Collecte"},
        "description": {
            "en": "Open-world gathering node types with direct map actions.",
            "fr": "Types de noeuds de collecte du monde ouvert avec actions carte directes.",
        },
    },
    "mining": {
        "hub": "resources",
        "kind": "node",
        "title": {"en": "Mining", "fr": "Minage"},
        "description": {
            "en": "Ore and lode node types extracted from SevenMap and game tables.",
            "fr": "Types de minerais et de filons extraits de SevenMap et des tables du jeu.",
        },
    },
    "mastery": {
        "hub": "resources",
        "kind": "node",
        "title": {"en": "Mastery", "fr": "Ma\u00eetrise"},
        "description": {
            "en": "Mastery resources tracked on the map.",
            "fr": "Ressources de ma\u00eetrise suivies sur la carte.",
        },
    },
    "items": {
        "hub": "resources",
        "kind": "item",
        "title": {"en": "Items", "fr": "Objets"},
        "description": {
            "en": "Referenced items pulled from item tables and linked systems.",
            "fr": "Objets r\u00e9f\u00e9renc\u00e9s issus des tables d'objets et des syst\u00e8mes li\u00e9s.",
        },
    },
    "engravings": {
        "hub": "resources",
        "kind": "recipe",
        "title": {"en": "Engravings", "fr": "Gravures"},
        "description": {
            "en": "Engraving recipes from the game's binding/engraving system.",
            "fr": "Recettes de gravure issues du systeme de binding/gravure du jeu.",
        },
    },
    "equipment": {
        "hub": "heroes",
        "kind": "item",
        "title": {"en": "Equipment", "fr": "\u00c9quipement"},
        "description": {
            "en": "Weapons, armor, accessories, and costume gear extracted from item tables.",
            "fr": "Armes, armures, accessoires et costumes extraits des tables d'objets.",
        },
    },
    "characters": {
        "hub": "heroes",
        "kind": "character",
        "title": {"en": "Characters", "fr": "Personnages"},
        "description": {
            "en": "Playable heroes with weapon styles, exact skills, and profile data.",
            "fr": "Heros jouables avec styles d'armes, competences detaillees et fiche de profil.",
        },
    },
    "weapons": {
        "hub": "heroes",
        "kind": "item",
        "title": {"en": "Weapons", "fr": "Armes"},
        "description": {
            "en": "Weapon records from the equipment item table.",
            "fr": "Fiches d'armes issues de la table d'\u00e9quipement.",
        },
    },
    "armor": {
        "hub": "heroes",
        "kind": "item",
        "title": {"en": "Armor", "fr": "Armures"},
        "description": {
            "en": "Armor and defense gear extracted from equipment tables.",
            "fr": "Armures et \u00e9quipements d\u00e9fensifs extraits des tables d'\u00e9quipement.",
        },
    },
    "costumes": {
        "hub": "heroes",
        "kind": "costume",
        "title": {"en": "Costumes", "fr": "Costumes"},
        "description": {
            "en": "Outfits, costume weapons, and hero appearance records.",
            "fr": "Tenues, armes cosmiques et fiches d'apparence des heros.",
        },
    },
    "accessories": {
        "hub": "heroes",
        "kind": "item",
        "title": {"en": "Accessories", "fr": "Accessoires"},
        "description": {
            "en": "Accessory gear references and related item data.",
            "fr": "R\u00e9f\u00e9rences d'accessoires et donn\u00e9es d'objets associ\u00e9es.",
        },
    },
    "recipes": {
        "hub": "resources",
        "kind": "recipe",
        "title": {"en": "Recipes", "fr": "Recettes"},
        "description": {
            "en": "Cooking and production recipes.",
            "fr": "Recettes de cuisine et de production.",
        },
    },
    "binding-recipes": {
        "hub": "resources",
        "kind": "recipe",
        "title": {"en": "Binding Recipes", "fr": "Recettes de liaison"},
        "description": {
            "en": "Binding recipes and equipment conversion recipes.",
            "fr": "Recettes de liaison et recettes de conversion d'\u00e9quipement.",
        },
    },
    "cooking-recipes": {
        "hub": "resources",
        "kind": "recipe",
        "title": {"en": "Cooking Recipes", "fr": "Recettes de cuisine"},
        "description": {
            "en": "Meal and food recipes extracted from CookingRecipeTable.",
            "fr": "Recettes de repas et de nourriture extraites de CookingRecipeTable.",
        },
    },
    "production-recipes": {
        "hub": "resources",
        "kind": "recipe",
        "title": {"en": "Production Recipes", "fr": "Recettes de production"},
        "description": {
            "en": "Production and crafting recipes extracted from ProductionRecipeTable.",
            "fr": "Recettes de production et d'artisanat extraites de ProductionRecipeTable.",
        },
    },
    "pets": {
        "hub": "creatures",
        "kind": "pet",
        "title": {"en": "Pets", "fr": "Familiers"},
        "description": {
            "en": "Capturable creatures and mount-capable companions.",
            "fr": "Cr\u00e9atures capturables et compagnons utilisables comme montures.",
        },
    },
    "ground-mounts": {
        "hub": "creatures",
        "kind": "pet",
        "title": {"en": "Ground Mounts", "fr": "Montures terrestres"},
        "description": {
            "en": "Rideable ground companions and mounts.",
            "fr": "Compagnons montables et montures terrestres.",
        },
    },
    "flying-mounts": {
        "hub": "creatures",
        "kind": "pet",
        "title": {"en": "Flying Mounts", "fr": "Montures volantes"},
        "description": {
            "en": "Flying mount-capable pets and creatures.",
            "fr": "Familiers et cr\u00e9atures pouvant servir de montures volantes.",
        },
    },
    "glider-pets": {
        "hub": "creatures",
        "kind": "pet",
        "title": {"en": "Glider Pets", "fr": "Familiers planeurs"},
        "description": {
            "en": "Glider-oriented companions and support creatures.",
            "fr": "Compagnons de planeur et cr\u00e9atures de soutien a\u00e9rien.",
        },
    },
    "monsters": {
        "hub": "creatures",
        "kind": "monster",
        "title": {"en": "Monsters", "fr": "Monstres"},
        "description": {
            "en": "Localized monster references extracted from MonsterActorTable.",
            "fr": "R\u00e9f\u00e9rences de monstres localis\u00e9es extraites de MonsterActorTable.",
        },
    },
    "bosses": {
        "hub": "creatures",
        "kind": "boss",
        "hidden": True,
        "title": {"en": "Bosses", "fr": "Boss"},
        "description": {
            "en": "Unified boss references across field, dungeon, and boss challenge content.",
            "fr": "References de boss unifiees pour le terrain, les donjons et les defis boss.",
        },
    },
    "field-bosses": {
        "hub": "creatures",
        "kind": "boss",
        "title": {"en": "Field Bosses", "fr": "Boss de terrain"},
        "description": {
            "en": "Boss encounters tracked directly on the world map.",
            "fr": "Boss suivis directement sur la carte du monde.",
        },
    },
    "dungeon-bosses": {
        "hub": "creatures",
        "kind": "boss",
        "title": {"en": "Dungeon Bosses", "fr": "Boss de donjon"},
        "description": {
            "en": "Bosses referenced by dungeon clear conditions and dungeon rewards.",
            "fr": "Boss references par les conditions de fin de donjon et les recompenses associees.",
        },
    },
    "boss-challenges": {
        "hub": "creatures",
        "kind": "boss",
        "title": {"en": "Boss Challenges", "fr": "Defier le boss"},
        "description": {
            "en": "Boss replay and challenge encounters.",
            "fr": "Rencontres du mode Defier le boss.",
        },
    },
    "fish": {
        "hub": "creatures",
        "kind": "fish",
        "title": {"en": "Fish", "fr": "Poissons"},
        "description": {
            "en": "Catchable fish definitions linked to fishing spots and reward items.",
            "fr": "D\u00e9finitions de poissons capturables li\u00e9es aux zones de p\u00eache et aux objets de r\u00e9compense.",
        },
    },
    "fishing-spots": {
        "hub": "regions",
        "kind": "fishing-spot",
        "title": {"en": "Fishing Spots", "fr": "Points de p\u00eache"},
        "description": {
            "en": "Fishing zones and the map points that reach them.",
            "fr": "Zones de p\u00eache et points de carte permettant de les atteindre.",
        },
    },
    "waypoints": {
        "hub": "systems",
        "kind": "waypoint",
        "title": {"en": "Waypoints", "fr": "T\u00e9l\u00e9porteurs"},
        "description": {
            "en": "Fast-travel anchors with localized names and descriptions.",
            "fr": "Points de voyage rapide avec noms et descriptions localis\u00e9s.",
        },
    },
    "portals": {
        "hub": "systems",
        "kind": "portal",
        "title": {"en": "Portals", "fr": "Portails"},
        "description": {
            "en": "Portal and revive-point definitions mined from PortalTable.",
            "fr": "D\u00e9finitions de portails et points de renaissance extraites de PortalTable.",
        },
    },
    "puzzles": {
        "hub": "systems",
        "kind": "puzzle",
        "title": {"en": "Puzzles", "fr": "\u00c9nigmes"},
        "description": {
            "en": "Puzzle and board-object system references.",
            "fr": "R\u00e9f\u00e9rences des syst\u00e8mes d'\u00e9nigmes et d'objets de plateau.",
        },
    },
    "unlocks": {
        "hub": "systems",
        "kind": "unlock",
        "title": {"en": "Unlock Conditions", "fr": "Conditions de d\u00e9blocage"},
        "description": {
            "en": "Area unlock conditions and grouped requirements.",
            "fr": "Conditions d'ouverture des zones et exigences group\u00e9es.",
        },
    },
    "npcs": {
        "hub": "systems",
        "kind": "npc",
        "title": {"en": "NPCs", "fr": "PNJ"},
        "description": {
            "en": "Named non-player characters extracted from NPCActorTable.",
            "fr": "Personnages non joueurs nomm\u00e9s extraits de NPCActorTable.",
        },
    },
    "avatars": {
        "hub": "heroes",
        "kind": "avatar",
        "title": {"en": "Avatars", "fr": "Avatars"},
        "description": {
            "en": "Avatar cosmetics and unlockable appearance entries.",
            "fr": "Cosm\u00e9tiques d'avatar et apparences d\u00e9bloquables.",
        },
    },
    "buffs": {
        "hub": "heroes",
        "kind": "effect",
        "title": {"en": "Buffs", "fr": "Buffs"},
        "description": {
            "en": "Positive status effects and effect families with exact variant details.",
            "fr": "Effets positifs et familles d'effets avec details de variantes exacts.",
        },
    },
    "debuffs": {
        "hub": "heroes",
        "kind": "effect",
        "title": {"en": "Debuffs", "fr": "Debuffs"},
        "description": {
            "en": "Crowd control and negative effects with exact variant details.",
            "fr": "Controles, malus et effets negatifs avec details de variantes exacts.",
        },
    },
    "quests": {
        "hub": "systems",
        "kind": "quest",
        "title": {"en": "Quests", "fr": "Qu\u00eates"},
        "description": {
            "en": "Main, side, hidden, and Stella quest records.",
            "fr": "Fiches de qu\u00eates principales, secondaires, cach\u00e9es et Stella.",
        },
    },
    "main-quests": {
        "hub": "systems",
        "kind": "quest",
        "title": {"en": "Main Quests", "fr": "Qu\u00eates principales"},
        "description": {
            "en": "Story quest progression records.",
            "fr": "Fiches de progression de l'histoire principale.",
        },
    },
    "side-quests": {
        "hub": "systems",
        "kind": "quest",
        "title": {"en": "Side Quests", "fr": "Qu\u00eates secondaires"},
        "description": {
            "en": "Side quest references and local descriptions.",
            "fr": "R\u00e9f\u00e9rences de qu\u00eates secondaires et descriptions localis\u00e9es.",
        },
    },
    "hidden-quests": {
        "hub": "systems",
        "kind": "quest",
        "title": {"en": "Hidden Quests", "fr": "Qu\u00eates cach\u00e9es"},
        "description": {
            "en": "Hidden quest references extracted from QuestHidden.",
            "fr": "R\u00e9f\u00e9rences de qu\u00eates cach\u00e9es extraites de QuestHidden.",
        },
    },
    "stella-quests": {
        "hub": "systems",
        "kind": "quest",
        "title": {"en": "Stella Quests", "fr": "Qu\u00eates Stella"},
        "description": {
            "en": "Stella-specific quest entries and progression records.",
            "fr": "Entr\u00e9es de qu\u00eates Stella et fiches de progression associ\u00e9es.",
        },
    },
}

ITEM_DETAIL_LISTS = {
    "weapon": "weapons",
    "armor": "armor",
    "accessory": "accessories",
}

ITEM_FAMILY_LABELS = {
    "book": {"en": "Grimoire", "fr": "Grimoire"},
    "staff": {"en": "Staff", "fr": "Baton"},
    "wand": {"en": "Wand", "fr": "Baguette"},
    "sword1h": {"en": "Longsword", "fr": "Epee longue"},
    "sword2h": {"en": "Greatsword", "fr": "Espadon"},
    "dualsword": {"en": "Dual swords", "fr": "Lames jumelles"},
    "axe": {"en": "Axe", "fr": "Hache"},
    "necklace": {"en": "Necklace", "fr": "Collier"},
    "earring": {"en": "Earring", "fr": "Boucle d'oreille"},
    "ring": {"en": "Ring", "fr": "Bague"},
    "armor": {"en": "Armor", "fr": "Armure"},
    "bindarmor": {"en": "Engraving armor", "fr": "Armure de gravure"},
    "fishingrod": {"en": "Fishing rod", "fr": "Canne a peche"},
}

ENGRAVING_ITEM_IDS = {
    "101080001",
    "101080002",
    "101080003",
    "101100100",
    "101100101",
    "101100102",
    "101100200",
    "101120295",
    "101120296",
    "101120297",
}

PET_CLASS_LISTS = {
    "ground-mount": "ground-mounts",
    "flying-mount": "flying-mounts",
    "glider": "glider-pets",
}

PET_TYPE_TO_CLASS = {
    "summon": "basic",
    "riding": "ground-mount",
    "gliding": "glider",
    "flying": "flying-mount",
}

QUEST_TYPE_META = {
    "main": {"list": "main-quests", "label_en": "Main quest", "label_fr": "Qu\u00eate principale"},
    "side": {"list": "side-quests", "label_en": "Side quest", "label_fr": "Qu\u00eate secondaire"},
    "hidden": {"list": "hidden-quests", "label_en": "Hidden quest", "label_fr": "Qu\u00eate cach\u00e9e"},
    "stella": {"list": "stella-quests", "label_en": "Stella quest", "label_fr": "Qu\u00eate Stella"},
}
RECIPE_TYPE_LABELS = {
    "binding": {"en": "Engraving", "fr": "Gravure"},
    "cooking": {"en": "Cooking", "fr": "Cuisine"},
    "production": {"en": "Production", "fr": "Production"},
}
RECIPE_TAB_ORDER = {"binding": 1, "cooking": 2, "production": 3}
PRODUCTION_GROUP_ORDER = {
    "production_tab_weapon": 1,
    "production_tab_equip": 2,
    "production_tab_acc": 3,
    "production_tab_use": 4,
    "production_tab_etc": 5,
    "production_tab_comb": 6,
}
QUEST_ID_PATTERN = re.compile(r"(\d{8,9})")
FORMAT_TAG_PATTERN = re.compile(r"\[#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\]|\[-\]")
PLACEHOLDER_PATTERN = re.compile(r"\{(\d+)\}")
PLACEHOLDER_VALUE_PATTERN = re.compile(r"\{(\d+)\}:(.+)")

STYLE_LABELS = {
    "axe": {"en": "Axe", "fr": "Hache"},
    "book": {"en": "Book", "fr": "Livre"},
    "cudgel3c": {"en": "Cudgel", "fr": "Gourdin"},
    "fishingrod": {"en": "Fishing Rod", "fr": "Canne a peche"},
    "gauntlets": {"en": "Gauntlets", "fr": "Gantelets"},
    "lance": {"en": "Lance", "fr": "Lance"},
    "shield": {"en": "Shield", "fr": "Bouclier"},
    "staff": {"en": "Staff", "fr": "Baton"},
    "sword1h": {"en": "Longsword", "fr": "Epee longue"},
    "sword2h": {"en": "Greatsword", "fr": "Espadon"},
    "sworddual": {"en": "Dual Swords", "fr": "Epees jumelles"},
    "wand": {"en": "Wand", "fr": "Baguette"},
}

ELEMENT_LABELS = {
    "dark": {"en": "Dark", "fr": "Tenebres"},
    "fire": {"en": "Fire", "fr": "Feu"},
    "holy": {"en": "Holy", "fr": "Lumiere"},
    "thunder": {"en": "Thunder", "fr": "Foudre"},
    "water": {"en": "Water", "fr": "Eau"},
    "wind": {"en": "Wind", "fr": "Vent"},
}

ROLE_LABELS = {
    "attacker": {"en": "Attacker", "fr": "Attaquant"},
    "buster": {"en": "Buster", "fr": "Buster"},
    "healer": {"en": "Healer", "fr": "Soigneur"},
    "supporter": {"en": "Support", "fr": "Support"},
    "warden": {"en": "Warden", "fr": "Gardien"},
}

MASTERY_TYPE_LABELS = {
    "normal": {"en": "Normal node", "fr": "Noeud normal"},
    "special": {"en": "Special node", "fr": "Noeud special"},
}

MASTERY_CONDITION_LABELS = {
    "always": {"en": "Always active", "fr": "Toujours actif"},
    "equip": {"en": "Active while equipped", "fr": "Actif quand equipe"},
}

SKILL_SLOT_LABELS = {
    "SkillAttack": {"en": "Basic Attack", "fr": "Attaque de base"},
    "SkillActiveNormal": {"en": "Skill E", "fr": "Competence E"},
    "SkillActiveThird": {"en": "Skill RMB", "fr": "Competence RMB"},
    "SkillActiveSpecial": {"en": "Ultimate", "fr": "Ultime"},
    "SkillPassive": {"en": "Passive", "fr": "Passif"},
    "SkillAerialAttack": {"en": "Aerial Attack", "fr": "Attaque aerienne"},
    "AvoidanceSkill": {"en": "Dodge", "fr": "Esquive"},
    "AirAvoidanceSkill": {"en": "Air Dodge", "fr": "Esquive aerienne"},
    "Just_AvoidanceSkill": {"en": "Perfect Dodge", "fr": "Esquive parfaite"},
    "Just_AvoidanceSkill_Reward": {"en": "Perfect Dodge Reward", "fr": "Bonus d'esquive parfaite"},
}

PROFILE_FIELDS = [
    ("gender", {"en": "Gender", "fr": "Genre"}, "Hero_Gender"),
    ("birth", {"en": "Birth", "fr": "Naissance"}, "Hero_Birth"),
    ("height", {"en": "Height", "fr": "Taille"}, "Hero_Height"),
    ("weight", {"en": "Weight", "fr": "Poids"}, "Hero_Weight"),
    ("blood", {"en": "Blood Type", "fr": "Groupe sanguin"}, "Hero_Blood"),
    ("voice", {"en": "Voice", "fr": "Voix"}, "Hero_Voice"),
]

CHARACTER_BASE_STAT_FIELDS = [
    ("B_Atk", {"en": "Attack", "fr": "Attaque"}),
    ("B_Def", {"en": "Defense", "fr": "Defense"}),
    ("B_MaxHp", {"en": "HP", "fr": "PV"}),
    ("C_Critical_Rate", {"en": "Crit rate", "fr": "Taux critique"}),
    ("C_Critical_Dam_Rate", {"en": "Crit damage", "fr": "Degats critiques"}),
    ("A_Accuracy", {"en": "Accuracy", "fr": "Precision"}),
    ("A_Block", {"en": "Block", "fr": "Blocage"}),
    ("Move_Spd", {"en": "Move speed", "fr": "Vitesse"}),
    ("Max_Stamina", {"en": "Stamina", "fr": "Endurance"}),
]

BUFF_BLOCK_FLAGS = {
    "BuffAction_UnableMove": {"en": "Locks movement", "fr": "Bloque le mouvement"},
    "BuffAction_UnableInputKey": {"en": "Locks inputs", "fr": "Bloque les commandes"},
    "BuffAction_UnableSkill": {"en": "Locks skills", "fr": "Bloque les competences"},
    "BuffAction_UnableRun": {"en": "Locks sprint", "fr": "Bloque la course"},
    "BuffAction_UnableJump": {"en": "Locks jump", "fr": "Bloque le saut"},
    "BuffAction_UnableAvoidance": {"en": "Locks dodge", "fr": "Bloque l'esquive"},
    "BuffAction_CancelSkill": {"en": "Cancels skills", "fr": "Interrompt les competences"},
    "BuffAction_UnableRecovery": {"en": "Blocks recovery", "fr": "Bloque la recuperation"},
    "BuffAction_SelfDestruction_Hit": {"en": "Breaks on hit", "fr": "Se dissipe au coup recu"},
}

GENERIC_MONSTER_PORTRAITS = {
    "portrait_normal_hud",
    "portrait_normal_party_hud",
    "portrait_normal_solo_hud",
}

GENERIC_BOSS_ICON = "Monster_Boss_01"
CREATURE_VARIANT_SUFFIX_RE = re.compile(
    r"_(?:social(?:_\d+)?|spawn(?:_\d+)?|battletutorial|battletutorial|tutorial|quest|test|dead|deadburn|trap|fake|small|large|statue|sleep|abysspiece|nuke|shockwave|minion|scale\d+|ember_crystal|violet_crystal|cyan_crystal)$",
    flags=re.IGNORECASE,
)
BOSS_PHASE_SUFFIX_RE = re.compile(r"_phase_\d+$", flags=re.IGNORECASE)
FIELD_BOSS_LABEL_PREFIX_RE = re.compile(r"^\s*world boss:\s*", flags=re.IGNORECASE)
UNUSABLE_CREATURE_LOCAL_KEYS = {
    "local_mon_name_unknown",
    "unknown_dialog",
}
TECHNICAL_CREATURE_MONSTER_IDS = {
    "50201302",
    "50201303",
    "50302303",
    "50303305",
    "50401302",
    "50401303",
    "50403302",
    "50403303",
    "50500601",
    "50500602",
    "50500604",
    "51000008",
    "51300006",
    "51300007",
    "51300016",
    "51300042",
    "51300043",
    "51300051",
    "51300052",
    "51300053",
    "51300054",
    "51300055",
    "51300056",
    "51300057",
    "51300058",
    "51300059",
    "51300060",
    "51300061",
    "51300062",
    "51300063",
    "51300064",
    "51300065",
    "51300066",
    "51300067",
    "51300068",
    "51300070",
    "51600003",
    "51600004",
    "51600006",
    "51800001",
    "51800002",
    "51800003",
    "51800004",
    "51800005",
    "51800006",
    "51800007",
}
TECHNICAL_CREATURE_ACTOR_PREFIXES = (
    "sum_",
    "obj_",
    "s_",
    "none_actor_data",
)
TECHNICAL_CREATURE_ACTOR_IDS = {
    "boss_barnacle_0001_barnaclerock_a01",
    "boss_barnacle_0001_barnaclerock_a02",
    "boss_drake_fall_rock_0001",
    "boss_drakecrystal_a01",
    "boss_scorpybeast_0001_statue",
    "mon_boss_caveguardian_darkevil_0002",
    "mon_boss_caveguardian_darkevil_0003",
    "mon_helbraml_wall_0001",
    "mon_invisible_object_0001",
    "mon_invisible_object_0002",
    "mon_invisible_object_0003",
    "obj_darkevil_caveguardian_center_0001",
    "obj_dracocrystal_a01",
    "obj_quest_scorpybeast_stone",
    "obj_scorpy_sandstorm_0001",
    "obj_tanaris_sector_0001",
    "sum_albion_drkevil_wall_0001",
    "sum_albion_drkevil_whip_0001",
}
TECHNICAL_CREATURE_ACTOR_PATTERNS = (
    "invisible_object",
    "barnaclerock",
    "fall_rock",
    "drakecrystal",
    "cocoon",
    "sandstorm",
    "_child",
    "_fake",
)
TECHNICAL_CREATURE_NAME_HINTS = (
    "작업용",
    "테스트",
    "test",
    "helper",
    "child",
    "기믹",
    "집합용",
    "투명",
)
FIELD_BOSS_LABEL_OVERRIDES = {
    "elite bigmoss": {"en": "Elite Bigmoss", "fr": "Bigmoss d'elite"},
    "elite callus": {"en": "Elite Callus", "fr": "Callus d'elite"},
    "elite darkevil": {"en": "Elite Darkevil", "fr": "Darkevil d'elite"},
    "elite darkevil archer": {"en": "Elite Darkevil Archer", "fr": "Archer darkevil d'elite"},
    "elite draco warrior": {"en": "Elite Draco Warrior", "fr": "Guerrier draco d'elite"},
    "elite fairy curse": {"en": "Elite Fairy Curse", "fr": "Fee maudite d'elite"},
    "elite giantbird": {"en": "Elite Giantbird", "fr": "Oiseau geant d'elite"},
    "elite moss demon": {"en": "Elite Moss Demon", "fr": "Demon moussu d'elite"},
    "elite orlian": {"en": "Elite Orlian", "fr": "Orlian d'elite"},
    "elite orlian demon": {"en": "Elite Orlian Demon", "fr": "Demon orlian d'elite"},
    "elite pirate captain": {"en": "Elite Pirate Captain", "fr": "Capitaine pirate d'elite"},
    "elite sandthief": {"en": "Elite Sandthief", "fr": "Voleur des sables d'elite"},
    "elite screamer wild": {"en": "Elite Screamer Wild", "fr": "Hurleur sauvage d'elite"},
    "elite singspirit": {"en": "Elite Singspirit", "fr": "Esprit chantant d'elite"},
    "elite werebear": {"en": "Elite Werebear", "fr": "Ours-garou d'elite"},
}
BOSS_CHALLENGE_MONSTER_IDS = {
    "50401301",
    "50402301",
    "50403301",
    "50404301",
    "50405301",
}
DUNGEON_BOSS_MONSTER_IDS = {
    "50200001",
    "50200004",
    "50203305",
    "50204301",
    "50204313",
}


def read_json(path: Path, *, sanitize: bool = False):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if sanitize:
        text = "".join(ch if ord(ch) >= 32 or ch in "\r\n\t" else " " for ch in text)
    text = re.sub(r"\bTRUE\b", "true", text)
    text = re.sub(r"\bFALSE\b", "false", text)
    return json.loads(text, strict=False)


def write_json(path: Path, payload, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    json_text = (
        json.dumps(payload, indent=2, ensure_ascii=True)
        if pretty
        else json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    )
    path.write_text(json_text + "\n", encoding="utf-8")


def verify_cloudflare_asset_sizes(paths: List[Path]) -> Dict[str, int]:
    sizes = {}
    oversized = []
    for path in paths:
        size = path.stat().st_size
        sizes[path.name] = size
        if size > CLOUDFLARE_MAX_ASSET_BYTES:
            oversized.append((path.name, size))
    if oversized:
        lines = [
            f"{name}: {size / (1024 * 1024):.2f} MiB"
            for name, size in oversized
        ]
        raise SystemExit(
            "Generated asset exceeds Cloudflare's 25 MiB per-file limit:\n  " + "\n  ".join(lines)
        )
    return sizes


def build_codex_url(params: Dict[str, str]) -> str:
    filtered = [(key, value) for key, value in params.items() if value]
    return f"{SITE_URL}?{urlencode(filtered)}" if filtered else SITE_URL


def xml_escape(value: object) -> str:
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_sitemap_xml(manifest: Dict, entries: List[Dict]) -> str:
    generated_at = manifest.get("generatedAt") or datetime.now(timezone.utc).isoformat()
    routes: List[Tuple[str, str]] = []

    for language in ["en", "fr"]:
        routes.append((build_codex_url({"lang": language, "view": "home"}), language))
        for hub_id in HUBS:
            routes.append((build_codex_url({"lang": language, "view": "hub", "kind": hub_id}), language))
        for list_id, meta in LISTS.items():
            if meta.get("hidden"):
                continue
            routes.append((build_codex_url({"lang": language, "view": "list", "kind": list_id}), language))
        for page_id in GUIDE_PAGE_IDS:
            routes.append((build_codex_url({"lang": language, "view": "page", "kind": page_id}), language))
        for entry in entries:
            if entry.get("kind") == "region":
                routes.append((build_codex_url({"lang": language, "view": "region", "slug": entry.get("slug", "")}), language))
                continue
            routes.append(
                (
                    build_codex_url(
                        {
                            "lang": language,
                            "view": "entry",
                            "kind": first_text(entry.get("kind")),
                            "slug": first_text(entry.get("slug")),
                        }
                    ),
                    language,
                )
            )

    unique_routes = unique(route for route, _language in routes)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for route in unique_routes:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{xml_escape(route)}</loc>",
                f"    <lastmod>{xml_escape(generated_at)}</lastmod>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def write_sitemap(path: Path, manifest: Dict, entries: List[Dict]) -> None:
    path.write_text(build_sitemap_xml(manifest, entries), encoding="utf-8")


def slugify(value: object) -> str:
    text = repair_mojibake(str(value or "")).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = text.replace("_", "-")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "entry"


def unique(values: Iterable[object]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def list_count(values: Iterable[object]) -> int:
    return sum(1 for _ in values)


def pluralize(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def first_text(*values: object) -> str:
    for value in values:
        text = repair_mojibake(str(value or "")).strip()
        if text:
            return text
    return ""


def title_case_stem(value: object) -> str:
    parts = [part for part in re.split(r"[_\-\s]+", first_text(value)) if part]
    return "_".join(part[:1].upper() + part[1:] for part in parts)


def normalize_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", first_text(value).lower())


def normalize_search_text(value: object) -> str:
    text = repair_mojibake(str(value or "")).lower()
    text = "".join(char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_engraving_item(row: Dict, name_en: str, name_fr: str) -> bool:
    item_id = first_text(row.get("Name"), row.get("String_Tid"))
    if item_id in ENGRAVING_ITEM_IDS:
        return True
    normalized = " ".join(
        [
            normalize_token(name_en),
            normalize_token(name_fr),
            normalize_token(first_text(row.get("Local_Key"), row.get("IconName"))),
        ]
    )
    return "resolutionfragment" in normalized or "engrav" in normalized


def humanize_token(value: object) -> str:
    text = first_text(value)
    if not text:
        return ""
    spaced = text.replace("_", " ").replace("-", " ")
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", spaced)
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", spaced)
    spaced = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", spaced)
    lowered = spaced.lower()
    replacements = [
        ("airavoidanceskill", "air avoidance skill"),
        ("justavoidanceskill", "perfect avoidance skill"),
        ("avoidanceskill", "avoidance skill"),
        ("jumpatk", "jump attack"),
        ("airatk", "air attack"),
        ("sworddual", "dual swords"),
        ("sword2h", "greatsword"),
        ("sword1h", "longsword"),
        ("weaponpassive", "weapon passive"),
        ("passiveskill", "passive skill"),
    ]
    for source, target in replacements:
        lowered = lowered.replace(source, target)
    return re.sub(r"\s+", " ", lowered).strip().title()


def short_summary(value: object, fallback: str = "") -> str:
    text = first_text(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return fallback
    first_line = next((line.strip() for line in text.split("\n") if line.strip()), "")
    if not first_line:
        return fallback
    sentence_match = re.match(r"^(.+?[.!?])(?:\s|$)", first_line)
    if sentence_match:
        return sentence_match.group(1).strip()
    return first_line[:180].strip()


def prefer_slot_skill_name(skill_key: str, localized_name: str) -> bool:
    normalized_skill = normalize_token(skill_key)
    normalized_name = normalize_token(localized_name)
    if not normalized_skill:
        return False
    technical_markers = [
        "avoidanceskill",
        "airavoidanceskill",
        "justavoidanceskill",
        "jumpatk",
        "airatk",
    ]
    return normalized_skill == normalized_name and any(marker in normalized_skill for marker in technical_markers)


def compact_title_stem(value: object) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\-\s]+", first_text(value)) if part)


def localize_value(localizer: "Localizer", value: object) -> Dict[str, str]:
    raw = first_text(value)
    en = first_text(localizer.translate(value, "en"), raw)
    fr = first_text(localizer.translate(value, "fr"), en, raw)
    return {"en": en, "fr": fr}


def localized_text(en: object, fr: object = "") -> Dict[str, str]:
    resolved_en = first_text(en)
    resolved_fr = first_text(fr, resolved_en)
    return {"en": resolved_en, "fr": resolved_fr}


def localized_enum(value: object, mapping: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    labels = mapping.get(normalize_token(value))
    if labels:
        return labels
    human = humanize_token(value)
    return {"en": human, "fr": human}


def parse_placeholder_map(replacements: object) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if isinstance(replacements, str):
        replacements = [replacements]
    if not isinstance(replacements, list):
        return mapping
    for raw in replacements:
        match = PLACEHOLDER_VALUE_PATTERN.match(first_text(raw))
        if not match:
            continue
        resolved = repair_mojibake(match.group(2)).replace("\xa0", " ").strip()
        if resolved.startswith("{") and resolved.endswith("}"):
            resolved = resolved[1:-1].strip()
        mapping[match.group(1)] = resolved
    return mapping


def format_game_text(value: object, replacements: object = None) -> str:
    text = repair_mojibake(str(value or ""))
    if not text:
        return ""
    text = FORMAT_TAG_PATTERN.sub("", text)
    placeholder_map = parse_placeholder_map(replacements)
    text = PLACEHOLDER_PATTERN.sub(lambda match: placeholder_map.get(match.group(1), match.group(0)), text)
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def flatten_search_terms(value: object) -> List[str]:
    if isinstance(value, dict):
        terms: List[str] = []
        for nested in value.values():
            terms.extend(flatten_search_terms(nested))
        return terms
    if isinstance(value, list):
        terms: List[str] = []
        for nested in value:
            terms.extend(flatten_search_terms(nested))
        return terms
    text = first_text(value)
    return [text] if text else []


def numeric_value(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def pet_icon_stems(*values: object) -> List[str]:
    stems: List[str] = []
    for raw in values:
        stem = first_text(raw)
        if not stem:
            continue
        stems.append(stem)
        lowered = stem.lower()
        if lowered.startswith("portrait_pet_hud_"):
            stems.append("Hud_PET_" + stem[len("portrait_pet_hud_") :])
        if lowered.startswith("portrait_pet_list_"):
            stems.append("Hud_PET_" + stem[len("portrait_pet_list_") :])
    return unique(stems)


def item_icon_stems(*values: object) -> List[str]:
    stems: List[str] = []
    for raw in values:
        stem = Path(first_text(raw)).stem
        if not stem:
            continue
        stems.extend([stem, stem.lower(), title_case_stem(stem)])
        lowered = stem.lower()
        trimmed = stem[5:] if lowered.startswith("icon_") else stem
        trimmed_parts = [part for part in trimmed.split("_") if part]
        stems.extend([trimmed, trimmed.lower(), title_case_stem(trimmed)])
        for index in range(1, min(len(trimmed_parts), 4)):
            tail = "_".join(trimmed_parts[index:])
            if tail:
                stems.extend([tail, tail.lower(), title_case_stem(tail)])
    return unique(stems)


def hero_portrait_stems(*values: object) -> List[str]:
    actor_key = first_text(*values)
    if not actor_key:
        return []
    compact = compact_title_stem(actor_key)
    return unique(
        [
            actor_key,
            compact,
            f"Dictionary_PC_{compact}_0001",
            f"Dictionary_PC_{compact}",
            f"Portrait_{compact}",
            f"icon_{compact}_001",
        ]
    )


def costume_image_stems(*values: object) -> List[str]:
    stems: List[str] = []
    for raw in values:
        stem = Path(first_text(raw)).stem
        if not stem:
            continue
        stems.extend([stem, stem.lower(), title_case_stem(stem)])
        lowered = stem.lower()
        costume_match = re.match(r"^([a-z0-9_]+)_costume_(\d{3})$", lowered)
        if costume_match:
            actor_name, variant = costume_match.groups()
            actor_label = compact_title_stem(actor_name)
            stems.extend(
                [
                    f"Costume_{actor_label}_{variant}",
                    f"Dictionary_Special_Costume_{actor_label}_{variant}",
                ]
            )
            continue
        if re.match(r"^([a-z0-9]+)$", lowered):
            actor_label = compact_title_stem(lowered)
            stems.extend(
                [
                    f"Costume_{actor_label}_001",
                    f"Dictionary_Special_Costume_{actor_label}_001",
                ]
            )
    return unique(stems)


def monster_icon_stems(actor_tid: object) -> List[str]:
    actor_key = first_text(actor_tid)
    if not actor_key:
        return []
    candidates = []
    pending = [actor_key]
    seen = set()
    while pending:
        current = first_text(pending.pop(0))
        if not current or current in seen:
            continue
        seen.add(current)
        candidates.append(current)
        candidates.extend(creature_visual_overrides(current))
        lowered = current.lower()
        if lowered.startswith("mon_"):
            suffix = current[4:]
            normalized = title_case_stem(suffix)
            candidates.extend(
                [
                    f"Dictionary_MON_{normalized}",
                    normalized,
                    f"Item_{normalized}_new",
                ]
            )
            fallback_suffix = re.sub(r"_(?:\d{4})$", "_0001", suffix, flags=re.IGNORECASE)
            if fallback_suffix != suffix:
                fallback_normalized = title_case_stem(fallback_suffix)
                candidates.extend(
                    [
                        f"Dictionary_MON_{fallback_normalized}",
                        fallback_normalized,
                        f"Item_{fallback_normalized}_new",
                    ]
                )
        elif lowered.startswith("boss_"):
            suffix = current[5:]
            suffix_no_index = re.sub(r"_\d+$", "", suffix)
            suffix_title = title_case_stem(suffix)
            suffix_title_no_index = title_case_stem(suffix_no_index)
            map_index_match = re.search(r"_(\d{4})$", suffix)
            map_index = map_index_match.group(1)[-3:] if map_index_match else "001"
            candidates.extend(
                [
                    f"Dictionary_Boss_{suffix_title}",
                    f"Dictionary_MON_Boss_{suffix_title}",
                    f"Dictionary_MON_{suffix_title}",
                    f"Map_Icon_{suffix_title_no_index}_{map_index}",
                    f"T_Boss_{suffix_title_no_index}",
                ]
            )
        stripped = re.sub(
            r"_(?:quest|test|dead|trap|fake|small|large|statue|social(?:_\d+)?|scale\d+|ember_crystal|violet_crystal|cyan_crystal|abysspiece|phase(?:_\d+)?)$",
            "",
            current,
            flags=re.IGNORECASE,
        )
        if stripped != current:
            pending.append(stripped)
    return unique(candidates)


CREATURE_VISUAL_OVERRIDE_MAP = {
    "mon_howzer_0001": ["Dictionary_PC_Howzer_0001", "hud_howzer_001"],
    "mon_tioreh_0011": ["Dictionary_PC_Tioreh_0001", "hud_tioreh_001", "Dictionary_MON_Mud_Tioreh_0001"],
    "mon_guila_0001": ["Dictionary_MON_Guila_Demon_0001", "Dictionary_PC_Guila_0001", "hud_guila_001"],
    "mon_bug_0001_axe": ["Dictionary_PC_Bug_0001", "hud_bug_001"],
    "mon_orlian_jar_seal_0001": ["Dictionary_MON_Orlian_Demon_0001", "Map_Icon_Orlian_Demon_001"],
    "boss_longdead_0001_phase_2": ["Dictionary_MON_Boss_Longdead_0001"],
    "elite callus": ["Dictionary_MON_Draco_Berserker_0001", "Map_Icon_Draco_Berserker_001"],
    "callus d'elite": ["Dictionary_MON_Draco_Berserker_0001", "Map_Icon_Draco_Berserker_001"],
}


def creature_visual_overrides(*values: object) -> List[str]:
    stems: List[str] = []
    for raw in values:
        for token in flatten_search_terms(raw):
            key = first_text(token).strip().lower()
            if key:
                stems.extend(CREATURE_VISUAL_OVERRIDE_MAP.get(key, []))
    return unique(stems)


def dictionary_visual_stems(*values: object) -> List[str]:
    stems: List[str] = []
    for raw in values:
        for token in flatten_search_terms(raw):
            stem = Path(first_text(token)).stem
            if not stem:
                continue
            stems.extend([stem, stem.lower(), title_case_stem(stem)])
            lowered = stem.lower()
            if lowered.startswith("icon_monster_"):
                stems.append(f"Dictionary_MON_{title_case_stem(stem[len('icon_monster_'):])}")
            elif lowered.startswith("icon_herodictionary_"):
                suffix = stem[len("icon_herodictionary_") :]
                stems.extend(
                    [
                        f"Dictionary_PC_{compact_title_stem(suffix)}_0001",
                        f"hud_{suffix}_001",
                    ]
                )
            elif lowered.startswith("local_mon_name_"):
                stems.append(f"Dictionary_MON_{title_case_stem(stem[len('local_mon_name_'):])}")
    return unique(stems)


def build_monster_dictionary_indexes(dictionary_rows: List[Dict]) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    by_local_key: Dict[str, List[Dict]] = defaultdict(list)
    by_actor_id: Dict[str, List[Dict]] = defaultdict(list)
    for row in dictionary_rows:
        if not isinstance(row, dict):
            continue
        local_key = first_text(row.get("Local_Key"))
        if local_key:
            by_local_key[local_key].append(row)
        actor_id = first_text(row.get("ModelView_ActorTid"))
        if actor_id:
            by_actor_id[actor_id].append(row)
    return by_local_key, by_actor_id


def monster_visual_candidates(
    row: Dict,
    dictionary_by_local_key: Dict[str, List[Dict]],
    dictionary_by_actor_id: Dict[str, List[Dict]],
) -> List[str]:
    actor_tid = row.get("ActorTid") if isinstance(row.get("ActorTid"), dict) else {"string_tid": row.get("ActorTid")}
    actor_key = first_text(actor_tid.get("string_tid"))
    candidates = []
    portrait = first_text(row.get("UI_HUD_Portrait"))
    if portrait and portrait not in GENERIC_MONSTER_PORTRAITS:
        candidates.append(portrait)
    candidates.extend(flatten_search_terms(row.get("UI_Actor_Icon_Headup_Center")))
    for key in monster_icon_stems(actor_key):
        candidates.append(key)
    normalized_actor_keys = unique(
        [
            normalize_creature_actor_tid(actor_key),
            normalize_creature_actor_tid(row.get("ActorAniKeyGroup")),
            normalize_creature_actor_tid(row.get("ActorModelTid_Root")),
        ]
    )
    for normalized_key in normalized_actor_keys:
        candidates.extend(monster_icon_stems(normalized_key))
    local_key = first_text(row.get("Local_Key"))
    local_mon_key = first_text(row.get("Local_Mon_Name"), row.get("Local_Mon_Name_Key"))
    candidates.extend(dictionary_visual_stems(local_mon_key))
    for dictionary_row in dictionary_by_local_key.get(local_key, []):
        candidates.extend([dictionary_row.get("Img"), dictionary_row.get("List_Icon")])
        candidates.extend(dictionary_visual_stems(dictionary_row.get("Img"), dictionary_row.get("List_Icon")))
    for dictionary_row in dictionary_by_local_key.get(local_mon_key, []):
        candidates.extend([dictionary_row.get("Img"), dictionary_row.get("List_Icon")])
        candidates.extend(dictionary_visual_stems(dictionary_row.get("Img"), dictionary_row.get("List_Icon"), dictionary_row.get("Local_Key")))
    actor_ids = [first_text(row.get("Name"))]
    for actor_id in actor_ids:
        for dictionary_row in dictionary_by_actor_id.get(actor_id, []):
            candidates.extend([dictionary_row.get("Img"), dictionary_row.get("List_Icon")])
            candidates.extend(dictionary_visual_stems(dictionary_row.get("Img"), dictionary_row.get("List_Icon"), dictionary_row.get("Local_Key")))
    return unique(candidates)


def creature_actor_tid(row: Dict) -> str:
    if not isinstance(row, dict):
        return ""
    actor_tid = row.get("ActorTid") if isinstance(row.get("ActorTid"), dict) else {"string_tid": row.get("ActorTid")}
    return first_text(actor_tid.get("string_tid"))


def is_placeholder_creature_name(value: object) -> bool:
    text = first_text(value)
    if not text:
        return True
    compact = re.sub(r"\s+", "", text)
    return bool(re.fullmatch(r"[?？！!.\-_<>()]+", compact))


def creature_name_fallback(actor_tid: object, default: str = "Creature") -> str:
    actor_key = first_text(actor_tid)
    if not actor_key:
        return default
    cleaned = actor_key
    cleaned = re.sub(r"^(?:mon_|boss_|ap_pet_|pet_|sum_|obj_)", "", cleaned, flags=re.IGNORECASE)
    cleaned = BOSS_PHASE_SUFFIX_RE.sub("", cleaned)
    cleaned = CREATURE_VARIANT_SUFFIX_RE.sub("", cleaned)
    cleaned = re.sub(r"_\d+$", "", cleaned)
    label = humanize_token(cleaned)
    return first_text(label, default)


def creature_local_key(row: Dict) -> str:
    return first_text(row.get("Local_Key"))


def creature_has_public_local_key(row: Dict, localizer: Localizer) -> bool:
    local_key = creature_local_key(row)
    if not local_key or local_key.lower() in UNUSABLE_CREATURE_LOCAL_KEYS:
        return False
    translated = first_text(localizer.translate(local_key, "en"))
    return bool(
        translated
        and not is_placeholder_creature_name(translated)
        and not any(hint in translated.lower() for hint in TECHNICAL_CREATURE_NAME_HINTS)
    )


def creature_editor_show_name(row: Dict) -> str:
    return repair_mojibake(first_text(row.get("EditorShowName"))).strip()


def creature_root_actor_tid(row: Dict) -> str:
    if not isinstance(row, dict):
        return ""
    actor_tid = row.get("ActorTid") if isinstance(row.get("ActorTid"), dict) else {}
    return first_text(actor_tid.get("ActorModelTid_Root"), actor_tid.get("string_tid"), row.get("ActorTid"))


def cleaned_field_boss_label(point: Dict) -> str:
    label = first_text(point.get("label"))
    if not label:
        return ""
    cleaned = FIELD_BOSS_LABEL_PREFIX_RE.sub("", label).strip()
    return first_text(cleaned, label)


def field_boss_point_names(point: Dict) -> Tuple[str, str]:
    label = cleaned_field_boss_label(point)
    if not label:
        return "", ""
    override = FIELD_BOSS_LABEL_OVERRIDES.get(label.lower())
    if override:
        return first_text(override.get("en"), label), first_text(override.get("fr"), override.get("en"), label)
    if label.lower().startswith("elite "):
        return label, f"{label[6:]} d'elite"
    return label, label


def localized_creature_names(row: Dict, localizer: Localizer) -> Tuple[str, str]:
    local_key = creature_local_key(row)
    actor_tid = creature_actor_tid(row)
    fallback_actor = creature_name_fallback(actor_tid, first_text(row.get("Name"), "Creature"))
    name_en = ""
    name_fr = ""
    if creature_has_public_local_key(row, localizer):
        name_en = first_text(localizer.translate(local_key, "en"))
        name_fr = first_text(localizer.translate(local_key, "fr"))
    if is_placeholder_creature_name(name_en) or any(hint in name_en.lower() for hint in TECHNICAL_CREATURE_NAME_HINTS):
        name_en = fallback_actor
    if is_placeholder_creature_name(name_fr) or any(hint in name_fr.lower() for hint in TECHNICAL_CREATURE_NAME_HINTS):
        name_fr = name_en
    return name_en, name_fr


def localized_creature_descriptions(row: Dict, localizer: Localizer) -> Tuple[str, str]:
    desc_en = first_text(localizer.translate(row.get("Local_Desc"), "en"))
    desc_fr = first_text(localizer.translate(row.get("Local_Desc"), "fr"), desc_en)
    return desc_en, desc_fr


def normalize_creature_actor_tid(actor_tid: object, *, boss: bool = False) -> str:
    actor_key = first_text(actor_tid).lower()
    if not actor_key:
        return ""
    normalized = BOSS_PHASE_SUFFIX_RE.sub("", actor_key)
    normalized = CREATURE_VARIANT_SUFFIX_RE.sub("", normalized)
    normalized = re.sub(r"_\d{4}$", "", normalized)
    if boss:
        normalized = re.sub(r"_(?:sleep|phase|state)_?\d*$", "", normalized, flags=re.IGNORECASE)
    return normalized


def creature_group_key(row: Dict, localizer: Localizer, *, boss: bool = False) -> str:
    local_key = creature_local_key(row).lower()
    if creature_has_public_local_key(row, localizer):
        return f"local:{local_key}"
    actor_key = normalize_creature_actor_tid(creature_root_actor_tid(row), boss=boss)
    if actor_key:
        return actor_key
    if local_key:
        return local_key
    return first_text(row.get("Name")).lower()


def is_technical_creature_row(row: Dict, localizer: Localizer) -> bool:
    monster_id = first_text(row.get("Name"))
    actor_key = creature_actor_tid(row).lower()
    editor_name = creature_editor_show_name(row).lower()
    name_en, name_fr = localized_creature_names(row, localizer)
    if monster_id in TECHNICAL_CREATURE_MONSTER_IDS:
        return True
    if actor_key in TECHNICAL_CREATURE_ACTOR_IDS:
        return True
    if actor_key.startswith(TECHNICAL_CREATURE_ACTOR_PREFIXES):
        return True
    if any(pattern in actor_key for pattern in TECHNICAL_CREATURE_ACTOR_PATTERNS):
        return True
    if any(hint in name_en.lower() or hint in name_fr.lower() or hint in editor_name for hint in TECHNICAL_CREATURE_NAME_HINTS):
        return True
    if is_placeholder_creature_name(name_en) and any(token in actor_key for token in ("invisible", "rock", "cocoon", "crystal")):
        return True
    if not creature_has_public_local_key(row, localizer) and not actor_key:
        return True
    return False


def choose_best_creature_row(rows: List[Dict], localizer: Localizer) -> Optional[Dict]:
    best_row = None
    best_score = -1
    for row in rows:
        if not isinstance(row, dict):
            continue
        name_en, name_fr = localized_creature_names(row, localizer)
        score = 0
        if not is_placeholder_creature_name(name_en):
            score += 8
        if not is_placeholder_creature_name(name_fr):
            score += 4
        if creature_has_public_local_key(row, localizer):
            score += 4
        if first_text(row.get("Local_Desc")):
            score += 2
        if first_text(row.get("DropGroupTid")) or first_text(row.get("FirstDropGroupTid")) or first_text(row.get("CatchDropGroupTid")):
            score += 2
        portrait = first_text(row.get("UI_HUD_Portrait"))
        if portrait and portrait not in GENERIC_MONSTER_PORTRAITS:
            score += 2
        actor_key = creature_actor_tid(row).lower()
        if actor_key.startswith("boss_"):
            score += 2
        if is_technical_creature_row(row, localizer):
            score -= 10
        if score > best_score:
            best_score = score
            best_row = row
    return best_row


def dedupe_acquisition_sources(rows: List[Dict]) -> List[Dict]:
    deduped = []
    seen = set()
    for row in rows:
        key = (
            first_text(row.get("kind")),
            first_text(row.get("relatedEntryId"), row.get("sourceId")),
            first_text(row.get("sourceGroupId")),
            first_text(row.get("standardLevel")),
            first_text(row.get("dropSourceType")),
            int(numeric_value(row.get("minCount")) or 0),
            int(numeric_value(row.get("maxCount")) or 0),
            int(numeric_value(row.get("rateRaw")) or 0),
            int(numeric_value(row.get("rateWeightTotal")) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    merged_monsters: Dict[Tuple, Dict] = {}
    ordered: List[Dict] = []

    def visual_monster_key(payload: Dict) -> Tuple:
        return (
            first_text(payload.get("kind")),
            normalize_token(payload.get("name", {}).get("en")),
            normalize_token(payload.get("name", {}).get("fr")),
            first_text(payload.get("standardLevel")),
            first_text(payload.get("dropSourceType")),
            normalize_token(payload.get("grade", {}).get("en")),
            normalize_token(payload.get("grade", {}).get("fr")),
        )

    def row_score(payload: Dict) -> Tuple:
        return (
            numeric_value(payload.get("rateDisplayPct")),
            int(numeric_value(payload.get("rateRaw")) or 0),
            int(numeric_value(payload.get("qualityMax")) or 0),
            int(numeric_value(payload.get("maxCount")) or 0),
            int(numeric_value(payload.get("recommendedPower")) or 0),
            0 if first_text(payload.get("relatedEntryId")).startswith("boss:") else 1,
        )

    for row in deduped:
        if first_text(row.get("kind")) != "monster":
            ordered.append(row)
            continue
        key = visual_monster_key(row)
        existing = merged_monsters.get(key)
        if not existing or row_score(row) > row_score(existing):
            merged_monsters[key] = row

    return ordered + list(merged_monsters.values())


def boss_match_tokens(*values: object) -> List[str]:
    text = " ".join(first_text(value) for value in values if first_text(value))
    if not text:
        return []
    text = repair_mojibake(text)
    text = re.sub(r"darkevilf", "darkevil f", text, flags=re.IGNORECASE)
    text = re.sub(r"darkevilarcher", "darkevil archer", text, flags=re.IGNORECASE)
    text = re.sub(r"graydemon", "gray demon", text, flags=re.IGNORECASE)
    text = re.sub(r"reddemon", "red demon", text, flags=re.IGNORECASE)
    text = re.sub(r"fairycurse", "fairy curse", text, flags=re.IGNORECASE)
    text = re.sub(r"mossdemon", "moss demon", text, flags=re.IGNORECASE)
    text = re.sub(r"piratecaptain", "pirate captain", text, flags=re.IGNORECASE)
    text = re.sub(r"sandthief", "sand thief", text, flags=re.IGNORECASE)
    text = re.sub(r"screamerwild", "screamer wild", text, flags=re.IGNORECASE)
    text = re.sub(r"singspirit", "sing spirit", text, flags=re.IGNORECASE)
    text = re.sub(r"dracowarlord", "draco warlord", text, flags=re.IGNORECASE)
    text = re.sub(r"dracowarriorm", "draco warrior", text, flags=re.IGNORECASE)
    text = re.sub(r"dracowarriorf", "draco warrior", text, flags=re.IGNORECASE)
    text = re.sub(r"orliandemon", "orlian demon", text, flags=re.IGNORECASE)
    text = re.sub(r"scolpibeast", "scorpy beast", text, flags=re.IGNORECASE)
    text = re.sub(r"scorpybeast", "scorpy beast", text, flags=re.IGNORECASE)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("RedDemon", "Red Demon")
    text = text.replace("GrayDemon", "Gray Demon")
    text = text.replace("DarkevilArcher", "Darkevil Archer")
    text = text.replace("FairyCurse", "Fairy Curse")
    text = text.replace("MossDemon", "Moss Demon")
    text = text.replace("PirateCaptain", "Pirate Captain")
    text = text.replace("Sandthief", "Sand Thief")
    text = text.replace("ScreamerWild", "Screamer Wild")
    text = text.replace("Singspirit", "Sing Spirit")
    text = text.replace("DracoWarlord", "Draco Warlord")
    text = text.replace("DracoWarriorM", "Draco Warrior")
    text = text.replace("DracoWarriorF", "Draco Warrior")
    text = text.replace("OrlianDemon", "Orlian Demon")
    stop_words = {"world", "boss", "field", "common", "mon", "elite", "of", "the", "local", "name"}
    tokens = []
    for part in re.split(r"[^A-Za-z0-9]+", text):
        lowered = part.lower()
        if not lowered or lowered in stop_words or lowered.isdigit() or re.match(r"^ch?\d+[a-z]*$", lowered):
            continue
        tokens.append(lowered)
        if lowered == "warlord":
            tokens.append("warrior")
    return unique(tokens)


def match_boss_monster_row(point: Dict, monster_rows: List[Dict], localizer: Localizer) -> Optional[Dict]:
    point_tokens = set(boss_match_tokens(point.get("name"), point.get("label")))
    if not point_tokens:
        return None
    minimum_hits = 2 if len(point_tokens) > 1 else 1
    wants_elite = "elite" in first_text(point.get("name"), point.get("label")).lower()
    wants_boss = "boss" in first_text(point.get("name"), point.get("label")).lower()
    best_score = -1
    best_row = None
    for row in monster_rows:
        if not isinstance(row, dict):
            continue
        if is_technical_creature_row(row, localizer):
            continue
        actor_tid = row.get("ActorTid") if isinstance(row.get("ActorTid"), dict) else {"string_tid": row.get("ActorTid")}
        name_en, _ = localized_creature_names(row, localizer)
        row_tokens = set(
            boss_match_tokens(
                row.get("Local_Key"),
                name_en,
                row.get("NPC_Job"),
                actor_tid.get("string_tid"),
            )
        )
        specific_hits = point_tokens & row_tokens
        if len(specific_hits) < minimum_hits:
            continue
        score = len(specific_hits) * 12
        grade = normalize_grade(row.get("Grade"))
        if wants_elite and grade == "elite":
            score += 4
        if wants_boss and grade == "boss":
            score += 4
        portrait = first_text(row.get("UI_HUD_Portrait"))
        if portrait and portrait not in GENERIC_MONSTER_PORTRAITS:
            score += 2
        if point_tokens.issubset(row_tokens):
            score += len(point_tokens) * 2
        if score > best_score:
            best_score = score
            best_row = row
    threshold = 24 if len(point_tokens) > 1 else 18
    return best_row if best_score >= threshold else None


def quest_icon_stems(quest_type: str, quest_id: str) -> List[str]:
    candidates = []
    if quest_type == "main":
        candidates.extend([f"main-quest-start-{quest_id}", "main-quest", "i_quest_1_non"])
    elif quest_type == "side":
        candidates.extend([f"side-quest-start-{quest_id}", "side-quest", "i_quest_side_non"])
    elif quest_type == "hidden":
        candidates.extend([f"hidden-quest-start-{quest_id}", "hidden-quest", "i_quest_hidden_non", "Quest_Hide"])
    elif quest_type == "stella":
        candidates.extend([f"stella-quest-start-{quest_id}", "i_quest_stella_non", "i_quest_stella"])
    return unique(candidates)


def quest_image_stems(quest_id: str) -> List[str]:
    return [f"QuestReplay_DirectingImage_{quest_id}_1", f"QuestReplay_DirectingImage_{quest_id}_2"]


def extract_quest_id(*values: object) -> str:
    for value in values:
        match = QUEST_ID_PATTERN.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


def quest_marker_stage(point: Dict) -> str:
    text = " ".join(
        str(point.get(key) or "")
        for key in ["name", "label", "description"]
    ).lower()
    if "start" in text:
        return "start"
    if "progress" in text:
        return "progress"
    if "end" in text or "clear" in text:
        return "end"
    return "marker"


def normalize_grade(value: object) -> str:
    return str(value or "").strip().lower()


def is_truthy_flag(value: object) -> bool:
    token = first_text(value).strip().lower()
    if token in {"true", "1", "yes"}:
        return True
    if token in {"false", "0", "no", ""}:
        return False
    return bool(numeric_value(value))


def normalize_disassemble_key(value: object) -> str:
    return first_text(value).strip().lower()


def rarity_payload(grade: object, fallback_hex: str = "") -> Optional[Dict[str, object]]:
    key = normalize_grade(grade)
    mapping = {
        "grade1": {"rank": 1, "label": {"en": "Common", "fr": "Commun"}, "hex": "#8892a0"},
        "grade2": {"rank": 2, "label": {"en": "Uncommon", "fr": "Peu commun"}, "hex": "#48c774"},
        "grade3": {"rank": 3, "label": {"en": "Rare", "fr": "Rare"}, "hex": "#4a8dff"},
        "grade4": {"rank": 4, "label": {"en": "Epic", "fr": "\u00c9pique"}, "hex": "#b06cff"},
        "grade5": {"rank": 5, "label": {"en": "Legendary", "fr": "L\u00e9gendaire"}, "hex": "#f4c542"},
    }
    if key not in mapping:
        return None
    payload = dict(mapping[key])
    payload["grade"] = key
    if fallback_hex:
        payload["hex"] = fallback_hex
    return payload


def format_ability_value(ability_key: object, value: object) -> str:
    token = normalize_token(ability_key)
    number = numeric_value(value)
    if abs(number - round(number)) < 1e-6:
        base = str(int(round(number)))
    else:
        base = f"{number:.2f}".rstrip("0").rstrip(".")
    if "rate" in token:
        scaled = number / 100.0
        if abs(scaled - round(scaled)) < 1e-6:
            base = str(int(round(scaled)))
        else:
            base = f"{scaled:.2f}".rstrip("0").rstrip(".")
        return f"+{base}%"
    if number > 0:
        return f"+{base}"
    return base


def build_ability_payload(
    ability_type: object,
    ability_value: object,
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    ability_id = first_text(ability_type)
    if not ability_id:
        return None
    stat_info = stat_info_by_id.get(normalize_token(ability_id), {})
    label_en = first_text(localizer.translate(stat_info.get("Local_key"), "en"), humanize_token(ability_id))
    label_fr = first_text(localizer.translate(stat_info.get("Local_key"), "fr"), label_en)
    return {
        "id": ability_id,
        "label": {"en": label_en, "fr": label_fr},
        "value": {
            "en": format_ability_value(ability_id, ability_value),
            "fr": format_ability_value(ability_id, ability_value),
        },
        "icon": assets.resolve_stem([stat_info.get("Icon")], "mastery"),
    }


def build_item_link_payload(
    item_id: object,
    count: object,
    localizer: Localizer,
    assets: AssetResolver,
    *,
    bucket: str = "items",
) -> Optional[Dict]:
    resolved_id = first_text(item_id)
    if not resolved_id:
        return None
    item_row = localizer.item_row(resolved_id) or {}
    return {
        "itemId": resolved_id,
        "count": int(numeric_value(count) or 0),
        "name": {
            "en": first_text(localizer.item_name(resolved_id, "en"), resolved_id),
            "fr": first_text(localizer.item_name(resolved_id, "fr"), localizer.item_name(resolved_id, "en"), resolved_id),
        },
        "description": {
            "en": localizer.item_desc(resolved_id, "en"),
            "fr": localizer.item_desc(resolved_id, "fr"),
        },
        "icon": assets.resolve_stem(item_icon_candidates(localizer, item_row, resolved_id), bucket),
        "rarity": rarity_payload(item_row.get("Grade")),
        "classification": first_text(item_row.get("ItemDetailType"), item_row.get("ItemDivision"), item_row.get("ItemType")),
    }


def item_icon_candidates(localizer: Localizer, item_row: Dict, item_id: object) -> List[str]:
    icon_name = first_text(item_row.get("IconName"))
    return unique(
        item_icon_stems(icon_name, item_id)
        + localizer.view_image_candidates(icon_name)
        + localizer.avatar_icon_candidates(item_id)
    )


def build_disassembly_level_index(disassemble_level_rows: List[Dict]) -> Dict[str, Dict]:
    curves: Dict[str, Dict] = {}
    for row in disassemble_level_rows:
        if not isinstance(row, dict):
            continue
        curve_id = normalize_disassemble_key(row.get("Name"))
        if not curve_id:
            continue
        values = [
            numeric_value(row.get(f"LV{level}"))
            for level in range(0, 101)
            if row.get(f"LV{level}") not in {None, ""}
        ]
        if not values:
            continue
        curves[curve_id] = {
            "id": first_text(row.get("Name")),
            "levelMin": 0,
            "levelMax": 100,
            "multiplierMin": round(min(values), 4),
            "multiplierMax": round(max(values), 4),
            "multiplierStart": round(numeric_value(row.get("LV0")) or min(values), 4),
            "multiplierEnd": round(numeric_value(row.get("LV100")) or max(values), 4),
        }
    return curves


def build_stat_info_index(stat_info_rows: List[Dict]) -> Dict[str, Dict]:
    return {
        normalize_token(row.get("Name")): row
        for row in stat_info_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }


def item_family_label(value: object, lang: str) -> str:
    key = normalize_token(value)
    if key in ITEM_FAMILY_LABELS:
        return ITEM_FAMILY_LABELS[key][lang]
    return humanize_token(value)


def build_growth_effect_payload(
    effect_id: object,
    slot_type: str,
    option_static_by_name: Dict[str, Dict],
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    row = option_static_by_name.get(first_text(effect_id))
    if not row:
        return None
    payload = build_ability_payload(row.get("AbilityType"), row.get("Value_Base"), stat_info_by_id, localizer, assets)
    if not payload:
        return None
    growth_steps = [
        format_ability_value(row.get("AbilityType"), row.get(f"Value_Add_{index}"))
        for index in range(1, 11)
        if numeric_value(row.get(f"Value_Add_{index}"))
    ]
    payload.update(
        {
            "slotType": slot_type,
            "growthType": first_text(row.get("GrowthType")),
            "growthSteps": growth_steps,
            "growthSummary": {
                "en": " / ".join(growth_steps),
                "fr": " / ".join(growth_steps),
            },
        }
    )
    return payload


def build_option_pool_rows(
    group_id: str,
    option_list_by_group: Dict[str, List[Dict]],
    option_random_by_group: Dict[str, List[Dict]],
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> List[Dict]:
    normalized = normalize_token(group_id)
    rows = option_random_by_group.get(normalized) or option_list_by_group.get(normalized) or []
    total_weight = sum(int(numeric_value(row.get("OptionRate")) or 0) for row in rows)
    grouped_payloads: Dict[str, Dict] = {}
    for row in rows:
        effect = build_ability_payload(row.get("AbilityType"), row.get("Value_Min"), stat_info_by_id, localizer, assets)
        if not effect:
            continue
        value_min = numeric_value(row.get("Value_Min"))
        value_max = numeric_value(row.get("Value_Max")) or value_min
        option_rate = int(numeric_value(row.get("OptionRate")) or 0)
        payload = grouped_payloads.get(effect["id"])
        if not payload:
            payload = {
                "id": first_text(row.get("Name"), effect["id"], group_id),
                "groupId": first_text(row.get("Group_ID"), group_id),
                "label": effect["label"],
                "icon": effect["icon"],
                "abilityId": effect["id"],
                "valueMin": value_min,
                "valueMax": value_max,
                "stepCount": int(numeric_value(row.get("Step_Count")) or 0),
                "stepValue": {
                    "en": format_ability_value(row.get("AbilityType"), row.get("Step_Value")) if numeric_value(row.get("Step_Value")) else "",
                    "fr": format_ability_value(row.get("AbilityType"), row.get("Step_Value")) if numeric_value(row.get("Step_Value")) else "",
                },
                "optionRatePct": 0,
                "tierMin": int(numeric_value(row.get("Tier")) or 0),
                "tierMax": int(numeric_value(row.get("Tier")) or 0),
                "tiers": [],
                "overlap": is_truthy_flag(row.get("Overlap")),
            }
            grouped_payloads[effect["id"]] = payload
        payload["valueMin"] = min(float(payload.get("valueMin") or value_min), value_min)
        payload["valueMax"] = max(float(payload.get("valueMax") or value_max), value_max)
        payload["optionRatePct"] = round(float(payload.get("optionRatePct") or 0) + ((option_rate / total_weight) * 100 if total_weight > 0 and option_rate > 0 else 0), 2)
        payload["tierMin"] = min(int(payload.get("tierMin") or 0), int(numeric_value(row.get("Tier")) or 0))
        payload["tierMax"] = max(int(payload.get("tierMax") or 0), int(numeric_value(row.get("Tier")) or 0))
        payload["tiers"].append(
            {
                "tier": int(numeric_value(row.get("Tier")) or 0),
                "chancePct": round((option_rate / total_weight) * 100, 2) if total_weight > 0 and option_rate > 0 else 0,
                "range": {
                    "en": effect["value"]["en"]
                    if abs(value_min - value_max) < 1e-6
                    else f"{format_ability_value(row.get('AbilityType'), value_min)} to {format_ability_value(row.get('AbilityType'), value_max)}",
                    "fr": effect["value"]["fr"]
                    if abs(value_min - value_max) < 1e-6
                    else f"{format_ability_value(row.get('AbilityType'), value_min)} a {format_ability_value(row.get('AbilityType'), value_max)}",
                },
            }
        )

    payloads = list(grouped_payloads.values())
    for payload in payloads:
        value_min = float(payload.get("valueMin") or 0)
        value_max = float(payload.get("valueMax") or 0)
        ability_id = payload.get("abilityId")
        payload["range"] = {
            "en": format_ability_value(ability_id, value_min)
            if abs(value_min - value_max) < 1e-6
            else f"{format_ability_value(ability_id, value_min)} to {format_ability_value(ability_id, value_max)}",
            "fr": format_ability_value(ability_id, value_min)
            if abs(value_min - value_max) < 1e-6
            else f"{format_ability_value(ability_id, value_min)} a {format_ability_value(ability_id, value_max)}",
        }
        payload["tiers"] = sorted(payload.get("tiers") or [], key=lambda item: int(item.get("tier") or 0))
    payloads.sort(key=lambda row: (-float(row.get("optionRatePct") or 0), first_text(row.get("label", {}).get("en"))))
    return payloads


def build_equipment_passive_rows(
    passive_rows: List[Dict],
    passive_base_by_id: Dict[str, Dict],
    passive_group_by_id: Dict[str, List[Dict]],
    localizer: Localizer,
    assets: AssetResolver,
) -> List[Dict]:
    payload_by_id: Dict[str, Dict] = {}
    for passive_row in passive_rows:
        passive_id = first_text(passive_row.get("EquipPassiveID"))
        if not passive_id:
            continue
        base_row = passive_base_by_id.get(normalize_token(passive_id), {})
        group_rows = passive_group_by_id.get(normalize_token(base_row.get("GroupID")), [])
        current_level = int(numeric_value(passive_row.get("PassiveLv")) or 0)
        active_level_row = next((row for row in group_rows if int(numeric_value(row.get("Level")) or 0) == current_level), {})
        description = {
            "en": localizer.format(active_level_row.get("Desc"), "en", active_level_row.get("Local_Replace"))
            or localizer.format(base_row.get("Desc"), "en", base_row.get("Local_Replace")),
            "fr": localizer.format(active_level_row.get("Desc"), "fr", active_level_row.get("Local_Replace"))
            or localizer.format(base_row.get("Desc"), "fr", base_row.get("Local_Replace"))
            or localizer.format(active_level_row.get("Desc"), "en", active_level_row.get("Local_Replace"))
            or localizer.format(base_row.get("Desc"), "en", base_row.get("Local_Replace")),
        }
        payload = payload_by_id.setdefault(
            passive_id,
            {
                "id": passive_id,
                "icon": assets.resolve_stem([base_row.get("Icon"), *localizer.view_image_candidates(base_row.get("Icon"))], "effects"),
                "name": {
                    "en": localizer.format(base_row.get("Core_Name"), "en", base_row.get("Local_Replace")) or humanize_token(passive_id),
                    "fr": localizer.format(base_row.get("Core_Name"), "fr", base_row.get("Local_Replace"))
                    or localizer.format(base_row.get("Core_Name"), "en", base_row.get("Local_Replace"))
                    or humanize_token(passive_id),
                },
                "description": description,
                "grantChancePct": 0,
                "level": 0,
                "maxLevel": int(numeric_value(base_row.get("MaxLv")) or 0),
                "levels": [
                    {
                        "level": int(numeric_value(row.get("Level")) or 0),
                        "description": {
                            "en": localizer.format(row.get("Desc"), "en", row.get("Local_Replace")),
                            "fr": localizer.format(row.get("Desc"), "fr", row.get("Local_Replace"))
                            or localizer.format(row.get("Desc"), "en", row.get("Local_Replace")),
                        },
                    }
                    for row in sorted(group_rows, key=lambda item: int(numeric_value(item.get("Level")) or 0))
                ],
                "rolls": [],
            },
        )
        roll_payload = {
            "level": current_level,
            "grantChancePct": round((numeric_value(passive_row.get("GivePer")) or 0), 2),
            "description": description,
        }
        if not any(
            int(existing.get("level") or 0) == roll_payload["level"]
            and abs(float(existing.get("grantChancePct") or 0) - float(roll_payload["grantChancePct"] or 0)) < 1e-6
            for existing in payload["rolls"]
        ):
            payload["rolls"].append(roll_payload)

    payloads: List[Dict] = []
    for payload in payload_by_id.values():
        payload["rolls"] = sorted(
            payload.get("rolls") or [],
            key=lambda row: (-float(row.get("grantChancePct") or 0), int(row.get("level") or 0)),
        )
        primary_roll = (payload.get("rolls") or [{}])[0]
        payload["grantChancePct"] = round(float(primary_roll.get("grantChancePct") or 0), 2)
        payload["level"] = int(primary_roll.get("level") or 0)
        payload["description"] = primary_roll.get("description") or payload.get("description") or {"en": "", "fr": ""}
        payloads.append(payload)
    payloads.sort(
        key=lambda row: (
            -float(row.get("grantChancePct") or 0),
            first_text((row.get("name") or {}).get("en"), row.get("id")),
        )
    )
    return payloads


def build_equipment_set_payloads(
    set_keys: List[str],
    set_rows_by_id: Dict[str, Dict],
    set_value_rows_by_group: Dict[str, List[Dict]],
    passive_base_by_id: Dict[str, Dict],
    passive_group_by_id: Dict[str, List[Dict]],
    set_members_by_group: Dict[str, List[str]],
    localizer: Localizer,
    assets: AssetResolver,
) -> List[Dict]:
    payloads: List[Dict] = []
    for set_key in unique(set_keys):
        set_row = set_rows_by_id.get(normalize_token(set_key), {})
        if not set_row:
            continue
        group_rows = sorted(
            set_value_rows_by_group.get(normalize_token(set_key), []),
            key=lambda row: (int(numeric_value(row.get("SetPartsCount")) or 0), first_text(row.get("Option_Type")), first_text(row.get("SetOption"))),
        )
        bonuses = []
        for row in group_rows:
            option_type = first_text(row.get("Option_Type")).lower()
            passive_base = passive_base_by_id.get(normalize_token(row.get("SetOption")), {}) if option_type == "passive" else {}
            passive_level = int(numeric_value(row.get("Passive_Lv")) or 0)
            passive_group_rows = passive_group_by_id.get(normalize_token(passive_base.get("GroupID")), [])
            passive_level_row = next((item for item in passive_group_rows if int(numeric_value(item.get("Level")) or 0) == passive_level), {})
            description_en = localizer.format(row.get("Local_Desc"), "en", row.get("Local_Replace"))
            description_fr = localizer.format(row.get("Local_Desc"), "fr", row.get("Local_Replace"))
            bonuses.append(
                {
                    "id": first_text(row.get("Name"), row.get("SetOption")),
                    "partsCount": int(numeric_value(row.get("SetPartsCount")) or 0),
                    "type": option_type or "option",
                    "name": {
                        "en": localizer.format(passive_base.get("Core_Name"), "en", passive_base.get("Local_Replace"))
                        or humanize_token(row.get("SetOption"))
                        or f"{int(numeric_value(row.get('SetPartsCount')) or 0)}-piece bonus",
                        "fr": localizer.format(passive_base.get("Core_Name"), "fr", passive_base.get("Local_Replace"))
                        or localizer.format(passive_base.get("Core_Name"), "en", passive_base.get("Local_Replace"))
                        or humanize_token(row.get("SetOption"))
                        or f"Bonus {int(numeric_value(row.get('SetPartsCount')) or 0)} pieces",
                    },
                    "description": {
                        "en": description_en
                        or localizer.format(passive_level_row.get("Desc"), "en", passive_level_row.get("Local_Replace"))
                        or localizer.format(passive_base.get("Desc"), "en", passive_base.get("Local_Replace")),
                        "fr": description_fr
                        or localizer.format(passive_level_row.get("Desc"), "fr", passive_level_row.get("Local_Replace"))
                        or localizer.format(passive_base.get("Desc"), "fr", passive_base.get("Local_Replace"))
                        or localizer.format(passive_level_row.get("Desc"), "en", passive_level_row.get("Local_Replace"))
                        or localizer.format(passive_base.get("Desc"), "en", passive_base.get("Local_Replace")),
                    },
                    "passiveLevel": passive_level,
                "icon": assets.resolve_stem([passive_base.get("Icon"), set_row.get("SetIcon")], "effects"),
            }
        )
        payloads.append(
            {
                "id": first_text(set_row.get("Name"), set_key),
                "name": {
                    "en": first_text(localizer.translate(set_row.get("SetName"), "en"), humanize_token(set_key), set_key),
                    "fr": first_text(localizer.translate(set_row.get("SetName"), "fr"), localizer.translate(set_row.get("SetName"), "en"), humanize_token(set_key), set_key),
                },
                "icon": assets.resolve_stem([set_row.get("SetIcon"), *localizer.view_image_candidates(set_row.get("SetIcon"))], "effects"),
                "totalParts": int(numeric_value(set_row.get("SetPartsCount")) or 0),
                "bonuses": bonuses,
                "pieceIds": unique(set_members_by_group.get(normalize_token(set_key), [])),
            }
        )
    return payloads


def build_reverse_disassembly_index(
    localizer: Localizer,
    assets: AssetResolver,
    disassemble_rows: List[Dict],
    disassemble_level_rows: List[Dict],
) -> Dict[str, List[Dict]]:
    disassembly_lookup = {
        (normalize_disassemble_key(row.get("Disassemble_Key")), normalize_grade(row.get("Grade"))): row
        for row in disassemble_rows
        if isinstance(row, dict) and normalize_disassemble_key(row.get("Disassemble_Key")) and normalize_grade(row.get("Grade"))
    }
    level_curve_lookup = build_disassembly_level_index(disassemble_level_rows)
    grouped_sources: Dict[str, Dict[str, Dict]] = defaultdict(dict)

    for item_id, item_row in localizer.resolver.item_index.items():
        if not isinstance(item_row, dict) or not is_truthy_flag(item_row.get("Disassemble_Type")):
            continue
        disassemble_key = normalize_disassemble_key(item_row.get("Disassemble_Key"))
        grade_key = normalize_grade(item_row.get("Grade"))
        if not disassemble_key or not grade_key:
            continue
        disassembly_row = disassembly_lookup.get((disassemble_key, grade_key))
        if not disassembly_row:
            continue
        source_payload = build_item_link_payload(item_id, 0, localizer, assets, bucket="items")
        if not source_payload:
            continue
        family_key = first_text(item_row.get("ItemDivision"), item_row.get("ItemDetailType"))
        for index in range(1, 6):
            output_item_id = first_text(disassembly_row.get(f"Item{index}"))
            rate_raw = int(numeric_value(disassembly_row.get(f"Item{index}_Rate")) or 0)
            if not output_item_id or rate_raw <= 0:
                continue
            level_curve_id = normalize_disassemble_key(disassembly_row.get(f"Item{index}_Level_Rate"))
            group_key = "|".join(
                [
                    grade_key,
                    normalize_token(item_row.get("ItemDetailType")),
                    normalize_token(family_key),
                    str(rate_raw),
                    str(int(numeric_value(disassembly_row.get(f"Item{index}_Min")) or 0)),
                    str(int(numeric_value(disassembly_row.get(f"Item{index}_Max")) or 0)),
                    level_curve_id,
                ]
            )
            group = grouped_sources[output_item_id].get(group_key)
            if not group:
                rarity = rarity_payload(item_row.get("Grade"))
                family_en = item_family_label(family_key or item_row.get("ItemDetailType"), "en")
                family_fr = item_family_label(family_key or item_row.get("ItemDetailType"), "fr")
                group = {
                    "id": f"recycle-source:{output_item_id}:{group_key}",
                    "sourceKind": "recycling",
                    "itemDetailType": first_text(item_row.get("ItemDetailType")),
                    "itemDivision": first_text(item_row.get("ItemDivision")),
                    "family": {"en": family_en, "fr": family_fr},
                    "label": {
                        "en": f"{rarity['label']['en']} {family_en}" if rarity else family_en,
                        "fr": f"{family_fr} {rarity['label']['fr']}" if rarity else family_fr,
                    },
                    "rarity": rarity,
                    "rateMode": "guaranteed" if rate_raw >= 10000 else "percent",
                    "rateRaw": rate_raw,
                    "rateDisplayPct": round(rate_raw / 100.0, 4) if rate_raw else 0,
                    "minCount": int(numeric_value(disassembly_row.get(f"Item{index}_Min")) or 0),
                    "maxCount": int(numeric_value(disassembly_row.get(f"Item{index}_Max")) or 0),
                    "levelCurveId": first_text(disassembly_row.get(f"Item{index}_Level_Rate")),
                    "levelCurve": dict(level_curve_lookup.get(level_curve_id, {})) if level_curve_id else {},
                    "sourceCount": 0,
                    "sampleItems": [],
                }
                grouped_sources[output_item_id][group_key] = group
            group["sourceCount"] += 1
            if len(group["sampleItems"]) < 4:
                group["sampleItems"].append(source_payload)

    reverse_index: Dict[str, List[Dict]] = {}
    for output_item_id, group_map in grouped_sources.items():
        rows = list(group_map.values())
        rows.sort(
            key=lambda row: (
                -int(numeric_value((row.get("rarity") or {}).get("rank")) or 0),
                first_text(row.get("family", {}).get("en")),
                -int(numeric_value(row.get("sourceCount")) or 0),
            )
        )
        reverse_index[output_item_id] = rows
    return reverse_index


def build_disassembly_item_payload(item_id: str, localizer: Localizer, assets: AssetResolver) -> Dict:
    payload = build_item_link_payload(item_id, 0, localizer, assets, bucket="items")
    if payload:
        return payload
    item_row = localizer.item_row(item_id) or {}
    return {
        "itemId": item_id,
        "count": 0,
        "name": {
            "en": first_text(localizer.item_name(item_id, "en"), item_id),
            "fr": first_text(localizer.item_name(item_id, "fr"), localizer.item_name(item_id, "en"), item_id),
        },
        "description": {
            "en": localizer.item_desc(item_id, "en"),
            "fr": localizer.item_desc(item_id, "fr"),
        },
        "icon": assets.resolve_stem(item_icon_candidates(localizer, item_row, item_id), "items"),
        "rarity": rarity_payload(item_row.get("Grade")),
        "classification": first_text(item_row.get("ItemDetailType"), item_row.get("ItemDivision"), item_row.get("ItemType")),
    }


def build_item_disassembly_index(
    item_ids: Iterable[str],
    localizer: Localizer,
    assets: AssetResolver,
    disassemble_rows: List[Dict],
    disassemble_level_rows: List[Dict],
) -> Tuple[Dict[str, Dict], List[str]]:
    disassembly_by_item: Dict[str, Dict] = {}
    referenced_item_ids: List[str] = []
    disassembly_lookup = {
        (normalize_disassemble_key(row.get("Disassemble_Key")), normalize_grade(row.get("Grade"))): row
        for row in disassemble_rows
        if isinstance(row, dict) and normalize_disassemble_key(row.get("Disassemble_Key")) and normalize_grade(row.get("Grade"))
    }
    level_curve_lookup = build_disassembly_level_index(disassemble_level_rows)

    for item_id in unique(item_ids):
        item_row = localizer.item_row(item_id) or {}
        if not item_row or not is_truthy_flag(item_row.get("Disassemble_Type")):
            continue
        disassemble_key = normalize_disassemble_key(item_row.get("Disassemble_Key"))
        grade_key = normalize_grade(item_row.get("Grade"))
        if not disassemble_key or not grade_key:
            continue
        disassembly_row = disassembly_lookup.get((disassemble_key, grade_key))
        if not disassembly_row:
            continue
        outputs: List[Dict] = []
        for index in range(1, 6):
            output_item_id = first_text(disassembly_row.get(f"Item{index}"))
            rate_raw = int(numeric_value(disassembly_row.get(f"Item{index}_Rate")) or 0)
            if not output_item_id or rate_raw <= 0:
                continue
            level_curve_id = normalize_disassemble_key(disassembly_row.get(f"Item{index}_Level_Rate"))
            level_curve = dict(level_curve_lookup.get(level_curve_id, {})) if level_curve_id else {}
            output_payload = build_disassembly_item_payload(output_item_id, localizer, assets)
            output_payload.update(
                {
                    "id": f"disassembly:{item_id}:{output_item_id}:{index}",
                    "rateMode": "guaranteed" if rate_raw >= 10000 else "percent",
                    "rateRaw": rate_raw,
                    "rateDisplayPct": round(rate_raw / 100.0, 4) if rate_raw else 0,
                    "minCount": int(numeric_value(disassembly_row.get(f"Item{index}_Min")) or 0),
                    "maxCount": int(numeric_value(disassembly_row.get(f"Item{index}_Max")) or 0),
                    "levelCurveId": first_text(disassembly_row.get(f"Item{index}_Level_Rate")),
                    "levelCurve": level_curve,
                    "hasLevelScaling": bool(level_curve),
                }
            )
            outputs.append(output_payload)
            referenced_item_ids.append(output_item_id)

        currencies: List[Dict] = []
        for index in range(1, 4):
            currency_id = first_text(disassembly_row.get(f"Currency{index}"))
            rate_raw = int(numeric_value(disassembly_row.get(f"Currency{index}_Rate")) or 0)
            if not currency_id or rate_raw <= 0:
                continue
            level_curve_id = normalize_disassemble_key(disassembly_row.get(f"Currency{index}_Level_Rate"))
            currencies.append(
                {
                    "id": f"disassembly:{item_id}:currency:{currency_id}:{index}",
                    "currencyId": currency_id,
                    "rateMode": "guaranteed" if rate_raw >= 10000 else "percent",
                    "rateRaw": rate_raw,
                    "rateDisplayPct": round(rate_raw / 100.0, 4) if rate_raw else 0,
                    "minCount": int(numeric_value(disassembly_row.get(f"Currency{index}_Min")) or 0),
                    "maxCount": int(numeric_value(disassembly_row.get(f"Currency{index}_Max")) or 0),
                    "levelCurveId": first_text(disassembly_row.get(f"Currency{index}_Level_Rate")),
                    "levelCurve": dict(level_curve_lookup.get(level_curve_id, {})) if level_curve_id else {},
                }
            )

        if outputs or currencies:
            disassembly_by_item[item_id] = {
                "enabled": True,
                "key": disassemble_key,
                "grade": grade_key,
                "outputs": outputs,
                "currencies": currencies,
                "hasLevelScaling": any(output.get("hasLevelScaling") for output in outputs) or any(currency.get("levelCurve") for currency in currencies),
            }
    return disassembly_by_item, unique(referenced_item_ids)


def format_scaled_percent(value: object) -> str:
    scaled = numeric_value(value) / 100.0
    if abs(scaled - round(scaled)) < 1e-6:
        text = str(int(round(scaled)))
    else:
        text = f"{scaled:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def flatten_behavior_names(value: object) -> List[str]:
    names: List[str] = []
    if isinstance(value, dict):
        for key in ("array", "Array", "String_Tid", "string_Tid", "Name", "name"):
            if value.get(key):
                names.extend(flatten_behavior_names(value.get(key)))
        return names
    if isinstance(value, list):
        for nested in value:
            names.extend(flatten_behavior_names(nested))
        return names
    resolved = first_text(value)
    return [resolved] if resolved else []


def hit_area_summary(hit_area: object) -> str:
    if not isinstance(hit_area, dict):
        return ""
    shape = first_text(hit_area.get("Shape"))
    values = [f"{key}:{int(numeric_value(hit_area.get(key)))}" for key in ("Radius", "Wide", "Top", "Max") if numeric_value(hit_area.get(key))]
    if not values:
        return shape
    return f"{shape} ({', '.join(values)})" if shape else ", ".join(values)


def build_attack_effect_payload(
    detail: Dict,
    hit_target: object,
    hit_area: object,
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
) -> Optional[Dict]:
    if not isinstance(detail, dict):
        return None
    scalings = []
    for index in (1, 2):
        stat_key = first_text(detail.get(f"Target_Stat_{index}"))
        rate_value = detail.get(f"Stat_Rate_{index}")
        if not stat_key or not first_text(rate_value) or abs(numeric_value(rate_value)) < 1e-6:
            continue
        stat_info = stat_info_by_id.get(normalize_token(stat_key), {})
        label_en = first_text(localizer.translate(stat_info.get("Local_key"), "en"), humanize_token(stat_key))
        label_fr = first_text(localizer.translate(stat_info.get("Local_key"), "fr"), label_en)
        scalings.append(
            {
                "id": stat_key,
                "label": {"en": label_en, "fr": label_fr},
                "value": {"en": format_scaled_percent(rate_value), "fr": format_scaled_percent(rate_value)},
            }
        )
    if not scalings and not first_text(detail.get("DamType"), detail.get("DamType_Element")):
        return None
    charge_value = int(numeric_value(detail.get("Charge_Element_Value")) or 0)
    return {
        "kind": "attack",
        "damageType": first_text(detail.get("DamType")),
        "element": first_text(detail.get("DamType_Element")),
        "target": first_text(hit_target),
        "area": hit_area_summary(hit_area),
        "scaling": scalings,
        "alwaysCritical": str(detail.get("Always_Critical") or "").lower() == "true",
        "ignoreBlock": str(detail.get("Ignore_Block") or "").lower() == "true",
        "ignoreDef": str(detail.get("Ignore_Def") or "").lower() == "true",
        "ignoreShield": str(detail.get("Ignore_Shield") or "").lower() == "true",
        "chargeElement": charge_value,
        "gaugeDamage": int(numeric_value(detail.get("GaugeDmg")) or 0),
    }


def build_set_buff_effect_payload(
    detail: Dict,
    buff_by_id: Dict[str, Dict],
    localizer: Localizer,
) -> Optional[Dict]:
    if not isinstance(detail, dict):
        return None
    buff_id = first_text(detail.get("BuffTid"))
    if not buff_id:
        return None
    buff_row = buff_by_id.get(buff_id, {})
    able_type = buff_row.get("AbleType") if isinstance(buff_row.get("AbleType"), dict) else {}
    name_en = first_text(
        localizer.translate(buff_row.get("Local_Key"), "en"),
        humanize_token(buff_row.get("ActorState")),
        humanize_token(able_type.get("string_Tid")),
        buff_id,
    )
    name_fr = first_text(localizer.translate(buff_row.get("Local_Key"), "fr"), name_en)
    duration_ms = int(numeric_value(detail.get("BuffTime")) or 0)
    duration_seconds = duration_ms / 1000.0 if duration_ms > 0 else 0.0
    return {
        "kind": "buff",
        "buffId": buff_id,
        "name": {"en": name_en, "fr": name_fr},
        "description": {
            "en": localizer.format(buff_row.get("Local_Desc"), "en", buff_row.get("Local_Replace")),
            "fr": localizer.format(buff_row.get("Local_Desc"), "fr", buff_row.get("Local_Replace")),
        },
        "side": "debuffs" if "debuff" in first_text(buff_row.get("Type")).lower() else "buffs",
        "durationSeconds": duration_seconds,
        "count": int(numeric_value(detail.get("BuffCnt")) or 0),
        "rate": int(numeric_value(detail.get("Rate")) or 0),
        "actorState": first_text(buff_row.get("ActorState")),
    }


def build_skill_effect_payloads(
    skill_row: Dict,
    behavior_by_id: Dict[str, Dict],
    buff_by_id: Dict[str, Dict],
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
) -> List[Dict]:
    behavior_names = []
    behavior_names.extend(flatten_behavior_names(skill_row.get("ActionStart_Behavior_Tid")))
    behavior_names.extend(flatten_behavior_names(skill_row.get("Action_Behavior_TidList")))
    behavior_names.extend(flatten_behavior_names(skill_row.get("Burst_Activation_Behavior_TidList")))
    effects: List[Dict] = []
    for order, behavior_name in enumerate(behavior_names, start=1):
        behavior = behavior_by_id.get(normalize_token(behavior_name))
        if not behavior:
            continue
        hit_target = behavior.get("HitTarget")
        hit_area = behavior.get("HitArea")
        for attack in behavior.get("BehaviorDetail_AttackTid") or []:
            payload = build_attack_effect_payload(attack, hit_target, hit_area, stat_info_by_id, localizer)
            if payload:
                payload["phase"] = order
                payload["behaviorId"] = first_text(behavior.get("Name"), behavior_name)
                effects.append(payload)
        for buff in behavior.get("BehaviorDetail_SetBuffTid") or []:
            payload = build_set_buff_effect_payload(buff, buff_by_id, localizer)
            if payload:
                payload["phase"] = order
                payload["behaviorId"] = first_text(behavior.get("Name"), behavior_name)
                effects.append(payload)
    return effects


def build_common_mastery_catalog(
    common_mastery_rows: List[Dict],
    stat_info_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Dict[str, Dict]:
    grouped_rows: Dict[str, List[Dict]] = defaultdict(list)
    stat_info_by_id = {
        normalize_token(row.get("Name")): row
        for row in stat_info_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    for row in common_mastery_rows:
        if not isinstance(row, dict):
            continue
        mastery_id = first_text(row.get("Common_Mastery_Tid"))
        if mastery_id:
            grouped_rows[mastery_id].append(row)

    catalog: Dict[str, Dict] = {}
    for mastery_id, rows in grouped_rows.items():
        ordered_rows = sorted(rows, key=lambda row: int(numeric_value(row.get("Common_Mastery_Index")) or 0))
        nodes = []
        for row in ordered_rows:
            abilities = [
                ability
                for ability in (
                    build_ability_payload(ability_type, ability_value, stat_info_by_id, localizer, assets)
                    for ability_type, ability_value in zip(row.get("Mastery_AbilityType") or [], row.get("Mastery_AbilityValue") or [])
                )
                if ability
            ]
            index = int(numeric_value(row.get("Common_Mastery_Index")) or 0)
            title_en = ", ".join(ability["label"]["en"] for ability in abilities[:3]) or f"Shared Mastery {index:02d}"
            title_fr = ", ".join(ability["label"]["fr"] for ability in abilities[:3]) or f"Maitrise partagee {index:02d}"
            nodes.append(
                {
                    "id": first_text(row.get("Name")),
                    "index": index,
                    "title": {"en": title_en, "fr": title_fr},
                    "abilities": abilities,
                    "icon": first_text((abilities[0] if abilities else {}).get("icon")),
                    "expValue": int(numeric_value(row.get("Mastery_Exp_Value")) or 0),
                    "currencyCost": int(numeric_value(row.get("CurrencyCost")) or 0),
                }
            )
        groups = []
        for start in range(0, len(nodes), 5):
            chunk = nodes[start : start + 5]
            group_index = (start // 5) + 1
            groups.append(
                {
                    "id": f"{mastery_id}:{group_index}",
                    "index": group_index,
                    "label": {"en": f"Tier {group_index}", "fr": f"Palier {group_index}"},
                    "nodes": chunk,
                    "expValue": sum(node.get("expValue", 0) for node in chunk),
                    "currencyCost": sum(node.get("currencyCost", 0) for node in chunk),
                }
            )
        catalog[mastery_id] = {
            "id": mastery_id,
            "label": {"en": "Shared Mastery", "fr": "Maitrise partagee"},
            "groups": groups,
            "totalNodes": len(nodes),
            "totalExp": sum(node.get("expValue", 0) for node in nodes),
            "totalCurrency": sum(node.get("currencyCost", 0) for node in nodes),
        }
    return catalog


def build_weapon_mastery_catalog(
    mastery_rows: List[Dict],
    mastery_group_rows: List[Dict],
    mastery_group_exp_rows: List[Dict],
    stat_info_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Dict[str, Dict]:
    mastery_rows_by_type: Dict[str, List[Dict]] = defaultdict(list)
    mastery_group_by_id = {
        first_text(row.get("Name")): row
        for row in mastery_group_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    mastery_exp_by_group: Dict[str, List[Dict]] = defaultdict(list)
    stat_info_by_id = {
        normalize_token(row.get("Name")): row
        for row in stat_info_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }

    for row in mastery_rows:
        if not isinstance(row, dict):
            continue
        mastery_rows_by_type[normalize_token(row.get("Weapon_Type"))].append(row)

    for row in mastery_group_exp_rows:
        if not isinstance(row, dict):
            continue
        group_id = first_text(row.get("WeaponGroupTid"))
        if group_id:
            mastery_exp_by_group[group_id].append(row)

    catalog: Dict[str, Dict] = {}
    for weapon_type, rows in mastery_rows_by_type.items():
        if not weapon_type:
            continue
        mastery_tids = sorted({first_text(row.get("Weapon_Mastery_Tid")) for row in rows if first_text(row.get("Weapon_Mastery_Tid"))})
        preferred_tid = mastery_tids[0] if mastery_tids else ""
        scoped_rows = [row for row in rows if first_text(row.get("Weapon_Mastery_Tid")) == preferred_tid] or rows
        rows = scoped_rows
        sample = rows[0]
        groups: List[Dict] = []
        grouped_nodes: Dict[str, List[Dict]] = defaultdict(list)
        for row in rows:
            grouped_nodes[first_text(row.get("Weapon_Mastery_Group"))].append(row)

        sorted_group_ids = sorted(
            grouped_nodes,
            key=lambda group_id: int(numeric_value(mastery_group_by_id.get(group_id, {}).get("Weapon_Mastery_Group_Index")) or 0),
        )
        for group_id in sorted_group_ids:
            group_rows = sorted(
                grouped_nodes[group_id],
                key=lambda row: (
                    int(numeric_value(row.get("Weapon_Mastery_Index")) or 0),
                    int(numeric_value(row.get("Weapon_Mastery_Grade")) or 0),
                    first_text(row.get("Name")),
                ),
            )
            group_meta = mastery_group_by_id.get(group_id, {})
            tier_index = int(numeric_value(group_meta.get("Weapon_Mastery_Group_Index")) or numeric_value(group_rows[0].get("Weapon_Mastery_Index")) or 0)
            nodes = []
            for row in group_rows:
                materials = []
                for material_id, material_count in zip(row.get("Weapon_Mastery_MaterialType") or [], row.get("Weapon_Mastery_MaterialValue") or []):
                    payload = build_item_link_payload(material_id, material_count, localizer, assets, bucket="mastery")
                    if payload:
                        materials.append(payload)
                abilities = [
                    ability
                    for ability in (
                        build_ability_payload(ability_type, ability_value, stat_info_by_id, localizer, assets)
                        for ability_type, ability_value in zip(row.get("Weapon_Mastery_AbilityType") or [], row.get("Weapon_Mastery_AbilityValue") or [])
                    )
                    if ability
                ]
                nodes.append(
                    {
                        "id": first_text(row.get("Name")),
                        "label": localized_enum(row.get("Weapon_Mastery_Type"), MASTERY_TYPE_LABELS),
                        "title": {
                            "en": first_text(localizer.translate(row.get("Skill_Weapon_Mastery_Name"), "en"), localized_enum(sample.get("Weapon_Type"), STYLE_LABELS)["en"]),
                            "fr": first_text(localizer.translate(row.get("Skill_Weapon_Mastery_Name"), "fr"), localized_enum(sample.get("Weapon_Type"), STYLE_LABELS)["fr"]),
                        },
                        "description": {
                            "en": localizer.format(row.get("Skill_Weapon_Mastery_Desc"), "en"),
                            "fr": localizer.format(row.get("Skill_Weapon_Mastery_Desc"), "fr"),
                        },
                        "applyCondition": localized_enum(row.get("Weapon_Mastery_Apply_Condition"), MASTERY_CONDITION_LABELS),
                        "grade": int(numeric_value(row.get("Weapon_Mastery_Grade")) or 0),
                        "icon": assets.resolve_stem([row.get("Weapon_Mastery_Icon")], "mastery"),
                        "materials": materials,
                        "abilities": abilities,
                        "currencyCost": int(numeric_value(row.get("CurrencyCost")) or 0),
                    }
                )
            milestones = []
            for row in sorted(
                mastery_exp_by_group.get(group_id, []),
                key=lambda item: int(numeric_value(item.get("WeaponGroupEXP_Index")) or 0),
            ):
                abilities = [
                    ability
                    for ability in (
                        build_ability_payload(ability_type, ability_value, stat_info_by_id, localizer, assets)
                        for ability_type, ability_value in zip(row.get("Mastery_AbilityType") or [], row.get("Mastery_AbilityValue") or [])
                    )
                    if ability
                ]
                milestones.append(
                    {
                        "id": first_text(row.get("Name")),
                        "index": int(numeric_value(row.get("WeaponGroupEXP_Index")) or 0),
                        "expValue": int(numeric_value(row.get("Mastery_Exp_Value")) or 0),
                        "abilities": abilities,
                    }
                )
            groups.append(
                {
                    "id": group_id,
                    "index": tier_index,
                    "label": {"en": f"Tier {tier_index}", "fr": f"Palier {tier_index}"},
                    "cover": assets.resolve_stem([group_meta.get("Weapon_Mastery_Group_Model")], "mastery"),
                    "expValue": int(numeric_value(group_meta.get("Weapon_Mastery_Exp_Value")) or 0),
                    "currencyCost": int(numeric_value(group_meta.get("Weapon_Mastery_CurrencyCost")) or 0),
                    "nodes": nodes,
                    "milestones": milestones,
                }
            )
        catalog[weapon_type] = {
            "id": first_text(sample.get("Weapon_Mastery_Tid")),
            "label": localized_enum(sample.get("Weapon_Type"), STYLE_LABELS),
            "groups": groups,
        }
    return catalog


def display_point_name(point: Dict, lang: str = "en") -> str:
    if point.get("type") == "pet":
        return first_text(
            point.get("pet_name_fr") if lang == "fr" else point.get("pet_name"),
            point.get("pet_name"),
            point.get("pet_name_fr"),
            point.get("label"),
            point.get("name"),
        )
    return first_text(
        point.get("resource_name_fr") if lang == "fr" else point.get("resource_name"),
        point.get("resource_name"),
        point.get("resource_name_fr"),
        point.get("label"),
        point.get("name"),
    )


def point_regions(point: Dict) -> List[str]:
    if isinstance(point.get("regions"), list) and point["regions"]:
        return unique(point["regions"])
    return unique([point.get("region")])


def build_map_ref(
    points: List[Dict],
    *,
    point_type: str = "",
    subcategory: str = "",
    resource_item_id: str = "",
    pet_item_id: str = "",
    actor_tid: str = "",
    mon_catch_tid: str = "",
    preferred_point_id: str = "",
) -> Optional[Dict]:
    if not points and not any([point_type, subcategory, resource_item_id, pet_item_id, actor_tid, mon_catch_tid]):
        return None
    region_ids = unique(
        region_id
        for point in points
        for region_id in (point.get("region_ids") or [point.get("region_id")])
        if region_id
    )
    regions = unique(region for point in points for region in point_regions(point))
    point_ids = unique(point.get("id") for point in points if point.get("id"))
    return {
        "pointIds": point_ids,
        "regionIds": region_ids,
        "regions": regions,
        "type": point_type,
        "subcategory": subcategory,
        "resourceItemId": resource_item_id,
        "petItemId": pet_item_id,
        "actorTid": actor_tid,
        "monCatchTid": mon_catch_tid,
        "preferredPointId": preferred_point_id or (point_ids[0] if point_ids else ""),
    }


class AssetResolver:
    def __init__(self) -> None:
        self.site_index = self._build_index(
            [
                CODEX_ASSETS_DIR / "generated",
                SITE_ASSETS_DIR / "icons",
                SITE_ASSETS_DIR / "subcategories",
                SITE_ASSETS_DIR / "game-icons",
            ]
        )
        export_roots = [
            FEXPORT_ROOT / "Content" / "UIImg",
            FEXPORT_ROOT / "Content" / "UI" / "UI_Resourse",
        ]
        self.export_index = self._build_index(export_roots, IMAGE_ASSET_SUFFIXES)
        self.export_package_index = self._build_index(export_roots, PACKAGE_ASSET_SUFFIXES)
        self._copied: Dict[Tuple[str, str], str] = {}
        self._downloaded: Dict[Tuple[str, str], str] = {}

    def _build_index(self, roots: List[Path], suffixes: Iterable[str] = IMAGE_ASSET_SUFFIXES) -> Dict[str, List[Path]]:
        index: Dict[str, List[Path]] = defaultdict(list)
        normalized_suffixes = {str(suffix).lower() for suffix in suffixes}
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in normalized_suffixes:
                    continue
                for key in unique([path.stem.lower(), normalize_token(path.stem)]):
                    if key:
                        index[key].append(path)
        return index

    def _copy(self, source: Path, bucket: str) -> str:
        key = (bucket, str(source))
        cached = self._copied.get(key)
        if cached:
            return cached
        target_dir = GENERATED_ASSETS_DIR / bucket
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        rel = "./" + target.relative_to(CODEX_ROOT).as_posix()
        self._copied[key] = rel
        return rel

    def _download(self, url: str, bucket: str, filename: str) -> str:
        key = (bucket, url)
        cached = self._downloaded.get(key)
        if cached:
            return cached
        target_dir = GENERATED_ASSETS_DIR / bucket
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        if not target.exists():
            try:
                with urlopen(url, timeout=20) as response:
                    if response.getcode() != 200:
                        return ""
                    target.write_bytes(response.read())
            except (HTTPError, URLError, TimeoutError, OSError):
                return ""
        rel = "./" + target.relative_to(CODEX_ROOT).as_posix()
        self._downloaded[key] = rel
        return rel

    def _remote_effect_icon_url(self, source: Path) -> str:
        normalized = source.as_posix().lower()
        if "/content/uiimg/origin/buff/frames/" not in normalized:
            return ""
        return f"{BUFF_ICON_REMOTE_BASE}{source.stem}.webp"

    def _resolve_remote_effect_icon(self, exact: str, compact: str, bucket: str) -> str:
        if bucket != "effects":
            return ""
        for key in unique([exact, compact]):
            if not key:
                continue
            for source in self.export_package_index.get(key, []):
                remote_url = self._remote_effect_icon_url(source)
                if not remote_url:
                    continue
                resolved = self._download(remote_url, bucket, f"{source.stem}.webp")
                if resolved:
                    return resolved
        return ""

    def _iterate_stem_candidates(self, candidates: Iterable[object]) -> Iterable[object]:
        for candidate in candidates:
            if isinstance(candidate, (list, tuple, set)):
                yield from self._iterate_stem_candidates(candidate)
                continue
            if isinstance(candidate, dict):
                for key in (
                    "string_tid",
                    "Name",
                    "name",
                    "Icon",
                    "icon",
                    "Portrait",
                    "portrait",
                    "UI_HUD_Portrait",
                    "UI_Actor_Icon_Headup_Center",
                ):
                    value = candidate.get(key)
                    if value:
                        yield from self._iterate_stem_candidates([value])
                continue
            yield candidate

    def resolve_site_asset(self, relative_path: str, bucket: str) -> str:
        raw = str(relative_path or "").strip().replace("\\", "/")
        if not raw:
            return ""
        normalized = raw.lstrip("./")
        candidates = [
            Path(raw),
            ROOT / raw,
            CODEX_ROOT / raw,
            DOCUMENTS_ROOT / raw,
            SEVENMAP_ROOT / raw,
            SITE_ROOT / raw,
        ]
        if normalized.startswith("site/assets/"):
            trimmed = normalized[len("site/assets/") :]
            candidates.append(SITE_ASSETS_DIR / trimmed)
        elif normalized.startswith("assets/"):
            trimmed = normalized[len("assets/") :]
            candidates.extend([SITE_ASSETS_DIR / trimmed, CODEX_ASSETS_DIR / trimmed])
        seen = set()
        for source in candidates:
            key = str(source)
            if key in seen:
                continue
            seen.add(key)
            if source.exists():
                return self._copy(source, bucket)
        return ""

    def resolve_stem(self, stem_candidates: Iterable[object], bucket: str) -> str:
        for candidate in self._iterate_stem_candidates(stem_candidates):
            stem = str(candidate or "").strip()
            if not stem:
                continue
            stem_base = Path(stem).stem
            exact = stem_base.lower()
            compact = normalize_token(stem_base)
            for source in self.site_index.get(exact, []):
                return self._copy(source, bucket)
            for source in self.export_index.get(exact, []):
                return self._copy(source, bucket)
            if compact and compact != exact:
                for source in self.site_index.get(compact, []):
                    return self._copy(source, bucket)
                for source in self.export_index.get(compact, []):
                    return self._copy(source, bucket)
            remote = self._resolve_remote_effect_icon(exact, compact, bucket)
            if remote:
                return remote
        return ""


class Localizer:
    def __init__(self) -> None:
        self.resolver = ResourceResolver(TEXTDATA_DIR, LOCALIZATION_DIR)
        self.view_image_index: Dict[str, Dict] = {}
        for row in read_json(TEXTDATA_DIR / "ViewImageTable.json"):
            if not isinstance(row, dict):
                continue
            name = first_text(row.get("Name"))
            for key in unique([name.lower(), normalize_token(name)]):
                if key:
                    self.view_image_index[key] = row
        self.avatar_by_item_id = {
            first_text(row.get("KeyItemID")): row
            for row in read_json(TEXTDATA_DIR / "AvatarTable.json")
            if isinstance(row, dict) and first_text(row.get("KeyItemID"))
        }

    def translate(self, key: object, lang: str) -> str:
        raw = str(key or "").strip()
        if not raw:
            return ""
        return repair_mojibake(self.resolver.localizations.get(lang.lower(), {}).get(raw.lower(), ""))

    def format(self, key: object, lang: str, replacements: object = None) -> str:
        translated = self.translate(key, lang)
        return format_game_text(translated, replacements)

    def item_row(self, item_id: object) -> Optional[Dict]:
        return self.resolver.item_index.get(str(item_id or "").strip())

    def item_name(self, item_id: object, lang: str) -> str:
        row = self.item_row(item_id)
        if not row:
            return ""
        key = first_text(row.get("Local_DropKey"), row.get("Local_Key"))
        return self.translate(key, lang)

    def item_desc(self, item_id: object, lang: str) -> str:
        row = self.item_row(item_id)
        if not row:
            return ""
        desc_key = first_text(row.get("Food_Local_Desc"), row.get("Local_Desc"))
        replacements = row.get("Food_Local_Replace") or row.get("Local_Replace") or []
        return self.format(desc_key, lang, replacements)

    def view_image_candidates(self, *values: object) -> List[str]:
        stems: List[str] = []
        for value in values:
            key = first_text(value)
            if not key:
                continue
            row = self.view_image_index.get(key.lower()) or self.view_image_index.get(normalize_token(key))
            if row:
                stems.extend([first_text(row.get("Icon")), first_text(row.get("IconSub"))])
        return unique(stems)

    def avatar_icon_candidates(self, item_id: object) -> List[str]:
        avatar_row = self.avatar_by_item_id.get(first_text(item_id))
        if not avatar_row:
            return []
        return unique([first_text(avatar_row.get("Icon"))] + self.view_image_candidates(avatar_row.get("Icon")))


def base_entry(
    *,
    entry_id: str,
    slug: str,
    kind: str,
    lists: List[str],
    name_en: str,
    name_fr: str,
    description_en: str = "",
    description_fr: str = "",
    summary_en: str = "",
    summary_fr: str = "",
    icon: str = "",
    image: str = "",
    rarity: Optional[Dict] = None,
    classification: str = "",
    regions: Optional[List[str]] = None,
    region_ids: Optional[List[str]] = None,
    map_ref: Optional[Dict] = None,
    source_tables: Optional[List[str]] = None,
    source_ids: Optional[Dict] = None,
    related: Optional[List[str]] = None,
    stats: Optional[Dict] = None,
    fields: Optional[Dict] = None,
    sort_index: Optional[int] = None,
    alias_slugs: Optional[List[str]] = None,
) -> Dict:
    payload = {
        "id": entry_id,
        "slug": slug,
        "aliasSlugs": alias_slugs or [],
        "kind": kind,
        "lists": lists,
        "locale": {
            "en": {
                "name": name_en,
                "description": description_en,
                "summary": summary_en,
            },
            "fr": {
                "name": name_fr or name_en,
                "description": description_fr,
                "summary": summary_fr or summary_en,
            },
        },
        "icon": icon,
        "image": image,
        "rarity": rarity,
        "class": classification,
        "regions": regions or [],
        "regionIds": region_ids or [],
        "mapRef": map_ref,
        "sourceTables": source_tables or [],
        "sourceIds": source_ids or {},
        "related": related or [],
        "stats": stats or {},
        "fields": fields or {},
    }
    if sort_index is not None:
        payload["sortIndex"] = int(sort_index)
    return payload


def build_region_entries(points: List[Dict], assets: AssetResolver) -> List[Dict]:
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    region_ids: Dict[str, List[str]] = defaultdict(list)
    for point in points:
        region = first_text(point.get("region"))
        if not region:
            continue
        grouped[region].append(point)
        region_ids[region].extend(unique(point.get("region_ids") or [point.get("region_id")]))

    entries: List[Dict] = []
    generic_icon = assets.resolve_stem(["T_WorldMap_Map_01_01", "worldmap_cache_4608"], "regions")
    for region, region_points in sorted(grouped.items(), key=lambda item: item[0]):
        slug = slugify(region)
        counts = Counter(str(point.get("type") or "") for point in region_points)
        point_ids = [point.get("id") for point in region_points if point.get("id")]
        entry = base_entry(
            entry_id=f"region:{slug}",
            slug=slug,
            kind="region",
            lists=["regions"],
            name_en=region,
            name_fr=REGION_LABELS_FR.get(region, region),
            summary_en=f"{len(region_points)} tracked map locations across {len(counts)} map systems.",
            summary_fr=f"{len(region_points)} emplacements suivis sur la carte, r\u00e9partis sur {len(counts)} syst\u00e8mes.",
            icon=generic_icon,
            source_tables=["map_data.json"],
            source_ids={"regionIds": unique(region_ids[region])},
            map_ref=build_map_ref(region_points, preferred_point_id=point_ids[0] if point_ids else "", point_type=""),
            regions=[region],
            region_ids=unique(region_ids[region]),
            stats={"pointCount": len(region_points), "typeCounts": dict(counts)},
            fields={
                "typeCounts": dict(counts),
            },
        )
        entries.append(entry)
    return entries


def collect_node_search_terms(group_points: List[Dict], raw_subcategory: str) -> List[str]:
    terms: List[str] = [raw_subcategory, humanize_token(raw_subcategory)]
    for point in group_points:
        terms.extend(
            [
                point.get("name"),
                point.get("label"),
                point.get("subcategory_label"),
                point.get("resource_name"),
                point.get("resource_name_fr"),
                point.get("resolution_source"),
            ]
        )
    return unique(terms)


def build_node_alias_slugs(
    point_type: str,
    canonical_slug: str,
    group_points: List[Dict],
    raw_subcategory: str,
) -> List[str]:
    candidates = [f"{point_type}-{slugify(raw_subcategory)}"] if raw_subcategory else []
    for point in group_points:
        for value in (
            point.get("label"),
            point.get("subcategory_label"),
            point.get("resource_name"),
        ):
            text = first_text(value)
            if text:
                candidates.append(f"{point_type}-{slugify(text)}")
    return [slug for slug in unique(candidates) if slug and slug != canonical_slug]


def build_node_entries(points: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    groups: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for point in points:
        point_type = str(point.get("type") or "")
        if point_type not in {"gathering", "mining", "mastery"}:
            continue
        item_id = first_text(point.get("resource_item_id"), point.get("resourceItemId"))
        subcategory = first_text(point.get("subcategory"), point.get("subcategory_label"), display_point_name(point, "en"))
        group_key = item_id or slugify(subcategory)
        groups[(point_type, group_key)].append(point)

    entries: List[Dict] = []
    for (point_type, key), group_points in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        sample = group_points[0]
        item_id = first_text(sample.get("resource_item_id"), sample.get("resourceItemId"))
        item_row = localizer.item_row(item_id) if item_id else None
        name_en = first_text(localizer.item_name(item_id, "en") if item_id else "", display_point_name(sample, "en"))
        name_fr = first_text(localizer.item_name(item_id, "fr") if item_id else "", display_point_name(sample, "fr"), name_en)
        desc_en = first_text(localizer.item_desc(item_id, "en") if item_id else "", sample.get("resource_description"))
        desc_fr = first_text(localizer.item_desc(item_id, "fr") if item_id else "", sample.get("resource_description_fr"))
        raw_subcategory = first_text(sample.get("subcategory"), sample.get("subcategory_label"), slugify(name_en))
        subcategory_label = first_text(sample.get("subcategory_label"), sample.get("resource_name"), name_en, raw_subcategory)
        slug = f"{point_type}-{slugify(name_en or key)}"
        icon = ""
        if raw_subcategory:
            icon = assets.resolve_site_asset(
                f"site/assets/subcategories/{point_type}/{slugify(raw_subcategory)}.png",
                point_type,
            )
        if not icon:
            icon = assets.resolve_stem(
                item_icon_stems(
                    item_row.get("IconName") if item_row else "",
                    sample.get("resource_icon_name"),
                    sample.get("resourceItemId"),
                    sample.get("resource_item_id"),
                ),
                point_type,
            )
        regions = unique(region for point in group_points for region in point_regions(point))
        region_ids = unique(
            region_id
            for point in group_points
            for region_id in (point.get("region_ids") or [point.get("region_id")])
            if region_id
        )
        rarity = rarity_payload(
            first_text(sample.get("resource_rarity_grade"), item_row.get("Grade") if item_row else ""),
            first_text(sample.get("resource_rarity_hex")),
        )
        search_terms = collect_node_search_terms(group_points, raw_subcategory)
        alias_slugs = build_node_alias_slugs(point_type, slug, group_points, raw_subcategory)
        entry = base_entry(
            entry_id=f"node:{point_type}:{slugify(key)}",
            slug=slug,
            kind="node",
            lists=[point_type],
            name_en=name_en or f"{point_type.title()} node",
            name_fr=name_fr or name_en or f"{point_type.title()} node",
            description_en=desc_en,
            description_fr=desc_fr,
            summary_en=f"{len(group_points)} tracked locations across {len(regions)} regions.",
            summary_fr=f"{len(group_points)} emplacements suivis sur {len(regions)} r\u00e9gions.",
            icon=icon,
            rarity=rarity,
            regions=regions,
            region_ids=region_ids,
            source_tables=["map_data.json"],
            source_ids={
                "resourceItemId": item_id,
                "subcategory": raw_subcategory,
                "resolutionSource": first_text(sample.get("resolution_source")),
                "resolutionConfidence": first_text(sample.get("resolution_confidence")),
            },
            map_ref=build_map_ref(
                group_points,
                point_type=point_type,
                subcategory=slugify(raw_subcategory),
                resource_item_id=item_id,
            ),
            stats={"pointCount": len(group_points)},
            fields={
                "subcategory": raw_subcategory,
                "subcategoryLabel": subcategory_label,
                "resourceItemId": item_id,
                "type": point_type,
                "searchTerms": search_terms,
            },
            alias_slugs=alias_slugs,
        )
        entries.append(entry)
    return entries


def pet_lookup_tokens(*values: object) -> List[str]:
    tokens: List[str] = []
    for raw in values:
        text = first_text(raw)
        if not text:
            continue
        cleaned = re.sub(r"^pet\s*:\s*", "", text, flags=re.IGNORECASE).strip()
        for candidate in [text, cleaned]:
            normalized = normalize_token(candidate)
            if normalized:
                tokens.append(normalized)
            parts = [
                part
                for part in re.split(r"[^a-z0-9]+", candidate.lower())
                if part and not part.isdigit() and part not in {"pet", "ap", "mon", "nature", "default", "set"}
            ]
            tokens.extend(parts)
            if parts:
                tokens.append("".join(parts))
    return unique(tokens)


def pet_row_class(row: Optional[Dict]) -> str:
    if not row:
        return ""
    return PET_TYPE_TO_CLASS.get(first_text(row.get("Type")).lower(), "")


def build_pet_lookup_index(pet_rows: List[Dict], localizer: Localizer) -> Dict[str, List[Dict]]:
    index: Dict[str, List[Dict]] = defaultdict(list)
    for row in pet_rows:
        if not isinstance(row, dict):
            continue
        local_key = first_text(row.get("Local_Key"))
        actor_tid = first_text(row.get("ActorTid"))
        for token in pet_lookup_tokens(
            row.get("ItemID"),
            local_key,
            actor_tid,
            actor_tid.replace("ap_pet_", "") if actor_tid else "",
            localizer.translate(local_key, "en") if local_key else "",
            localizer.translate(local_key, "fr") if local_key else "",
        ):
            index[token].append(row)
    return index


def resolve_pet_row_from_point(sample: Dict, lookup_index: Dict[str, List[Dict]]) -> Optional[Dict]:
    point_class = first_text(sample.get("pet_class"))
    actor_tid = first_text(sample.get("actor_tid"), sample.get("actorTid"))
    label = first_text(sample.get("pet_name"), sample.get("label"), sample.get("name"))
    scores: Dict[str, int] = defaultdict(int)
    candidates_by_item: Dict[str, Dict] = {}
    for token in pet_lookup_tokens(label, actor_tid, actor_tid.replace("mon_", "") if actor_tid else ""):
        for row in lookup_index.get(token, []):
            item_id = first_text(row.get("ItemID"))
            if not item_id:
                continue
            candidates_by_item[item_id] = row
            scores[item_id] += max(8, len(token))
            if token in pet_lookup_tokens(label):
                scores[item_id] += 12
            if token in pet_lookup_tokens(actor_tid):
                scores[item_id] += 8
    if not scores:
        return None
    if point_class:
        for item_id, row in candidates_by_item.items():
            row_class = pet_row_class(row)
            if row_class and row_class == point_class:
                scores[item_id] += 40
            elif row_class and row_class != point_class:
                scores[item_id] -= 20
    best_item_id = max(scores.items(), key=lambda item: (item[1], item[0]))[0]
    return candidates_by_item.get(best_item_id)


def build_pet_entries(points: List[Dict], pet_rows: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    raw_point_groups: Dict[str, List[Dict]] = defaultdict(list)
    for point in points:
        if str(point.get("type") or "") != "pet":
            continue
        pet_item_id = first_text(point.get("pet_item_id"), point.get("petItemId"))
        key = pet_item_id or slugify(display_point_name(point, "en"))
        raw_point_groups[key].append(point)

    pet_by_item = {first_text(row.get("ItemID")): row for row in pet_rows if first_text(row.get("ItemID"))}
    pet_lookup_index = build_pet_lookup_index(pet_rows, localizer)
    point_groups: Dict[str, List[Dict]] = defaultdict(list)
    for key, group_points in raw_point_groups.items():
        sample = group_points[0]
        resolved_item_id = first_text(sample.get("pet_item_id"), sample.get("petItemId"))
        if not resolved_item_id:
            resolved_row = resolve_pet_row_from_point(sample, pet_lookup_index)
            resolved_item_id = first_text(resolved_row.get("ItemID")) if resolved_row else ""
        point_groups[resolved_item_id or key].extend(group_points)

    entries: List[Dict] = []
    for key in sorted(unique(list(point_groups.keys()) + list(pet_by_item.keys()))):
        group_points = point_groups.get(key, [])
        pet_row = pet_by_item.get(key)
        sample = group_points[0] if group_points else pet_row or {}
        if not pet_row and group_points:
            pet_row = resolve_pet_row_from_point(sample, pet_lookup_index)
        item_id = first_text(
            sample.get("pet_item_id"),
            sample.get("petItemId"),
            pet_row.get("ItemID") if pet_row else "",
        )
        name_en = first_text(
            localizer.translate(pet_row.get("Local_Key"), "en") if pet_row else "",
            display_point_name(sample, "en"),
        )
        name_fr = first_text(
            localizer.translate(pet_row.get("Local_Key"), "fr") if pet_row else "",
            display_point_name(sample, "fr"),
            name_en,
        )
        desc_en = first_text(
            sample.get("pet_description"),
            localizer.translate(pet_row.get("Desc_Key"), "en") if pet_row else "",
        )
        desc_fr = first_text(
            sample.get("pet_description_fr"),
            localizer.translate(pet_row.get("Desc_Key"), "fr") if pet_row else "",
        )
        pet_class = first_text(sample.get("pet_class"))
        item_row = localizer.item_row(item_id)
        rarity = rarity_payload(first_text(sample.get("pet_rarity_grade"), item_row.get("Grade") if item_row else ""))
        difficulty_level = max(
            int(numeric_value(point.get("pet_catch_difficulty") or point.get("petCatchDifficulty")))
            for point in group_points
        ) if group_points else 0
        rarity_rank = int(numeric_value((rarity or {}).get("rank")) or 0)
        sort_index = difficulty_level * 100 + rarity_rank if difficulty_level > 0 else 900000 + rarity_rank
        icon = assets.resolve_stem(
            pet_icon_stems(
                sample.get("pet_icon_name"),
                pet_row.get("Icon") if pet_row else "",
                pet_row.get("Portrait") if pet_row else "",
                item_row.get("IconName") if item_row else "",
            )
            + ["pet"],
            "pets",
        ) or assets.resolve_site_asset("site/assets/icons/pet.png", "pets")
        regions = unique(region for point in group_points for region in point_regions(point))
        region_ids = unique(
            region_id
            for point in group_points
            for region_id in (point.get("region_ids") or [point.get("region_id")])
            if region_id
        )
        lists = ["pets"]
        pet_class = first_text(pet_class, pet_row_class(pet_row))
        pet_list = PET_CLASS_LISTS.get(pet_class)
        if pet_list:
            lists.append(pet_list)
        legacy_name_en = first_text(display_point_name(sample, "en"))
        legacy_name_fr = first_text(display_point_name(sample, "fr"))
        alias_slugs = []
        if legacy_name_en and slugify(legacy_name_en) != slugify(name_en):
            alias_slugs.append(f"pet-unknown-{slugify(legacy_name_en)}")
        entry = base_entry(
            entry_id=f"pet:{item_id or slugify(name_en)}",
            slug=f"pet-{item_id or 'unknown'}-{slugify(name_en)}",
            kind="pet",
            lists=unique(lists),
            name_en=name_en or "Unknown pet",
            name_fr=name_fr or name_en or "Unknown pet",
            description_en=desc_en,
            description_fr=desc_fr,
            summary_en=f"{len(group_points)} tracked capture locations across {len(regions)} regions." if group_points else "Pet reference extracted from game tables.",
            summary_fr=f"{len(group_points)} emplacements de capture suivis sur {len(regions)} r\u00e9gions." if group_points else "R\u00e9f\u00e9rence de familier extraite des tables du jeu.",
            icon=icon,
            rarity=rarity,
            classification=pet_class,
            regions=regions,
            region_ids=region_ids,
            source_tables=unique(["map_data.json", "PetDataInfo.json"] if group_points else ["PetDataInfo.json"]),
            source_ids={
                "itemId": item_id,
                "actorTid": first_text(sample.get("actor_tid"), sample.get("actorTid"), pet_row.get("ActorTid") if pet_row else ""),
            },
            map_ref=build_map_ref(
                group_points,
                point_type="pet",
                pet_item_id=item_id,
                actor_tid=first_text(sample.get("actor_tid"), sample.get("actorTid"), pet_row.get("ActorTid") if pet_row else ""),
                mon_catch_tid=first_text(sample.get("mon_catch_tid"), sample.get("monCatchTid")),
            )
            if group_points
            else None,
            stats={"pointCount": len(group_points)},
            fields={
                "itemId": item_id,
                "openCondition": pet_row.get("Open_Condition") if pet_row else "",
                "openConditionValue": pet_row.get("Open_Condition_Value") if pet_row else [],
                "actorTid": pet_row.get("ActorTid") if pet_row else "",
                "petDifficultyLevel": difficulty_level,
                "petCatchRateAdd": int(numeric_value(sample.get("pet_catch_rate_add") or sample.get("petCatchRateAdd"))),
                "petCatchRateAddMaxHpRate": int(
                    numeric_value(sample.get("pet_catch_rate_add_max_hp_rate") or sample.get("petCatchRateAddMaxHpRate"))
                ),
                "petCatchTargetHpRate": int(
                    numeric_value(sample.get("pet_catch_target_hp_rate") or sample.get("petCatchTargetHpRate"))
                ),
                "searchTerms": unique(
                    [
                        legacy_name_en,
                        legacy_name_fr,
                        first_text(sample.get("label")),
                        first_text(sample.get("name")),
                        first_text(sample.get("actor_tid"), sample.get("actorTid")),
                    ]
                ),
            },
            sort_index=sort_index,
            alias_slugs=unique(alias_slugs),
        )
        entries.append(entry)
    return entries


def build_boss_entries(
    points: List[Dict],
    field_boss_rows: List[Dict],
    dungeon_rows: List[Dict],
    monster_rows: List[Dict],
    dictionary_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Tuple[List[Dict], Dict[str, str]]:
    map_groups: Dict[str, List[Dict]] = defaultdict(list)
    for point in points:
        if str(point.get("type") or "") != "boss":
            continue
        key = first_text(point.get("name"), point.get("label"), point.get("id"))
        map_groups[key].append(point)

    dictionary_by_local_key, dictionary_by_actor_id = build_monster_dictionary_indexes(dictionary_rows)
    monster_rows_by_id = {
        first_text(row.get("Name")): row
        for row in monster_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    field_boss_by_spawn = {
        first_text(row.get("Spawn_ID")).lower(): row
        for row in field_boss_rows
        if isinstance(row, dict) and first_text(row.get("Spawn_ID"))
    }

    dungeon_refs: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: {"dungeon": [], "challenge": []})
    for row in dungeon_rows:
        if not isinstance(row, dict):
            continue
        if first_text(row.get("Dungeon_Clear_Type")).lower() != "boss":
            continue
        clear_value = first_text(row.get("Dungeon_Clear_Value"))
        if not clear_value or clear_value == "0":
            continue
        dungeon_type = first_text(row.get("Dungeon_Type")).lower()
        if dungeon_type == "normal" and clear_value in DUNGEON_BOSS_MONSTER_IDS:
            dungeon_refs[clear_value]["dungeon"].append(row)
        elif dungeon_type == "boss_replay" and clear_value in BOSS_CHALLENGE_MONSTER_IDS:
            dungeon_refs[clear_value]["challenge"].append(row)

    grouped: Dict[str, Dict] = {}

    def ensure_group(group_key: str) -> Dict:
        return grouped.setdefault(
            group_key,
            {
                "rows": [],
                "map_points": [],
                "field": False,
                "dungeon": False,
                "challenge": False,
                "source_tables": set(),
                "fieldBossTid": "",
                "fieldBossIcon": "",
                "mapNameEn": "",
                "mapNameFr": "",
            },
        )

    for field_row in field_boss_rows:
        if not isinstance(field_row, dict):
            continue
        monster_id = first_text(field_row.get("FieldBossTid"))
        row = monster_rows_by_id.get(monster_id)
        if not row or is_technical_creature_row(row, localizer):
            continue
        group_key = creature_group_key(row, localizer, boss=True) or monster_id.lower()
        payload = ensure_group(group_key)
        payload["rows"].append(row)
        payload["field"] = True
        payload["fieldBossTid"] = first_text(payload.get("fieldBossTid"), monster_id)
        payload["fieldBossIcon"] = first_text(payload.get("fieldBossIcon"), field_row.get("FieldBoss_Icon"))
        payload["source_tables"].update({"FieldBossTable.json", "MonsterActorTable.json"})

    for key, group_points in sorted(map_groups.items(), key=lambda item: item[0]):
        sample = group_points[0]
        spawn_key = first_text(sample.get("name")).lower()
        field_row = field_boss_by_spawn.get(spawn_key)
        matched_row = monster_rows_by_id.get(first_text(field_row.get("FieldBossTid"))) if field_row else None
        if not matched_row:
            matched_row = match_boss_monster_row(sample, monster_rows, localizer)
        if matched_row and is_technical_creature_row(matched_row, localizer):
            matched_row = None
        point_name_en, point_name_fr = field_boss_point_names(sample)
        group_key = ""
        if matched_row:
            group_key = creature_group_key(matched_row, localizer, boss=True)
        if not group_key:
            group_key = slugify(point_name_en or key)
        payload = ensure_group(group_key or slugify(key))
        payload["map_points"].extend(group_points)
        payload["field"] = True
        payload["mapNameEn"] = first_text(payload.get("mapNameEn"), point_name_en)
        payload["mapNameFr"] = first_text(payload.get("mapNameFr"), point_name_fr, point_name_en)
        payload["source_tables"].add("map_data.json")
        if field_row:
            payload["fieldBossTid"] = first_text(payload.get("fieldBossTid"), field_row.get("FieldBossTid"))
            payload["fieldBossIcon"] = first_text(payload.get("fieldBossIcon"), field_row.get("FieldBoss_Icon"))
            payload["source_tables"].add("FieldBossTable.json")
        if matched_row:
            payload["rows"].append(matched_row)
            payload["source_tables"].add("MonsterActorTable.json")

    for monster_id, bucket_rows in dungeon_refs.items():
        row = monster_rows_by_id.get(monster_id)
        if not row or is_technical_creature_row(row, localizer):
            continue
        group_key = creature_group_key(row, localizer, boss=True) or monster_id.lower()
        payload = ensure_group(group_key)
        payload["rows"].append(row)
        payload["dungeon"] = payload["dungeon"] or bool(bucket_rows["dungeon"])
        payload["challenge"] = payload["challenge"] or bool(bucket_rows["challenge"])
        payload["source_tables"].update({"MonsterActorTable.json", "DungeonTable.json"})

    for row in monster_rows:
        if not isinstance(row, dict) or is_technical_creature_row(row, localizer):
            continue
        monster_id = first_text(row.get("Name"))
        if not monster_id:
            continue
        group_key = creature_group_key(row, localizer, boss=True) or monster_id.lower()
        if group_key not in grouped:
            continue
        payload = ensure_group(group_key)
        payload["rows"].append(row)
        payload["source_tables"].add("MonsterActorTable.json")

    entries: List[Dict] = []
    raw_to_entry_id: Dict[str, str] = {}
    for key, payload in sorted(grouped.items(), key=lambda item: item[0]):
        rows = [row for row in payload["rows"] if isinstance(row, dict)]
        if not rows and not payload["map_points"]:
            continue
        sample_row = choose_best_creature_row(rows, localizer) if rows else None
        sample_point = payload["map_points"][0] if payload["map_points"] else {}
        row_name_en, row_name_fr = localized_creature_names(sample_row, localizer) if sample_row else ("", "")
        point_name_en = first_text(payload.get("mapNameEn"))
        point_name_fr = first_text(payload.get("mapNameFr"), point_name_en)
        if payload["field"] and point_name_en and not payload.get("fieldBossTid"):
            name_en, name_fr = point_name_en, point_name_fr
        else:
            name_en = first_text(row_name_en, point_name_en, "Boss")
            name_fr = first_text(row_name_fr, point_name_fr, name_en)
        desc_en, desc_fr = localized_creature_descriptions(sample_row, localizer) if sample_row else ("", "")
        icon_candidates = []
        for row in rows:
            icon_candidates.extend(monster_visual_candidates(row, dictionary_by_local_key, dictionary_by_actor_id))
        icon_candidates.extend(
            [
                cleaned_field_boss_label(sample_point),
                sample_point.get("label"),
                sample_point.get("name"),
                payload.get("fieldBossIcon"),
            ]
        )
        icon_candidates.extend(
            creature_visual_overrides(
                point_name_en,
                point_name_fr,
                cleaned_field_boss_label(sample_point),
                sample_point.get("label"),
                sample_point.get("name"),
                payload.get("fieldBossTid"),
            )
        )
        icon_candidates.append(GENERIC_BOSS_ICON)
        icon = assets.resolve_stem(icon_candidates, "bosses")
        regions = unique(region for point in payload["map_points"] for region in point_regions(point))
        region_ids = unique(
            region_id
            for point in payload["map_points"]
            for region_id in (point.get("region_ids") or [point.get("region_id")])
            if region_id
        )
        monster_ids = unique(first_text(row.get("Name")) for row in rows if first_text(row.get("Name")))
        drop_group_ids = unique(first_text(row.get("DropGroupTid")) for row in rows if first_text(row.get("DropGroupTid")))
        first_drop_group_ids = unique(first_text(row.get("FirstDropGroupTid")) for row in rows if first_text(row.get("FirstDropGroupTid")))
        catch_drop_group_ids = unique(first_text(row.get("CatchDropGroupTid")) for row in rows if first_text(row.get("CatchDropGroupTid")))
        actor_tid = first_text(creature_root_actor_tid(sample_row), sample_point.get("actor_tid"), sample_point.get("actorTid"))
        lists = []
        if payload["field"]:
            lists.append("field-bosses")
        if payload["dungeon"]:
            lists.append("dungeon-bosses")
        if payload["challenge"]:
            lists.append("boss-challenges")
        lists.append("bosses")
        category_labels_en = []
        category_labels_fr = []
        if payload["field"]:
            category_labels_en.append("Field boss")
            category_labels_fr.append("Boss de terrain")
        if payload["dungeon"]:
            category_labels_en.append("Dungeon boss")
            category_labels_fr.append("Boss de donjon")
        if payload["challenge"]:
            category_labels_en.append("Boss challenge")
            category_labels_fr.append("Defier le boss")
        summary_en = first_text(", ".join(category_labels_en) + " reference.", "Boss reference.")
        summary_fr = first_text(", ".join(category_labels_fr) + ".", "Boss.")
        if payload["map_points"]:
            summary_en = f"{summary_en} {len(payload['map_points'])} tracked map locations."
            summary_fr = f"{summary_fr} {len(payload['map_points'])} emplacements de carte suivis."
        entry_id = f"boss:{slugify(key)}"
        entry = base_entry(
            entry_id=entry_id,
            slug=f"boss-{slugify(name_en or key)}",
            kind="boss",
            lists=unique(lists),
            name_en=name_en or "Boss",
            name_fr=name_fr or name_en or "Boss",
            description_en=desc_en,
            description_fr=desc_fr,
            summary_en=summary_en,
            summary_fr=summary_fr,
            icon=icon,
            rarity=rarity_payload(sample_row.get("Grade")) if sample_row else None,
            regions=regions,
            region_ids=region_ids,
            source_tables=sorted(payload["source_tables"]),
            source_ids={
                "actorTid": actor_tid,
                "monsterId": first_text(monster_ids[0] if monster_ids else ""),
            },
            map_ref=build_map_ref(
                payload["map_points"],
                point_type="boss",
                actor_tid=first_text(sample_point.get("actor_tid"), sample_point.get("actorTid"), actor_tid),
            )
            if payload["map_points"]
            else None,
            stats={"pointCount": len(payload["map_points"]), "variantCount": len(monster_ids)},
            fields={
                "actorTid": actor_tid,
                "monsterIds": monster_ids,
                "dropGroupTids": drop_group_ids,
                "firstDropGroupTids": first_drop_group_ids,
                "catchDropGroupTids": catch_drop_group_ids,
                "bossCategories": unique(
                    [
                        "field" if payload["field"] else "",
                        "dungeon" if payload["dungeon"] else "",
                        "challenge" if payload["challenge"] else "",
                    ]
                ),
            },
        )
        entries.append(entry)
        for monster_id in monster_ids:
            raw_to_entry_id[f"monster:{monster_id}"] = entry_id
    return entries, raw_to_entry_id


def build_waypoint_entries(points: List[Dict], waypoint_rows: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    point_groups: Dict[str, List[Dict]] = defaultdict(list)
    for point in points:
        if str(point.get("type") or "") != "warp-points":
            continue
        key = first_text(point.get("waypoint_id"), point.get("waypointId"), point.get("name"), point.get("id"))
        point_groups[key].append(point)
    waypoint_by_id = {first_text(row.get("Name"), row.get("string_tid")): row for row in waypoint_rows}

    entries: List[Dict] = []
    for key, group_points in sorted(point_groups.items(), key=lambda item: item[0]):
        row = waypoint_by_id.get(key)
        sample = group_points[0]
        name_en = first_text(localizer.translate(row.get("Local_Key"), "en") if row else "", display_point_name(sample, "en"))
        name_fr = first_text(localizer.translate(row.get("Local_Key"), "fr") if row else "", display_point_name(sample, "fr"))
        desc_en = first_text(localizer.translate(row.get("Local_Desc"), "en") if row else "")
        desc_fr = first_text(localizer.translate(row.get("Local_Desc"), "fr") if row else "")
        icon = assets.resolve_site_asset("site/assets/icons/warp-points.png", "waypoints") or assets.resolve_stem(
            ["Waypoint_Open", "i_waypoint"],
            "waypoints",
        )
        regions = unique(region for point in group_points for region in point_regions(point))
        region_ids = unique(
            region_id
            for point in group_points
            for region_id in (point.get("region_ids") or [point.get("region_id")])
            if region_id
        )
        entries.append(
            base_entry(
                entry_id=f"waypoint:{key}",
                slug=f"waypoint-{key}-{slugify(name_en)}",
                kind="waypoint",
                lists=["waypoints"],
                name_en=name_en or f"Waypoint {key}",
                name_fr=name_fr or name_en or f"Waypoint {key}",
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=f"{len(group_points)} tracked map anchors across {len(regions)} regions.",
                summary_fr=f"{len(group_points)} points d'ancrage suivis sur {len(regions)} r\u00e9gions.",
                icon=icon,
                regions=regions,
                region_ids=region_ids,
                source_tables=unique(["map_data.json", "WaypointTable.json"] if row else ["map_data.json"]),
                source_ids={"waypointId": key},
                map_ref=build_map_ref(
                    group_points,
                    point_type="warp-points",
                    preferred_point_id=group_points[0].get("id") or "",
                ),
                stats={"pointCount": len(group_points)},
                fields={
                    "zoneIds": row.get("Zone_Tid") if row else [],
                    "zoneGroup": row.get("Zone_Group") if row else "",
                },
            )
        )
    return entries


def build_fishing_spot_entries(points: List[Dict], zone_rows: List[Dict], assets: AssetResolver) -> List[Dict]:
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for point in points:
        if str(point.get("type") or "") != "fishing-point":
            continue
        key = first_text(point.get("source_spawn_table"), point.get("name"), point.get("id"))
        groups[key].append(point)

    zone_by_zone_tid: Dict[str, List[Dict]] = defaultdict(list)
    for row in zone_rows:
        zone_by_zone_tid[first_text(row.get("FieldFishing_ZoneTid"))].append(row)

    entries: List[Dict] = []
    for key, group_points in sorted(groups.items(), key=lambda item: item[0]):
        sample = group_points[0]
        region_ids = unique(
            region_id
            for point in group_points
            for region_id in (point.get("region_ids") or [point.get("region_id")])
            if region_id
        )
        matching_zones = [row for region_id in region_ids for row in zone_by_zone_tid.get(region_id, [])]
        fish_ids = unique(fish_id for row in matching_zones for fish_id in (row.get("AppearFish") or []))
        name_en = display_point_name(sample, "en")
        name_fr = display_point_name(sample, "fr")
        icon = assets.resolve_site_asset("site/assets/icons/fishing-point.png", "fishing") or assets.resolve_stem(
            ["Fishing", "i_interaction_fishing"],
            "fishing",
        )
        regions = unique(region for point in group_points for region in point_regions(point))
        entries.append(
            base_entry(
                entry_id=f"fishing-spot:{slugify(key)}",
                slug=f"fishing-spot-{slugify(name_en or key)}",
                kind="fishing-spot",
                lists=["fishing-spots"],
                name_en=name_en or "Fishing spot",
                name_fr=name_fr or name_en or "Fishing spot",
                summary_en=f"{len(group_points)} tracked fishing markers with {len(fish_ids)} linked fish ids.",
                summary_fr=f"{len(group_points)} marqueurs de p\u00eache suivis avec {len(fish_ids)} identifiants de poissons li\u00e9s.",
                icon=icon,
                regions=regions,
                region_ids=region_ids,
                source_tables=unique(["map_data.json", "FishingZoneActorTable.json"] if matching_zones else ["map_data.json"]),
                source_ids={"sourceSpawnTable": key},
                map_ref=build_map_ref(group_points, point_type="fishing-point"),
                stats={"pointCount": len(group_points), "fishCount": len(fish_ids)},
                fields={
                    "fishIds": fish_ids,
                    "zones": [row.get("Name") for row in matching_zones],
                },
            )
        )
    return entries


def build_dungeon_acquisition_source(
    pack_row: Dict,
    group_rate: int,
    bucket_meta: Dict,
    dungeon_row: Dict,
    dungeon_group_by_id: Dict[str, Dict],
    monster_rows_by_id: Dict[str, Dict],
    quest_names_by_id: Dict[str, Dict[str, Dict[str, str]]],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    dungeon_id = first_text(dungeon_row.get("Name"))
    if not dungeon_id:
        return None
    group_row = dungeon_group_by_id.get(first_text(dungeon_row.get("Dungeon_Group")), {})
    difficulty = localized_text(
        first_text(localizer.translate(dungeon_row.get("Local_Sub_Name"), "en"), title_case_stem(dungeon_row.get("Standard_Level"))),
        first_text(localizer.translate(dungeon_row.get("Local_Sub_Name"), "fr"), localizer.translate(dungeon_row.get("Local_Sub_Name"), "en"), title_case_stem(dungeon_row.get("Standard_Level"))),
    )
    group_name = localized_text(
        first_text(localizer.translate(group_row.get("Local_Main_Name"), "en"), localizer.translate(group_row.get("Local_Main_Sub_Name"), "en"), f"Dungeon {dungeon_id}"),
        first_text(localizer.translate(group_row.get("Local_Main_Name"), "fr"), localizer.translate(group_row.get("Local_Main_Sub_Name"), "fr"), localizer.translate(group_row.get("Local_Main_Name"), "en"), localizer.translate(group_row.get("Local_Main_Sub_Name"), "en"), f"Dungeon {dungeon_id}"),
    )
    location = localized_text(
        localizer.translate(group_row.get("Local_Main_Sub_Name"), "en"),
        localizer.translate(group_row.get("Local_Main_Sub_Name"), "fr"),
    )
    title = localized_text(group_name["en"], group_name["fr"])
    if difficulty["en"] and difficulty["en"].lower() not in title["en"].lower():
        title["en"] = f"{title['en']} · {difficulty['en']}"
    if difficulty["fr"] and difficulty["fr"].lower() not in title["fr"].lower():
        title["fr"] = f"{title['fr']} · {difficulty['fr']}"
    subtitle_en = location["en"] if location["en"] and location["en"].lower() != group_name["en"].lower() else ""
    subtitle_fr = location["fr"] if location["fr"] and location["fr"].lower() != group_name["fr"].lower() else subtitle_en
    clear_target_id = first_text(dungeon_row.get("Dungeon_Clear_Value")) if first_text(dungeon_row.get("Dungeon_Clear_Type")).lower() == "boss" else ""
    clear_target_row = monster_rows_by_id.get(clear_target_id, {})
    boss_name_en, boss_name_fr = localized_creature_names(clear_target_row, localizer) if clear_target_row else ("", "")
    boss_name = localized_text(
        first_text(boss_name_en),
        first_text(boss_name_fr, boss_name_en),
    )
    description = localized_text(
        first_text(localizer.translate(group_row.get("Local_Main_Desc"), "en"), localizer.translate(dungeon_row.get("Local_Sub_Desc"), "en")),
        first_text(localizer.translate(group_row.get("Local_Main_Desc"), "fr"), localizer.translate(dungeon_row.get("Local_Sub_Desc"), "fr"), localizer.translate(group_row.get("Local_Main_Desc"), "en"), localizer.translate(dungeon_row.get("Local_Sub_Desc"), "en")),
    )
    open_quest_id = first_text(dungeon_row.get("Open_Condition_Quest"))
    quest_name = quest_names_by_id.get(open_quest_id, {}) if open_quest_id else {}
    icon = assets.resolve_stem(
        [
            group_row.get("Dungeon_Group_Icon"),
            dungeon_row.get("DungeonPopup_theme_Image"),
            dungeon_row.get("Dungeon_theme_Image"),
            "Portal",
        ],
        "sources",
    )
    image = assets.resolve_stem(
        [
            dungeon_row.get("DungeonPopup_theme_Image"),
            dungeon_row.get("Dungeon_theme_Image"),
        ],
        "sources",
    )
    related_entry_id = f"monster:{clear_target_id}" if clear_target_id in monster_rows_by_id else ""
    rate_meta = drop_rate_metadata(pack_row, group_rate, bucket_meta)
    return {
        "id": f"dungeon:{dungeon_id}:{first_text(pack_row.get('Name'))}",
        "kind": "dungeon",
        "name": title,
        "subtitle": localized_text(subtitle_en, subtitle_fr),
        "description": description,
        "icon": icon,
        "image": image,
        "difficulty": difficulty,
        "bossName": boss_name,
        "recommendedPower": int(numeric_value(dungeon_row.get("Recommend_BattlePower")) or 0),
        "qualityMax": int(numeric_value(pack_row.get("Quality_Max")) or 0),
        "minCount": int(numeric_value(pack_row.get("Min_Cnt")) or 0),
        "maxCount": int(numeric_value(pack_row.get("Max_Cnt")) or 0),
        "priority": int(numeric_value(pack_row.get("Priority")) or 0),
        "standardLevel": first_text(pack_row.get("Standard_Level")),
        "unlockQuest": localized_text(
            first_text(quest_name.get("en", {}).get("name")),
            first_text(quest_name.get("fr", {}).get("name"), quest_name.get("en", {}).get("name")),
        ),
        "relatedEntryId": related_entry_id,
        "sourceId": dungeon_id,
        "sourceGroupId": first_text(dungeon_row.get("Reward_Tid")),
        **rate_meta,
    }


def build_monster_acquisition_source(
    pack_row: Dict,
    group_rate: int,
    bucket_meta: Dict,
    monster_row: Dict,
    source_field: str,
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    monster_id = first_text(monster_row.get("Name"))
    if not monster_id:
        return None
    actor_tid = monster_row.get("ActorTid") if isinstance(monster_row.get("ActorTid"), dict) else {"string_tid": monster_row.get("ActorTid")}
    name_en, name_fr = localized_creature_names(monster_row, localizer)
    name = localized_text(first_text(name_en, monster_id), first_text(name_fr, name_en, monster_id))
    description = localized_text(
        localizer.translate(monster_row.get("Local_Desc"), "en"),
        localizer.translate(monster_row.get("Local_Desc"), "fr"),
    )
    icon = assets.resolve_stem(
        [
            monster_row.get("UI_HUD_Portrait"),
            monster_row.get("UI_Actor_Icon_Headup_Center"),
            monster_icon_stems(actor_tid.get("string_tid") if isinstance(actor_tid, dict) else ""),
            "Monster_Normal_01",
        ],
        "sources",
    )
    if source_field == "FirstDropGroupTid":
        source_note = localized_text("First-drop reward", "Premier butin")
    elif source_field == "CatchDropGroupTid":
        source_note = localized_text("Capture reward", "Butin de capture")
    else:
        source_note = localized_text("Monster drop", "Butin de monstre")
    grade = localized_text(humanize_token(monster_row.get("Grade")), humanize_token(monster_row.get("Grade")))
    rate_meta = drop_rate_metadata(pack_row, group_rate, bucket_meta)
    return {
        "id": f"monster:{monster_id}:{first_text(pack_row.get('Name'))}",
        "kind": "monster",
        "name": name,
        "subtitle": source_note,
        "description": description,
        "icon": icon,
        "image": "",
        "grade": grade,
        "qualityMax": int(numeric_value(pack_row.get("Quality_Max")) or 0),
        "minCount": int(numeric_value(pack_row.get("Min_Cnt")) or 0),
        "maxCount": int(numeric_value(pack_row.get("Max_Cnt")) or 0),
        "priority": int(numeric_value(pack_row.get("Priority")) or 0),
        "standardLevel": first_text(pack_row.get("Standard_Level")),
        "dropSourceType": (
            "first-drop"
            if source_field == "FirstDropGroupTid"
            else "catch-drop"
            if source_field == "CatchDropGroupTid"
            else "monster-drop"
        ),
        "relatedEntryId": f"monster:{monster_id}",
        "sourceId": monster_id,
        "sourceGroupId": first_text(monster_row.get(source_field)),
        **rate_meta,
    }


def prettify_source_seed(value: object) -> str:
    text = first_text(value)
    if not text:
        return ""
    text = re.sub(r"^ch\d+_", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^equipd?_", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^rewardbox_", "", text, flags=re.IGNORECASE)
    text = re.sub(r"_0?\d+$", "", text)
    text = re.sub(r"^(boss|elite|dungeon)_", "", text, flags=re.IGNORECASE)
    return humanize_token(text)


def match_source_creature_row(seed: object, monster_rows: List[Dict], localizer: Localizer) -> Optional[Dict]:
    seed_tokens = set(boss_match_tokens(seed))
    if not seed_tokens:
        return None
    wants_elite = "elite" in first_text(seed).lower()
    wants_boss = "boss" in first_text(seed).lower()
    best_score = -1
    best_row = None
    for row in monster_rows:
        if not isinstance(row, dict) or is_technical_creature_row(row, localizer):
            continue
        actor_tid = row.get("ActorTid") if isinstance(row.get("ActorTid"), dict) else {"string_tid": row.get("ActorTid")}
        name_en, _ = localized_creature_names(row, localizer)
        row_tokens = set(
            boss_match_tokens(
                row.get("Local_Key"),
                name_en,
                row.get("NPC_Job"),
                actor_tid.get("string_tid"),
            )
        )
        hits = seed_tokens & row_tokens
        if not hits:
            continue
        score = len(hits) * 10
        if seed_tokens.issubset(row_tokens):
            score += len(seed_tokens) * 3
        grade = normalize_grade(row.get("Grade"))
        if wants_elite and grade == "elite":
            score += 4
        if wants_boss and grade == "boss":
            score += 4
        portrait = first_text(row.get("UI_HUD_Portrait"))
        if portrait and portrait not in GENERIC_MONSTER_PORTRAITS:
            score += 2
        if score > best_score:
            best_score = score
            best_row = row
    return best_row if best_score >= 10 else None


def build_interaction_acquisition_source(
    pack_row: Dict,
    group_rate: int,
    bucket_meta: Dict,
    interaction_row: Dict,
    monster_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    interaction_id = first_text(interaction_row.get("Name"))
    drop_group_id = first_text(interaction_row.get("DropGroupTid"))
    if not interaction_id or not drop_group_id:
        return None
    button_tid = first_text(interaction_row.get("ButtonTid")).lower()
    if "dungeon" in button_tid:
        source_kind = "dungeon"
        source_note = localized_text("Dungeon reward cube", "Cube de recompense de donjon")
        label_seed = drop_group_id
    elif "boss" in button_tid:
        source_kind = "monster"
        source_note = localized_text("Boss reward cube", "Cube de recompense de boss")
        label_seed = first_text(pack_row.get("DropPack_Key"), drop_group_id)
    else:
        source_kind = "monster"
        source_note = localized_text("Elite reward cube", "Cube de recompense elite")
        label_seed = first_text(pack_row.get("DropPack_Key"), drop_group_id)
    matched_row = match_source_creature_row(label_seed, monster_rows, localizer) or match_source_creature_row(drop_group_id, monster_rows, localizer)
    if matched_row:
        monster_id = first_text(matched_row.get("Name"))
        name_en, name_fr = localized_creature_names(matched_row, localizer)
        name = localized_text(first_text(name_en, prettify_source_seed(label_seed), drop_group_id), first_text(name_fr, name_en, prettify_source_seed(label_seed), drop_group_id))
        description = localized_text(
            localizer.translate(matched_row.get("Local_Desc"), "en"),
            localizer.translate(matched_row.get("Local_Desc"), "fr"),
        )
        actor_tid = matched_row.get("ActorTid") if isinstance(matched_row.get("ActorTid"), dict) else {"string_tid": matched_row.get("ActorTid")}
        icon = assets.resolve_stem(
            [
                matched_row.get("UI_HUD_Portrait"),
                matched_row.get("UI_Actor_Icon_Headup_Center"),
                monster_icon_stems(actor_tid.get("string_tid") if isinstance(actor_tid, dict) else ""),
            ],
            "sources",
        )
        related_entry_id = f"monster:{monster_id}" if monster_id else ""
        grade = localized_text(humanize_token(matched_row.get("Grade")), humanize_token(matched_row.get("Grade")))
    else:
        label = first_text(prettify_source_seed(label_seed), prettify_source_seed(drop_group_id), source_note["en"])
        name = localized_text(label, label)
        description = localized_text("", "")
        icon = assets.resolve_stem([interaction_row.get("ActorHudIcon"), interaction_row.get("ButtonTid")], "sources")
        related_entry_id = ""
        grade = localized_text("", "")
    rate_meta = drop_rate_metadata(pack_row, group_rate, bucket_meta)
    return {
        "id": f"interaction:{interaction_id}:{first_text(pack_row.get('Name'))}",
        "kind": source_kind,
        "name": name,
        "subtitle": source_note,
        "description": description,
        "icon": icon,
        "image": "",
        "grade": grade,
        "qualityMax": int(numeric_value(pack_row.get("Quality_Max")) or 0),
        "minCount": int(numeric_value(pack_row.get("Min_Cnt")) or 0),
        "maxCount": int(numeric_value(pack_row.get("Max_Cnt")) or 0),
        "priority": int(numeric_value(pack_row.get("Priority")) or 0),
        "standardLevel": first_text(pack_row.get("Standard_Level")),
        "dropSourceType": "reward-cube",
        "relatedEntryId": related_entry_id,
        "sourceId": interaction_id,
        "sourceGroupId": drop_group_id,
        **rate_meta,
    }


def build_drop_group_acquisition_source(
    pack_row: Dict,
    group_rate: int,
    bucket_meta: Dict,
    group_row: Dict,
    monster_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    drop_group_id = first_text(group_row.get("Name"))
    if not drop_group_id:
        return None
    pack_keys = [first_text(value) for value in (group_row.get("DropPack_Key") or []) if first_text(value)]
    group_lower = drop_group_id.lower()
    is_boss = "boss" in group_lower or any("boss" in value.lower() for value in pack_keys)
    is_elite = "elite" in group_lower or any("elite" in value.lower() for value in pack_keys)
    if not is_boss and not is_elite:
        return None

    specific_pack_keys = [
        value
        for value in pack_keys
        if value
        and not re.match(
            r"^(?:ch\d+_(?:boss|elite)|mastery_|hawk_feeding_|equip(?:d|_|$)|specialproduct_|item_|reward_)",
            value,
            flags=re.IGNORECASE,
        )
    ]
    label_seed = first_text(*specific_pack_keys, drop_group_id)
    matched_row = match_source_creature_row(label_seed, monster_rows, localizer) or match_source_creature_row(drop_group_id, monster_rows, localizer)
    if not matched_row:
        return None

    monster_id = first_text(matched_row.get("Name"))
    name_en, name_fr = localized_creature_names(matched_row, localizer)
    name = localized_text(first_text(name_en, prettify_source_seed(label_seed), drop_group_id), first_text(name_fr, name_en, prettify_source_seed(label_seed), drop_group_id))
    description = localized_text(
        localizer.translate(matched_row.get("Local_Desc"), "en"),
        localizer.translate(matched_row.get("Local_Desc"), "fr"),
    )
    actor_tid = matched_row.get("ActorTid") if isinstance(matched_row.get("ActorTid"), dict) else {"string_tid": matched_row.get("ActorTid")}
    icon = assets.resolve_stem(
        [
            matched_row.get("UI_HUD_Portrait"),
            matched_row.get("UI_Actor_Icon_Headup_Center"),
            monster_icon_stems(actor_tid.get("string_tid") if isinstance(actor_tid, dict) else ""),
        ],
        "sources",
    )
    rate_meta = drop_rate_metadata(pack_row, group_rate, bucket_meta)
    return {
        "id": f"group:{drop_group_id}:{first_text(pack_row.get('Name'))}",
        "kind": "monster",
        "name": name,
        "subtitle": localized_text("Boss reward", "Butin de boss") if is_boss else localized_text("Elite reward", "Butin d'elite"),
        "description": description,
        "icon": icon,
        "image": "",
        "grade": localized_text(humanize_token(matched_row.get("Grade")), humanize_token(matched_row.get("Grade"))),
        "qualityMax": int(numeric_value(pack_row.get("Quality_Max")) or 0),
        "minCount": int(numeric_value(pack_row.get("Min_Cnt")) or 0),
        "maxCount": int(numeric_value(pack_row.get("Max_Cnt")) or 0),
        "priority": int(numeric_value(pack_row.get("Priority")) or 0),
        "standardLevel": first_text(pack_row.get("Standard_Level")),
        "dropSourceType": "monster-drop",
        "relatedEntryId": f"monster:{monster_id}" if monster_id else "",
        "sourceId": drop_group_id,
        "sourceGroupId": drop_group_id,
        **rate_meta,
    }


def build_quest_acquisition_source(
    pack_row: Dict,
    quest_id: str,
    quest_entry_id: str,
    quest_locale: Dict[str, Dict[str, str]],
    assets: AssetResolver,
) -> Optional[Dict]:
    if not quest_id:
        return None
    name_en = first_text(quest_locale.get("en", {}).get("name"), f"Quest {quest_id}")
    name_fr = first_text(quest_locale.get("fr", {}).get("name"), f"Quete {quest_id}", name_en)
    return {
        "id": f"quest:{quest_id}:{first_text(pack_row.get('Name'))}",
        "kind": "quest",
        "name": localized_text(name_en, name_fr),
        "subtitle": localized_text("Quest reward", "Recompense de quete"),
        "description": localized_text("", ""),
        "icon": assets.resolve_stem(["i_quest_1_non", "Quest", "scroll"], "sources"),
        "image": "",
        "qualityMax": int(numeric_value(pack_row.get("Quality_Max")) or 0),
        "minCount": int(numeric_value(pack_row.get("Min_Cnt")) or 0),
        "maxCount": int(numeric_value(pack_row.get("Max_Cnt")) or 0),
        "priority": int(numeric_value(pack_row.get("Priority")) or 0),
        "standardLevel": first_text(pack_row.get("Standard_Level")),
        "rateMode": "guaranteed",
        "relatedEntryId": quest_entry_id,
        "sourceId": quest_id,
        "sourceGroupId": first_text(pack_row.get("DropPack_Key")),
    }


def build_recipe_acquisition_source(recipe_entry: Dict) -> Optional[Dict]:
    recipe_id = first_text(recipe_entry.get("fields", {}).get("recipeId"), recipe_entry.get("id"))
    if not recipe_id:
        return None
    recipe_type_label = recipe_entry.get("fields", {}).get("recipeTypeLabel") or {}
    return {
        "id": f"recipe:{recipe_id}",
        "kind": "recipe",
        "name": recipe_entry.get("locale", {}),
        "subtitle": localized_text(
            first_text(recipe_type_label.get("en"), "Recipe"),
            first_text(recipe_type_label.get("fr"), "Recette"),
        ),
        "description": localized_text(
            first_text(recipe_entry.get("locale", {}).get("en", {}).get("summary")),
            first_text(recipe_entry.get("locale", {}).get("fr", {}).get("summary"), recipe_entry.get("locale", {}).get("en", {}).get("summary")),
        ),
        "icon": first_text(recipe_entry.get("icon")),
        "image": first_text(recipe_entry.get("image")),
        "minCount": 1,
        "maxCount": 1,
        "rateMode": "guaranteed",
        "relatedEntryId": first_text(recipe_entry.get("id")),
        "sourceId": recipe_id,
        "sourceGroupId": recipe_id,
    }


def build_event_acquisition_source(
    mission_row: Dict,
    group_row: Dict,
    condition_row: Dict,
    event_row: Dict,
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    mission_id = first_text(mission_row.get("Name"))
    if not mission_id:
        return None
    event_title = localized_text(
        first_text(localizer.translate(event_row.get("Event_Title"), "en"), localizer.translate(group_row.get("Group_Title_LocalKey"), "en"), f"Event {first_text(event_row.get('Name'))}"),
        first_text(localizer.translate(event_row.get("Event_Title"), "fr"), localizer.translate(group_row.get("Group_Title_LocalKey"), "fr"), localizer.translate(event_row.get("Event_Title"), "en"), localizer.translate(group_row.get("Group_Title_LocalKey"), "en"), f"Event {first_text(event_row.get('Name'))}"),
    )
    subtitle = localized_text(
        localizer.translate(event_row.get("Event_Page_Text_1"), "en"),
        localizer.translate(event_row.get("Event_Page_Text_1"), "fr"),
    )
    description = localized_text(
        first_text(localizer.translate(event_row.get("Event_Page_Text_2"), "en"), localizer.translate(condition_row.get("Local_Key"), "en")),
        first_text(localizer.translate(event_row.get("Event_Page_Text_2"), "fr"), localizer.translate(condition_row.get("Local_Key"), "fr"), localizer.translate(event_row.get("Event_Page_Text_2"), "en"), localizer.translate(condition_row.get("Local_Key"), "en")),
    )
    icon = assets.resolve_stem(
        [
            event_row.get("Event_Tab_Img"),
            "Mission",
        ],
        "sources",
    )
    return {
        "id": f"event:{mission_id}",
        "kind": "event",
        "name": event_title,
        "subtitle": localized_text(
            first_text(subtitle["en"], localizer.translate(group_row.get("Group_Title_LocalKey"), "en")),
            first_text(subtitle["fr"], localizer.translate(group_row.get("Group_Title_LocalKey"), "fr"), subtitle["en"]),
        ),
        "description": description,
        "icon": icon,
        "image": "",
        "conditionType": localized_text(
            first_text(localizer.format(condition_row.get("Local_Key"), "en"), humanize_token(condition_row.get("Condition_Type"))),
            first_text(localizer.format(condition_row.get("Local_Key"), "fr"), localizer.format(condition_row.get("Local_Key"), "en"), humanize_token(condition_row.get("Condition_Type"))),
        ),
        "conditionValue": int(numeric_value(condition_row.get("Condition_Value_Count")) or 0),
        "qualityMax": max(int(numeric_value(mission_row.get("Reward_Quality_1")) or 0), int(numeric_value(mission_row.get("Reward_Quality_2")) or 0), int(numeric_value(mission_row.get("Reward_Quality_3")) or 0)),
        "relatedEntryId": "",
        "sourceId": mission_id,
        "sourceGroupId": first_text(group_row.get("Name")),
        "rateMode": "guaranteed",
    }


def drop_pack_bucket_key(pack_row: Dict) -> Tuple[str, str]:
    return (first_text(pack_row.get("DropPack_Key")), first_text(pack_row.get("Standard_Level")))


def build_drop_bucket_index(drop_pack_rows: List[Dict]) -> Dict[Tuple[str, str], Dict]:
    buckets: Dict[Tuple[str, str], Dict] = defaultdict(lambda: {"totalRate": 0, "itemCounts": Counter()})
    for row in drop_pack_rows:
        if not isinstance(row, dict) or first_text(row.get("DropType")).lower() != "item":
            continue
        bucket = buckets[drop_pack_bucket_key(row)]
        bucket["totalRate"] += int(numeric_value(row.get("Rate")) or 0)
        item_id = first_text(row.get("Item_Tid"))
        if item_id:
            bucket["itemCounts"][item_id] += 1
    return dict(buckets)


def drop_rate_metadata(pack_row: Dict, group_rate: int, bucket_meta: Optional[Dict]) -> Dict:
    rate = int(numeric_value(pack_row.get("Rate")) or 0)
    group_rate_value = int(group_rate or 0)
    total_rate = int((bucket_meta or {}).get("totalRate") or 0)
    item_id = first_text(pack_row.get("Item_Tid"))
    item_occurrences = int(((bucket_meta or {}).get("itemCounts") or {}).get(item_id, 0))
    drop_percent = 0.0
    if rate and total_rate > 0:
        drop_percent = (rate / total_rate) * 100.0
        if 0 < group_rate_value <= 10000:
            drop_percent *= group_rate_value / 10000.0
    is_exact_percent = bool(rate and total_rate == 10000 and item_occurrences == 1 and group_rate_value in {0, 10000})
    payload = {
        "rateRaw": rate,
        "rateWeightTotal": total_rate,
        "groupRateRaw": group_rate_value,
        "rateMode": "estimated-percent" if drop_percent else "",
    }
    if drop_percent:
        payload["rateDisplayPct"] = round(drop_percent, 4)
    if is_exact_percent:
        payload["rateMode"] = "percent"
    return payload


def build_item_acquisition_sources(
    item_ids: Iterable[str],
    drop_pack_rows: List[Dict],
    drop_group_rows: List[Dict],
    dungeon_rows: List[Dict],
    dungeon_group_rows: List[Dict],
    monster_rows: List[Dict],
    interaction_rows: List[Dict],
    recipe_entries: List[Dict],
    event_mission_rows: List[Dict],
    event_group_rows: List[Dict],
    event_condition_rows: List[Dict],
    event_rows: List[Dict],
    quest_entries: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Dict[str, List[Dict]]:
    def normalized_lookup_key(value: object) -> str:
        return first_text(value).strip().lower()

    item_id_set = set(unique(item_ids))
    drop_bucket_index = build_drop_bucket_index(drop_pack_rows)
    drop_groups_by_pack: Dict[str, List[Dict]] = defaultdict(list)
    dungeons_by_reward_tid: Dict[str, List[Dict]] = defaultdict(list)
    dungeon_group_by_id = {
        normalized_lookup_key(row.get("Name")): row
        for row in dungeon_group_rows
        if isinstance(row, dict) and normalized_lookup_key(row.get("Name"))
    }
    monster_rows_by_id = {
        first_text(row.get("Name")): row
        for row in monster_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    monsters_by_drop_group: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)
    interactions_by_drop_group: Dict[str, List[Dict]] = defaultdict(list)
    recipes_by_reward_item: Dict[str, List[Dict]] = defaultdict(list)
    event_groups_by_id = {
        first_text(row.get("Name")): row
        for row in event_group_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    event_conditions_by_id = {
        first_text(row.get("Name")): row
        for row in event_condition_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    events_by_id = {
        first_text(row.get("Name")): row
        for row in event_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    quest_names_by_id = {
        first_text(entry.get("fields", {}).get("questId")): entry.get("locale", {})
        for entry in quest_entries
        if first_text(entry.get("fields", {}).get("questId"))
    }
    quest_entry_ids_by_id = {
        first_text(entry.get("fields", {}).get("questId")): first_text(entry.get("id"))
        for entry in quest_entries
        if first_text(entry.get("fields", {}).get("questId")) and first_text(entry.get("id"))
    }

    for row in drop_group_rows:
        if not isinstance(row, dict):
            continue
        for pack_key in row.get("DropPack_Key") or []:
            resolved_key = normalized_lookup_key(pack_key)
            if resolved_key:
                drop_groups_by_pack[resolved_key].append(row)

    for row in dungeon_rows:
        if not isinstance(row, dict):
            continue
        reward_tid = normalized_lookup_key(row.get("Reward_Tid"))
        if reward_tid:
            dungeons_by_reward_tid[reward_tid].append(row)

    for row in monster_rows:
        if not isinstance(row, dict):
            continue
        for field_name in ("DropGroupTid", "FirstDropGroupTid", "CatchDropGroupTid"):
            group_id = normalized_lookup_key(row.get(field_name))
            if group_id:
                monsters_by_drop_group[group_id].append((field_name, row))

    for row in interaction_rows:
        if not isinstance(row, dict):
            continue
        group_id = normalized_lookup_key(row.get("DropGroupTid"))
        if group_id:
            interactions_by_drop_group[group_id].append(row)

    for entry in recipe_entries:
        if not isinstance(entry, dict) or first_text(entry.get("kind")) != "recipe":
            continue
        reward_item_id = first_text(entry.get("fields", {}).get("rewardItemId"))
        if reward_item_id:
            recipes_by_reward_item[reward_item_id].append(entry)

    sources_by_item: Dict[str, List[Dict]] = defaultdict(list)
    seen_source_ids: Dict[str, set] = defaultdict(set)

    def append_source(item_id: str, source: Optional[Dict]) -> None:
        if not source:
            return
        source_id = first_text(source.get("id"))
        if not source_id or source_id in seen_source_ids[item_id]:
            return
        seen_source_ids[item_id].add(source_id)
        sources_by_item[item_id].append(source)

    for row in drop_pack_rows:
        if not isinstance(row, dict):
            continue
        item_id = first_text(row.get("Item_Tid"))
        if not item_id or item_id not in item_id_set or first_text(row.get("DropType")).lower() != "item":
            continue
        pack_key = normalized_lookup_key(row.get("DropPack_Key"))
        if not pack_key:
            continue
        bucket_meta = drop_bucket_index.get(drop_pack_bucket_key(row), {})
        quest_id = extract_quest_id(row.get("DropPack_Key"), row.get("Name"))
        if quest_id and "reward" in pack_key:
            append_source(
                item_id,
                build_quest_acquisition_source(
                    row,
                    quest_id,
                    quest_entry_ids_by_id.get(quest_id, ""),
                    quest_names_by_id.get(quest_id, {}),
                    assets,
                ),
            )
        for group_row in drop_groups_by_pack.get(pack_key, []):
            group_id = normalized_lookup_key(group_row.get("Name"))
            group_pack_keys = [normalized_lookup_key(value) for value in (group_row.get("DropPack_Key") or [])]
            group_pack_rates = [int(numeric_value(value) or 0) for value in (group_row.get("DropPack_Rate") or [])]
            group_rate = 0
            group_linked_source = False
            for index, candidate_key in enumerate(group_pack_keys):
                if candidate_key == pack_key:
                    group_rate = group_pack_rates[index] if index < len(group_pack_rates) else 0
                    break
            dungeon_candidates = list(dungeons_by_reward_tid.get(group_id, []))
            standard_level = first_text(row.get("Standard_Level"))
            if standard_level and dungeon_candidates:
                matched = [candidate for candidate in dungeon_candidates if first_text(candidate.get("Standard_Level")) == standard_level]
                if matched:
                    dungeon_candidates = matched
                elif len(dungeon_candidates) > 1:
                    dungeon_candidates = []
            for dungeon_row in dungeon_candidates:
                source = build_dungeon_acquisition_source(
                    row,
                    group_rate,
                    bucket_meta,
                    dungeon_row,
                    dungeon_group_by_id,
                    monster_rows_by_id,
                    quest_names_by_id,
                    localizer,
                    assets,
                )
                append_source(item_id, source)
                if source and first_text(source.get("relatedEntryId")):
                    group_linked_source = True
            for source_field, monster_row in monsters_by_drop_group.get(group_id, []):
                source = build_monster_acquisition_source(row, group_rate, bucket_meta, monster_row, source_field, localizer, assets)
                append_source(item_id, source)
                if source and first_text(source.get("relatedEntryId")):
                    group_linked_source = True
            for interaction_row in interactions_by_drop_group.get(group_id, []):
                source = build_interaction_acquisition_source(row, group_rate, bucket_meta, interaction_row, monster_rows, localizer, assets)
                append_source(item_id, source)
                if source and first_text(source.get("relatedEntryId")):
                    group_linked_source = True
            if not group_linked_source:
                append_source(item_id, build_drop_group_acquisition_source(row, group_rate, bucket_meta, group_row, monster_rows, localizer, assets))

    for item_id, recipe_rows in recipes_by_reward_item.items():
        if item_id not in item_id_set:
            continue
        for recipe_entry in recipe_rows:
            append_source(item_id, build_recipe_acquisition_source(recipe_entry))

    for mission_row in event_mission_rows:
        if not isinstance(mission_row, dict):
            continue
        reward_item_ids = [first_text(mission_row.get(f"Reward_Tid_{index}")) for index in range(1, 4)]
        if not any(reward_item_ids):
            continue
        group_row = event_groups_by_id.get(first_text(mission_row.get("FixedGroup_Tid")), {})
        condition_row = event_conditions_by_id.get(first_text(mission_row.get("Finish_ConditionTid")), {})
        event_row = events_by_id.get(first_text(group_row.get("Event_Data_Tid")), {})
        source = build_event_acquisition_source(mission_row, group_row, condition_row, event_row, localizer, assets)
        for reward_item_id in reward_item_ids:
            if reward_item_id and reward_item_id in item_id_set:
                append_source(reward_item_id, source)

    kind_order = {"dungeon": 0, "monster": 1, "quest": 2, "recipe": 3, "event": 4}
    for item_id, rows in sources_by_item.items():
        rows.sort(
            key=lambda row: (
                kind_order.get(first_text(row.get("kind")), 99),
                int(numeric_value(row.get("recommendedPower")) or 0),
                int(numeric_value(row.get("priority")) or 0),
                int(numeric_value(row.get("qualityMax")) or 0),
                first_text(row.get("name", {}).get("en")),
            )
        )
    return dict(sources_by_item)


def remap_acquisition_source_entries(
    acquisition_sources_by_item: Dict[str, List[Dict]],
    raw_to_entry_id: Dict[str, str],
) -> Dict[str, List[Dict]]:
    remapped: Dict[str, List[Dict]] = {}
    for item_id, rows in acquisition_sources_by_item.items():
        updated_rows = []
        for row in rows:
            payload = dict(row)
            related_entry_id = first_text(payload.get("relatedEntryId"))
            if related_entry_id and related_entry_id in raw_to_entry_id:
                payload["relatedEntryId"] = raw_to_entry_id[related_entry_id]
            updated_rows.append(payload)
        remapped[item_id] = dedupe_acquisition_sources(updated_rows)
    return remapped


def build_item_entries(
    item_ids: Iterable[str],
    localizer: Localizer,
    assets: AssetResolver,
    source_relations: Dict[str, Dict[str, List[str]]],
    stat_info_rows: List[Dict],
    option_static_rows: List[Dict],
    option_list_rows: List[Dict],
    option_random_rows: List[Dict],
    set_rows: List[Dict],
    set_value_rows: List[Dict],
    passive_base_rows: List[Dict],
    passive_group_rows: List[Dict],
    acquisition_sources_by_item: Optional[Dict[str, List[Dict]]] = None,
    disassembly_by_item: Optional[Dict[str, Dict]] = None,
    recycled_from_by_item: Optional[Dict[str, List[Dict]]] = None,
) -> List[Dict]:
    entries: List[Dict] = []
    stat_info_by_id = build_stat_info_index(stat_info_rows)
    option_static_by_name = {
        first_text(row.get("Name")): row
        for row in option_static_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    option_list_by_group: Dict[str, List[Dict]] = defaultdict(list)
    for row in option_list_rows:
        if not isinstance(row, dict):
            continue
        group_id = normalize_token(row.get("Group_ID"))
        if group_id:
            option_list_by_group[group_id].append(row)
    option_random_by_group: Dict[str, List[Dict]] = defaultdict(list)
    for row in option_random_rows:
        if not isinstance(row, dict):
            continue
        group_id = normalize_token(row.get("Group_ID"))
        if group_id:
            option_random_by_group[group_id].append(row)
    passive_base_by_id = {
        normalize_token(row.get("Name")): row
        for row in passive_base_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    set_rows_by_id = {
        normalize_token(row.get("Name")): row
        for row in set_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    set_value_rows_by_group: Dict[str, List[Dict]] = defaultdict(list)
    for row in set_value_rows:
        if not isinstance(row, dict):
            continue
        group_id = normalize_token(row.get("SetGroupTId"))
        if group_id:
            set_value_rows_by_group[group_id].append(row)
    passive_group_by_id: Dict[str, List[Dict]] = defaultdict(list)
    for row in passive_group_rows:
        if not isinstance(row, dict):
            continue
        group_id = normalize_token(row.get("GroupID"))
        if group_id:
            passive_group_by_id[group_id].append(row)
    set_members_by_group: Dict[str, List[str]] = defaultdict(list)
    for source_item_id, source_item_row in localizer.resolver.item_index.items():
        if not isinstance(source_item_row, dict):
            continue
        for set_key in source_item_row.get("SetKeyList") or []:
            normalized = normalize_token(set_key)
            if normalized:
                set_members_by_group[normalized].append(source_item_id)

    for item_id in sorted(unique(item_ids)):
        row = localizer.item_row(item_id)
        if not row:
            continue
        name_en = localizer.item_name(item_id, "en")
        name_fr = localizer.item_name(item_id, "fr")
        desc_en = localizer.item_desc(item_id, "en")
        desc_fr = localizer.item_desc(item_id, "fr")
        icon = assets.resolve_stem(item_icon_candidates(localizer, row, item_id), "items")
        rarity = rarity_payload(row.get("Grade"))
        item_type = first_text(row.get("ItemDetailType"), row.get("ItemDivision"), row.get("ItemType"))
        lists = []
        if source_relations.get(item_id, {}).get("nodes"):
            lists.append("materials")
        if first_text(row.get("ItemType")).lower() == "equip":
            detail_list = ITEM_DETAIL_LISTS.get(first_text(row.get("ItemDetailType")).lower())
            if detail_list and not (detail_list == "armor" and normalize_token(row.get("ItemDivision")) == "bindarmor"):
                lists.append(detail_list)
            lists.append("equipment")
        if not lists:
            lists.append("items")
        lists = unique(lists)
        classification = first_text(row.get("ItemDivision"), row.get("ItemDetailType"), row.get("ItemType"))
        relation_map = source_relations.get(item_id, {})
        related_characters = unique(relation_map.get("characters", []))
        related_costumes = unique(relation_map.get("costumes", []))
        related_recipes = unique(relation_map.get("recipes", []))
        related_nodes = unique(relation_map.get("nodes", []))
        acquisition_sources = list(acquisition_sources_by_item.get(item_id, [])) if acquisition_sources_by_item else []
        disassembly = dict(disassembly_by_item.get(item_id, {})) if disassembly_by_item else {}
        recycled_from = list(recycled_from_by_item.get(item_id, [])) if recycled_from_by_item else []
        related_acquisition_entries = unique(source.get("relatedEntryId") for source in acquisition_sources if first_text(source.get("relatedEntryId")))
        recipe_count = list_count(relation_map.get("recipes", []))
        source_count = list_count(relation_map.get("nodes", []))
        character_count = list_count(relation_map.get("characters", []))
        costume_count = list_count(relation_map.get("costumes", []))
        acquisition_count = len(acquisition_sources)
        disassembly_count = len(disassembly.get("outputs") or [])
        recycled_from_count = len(recycled_from)
        growth_effects = [
            payload
            for payload in [
                *[
                    build_growth_effect_payload(effect_id, "main", option_static_by_name, stat_info_by_id, localizer, assets)
                    for effect_id in (row.get("Growth_Ability_Main") or [])
                ],
                *[
                    build_growth_effect_payload(effect_id, "sub", option_static_by_name, stat_info_by_id, localizer, assets)
                    for effect_id in (row.get("Growth_Ability_Sub") or [])
                ],
            ]
            if payload
        ]
        option_pool_ids = [first_text(option_id) for option_id in (row.get("Equip_Option") or []) if first_text(option_id)]
        option_pool_counter = Counter(option_pool_ids)
        equipment_option_pools = [
            {
                "id": group_id,
                "groupId": group_id,
                "slotCount": slot_count,
                "rows": build_option_pool_rows(group_id, option_list_by_group, option_random_by_group, stat_info_by_id, localizer, assets),
            }
            for group_id, slot_count in option_pool_counter.items()
        ]
        equipment_option_pools = [pool for pool in equipment_option_pools if pool.get("rows")]
        equipment_passives = build_equipment_passive_rows(row.get("Equip_Passive") or [], passive_base_by_id, passive_group_by_id, localizer, assets)
        equipment_sets = build_equipment_set_payloads(
            row.get("SetKeyList") or [],
            set_rows_by_id,
            set_value_rows_by_group,
            passive_base_by_id,
            passive_group_by_id,
            set_members_by_group,
            localizer,
            assets,
        )
        if "weapons" in lists:
            summary_en = f"{character_count} heroes, {recipe_count} linked recipes, {acquisition_count} acquisition sources."
            summary_fr = f"{character_count} heros, {recipe_count} recettes liees, {acquisition_count} sources d'obtention."
        elif "armor" in lists or "accessories" in lists or ("equipment" in lists and costume_count):
            summary_en = f"{character_count} heroes, {costume_count} costumes, {recipe_count} linked recipes, {acquisition_count} acquisition sources."
            summary_fr = f"{character_count} heros, {costume_count} costumes, {recipe_count} recettes liees, {acquisition_count} sources d'obtention."
        else:
            summary_en = f"{recipe_count} recipes, {character_count} characters, {source_count} map sources, {acquisition_count} acquisition sources."
            summary_fr = f"{recipe_count} recettes, {character_count} personnages, {source_count} sources carte, {acquisition_count} sources d'obtention."
        entries.append(
            base_entry(
                entry_id=f"item:{item_id}",
                slug=f"item-{item_id}-{slugify(name_en or item_id)}",
                kind="item",
                lists=unique(lists),
                name_en=name_en or item_id,
                name_fr=name_fr or name_en or item_id,
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=summary_en,
                summary_fr=summary_fr,
                icon=icon,
                rarity=rarity,
                classification=classification,
                source_tables=unique(
                    [
                        f"ItemTable_Data_{row.get('ItemType')}.json" if row.get("ItemType") else "ItemTable_Data_*.json",
                        "Option_StaticTable.json" if growth_effects else "",
                        "ItemTable_OptionListData.json" if equipment_option_pools else "",
                        "Option_RandomTable.json" if equipment_option_pools else "",
                        "EquipSetOptionTable.json" if equipment_sets else "",
                        "EquipSetOptionValueTable.json" if equipment_sets else "",
                        "ItemTable_Equip_Passive_Base.json" if equipment_passives else "",
                        "ItemTable_Equip_Passive_Group.json" if equipment_passives else "",
                        "DisassembleData.json" if disassembly else "",
                        "Disassemble_Level.json" if disassembly.get("hasLevelScaling") else "",
                    ]
                ),
                source_ids={"itemId": item_id},
                related=unique(
                    related_nodes
                    + related_recipes
                    + relation_map.get("pets", [])
                    + relation_map.get("avatars", [])
                    + relation_map.get("fish", [])
                    + related_characters
                    + related_costumes
                    + related_acquisition_entries
                ),
                stats={
                    "recipeCount": recipe_count,
                    "sourceCount": source_count,
                    "characterCount": character_count,
                    "costumeCount": costume_count,
                    "acquisitionCount": acquisition_count,
                    "disassemblyCount": disassembly_count,
                    "recycledFromCount": recycled_from_count,
                    "equipmentEffectCount": len(growth_effects) + sum(len(pool.get("rows") or []) for pool in equipment_option_pools) + len(equipment_passives),
                    "setCount": len(equipment_sets),
                },
                fields={
                    "itemId": item_id,
                    "itemType": row.get("ItemType"),
                    "itemDetailType": row.get("ItemDetailType"),
                    "itemDivision": row.get("ItemDivision"),
                    "iconName": row.get("IconName"),
                    "battleType": first_text(row.get("BattleType")),
                    "element": first_text(row.get("Element")),
                    "reinforceMax": int(numeric_value(row.get("Reinforce_Max")) or 0),
                    "promotionGroup": first_text(row.get("PromotionGroupID")),
                    "expGroup": first_text(row.get("ExpGroupID")),
                    "sellCostType": first_text(row.get("Sell_CostType")),
                    "sellCostValue": int(numeric_value(row.get("Sell_CostValue")) or 0),
                    "maxUseCount": int(numeric_value(row.get("Max_Use_Count")) or 0),
                    "equipModels": unique(row.get("Equip_Model") or []),
                    "useFunctions": [
                        {
                            "type": first_text(use_row.get("Type")),
                            "subType": first_text(use_row.get("SubType")),
                            "value": first_text(use_row.get("Value")),
                        }
                        for use_row in (row.get("UseFunction") or [])
                        if isinstance(use_row, dict)
                    ],
                    "relatedCharacters": related_characters,
                    "relatedCostumes": related_costumes,
                    "relatedRecipes": related_recipes,
                    "relatedNodes": related_nodes,
                    "acquisitionSources": acquisition_sources,
                    "recycledFrom": recycled_from,
                    "disassembly": disassembly,
                    "equipmentGrowthEffects": growth_effects,
                    "equipmentOptionPools": equipment_option_pools,
                    "equipmentPassives": equipment_passives,
                    "equipmentSets": equipment_sets,
                    "searchTerms": unique(relation_map.get("searchTerms", []) + flatten_search_terms(acquisition_sources)),
                },
                sort_index=100000 - int(numeric_value((rarity or {}).get("rank")) or 0) * 10000,
            )
        )
    return entries


def build_loot_by_source_entry(
    acquisition_sources_by_item: Dict[str, List[Dict]],
    localizer: Localizer,
    assets: AssetResolver,
) -> Dict[str, List[Dict]]:
    loot_by_entry: Dict[str, List[Dict]] = defaultdict(list)
    seen_loot_ids: Dict[str, set] = defaultdict(set)

    for item_id, source_rows in acquisition_sources_by_item.items():
        item_payload = build_item_link_payload(item_id, 0, localizer, assets, bucket="items")
        if not item_payload:
            continue
        for source in source_rows:
            related_entry_id = first_text(source.get("relatedEntryId"))
            source_kind = first_text(source.get("kind"))
            if not related_entry_id or source_kind not in {"monster", "dungeon"}:
                continue
            loot_id = "|".join(
                [
                    item_id,
                    related_entry_id,
                    source_kind,
                    first_text(source.get("sourceGroupId")),
                    first_text(source.get("standardLevel")),
                    first_text(source.get("dropSourceType")),
                    str(int(numeric_value(source.get("minCount")) or 0)),
                    str(int(numeric_value(source.get("maxCount")) or 0)),
                ]
            )
            if loot_id in seen_loot_ids[related_entry_id]:
                continue
            seen_loot_ids[related_entry_id].add(loot_id)
            loot_row = dict(item_payload)
            loot_row.update(
                {
                    "id": loot_id,
                    "sourceName": source.get("name"),
                    "sourceSubtitle": source.get("subtitle"),
                    "difficulty": source.get("difficulty"),
                    "bossName": source.get("bossName"),
                    "recommendedPower": int(numeric_value(source.get("recommendedPower")) or 0),
                    "minCount": int(numeric_value(source.get("minCount")) or 0),
                    "maxCount": int(numeric_value(source.get("maxCount")) or 0),
                    "qualityMax": int(numeric_value(source.get("qualityMax")) or 0),
                    "priority": int(numeric_value(source.get("priority")) or 0),
                    "standardLevel": first_text(source.get("standardLevel")),
                    "sourceKind": source_kind,
                    "dropSourceType": first_text(source.get("dropSourceType")),
                    "rateMode": first_text(source.get("rateMode")),
                    "rateDisplayPct": numeric_value(source.get("rateDisplayPct")),
                    "rateRaw": int(numeric_value(source.get("rateRaw")) or 0),
                    "rateWeightTotal": int(numeric_value(source.get("rateWeightTotal")) or 0),
                }
            )
            loot_by_entry[related_entry_id].append(loot_row)

    for rows in loot_by_entry.values():
        rows.sort(
            key=lambda row: (
                0
                if row.get("dropSourceType") == "first-drop"
                else 1
                if row.get("sourceKind") == "monster"
                else 2,
                -int(bool(row.get("rateDisplayPct"))),
                -int(numeric_value(row.get("rateDisplayPct")) * 1000),
                -int(numeric_value(row.get("rateRaw")) or 0),
                -int(numeric_value((row.get("rarity") or {}).get("rank")) or 0),
                first_text(row.get("name", {}).get("en"), row.get("itemId")),
            )
        )
    return dict(loot_by_entry)


def recipe_relation_item_ids(row: Dict) -> Tuple[List[str], List[str]]:
    materials = []
    rewards = []
    for index in range(1, 8):
        item_id = first_text(row.get(f"Material_Tid_{index}"))
        count = int(row.get(f"Material_Cnt_{index}") or 0)
        if item_id and count > 0:
            materials.append(item_id)
    for index in range(1, 4):
        item_id = first_text(row.get(f"Reward_Item_Tid_{index}"))
        count = int(row.get(f"Reward_Item_Cnt_{index}") or 0)
        if item_id and count > 0:
            rewards.append(item_id)
    return materials, rewards


def parse_numeric_tokens(value: object) -> List[int]:
    if isinstance(value, list):
        return [int(numeric_value(item) or 0) for item in value if numeric_value(item)]
    return [int(match) for match in re.findall(r"\d+", first_text(value))]


def recipe_variant_rank(function_type: object) -> int:
    token = first_text(function_type).lower()
    if "manual" in token or token == "production":
        return 0
    if "auto" in token:
        return 1
    return 2


def recipe_signature(recipe_type: str, row: Dict) -> Tuple:
    reward_items = [first_text(row.get(f"Reward_Item_Tid_{index}")) for index in range(1, 4) if first_text(row.get(f"Reward_Item_Tid_{index}"))]
    reward_focus = first_text(row.get("Show_Reward_Tid"), reward_items[0] if reward_items else "")
    return recipe_type, reward_focus


def recipe_sort_index(recipe_type: str, row: Dict) -> int:
    tab_order = RECIPE_TAB_ORDER.get(recipe_type, 9)
    if recipe_type == "production":
        group_order = PRODUCTION_GROUP_ORDER.get(first_text(row.get("Group")).lower(), 99)
        recipe_group_tokens = parse_numeric_tokens(row.get("Recipe_Group"))
        subgroup_order = recipe_group_tokens[0] if recipe_group_tokens else 0
        progress_order = int(numeric_value(row.get("Contents_Level")) or 0)
    else:
        group_order = int(numeric_value(row.get("Group")) or 0)
        subgroup_order = 0
        progress_order = int(numeric_value(row.get("Show_Reward_Lv")) or numeric_value(row.get("Contents_Level")) or 0)
    priority_order = int(numeric_value(row.get("Priority")) or 0)
    return (
        tab_order * 100_000_000
        + group_order * 1_000_000
        + subgroup_order * 1_000
        + progress_order * 10
        + min(priority_order, 9)
    )


def recipe_choice_key(recipe_type: str, row: Dict) -> Tuple:
    reward_focus = first_text(row.get("Show_Reward_Tid"))
    return (
        recipe_variant_rank(row.get("Function_Type")),
        int(numeric_value(row.get("Priority")) or 0),
        recipe_sort_index(recipe_type, row),
        reward_focus,
        first_text(row.get("Name")),
    )


def recipe_dictionary_sort_index(
    reward_item_id: object,
    recipe_type: str,
    row: Dict,
    localizer: "Localizer",
    dictionary_by_local_key: Dict[str, Dict],
) -> int:
    item_row = localizer.item_row(reward_item_id) or {}
    local_key = first_text(item_row.get("Local_Key"))
    dictionary_row = dictionary_by_local_key.get(local_key)
    if dictionary_row:
        class_sort = int(numeric_value(dictionary_row.get("Class_Sort")) or 0)
        group_sort = int(numeric_value(dictionary_row.get("Group_Sort")) or 0)
        list_sort = int(numeric_value(dictionary_row.get("List_Sort")) or 0)
        dictionary_id = int(numeric_value(dictionary_row.get("Dictionary_ID")) or 0)
        return class_sort * 1_000_000_000 + group_sort * 10_000_000 + list_sort * 10_000 + dictionary_id
    return 9_000_000_000 + recipe_sort_index(recipe_type, row)


def build_recipe_entries(
    binding_rows: List[Dict],
    cooking_rows: List[Dict],
    production_rows: List[Dict],
    making_rows: List[Dict],
    dictionary_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Tuple[List[Dict], Dict[str, Dict[str, List[str]]], List[str]]:
    entries: List[Dict] = []
    relations: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    referenced_items: List[str] = []

    dictionary_by_local_key = {
        first_text(row.get("Local_Key")): row
        for row in dictionary_rows
        if isinstance(row, dict) and first_text(row.get("Local_Key"))
    }
    recipe_groups: Dict[Tuple, Dict] = {}

    def variant_payload(recipe_type: str, row: Dict, materials: List[str], rewards: List[str]) -> Dict:
        return {
            "id": f"recipe-variant:{recipe_type}:{row.get('Name')}",
            "recipeId": row.get("Name"),
            "functionType": row.get("Function_Type"),
            "priority": int(numeric_value(row.get("Priority")) or 0),
            "contentsLevel": int(numeric_value(row.get("Contents_Level")) or 0),
            "showRewardLevel": int(numeric_value(row.get("Show_Reward_Lv")) or 0),
            "group": row.get("Group"),
            "recipeGroup": row.get("Recipe_Group"),
            "materials": [
                {
                    "itemId": item_id,
                    "count": int(row.get(f"Material_Cnt_{index}") or 0),
                }
                for index, item_id in enumerate(materials, start=1)
            ],
            "rewards": [
                {
                    "itemId": item_id,
                    "count": int(row.get(f"Reward_Item_Cnt_{index}") or 0),
                }
                for index, item_id in enumerate(rewards, start=1)
            ],
        }

    def add_entry(group: Dict) -> None:
        primary = group["primary"]
        recipe_type = primary["recipeType"]
        row = primary["row"]
        variants = sorted(group["variants"], key=lambda item: recipe_choice_key(item["recipeType"], item["row"]))
        materials = primary["materials"]
        rewards = primary["rewards"]
        reward_focus = first_text(row.get("Show_Reward_Tid"), rewards[0] if rewards else "")
        reward_name_en = localizer.item_name(reward_focus, "en")
        reward_name_fr = localizer.item_name(reward_focus, "fr")
        title_key = first_text(row.get("Recipe_Title_Local_Key"))
        name_en = first_text(localizer.translate(title_key, "en"), reward_name_en, f"{recipe_type.title()} recipe {row.get('Name')}")
        name_fr = first_text(localizer.translate(title_key, "fr"), reward_name_fr, name_en)
        item_row = localizer.item_row(reward_focus)
        reward_rarity = rarity_payload(item_row.get("Grade")) if item_row else None
        recipe_replacements = []
        recipe_desc_key = row.get("Show_Reward_Local")
        if item_row:
            recipe_replacements = item_row.get("Food_Local_Replace") or item_row.get("Local_Replace") or []
            recipe_desc_key = first_text(item_row.get("Food_Local_Desc"), row.get("Show_Reward_Local"))
        desc_en = first_text(localizer.format(recipe_desc_key, "en", recipe_replacements), localizer.item_desc(reward_focus, "en"))
        desc_fr = first_text(localizer.format(recipe_desc_key, "fr", recipe_replacements), localizer.item_desc(reward_focus, "fr"))
        recipe_label = RECIPE_TYPE_LABELS.get(recipe_type, {"en": title_case_stem(recipe_type), "fr": title_case_stem(recipe_type)})
        ingredient_label_en = pluralize(len(materials), "ingredient", "ingredients")
        ingredient_label_fr = pluralize(len(materials), "ingredient", "ingredients")
        reward_label_en = pluralize(len(rewards), "reward", "rewards")
        reward_label_fr = pluralize(len(rewards), "recompense", "recompenses")
        icon = assets.resolve_stem(item_icon_candidates(localizer, item_row or {}, reward_focus), "recipes")
        entry_id = f"recipe:{recipe_type}:{row.get('Name')}"
        variant_count = len(variants)
        variant_suffix_en = f", {variant_count} variants" if variant_count > 1 else ""
        variant_suffix_fr = f", {variant_count} variantes" if variant_count > 1 else ""
        sort_index = recipe_dictionary_sort_index(reward_focus, recipe_type, row, localizer, dictionary_by_local_key)
        related_items = unique(item_id for variant in variants for item_id in variant["materials"] + variant["rewards"])
        recipe_lists = ["engravings", "recipes"] if recipe_type == "binding" else ["recipes", f"{recipe_type}-recipes"]
        entry = base_entry(
            entry_id=entry_id,
            slug=f"recipe-{recipe_type}-{row.get('Name')}-{slugify(name_en)}",
            kind="recipe",
            lists=recipe_lists,
            name_en=name_en,
            name_fr=name_fr,
            description_en=desc_en,
            description_fr=desc_fr,
            summary_en=f"{len(materials)} {ingredient_label_en}, {len(rewards)} {reward_label_en}{variant_suffix_en}. {recipe_label['en']} recipe.",
            summary_fr=f"{len(materials)} {ingredient_label_fr}, {len(rewards)} {reward_label_fr}{variant_suffix_fr}. Recette de {recipe_label['fr'].lower()}.",
            icon=icon,
            rarity=reward_rarity,
            classification=recipe_label["en"],
            source_tables=unique(variant["tableName"] for variant in variants),
            source_ids={
                "recipeId": row.get("Name"),
                "recipeIds": unique(first_text(variant["row"].get("Name")) for variant in variants if first_text(variant["row"].get("Name"))),
                "rewardItemId": reward_focus,
            },
            related=unique(f"item:{item_id}" for item_id in related_items),
            stats={"ingredientCount": len(materials), "rewardCount": len(rewards), "variantCount": variant_count},
            fields={
                "recipeType": recipe_type,
                "recipeTypeLabel": recipe_label,
                "functionType": row.get("Function_Type"),
                "group": row.get("Group"),
                "recipeGroup": row.get("Recipe_Group"),
                "contentsLevel": row.get("Contents_Level"),
                "priority": row.get("Priority"),
                "showRewardLevel": row.get("Show_Reward_Lv"),
                "rewardItemId": reward_focus,
                "dictionarySort": sort_index,
                "materials": [
                    {
                        "itemId": item_id,
                        "count": int(row.get(f"Material_Cnt_{index}") or 0),
                    }
                    for index, item_id in enumerate(materials, start=1)
                ],
                "rewards": [
                    {
                        "itemId": item_id,
                        "count": int(row.get(f"Reward_Item_Cnt_{index}") or 0),
                    }
                    for index, item_id in enumerate(rewards, start=1)
                ],
                "variants": [variant_payload(recipe_type, variant["row"], variant["materials"], variant["rewards"]) for variant in variants],
            },
            sort_index=sort_index,
        )
        entries.append(entry)
        for item_id in related_items:
            relations[item_id]["recipes"].append(entry_id)

    def register_candidate(recipe_type: str, row: Dict, table_name: str) -> None:
        materials, rewards = recipe_relation_item_ids(row)
        key = recipe_signature(recipe_type, row)
        candidate = {
            "recipeType": recipe_type,
            "row": row,
            "tableName": table_name,
            "materials": materials,
            "rewards": rewards,
        }
        referenced_items.extend(materials + rewards)
        current = recipe_groups.get(key)
        if not current:
            recipe_groups[key] = {
                "primary": candidate,
                "variants": [candidate],
            }
            return
        current["variants"].append(candidate)
        if recipe_choice_key(recipe_type, row) < recipe_choice_key(current["primary"]["recipeType"], current["primary"]["row"]):
            current["primary"] = candidate

    for row in binding_rows:
        if isinstance(row, dict):
            register_candidate("binding", row, "BindingRecipeTable.json")
    for row in cooking_rows:
        if isinstance(row, dict):
            register_candidate("cooking", row, "CookingRecipeTable.json")
    for row in production_rows:
        if isinstance(row, dict):
            register_candidate("production", row, "ProductionRecipeTable.json")
    for row in making_rows:
        if isinstance(row, dict):
            register_candidate("production", row, "MakingRecipe.json")
    for group in sorted(
        recipe_groups.values(),
        key=lambda item: (
            recipe_dictionary_sort_index(
                first_text(item["primary"]["row"].get("Show_Reward_Tid"), item["primary"]["rewards"][0] if item["primary"]["rewards"] else ""),
                item["primary"]["recipeType"],
                item["primary"]["row"],
                localizer,
                dictionary_by_local_key,
            ),
            first_text(item["primary"]["row"].get("Show_Reward_Tid")),
            first_text(item["primary"]["row"].get("Name")),
        ),
    ):
        add_entry(group)
    return entries, relations, referenced_items


def build_skill_payload(
    slot_key: str,
    skill_id: str,
    pc_skill_by_id: Dict[str, Dict],
    shared_skill_by_id: Dict[str, Dict],
    pc_behavior_by_id: Dict[str, Dict],
    shared_behavior_by_id: Dict[str, Dict],
    buff_by_id: Dict[str, Dict],
    stat_info_by_id: Dict[str, Dict],
    localizer: Localizer,
    assets: AssetResolver,
) -> Optional[Dict]:
    skill_key = first_text(skill_id)
    if not skill_key:
        return None
    is_pc_skill = skill_key in pc_skill_by_id
    row = pc_skill_by_id.get(skill_key) or shared_skill_by_id.get(skill_key)
    if not row:
        return None
    slot = SKILL_SLOT_LABELS.get(slot_key, {"en": humanize_token(slot_key), "fr": humanize_token(slot_key)})
    localized_name_en = first_text(localizer.translate(row.get("Local_Key"), "en"))
    localized_name_fr = first_text(localizer.translate(row.get("Local_Key"), "fr"))
    name_en = first_text(localized_name_en, humanize_token(skill_key))
    name_fr = first_text(localized_name_fr, name_en)
    if prefer_slot_skill_name(skill_key, name_en) or (not localized_name_en and slot_key in {"SkillAerialAttack", "AvoidanceSkill", "AirAvoidanceSkill", "Just_AvoidanceSkill"}):
        name_en = slot["en"]
        name_fr = slot["fr"]
    desc_en = localizer.format(row.get("Local_Desc"), "en", row.get("Local_Replace"))
    desc_fr = localizer.format(row.get("Local_Desc"), "fr", row.get("Local_Replace"))
    sub_desc_key = first_text(row.get("Local_SubDesc"))
    sub_desc_en = localizer.format(sub_desc_key, "en", row.get("Local_Replace"))
    sub_desc_fr = localizer.format(sub_desc_key, "fr", row.get("Local_Replace"))
    effects = build_skill_effect_payloads(
        row,
        pc_behavior_by_id if is_pc_skill else shared_behavior_by_id,
        buff_by_id,
        stat_info_by_id,
        localizer,
    )
    return {
        "id": skill_key,
        "slot": slot,
        "name": {"en": name_en, "fr": name_fr},
        "description": {"en": desc_en, "fr": desc_fr},
        "subDescription": {"en": sub_desc_en, "fr": sub_desc_fr},
        "icon": assets.resolve_stem([row.get("Icon"), row.get("IconHighlight")], "skills"),
        "function": first_text(row.get("Function")),
        "category": first_text(row.get("SkillCategory")),
        "division": first_text(row.get("Division")),
        "target": first_text(row.get("Target")),
        "damageType": first_text(row.get("SkillDamType")),
        "range": int(numeric_value(row.get("SkillRange"))),
        "chargeTime": numeric_value(row.get("ChargeTime")),
        "coolTime": numeric_value(row.get("CoolTime")),
        "keyInputType": first_text(row.get("KeyInputType")),
        "useType": first_text(row.get("UseType")),
        "staminaCost": int(numeric_value(row.get("UseStamina")) or 0),
        "staminaRate": int(numeric_value(row.get("UseStaminaRate")) or 0),
        "hpCost": int(numeric_value(row.get("UseHP")) or 0),
        "hpRate": int(numeric_value(row.get("UseHPRate")) or 0),
        "ultimateSkillId": first_text(row.get("UltimateReinforceSkillTid")),
        "breakSkillId": first_text(row.get("BreakSkillTid")),
        "linkSkills": unique(flatten_behavior_names(row.get("LinkSkill"))),
        "effects": effects,
        "searchTerms": unique(
            [
                skill_key,
                name_en,
                name_fr,
                desc_en,
                desc_fr,
                sub_desc_en,
                sub_desc_fr,
                row.get("Function"),
                row.get("SkillCategory"),
                row.get("Division"),
                row.get("SkillDamType"),
                row.get("Target"),
                *flatten_search_terms(effects),
            ]
        ),
    }


def build_character_entries(
    hero_actor_rows: List[Dict],
    hero_profile_rows: List[Dict],
    hero_stat_group_rows: List[Dict],
    hero_mastery_rows: List[Dict],
    common_mastery_catalog: Dict[str, Dict],
    default_skill_rows: List[Dict],
    default_skill_weapon_rows: List[Dict],
    pc_skill_rows: List[Dict],
    shared_skill_rows: List[Dict],
    pc_skill_behavior_rows: List[Dict],
    shared_skill_behavior_rows: List[Dict],
    buff_rows: List[Dict],
    stat_info_rows: List[Dict],
    mastery_catalog: Dict[str, Dict],
    localizer: Localizer,
    assets: AssetResolver,
    costume_ids_by_hero: Dict[str, List[str]],
) -> List[Dict]:
    profile_by_id = {first_text(row.get("Name")): row for row in hero_profile_rows if isinstance(row, dict)}
    stat_group_by_id = {first_text(row.get("Name")): row for row in hero_stat_group_rows if isinstance(row, dict)}
    hero_mastery_by_id = {first_text(row.get("Name")): row for row in hero_mastery_rows if isinstance(row, dict)}
    default_skill_by_id = {first_text(row.get("Name")): row for row in default_skill_rows if isinstance(row, dict)}
    default_style_by_key = {
        first_text(row.get("DefaultSkillGroupKey")): row
        for row in default_skill_weapon_rows
        if isinstance(row, dict) and int(numeric_value(row.get("Potential_Level"))) == 0
    }
    potential_rows_by_key: Dict[str, List[Dict]] = defaultdict(list)
    for row in default_skill_weapon_rows:
        if not isinstance(row, dict):
            continue
        style_key = first_text(row.get("DefaultSkillGroupKey"))
        if style_key and int(numeric_value(row.get("Potential_Level"))) > 0:
            potential_rows_by_key[style_key].append(row)
    pc_skill_by_id = {first_text(row.get("Name")): row for row in pc_skill_rows if isinstance(row, dict)}
    shared_skill_by_id = {first_text(row.get("Name")): row for row in shared_skill_rows if isinstance(row, dict)}
    pc_behavior_by_id = {normalize_token(row.get("Name")): row for row in pc_skill_behavior_rows if isinstance(row, dict) and first_text(row.get("Name"))}
    shared_behavior_by_id = {normalize_token(row.get("Name")): row for row in shared_skill_behavior_rows if isinstance(row, dict) and first_text(row.get("Name"))}
    buff_by_id = {first_text(row.get("Name")): row for row in buff_rows if isinstance(row, dict) and first_text(row.get("Name"))}
    stat_info_by_id = {
        normalize_token(row.get("Name")): row
        for row in stat_info_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }

    def build_potential_levels(style_key: str, base_style_row: Dict) -> List[Dict]:
        levels = []
        previous_row = base_style_row or {}
        ordered_rows = sorted(
            potential_rows_by_key.get(style_key, []),
            key=lambda item: int(numeric_value(item.get("Potential_Level")) or 0),
        )
        for potential_row in ordered_rows:
            bonuses = [
                bonus
                for bonus in (
                    build_ability_payload(bonus_row.get("TargetAbil"), bonus_row.get("Value"), stat_info_by_id, localizer, assets)
                    for bonus_row in (potential_row.get("GradePassiveStat") or [])
                    if isinstance(bonus_row, dict)
                )
                if bonus
            ]
            changed_slots = []
            for skill_field in SKILL_SLOT_LABELS:
                if first_text(potential_row.get(skill_field)) and first_text(potential_row.get(skill_field)) != first_text(previous_row.get(skill_field)):
                    changed_slots.append(SKILL_SLOT_LABELS.get(skill_field, {"en": humanize_token(skill_field), "fr": humanize_token(skill_field)}))
            desc_en = localizer.format(potential_row.get("Local_Key"), "en", potential_row.get("Local_Replace"))
            desc_fr = localizer.format(potential_row.get("Local_Key"), "fr", potential_row.get("Local_Replace"))
            levels.append(
                {
                    "id": first_text(potential_row.get("Name"), style_key),
                    "level": int(numeric_value(potential_row.get("Potential_Level")) or 0),
                    "description": {
                        "en": desc_en or f"Potential level {int(numeric_value(potential_row.get('Potential_Level')) or 0)}",
                        "fr": desc_fr or f"Niveau de potentiel {int(numeric_value(potential_row.get('Potential_Level')) or 0)}",
                    },
                    "bonuses": bonuses,
                    "changedSlots": changed_slots,
                }
            )
            previous_row = potential_row
        return levels

    entries: List[Dict] = []
    for row in hero_actor_rows:
        if not isinstance(row, dict):
            continue
        hero_id = first_text(row.get("Name"))
        if not hero_id or hero_id not in profile_by_id:
            continue
        actor_key = row.get("ActorTid", {}).get("string_tid") if isinstance(row.get("ActorTid"), dict) else row.get("ActorTid")
        name_en = first_text(localizer.translate(row.get("Local_Key"), "en"), hero_id)
        name_fr = first_text(localizer.translate(row.get("Local_Key"), "fr"), name_en)
        desc_en = localizer.format(row.get("Local_Desc"), "en")
        desc_fr = localizer.format(row.get("Local_Desc"), "fr")
        profile_row = profile_by_id.get(hero_id, {})
        stat_group_row = stat_group_by_id.get(first_text(row.get("StatGroupTid")), {})
        hero_mastery_row = hero_mastery_by_id.get(hero_id, {})
        loadout_row = default_skill_by_id.get(first_text(row.get("Base_Skill_Key")), {})
        hero_show_item_id = first_text(row.get("Hero_Show_Item"))
        hero_show_item_row = localizer.item_row(hero_show_item_id) or {}
        image = assets.resolve_stem(
            [
                row.get("Portrait_Big"),
                row.get("Portrait_Combine_PC"),
                row.get("Portrait_Combine_Mobile"),
                row.get("Portrait_List"),
                row.get("UI_Gacha_Icon_Result"),
                item_icon_candidates(localizer, hero_show_item_row, hero_show_item_id),
                hero_portrait_stems(actor_key),
            ],
            "characters",
        )
        icon = assets.resolve_stem(
            [
                row.get("Portrait_Gacha"),
                row.get("Portrait_HUD"),
                row.get("Portrait_Slot"),
                row.get("Portrait_Tag"),
                row.get("UI_Gacha_Icon_Result"),
                item_icon_candidates(localizer, hero_show_item_row, hero_show_item_id),
                hero_portrait_stems(actor_key),
            ],
            "characters",
        )

        potential_item = build_item_link_payload(row.get("Hero_Potential_Item"), 1, localizer, assets, bucket="mastery")
        mastery_activation_materials = [
            payload
            for payload in (
                build_item_link_payload(material_id, material_count, localizer, assets, bucket="mastery")
                for material_id, material_count in zip(
                    hero_mastery_row.get("Weapon_Mastery_Activate_MaterialTIds") or [],
                    hero_mastery_row.get("Weapon_Mastery_Activate_MaterialValue") or [],
                )
            )
            if payload
        ]
        common_mastery = common_mastery_catalog.get(first_text(hero_mastery_row.get("Common_Mastery_Tid"))) or {}

        profile = []
        for field_key, label, source_key in PROFILE_FIELDS:
            value = localize_value(localizer, profile_row.get(source_key))
            if not value["en"] and not value["fr"]:
                continue
            profile.append({"id": field_key, "label": label, "value": value})

        base_stats = []
        for stat_key, label in CHARACTER_BASE_STAT_FIELDS:
            if stat_group_row.get(stat_key) in (None, "", []):
                continue
            formatted_value = format_ability_value(stat_key, stat_group_row.get(stat_key))
            base_stats.append(
                {
                    "id": stat_key,
                    "label": label,
                    "value": {"en": formatted_value, "fr": formatted_value},
                }
            )

        default_equipment = []
        equipment_by_style: Dict[str, Dict] = {}
        for item_id in row.get("Hero_Default_Equip") or []:
            equip_id = first_text(item_id)
            if not equip_id:
                continue
            item_row = localizer.item_row(equip_id) or {}
            item_name_en = first_text(localizer.item_name(equip_id, "en"), equip_id)
            item_name_fr = first_text(localizer.item_name(equip_id, "fr"), item_name_en)
            item_division = first_text(item_row.get("ItemDivision"), item_row.get("ItemDetailType"))
            normalized_style = normalize_token(item_division)
            equipment_by_style[normalized_style] = {
                "itemId": equip_id,
                "name": {"en": item_name_en, "fr": item_name_fr},
                "icon": assets.resolve_stem(
                    [
                        *item_icon_candidates(localizer, item_row, equip_id),
                        f"UI_T_Mastery_Weapon_{first_text(item_row.get('ItemDivision'), item_row.get('ItemDetailType'))}",
                    ],
                    "items",
                ),
                "type": localized_enum(item_division, STYLE_LABELS),
            }
            default_equipment.append(equipment_by_style[normalized_style])

        weapon_styles = []
        total_potential_levels = 0
        search_terms = [hero_id, actor_key, row.get("CharacterTid"), row.get("Kind")]
        for slot_index in range(1, 4):
            weapon_type = first_text(loadout_row.get(f"WeaponType0{slot_index}"))
            style_key = first_text(loadout_row.get(f"WeaponType0{slot_index}Value"))
            if not weapon_type or not style_key:
                continue
            style_row = default_style_by_key.get(style_key, {})
            style_token = normalize_token(weapon_type)
            element = localized_enum(loadout_row.get(f"WeaponType0{slot_index}_Element"), ELEMENT_LABELS)
            role = localized_enum(loadout_row.get(f"WeaponType0{slot_index}_Roll"), ROLE_LABELS)
            style_label = localized_enum(weapon_type, STYLE_LABELS)
            linked_item = equipment_by_style.get(style_token)
            skills = []
            for skill_field in SKILL_SLOT_LABELS:
                payload = build_skill_payload(
                    skill_field,
                    first_text(style_row.get(skill_field)),
                    pc_skill_by_id,
                    shared_skill_by_id,
                    pc_behavior_by_id,
                    shared_behavior_by_id,
                    buff_by_id,
                    stat_info_by_id,
                    localizer,
                    assets,
                )
                if payload:
                    skills.append(payload)
                    search_terms.extend(payload.get("searchTerms", []))
            potential_levels = build_potential_levels(style_key, style_row)
            total_potential_levels += len(potential_levels)
            style_entry = {
                "id": style_key,
                "weaponType": weapon_type,
                "styleToken": style_token,
                "label": style_label,
                "element": element,
                "role": role,
                "itemId": linked_item.get("itemId") if linked_item else "",
                "icon": linked_item.get("icon") if linked_item else "",
                "skills": skills,
                "potentialLevels": potential_levels,
                "mastery": mastery_catalog.get(style_token) or {},
            }
            weapon_styles.append(style_entry)
            search_terms.extend(
                [
                    style_key,
                    style_label["en"],
                    style_label["fr"],
                    element["en"],
                    element["fr"],
                    role["en"],
                    role["fr"],
                ]
            )

        costume_ids = costume_ids_by_hero.get(hero_id, [])
        related = unique(
            [f"item:{entry['itemId']}" for entry in default_equipment]
            + [f"costume:{costume_id}" for costume_id in costume_ids]
        )
        total_skills = sum(len(style.get("skills", [])) for style in weapon_styles)
        common_mastery_node_count = sum(len(group.get("nodes", [])) for group in common_mastery.get("groups", []))
        entries.append(
            base_entry(
                entry_id=f"character:{hero_id}",
                slug=f"character-{hero_id}-{slugify(name_en)}",
                kind="character",
                lists=["characters"],
                name_en=name_en,
                name_fr=name_fr,
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=f"{len(weapon_styles)} weapon styles, {total_skills} tracked skills, {len(costume_ids)} costumes, and {common_mastery_node_count} shared mastery nodes.",
                summary_fr=f"{len(weapon_styles)} styles d'armes, {total_skills} competences suivies, {len(costume_ids)} costumes et {common_mastery_node_count} noeuds de maitrise partagee.",
                icon=icon,
                image=image,
                rarity=rarity_payload(row.get("Grade")),
                classification=first_text(row.get("Kind")),
                source_tables=[
                    "HeroActorTable.json",
                    "HeroMastery.json",
                    "HeroCommonMastery.json",
                    "HeroProfileInfo.json",
                    "DefaultSkillTable.json",
                    "DefaultSkillWeaponTypeTable.json",
                    "PC_SkillTable.json",
                    "SkillTable.json",
                    "PC_SkillBehaviorTable.json",
                    "SkillBehaviorTable.json",
                ],
                source_ids={"heroId": hero_id},
                related=related,
                stats={
                    "weaponStyleCount": len(weapon_styles),
                    "skillCount": total_skills,
                    "costumeCount": len(costume_ids),
                    "masteryNodeCount": common_mastery_node_count,
                    "potentialLevelCount": total_potential_levels,
                },
                fields={
                    "heroId": hero_id,
                    "actorKey": actor_key,
                    "profile": profile,
                    "baseStats": base_stats,
                    "potentialItem": potential_item,
                    "masteryActivationMaterials": mastery_activation_materials,
                    "commonMastery": common_mastery,
                    "defaultEquipment": default_equipment,
                    "weaponStyles": weapon_styles,
                    "searchTerms": unique(search_terms),
                },
            )
        )
    return entries


def build_costume_entries(
    costume_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
    hero_entries: List[Dict],
) -> Tuple[List[Dict], List[str]]:
    hero_name_by_id = {
        first_text(entry.get("fields", {}).get("heroId")): {
            "en": entry.get("locale", {}).get("en", {}).get("name", ""),
            "fr": entry.get("locale", {}).get("fr", {}).get("name", ""),
        }
        for entry in hero_entries
    }
    entries: List[Dict] = []
    referenced_items: List[str] = []
    for row in costume_rows:
        if not isinstance(row, dict):
            continue
        costume_id = first_text(row.get("Name"))
        item_id = first_text(row.get("ItemID"))
        if not costume_id or not item_id:
            continue
        referenced_items.append(item_id)
        hero_id = first_text((row.get("Show_Condition_Value") or [""])[0])
        hero_name = hero_name_by_id.get(hero_id, {"en": hero_id, "fr": hero_id})
        item_row = localizer.item_row(item_id) or {}
        name_en = first_text(localizer.item_name(item_id, "en"), localizer.translate(row.get("Local_Key"), "en"), costume_id)
        name_fr = first_text(localizer.item_name(item_id, "fr"), localizer.translate(row.get("Local_Key"), "fr"), name_en)
        desc_en = first_text(localizer.item_desc(item_id, "en"), localizer.format(row.get("Desc_Key"), "en"))
        desc_fr = first_text(localizer.item_desc(item_id, "fr"), localizer.format(row.get("Desc_Key"), "fr"))
        icon = assets.resolve_stem(unique([row.get("Icon")] + item_icon_candidates(localizer, item_row or {}, item_id)), "costumes")
        image = assets.resolve_stem(
            costume_image_stems(
                row.get("Change_Model"),
                hero_name["en"],
                hero_name["fr"],
            ),
            "costumes",
        )
        related = unique([f"character:{hero_id}" if hero_id else "", f"item:{item_id}"])
        search_terms = unique(
            [
                costume_id,
                item_id,
                hero_id,
                hero_name["en"],
                hero_name["fr"],
                row.get("Change_Model"),
                row.get("Open_Condition"),
                row.get("Show_Condition"),
            ]
        )
        entries.append(
            base_entry(
                entry_id=f"costume:{costume_id}",
                slug=f"costume-{costume_id}-{slugify(name_en)}",
                kind="costume",
                lists=["costumes"],
                name_en=name_en,
                name_fr=name_fr,
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=short_summary(desc_en, f"{hero_name['en']} costume unlock entry."),
                summary_fr=short_summary(desc_fr, f"Entree de costume pour {hero_name['fr']}."),
                icon=icon,
                image=image,
                rarity=rarity_payload(item_row.get("Grade")),
                classification=first_text(item_row.get("ItemDetailType"), "Costume"),
                source_tables=["CostumeTable.json", "ItemTable_Data_Equip.json"],
                source_ids={"costumeId": costume_id, "itemId": item_id, "heroId": hero_id},
                related=related,
                stats={"heroLinked": 1 if hero_id else 0},
                fields={
                    "heroId": hero_id,
                    "heroName": hero_name,
                    "itemId": item_id,
                    "unlockCondition": row.get("Open_Condition"),
                    "unlockValue": row.get("Open_Condition_Value"),
                    "showCondition": row.get("Show_Condition"),
                    "showValue": row.get("Show_Condition_Value"),
                    "modelKey": row.get("Change_Model"),
                    "isDefault": int(numeric_value(row.get("Default"))),
                    "searchTerms": search_terms,
                },
            )
        )
    return entries, referenced_items


def build_effect_entries(
    buff_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
    stat_info_rows: List[Dict],
) -> List[Dict]:
    grouped_rows: Dict[str, List[Dict]] = defaultdict(list)
    stat_info_by_id = {
        normalize_token(row.get("Name")): row
        for row in stat_info_rows
        if isinstance(row, dict) and first_text(row.get("Name"))
    }
    for row in buff_rows:
        if not isinstance(row, dict):
            continue
        effect_side = "debuffs" if "debuff" in first_text(row.get("Type")).lower() else "buffs"
        able_type = row.get("AbleType") if isinstance(row.get("AbleType"), dict) else {}
        name_key = first_text(row.get("Local_Key"))
        desc_key = first_text(row.get("Local_Desc"))
        if not first_text(name_key, desc_key):
            continue
        key = "|".join([effect_side, (name_key or desc_key).lower(), (desc_key or name_key).lower()])
        grouped_rows[key].append(row)

    entries: List[Dict] = []
    for group_key, rows in sorted(grouped_rows.items(), key=lambda item: item[0]):
        sample = rows[0]
        effect_list = "debuffs" if group_key.startswith("debuffs|") else "buffs"
        name_en = first_text(localizer.translate(sample.get("Local_Key"), "en"), humanize_token(sample.get("AbleType", {}).get("string_Tid")), sample.get("Name"))
        name_fr = first_text(localizer.translate(sample.get("Local_Key"), "fr"), name_en)
        icon = assets.resolve_stem(
            [
                [row.get("Icon") for row in rows if first_text(row.get("Icon"))],
                "Buff" if effect_list == "buffs" else "Buff2",
            ],
            "effects",
        )
        variants = []
        apply_types = []
        actor_states = []
        search_terms = [group_key, name_en, name_fr]
        for row in sorted(rows, key=lambda item: first_text(item.get("Name"))):
            able_type = row.get("AbleType") if isinstance(row.get("AbleType"), dict) else {}
            desc_en = localizer.format(row.get("Local_Desc"), "en", row.get("Local_Replace"))
            desc_fr = localizer.format(row.get("Local_Desc"), "fr", row.get("Local_Replace"))
            stack_type = row.get("StackType") if isinstance(row.get("StackType"), dict) else {}
            block_flags = [
                label
                for flag, label in BUFF_BLOCK_FLAGS.items()
                if str(able_type.get(flag) or "").lower() == "true"
            ]
            stat_changes = [
                change
                for change in (
                    build_ability_payload(change_row.get("TargetAbil"), change_row.get("Value"), stat_info_by_id, localizer, assets)
                    for change_row in (row.get("AddAbil_List") or [])
                    if isinstance(change_row, dict)
                )
                if change
            ]
            damage_hooks = [
                {
                    "trigger": first_text(change_row.get("ActiveType")),
                    "rule": first_text(change_row.get("Type")),
                    "value": format_ability_value("rate", change_row.get("Value")),
                }
                for change_row in (row.get("AddDam_List") or [])
                if isinstance(change_row, dict)
            ]
            tick_effects = [
                {
                    "behaviorId": first_text(change_row.get("SkillBehaviorTid")),
                    "intervalSeconds": numeric_value(change_row.get("TickTime")) / 1000.0,
                }
                for change_row in (row.get("TickDam_List") or [])
                if isinstance(change_row, dict)
            ]
            material = build_item_link_payload(row.get("Material_TID"), 1, localizer, assets, bucket="effects")
            variants.append(
                {
                    "id": first_text(row.get("Name")),
                    "type": first_text(row.get("Type")),
                    "applyType": first_text(row.get("ApplyType")),
                    "detailType": first_text(row.get("DetailType")),
                    "actorState": first_text(row.get("ActorState")),
                    "ableType": first_text(able_type.get("string_Tid"), able_type.get("String_Tid")),
                    "description": {"en": desc_en, "fr": desc_fr},
                    "blocks": block_flags,
                    "stackFlags": [humanize_token(flag) for flag, value in stack_type.items() if str(value).lower() == "true"],
                    "deleteType": first_text(row.get("DeleteType")),
                    "group": first_text(row.get("Group")),
                    "showIcon": first_text(row.get("ShowIcon")),
                    "statChanges": stat_changes,
                    "damageHooks": damage_hooks,
                    "tickEffects": tick_effects,
                    "material": material,
                }
            )
            apply_types.append(first_text(row.get("ApplyType")))
            actor_states.append(first_text(row.get("ActorState")))
            search_terms.extend(
                [
                    row.get("Name"),
                    desc_en,
                    desc_fr,
                    row.get("Type"),
                    row.get("DetailType"),
                    row.get("ActorState"),
                    able_type.get("string_Tid"),
                    able_type.get("String_Tid"),
                    *flatten_search_terms(stat_changes),
                    *flatten_search_terms(damage_hooks),
                ]
            )
        summary_en = f"{len(variants)} variants across {len(unique(apply_types))} application types."
        summary_fr = f"{len(variants)} variantes sur {len(unique(apply_types))} types d'application."
        primary_desc_en = next((variant["description"]["en"] for variant in variants if variant["description"]["en"]), "")
        primary_desc_fr = next((variant["description"]["fr"] for variant in variants if variant["description"]["fr"]), primary_desc_en)
        entries.append(
            base_entry(
                entry_id=f"effect:{slugify(group_key)}",
                slug=f"effect-{slugify(effect_list)}-{slugify(name_en)}-{slugify(sample.get('Name'))}",
                kind="effect",
                lists=[effect_list],
                name_en=name_en,
                name_fr=name_fr,
                description_en=primary_desc_en,
                description_fr=primary_desc_fr,
                summary_en=summary_en,
                summary_fr=summary_fr,
                icon=icon,
                classification=effect_list[:-1],
                source_tables=["BuffTable.json"],
                source_ids={"effectGroup": first_text(sample.get("Local_Key"), sample.get("Name"))},
                stats={"variantCount": len(variants)},
                fields={
                    "effectGroup": effect_list[:-1],
                    "applyTypes": unique(apply_types),
                    "actorStates": unique(actor_states),
                    "variants": variants,
                    "searchTerms": unique(search_terms),
                },
            )
        )
    return entries


def build_monster_entries(
    monster_rows: List[Dict],
    dictionary_rows: List[Dict],
    localizer: Localizer,
    assets: AssetResolver,
    skip_entry_ids: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict], Dict[str, str]]:
    dictionary_by_local_key, dictionary_by_actor_id = build_monster_dictionary_indexes(dictionary_rows)
    skip_entry_ids = skip_entry_ids or {}
    grouped_rows: Dict[str, List[Dict]] = defaultdict(list)
    for row in monster_rows:
        if not isinstance(row, dict) or is_technical_creature_row(row, localizer):
            continue
        monster_id = first_text(row.get("Name"))
        if not monster_id:
            continue
        if f"monster:{monster_id}" in skip_entry_ids:
            continue
        actor_tid = creature_actor_tid(row)
        if actor_tid.lower().startswith("boss_") or normalize_grade(row.get("Grade")) == "boss":
            continue
        group_key = creature_group_key(row, localizer, boss=False)
        grouped_rows[group_key or monster_id.lower()].append(row)

    entries: List[Dict] = []
    raw_to_entry_id: Dict[str, str] = {}
    for key, rows in sorted(grouped_rows.items(), key=lambda item: item[0]):
        sample = choose_best_creature_row(rows, localizer)
        if not sample:
            continue
        monster_ids = unique(first_text(row.get("Name")) for row in rows if first_text(row.get("Name")))
        sample_monster_id = first_text(sample.get("Name"), monster_ids[0] if monster_ids else "")
        actor_tid = creature_actor_tid(sample)
        grade = normalize_grade(sample.get("Grade"))
        generic_icon = "Monster_Normal_02" if grade in {"elite", "boss"} else "Monster_Normal_01"
        name_en, name_fr = localized_creature_names(sample, localizer)
        desc_en, desc_fr = localized_creature_descriptions(sample, localizer)
        icon = assets.resolve_stem(
            unique(
                [
                    candidate
                    for row in rows
                    for candidate in monster_visual_candidates(row, dictionary_by_local_key, dictionary_by_actor_id)
                ]
                + [generic_icon]
            ),
            "monsters",
        )
        rarity = rarity_payload(sample.get("Grade"))
        drop_group_ids = unique(first_text(row.get("DropGroupTid")) for row in rows if first_text(row.get("DropGroupTid")))
        catch_drop_group_ids = unique(first_text(row.get("CatchDropGroupTid")) for row in rows if first_text(row.get("CatchDropGroupTid")))
        first_drop_group_ids = unique(first_text(row.get("FirstDropGroupTid")) for row in rows if first_text(row.get("FirstDropGroupTid")))
        entry_id = f"monster:{sample_monster_id}"
        summary_en = f"Monster archetype merged from {len(rows)} actor rows."
        summary_fr = f"Archetype de monstre fusionne a partir de {len(rows)} lignes d'acteur."
        entries.append(
            base_entry(
                entry_id=entry_id,
                slug=f"monster-{sample_monster_id}-{slugify(name_en)}",
                kind="monster",
                lists=["monsters"],
                name_en=name_en,
                name_fr=name_fr,
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=summary_en,
                summary_fr=summary_fr,
                icon=icon,
                rarity=rarity,
                source_tables=["MonsterActorTable.json"],
                source_ids={
                    "monsterId": sample_monster_id,
                    "actorTid": actor_tid,
                },
                stats={"variantCount": len(rows)},
                fields={
                    "actorTid": actor_tid,
                    "monsterIds": monster_ids,
                    "dropGroupTids": drop_group_ids,
                    "firstDropGroupTids": first_drop_group_ids,
                    "catchDropGroupTids": catch_drop_group_ids,
                    "monsterSubTypes": unique(first_text(row.get("MonsterSubType")) for row in rows if first_text(row.get("MonsterSubType"))),
                    "npcActorTypes": unique(first_text(row.get("NPCActorType")) for row in rows if first_text(row.get("NPCActorType"))),
                },
            )
        )
        for monster_id in monster_ids:
            raw_to_entry_id[f"monster:{monster_id}"] = entry_id
    return entries, raw_to_entry_id


def build_portal_entries(portal_rows: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    entries: List[Dict] = []
    for row in portal_rows:
        portal_id = first_text(row.get("Name"))
        if not portal_id:
            continue
        type_label = first_text(row.get("Type"), "portal")
        use_type = first_text(row.get("UseType"))
        zone_tid = first_text(row.get("Zone_Tid"))
        localized_name_en = localizer.translate(row.get("Local_PortalName"), "en")
        localized_name_fr = localizer.translate(row.get("Local_PortalName"), "fr")
        name_en = first_text(localized_name_en, f"{type_label.title()} {portal_id}")
        name_fr = first_text(localized_name_fr, name_en)
        desc_en = f"Zone {zone_tid}" + (f" | Use type: {use_type}" if use_type else "")
        desc_fr = f"Zone {zone_tid}" + (f" | Type d'usage : {use_type}" if use_type else "")
        generic_icon = "RevivePoint" if "revive" in " ".join([type_label, use_type]).lower() else "Portal"
        icon = assets.resolve_stem([row.get("Type"), row.get("UseType"), generic_icon], "portals")
        entries.append(
            base_entry(
                entry_id=f"portal:{portal_id}",
                slug=f"portal-{portal_id}",
                kind="portal",
                lists=["portals"],
                name_en=name_en,
                name_fr=name_fr,
                description_en=desc_en,
                description_fr=desc_fr,
                summary_en=f"Portal type {type_label} in zone {zone_tid}.",
                summary_fr=f"Portail de type {type_label} dans la zone {zone_tid}.",
                icon=icon,
                source_tables=["PortalTable.json"],
                source_ids={"portalId": portal_id},
                fields={
                    "type": row.get("Type"),
                    "useType": row.get("UseType"),
                    "zoneTid": row.get("Zone_Tid"),
                    "arrivePortalTid": row.get("Arrive_Portal_Tid"),
                    "position": {
                        "x": row.get("X_Pos"),
                        "y": row.get("Y_Pos"),
                        "z": row.get("Z_Pos"),
                    },
                },
            )
        )
    return entries


def build_puzzle_entries(puzzle_rows: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    entries: List[Dict] = []
    for row in puzzle_rows:
        puzzle_id = first_text(row.get("Name"))
        if not puzzle_id:
            continue
        zone_ids = unique(row.get("Array_Puzzle_Spawn_ZoneID") or [])
        actor_spawns = unique(row.get("Array_Puzzle_Actor_SpawnTid") or [])
        complete_en = localizer.translate(row.get("Complete_Msg_LocalKey"), "en")
        complete_fr = localizer.translate(row.get("Complete_Msg_LocalKey"), "fr")
        name_en = first_text(localizer.translate(row.get("Local_Key"), "en"), f"Puzzle {puzzle_id}")
        name_fr = first_text(localizer.translate(row.get("Local_Key"), "fr"), name_en)
        icon = assets.resolve_stem(["i_interaction_liftswitch"], "puzzles")
        entries.append(
            base_entry(
                entry_id=f"puzzle:{puzzle_id}",
                slug=f"puzzle-{puzzle_id}",
                kind="puzzle",
                lists=["puzzles"],
                name_en=name_en,
                name_fr=name_fr,
                description_en=complete_en,
                description_fr=complete_fr,
                summary_en=f"{len(actor_spawns)} actor spawn ids across {len(zone_ids)} zone ids.",
                summary_fr=f"{len(actor_spawns)} identifiants de spawn d'acteurs sur {len(zone_ids)} zones.",
                icon=icon,
                source_tables=["PuzzleTable.json"],
                source_ids={"puzzleId": puzzle_id},
                fields={
                    "zoneIds": zone_ids,
                    "actorSpawnIds": actor_spawns,
                    "completeMsgKey": row.get("Complete_Msg_LocalKey"),
                    "dictionaryTid": row.get("Dictionary_Tid"),
                },
            )
        )
    return entries


def build_unlock_entries(condition_rows: List[Dict], group_rows: List[Dict], localizer: Localizer, assets: AssetResolver) -> List[Dict]:
    entries: List[Dict] = []
    generic_icon = assets.resolve_stem(["icon_item_BoxOpen", "Waypoint_Open"], "unlocks")
    for row in condition_rows:
        cond_id = first_text(row.get("Name"), row.get("String_Tid"))
        name_en = first_text(
            localizer.translate(row.get("String_Tid"), "en"),
            f"{row.get('Condition_Type')} {row.get('Condition_Target')}",
        )
        name_fr = first_text(
            localizer.translate(row.get("String_Tid"), "fr"),
            name_en,
        )
        entries.append(
            base_entry(
                entry_id=f"unlock-condition:{cond_id}",
                slug=f"unlock-condition-{slugify(cond_id)}",
                kind="unlock",
                lists=["unlocks"],
                name_en=name_en,
                name_fr=name_fr,
                summary_en="Single unlock condition from AreaOpenConditionTable.",
                summary_fr="Condition unique de d\u00e9blocage issue de AreaOpenConditionTable.",
                icon=generic_icon,
                source_tables=["AreaOpenConditionTable.json"],
                source_ids={"conditionId": cond_id},
                fields={
                    "conditionType": row.get("Condition_Type"),
                    "conditionTarget": row.get("Condition_Target"),
                    "stringTid": row.get("String_Tid"),
                },
            )
        )
    for row in group_rows:
        cond_id = first_text(row.get("Name"), row.get("String_Tid"))
        name_en = first_text(localizer.translate(row.get("String_Tid"), "en"), f"Condition group {cond_id}")
        name_fr = first_text(localizer.translate(row.get("String_Tid"), "fr"), f"Groupe de conditions {cond_id}")
        entries.append(
            base_entry(
                entry_id=f"unlock-group:{cond_id}",
                slug=f"unlock-group-{slugify(cond_id)}",
                kind="unlock",
                lists=["unlocks"],
                name_en=name_en,
                name_fr=name_fr,
                summary_en=f"{len(row.get('Link_Condition') or [])} linked condition rows.",
                summary_fr=f"{len(row.get('Link_Condition') or [])} lignes de conditions li\u00e9es.",
                icon=generic_icon,
                source_tables=["AreaOpenConditionGroupTable.json"],
                source_ids={"conditionGroupId": cond_id},
                fields={
                    "linkCondition": row.get("Link_Condition") or [],
                    "stringTid": row.get("String_Tid"),
                },
            )
        )
    return entries


def build_quest_entries(
    points: List[Dict],
    quest_rows_by_type: Dict[str, List[Dict]],
    localizer: Localizer,
    assets: AssetResolver,
) -> List[Dict]:
    point_groups: Dict[str, List[Dict]] = defaultdict(list)
    for point in points:
        if str(point.get("type") or "") != "quest":
            continue
        quest_id = extract_quest_id(point.get("name"), point.get("label"), point.get("description"))
        if quest_id:
            point_groups[quest_id].append(point)

    entries: List[Dict] = []
    source_tables = {
        "main": "QuestStory.json",
        "side": "QuestSide.json",
        "hidden": "QuestHidden.json",
        "stella": "QuestStella.json",
    }
    for quest_type, rows in quest_rows_by_type.items():
        meta = QUEST_TYPE_META[quest_type]
        source_table = source_tables[quest_type]
        for row in rows:
            quest_id = first_text(row.get("Name"), row.get("String_Tid"))
            if not quest_id:
                continue
            group_points = point_groups.get(quest_id, [])
            name_en = first_text(localizer.translate(row.get("Local_Key"), "en"), f"{meta['label_en']} {quest_id}")
            name_fr = first_text(localizer.translate(row.get("Local_Key"), "fr"), name_en)
            subtitle_en = first_text(
                localizer.translate(row.get("Quest_Info_SubTitle"), "en"),
                localizer.translate(row.get("Quest_Start_SubTitle"), "en"),
            )
            subtitle_fr = first_text(
                localizer.translate(row.get("Quest_Info_SubTitle"), "fr"),
                localizer.translate(row.get("Quest_Start_SubTitle"), "fr"),
                subtitle_en,
            )
            desc_en = first_text(localizer.translate(row.get("Quest_Info_Desc"), "en"), subtitle_en)
            desc_fr = first_text(localizer.translate(row.get("Quest_Info_Desc"), "fr"), subtitle_fr)
            regions = unique(region for point in group_points for region in point_regions(point))
            region_ids = unique(
                region_id
                for point in group_points
                for region_id in (point.get("region_ids") or [point.get("region_id")])
                if region_id
            )
            marker_counts = Counter(quest_marker_stage(point) for point in group_points)
            preferred_point_id = next(
                (
                    point.get("id")
                    for point in group_points
                    if quest_marker_stage(point) == "start" and point.get("id")
                ),
                "",
            )
            summary_en = subtitle_en or (
                f"{len(group_points)} tracked quest markers across {len(regions)} regions."
                if group_points
                else f"{meta['label_en']} extracted from {source_table}."
            )
            summary_fr = subtitle_fr or (
                f"{len(group_points)} marqueurs de qu\u00eate suivis sur {len(regions)} r\u00e9gions."
                if group_points
                else f"{meta['label_fr']} extraite de {source_table}."
            )
            icon = assets.resolve_stem(quest_icon_stems(quest_type, quest_id), "quests")
            image = assets.resolve_stem(quest_image_stems(quest_id), "quests")
            entries.append(
                base_entry(
                    entry_id=f"quest:{quest_type}:{quest_id}",
                    slug=f"quest-{quest_type}-{quest_id}-{slugify(name_en)}",
                    kind="quest",
                    lists=["quests", meta["list"]],
                    name_en=name_en,
                    name_fr=name_fr,
                    description_en=desc_en,
                    description_fr=desc_fr,
                    summary_en=summary_en,
                    summary_fr=summary_fr,
                    icon=icon,
                    image=image,
                    classification=quest_type,
                    regions=regions,
                    region_ids=region_ids,
                    map_ref=build_map_ref(
                        group_points,
                        point_type="quest",
                        preferred_point_id=preferred_point_id,
                    )
                    if group_points
                    else None,
                    source_tables=unique([source_table, "map_data.json"] if group_points else [source_table]),
                    source_ids={
                        "questId": quest_id,
                        "questGroupId": row.get("Quest_Group_ID"),
                        "playZone": row.get("Play_Zone"),
                    },
                    stats={
                        "pointCount": len(group_points),
                        "startCount": marker_counts.get("start", 0),
                        "progressCount": marker_counts.get("progress", 0),
                        "endCount": marker_counts.get("end", 0),
                    },
                    fields={
                        "questType": quest_type,
                        "questGroupId": row.get("Quest_Group_ID"),
                        "playZone": row.get("Play_Zone"),
                        "playSector": row.get("Play_Sector"),
                        "questStartType": row.get("Quest_Start_Type"),
                        "questStartTarget": row.get("Quest_Start_Target"),
                        "questStartTargetSign": row.get("Quest_Start_Target_Sign"),
                        "questStartValue": row.get("Quest_Start_Value"),
                        "questSignStartGroup": row.get("QuestSign_Start_Group"),
                        "questSignGroup": row.get("QuestSign_Group"),
                        "rewardGroup": row.get("Quest_End_RewardGroup"),
                        "rewardExp": row.get("Quest_End_Reward_Exp"),
                        "prevQuestId": row.get("Prev_Quest_ID"),
                        "nextQuestId": row.get("Next_Quest_ID"),
                        "startConditionGroup": row.get("Start_Add_ConditionGroup"),
                        "finishConditionGroup": row.get("Quest_Finish_ConditionGroup"),
                    },
                )
            )
    return entries


def attach_item_relations(entries: List[Dict], item_relations: Dict[str, Dict[str, List[str]]]) -> None:
    by_id = {entry["id"]: entry for entry in entries}
    for item_id, relation_map in item_relations.items():
        item_entry = by_id.get(f"item:{item_id}")
        if not item_entry:
            continue
        relation_ids = []
        for relation_type, values in relation_map.items():
            if relation_type == "searchTerms":
                continue
            relation_ids.extend(values)
        item_entry["related"] = unique(item_entry["related"] + relation_ids)
        if not item_entry.get("icon") and not item_entry.get("image"):
            related_entries = [by_id.get(entry_id) for entry_id in item_entry["related"]]
            costume_media = next(
                (
                    related_entry
                    for related_entry in related_entries
                    if related_entry and related_entry.get("kind") == "costume" and (related_entry.get("image") or related_entry.get("icon"))
                ),
                None,
            )
            if costume_media:
                item_entry["image"] = costume_media.get("image") or costume_media.get("icon") or ""
                item_entry["icon"] = costume_media.get("icon") or costume_media.get("image") or ""


def attach_loot_relations(entries: List[Dict], loot_by_entry: Dict[str, List[Dict]]) -> None:
    by_id = {entry["id"]: entry for entry in entries}
    for entry in entries:
        target_entry_id = first_text(entry.get("id"))
        if not target_entry_id:
            continue
        loot_rows = list(loot_by_entry.get(target_entry_id, []))
        if not loot_rows:
            continue
        entry.setdefault("fields", {})["lootDrops"] = loot_rows
        entry.setdefault("stats", {})["dropCount"] = len(loot_rows)
        linked_items = [f"item:{first_text(row.get('itemId'))}" for row in loot_rows if first_text(row.get("itemId")) and by_id.get(f"item:{first_text(row.get('itemId'))}")]
        entry["related"] = unique(entry.get("related", []) + linked_items)


def attach_character_effect_relations(character_entries: List[Dict], effect_entries: List[Dict]) -> None:
    effect_id_by_variant: Dict[str, str] = {}
    for effect_entry in effect_entries:
        for variant in effect_entry.get("fields", {}).get("variants", []):
            variant_id = first_text(variant.get("id"))
            if variant_id:
                effect_id_by_variant[variant_id] = effect_entry["id"]

    related_characters_by_effect: Dict[str, List[str]] = defaultdict(list)
    for character_entry in character_entries:
        related_effect_ids: List[str] = []
        for style in character_entry.get("fields", {}).get("weaponStyles", []):
            for skill in style.get("skills", []):
                for effect in skill.get("effects", []):
                    if effect.get("kind") != "buff":
                        continue
                    effect_id = effect_id_by_variant.get(first_text(effect.get("buffId")))
                    if not effect_id:
                        continue
                    related_effect_ids.append(effect_id)
                    related_characters_by_effect[effect_id].append(character_entry["id"])
        related_effect_ids = unique(related_effect_ids)
        if related_effect_ids:
            character_entry["fields"]["relatedEffects"] = related_effect_ids
            character_entry["related"] = unique(character_entry["related"] + related_effect_ids)

    by_effect_id = {entry["id"]: entry for entry in effect_entries}
    for effect_id, character_ids in related_characters_by_effect.items():
        effect_entry = by_effect_id.get(effect_id)
        if effect_entry:
            effect_entry["related"] = unique(effect_entry.get("related", []) + character_ids)


def build_search_index(entries: List[Dict]) -> List[Dict]:
    docs = []
    for entry in entries:
        locale = entry["locale"]
        extra_terms = flatten_search_terms(entry.get("fields", {}).get("searchTerms"))
        search_text = " ".join(
            unique(
                [
                    locale["en"]["name"],
                    locale["fr"]["name"],
                    locale["en"]["summary"],
                    locale["fr"]["summary"],
                    locale["en"]["description"],
                    locale["fr"]["description"],
                    entry["kind"],
                    " ".join(entry.get("lists") or []),
                    " ".join(entry.get("regions") or []),
                    " ".join(entry.get("aliasSlugs") or []),
                    json.dumps(entry.get("sourceIds") or {}, ensure_ascii=True),
                    " ".join(extra_terms),
                ]
            )
        ).lower()
        docs.append(
            {
                "id": entry["id"],
                "slug": entry["slug"],
                "kind": entry["kind"],
                "lists": entry["lists"],
                "titleEn": locale["en"]["name"],
                "titleFr": locale["fr"]["name"],
                "titleEnNorm": normalize_search_text(locale["en"]["name"]),
                "titleFrNorm": normalize_search_text(locale["fr"]["name"]),
                "summaryEn": locale["en"]["summary"],
                "summaryFr": locale["fr"]["summary"],
                "regions": entry.get("regions") or [],
                "regionIds": entry.get("regionIds") or [],
                "rarityGrade": entry.get("rarity", {}).get("grade") if entry.get("rarity") else "",
                "rarityRank": int(numeric_value((entry.get("rarity") or {}).get("rank")) or 0),
                "sortIndex": entry.get("sortIndex"),
                "mapLinked": bool(entry.get("mapRef")),
                "searchText": search_text,
                "searchTextNorm": normalize_search_text(search_text),
            }
        )
    return docs


def build_manifest(entries: List[Dict], region_entries: List[Dict]) -> Dict:
    def featured_entry_sort_key(entry: Dict) -> Tuple[int, int, int, str]:
        sort_index = int(numeric_value(entry.get("sortIndex")) or 999999999)
        rarity_rank = int(numeric_value((entry.get("rarity") or {}).get("rank")) or 0)
        point_count = int(numeric_value((entry.get("stats") or {}).get("pointCount")) or 0)
        name_en = first_text(entry.get("locale", {}).get("en", {}).get("name"))
        return (sort_index, -point_count, rarity_rank, normalize_search_text(name_en))

    list_counts = Counter()
    map_linked_counts = Counter()
    kind_counts = Counter(entry["kind"] for entry in entries)
    for entry in entries:
        for list_id in entry.get("lists") or []:
            list_counts[list_id] += 1
            if entry.get("mapRef"):
                map_linked_counts[list_id] += 1

    featured_regions = sorted(
        region_entries,
        key=lambda entry: entry.get("stats", {}).get("pointCount", 0),
        reverse=True,
    )[:6]
    featured_materials = [
        entry for entry in entries if "materials" in entry.get("lists", [])
    ][:6]
    featured_pets = sorted(
        [entry for entry in entries if "pets" in entry.get("lists", [])],
        key=featured_entry_sort_key,
    )[:6]
    featured_systems = [
        entry
        for entry in entries
        if any(list_id in entry.get("lists", []) for list_id in ["waypoints", "portals", "puzzles"])
    ][:6]

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "entries": len(entries),
            "kinds": dict(kind_counts),
            "lists": dict(list_counts),
            "mapLinkedLists": dict(map_linked_counts),
        },
        "hubs": HUBS,
        "lists": {
            list_id: {
                **LISTS[list_id],
                "count": list_counts.get(list_id, 0),
                "mapLinkedCount": map_linked_counts.get(list_id, 0),
            }
            for list_id in LISTS
        },
        "featured": {
            "regions": [
                {
                    "id": entry["id"],
                    "slug": entry["slug"],
                    "name": entry["locale"],
                    "pointCount": entry.get("stats", {}).get("pointCount", 0),
                }
                for entry in featured_regions
            ],
            "materials": [
                {
                    "id": entry["id"],
                    "slug": entry["slug"],
                    "name": entry["locale"],
                    "icon": entry.get("icon", ""),
                }
                for entry in featured_materials
            ],
            "pets": [
                {
                    "id": entry["id"],
                    "slug": entry["slug"],
                    "name": entry["locale"],
                    "icon": entry.get("icon", ""),
                }
                for entry in featured_pets
            ],
            "systems": [
                {
                    "id": entry["id"],
                    "slug": entry["slug"],
                    "name": entry["locale"],
                    "icon": entry.get("icon", ""),
                }
                for entry in featured_systems
            ],
        },
    }


def main() -> None:
    CODEX_DATA_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    map_points = read_json(MAP_DATA_PATH)
    if not isinstance(map_points, list):
        raise SystemExit("map_data.json must be a list")

    localizer = Localizer()
    assets = AssetResolver()

    waypoint_rows = read_json(TEXTDATA_DIR / "WaypointTable.json")
    pet_rows = read_json(TEXTDATA_DIR / "PetDataInfo.json")
    binding_rows = read_json(TEXTDATA_DIR / "BindingRecipeTable.json")
    cooking_rows = read_json(TEXTDATA_DIR / "CookingRecipeTable.json")
    production_rows = read_json(TEXTDATA_DIR / "ProductionRecipeTable.json")
    making_rows = read_json(TEXTDATA_DIR / "MakingRecipe.json")
    disassemble_rows = read_json(TEXTDATA_DIR / "DisassembleData.json")
    disassemble_level_rows = read_json(TEXTDATA_DIR / "Disassemble_Level.json")
    option_list_rows = read_json(TEXTDATA_DIR / "ItemTable_OptionListData.json")
    option_static_rows = read_json(TEXTDATA_DIR / "Option_StaticTable.json")
    option_random_rows = read_json(TEXTDATA_DIR / "Option_RandomTable.json")
    set_rows = read_json(TEXTDATA_DIR / "EquipSetOptionTable.json")
    set_value_rows = read_json(TEXTDATA_DIR / "EquipSetOptionValueTable.json")
    passive_base_rows = read_json(TEXTDATA_DIR / "ItemTable_Equip_Passive_Base.json")
    passive_group_rows = read_json(TEXTDATA_DIR / "ItemTable_Equip_Passive_Group.json")
    monster_rows = read_json(TEXTDATA_DIR / "MonsterActorTable.json", sanitize=True)
    drop_pack_rows = read_json(TEXTDATA_DIR / "DropPackTable.json", sanitize=True)
    drop_group_rows = read_json(TEXTDATA_DIR / "DropGroupTable.json", sanitize=True)
    dungeon_rows = read_json(TEXTDATA_DIR / "DungeonTable.json", sanitize=True)
    dungeon_group_rows = read_json(TEXTDATA_DIR / "DungeonGroupTable.json", sanitize=True)
    interaction_rows = read_json(TEXTDATA_DIR / "InteractionTable.json", sanitize=True)
    field_boss_rows = read_json(TEXTDATA_DIR / "FieldBossTable.json", sanitize=True)
    portal_rows = read_json(TEXTDATA_DIR / "PortalTable.json")
    puzzle_rows = read_json(TEXTDATA_DIR / "PuzzleTable.json")
    condition_rows = read_json(TEXTDATA_DIR / "AreaOpenConditionTable.json")
    condition_group_rows = read_json(TEXTDATA_DIR / "AreaOpenConditionGroupTable.json")
    fishing_zone_rows = read_json(TEXTDATA_DIR / "FishingZoneActorTable.json")
    quest_story_rows = read_json(TEXTDATA_DIR / "QuestStory.json")
    quest_side_rows = read_json(TEXTDATA_DIR / "QuestSide.json")
    quest_hidden_rows = read_json(TEXTDATA_DIR / "QuestHidden.json")
    quest_stella_rows = read_json(TEXTDATA_DIR / "QuestStella.json")
    event_mission_rows = read_json(TEXTDATA_DIR / "EventMissionFixed.json", sanitize=True)
    event_group_rows = read_json(TEXTDATA_DIR / "EventMissionFixedGroup.json", sanitize=True)
    event_condition_rows = read_json(TEXTDATA_DIR / "EventCondition.json", sanitize=True)
    event_rows = read_json(TEXTDATA_DIR / "EventData.json", sanitize=True)
    hero_profile_rows = read_json(TEXTDATA_DIR / "HeroProfileInfo.json")
    hero_actor_rows = read_json(TEXTDATA_DIR / "HeroActorTable.json")
    hero_stat_group_rows = read_json(TEXTDATA_DIR / "HeroStatGroupTable.json")
    hero_mastery_rows = read_json(TEXTDATA_DIR / "HeroMastery.json")
    hero_common_mastery_rows = read_json(TEXTDATA_DIR / "HeroCommonMastery.json")
    default_skill_rows = read_json(TEXTDATA_DIR / "DefaultSkillTable.json")
    default_skill_weapon_rows = read_json(TEXTDATA_DIR / "DefaultSkillWeaponTypeTable.json")
    mastery_rows = read_json(TEXTDATA_DIR / "HeroWeaponMastery.json")
    mastery_group_rows = read_json(TEXTDATA_DIR / "HeroWeaponMasteryGroup.json")
    mastery_group_exp_rows = read_json(TEXTDATA_DIR / "HeroWeaponMasteryGroupExp.json")
    stat_info_rows = read_json(TEXTDATA_DIR / "StatInfoTable.json")
    pc_skill_rows = read_json(TEXTDATA_DIR / "PC_SkillTable.json")
    shared_skill_rows = read_json(TEXTDATA_DIR / "SkillTable.json")
    pc_skill_behavior_rows = read_json(TEXTDATA_DIR / "PC_SkillBehaviorTable.json")
    shared_skill_behavior_rows = read_json(TEXTDATA_DIR / "SkillBehaviorTable.json")
    costume_rows = read_json(TEXTDATA_DIR / "CostumeTable.json")
    buff_rows = read_json(TEXTDATA_DIR / "BuffTable.json")
    dictionary_rows = read_json(TEXTDATA_DIR / "DictionaryTable.json", sanitize=True)

    costume_ids_by_hero: Dict[str, List[str]] = defaultdict(list)
    for row in costume_rows:
        if not isinstance(row, dict):
            continue
        hero_id = first_text((row.get("Show_Condition_Value") or [""])[0])
        costume_id = first_text(row.get("Name"))
        if hero_id and costume_id:
            costume_ids_by_hero[hero_id].append(costume_id)

    mastery_catalog = build_weapon_mastery_catalog(
        mastery_rows,
        mastery_group_rows,
        mastery_group_exp_rows,
        stat_info_rows,
        localizer,
        assets,
    )
    common_mastery_catalog = build_common_mastery_catalog(
        hero_common_mastery_rows,
        stat_info_rows,
        localizer,
        assets,
    )

    region_entries = build_region_entries(map_points, assets)
    node_entries = build_node_entries(map_points, localizer, assets)
    pet_entries = build_pet_entries(map_points, pet_rows, localizer, assets)
    character_entries = build_character_entries(
        hero_actor_rows,
        hero_profile_rows,
        hero_stat_group_rows,
        hero_mastery_rows,
        common_mastery_catalog,
        default_skill_rows,
        default_skill_weapon_rows,
        pc_skill_rows,
        shared_skill_rows,
        pc_skill_behavior_rows,
        shared_skill_behavior_rows,
        buff_rows,
        stat_info_rows,
        mastery_catalog,
        localizer,
        assets,
        costume_ids_by_hero,
    )
    costume_entries, costume_item_ids = build_costume_entries(costume_rows, localizer, assets, character_entries)
    effect_entries = build_effect_entries(buff_rows, localizer, assets, stat_info_rows)
    attach_character_effect_relations(character_entries, effect_entries)
    boss_entries, boss_entry_ids_by_raw_monster = build_boss_entries(
        map_points,
        field_boss_rows,
        dungeon_rows,
        monster_rows,
        dictionary_rows,
        localizer,
        assets,
    )
    waypoint_entries = build_waypoint_entries(map_points, waypoint_rows, localizer, assets)
    fishing_entries = build_fishing_spot_entries(map_points, fishing_zone_rows, assets)
    recipe_entries, recipe_relations, recipe_item_ids = build_recipe_entries(
        binding_rows,
        cooking_rows,
        production_rows,
        making_rows,
        dictionary_rows,
        localizer,
        assets,
    )
    monster_entries, monster_entry_ids_by_raw_monster = build_monster_entries(
        monster_rows,
        dictionary_rows,
        localizer,
        assets,
        boss_entry_ids_by_raw_monster,
    )
    portal_entries = build_portal_entries(portal_rows, localizer, assets)
    puzzle_entries = build_puzzle_entries(puzzle_rows, localizer, assets)
    unlock_entries = build_unlock_entries(condition_rows, condition_group_rows, localizer, assets)
    quest_entries = build_quest_entries(
        map_points,
        {
            "main": quest_story_rows,
            "side": quest_side_rows,
            "hidden": quest_hidden_rows,
            "stella": quest_stella_rows,
        },
        localizer,
        assets,
    )

    item_relations: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    referenced_item_ids: List[str] = []

    for entry in node_entries:
        item_id = first_text(entry.get("fields", {}).get("resourceItemId"))
        if item_id:
            item_relations[item_id]["nodes"].append(entry["id"])
            referenced_item_ids.append(item_id)

    for entry in pet_entries:
        item_id = first_text(entry.get("fields", {}).get("itemId"))
        if item_id:
            item_relations[item_id]["pets"].append(entry["id"])
            referenced_item_ids.append(item_id)

    for item_id, relation_map in recipe_relations.items():
        referenced_item_ids.append(item_id)
        for relation_type, relation_ids in relation_map.items():
            item_relations[item_id][relation_type].extend(relation_ids)

    for entry in character_entries:
        hero_names = [entry.get("locale", {}).get("en", {}).get("name", ""), entry.get("locale", {}).get("fr", {}).get("name", "")]
        for gear in entry.get("fields", {}).get("defaultEquipment", []):
            item_id = first_text(gear.get("itemId"))
            if not item_id:
                continue
            item_relations[item_id]["characters"].append(entry["id"])
            item_relations[item_id]["searchTerms"].extend(hero_names)
            referenced_item_ids.append(item_id)
        potential_item_id = first_text(entry.get("fields", {}).get("potentialItem", {}).get("itemId"))
        if potential_item_id:
            item_relations[potential_item_id]["characters"].append(entry["id"])
            item_relations[potential_item_id]["searchTerms"].extend(hero_names)
            referenced_item_ids.append(potential_item_id)
        for material in entry.get("fields", {}).get("masteryActivationMaterials", []):
            item_id = first_text(material.get("itemId"))
            if not item_id:
                continue
            item_relations[item_id]["characters"].append(entry["id"])
            item_relations[item_id]["searchTerms"].extend(hero_names)
            referenced_item_ids.append(item_id)

    for entry in costume_entries:
        item_id = first_text(entry.get("fields", {}).get("itemId"))
        if not item_id:
            continue
        item_relations[item_id]["costumes"].append(entry["id"])
        item_relations[item_id]["searchTerms"].extend(
            [
                entry.get("locale", {}).get("en", {}).get("name", ""),
                entry.get("locale", {}).get("fr", {}).get("name", ""),
                entry.get("fields", {}).get("heroName", {}).get("en", ""),
                entry.get("fields", {}).get("heroName", {}).get("fr", ""),
            ]
        )
        referenced_item_ids.append(item_id)

    drop_item_ids = [
        first_text(row.get("Item_Tid"))
        for row in drop_pack_rows
        if isinstance(row, dict) and first_text(row.get("DropType")).lower() == "item" and first_text(row.get("Item_Tid"))
    ]
    referenced_item_ids = unique(referenced_item_ids + recipe_item_ids + costume_item_ids + drop_item_ids + sorted(ENGRAVING_ITEM_IDS))
    disassembly_by_item, disassembly_output_item_ids = build_item_disassembly_index(
        referenced_item_ids,
        localizer,
        assets,
        disassemble_rows,
        disassemble_level_rows,
    )
    recycled_from_by_item = build_reverse_disassembly_index(
        localizer,
        assets,
        disassemble_rows,
        disassemble_level_rows,
    )
    referenced_item_ids = unique(referenced_item_ids + disassembly_output_item_ids)
    acquisition_sources_by_item = build_item_acquisition_sources(
        referenced_item_ids,
        drop_pack_rows,
        drop_group_rows,
        dungeon_rows,
        dungeon_group_rows,
        monster_rows,
        interaction_rows,
        recipe_entries,
        event_mission_rows,
        event_group_rows,
        event_condition_rows,
        event_rows,
        quest_entries,
        localizer,
        assets,
    )
    raw_monster_to_entry_id = {}
    raw_monster_to_entry_id.update(monster_entry_ids_by_raw_monster)
    raw_monster_to_entry_id.update(boss_entry_ids_by_raw_monster)
    acquisition_sources_by_item = remap_acquisition_source_entries(acquisition_sources_by_item, raw_monster_to_entry_id)
    for item_id, acquisition_sources in acquisition_sources_by_item.items():
        for source in acquisition_sources:
            related_entry_id = first_text(source.get("relatedEntryId"))
            if related_entry_id:
                item_relations[item_id]["acquisition"].append(related_entry_id)
        item_relations[item_id]["searchTerms"].extend(flatten_search_terms(acquisition_sources))

    item_entries = build_item_entries(
        referenced_item_ids,
        localizer,
        assets,
        item_relations,
        stat_info_rows,
        option_static_rows,
        option_list_rows,
        option_random_rows,
        set_rows,
        set_value_rows,
        passive_base_rows,
        passive_group_rows,
        acquisition_sources_by_item,
        disassembly_by_item,
        recycled_from_by_item,
    )
    loot_by_entry = build_loot_by_source_entry(acquisition_sources_by_item, localizer, assets)

    all_entries = (
        region_entries
        + node_entries
        + character_entries
        + item_entries
        + costume_entries
        + recipe_entries
        + pet_entries
        + boss_entries
        + waypoint_entries
        + fishing_entries
        + monster_entries
        + effect_entries
        + portal_entries
        + puzzle_entries
        + unlock_entries
        + quest_entries
    )

    attach_item_relations(all_entries, item_relations)
    attach_loot_relations(all_entries, loot_by_entry)
    search_index = build_search_index(all_entries)
    manifest = build_manifest(all_entries, region_entries)

    generated_paths = [
        CODEX_DATA_DIR / "manifest.json",
        CODEX_DATA_DIR / "regions.json",
        CODEX_DATA_DIR / "entries-resources.json",
        CODEX_DATA_DIR / "entries-heroes.json",
        CODEX_DATA_DIR / "entries-creatures.json",
        CODEX_DATA_DIR / "entries-systems.json",
        CODEX_DATA_DIR / "search-index.json",
    ]
    sitemap_path = CODEX_ROOT / "sitemap.xml"

    write_json(generated_paths[0], manifest)
    write_json(generated_paths[1], region_entries)
    write_json(generated_paths[2], node_entries + item_entries + recipe_entries)
    write_json(generated_paths[3], character_entries + costume_entries + effect_entries)
    write_json(generated_paths[4], pet_entries + boss_entries + monster_entries + fishing_entries)
    write_json(
        generated_paths[5],
        waypoint_entries + portal_entries + puzzle_entries + unlock_entries + quest_entries,
    )
    write_json(generated_paths[6], search_index)
    write_sitemap(sitemap_path, manifest, all_entries)
    generated_sizes = verify_cloudflare_asset_sizes(generated_paths + [sitemap_path])

    summary = {
        "manifest": manifest["counts"],
        "cloudflareAssetLimitMiB": round(CLOUDFLARE_MAX_ASSET_BYTES / (1024 * 1024), 2),
        "files": [
            {
                "name": path.name,
                "sizeBytes": generated_sizes[path.name],
                "sizeMiB": round(generated_sizes[path.name] / (1024 * 1024), 2),
            }
            for path in generated_paths + [sitemap_path]
        ],
    }
    write_json(CODEX_DATA_DIR / "build-summary.json", summary)

    print("SevenCodex data generated:")
    print(f"  entries: {len(all_entries)}")
    print(f"  regions: {len(region_entries)}")
    print(f"  resources: {len(node_entries) + len(item_entries) + len(recipe_entries)}")
    print(f"  heroes: {len(character_entries) + len(costume_entries) + len(effect_entries)}")
    print(f"  creatures: {len(pet_entries) + len(boss_entries) + len(monster_entries) + len(fishing_entries)}")
    print(
        f"  systems: {len(waypoint_entries) + len(portal_entries) + len(puzzle_entries) + len(unlock_entries) + len(quest_entries)}"
    )


if __name__ == "__main__":
    main()
