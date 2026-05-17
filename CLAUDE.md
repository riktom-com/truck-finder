# truck-finder — South Georgia Truck Finder

**Subdomain:** https://trucks.riktom.com
**Stack:** FastAPI + static HTML frontend
**VPS path:** `/opt/truck-finder/`
**Port:** 8005
**Systemd unit:** `truck-finder-api.service`
**nginx config:** `/etc/nginx/sites-available/trucks.riktom.com`
**GitHub:** https://github.com/riktom-com/truck-finder

## What It Does
Helps South Georgia outdoorspeople locate nearby service trucks, towing, and roadside assistance relevant to rural areas.

## Stack
- `main.py` — FastAPI backend on port 8005
- `index.html` — Static HTML frontend served by nginx
- `requirements.txt` — Python dependencies (fastapi, uvicorn)

## Deploy
Files live at `/opt/truck-finder/` on VPS (72.62.83.12).
Service managed by systemd as `truck-finder-api.service`.

Secrets stored as systemd `Environment=` directives — never in source.

## Standardized Nav (rk-nav)

This app uses the shared riktom.com nav block (scoped `.rk-*` classes, self-contained CSS) that is identical across all 11 riktom.com properties. The block is enclosed by marker comments:

```
<!-- rk-nav:start -->
... nav HTML + scoped style ...
<!-- rk-nav:end -->
```

**To update the nav site-wide** (add a new app, change a link, restyle):
1. Edit `/tmp/patch_navs.py` on the VPS (or `/tmp/sync/patch_local.py` for local repos) with the new HTML.
2. Re-run the patcher — it finds the markers and replaces the block in place. The replace is idempotent.
3. For repos with React/Vite builds (e.g. fire-watcher), re-patch after rebuild since `dist/index.html` is regenerated.

Nav contents: Logo · About · Blog · Apps ▾ (11 apps) · 💡 Suggest · 🏠 Home (top-right white pill).
