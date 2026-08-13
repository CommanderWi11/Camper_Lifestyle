// Top 5 de hoy + Favoritos — minimal cards, nothing else.
//
// listings.json holds today's ranked Top 5 (rank 1-5) and Favorites (starred,
// rank null). A listing that drops out of the Top 5 and was never starred simply
// isn't in the file on the next research pass — no archive to maintain here.
//
// The manual research snapshots (history.json) render on their own page since
// 2026-08-13 — manual.html / manual.js, linked from the header. Data loading,
// card rendering, and the star/discard handlers live in shared.js.

async function init() {
  await loadData();

  const dates = allListings.map(l => l.checked_at || l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    const daysAgo = Math.floor((Date.now() - new Date(dates[0]).getTime()) / 86400000);
    document.getElementById('last-updated').textContent =
      daysAgo <= 0 ? `Actualizado hoy` : daysAgo === 1 ? `Actualizado ayer` : `Hace ${daysAgo} días`;
  }

  wireGrid();
  render();
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
    : '<p class="msg">Pulsa ★ en una autocaravana para guardarla aquí.</p>';
  html += '</section>';

  grid.innerHTML = html;
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML = '<p class="msg">Error al cargar. Recarga la página.</p>';
  console.error('Init failed:', err);
});
