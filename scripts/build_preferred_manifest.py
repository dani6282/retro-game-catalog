#!/usr/bin/env python3
"""Select one preferred C64 and Amiga release per normalized game title."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from title_normalization import ascii_fold, clean_title, detect_language, is_non_game, title_key


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "public" / "catalog.json"
OUT_PATH = ROOT / "public" / "preferred-manifest.json"

PLATFORM_FAMILIES = {
    "c64": "c64",
    "amiga": "amiga",
    "amiga500": "amiga",
    "amiga1200": "amiga",
    "amigacd32": "amiga",
    "amigacdtv": "amiga",
}

SUPPORT_DIRECTORIES = {"audio", "data", "in", "roms"}
EXTRA_CATEGORIES = {"BETA", "Mags"}
EXTRA_MARKERS = (
    " coverdisk",
    " cover disk",
    " demo",
    " magic disk",
    " preview",
    " prototype",
    " trainer",
)

LANGUAGE_RANK = {
    "German": 0,
    "English": 1,
    None: 1,
    "French": 2,
    "Italian": 2,
    "Spanish": 2,
}

AMIGA_CATEGORY_RANK = {
    "AGA": 0,
    "CD32": 1,
    "CDTV": 1,
    "Cinemaware": 2,
    "OCS": 2,
    "Foreign": 3,
    "NTSC": 4,
    "ARCADIA": 5,
    "BETA": 8,
    "Mags": 9,
}

REGION_RANK = {
    "germany": 0,
    "europe": 1,
    "world": 1,
    "uk": 1,
    "usa": 2,
}


def platform_family(entry: dict) -> str | None:
    return PLATFORM_FAMILIES.get(str(entry.get("platform") or "").lower())


def release_identity(entry: dict) -> str:
    """Keep release/region markers but collapse disk and side components."""

    value = clean_title(entry.get("title") or Path(entry.get("path") or "").stem)
    media = re.search(
        r"\s*(?:\([^)]*\b(?:disk|disc|side)\b[^)]*\)|\b(?:disk|disc|side)\s*(?:of\s*)?[a-z0-9]+\b)",
        value,
        flags=re.I,
    )
    if media:
        value = value[: media.start()]
    value = ascii_fold(value).lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def entry_language(entry: dict) -> str | None:
    return detect_language(entry.get("title"), entry.get("path"), entry.get("category")) or entry.get("language")


def is_extra(entry: dict) -> bool:
    if entry.get("category") in EXTRA_CATEGORIES:
        return True
    haystack = f" {entry.get('title') or ''} {entry.get('path') or ''}".lower()
    return any(marker in haystack for marker in EXTRA_MARKERS)


def is_support_entry(entry: dict) -> bool:
    return (
        entry.get("source") == "PiMiga"
        and entry.get("collection") == "Installed"
        and str(entry.get("path") or "").strip("/").lower() in SUPPORT_DIRECTORIES
    )


def candidate_key(entry: dict) -> tuple:
    return (
        entry.get("source"),
        entry.get("collection"),
        entry.get("category"),
        entry_language(entry),
        release_identity(entry),
    )


def region_rank(candidate: dict) -> int:
    haystack = candidate_text(candidate).lower()
    return min((rank for marker, rank in REGION_RANK.items() if marker in haystack), default=1)


def candidate_text(candidate: dict) -> str:
    return " ".join(asset.get("title") or "" for asset in candidate["assets"])


def c64_quality_rank(candidate: dict) -> tuple[int, ...]:
    text = candidate_text(candidate).lower()
    unofficial_rank = 1 if "(unl)" in text or "unlicensed" in text else 0
    explicit_region_rank = 0 if re.search(r"\((?:europe|world|uk|germany)\)", text) else 1
    completeness_rank = -len(candidate["assets"])
    return (unofficial_rank, explicit_region_rank, completeness_rank)


def amiga_quality_rank(candidate: dict) -> tuple[int, ...]:
    text = candidate_text(candidate).lower()
    category = candidate.get("category")
    launchable_rank = 0 if candidate.get("hasLaunchableFiles") is not False else 1
    ntsc_rank = 1 if "ntsc" in text else 0
    incomplete_rank = 1 if any(marker in text for marker in ("no music", "nomusic", "demo")) else 0

    if category in {"AGA", "Foreign"}:
        if "aga" in text:
            edition_rank = 0
        elif "cd32" in text:
            edition_rank = 2
        elif "cdtv" in text:
            edition_rank = 3
        else:
            edition_rank = 1
    elif category == "CD32":
        edition_rank = 0 if "cd32" in text else 1
    elif category == "CDTV":
        edition_rank = 0 if "cdtv" in text else 1
    else:
        edition_rank = 0

    completeness_rank = -len(candidate["assets"])
    return (launchable_rank, ntsc_rank, incomplete_rank, edition_rank, completeness_rank)


def candidate_priority(candidate: dict) -> tuple[int, ...]:
    language = candidate["language"]
    language_rank = LANGUAGE_RANK.get(language, 3)
    if candidate["platform"] == "c64":
        return (language_rank, region_rank(candidate), *c64_quality_rank(candidate))

    whdload_rank = 0 if candidate["collection"] == "WHDLoad" else 1
    category_rank = AMIGA_CATEGORY_RANK.get(candidate.get("category"), 3)
    source_rank = 0 if candidate["library"] == "PiMiga" else 1
    quality = amiga_quality_rank(candidate)
    return (language_rank, whdload_rank, quality[0], category_rank, source_rank, *quality[1:])


def compact_asset(entry: dict) -> dict:
    return {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "path": entry.get("path"),
        "absolutePath": entry.get("absolutePath"),
        "format": entry.get("format"),
        "sizeBytes": entry.get("sizeBytes"),
        "fileCount": entry.get("fileCount"),
        "hasLaunchableFiles": entry.get("hasLaunchableFiles"),
    }


def make_candidate(family: str, entries: list[dict]) -> dict:
    first = entries[0]
    candidate = {
        "platform": family,
        "library": first.get("source"),
        "collection": first.get("collection"),
        "category": first.get("category"),
        "language": entry_language(first),
        "releaseIdentity": release_identity(first),
        "assets": [compact_asset(entry) for entry in sorted(entries, key=lambda item: item.get("path") or "")],
    }
    launchability = {entry.get("hasLaunchableFiles") for entry in entries}
    candidate["hasLaunchableFiles"] = (
        True if True in launchability else False if launchability == {False} else None
    )
    candidate["priority"] = list(candidate_priority(candidate))
    return candidate


def review_reasons(candidates: list[dict], selected: dict) -> list[str]:
    reasons = []
    same_language = [
        candidate
        for candidate in candidates
        if candidate["language"] == selected["language"] and candidate.get("hasLaunchableFiles") is not False
    ]
    categories = {candidate.get("category") for candidate in same_language if candidate.get("category")}
    if selected["platform"] == "amiga" and len(categories & {"AGA", "OCS", "CD32", "CDTV"}) > 1:
        reasons.append("competing-amiga-hardware-editions")
    if selected["collection"] == "Installed":
        reasons.append("installed-pimiga-title-needs-launch-review")
    if sum(candidate["priority"] == selected["priority"] for candidate in candidates) > 1:
        reasons.append("equal-priority-candidates")
    return reasons


def build_manifest(raw: dict) -> dict:
    grouped_entries: dict[tuple[str, str], list[dict]] = {}
    excluded = []

    for entry in raw["games"]:
        family = platform_family(entry)
        if not family:
            continue
        if is_non_game(entry.get("title", ""), entry.get("path", "")) or is_support_entry(entry):
            excluded.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "path": entry.get("path"),
                    "reason": "non-game-or-support-entry",
                }
            )
            continue
        key = title_key(entry.get("title", "")) or entry.get("normalizedTitle") or entry["id"]
        grouped_entries.setdefault((family, key), []).append(entry)

    selected_records = []
    rejected_records = []
    extra_records = []
    review_records = []

    for (family, key), entries in sorted(grouped_entries.items()):
        by_candidate: dict[tuple, list[dict]] = {}
        for entry in entries:
            by_candidate.setdefault(candidate_key(entry), []).append(entry)
        candidates = [make_candidate(family, values) for values in by_candidate.values()]
        candidates.sort(key=lambda candidate: (candidate_priority(candidate), candidate["releaseIdentity"]))
        main_candidates = [candidate for candidate in candidates if not any(is_extra(entry) for entry in entries_for(candidate, by_candidate))]
        extras = [candidate for candidate in candidates if candidate not in main_candidates]

        for candidate in extras:
            extra_records.append({"groupKey": f"{family}:{key}", **candidate})
        if not main_candidates:
            continue

        selected = main_candidates[0]
        reasons = review_reasons(main_candidates, selected)
        selected_record = {
            "groupKey": f"{family}:{key}",
            "titleKey": key,
            "platform": family,
            "language": selected["language"],
            "targetCollection": "main",
            "reviewRequired": bool(reasons),
            "reviewReasons": reasons,
            "candidate": selected,
        }
        selected_records.append(selected_record)
        if reasons:
            review_records.append(selected_record)

        for candidate in main_candidates[1:]:
            rejected_records.append(
                {
                    "groupKey": f"{family}:{key}",
                    "candidate": candidate,
                    "reason": "lower-preference-than-selected",
                }
            )

    language_counts = Counter(record["language"] or "Neutral" for record in selected_records)
    platform_counts = Counter(record["platform"] for record in selected_records)
    multidisk_count = sum(len(record["candidate"]["assets"]) > 1 for record in selected_records)
    return {
        "generatedAt": raw.get("generatedAt"),
        "sourceRoots": raw.get("sourceRoots", {}),
        "policy": {
            "scope": "one release per normalized title per platform family",
            "languageOrder": ["German", "English or neutral", "other language"],
            "platformFamilies": PLATFORM_FAMILIES,
        },
        "summary": {
            "selected": len(selected_records),
            "rejected": len(rejected_records),
            "extras": len(extra_records),
            "needsReview": len(review_records),
            "excluded": len(excluded),
            "multidiskOrMultiside": multidisk_count,
            "selectedByPlatform": dict(sorted(platform_counts.items())),
            "selectedByLanguage": dict(sorted(language_counts.items())),
        },
        "selected": selected_records,
        "rejected": rejected_records,
        "extras": extra_records,
        "needsReview": review_records,
        "excluded": excluded,
    }


def entries_for(candidate: dict, grouped: dict[tuple, list[dict]]) -> list[dict]:
    signature = (
        candidate["library"],
        candidate["collection"],
        candidate["category"],
        candidate["language"],
        candidate["releaseIdentity"],
    )
    return grouped[signature]


def main() -> int:
    manifest = build_manifest(json.loads(RAW_PATH.read_text()))
    OUT_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    for key, value in manifest["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
