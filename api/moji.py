import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

MOJI_BASE_URL = "https://aliv18.data.moji.com/whapi/json/alicityweather"
MOJI_TOKENS = {
    "condition": "50b53ff8dd7d9fa320d3d3ca32cf8ed1",
    "forecast15days": "f9f212e1996e79e0e602b08ea297ffb0",
    "forecast24hours": "008d2ad9197090c5dddc76f583616606",
    "alert": "7ebe966ee2e04bbd8cdbc0b84f7f3bc7",
}
ALLOWED_CITY_IDS = {
    285325, 2566, 3158, 3154, 3157, 3156, 3133,
    3137, 3127, 3124, 3132, 3121, 3117, 3084,
}

CACHE_TTL = 20 * 60
CACHE = {}
CACHE_LOCK = None
try:
    import threading
    CACHE_LOCK = threading.Lock()
except Exception:
    pass

MOJI_APPCODE = os.environ.get("MOJI_APPCODE", "")


def mc_get(key):
    entry = CACHE.get(key)
    if not entry:
        return None
    if time.time() - entry["t"] > CACHE_TTL:
        return None
    return entry["v"]


def mc_set(key, value):
    if CACHE_LOCK:
        with CACHE_LOCK:
            CACHE[key] = {"v": value, "t": time.time()}
    else:
        CACHE[key] = {"v": value, "t": time.time()}


def call_moji(city_id, api_type):
    cached = mc_get(f"{city_id}-{api_type}")
    if cached is not None:
        return cached, True

    if not MOJI_APPCODE:
        cached = mc_get(f"{city_id}-{api_type}")
        if cached:
            return cached, True
        raise RuntimeError("MOJI_APPCODE not set")

    token = MOJI_TOKENS.get(api_type)
    if not token:
        raise ValueError(f"Unsupported type: {api_type}")

    body = urllib.parse.urlencode({"cityId": city_id, "token": token}).encode("utf-8")
    req = urllib.request.Request(
        f"{MOJI_BASE_URL}/{api_type}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"APPCODE {MOJI_APPCODE}",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "travel-map-site/2.0",
        },
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        cached = mc_get(f"{city_id}-{api_type}")
        if cached:
            return cached, True
        raise

    if payload.get("code") != 0:
        raise RuntimeError(payload.get("msg") or f"Moji error: {payload.get('code')}")

    mc_set(f"{city_id}-{api_type}", payload)
    return payload, False


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status, payload):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self.send_json(200, {"ok": True, "service": "travel-map-moji"})

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/moji":
            return self.send_json(404, {"ok": False, "error": "Not found"})

        query = urllib.parse.parse_qs(parsed.query)
        city_id = query.get("cityId", [""])[0].strip()
        requested = query.get("types", ["forecast24hours,alert"])[0].split(",")
        api_types = list(dict.fromkeys(t.strip() for t in requested if t.strip()))[:3]

        if not city_id.isdigit() or int(city_id) not in ALLOWED_CITY_IDS:
            return self.send_json(400, {"ok": False, "error": "cityId not allowed"})

        result = {}
        cache_hits = {}
        try:
            for api_type in api_types:
                if api_type not in MOJI_TOKENS:
                    continue
                result[api_type], cache_hits[api_type] = call_moji(city_id, api_type)
            self.send_json(200, {
                "ok": True,
                "cityId": int(city_id),
                "cache": cache_hits,
                "result": result,
            })
        except Exception as e:
            self.send_json(502, {"ok": False, "error": str(e)})
