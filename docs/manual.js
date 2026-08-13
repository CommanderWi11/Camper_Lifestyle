// Añadidos a mano — the manual research snapshots (history.json), moved off the
// main dashboard onto their own page 2026-08-13. One dated sub-section per
// batch, same cards and star/discard plumbing as the main page (shared.js).
//
// Exclusion semantics are identical to when this lived below Favoritos: a
// listing already in today's Top 5, starred (it shows under Favoritos on the
// main page), or discarded is not shown here. Across dates each vehicle (by
// id) renders at most once, under its most recent date — dedupeHistoryByLatest
// in history-dedup.js. docs/history.json itself keeps every dated mention;
// only rendering is deduped.

async function init() {
  await loadData();
  wireGrid();
  render();
}

function render() {
  const grid = document.getElementById('listings-grid');
  const top5Ids = new Set(allListings.filter(l => l.rank && !hiddenSet.has(l.id)).map(l => l.id));
  const excludeIds = new Set([...hiddenSet, ...starredSet, ...top5Ids]);
  const deduped = dedupeHistoryByLatest(historySnapshots, excludeIds);

  if (!deduped.length) {
    grid.innerHTML = '<p class="msg">Nada por aquí todavía.</p>';
    return;
  }

  let html = '';
  for (const snapshot of deduped) {
    html += `<div class="history-batch"><h3 class="history-heading">${formatDateEs(snapshot.date)}</h3>`;
    html += `<div class="grid">${snapshot.entries.map(renderCard).join('')}</div>`;
    html += '</div>';
  }
  grid.innerHTML = `<section>${html}</section>`;
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML = '<p class="msg">Error al cargar. Recarga la página.</p>';
  console.error('Init failed:', err);
});
