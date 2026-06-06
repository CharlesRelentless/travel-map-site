# Public HTTPS Deployment

## Recommended Topology

Deploy one Render Web Service that serves both:

- `https://<service>.onrender.com/index-amap.html`
- `https://<service>.onrender.com/api/moji`

Keeping the map and API on the same HTTPS origin avoids mixed-content and CORS failures on phones.

## Deployment Steps

1. Push this project to a private GitHub, GitLab, or Bitbucket repository.
2. In Render, create a Blueprint from the repository's root `render.yaml`.
3. Set the secret environment variable `MOJI_APPCODE`.
4. Leave `TRAVEL_MAP_ALLOWED_ORIGIN` empty when using the same service for the map and API.
5. Wait for `/healthz` to report `{"ok":true,...}`.
6. Add the Render HTTPS hostname to the AMap Web key's allowed-domain list.
7. Open the map from a phone using cellular data:

   ```text
   https://<service>.onrender.com/index-amap.html
   ```

## Required Field Test

- Confirm the map loads and location permission works over HTTPS.
- Confirm a city stop shows `墨迹当前` and an arrival-time forecast.
- Confirm `/api/moji?cityId=2566&types=condition,forecast24hours,alert` returns `ok: true`.
- Confirm a route CityID works and an unrelated CityID is rejected.
- Confirm severe-weather alerts appear when the API returns an official alert.

## Operational Notes

- Use an always-on instance. A sleeping instance can delay urgent warnings.
- The local file cache is ephemeral on Render but still reduces calls while the instance is running.
- Monitor Render logs and `/healthz` before each driving day.
- Never commit `.env.local` or the real Moji AppCode.
