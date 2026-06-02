#!/usr/bin/env python3
"""Build the compact browser catalog from the raw disk inventory."""

from __future__ import annotations

import json
import math
from pathlib import Path

from title_normalization import display_title, is_non_game, title_key


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "public" / "catalog.json"
WIKI_PATH = ROOT / "public" / "wiki-links.json"
RANKS_PATH = ROOT / "public" / "community-ranks.json"
INDEX_PATH = ROOT / "public" / "game-index.json"
DETAILS_DIR = ROOT / "public" / "details"

POPULAR_TITLE_HINTS = {
    "bubble bobble",
    "civilization",
    "defender of the crown",
    "doom",
    "elite",
    "gauntlet",
    "giana sisters",
    "lemmings",
    "maniac mansion",
    "monkey island",
    "pac man",
    "ports of call",
    "prince of persia",
    "rtype",
    "secret of monkey island",
    "sensible soccer",
    "speedball",
    "stunt car racer",
    "turrican",
    "zak mckracken",
}


def unique(values: list[str | None]) -> list[str]:
    return sorted({value for value in values if value}, key=str.casefold)


def has_metadata(entry: dict) -> bool:
    return any(entry.get(key) for key in ["genre", "developer", "publisher", "rating", "description", "players"])


def format_label(entry: dict) -> str:
    if entry.get("collection") == "WHDLoad":
        return "WHDLoad"
    if entry.get("collection") == "Installed":
        return "Installed"
    if entry.get("platform") == "scummvm":
        return "ScummVM"
    if entry.get("source") == "Batocera":
        return "ROM file"
    return "File"


def variant_label(entry: dict) -> str:
    return " / ".join([value for value in [entry.get("language"), entry.get("category"), format_label(entry)] if value])


def heuristic_score(group: dict) -> int:
    title = group["title"].lower()
    hint_score = 100 if any(hint in title for hint in POPULAR_TITLE_HINTS) else 0
    both_score = 35 if len(group["libraries"]) > 1 else 0
    metadata_score = 12 if group["hasMetadata"] else 0
    variant_score = min(group["variantCount"], 15) * 2
    ratings = []
    for entry in group["_entries"]:
        try:
            ratings.append(float(entry.get("rating") or "nan"))
        except ValueError:
            pass
    ratings = [rating for rating in ratings if math.isfinite(rating)]
    rating_score = (sum(ratings) / len(ratings) * 20) if ratings else 0
    return round(hint_score + both_score + metadata_score + variant_score + rating_score)


def community_score(ranks: list[dict]) -> int:
    if not ranks:
        return 0
    best_rank = min(rank["rank"] for rank in ranks)
    best_votes = max((rank.get("votes") or 0) for rank in ranks)
    vote_bonus = min(best_votes // 50, 15)
    return 1000 + max(0, 101 - best_rank) * 8 + vote_bonus


def title_weight(title: str | None) -> int:
    return sum(1 for char in title or "" if char.isalnum())


def best_local_title(entries: list[dict]) -> str:
    titles = unique([display_title(entry.get("title", "")) for entry in entries])
    return sorted(titles, key=lambda title: (-title_weight(title), title.casefold()))[0] if titles else ""


def compact_rank(rank: dict) -> dict:
    return {
        "title": rank.get("title"),
        "sourceId": rank.get("sourceId"),
        "sourceName": rank.get("sourceName"),
        "sourceFamily": rank.get("sourceFamily"),
        "sourcePriority": rank.get("sourcePriority"),
        "platform": rank.get("platform"),
        "rank": rank.get("rank"),
        "score": rank.get("score"),
        "votes": rank.get("votes"),
        "url": rank.get("url"),
    }


def compact_variant(entry: dict) -> dict:
    return {
        "title": entry.get("title"),
        "library": entry.get("source"),
        "platform": entry.get("platform"),
        "format": format_label(entry),
        "language": entry.get("language"),
        "category": entry.get("category"),
        "path": entry.get("path"),
        "genre": entry.get("genre"),
        "developer": entry.get("developer"),
        "publisher": entry.get("publisher"),
        "players": entry.get("players"),
        "rating": entry.get("rating"),
    }

def detail_bucket(key: str) -> str:
    first = (key[:1] or "_").lower()
    if first.isdigit():
        return "0-9"
    if first.isalpha():
        return first
    return "_"


def main() -> int:
    raw = json.loads(RAW_PATH.read_text())
    wiki = json.loads(WIKI_PATH.read_text()).get("links", {}) if WIKI_PATH.exists() else {}
    rank_payload = json.loads(RANKS_PATH.read_text()) if RANKS_PATH.exists() else {"byKey": {}, "sources": []}
    community_ranks = rank_payload.get("byKey", {})
    groups_by_key: dict[str, dict] = {}
    included_entries = [entry for entry in raw["games"] if not is_non_game(entry.get("title", ""), entry.get("path", ""))]
    excluded_non_games = len(raw["games"]) - len(included_entries)

    for entry in included_entries:
        key = title_key(entry["title"]) or entry.get("normalizedTitle") or entry["id"]
        groups_by_key.setdefault(key, {"key": key, "title": display_title(entry["title"]) or entry["title"], "_entries": []})
        groups_by_key[key]["_entries"].append(entry)

    groups = []
    details_by_bucket: dict[str, dict] = {}
    for group in groups_by_key.values():
        entries = group["_entries"]
        group["title"] = best_local_title(entries) or group["title"]
        variants = sorted(entries, key=lambda item: (item.get("source") or "", variant_label(item), item.get("path") or ""))
        descriptions = unique([entry.get("description") for entry in entries])[:2]
        metadata_bits = unique(
            [value for entry in entries for value in [entry.get("genre"), entry.get("developer"), entry.get("publisher")] if value]
        )[:4]
        ranks = [compact_rank(rank) for rank in community_ranks.get(group["key"], [])]
        if ranks and title_weight(ranks[0]["title"]) >= title_weight(group["title"]):
            group["title"] = ranks[0]["title"]
        bucket = detail_bucket(group["key"])
        details_by_bucket.setdefault(bucket, {})[group["key"]] = {
            "descriptions": descriptions,
            "variants": [compact_variant(entry) for entry in variants],
        }
        group.update(
            {
                "variantCount": len(entries),
                "libraries": unique([entry.get("source") for entry in entries]),
                "platforms": unique([entry.get("platform") for entry in entries]),
                "formats": unique([format_label(entry) for entry in entries]),
                "languages": unique([entry.get("language") for entry in entries]),
                "categories": unique([entry.get("category") for entry in entries]),
                "hasMetadata": any(has_metadata(entry) for entry in entries),
                "hasDescription": bool(descriptions),
                "metadataBits": metadata_bits,
                "communityRanks": ranks,
                "communityScore": community_score(ranks),
                "wiki": wiki.get(group["key"]),
                "detailFile": f"details/{bucket}.json",
            }
        )
        group["heuristicScore"] = heuristic_score(group)
        group["popularity"] = group["communityScore"] + group["heuristicScore"]
        group["searchText"] = " ".join(
            [
                group["title"],
                " ".join(group["libraries"]),
                " ".join(group["platforms"]),
                " ".join(group["formats"]),
                " ".join(group["languages"]),
                " ".join(group["categories"]),
                " ".join(group["metadataBits"]),
                " ".join(rank["sourceName"] for rank in group["communityRanks"]),
                group["wiki"]["article"] if group["wiki"] else "",
                *[
                    " ".join(
                        str(value or "")
                        for value in [
                            variant["title"],
                            variant["genre"],
                            variant["developer"],
                            variant["publisher"],
                            variant["players"],
                        ]
                    )
                    for variant in details_by_bucket[bucket][group["key"]]["variants"]
                ],
            ]
        ).lower()
        del group["_entries"]
        groups.append(group)

    groups.sort(key=lambda group: (-group["popularity"], group["title"].casefold()))
    by_source: dict[str, int] = {}
    for entry in included_entries:
        by_source[entry["source"]] = by_source.get(entry["source"], 0) + 1
    payload = {
        "generatedAt": raw.get("generatedAt"),
        "sourceRoots": raw.get("sourceRoots", {}),
            "summary": {
                "games": len(groups),
                "variants": len(included_entries),
                "rawVariants": raw["summary"]["total"],
                "excludedNonGames": excluded_non_games,
                "bySource": dict(sorted(by_source.items())),
                "inBothLibraries": sum(1 for group in groups if len(group["libraries"]) > 1),
                "variantsInBothLibraries": sum(group["variantCount"] for group in groups if len(group["libraries"]) > 1),
                "withMetadata": sum(1 for group in groups if group["hasMetadata"]),
                "withWiki": sum(1 for group in groups if group["wiki"]),
                "withCommunityRank": sum(1 for group in groups if group["communityRanks"]),
            },
            "communityRankSources": rank_payload.get("sources", []),
        "groups": groups,
    }
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    for old in DETAILS_DIR.glob("*.json"):
        old.unlink()
    for bucket, details in details_by_bucket.items():
        (DETAILS_DIR / f"{bucket}.json").write_text(json.dumps(details, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {INDEX_PATH}")
    print(f"Detail chunks: {len(details_by_bucket)}")
    print(f"Games: {payload['summary']['games']}")
    print(f"Index size: {INDEX_PATH.stat().st_size / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
