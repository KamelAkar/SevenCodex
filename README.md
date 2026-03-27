# SevenCodex

SevenCodex is the standalone static site for the SevenCodex companion product.
It lives in its own workspace beside SevenMap as a bilingual codex/wiki for Seven Deadly Sins: Origin.

## What is here

- `index.html`: static app shell and entry point
- `src/`: native ES modules for routing, data loading, rendering, search, and i18n
- `styles/`: shared design system and page-specific styling
- `data/`: generated codex payloads
- `assets/`: static assets plus generated copied icons/images
- `docs/`: local architecture and pipeline notes
- `scripts/`: codex build scripts, including the data generator and resolver helpers

## Current scope

- bilingual EN/FR UI and generated content
- data-driven home, hub, list, region, entry, search, and guide pages
- generated search index and category navigation
- real extracted resources, creatures, systems, recipes, regions, and unlock data
- SevenMap deep links from codex entries and reverse codex links from the map

## Current data

The codex generator produces normalized JSON under `data/` and copied assets under `assets/generated/`.

See [docs/codex-pipeline.md](/C:/Users/Ravnow/Documents/SevenCodex/docs/codex-pipeline.md) for the current pipeline, source tables, output contract, and map integration model.

## Run locally

Serve this folder with any static server and open it in a browser.

PowerShell:

```powershell
python -m http.server 8081 --directory .
```

When SevenMap is served separately on `http://127.0.0.1:8080/`, the codex detects that localhost root-mode setup and points cross-links to the sibling map port automatically.

The generator expects the sibling SevenMap workspace at:

- `C:\Users\Ravnow\Documents\SevenMap`

## Rebuild data

From the SevenCodex root:

```powershell
python scripts/build_codex_data.py
```
