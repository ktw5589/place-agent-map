import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import database
from ranking import compute_final_score


class PlaceHarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.old_db = database.DB_PATH
        self.old_use_postgres = database.USE_POSTGRES
        database.DB_PATH = self.tmp.name
        database.USE_POSTGRES = False
        database.init_db()

        import main
        main.init_db()
        self.client = TestClient(main.app)

    def tearDown(self):
        database.DB_PATH = self.old_db
        database.USE_POSTGRES = self.old_use_postgres
        os.unlink(self.tmp.name)

    def test_add_place_saves_only_user_rating_and_provider_metadata(self):
        fake_place = {
            "name": "조용한카페",
            "provider": "google",
            "provider_place_id": "places/quiet-cafe",
            "address": "서울 어딘가",
            "latitude": 37.56,
            "longitude": 126.97,
            "provider_rating": 4.3,
            "category": "cafe",
            "photo_refs": "[]",
            "lookup_status": "google_ok",
        }
        with patch("main.lookup_place", new=AsyncMock(return_value=fake_place)):
            res = self.client.post("/api/places", json={"name": "조용한카페", "user_rating": 4.8})

        self.assertEqual(res.status_code, 200)
        body = res.json()["place"]
        self.assertEqual(body["user_rating"], 4.8)
        self.assertEqual(body["provider_place_id"], "places/quiet-cafe")

        with sqlite3.connect(self.tmp.name) as conn:
            row = conn.execute("SELECT name, user_rating, provider_place_id FROM places").fetchone()
        self.assertEqual(row[0], "조용한카페")
        self.assertEqual(row[1], 4.8)
        self.assertEqual(row[2], "places/quiet-cafe")

    def test_search_uses_ai_analysis_and_weighted_ranking(self):
        database.add_place({
            "name": "스터디카페형 카페",
            "user_rating": 4.7,
            "provider": "google",
            "provider_place_id": "places/study-cafe",
            "address": "서울",
            "latitude": 37.56,
            "longitude": 126.97,
            "provider_rating": 4.2,
            "category": "cafe",
            "photo_refs": "[]",
        })
        fake_ai = {
            "intent_match": 0.95,
            "environment_score": 0.9,
            "evidence_confidence": 0.8,
            "tags": ["조용함", "공부"],
            "reason": "좌석과 책상이 있어 공부 목적에 적합합니다.",
        }
        with patch("main.analyze_place_for_query", new=AsyncMock(return_value=fake_ai)):
            res = self.client.post("/api/search", json={"query": "조용한 공부를 할 수 있는 카페"})

        self.assertEqual(res.status_code, 200)
        results = res.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0]["final_score"], 80)
        self.assertIn("공부 목적", results[0]["ai"]["reason"])

    def test_duplicate_place_ratings_are_merged_by_average(self):
        first = {
            "name": "맥도날드 중앙대점",
            "user_rating": 4.0,
            "provider": "google",
            "provider_place_id": "places/mcdonalds-cau",
            "address": "서울 동작구",
            "latitude": 37.5,
            "longitude": 126.95,
            "provider_rating": 4.2,
            "category": "fast_food_restaurant",
            "photo_refs": "[]",
        }
        second = {**first, "user_rating": 3.0}

        first_id = database.add_place(first)
        second_id = database.add_place(second)

        self.assertEqual(first_id, second_id)
        places = database.list_places()
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0]["name"], "맥도날드 중앙대점")
        self.assertEqual(places[0]["user_rating"], 3.5)
        self.assertEqual(places[0]["rating_count"], 2)

    def test_delete_place_removes_registered_rating(self):
        place_id = database.add_place({
            "name": "삭제할 카페",
            "user_rating": 4.0,
            "provider": "google",
            "provider_place_id": "places/delete-me",
            "address": "서울",
            "latitude": 37.56,
            "longitude": 126.97,
            "provider_rating": 4.2,
            "category": "cafe",
            "photo_refs": "[]",
        })

        res = self.client.delete(f"/api/places/{place_id}")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(database.list_places(), [])

    def test_ranking_weights_user_map_and_ai_scores(self):
        result = compute_final_score(
            {"user_rating": 5, "provider_rating": 4},
            {"intent_match": 1, "environment_score": 0.8, "evidence_confidence": 0.7},
        )
        self.assertEqual(result["final_score"], 91.0)

    def test_home_page_loads(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("공동 맛집 지도", res.text)
        self.assertIn("AI로 추천받기", res.text)


if __name__ == "__main__":
    unittest.main()
