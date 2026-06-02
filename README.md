# Retro Game Catalog

A static mini-app for browsing the current Woodstock retro game inventory across:

- Batocera on the WDC drive
- PiMiga on the mounted SSD or restored image

The app is intentionally static: the generated `public/catalog.json` file is the data source, and `index.html` can be served by GitHub Pages, Netlify, Caddy, nginx, or any plain web server.

## Regenerate The Catalog

On the Mac, from this repo:

```bash
./scripts/collect_catalog.sh woodstock
```

The wrapper sends `scripts/woodstock_inventory.py` to Woodstock over SSH and writes a fresh `public/catalog.json`.

Expected Woodstock mounts:

- `/mnt/wd-WXF1A94HCEF5-share/roms`
- `/mnt/pimiga-root/home/pi/pimiga/disks/Games`

The script only reads from those paths.

## Wikipedia Links

Some grouped games have curated Wikipedia links. Edit `data/wikipedia-title-map.json`, then rebuild the static browser data:

```bash
./scripts/build_wikipedia_links.py
```

This does not query Wikipedia; it only turns known article titles into links.

## Community Ranks

Community ranking data is generated from reproducible source definitions in `data/community-rank-sources.json`.

```bash
./scripts/build_community_ranks.py
```

The scraper currently imports:

- C64-Wiki TOP100
- C64-Wiki TOP1000 page, using however many rows the live page currently exposes
- Lemon Amiga Top 100 with at least 50 votes
- Lemon Amiga Top 100 with at least 25 votes, as a broader lower-priority source

The script uses only Python standard-library modules. It falls back to `curl` if the local Python install cannot validate HTTPS certificates.

Generated file:

- `public/community-ranks.json`

## Browser Data

The app loads a pre-grouped index for speed, then lazy-loads detail chunks only when a game is expanded:

```bash
./scripts/build_grouped_catalog.py
```

Run this after changing `public/catalog.json`, `public/wiki-links.json`, or `public/community-ranks.json`.

Title matching is centralized in `scripts/title_normalization.py`. It preserves sequels and plus-editions, collapses multi-disk variants, and excludes explicit `ZZZ(notgame)` utility entries from the user-facing game counts.

Generated files:

- `public/game-index.json`
- `public/details/*.json`

To check that grouped counts, detail chunks, known tricky titles, and rank matches remain sane:

```bash
./scripts/audit_catalog_matching.py
```

## Run Locally

Use any static server:

```bash
python3 -m http.server 4173
```

Then open:

```text
http://localhost:4173
```

## Deploy

The primary deployment is Woodstock using the files in `deploy/woodstock`.

The repository also includes a manual GitHub Pages workflow in `.github/workflows/pages.yml`. GitHub Pages must be enabled for the repository before that workflow can succeed.

Current Woodstock deployment:

- Static files: `/srv/data/retro-game-catalog`
- Compose file: `/srv/docker/woodstock/compose/retro-game-catalog.yml`
- URL: `http://192.168.87.41:8783`
- Homepage tile: `Retro-Spielkatalog`

To refresh the Woodstock deployment after regenerating `public/catalog.json`, copy this repo to `/srv/data/retro-game-catalog` and run:

```bash
cd /srv/docker/woodstock/compose
docker compose -f retro-game-catalog.yml up -d
```
