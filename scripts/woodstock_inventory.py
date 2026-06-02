#!/usr/bin/env python3
"""Inventory the currently mounted Batocera and PiMiga game libraries.

Run this on Woodstock. It reads only from the mounted disks and writes JSON to
stdout, so callers can redirect it into the static site's public/catalog.json.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from title_normalization import clean_title, is_non_game, title_key


BATOCERA_ROMS = Path(os.environ.get("BATOCERA_ROMS", "/mnt/wd-WXF1A94HCEF5-share/roms"))
PIMIGA_GAMES = Path(os.environ.get("PIMIGA_GAMES", "/mnt/pimiga-root/home/pi/pimiga/disks/Games"))

SKIP_DIRS = {
    "3dboxes",
    "boxart",
    "covers",
    "downloaded_images",
    "hi",
    "images",
    "inp",
    "manuals",
    "media",
    "memcard",
    "music",
    "nvram",
    "saves",
    "screenshots",
    "snap",
    "titles",
    "videos",
}

ROM_EXTENSIONS = {
    ".2d",
    ".68k",
    ".7z",
    ".adf",
    ".adz",
    ".bin",
    ".cas",
    ".ccd",
    ".chd",
    ".cmd",
    ".crt",
    ".cue",
    ".d64",
    ".dim",
    ".dsk",
    ".g64",
    ".gz",
    ".hdf",
    ".ipf",
    ".lha",
    ".lnx",
    ".m3u",
    ".mgw",
    ".mx1",
    ".mx2",
    ".prg",
    ".rom",
    ".scummvm",
    ".tap",
    ".tzx",
    ".vec",
    ".xfd",
    ".zip",
    ".z80",
}

LETTER_BUCKETS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ") | {"0", "0-9", "#"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def stable_id(*parts: str) -> str:
    data = "\0".join(parts).encode("utf-8", "surrogateescape")
    return hashlib.sha1(data).hexdigest()[:16]


def title_from_path(path: Path) -> str:
    stem = path.name
    if path.suffix:
        stem = path.stem
    stem = clean_title(stem)
    return stem or path.name


def normalize_title(title: str) -> str:
    return title_key(title)


def file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


def language_hint(text: str) -> str | None:
    hay = text.lower()
    if re.search(r"(^|[^a-z])(de|ger|german|deutsch)([^a-z]|$)", hay):
        return "German"
    if re.search(r"(^|[^a-z])(fr|fre|french|francais)([^a-z]|$)", hay):
        return "French"
    if re.search(r"(^|[^a-z])(it|ita|italian)([^a-z]|$)", hay):
        return "Italian"
    if re.search(r"(^|[^a-z])(es|spa|spanish)([^a-z]|$)", hay):
        return "Spanish"
    return None


def make_entry(
    source: str,
    title: str,
    platform: str,
    path: Path,
    root: Path,
    collection: str | None = None,
    category: str | None = None,
    source_kind: str | None = None,
) -> dict:
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    fmt = "directory" if path.is_dir() else (path.suffix.lower().lstrip(".") or "file")
    normalized = normalize_title(title)
    return {
        "id": stable_id(source, platform, rel),
        "title": title,
        "normalizedTitle": normalized,
        "source": source,
        "platform": platform,
        "collection": collection or platform,
        "category": category,
        "format": fmt,
        "language": language_hint(" ".join([title, rel, category or ""])),
        "path": rel,
        "absolutePath": str(path),
        "sizeBytes": file_size(path),
        "sourceKind": source_kind,
        "nonGame": is_non_game(title, rel),
    }


def parse_batocera_gamelist(platform_dir: Path) -> list[dict]:
    gamelist = platform_dir / "gamelist.xml"
    if not gamelist.exists():
        return []

    entries = []
    try:
        root = ET.parse(gamelist).getroot()
    except ET.ParseError:
        return entries

    seen_paths = set()
    for game in root.findall("game"):
        rel_path = (game.findtext("path") or "").strip()
        if not rel_path:
            continue
        rom_path = (platform_dir / rel_path).resolve()
        if not rom_path.exists():
            continue
        title = (game.findtext("name") or title_from_path(rom_path)).strip()
        entry = make_entry(
            "Batocera",
            title,
            platform_dir.name,
            rom_path,
            BATOCERA_ROMS,
            collection=platform_dir.name,
            source_kind="gamelist",
        )
        entry["description"] = (game.findtext("desc") or "").strip() or None
        entry["rating"] = (game.findtext("rating") or "").strip() or None
        entry["genre"] = (game.findtext("genre") or "").strip() or None
        entry["developer"] = (game.findtext("developer") or "").strip() or None
        entry["publisher"] = (game.findtext("publisher") or "").strip() or None
        entry["players"] = (game.findtext("players") or "").strip() or None
        entries.append(entry)
        seen_paths.add(str(rom_path))
    return entries


def scan_batocera_missing(platform_dir: Path, known_paths: set[str]) -> list[dict]:
    entries = []
    for root, dirs, files in os.walk(platform_dir):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        root_path = Path(root)

        if platform_dir.name == "scummvm":
            for directory in dirs:
                game_dir = root_path / directory
                if root_path == platform_dir and directory.lower() not in SKIP_DIRS:
                    real = str(game_dir.resolve())
                    if real not in known_paths:
                        entries.append(
                            make_entry("Batocera", title_from_path(game_dir), "scummvm", game_dir, BATOCERA_ROMS, source_kind="scan")
                        )
            if root_path == platform_dir:
                dirs[:] = []

        for filename in files:
            path = root_path / filename
            if path.name == "gamelist.xml" or path.suffix.lower() not in ROM_EXTENSIONS:
                continue
            real = str(path.resolve())
            if real in known_paths:
                continue
            entries.append(
                make_entry("Batocera", title_from_path(path), platform_dir.name, path, BATOCERA_ROMS, source_kind="scan")
            )
    return entries


def collect_batocera() -> list[dict]:
    if not BATOCERA_ROMS.exists():
        return []
    entries = []
    for platform_dir in sorted(p for p in BATOCERA_ROMS.iterdir() if p.is_dir()):
        platform_entries = parse_batocera_gamelist(platform_dir)
        known = {e["absolutePath"] for e in platform_entries}
        platform_entries.extend(scan_batocera_missing(platform_dir, known))
        entries.extend(platform_entries)
    return entries


def contains_launchable_files(path: Path) -> bool:
    try:
        for child in path.iterdir():
            if child.is_file() and child.suffix.lower() in {".slave", ".info", ".lha", ".adf", ".hdf", ".exe", ""}:
                return True
    except OSError:
        return False
    return False


def collect_pimiga_whdload(whdload: Path) -> list[dict]:
    entries = []
    if not whdload.exists():
        return entries

    for category_dir in sorted(p for p in whdload.iterdir() if p.is_dir()):
        category = category_dir.name
        for child in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            grandchildren = sorted(p for p in child.iterdir() if p.is_dir()) if child.exists() else []
            if child.name.upper() in LETTER_BUCKETS and grandchildren:
                for game_dir in grandchildren:
                    entries.append(
                        make_entry(
                            "PiMiga",
                            title_from_path(game_dir),
                            "Amiga",
                            game_dir,
                            PIMIGA_GAMES,
                            collection="WHDLoad",
                            category=category,
                            source_kind="whdload",
                        )
                    )
            elif contains_launchable_files(child) or grandchildren:
                entries.append(
                    make_entry(
                        "PiMiga",
                        title_from_path(child),
                        "Amiga",
                        child,
                        PIMIGA_GAMES,
                        collection="WHDLoad",
                        category=category,
                        source_kind="whdload",
                    )
                )
    return entries


def collect_pimiga_direct() -> list[dict]:
    entries = []
    if not PIMIGA_GAMES.exists():
        return entries

    for child in sorted(p for p in PIMIGA_GAMES.iterdir() if p.is_dir()):
        if child.name == "WHDLOAD":
            continue
        entries.append(
            make_entry(
                "PiMiga",
                title_from_path(child),
                "Amiga",
                child,
                PIMIGA_GAMES,
                collection="Installed",
                category="Direct",
                source_kind="installed-dir",
            )
        )
    entries.extend(collect_pimiga_whdload(PIMIGA_GAMES / "WHDLOAD"))
    return entries


def add_presence(entries: list[dict]) -> None:
    sources_by_key: dict[str, set[str]] = {}
    for entry in entries:
        if entry["normalizedTitle"]:
            sources_by_key.setdefault(entry["normalizedTitle"], set()).add(entry["source"])
    for entry in entries:
        sources = sorted(sources_by_key.get(entry["normalizedTitle"], {entry["source"]}))
        entry["sourcesForTitle"] = sources
        entry["appearsInBoth"] = len(sources) > 1


def summary(entries: list[dict]) -> dict:
    by_source: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    by_collection: dict[str, int] = {}
    both = 0
    for entry in entries:
        by_source[entry["source"]] = by_source.get(entry["source"], 0) + 1
        by_platform[entry["platform"]] = by_platform.get(entry["platform"], 0) + 1
        key = f"{entry['source']} / {entry['collection']}"
        by_collection[key] = by_collection.get(key, 0) + 1
        both += 1 if entry.get("appearsInBoth") else 0
    return {
        "total": len(entries),
        "bySource": dict(sorted(by_source.items())),
        "byPlatform": dict(sorted(by_platform.items())),
        "byCollection": dict(sorted(by_collection.items())),
        "appearsInBothCount": both,
    }


def main() -> int:
    entries = collect_batocera()
    entries.extend(collect_pimiga_direct())
    entries.sort(key=lambda e: (e["title"].lower(), e["source"], e["collection"], e["path"]))
    add_presence(entries)
    payload = {
        "generatedAt": now_iso(),
        "sourceRoots": {
            "batocera": str(BATOCERA_ROMS),
            "pimiga": str(PIMIGA_GAMES),
        },
        "summary": summary(entries),
        "games": entries,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
