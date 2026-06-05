#!/usr/bin/env python3
"""Audit the preferred C64/Amiga selection manifest."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "public" / "preferred-manifest.json"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    selected = manifest["selected"]
    failures = []

    group_keys = [record["groupKey"] for record in selected]
    if len(group_keys) != len(set(group_keys)):
        failures.append("selected records contain duplicate platform/title groups")

    selected_ids = [
        asset["id"]
        for record in selected
        for asset in record["candidate"]["assets"]
        if asset.get("id")
    ]
    if len(selected_ids) != len(set(selected_ids)):
        failures.append("a source asset appears in more than one selected release")

    selected_by_group = {record["groupKey"]: record for record in selected}
    for rejected in manifest["rejected"]:
        chosen = selected_by_group[rejected["groupKey"]]
        if chosen["candidate"]["priority"] > rejected["candidate"]["priority"]:
            failures.append(f"{rejected['groupKey']} selected a lower-priority candidate")
        if rejected["candidate"]["language"] == "German" and chosen["language"] != "German":
            failures.append(f"{rejected['groupKey']} rejected German for {chosen['language'] or 'neutral'}")

    german_groups = sum(record["language"] == "German" for record in selected)
    multidisk_groups = sum(len(record["candidate"]["assets"]) > 1 for record in selected)
    review_groups = len(manifest["needsReview"])

    print("Preferred manifest audit")
    print(f"Selected groups: {len(selected)}")
    print(f"German selections: {german_groups}")
    print(f"Multidisk/multiside selections: {multidisk_groups}")
    print(f"Needs review: {review_groups}")
    print(f"Extras: {len(manifest['extras'])}")
    print(f"Excluded support/non-games: {len(manifest['excluded'])}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
