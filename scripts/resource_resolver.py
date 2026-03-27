#!/usr/bin/env python3
"""
Resolve mining/gathering POIs against exported game tables.

This module links world-resource actors to:
- drop groups / drop packs
- item tables
- localized names and descriptions from UE locres files
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_TEXTDATA_DIR = Path("../FModel/Output/Exports/SevenDeadlySins/Content/TextDatas/CData")
DEFAULT_LOCALIZATION_DIR = Path("../FModel/Output/Exports/SevenDeadlySins/Content/Localization/Game")

WEAPON_LABELS = {
    "axe": {"en": "Axe", "fr": "Hache"},
    "book": {"en": "Book", "fr": "Livre"},
    "cudgel_3_c": {"en": "Cudgel", "fr": "Gourdin"},
    "dual_sword": {"en": "Dual Swords", "fr": "Epées jumelles"},
    "gloves": {"en": "Gauntlets", "fr": "Gantelets"},
    "great_sword": {"en": "Greatsword", "fr": "Espadon"},
    "lance": {"en": "Lance", "fr": "Lance"},
    "long_sword": {"en": "Longsword", "fr": "Epée longue"},
    "magic_book": {"en": "Grimoire", "fr": "Grimoire"},
    "rapier": {"en": "Rapier", "fr": "Rapière"},
    "staff": {"en": "Staff", "fr": "Bâton"},
    "sword_shild": {"en": "Sword & Shield", "fr": "Epée et bouclier"},
    "wand": {"en": "Wand", "fr": "Baguette"},
}

MASTERY_ITEM_IDS = {
    "siren_tear": "101040101",
    "titan_beetle": "101040102",
    "giant_bird_feather": "101040103",
    "knight_crest": "101040104",
    "evening_primrose": "101040105",
    "lapis_stone": "101040106",
    "allure_mushroom": "101040201",
    "whirl_flower": "101040202",
    "spirit_flower": "101040203",
    "ghostly_firefly": "101040204",
    "luminorb_essence": "101040205",
    "spirit_stone_piece": "101040206",
    "dragon_blood_stone": "101040301",
    "dragon_tail_flower": "101040302",
    "thunder_flower": "101040303",
    "void_obsidian_stone": "101040304",
    "waterway_tree_essence": "101040305",
    "pioneer_crystal_necklace": "101040306",
    "courage_tablet_piece": "101040401",
    "armor_cactus_essence": "101040402",
    "wisdom_tablet_piece": "101040403",
    "sand_flower": "101040404",
    "invader_emblem": "101040405",
    "mercy_tablet_piece": "101040406",
    "giant_flower_herb": "101040501",
    "ollin_mana_stone": "101040502",
    "erod_ancient_dragon_scale": "101040505",
    "blood_crystal_flower": "101040506",
}

RESOURCE_BLACKLIST = {
    "gathering": {
        "dragon_egg_piece",
        "gravestone_restore_parts",
    }
}

GATHERING_GROUP_ALIASES = {
    "active_sea_grape": "gathering_active_sea_grapes",
    "bone_fragment_bird": "gathering_bird_bone_fragment",
    "bone_fragment_bison": "gathering_bison_bone_fragment",
    "bone_fragment_rabbit": "gathering_rabbit_bone_fragment",
    "bone_fragment_wolf": "gathering_wolf_bone_fragment",
    "boston_ivy": "gathering_ivy_vines",
    "butter_fly": "gathering_butterfly",
    "dandelion": "gathering_dandelion_root",
    "death_petal": "gathering_petal_death",
    "dragon_breath_powder": "gathering_old_dragons_sigh_powder",
    "dwarf_trumpet": "specialproduct_dwarftrumpet",
    "echo_bag": "gathering_echo_bag",
    "edible_moss": "gathering_edible_moss",
    "eternal_life_petal": "gathering_petal_eternal_life",
    "explosive_paprika": "gathering_exploding_paprika",
    "feather_chicken": "gathering_chicken_feathers",
    "feather_crow": "gathering_crow_feather",
    "feather_pigeon": "gathering_pigeon_feather",
    "feather_seagull": "gathering_seagull_feathers",
    "fire_fly": "gathering_firefly",
    "flash_lemon": "gathering_flash_of_lemon",
    "fluffy_hedgehog_quills": "gathering_fluffy_hedgehog_thorns",
    "glory_bay_leaf": "gathering_glory_laurel_leaves",
    "hair_tuft_bird": "gathering_new_hairball",
    "hair_tuft_bison": "gathering_bison_furball",
    "hair_tuft_rabbit": "gathering_rabbit_fur_ball",
    "hair_tuft_wolf": "gathering_wolf_fur_ball",
    "hammer_golem_heart": "gathering_hammer_golem_heart",
    "honey_comb": "gathering_honey",
    "honeycomb": "gathering_honey",
    "innocence_petal": "gathering_petal_innocence",
    "kudzu_vine": "gathering_kudzu_vine",
    "lady_bug": "gathering_ladybug",
    "oxygen_water_plant": "gathering_oxygen_myelin_sheath",
    "pine_apple": "gathering_pineapple",
    "pigeon_egg": "gathering_pigeon_egg",
    "safflower": "gathering_safflower_seeds",
    "scream_petal": "gathering_petal_scream",
    "seagull_egg": "gathering_seagull_eggs",
    "shiitake_mushroom": "gathering_shiitake_mushrooms",
    "strong_dew_chain": "gathering_strong_dew_chain",
    "sweet_potato": "gathering_sweet_potato",
    "tooth_fairy_dentures": "gathering_tooth_fairys_dentures",
    "tree_sap": "gathering_tree_sap",
    "unicorn_whirlwind_horn": "gathering_unicorn_tornado_horn",
    "west_wind_wild_strawberry": "gathering_westwind_wildstrawberry",
    "wheat_plant": "gathering_wheat",
    "wildflower_vine": "gathering_wildflower_vines",
    "wisteria": "gathering_wisteria_vine",
}

GATHERING_ITEM_NAME_FALLBACKS = {
    "apple": "apple",
    "corn": "corn",
    "crow_egg": "crow egg",
    "egg": "egg",
    "giant_bird_egg": "giant bird egg",
    "nettle": "nettle",
}

MOJIBAKE_HINTS = ("Ã", "Å", "â€™", "â€œ", "â€", "Â")


RARITY_BY_GRADE = {
    "grade1": {"rank": "1", "color": "gray", "hex": "#8892a0"},
    "grade2": {"rank": "2", "color": "green", "hex": "#48c774"},
    "grade3": {"rank": "3", "color": "blue", "hex": "#4a8dff"},
    "grade4": {"rank": "4", "color": "violet", "hex": "#b06cff"},
    "grade5": {"rank": "5", "color": "yellow", "hex": "#f4c542"},
}

def split_camel_words(value: str) -> List[str]:
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", value)


def snake_case_from_camel(value: str) -> str:
    return "_".join(part.lower() for part in split_camel_words(value))


def singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("ves") and len(token) > 3:
        return token[:-3] + "f"
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def token_signature(value: str) -> str:
    parts = [part for part in re.split(r"[_\W]+", value.lower()) if part]
    return "".join(singularize_token(part) for part in parts)


def humanize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_") if part).strip()


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def repair_mojibake(value: object) -> str:
    text = normalize_text(value)
    if not text or not any(hint in text for hint in MOJIBAKE_HINTS):
        return text
    for source in ("latin-1", "cp1252"):
        try:
            fixed = text.encode(source).decode("utf-8")
        except UnicodeError:
            continue
        if fixed:
            return fixed
    return text


def normalize_grade(value: object) -> str:
    return normalize_text(value).lower()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_drop_groups(path: Path) -> List[Dict]:
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r"\bTRUE\b", "true", text)
    text = re.sub(r"\bFALSE\b", "false", text)
    return json.loads(text)


class ResourceResolver:
    def __init__(self, textdata_dir: Path, localization_dir: Path) -> None:
        self.textdata_dir = textdata_dir
        self.localization_dir = localization_dir
        self.enabled = textdata_dir.is_dir()

        self.localizations: Dict[str, Dict[str, str]] = {}
        self.item_index: Dict[str, Dict] = {}
        self.item_name_index: Dict[str, Dict] = {}
        self.drop_groups: Dict[str, Dict] = {}
        self.drop_packs_by_group: Dict[str, List[Dict]] = {}
        self.gathering_group_lookup: Dict[str, str] = {}
        self.mining_actor_lookup: Dict[str, Dict[str, str]] = {}

        if not self.enabled:
            return

        self._load_localizations()
        self._load_items()
        self._load_drop_tables()
        self._load_mining_table()
        self._build_gathering_lookup()

    def _load_localizations(self) -> None:
        try:
            from UE4Parse.BinaryReader import BinaryStream
            from UE4Parse.Localization.FTextLocalizationResource import FTextLocalizationResource
        except Exception:
            return

        if not self.localization_dir.is_dir():
            return

        roots = [self.localization_dir]
        patch_root = self.localization_dir.parent / "GamePatch"
        if patch_root.is_dir():
            roots.append(patch_root)

        for root in roots:
            for lang_dir in root.iterdir():
                if not lang_dir.is_dir():
                    continue
                flat = self.localizations.setdefault(lang_dir.name.lower(), {})
                for locres in sorted(lang_dir.glob("*.locres")):
                    try:
                        resource = FTextLocalizationResource(BinaryStream(str(locres))).GetValue()
                    except Exception:
                        continue
                    for _, entries in resource.items():
                        for key, value in entries.items():
                            flat[str(key).lower()] = repair_mojibake(value)

    def _load_items(self) -> None:
        for path in self.textdata_dir.glob("ItemTable_Data_*.json"):
            try:
                payload = load_json(path)
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                item_id = normalize_text(row.get("Name"))
                if not item_id:
                    continue
                self.item_index[item_id] = row

        for item_id, row in self.item_index.items():
            name = self._item_name(row, "en")
            if not name:
                continue
            self.item_name_index[name.lower()] = row

    def _load_drop_tables(self) -> None:
        try:
            drop_groups = load_drop_groups(self.textdata_dir / "DropGroupTable.json")
        except Exception:
            drop_groups = []
        try:
            drop_packs = load_json(self.textdata_dir / "DropPackTable.json")
        except Exception:
            drop_packs = []

        if isinstance(drop_groups, list):
            self.drop_groups = {
                normalize_text(row.get("Name")): row
                for row in drop_groups
                if isinstance(row, dict) and normalize_text(row.get("Name"))
            }

        if isinstance(drop_packs, list):
            for row in drop_packs:
                if not isinstance(row, dict):
                    continue
                if normalize_text(row.get("DropType")).lower() != "item":
                    continue
                key = normalize_text(row.get("DropPack_Key"))
                if not key:
                    continue
                self.drop_packs_by_group.setdefault(key, []).append(row)

    def _load_mining_table(self) -> None:
        path = self.textdata_dir / "MiningObjectTable.json"
        try:
            payload = load_json(path)
        except Exception:
            return
        if not isinstance(payload, list):
            return

        for row in payload:
            if not isinstance(row, dict):
                continue
            group_key = normalize_text(row.get("DropGroupTid"))
            actor = row.get("ActorTid") or {}
            actor_tid = normalize_text(actor.get("string_tid") if isinstance(actor, dict) else actor)
            if not actor_tid or not actor_tid.startswith("ad_mining_"):
                continue
            alias = re.sub(r"^ad_mining_", "", actor_tid)
            alias = re.sub(r"_\d+$", "", alias)
            if not alias:
                continue
            if group_key:
                local_key = normalize_text(row.get("Local_Key"))
                item_match = re.search(r"(\d{9})$", local_key)
                self.mining_actor_lookup[token_signature(alias)] = {
                    "group_key": group_key,
                    "item_id": item_match.group(1) if item_match else "",
                }

    def _build_gathering_lookup(self) -> None:
        for group_key in self.drop_groups:
            if group_key.startswith("gathering_"):
                self.gathering_group_lookup[token_signature(group_key[10:])] = group_key
            elif group_key.startswith("specialproduct_"):
                self.gathering_group_lookup[token_signature(group_key[15:])] = group_key

    def _localize(self, key: str, lang: str) -> str:
        if not key:
            return ""
        return repair_mojibake(self.localizations.get(lang.lower(), {}).get(key.lower(), ""))

    def _item_name(self, item: Optional[Dict], lang: str) -> str:
        if not item:
            return ""
        key = normalize_text(item.get("Local_DropKey")) or normalize_text(item.get("Local_Key"))
        return self._localize(key, lang)

    def _item_description(self, item: Optional[Dict], lang: str) -> str:
        if not item:
            return ""
        return self._localize(normalize_text(item.get("Local_Desc")), lang)

    def _best_pack_item(self, group_key: str, preferred_item_id: str = "", mining_mode: bool = False) -> Optional[Dict]:
        pack_rows = self.drop_packs_by_group.get(group_key) or []
        if not pack_rows:
            group = self.drop_groups.get(group_key) or {}
            pack_keys = group.get("DropPack_Key") or []
            pack_rows = [
                row
                for key in pack_keys
                for row in self.drop_packs_by_group.get(normalize_text(key), [])
            ]
        if not pack_rows:
            return None
        if preferred_item_id:
            for row in pack_rows:
                if normalize_text(row.get("Item_Tid")) == preferred_item_id:
                    return self.item_index.get(preferred_item_id)
        if mining_mode:
            mining_specific = [row for row in pack_rows if normalize_text(row.get("Item_Tid")) != "101010000"]
            if mining_specific:
                pack_rows = mining_specific
        ordered = sorted(
            pack_rows,
            key=lambda row: (
                -int(row.get("Rate", 0) or 0),
                -int(row.get("Min_Cnt", 0) or 0),
                str(row.get("Item_Tid") or ""),
            ),
        )
        item_id = normalize_text(ordered[0].get("Item_Tid"))
        return self.item_index.get(item_id)

    def _resource_payload(
        self,
        *,
        resolved_type: str,
        raw_slug: str,
        item: Optional[Dict],
        group_key: str = "",
        source: str,
        confidence: str,
    ) -> Dict[str, str]:
        item_id = normalize_text(item.get("Name")) if item else ""
        label_en = self._item_name(item, "en") or humanize_slug(raw_slug)
        label_fr = self._item_name(item, "fr")
        desc_en = self._item_description(item, "en")
        desc_fr = self._item_description(item, "fr")
        grade = normalize_grade(item.get("Grade")) if item else ""
        rarity = RARITY_BY_GRADE.get(grade, {})
        return {
            "type": resolved_type,
            "label": label_en,
            "description": desc_en,
            "subcategory": raw_slug,
            "subcategory_label": label_en,
            "resource_name": label_en,
            "resource_name_fr": label_fr,
            "resource_description": desc_en,
            "resource_description_fr": desc_fr,
            "resource_item_id": item_id,
            "resource_drop_group": group_key,
            "resource_icon_name": normalize_text(item.get("IconName")) if item else "",
            "resource_rarity_grade": grade,
            "resource_rarity_rank": rarity.get("rank", ""),
            "resource_rarity_color": rarity.get("color", ""),
            "resource_rarity_hex": rarity.get("hex", ""),
            "resolution_source": source,
            "resolution_confidence": confidence,
        }

    def _fallback_payload(self, *, raw_slug: str, resolved_type: str = "gathering") -> Dict[str, str]:
        label = humanize_slug(raw_slug)
        return {
            "type": resolved_type,
            "label": label,
            "description": "",
            "subcategory": raw_slug,
            "subcategory_label": label,
            "resource_name": label,
            "resource_name_fr": "",
            "resource_description": "",
            "resource_description_fr": "",
            "resource_item_id": "",
            "resource_drop_group": "",
            "resource_icon_name": "",
            "resource_rarity_grade": "",
            "resource_rarity_rank": "",
            "resource_rarity_color": "",
            "resource_rarity_hex": "",
            "resolution_source": "fallback-name",
            "resolution_confidence": "low",
        }

    def _weapon_payload(self, raw_slug: str) -> Dict[str, str]:
        labels = WEAPON_LABELS.get(raw_slug, {})
        label_en = labels.get("en") or humanize_slug(raw_slug)
        label_fr = labels.get("fr", "")
        return {
            "type": "weapons",
            "label": label_en,
            "description": "",
            "subcategory": raw_slug,
            "subcategory_label": label_en,
            "resource_name": label_en,
            "resource_name_fr": label_fr,
            "resource_description": "",
            "resource_description_fr": "",
            "resource_item_id": "",
            "resource_drop_group": "",
            "resource_icon_name": "",
            "resource_rarity_grade": "",
            "resource_rarity_rank": "",
            "resource_rarity_color": "",
            "resource_rarity_hex": "",
            "resolution_source": "weapon-alias",
            "resolution_confidence": "medium",
        }

    def _resolve_group(
        self,
        group_key: str,
        *,
        resolved_type: str,
        raw_slug: str,
        source: str,
        preferred_item_id: str = "",
    ) -> Optional[Dict[str, str]]:
        if not group_key:
            return None
        item = self._best_pack_item(
            group_key,
            preferred_item_id=preferred_item_id,
            mining_mode=resolved_type == "mining",
        )
        if not item and resolved_type == "gathering":
            return self._fallback_payload(raw_slug=raw_slug)
        confidence = "strong" if item else "low"
        return self._resource_payload(
            resolved_type=resolved_type,
            raw_slug=raw_slug,
            item=item,
            group_key=group_key,
            source=source,
            confidence=confidence,
        )

    def _resolve_item_name(self, item_name: str, raw_slug: str) -> Optional[Dict[str, str]]:
        item = self.item_name_index.get(item_name.lower())
        if not item:
            return None
        return self._resource_payload(
            resolved_type="gathering",
            raw_slug=raw_slug,
            item=item,
            group_key="",
            source="localized-item-name",
            confidence="medium",
        )

    def _resolve_item_id(self, item_id: str, raw_slug: str, *, resolved_type: str, source: str) -> Optional[Dict[str, str]]:
        item = self.item_index.get(item_id)
        if not item:
            return None
        return self._resource_payload(
            resolved_type=resolved_type,
            raw_slug=raw_slug,
            item=item,
            group_key="",
            source=source,
            confidence="strong",
        )

    def _extract_resource_slug(self, name: str, needle: str) -> Optional[str]:
        m = re.search(rf"(?:Common|Uncommon|Magic)_{needle}_([A-Za-z0-9]+)", name, re.IGNORECASE)
        if not m:
            return None
        return snake_case_from_camel(m.group(1))

    def resolve(self, name: str, candidate_type: str) -> Optional[Dict[str, str]]:
        if not self.enabled:
            return None

        raw_name = normalize_text(name)
        lowered = raw_name.lower()

        if candidate_type == "mining" and "common_gathering_" in lowered:
            return self._resolve_gathering(raw_name)
        if candidate_type == "mining":
            return self._resolve_mining(raw_name)
        if candidate_type == "mastery":
            return self._resolve_mastery(raw_name)
        if candidate_type == "gathering":
            return self._resolve_gathering(raw_name)
        return None

    def _resolve_mining(self, name: str) -> Optional[Dict[str, str]]:
        slug = self._extract_resource_slug(name, "Mining")
        if slug:
            if slug == "bone_fragment_bird":
                return self._resolve_group(
                    "gathering_bird_bone_fragment",
                    resolved_type="gathering",
                    raw_slug=slug,
                    source="cross-category-mining-alias",
                )

            base = re.sub(r"_(vein|lode)$", "", slug)
            mining_meta = self.mining_actor_lookup.get(token_signature(base))
            group_key = normalize_text(mining_meta.get("group_key")) if mining_meta else ""
            preferred_item_id = normalize_text(mining_meta.get("item_id")) if mining_meta else ""
            if not group_key:
                candidate = f"mining_ore_{base}"
                if candidate in self.drop_groups:
                    group_key = candidate
            if not group_key:
                return None
            return self._resolve_group(
                group_key,
                resolved_type="mining",
                raw_slug=slug,
                source="mining-object",
                preferred_item_id=preferred_item_id,
            )

        sample = re.search(r"Obj_Miningitem_([A-Za-z]+)", name)
        if sample:
            base = sample.group(1).lower()
            group_key = f"mining_ore_{base}"
            if group_key in self.drop_groups:
                return self._resolve_group(group_key, resolved_type="mining", raw_slug=f"{base}_vein", source="sample-object")
        return None

    def _resolve_gathering(self, name: str) -> Optional[Dict[str, str]]:
        slug = self._extract_resource_slug(name, "Gathering")
        if not slug:
            return None

        if slug in WEAPON_LABELS:
            return self._weapon_payload(slug)

        if slug in RESOURCE_BLACKLIST.get("gathering", set()):
            return None

        alias_group = GATHERING_GROUP_ALIASES.get(slug)
        if alias_group:
            return self._resolve_group(alias_group, resolved_type="gathering", raw_slug=slug, source="alias")

        exact_group = self.gathering_group_lookup.get(token_signature(slug))
        if exact_group:
            return self._resolve_group(exact_group, resolved_type="gathering", raw_slug=slug, source="drop-group")

        item_name = GATHERING_ITEM_NAME_FALLBACKS.get(slug)
        if item_name:
            resolved = self._resolve_item_name(item_name, slug)
            if resolved:
                return resolved

        return self._fallback_payload(raw_slug=slug)

    def _resolve_mastery(self, name: str) -> Optional[Dict[str, str]]:
        slug = self._extract_resource_slug(name, "Mastery")
        if not slug:
            return None

        item_id = MASTERY_ITEM_IDS.get(slug)
        if item_id:
            resolved = self._resolve_item_id(
                item_id,
                slug,
                resolved_type="mastery",
                source="mastery-item-id",
            )
            if resolved:
                return resolved

        return self._fallback_payload(raw_slug=slug, resolved_type="mastery")
