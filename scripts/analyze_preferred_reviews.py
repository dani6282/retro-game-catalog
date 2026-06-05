#!/usr/bin/env python3
"""Summarize preferred-manifest review queues and candidate differences."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "public" / "preferred-manifest.json"

MARKERS = (
    "alt",
    "alternate",
    "arcadia",
    "beta",
    "cd32",
    "cdtv",
    "crack",
    "demo",
    "fast",
    "files",
    "fixed",
    "image",
    "ntsc",
    "ocs",
    "pal",
    "rev",
    "set",
    "slow",
    "trainer",
    "version",
    "512k",
    "1mb",
    "2mb",
    "mt32",
)


def candidates_by_group(manifest: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for record in manifest["selected"]:
        grouped.setdefault(record["groupKey"], []).append(record["candidate"])
    for record in manifest["rejected"]:
        grouped.setdefault(record["groupKey"], []).append(record["candidate"])
    return grouped


def title_text(candidate: dict) -> str:
    return " | ".join(asset.get("title") or "" for asset in candidate["assets"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", default="equal-priority-candidates")
    parser.add_argument("--platform", choices=["amiga", "c64"])
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text())
    grouped = candidates_by_group(manifest)
    reviews = [record for record in manifest["needsReview"] if args.reason in record["reviewReasons"]]
    if args.platform:
        reviews = [record for record in reviews if record["platform"] == args.platform]
    reviews.sort(key=lambda record: record["groupKey"])

    source_counts = Counter()
    candidate_counts = Counter()
    marker_counts = Counter()
    same_release_identity = 0

    for record in reviews:
        candidates = grouped[record["groupKey"]]
        selected_priority = record["candidate"]["priority"]
        tied = [candidate for candidate in candidates if candidate["priority"] == selected_priority]
        candidate_counts[len(tied)] += 1
        source_counts[
            (
                record["platform"],
                record["candidate"]["library"],
                record["candidate"]["collection"],
                record["candidate"].get("category") or "none",
            )
        ] += 1
        identities = {candidate["releaseIdentity"] for candidate in tied}
        same_release_identity += len(identities) == 1
        for candidate in tied:
            lower = title_text(candidate).lower()
            for marker in MARKERS:
                if marker in lower:
                    marker_counts[marker] += 1

    print(f"Review reason: {args.reason}")
    print(f"Groups: {len(reviews)}")
    print(f"Same release identity: {same_release_identity}")
    print("\nSelected platform/source:")
    for signature, count in source_counts.most_common():
        print(f"{count:5}  {' / '.join(signature)}")
    print("\nTied candidate counts:")
    for count, groups in sorted(candidate_counts.items()):
        print(f"{groups:5} groups with {count} tied candidates")
    print("\nTitle markers:")
    for marker, count in marker_counts.most_common():
        print(f"{count:5}  {marker}")
    print("\nCandidate samples:")
    for record in reviews[: args.limit]:
        print(f"\n### {record['groupKey']}")
        selected_priority = record["candidate"]["priority"]
        for candidate in grouped[record["groupKey"]]:
            if candidate["priority"] != selected_priority:
                continue
            print(
                "\t".join(
                    [
                        str(candidate["priority"]),
                        candidate["language"] or "Neutral",
                        candidate["library"] or "",
                        candidate["collection"] or "",
                        candidate.get("category") or "",
                        candidate["releaseIdentity"],
                        title_text(candidate),
                    ]
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
