import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_agent import analyze_place_for_query
from database import add_place, init_db, list_places, log_search
from map_provider import lookup_place
from ranking import compute_final_score


app = FastAPI(title="AI Place Agent Map")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
SEARCH_CONCURRENCY = 3


class PlaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    user_rating: float = Field(ge=0, le=5)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/places")
def places():
    return {"places": list_places()}


@app.get("/api/places/summary")
def places_summary():
    compact_places = []
    for place in list_places():
        compact_places.append({
            "id": place["id"],
            "name": place["name"],
            "user_rating": place["user_rating"],
            "provider": place["provider"],
            "address": place["address"],
            "provider_rating": place["provider_rating"],
            "category": place["category"],
        })
    return {"count": len(compact_places), "places": compact_places}


@app.post("/api/places")
async def create_place(payload: PlaceCreate):
    place = await lookup_place(payload.name.strip())
    place["user_rating"] = payload.user_rating
    place_id = add_place(place)
    place["id"] = place_id
    return {"place": place}


@app.post("/api/search")
async def search(payload: SearchRequest):
    candidates = list_places()
    if not candidates:
        return {"query": payload.query, "results": []}

    semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)

    async def analyze_one(place: dict) -> dict:
        async with semaphore:
            ai_result = await analyze_place_for_query(payload.query, place)
        score = compute_final_score(place, ai_result)
        return {**place, **score, "ai": ai_result}

    results = await asyncio.gather(*(analyze_one(place) for place in candidates))
    for place in results:
        place.pop("photo_refs", None)

    results.sort(key=lambda item: item["final_score"], reverse=True)
    log_search(payload.query, len(results))
    return {"query": payload.query, "results": results}


@app.exception_handler(ValueError)
def value_error_handler(_, exc: ValueError):
    raise HTTPException(status_code=400, detail=str(exc))
