import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from map_provider import fetch_google_photo_bytes


load_dotenv()

DEFAULT_ANALYSIS = {
    "intent_match": 0.55,
    "environment_score": 0.50,
    "evidence_confidence": 0.35,
    "tags": [],
    "reason": "API 키가 없거나 분석에 실패해 기본 점수로 계산했습니다.",
}


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _heuristic_analysis(query: str, place: dict) -> dict:
    q = query.lower()
    name = (place.get("name") or "").lower()
    category = (place.get("category") or "").lower()
    tags = []
    intent = 0.55
    env = 0.50

    if any(word in q for word in ["카페", "까페", "공부", "조용", "책상"]):
        if any(word in name or word in category for word in ["카페", "cafe", "coffee", "커피"]):
            intent += 0.25
            tags.append("카페 후보")
        if any(word in q for word in ["공부", "책상", "조용"]):
            env += 0.15
            tags.append("공부/조용함 조건")

    if any(word in q for word in ["맛집", "식사", "저녁", "점심"]):
        if "restaurant" in category or any(word in name for word in ["식당", "밥", "라멘", "고기"]):
            intent += 0.20
            tags.append("식사 후보")

    return {
        "intent_match": min(intent, 0.95),
        "environment_score": min(env, 0.85),
        "evidence_confidence": 0.40,
        "tags": tags,
        "reason": "Gemini 분석을 사용할 수 없어 이름과 카테고리 기반으로 임시 판단했습니다.",
    }


async def analyze_place_for_query(query: str, place: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _heuristic_analysis(query, place)

    prompt = f"""
너는 지도 기반 맛집/장소 추천 서비스의 장소 분석 에이전트다.
사용자 검색 의도와 장소 정보를 비교해 JSON만 출력하라.

사용자 검색어: {query}

장소 정보:
- 이름: {place.get("name")}
- 주소: {place.get("address")}
- 카테고리: {place.get("category")}
- 사용자 평점: {place.get("user_rating")}
- 지도 평점: {place.get("provider_rating")}

판단 기준:
- intent_match: 검색 의도와 장소가 얼마나 맞는지 0.0~1.0
- environment_score: 사진/정보상 분위기, 좌석, 책상, 공부 가능성, 조용함 등 환경 적합도 0.0~1.0
- evidence_confidence: 실제 정보에 근거해 판단했다고 볼 수 있는 신뢰도 0.0~1.0
- tags: 짧은 한국어 태그 배열
- reason: 추천 또는 제외 이유를 한국어 한 문장으로

특히 검색어가 '조용한 공부 카페'라면 카페 여부, 좌석/책상 가능성, 혼잡도, 오래 머무를 수 있는 분위기를 중점 판단하라.
확실하지 않으면 점수를 과하게 주지 마라.

반드시 아래 형식 JSON만 출력:
{{
  "intent_match": 0.0,
  "environment_score": 0.0,
  "evidence_confidence": 0.0,
  "tags": [],
  "reason": "..."
}}
"""
    parts = [prompt]
    photo_refs = []
    try:
        photo_refs = json.loads(place.get("photo_refs") or "[]")
    except json.JSONDecodeError:
        photo_refs = []

    if photo_refs:
        photo = await fetch_google_photo_bytes(photo_refs[0])
        if photo:
            data, mime = photo
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=parts,
        )
        parsed = json.loads(_strip_json_fence(response.text or ""))
        return {
            "intent_match": float(parsed.get("intent_match", DEFAULT_ANALYSIS["intent_match"])),
            "environment_score": float(parsed.get("environment_score", DEFAULT_ANALYSIS["environment_score"])),
            "evidence_confidence": float(parsed.get("evidence_confidence", DEFAULT_ANALYSIS["evidence_confidence"])),
            "tags": parsed.get("tags") if isinstance(parsed.get("tags"), list) else [],
            "reason": str(parsed.get("reason") or DEFAULT_ANALYSIS["reason"]),
        }
    except Exception:
        return _heuristic_analysis(query, place)
