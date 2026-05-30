from typing import Optional


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def rating_to_unit(rating: Optional[float]) -> float:
    if rating is None:
        return 0.5
    return clamp(float(rating) / 5.0)


def compute_final_score(place: dict, ai_result: dict) -> dict:
    user_score = rating_to_unit(place.get("user_rating"))
    provider_score = rating_to_unit(place.get("provider_rating"))
    intent_score = clamp(float(ai_result.get("intent_match", 0.5)))
    environment_score = clamp(float(ai_result.get("environment_score", 0.5)))
    evidence_score = clamp(float(ai_result.get("evidence_confidence", 0.4)))

    final_unit = (
        user_score * 0.35
        + provider_score * 0.15
        + intent_score * 0.25
        + environment_score * 0.15
        + evidence_score * 0.10
    )
    return {
        "final_score": round(final_unit * 100, 1),
        "score_parts": {
            "user_rating": round(user_score * 100, 1),
            "map_rating": round(provider_score * 100, 1),
            "intent_match": round(intent_score * 100, 1),
            "environment": round(environment_score * 100, 1),
            "evidence": round(evidence_score * 100, 1),
        },
    }
