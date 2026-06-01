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

The repository is ready for GitHub Pages. Push it to a GitHub repo named `retro-game-catalog`; the workflow in `.github/workflows/pages.yml` publishes the static site from the repository root.

It is also deployable on Woodstock using the files in `deploy/woodstock`.

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
