# Current Status

## Project Goal

Provide a mobile-friendly seven-day self-driving route map with location-aware ETA and actionable severe-weather warnings.

## Current Objective

Deploy the map and Moji weather proxy to one public HTTPS origin so phones can use weather warnings outside the local network.

## Completed

- Added 20-minute frontend weather expiry and refresh.
- Added cross-Day forward-stop scanning and deduplicated severe-weather popup.
- Added detailed fallback reasons instead of the generic “weather API unavailable” message.
- Added Moji `condition` current-temperature parsing and separate current/arrival labels.
- Added an old-cache upgrade check so pre-change browser weather cache triggers a new Moji condition request.
- Removed legacy HTML backups, the old OSM page, and `index.html`.
- Retained only `index-amap.previous.html` as the rollback copy.
- Added a Render HTTPS deployment blueprint and non-secret environment template.
- Hardened the public proxy with a health endpoint, file allowlist, route CityID allowlist, rate limiting, configurable CORS, and stale-cache fallback.
- Added `docs/public-deployment.md` with deployment and cellular-network field-test steps.

## Next Actions

- Verify the current/arrival labels visually on a phone after a hard refresh.
- Consider adding a manual “refresh weather now” button for field use.
- Push the project to a private Git repository and create the Render service from `render.yaml`.
- Set `MOJI_APPCODE` in Render and add the deployed HTTPS domain to the AMap Web key allowlist.
- Test location permission, map loading, and severe-weather popup from a phone using cellular data.

## Blockers

- Open-Meteo was unreachable from the current network during the latest check.
- In-app browser visual automation was unavailable in the current Windows sandbox.
- Public deployment cannot be completed without the user's Git hosting and Render account access.

## Key Decisions

- `index-amap.html` is the only supported runtime entry.
- Keep only one rollback copy, `index-amap.previous.html`, and refresh it before risky changes.
- Moji city/current weather is not used as the actual temperature for unmanned-area stops.
- Current conditions and arrival-time forecast are displayed separately.
- Public production serves `index-amap.html` and `/api/moji` from the same HTTPS origin.
- Use an always-on instance because free-instance cold starts are unsuitable for urgent travel warnings.

## Verification

- Moji proxy returned `condition`, 25 hourly forecast rows, and active official alerts for city ID 2566.
- Latest Moji check returned current temperature `18°C`, condition `多云`, updated `2026-06-06 21:35:08`.
- Embedded JavaScript syntax validation passed for `index-amap.html`.
- `index-amap.previous.html` matched the current working version when created before cleanup.
- Local proxy returned HTTP 200 for `index-amap.html`; removed `index.html` returned not found.
- Cleanup verification found only `index-amap.html` and `index-amap.previous.html` among application HTML variants/backups.
- `weather_proxy.py` Python compile validation passed.
- Hardened proxy validation on port 8010: `/healthz` returned healthy, root redirected to `index-amap.html`, map returned HTTP 200, and `.env.local` plus `AGENTS.md` returned 404.
- Hardened proxy validation: route CityID 2566 returned Moji data, unrelated CityID 1 returned HTTP 400, and current response was not stale.
