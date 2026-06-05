#!/usr/bin/env python3
"""Profile runnable Amiga hardware-edition conflicts in the preferred manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "public" / "preferred-manifest.json"
GAME_INDEX_PATH = ROOT / "public" / "game-index.json"
HARDWARE_CATEGORIES = {"AGA", "OCS", "CD32", "CDTV"}
REVIEW_REASON = "competing-amiga-hardware-editions"


def candidates_by_group(manifest: dict) -> dict[str, list[dict]]:
    grouped = {record["groupKey"]: [record["candidate"]] for record in manifest["selected"]}
    for record in manifest["rejected"]:
        grouped.setdefault(record["groupKey"], []).append(record["candidate"])
    return grouped


def candidate_size(candidate: dict) -> int:
    return sum(asset.get("sizeBytes") or 0 for asset in candidate["assets"])


def candidate_title(candidate: dict) -> str:
    return " + ".join(asset.get("title") or "" for asset in candidate["assets"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=160)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--ranked", action="store_true")
    parser.add_argument("--game-index", type=Path, default=GAME_INDEX_PATH)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    game_index = json.loads(args.game_index.read_text()) if args.ranked else {"groups": []}
    index_by_key = {group["key"]: group for group in game_index["groups"]}
    grouped = candidates_by_group(manifest)
    rows = []

    for record in manifest["needsReview"]:
        if REVIEW_REASON not in record["reviewReasons"]:
            continue
        candidates = [
            candidate
            for candidate in grouped[record["groupKey"]]
            if candidate.get("hasLaunchableFiles") is not False
            and candidate.get("category") in HARDWARE_CATEGORIES
        ]
        categories = tuple(sorted({candidate["category"] for candidate in candidates}))
        identity_count = len({candidate["releaseIdentity"] for candidate in candidates})
        title_key = record["titleKey"]
        index_record = index_by_key.get(title_key, {})
        rows.append(
            (
                record["groupKey"],
                categories,
                identity_count,
                candidates,
                index_record.get("popularity", 0),
                index_record.get("communityRanks", []),
            )
        )

    if args.ranked:
        rows.sort(key=lambda row: (-row[4], row[0]))

    print(f"Runnable hardware review groups: {len(rows)}")
    print("\nCategory combinations:")
    for categories, count in Counter(row[1] for row in rows).most_common():
        print(f"{count:5}  {' / '.join(categories)}")

    print("\nRelease identity counts:")
    for identity_count, count in sorted(Counter(row[2] for row in rows).items()):
        print(f"{count:5}  groups with {identity_count} release identities")

    print("\nSame-identity category combinations:")
    for categories, count in Counter(row[1] for row in rows if row[2] == 1).most_common():
        print(f"{count:5}  {' / '.join(categories)}")

    print("\nDifferent-identity category combinations:")
    for categories, count in Counter(row[1] for row in rows if row[2] > 1).most_common():
        print(f"{count:5}  {' / '.join(categories)}")

    print("\nCandidate samples:")
    for group_key, categories, identity_count, candidates, popularity, community_ranks in rows[: args.limit]:
        descriptions = []
        for candidate in candidates:
            descriptions.append(
                ":".join(
                    [
                        candidate["category"],
                        candidate["releaseIdentity"],
                        str(candidate_size(candidate)),
                        candidate_title(candidate),
                    ]
                )
            )
        fields = [
            group_key,
            "/".join(categories),
            f"identities={identity_count}",
            f"popularity={popularity}",
            " | ".join(descriptions),
        ]
        if args.ranked:
            amiga_ranks = [rank for rank in community_ranks if rank.get("platform") == "amiga"]
            fields.append(
                " | ".join(
                    f"{rank['sourceName']} #{rank['rank']} {rank['url']}" for rank in amiga_ranks
                )
            )
        print("\t".join(fields))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
