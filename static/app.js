const map = L.map("map").setView([37.5665, 126.9780], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

let markers = [];

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
      <p class="meta">내 평점 ${place.user_rating} · 지도 평점 ${place.provider_rating ?? "없음"} · ${place.category ?? "분류 없음"}</p>
      <p class="reason">${place.ai?.reason ?? ""}</p>
    </article>
  `).join("");
}

async function loadPlaces() {
  const res = await fetch("/api/places");
  const data = await res.json();
  renderMarkers(data.places || []);
}

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
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query })
  });
  const data = await res.json();
  renderResults(data.results || []);
  renderMarkers(data.results || []);
});

loadPlaces();
