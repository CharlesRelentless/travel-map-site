# Project Guide

## Purpose

Single-page travel support map for the 2026-06-06 seven-day G219, Ali, Everest, and Lhasa driving itinerary. It combines route stops, AMap driving ETA, browser location, Moji weather alerts, and coordinate-based forecast fallback.

## High-Signal Files

- `index-amap.html`: canonical application source.
- `index-amap.previous.html`: the only retained rollback copy; replace it with the current working version immediately before future risky changes.
- `weather_proxy.py`: static server and server-side Moji API proxy.
- `render.yaml`: public HTTPS deployment blueprint.
- `.env.example`: non-secret environment variable template.
- `.env.local`: local secret configuration; never commit or expose it.
- `README.md`: detailed project history and operating notes.
- `docs/current-status.md`: concise current handoff status.

## Verified Commands

```powershell
conda run --no-capture-output python -m py_compile weather_proxy.py
conda run --no-capture-output python weather_proxy.py
```

Open `http://127.0.0.1:8000/index-amap.html`.

Validate embedded JavaScript syntax:

```powershell
node -e "const fs=require('fs'),vm=require('vm'); const h=fs.readFileSync('index-amap.html','utf8'); [...h.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].forEach((m,i)=>new vm.Script(m[1],{filename:'inline-'+i+'.js'}));"
```

## Durable Rules

- Keep Moji AppCode only in `.env.local` or server environment variables.
- Do not present a nearby county's current temperature as an unmanned-area stop's actual temperature.
- Distinguish Moji current conditions from forecast temperature at planned/estimated arrival time.
- Preserve fallback behavior when Moji or Open-Meteo is unavailable.
- Keep only one rollback copy: `index-amap.previous.html`.
- Do not recreate `index.html`; the supported entry is `index-amap.html`.
- Public deployment should serve the map and weather API from the same HTTPS origin.
- Use an always-on production instance for travel warning reliability; do not rely on a sleeping free instance.
- Add the public HTTPS domain to the AMap Web key allowlist after deployment.
