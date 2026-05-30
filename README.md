# AI Place Agent Map

지도 기반 AI 맛집/장소 추천 에이전트입니다.

사용자는 음식점 또는 카페 이름과 평점만 입력합니다. 서버는 지도 API로 실제 장소 정보를 찾고, DB에는 사용자 평점과 지도 provider의 place id를 저장합니다. 검색 사용자는 자연어로 조건을 입력하고, Gemini가 장소 정보와 사진 정보를 바탕으로 적합도를 판단합니다.

## Architecture

```text
사용자 장소 등록
→ FastAPI
→ Google Places API로 장소 검색
→ SQLite에 name, user_rating, provider_place_id 저장

사용자 자연어 검색
→ FastAPI
→ DB 후보 조회
→ Google Places/Gemini로 장소 적합도 분석
→ ranking.py에서 가중치 점수 계산
→ 결과 반환
```

## Setup

```bash
cd /Users/taewony5589/CODING/place-agent-map
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 필요한 키를 넣습니다.

```env
GEMINI_API_KEY=...
GOOGLE_MAPS_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

키가 없어도 fallback으로 실행은 됩니다. 다만 실제 지도 장소 검색과 사진 기반 AI 분석은 제한됩니다.

## Run

```bash
uvicorn main:app --reload
```

브라우저에서 엽니다.

```text
http://127.0.0.1:8000/
```

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Environment Variables:

```text
GEMINI_API_KEY
GOOGLE_MAPS_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```
