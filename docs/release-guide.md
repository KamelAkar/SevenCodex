# SevenCodex Release Guide

This guide is for a lightweight public release of the static SevenCodex site.

## 1. Pre-release checks

From the repository root:

```powershell
python scripts/build_codex_data.py
python -m py_compile scripts/build_codex_data.py
node --check src/app.js
node --check src/render.js
node --check src/render-content.js
node --check src/render-kit.js
node --check src/map-links.js
node --check src/i18n.js
node --check src/seo.js
```

Then confirm the worktree only contains intentional changes:

```powershell
git status
git diff --stat
```

## 2. Local smoke test

Serve SevenCodex locally:

```powershell
python -m http.server 8003 --directory .
```

If you want to validate cross-links, serve SevenMap beside it on `http://localhost:8002/`.

Minimum pages to verify manually:

- `/?lang=fr&view=home`
- `/?lang=en&view=search&q=tiger%20moth`
- `/?lang=fr&view=entry&kind=character&slug=character-1018-guila`
- `/?lang=fr&view=entry&kind=item&slug=item-101080001-low-quality-resolution-fragment&tab=obtain`
- `/?lang=fr&view=entry&kind=boss&slug=boss-red-demon`

What to check:

- no horizontal overflow on mobile width
- logo, favicon and manifest icons are correct
- search works in EN and FR
- item pages resolve drops, obtain sources and internal links
- `Open on Map` opens SevenMap with the expected filters
- boss pages show world-level loot when available
- characters, buffs, debuffs and recipes still render icons and labels

## 3. Release hygiene

Before publishing:

- bump cache-busting query strings in [index.html](/Users/Ravnow/Documents/SevenCodex/index.html) when shipping JS or CSS changes
- make sure `robots.txt`, `site.webmanifest`, `humans.txt` and SEO meta still match the public domain
- verify canonical and `hreflang` links on at least home, one entry page and one search page
- confirm the site still mentions that it is in early access if that banner should stay live

## 4. Deploy

SevenCodex is a static site. Publish the repository contents as static files, including:

- `index.html`
- `styles.css`
- `styles/`
- `src/`
- `data/`
- `assets/`
- `robots.txt`
- `site.webmanifest`
- `humans.txt`

If the host rewrites everything to a single HTML file, keep query parameters intact because routing depends on them.

## 5. Git release flow

```powershell
git add .
git commit -m "Prepare SevenCodex early release"
git push origin main
```

If you want a visible checkpoint:

```powershell
git tag early-release-YYYYMMDD
git push origin early-release-YYYYMMDD
```

## 6. Post-release checks

After the site is live:

- open the public URL in a private window
- hard refresh once to validate the new cache key
- verify favicon, title, description and Open Graph preview
- test one Codex -> SevenMap link from the public domain
- watch for missing generated assets under `assets/generated/`

## 7. Known release-sensitive areas

These areas deserve extra attention before a wider announcement:

- effects that still fall back to generic buff/debuff icons
- entries whose loot or obtain data depends on alias matching
- cross-project deep links when SevenMap changes query handling
- large generated diffs from `scripts/build_codex_data.py`
