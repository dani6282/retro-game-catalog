#!/usr/bin/env python3
"""Audit the preferred C64/Amiga selection manifest."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from build_preferred_manifest import review_action


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "public" / "preferred-manifest.json"


def audit_manifest(manifest: dict) -> list[str]:
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
    review_by_group = {record["groupKey"]: record for record in manifest["needsReview"]}
    expected_review_groups = {
        record["groupKey"] for record in selected if record.get("reviewRequired", False)
    }
    if set(review_by_group) != expected_review_groups:
        failures.append("needsReview does not match selected records requiring review")

    for record in selected:
        disposition = record.get("reviewDisposition")
        if record.get("reviewRequired", False):
            if not disposition:
                failures.append(f"{record['groupKey']} has no review disposition")
                continue
            if disposition.get("status") != "deferred-to-build-validation":
                failures.append(f"{record['groupKey']} has an invalid review disposition status")
            if disposition.get("phase1Blocking") is not False:
                failures.append(f"{record['groupKey']} remains Phase 1 blocking")
            actions = disposition.get("actions", [])
            if [action.get("reason") for action in actions] != record["reviewReasons"]:
                failures.append(f"{record['groupKey']} review actions do not match review reasons")
            for action in actions:
                expected = review_action(record["platform"], action.get("reason"))
                if action != expected:
                    failures.append(f"{record['groupKey']} has an invalid review action")
        elif disposition:
            failures.append(f"{record['groupKey']} has a disposition but does not require review")

        override = record.get("manualOverride")
        if not override:
            continue
        selector = override.get("selector", {})
        if not selector or any(record["candidate"].get(field) != value for field, value in selector.items()):
            failures.append(f"{record['groupKey']} manual override does not match selected candidate")
        if not override.get("rationale"):
            failures.append(f"{record['groupKey']} manual override has no rationale")
        if not override.get("evidence"):
            failures.append(f"{record['groupKey']} manual override has no evidence")

    for rejected in manifest["rejected"]:
        chosen = selected_by_group[rejected["groupKey"]]
        if not chosen.get("manualOverride") and chosen["candidate"]["priority"] > rejected["candidate"]["priority"]:
            failures.append(f"{rejected['groupKey']} selected a lower-priority candidate")
        if rejected["candidate"]["language"] == "German" and chosen["language"] != "German":
            failures.append(f"{rejected['groupKey']} rejected German for {chosen['language'] or 'neutral'}")

    actual_queue_counts = Counter(
        action["queue"]
        for record in manifest["needsReview"]
        for action in record.get("reviewDisposition", {}).get("actions", [])
    )
    summary = manifest.get("summary", {})
    if (
        "reviewActionsByQueue" in summary
        and summary["reviewActionsByQueue"] != dict(sorted(actual_queue_counts.items()))
    ):
        failures.append("reviewActionsByQueue summary does not match review dispositions")
    if summary.get("phase1BlockingReviews", 0) != 0:
        failures.append("phase1BlockingReviews summary is not zero")

    return failures


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    selected = manifest["selected"]
    failures = audit_manifest(manifest)

    german_groups = sum(record["language"] == "German" for record in selected)
    multidisk_groups = sum(len(record["candidate"]["assets"]) > 1 for record in selected)
    review_groups = len(manifest["needsReview"])

    print("Preferred manifest audit")
    print(f"Selected groups: {len(selected)}")
    print(f"German selections: {german_groups}")
    print(f"Multidisk/multiside selections: {multidisk_groups}")
    print(f"Needs review: {review_groups}")
    print(f"Phase 1 blocking reviews: {manifest['summary'].get('phase1BlockingReviews')}")
    for queue, count in manifest["summary"].get("reviewActionsByQueue", {}).items():
        print(f"Deferred {queue}: {count}")
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
