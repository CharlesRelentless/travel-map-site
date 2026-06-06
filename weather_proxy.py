import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".weather-cache"
CACHE_TTL_SECONDS = 20 * 60
STALE_CACHE_MAX_AGE_SECONDS = 6 * 60 * 60
MOJI_BASE_URL = "https://aliv18.data.moji.com/whapi/json/alicityweather"
PUBLIC_FILES = {"/index-amap.html", "/sw.js"}
DEFAULT_ALLOWED_CITY_IDS = {
    285325, 2566, 3158, 3154, 3157, 3156, 3133,
    3137, 3127, 3124, 3132, 3121, 3117, 3084,
}
RATE_LIMIT_WINDOW_SECONDS = 5 * 60
RATE_LIMIT_REQUESTS = 90
rate_limit_lock = threading.Lock()
rate_limit_buckets = {}
MOJI_TOKENS = {
    "condition": "50b53ff8dd7d9fa320d3d3ca32cf8ed1",
    "forecast15days": "f9f212e1996e79e0e602b08ea297ffb0",
    "forecast24hours": "008d2ad9197090c5dddc76f583616606",
    "alert": "7ebe966ee2e04bbd8cdbc0b84f7f3bc7",
}


def load_local_env():
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_local_env()
MOJI_APPCODE = os.environ.get("MOJI_APPCODE", "")
ALLOW_INSECURE_SSL = os.environ.get("MOJI_ALLOW_INSECURE_SSL") == "1"
ALLOWED_ORIGIN = os.environ.get("TRAVEL_MAP_ALLOWED_ORIGIN", "").rstrip("/")
ALLOWED_CITY_IDS = {
    int(item)
    for item in os.environ.get(
        "TRAVEL_MAP_ALLOWED_CITY_IDS",
        ",".join(str(item) for item in sorted(DEFAULT_ALLOWED_CITY_IDS)),
    ).split(",")
    if item.strip().isdigit()
}


def json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def cache_path(city_id, api_type):
    return CACHE_DIR / f"{city_id}-{api_type}.json"


def read_cache(city_id, api_type, max_age=CACHE_TTL_SECONDS):
    path = cache_path(city_id, api_type)
    if not path.exists() or time.time() - path.stat().st_mtime > max_age:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(city_id, api_type, payload):
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path(city_id, api_type).write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def call_moji(city_id, api_type):
    cached = read_cache(city_id, api_type)
    if cached is not None:
        return cached, True, False
    if not MOJI_APPCODE:
        raise RuntimeError("MOJI_APPCODE is missing from .env.local")
    token = MOJI_TOKENS.get(api_type)
    if not token:
        raise ValueError(f"Unsupported Moji API type: {api_type}")
    body = urllib.parse.urlencode({"cityId": city_id, "token": token}).encode("utf-8")
    request = urllib.request.Request(
        f"{MOJI_BASE_URL}/{api_type}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"APPCODE {MOJI_APPCODE}",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "travel-map-site/1.0",
        },
    )
    context = ssl._create_unverified_context() if ALLOW_INSECURE_SSL else None
    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("msg") or f"Moji API error: {payload.get('code')}")
        write_cache(city_id, api_type, payload)
        return payload, False, False
    except (RuntimeError, urllib.error.URLError, TimeoutError):
        stale = read_cache(city_id, api_type, STALE_CACHE_MAX_AGE_SECONDS)
        if stale is not None:
            return stale, True, True
        raise


def client_is_rate_limited(address):
    now = time.time()
    with rate_limit_lock:
        bucket = [stamp for stamp in rate_limit_buckets.get(address, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            rate_limit_buckets[address] = bucket
            return True
        bucket.append(now)
        rate_limit_buckets[address] = bucket
        return False


class TravelMapHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        origin = self.headers.get("Origin", "").rstrip("/")
        if ALLOWED_ORIGIN and origin == ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def send_json(self, status, payload):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            return self.send_json(200, {"ok": True, "service": "travel-map-weather"})
        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/index-amap.html")
            self.end_headers()
            return
        if parsed.path != "/api/moji":
            if parsed.path not in PUBLIC_FILES:
                return self.send_json(404, {"ok": False, "error": "Not found"})
            return super().do_GET()
        forwarded = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        client_address = forwarded or self.client_address[0]
        if client_is_rate_limited(client_address):
            return self.send_json(429, {"ok": False, "error": "Too many requests"})
        origin = self.headers.get("Origin", "").rstrip("/")
        if ALLOWED_ORIGIN and origin and origin != ALLOWED_ORIGIN:
            return self.send_json(403, {"ok": False, "error": "Origin not allowed"})
        if parsed.path == "/.env.local" or parsed.path.startswith("/.weather-cache/"):
            return self.send_json(404, {"ok": False, "error": "Not found"})
        query = urllib.parse.parse_qs(parsed.query)
        city_id = query.get("cityId", [""])[0].strip()
        requested = query.get("types", ["forecast24hours,alert"])[0].split(",")
        api_types = list(dict.fromkeys(item.strip() for item in requested if item.strip()))[:3]
        if not city_id.isdigit() or int(city_id) not in ALLOWED_CITY_IDS:
            return self.send_json(400, {"ok": False, "error": "cityId is not allowed"})
        result = {}
        cache_hits = {}
        stale_hits = {}
        try:
            for api_type in api_types:
                if api_type not in MOJI_TOKENS:
                    continue
                result[api_type], cache_hits[api_type], stale_hits[api_type] = call_moji(city_id, api_type)
            self.send_json(200, {
                "ok": True, "cityId": int(city_id), "cache": cache_hits,
                "stale": stale_hits, "result": result,
            })
        except (RuntimeError, ValueError, urllib.error.URLError, TimeoutError) as error:
            self.send_json(502, {"ok": False, "error": str(error)})


if __name__ == "__main__":
    os.chdir(ROOT)
    host = os.environ.get("TRAVEL_MAP_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("TRAVEL_MAP_PORT", "8000")))
    print(f"Travel map: http://127.0.0.1:{port}/index-amap.html")
    print(f"LAN access: http://<computer-ip>:{port}/index-amap.html")
    try:
        ThreadingHTTPServer((host, port), TravelMapHandler).serve_forever()
    except Exception as error:
        (ROOT / "weather_proxy.error.log").write_text(repr(error), encoding="utf-8")
        raise
