const map = L.map("map").setView([37.5665, 126.9780], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

let markers = [];
let currentPlaces = [];

function clearMarkers() {
  markers.forEach(marker => marker.remove());
  markers = [];
}

function renderMarkers(places) {
  clearMarkers();
  const bounds = [];
  places.forEach(place => {
    if (!place.latitude || !place.longitude) return;
    const marker = L.marker([place.latitude, place.longitude])
      .addTo(map)
      .bindPopup(`<strong>${place.name}</strong><br>${place.address || ""}<br>내 평점: ${place.user_rating}`);
    markers.push(marker);
    bounds.push([place.latitude, place.longitude]);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
}

function renderResults(results) {
  const el = document.getElementById("results");
  if (!results.length) {
    el.textContent = "조건에 맞는 장소가 아직 없습니다.";
    return;
  }
  el.innerHTML = results.map((place, idx) => `
    <article class="result">
      <strong>${idx + 1}. ${place.name}</strong>
      <span class="score">AI 재해석 점수 ${place.final_score}점</span>
      <p class="meta">평균 평점 ${place.user_rating} · 참여 ${place.rating_count ?? 1}명 · 지도 평점 ${place.provider_rating ?? "없음"} · ${place.category ?? "분류 없음"}</p>
      <p class="reason">${place.ai?.reason ?? ""}</p>
      <button class="delete-place result-delete" type="button" data-id="${place.id}" aria-label="${place.name} 삭제">이 장소 삭제</button>
    </article>
  `).join("");
}

function renderPlacesList(places) {
  const el = document.getElementById("places-list");
  if (!places.length) {
    el.textContent = "아직 등록된 장소가 없습니다.";
    return;
  }
  el.innerHTML = places.map(place => `
    <article class="place-item">
      <div>
        <strong>${place.name}</strong>
        <p class="meta">평균 평점 ${place.user_rating} · 참여 ${place.rating_count ?? 1}명 · 지도 평점 ${place.provider_rating ?? "없음"}</p>
      </div>
      <button class="delete-place" type="button" data-id="${place.id}" aria-label="${place.name} 삭제">삭제</button>
    </article>
  `).join("");
}

async function deletePlace(placeId) {
  const ok = confirm("이 장소의 등록된 평균 평점 정보를 삭제할까요?");
  if (!ok) return;
  const res = await fetch(`/api/places/${placeId}`, { method: "DELETE" });
  if (!res.ok) {
    alert("삭제에 실패했습니다. 잠시 뒤 다시 시도해주세요.");
    return;
  }
  await loadPlaces();
  renderResults([]);
}

async function loadPlaces() {
  const res = await fetch("/api/places");
  const data = await res.json();
  currentPlaces = data.places || [];
  renderMarkers(currentPlaces);
  renderPlacesList(currentPlaces);
}

document.getElementById("places-list").addEventListener("click", async (event) => {
  const button = event.target.closest(".delete-place");
  if (!button) return;
  await deletePlace(button.dataset.id);
});

document.getElementById("results").addEventListener("click", async (event) => {
  const button = event.target.closest(".delete-place");
  if (!button) return;
  await deletePlace(button.dataset.id);
});

document.getElementById("place-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("place-name").value.trim();
  const user_rating = Number(document.getElementById("place-rating").value);
  if (!name) return;
  await fetch("/api/places", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, user_rating })
  });
  event.target.reset();
  document.getElementById("place-rating").value = "4.0";
  await loadPlaces();
});

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("search-query").value.trim();
  if (!query) return;
  const button = document.getElementById("search-button");
  const resultsEl = document.getElementById("results");
  button.classList.add("is-loading");
  button.disabled = true;
  resultsEl.innerHTML = `<div class="loading"><span class="spinner inline" aria-hidden="true"></span>AI가 장소와 조건을 비교하는 중입니다...</div>`;
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });
    if (!res.ok) throw new Error("search failed");
    const data = await res.json();
    renderResults(data.results || []);
    renderMarkers(data.results || []);
  } catch (error) {
    resultsEl.textContent = "AI 추천을 불러오지 못했습니다. 잠시 뒤 다시 시도해주세요.";
  } finally {
    button.classList.remove("is-loading");
    button.disabled = false;
  }
});

loadPlaces();
