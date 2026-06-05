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

## What The App Searches

The deployed web app is static. Normal browsing and searching use only generated local JSON files:

- `public/game-index.json`
- `public/details/*.json`
- `public/community-ranks.json`

That means the app does not need the PiMiga SSD plugged in once the catalog has been generated.

The current generated catalog includes PiMiga entries captured when the PiMiga SSD was mounted at:

```text
/mnt/pimiga-root/home/pi/pimiga/disks/Games
```

Woodstock also has a full-disk PiMiga image backup on the WDC storage partition:

```text
/mnt/wd-WXF1A94HCEF5-storage/Retro_Games/PiMiga_Backup/PiMiga5_SAMSUNG_MZNLF128HCHP_20260601-083644_full-disk.img
```

However, `scripts/collect_catalog.sh` does not automatically mount or inspect that image. A fresh PiMiga rescan currently needs either:

- the original PiMiga SSD mounted at `/mnt/pimiga-root`, or
- the saved full-disk image mounted read-only with its root filesystem exposed at `/mnt/pimiga-root`.

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

Title matching is centralized in `scripts/title_normalization.py`. It preserves sequels and plus-editions, collapses multi-disk variants, and excludes explicit `ZZZ(notgame)` utility entries from the user-facing game counts. Known compact PiMIGA names such as `Lemmings21MB` are disambiguated as `Lemmings 2 (1 MB)` rather than being merged into the first game; genuine memory variants such as `WormsDCAGA12MB` remain attached to their base title.

Generated files:

- `public/game-index.json`
- `public/details/*.json`

To check that grouped counts, detail chunks, known tricky titles, and rank matches remain sane:

```bash
./scripts/audit_catalog_matching.py
```

## Preferred Collection Manifest

Generate the platform-aware C64 and Amiga curation manifest:

```bash
./scripts/build_preferred_manifest.py
./scripts/audit_preferred_manifest.py
```

The manifest keeps C64 and Amiga releases separate, prefers German over
English or language-neutral releases, preserves multidisk releases as one
selection, and flags ambiguous Amiga hardware editions for manual review.
For PiMIGA directories, the inventory records recursive file counts, sizes,
and whether the package contains a launchable file. Complete WHDLoad packages
therefore outrank same-title artwork/index stubs, while genuinely runnable
AGA, OCS, CD32, and CDTV alternatives remain in the review queue.

Generated file:

- `public/preferred-manifest.json`

Run the regression tests with:

```bash
python3 -m unittest discover -s tests -v
```

Profile a manual-review queue with:

```bash
./scripts/analyze_preferred_reviews.py
./scripts/analyze_preferred_reviews.py --platform c64
./scripts/analyze_amiga_hardware_reviews.py
```

The analyzer prints tied candidates and common variant markers without
modifying the manifest. The Amiga hardware analyzer separates duplicate
folder placements of one release from genuinely different AGA, OCS, CD32, and
CDTV editions.

Reviewed choices belong in `config/preferred-overrides.json`. Each override
selects a candidate by stable fields such as `releaseIdentity` and `category`,
records its rationale and evidence, and lists the review reasons it resolves.
The manifest build fails when a selector no longer matches exactly one
candidate, preventing stale decisions from silently selecting another release.

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
