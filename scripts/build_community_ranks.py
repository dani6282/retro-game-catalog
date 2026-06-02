#!/usr/bin/env python3
"""Build community ranking data from public top-list pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "community-rank-sources.json"
OUT_PATH = ROOT / "public" / "community-ranks.json"


def clean_title(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[_]+", " ", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return re.sub(r"\s+", " ", value).strip()


def title_for_key(title: str) -> str:
    value = clean_title(title)
    article_match = re.match(r"^(.+),\s+(The|A|An)$", value, flags=re.I)
    if article_match:
        value = f"{article_match.group(2)} {article_match.group(1)}"
    value = re.sub(
        r"\s+(De|Ger|German|Deutsch|Fr|Fre|French|Francais|It|Ita|Italian|Es|Spa|Spanish)$",
        "",
        value,
        flags=re.I,
    ).strip()
    return value


def title_key(title: str) -> str:
    value = title_for_key(title).lower()
    value = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", value)
    value = re.sub(r"\b(disk|disc|side|part|cd|v|version)\s*\d+(\.\d+)?\b", " ", value)
    value = re.sub(r"\b(ntsc|pal|aga|ocs|ecs|cd32|whdload)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "retro-game-catalog/1.0 (+https://github.com/dani6282/retro-game-catalog)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception as error:
        print(f"urllib fetch failed for {url}: {error}; trying curl", file=sys.stderr)
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "30", "-A", "retro-game-catalog/1.0", url],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout


def absolute_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(href))


def parse_c64_wiki(source: dict, markup: str) -> list[dict]:
    items = []
    pattern = re.compile(
        r'<a href="(?P<href>[^"]+)">\s*<img src="[^"]*/(?P<rank>\d{5})_(?P<score>\d+\.\d+)_'
        r'[^"]+\.png" alt="(?P<title>[^"]+)"',
        re.I,
    )
    for match in pattern.finditer(markup):
        title = clean_title(match.group("title"))
        items.append(
            {
                "key": title_key(title),
                "title": title_for_key(title),
                "sourceId": source["id"],
                "sourceName": source["name"],
                "platform": source["platform"],
                "rank": int(match.group("rank")),
                "score": float(match.group("score")),
                "votes": None,
                "url": absolute_url(source["url"], match.group("href")),
            }
        )
    return items


def parse_lemon_amiga(source: dict, markup: str) -> list[dict]:
    items = []
    containers = re.split(r'<div class="votes-list-game-container clearfix">', markup, flags=re.I)[1:]
    for position, container in enumerate(containers, start=1):
        title_match = re.search(
            r'<h3 class="text-truncate">\s*<a href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            container,
            flags=re.I | re.S,
        )
        score_match = re.search(r'<span class="votes-list-score">(?P<score>\d+(?:\.\d+)?)</span>', container, flags=re.I)
        votes_match = re.search(r'>(?P<votes>\d+)&nbsp;votes</a>', container, flags=re.I)
        if not title_match or not score_match:
            continue
        title = clean_title(title_match.group("title"))
        items.append(
            {
                "key": title_key(title),
                "title": title_for_key(title),
                "sourceId": source["id"],
                "sourceName": source["name"],
                "platform": source["platform"],
                "rank": position,
                "score": float(score_match.group("score")),
                "votes": int(votes_match.group("votes")) if votes_match else None,
                "url": absolute_url(source["url"], title_match.group("href")),
            }
        )
    return items


PARSERS = {
    "c64-wiki-top100": parse_c64_wiki,
    "lemon-amiga-top100": parse_lemon_amiga,
}


def build_payload(markups: dict[str, str]) -> dict:
    config = json.loads(SOURCES_PATH.read_text())
    rankings = []
    for source in config["sources"]:
        parser = PARSERS[source["id"]]
        entries = parser(source, markups[source["id"]])
        rankings.extend(entries)
        print(f"{source['name']}: {len(entries)} entries", file=sys.stderr)

    by_key: dict[str, list[dict]] = {}
    for entry in rankings:
        by_key.setdefault(entry["key"], []).append(entry)

    return {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sources": config["sources"],
        "rankings": sorted(rankings, key=lambda item: (item["sourceId"], item["rank"], item["title"].casefold())),
        "byKey": {key: sorted(values, key=lambda item: (item["rank"], item["sourceName"])) for key, values in sorted(by_key.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures-dir", type=Path, help="Read source HTML fixtures from this directory instead of fetching.")
    parser.add_argument("--write-fixtures-dir", type=Path, help="Also write fetched source HTML to this directory.")
    args = parser.parse_args()

    config = json.loads(SOURCES_PATH.read_text())
    markups = {}
    for source in config["sources"]:
        if args.fixtures_dir:
            markups[source["id"]] = (args.fixtures_dir / f"{source['id']}.html").read_text()
        else:
            markups[source["id"]] = fetch(source["url"])
        if args.write_fixtures_dir:
            args.write_fixtures_dir.mkdir(parents=True, exist_ok=True)
            (args.write_fixtures_dir / f"{source['id']}.html").write_text(markups[source["id"]])

    payload = build_payload(markups)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    print(f"Ranked titles: {len(payload['rankings'])}")
    print(f"Unique keys: {len(payload['byKey'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
