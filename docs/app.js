// Top 5 de hoy + Favoritos — minimal cards, nothing else.
//
// listings.json / listings-gc.json each hold one track's ranked Top 5 (rank
// 1-5) and Favorites (starred, rank null) — Tafira and Gran Canaria
// respectively, switched via the tab bar (see wireTabs()). A listing that
// drops out of a track's Top 5 and was never starred simply isn't in that
// file on the next research pass — no archive to maintain here.
//
// The manual research snapshots (history.json) render on their own page since
// 2026-08-13 — manual.html / manual.js, linked from the header. That page is
// Tafira-only and has no tabs. Data loading, card rendering, and the
// star/discard handlers live in shared.js.

async function init() {
  await loadData();
  wireGrid();
  wireTabs();
  updateLastUpdated();
  render();
}

function updateLastUpdated() {
  const dates = allListings.map(l => l.checked_at || l.added_at).filter(Boolean).sort().reverse();
  const el = document.getElementById('last-updated');
  if (!dates.length) { el.textContent = ''; return; }
  const daysAgo = Math.floor((Date.now() - new Date(dates[0]).getTime()) / 86400000);
  el.textContent = daysAgo <= 0 ? `Actualizado hoy` : daysAgo === 1 ? `Actualizado ayer` : `Hace ${daysAgo} días`;
}

function wireTabs() {
  const buttons = document.querySelectorAll('.tab-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('active')) return;
      buttons.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      setActiveTrack(btn.dataset.track);
      updateLastUpdated();
      render();
    });
  });
}

function splitTop5AndFavorites(listings, known) {
  const top5 = listings.filter(l => l.rank).sort((a, b) => a.rank - b.rank);
  const top5Ids = new Set(top5.map(l => l.id));
  const favorites = [...starredSet]
    .filter(id => !hiddenSet.has(id) && !top5Ids.has(id) && known.has(id))
    .map(id => known.get(id))
    .sort((a, b) => (starredAtById.get(b.id) || '').localeCompare(starredAtById.get(a.id) || ''));
  return { top5, favorites };
}

function render() {
  const known = allKnownEntries();
  const listings = allListings.filter(l => !hiddenSet.has(l.id));
  const { top5, favorites } = splitTop5AndFavorites(listings, known);
  const grid = document.getElementById('listings-grid');

  if (!top5.length && !favorites.length) {
    grid.innerHTML = '<p class="msg">Nada por aquí todavía.</p>';
    return;
  }

  let html = '<section><h2>Top 5</h2>';
  html += top5.length
    ? `<div class="grid">${top5.map(renderCard).join('')}</div>`
    : '<p class="msg">Sin ganadores hoy.</p>';
  html += '</section>';

  html += '<section><h2 class="favorites-heading">Favoritos</h2>';
  html += favorites.length
    ? `<div class="grid">${favorites.map(renderCard).join('')}</div>`
    : '<p class="msg">Pulsa ★ en una vivienda para guardarla aquí.</p>';
  html += '</section>';

  grid.innerHTML = html;
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML = '<p class="msg">Error al cargar. Recarga la página.</p>';
  console.error('Init failed:', err);
});
