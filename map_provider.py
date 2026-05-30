import hashlib
import json
import os
from typing import Optional, Tuple
from urllib.parse import quote

import httpx
from dotenv import load_dotenv


load_dotenv()

GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PHOTO_URL = "https://places.googleapis.com/v1/{photo_name}/media"


def _mock_coordinates(name: str) -> tuple[float, float]:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    lat_offset = (int(digest[:6], 16) % 9000) / 100000
    lng_offset = (int(digest[6:12], 16) % 9000) / 100000
    return 37.55 + lat_offset, 126.92 + lng_offset


def fallback_place_lookup(name: str) -> dict:
    lat, lng = _mock_coordinates(name)
    is_cafe = any(word in name.lower() for word in ["cafe", "카페", "커피", "coffee", "스타벅스"])
    category = "cafe" if is_cafe else "restaurant"
    return {
        "name": name,
        "provider": "mock",
        "provider_place_id": f"mock:{quote(name)}",
        "address": "지도 API 키가 없어 임시 좌표로 표시됩니다.",
        "latitude": lat,
        "longitude": lng,
        "provider_rating": None,
        "category": category,
        "photo_refs": "[]",
        "lookup_status": "fallback_no_google_key",
    }


async def lookup_place(name: str) -> dict:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return fallback_place_lookup(name)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.primaryType,places.photos.name"
        ),
    }
    payload = {
        "textQuery": name,
        "languageCode": "ko",
        "regionCode": "KR",
        "maxResultCount": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(GOOGLE_TEXT_SEARCH_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return fallback_place_lookup(name)

    places = data.get("places") or []
    if not places:
        return fallback_place_lookup(name)

    place = places[0]
    location = place.get("location") or {}
    display = place.get("displayName") or {}
    photos = [p.get("name") for p in place.get("photos", []) if p.get("name")]
    return {
        "name": display.get("text") or name,
        "provider": "google",
        "provider_place_id": place.get("id"),
        "address": place.get("formattedAddress"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "provider_rating": place.get("rating"),
        "category": place.get("primaryType") or "restaurant",
        "photo_refs": json.dumps(photos[:3], ensure_ascii=False),
        "lookup_status": "google_ok",
    }


async def fetch_google_photo_bytes(photo_name: str) -> Optional[Tuple[bytes, str]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key or not photo_name:
        return None
    url = GOOGLE_PHOTO_URL.format(photo_name=photo_name)
    params = {"key": api_key, "maxWidthPx": 640}
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            return response.content, content_type
    except Exception:
        return None
