# backend/pexels.py
import os
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Simple in-memory TTL cache to avoid hammering Pexels during development/demo
_CACHE = {}
CACHE_TTL = 300  # seconds

def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > CACHE_TTL:
        del _CACHE[key]
        return None
    return data

def _cache_set(key, data):
    _CACHE[key] = (time.time(), data)

_VALID_ORIENTATIONS = {"landscape", "portrait", "square"}


def _matches_orientation(width: int, height: int, orientation: str) -> bool:
    if not width or not height:
        return False
    if orientation == "landscape":
        return width >= height
    if orientation == "portrait":
        return height >= width
    if orientation == "square":
        return abs(width - height) <= min(width, height) * 0.1
    return True


def search_pexels(
    keyword: str,
    orientation: str = "landscape",
    per_page: int = 3,
    page: int = 1,
) -> List[Dict]:
    """
    Query Pexels video search and return list of candidate video metadata dicts:
    { url, id, width, height, duration, thumbnail }
    """
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not set in environment")

    norm_orientation = orientation.lower() if isinstance(orientation, str) else ""
    params_orientation = norm_orientation if norm_orientation in _VALID_ORIENTATIONS else None

    key = f"pexels:{params_orientation}:{keyword}:{per_page}:{page}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": keyword,
        "per_page": per_page,
        "page": page,
    }
    if params_orientation:
        params["orientation"] = params_orientation

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = []
        for v in data.get("videos", []):
            # pick the best video file (prefer highest resolution)
            files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0) * f.get("height", 0), reverse=True)
            if params_orientation:
                filtered = [f for f in files if _matches_orientation(f.get("width"), f.get("height"), params_orientation)]
                if filtered:
                    files = filtered
            if not files:
                continue
            best = files[0]
            preview = None
            if files:
                preview = files[-1].get("link")
            user = v.get("user", {}) or {}
            videos.append({
                "url": best.get("link"),
                "id": str(v.get("id")),
                "width": best.get("width"),
                "height": best.get("height"),
                "duration": v.get("duration"),
                "thumbnail": v.get("image") or v.get("video_pictures", [{}])[0].get("picture"),
                "previewUrl": preview or best.get("link"),
                "pageUrl": v.get("url"),
                "source": "pexels",
                "attribution": {
                    "name": user.get("name"),
                    "url": user.get("url"),
                },
                "raw_files": files  # optional, for debugging or advanced UI
            })

        _cache_set(key, videos)
        return videos

    except requests.RequestException as e:
        # return empty list on error (frontend logs will show)
        print("Pexels request failed:", e)
        return []
