#!/usr/bin/env python3
"""Audit catalog grouping, variant conservation, and community-rank matching."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "public" / "catalog.json"
INDEX_PATH = ROOT / "public" / "game-index.json"
DETAILS_DIR = ROOT / "public" / "details"
RANKS_PATH = ROOT / "public" / "community-ranks.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def detail_variant_count(groups: list[dict]) -> int:
    cache: dict[str, dict] = {}
    total = 0
    for group in groups:
        detail_file = group["detailFile"]
        if detail_file not in cache:
            cache[detail_file] = load_json(ROOT / "public" / detail_file)
        total += len(cache[detail_file][group["key"]]["variants"])
    return total


def find_group(groups_by_key: dict[str, dict], key: str) -> dict | None:
    return groups_by_key.get(key)


def main() -> int:
    raw = load_json(RAW_PATH)
    index = load_json(INDEX_PATH)
    ranks = load_json(RANKS_PATH) if RANKS_PATH.exists() else {"rankings": [], "byKey": {}}
    groups = index["groups"]
    groups_by_key = {group["key"]: group for group in groups}
    failures: list[str] = []

    variant_sum = sum(group["variantCount"] for group in groups)
    detail_sum = detail_variant_count(groups)
    summary_variants = index["summary"]["variants"]
    if variant_sum != summary_variants:
        failures.append(f"group variant sum {variant_sum} != summary variants {summary_variants}")
    if detail_sum != summary_variants:
        failures.append(f"detail variant sum {detail_sum} != summary variants {summary_variants}")

    non_game_groups = [group for group in groups if "zzz(notgame)" in group["searchText"] or "zzz notgame" in group["searchText"]]
    if non_game_groups:
        failures.append(f"{len(non_game_groups)} non-game utility groups leaked into the game index")

    separated_pairs = [
        ("backtothefuture", "backtothefuturepart2"),
        ("backtothefuture", "backtothefuturepart3"),
        ("internationalkarate", "internationalkarateplus"),
        ("uridium", "uridiumplus"),
    ]
    for left, right in separated_pairs:
        if left not in groups_by_key or right not in groups_by_key:
            failures.append(f"expected separate groups {left!r} and {right!r}")

    collapsed_disk_sets = [
        "ishar2messengersofdoom",
        "ishar3thesevengatesofinfinity",
        "formulaonegrandprix",
        "burntime",
    ]
    for key in collapsed_disk_sets:
        group = find_group(groups_by_key, key)
        if not group:
            failures.append(f"expected collapsed disk group {key!r}")
        elif group["variantCount"] < 2:
            failures.append(f"expected multiple variants in collapsed disk group {key!r}")

    rank_rows = ranks.get("rankings", [])
    ranked_keys = set(ranks.get("byKey", {}))
    matched_rank_keys = ranked_keys & set(groups_by_key)
    unmatched_rank_keys = sorted(ranked_keys - set(groups_by_key))

    print("Catalog matching audit")
    print(f"Raw entries: {raw['summary']['total']}")
    print(f"Game variants: {summary_variants}")
    print(f"Excluded non-games: {index['summary'].get('excludedNonGames', 0)}")
    print(f"Grouped games: {index['summary']['games']}")
    print(f"Groups in both libraries: {index['summary']['inBothLibraries']}")
    print(f"Variants in both-library groups: {index['summary'].get('variantsInBothLibraries', 0)}")
    print(f"Community rank rows: {len(rank_rows)}")
    print(f"Unique ranked keys: {len(ranked_keys)}")
    print(f"Ranked keys matched locally: {len(matched_rank_keys)}")
    print(f"Ranked keys not present locally: {len(unmatched_rank_keys)}")
    if unmatched_rank_keys:
        preview = ", ".join(unmatched_rank_keys[:12])
        print(f"Unmatched preview: {preview}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
