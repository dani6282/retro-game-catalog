#!/usr/bin/env python3
"""Build static Wikipedia links from the curated title map."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "wikipedia-title-map.json"
OUT_PATH = ROOT / "public" / "wiki-links.json"


def main() -> int:
    title_map = json.loads(MAP_PATH.read_text())
    links = {}
    for game_title, article in sorted(title_map.items()):
        encoded = urllib.parse.quote(article.replace(" ", "_"), safe="")
        key = "".join(ch for ch in game_title.lower() if ch.isalnum())
        links[key] = {
            "title": game_title,
            "article": article,
            "url": f"https://en.wikipedia.org/wiki/{encoded}",
        }
    OUT_PATH.write_text(
        json.dumps(
            {
                "source": "Curated Wikipedia article map",
                "sourceProject": "en.wikipedia.org",
                "links": links,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote {OUT_PATH}")
    print(f"Links: {len(links)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
