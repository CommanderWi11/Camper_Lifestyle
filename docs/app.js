// Top 5 de hoy + Favoritos — minimal cards, nothing else.
//
// listings.json holds today's ranked Top 5 (rank 1-5) and Favorites (starred,
// rank null). A listing that drops out of the Top 5 and was never starred simply
// isn't in the file on the next research pass — no archive to maintain here.
//
// history.json is a SEPARATE, additive concept: dated snapshots of Luis's manual
// deep-research passes (sites the automated harvester can't reach), added
// 2026-07-27 via scripts/ingest_manual_shortlist.py. It never feeds back into
// listings.json/board.py — it's just rendered below Favoritos, one section per
// date, using the same card/star/delete plumbing.

let allListings = [];
let historySnapshots = [];
let starredSet = new Set();
let starredAtById = new Map();
let hiddenSet = new Set();

let supabaseClient = null;
let online = false;

const local = {
  get(key) {
    try { return JSON.parse(localStorage.getItem(key) || '[]'); }
    catch { return []; }
  },
  set(key, value) { localStorage.setItem(key, JSON.stringify(value)); },
};

// A dead Supabase host does not fail fast, so cap the wait rather than let the
// page hang forever waiting on a project that no longer exists.
const withTimeout = (promise, ms) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error('timed out')), ms)),
]);

async function loadState() {
  if (typeof SUPABASE_URL === 'string' && SUPABASE_URL && window.supabase) {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    try {
      const [stars, hidden] = await withTimeout(Promise.all([
        supabaseClient.from('camper_stars').select('listing_id, created_at'),
        supabaseClient.from('camper_hidden').select('listing_id'),
      ]), 5000);
      if (stars.error || hidden.error) throw (stars.error || hidden.error);
      online = true;
      stars.data.forEach(r => { starredSet.add(r.listing_id); starredAtById.set(r.listing_id, r.created_at); });
      hidden.data.forEach(r => hiddenSet.add(r.listing_id));
      return;
    } catch (err) {
      console.warn('Supabase unreachable, using localStorage:', err?.message || err);
    }
  }
  online = false;
  document.getElementById('offline-banner').hidden = false;
  local.get('camper_stars').forEach(id => starredSet.add(id));
  local.get('camper_hidden').forEach(id => hiddenSet.add(id));
}

async function persistStar(id, starred) {
  if (!online) return local.set('camper_stars', [...starredSet]);
  const { error } = starred
    ? await supabaseClient.from('camper_stars').insert({ listing_id: id })
    : await supabaseClient.from('camper_stars').delete().eq('listing_id', id);
  if (error) throw error;
}

async function persistHidden(id) {
  if (!online) return local.set('camper_hidden', [...hiddenSet]);
  const { error } = await supabaseClient.from('camper_hidden').insert({ listing_id: id });
  if (error) throw error;
}

async function init() {
  const [listings, history] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    fetch('history.json').then(r => r.ok ? r.json() : []).catch(() => []),
    loadState(),
  ]);
  allListings = listings;
  historySnapshots = history;

  const dates = allListings.map(l => l.checked_at || l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    const daysAgo = Math.floor((Date.now() - new Date(dates[0]).getTime()) / 86400000);
    document.getElementById('last-updated').textContent =
      daysAgo <= 0 ? `Actualizado hoy` : daysAgo === 1 ? `Actualizado ayer` : `Hace ${daysAgo} días`;
  }

  const grid = document.getElementById('listings-grid');
  grid.addEventListener('click', handleStarToggle);
  grid.addEventListener('click', handleDiscardToggle);

  render();
}

/** Every listing this dashboard knows about, automated board + history, keyed
 *  by id — a favorite can be starred from either, so Favoritos has to be able
 *  to find it wherever it lives. historySnapshots is newest-first, so on a
 *  shared id (the same vehicle reappearing across dated searches) the most
 *  recent snapshot's copy wins. */
function allKnownEntries() {
  const known = new Map();
  for (const l of allListings) known.set(l.id, l);
  for (const snapshot of historySnapshots) {
    for (const e of snapshot.entries) {
      if (!known.has(e.id)) known.set(e.id, e);
    }
  }
  return known;
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

  if (!top5.length && !favorites.length && !historySnapshots.length) {
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

  const top5Ids = new Set(top5.map(l => l.id));
  html += renderHistory(top5Ids);

  grid.innerHTML = html;
}

const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function formatDateEs(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return `${d} ${MONTHS_ES[m - 1]} ${y}`;
}

/** Manual research snapshots (history.json), one dated sub-section per batch,
 *  all nested under a single "Manual Searches" umbrella section (just below
 *  Favoritos). A listing already shown in Top 5, Favoritos (starred), or
 *  discarded is excluded here so it isn't shown twice. Across dates, each
 *  vehicle (by id) is shown at most once, under its most recent date — see
 *  dedupeHistoryByLatest in history-dedup.js. docs/history.json itself keeps
 *  every dated mention; only rendering is deduped. */
function renderHistory(top5Ids) {
  if (!historySnapshots.length) return '';
  const excludeIds = new Set([...hiddenSet, ...starredSet, ...top5Ids]);
  const deduped = dedupeHistoryByLatest(historySnapshots, excludeIds);
  if (!deduped.length) return '';
  let body = '';
  for (const snapshot of deduped) {
    body += `<div class="history-batch"><h3 class="history-heading">${formatDateEs(snapshot.date)}</h3>`;
    body += `<div class="grid">${snapshot.entries.map(renderCard).join('')}</div>`;
    body += '</div>';
  }
  return `<section><h2 class="manual-heading">Búsquedas manuales</h2>${body}</section>`;
}

function renderCard(listing) {
  const price = listing.price > 0 ? `${listing.price.toLocaleString('es-ES')} €` : '—';
  const isStarred = starredSet.has(listing.id);
  const size = listing.specs?.length_m ? `${String(listing.specs.length_m).replace('.', ',')} m` : null;
  const km = listing.km != null ? `${listing.km.toLocaleString('es-ES')} km` : null;

  return `
    <article class="card" data-id="${listing.id}">
      <a class="photo-link" href="${listing.url}" target="_blank" rel="noopener noreferrer">
        ${listing.photo
          ? `<img class="photo" src="${listing.photo}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
          : ''}
        <div class="photo photo--empty"${listing.photo ? ' style="display:none"' : ''}>🚐</div>
      </a>
      <div class="card-body">
        <a class="title" href="${listing.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(listing.title)}</a>
        <div class="price">${price}</div>
        <div class="meta">
          ${listing.location ? `<span>📍 ${escapeHtml(listing.location)}</span>` : ''}
          ${size ? `<span>📏 ${size}</span>` : ''}
          ${km   ? `<span>🛣️ ${km}</span>` : ''}
        </div>
        <div class="actions">
          <button class="btn-star${isStarred ? ' active' : ''}" data-id="${listing.id}">${isStarred ? '★ Favorito' : '☆ Favorito'}</button>
          <button class="btn-delete" data-id="${listing.id}">🗑 Eliminar</button>
        </div>
      </div>
    </article>`;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function handleStarToggle(e) {
  const btn = e.target.closest('.btn-star');
  if (!btn) return;
  const id = btn.dataset.id;
  btn.disabled = true;
  const starred = !starredSet.has(id);
  starred ? starredSet.add(id) : starredSet.delete(id);
  if (starred) starredAtById.set(id, new Date().toISOString());
  try {
    await persistStar(id, starred);
  } catch {
    starred ? starredSet.delete(id) : starredSet.add(id);
    alert('No se pudo guardar el favorito.');
  }
  btn.disabled = false;
  render();
}

/** Permanent: removes it from the dashboard and stops the daily search from ever
 *  surfacing it again (harvest.py reads the discard list before it scrapes). */
async function handleDiscardToggle(e) {
  const btn = e.target.closest('.btn-delete');
  if (!btn) return;
  const id = btn.dataset.id;
  const listing = allListings.find(l => l.id === id)
    || historySnapshots.flatMap(s => s.entries).find(e => e.id === id);
  if (!confirm(`¿Eliminar "${listing ? listing.title : 'esta autocaravana'}"? No volverá a aparecer.`)) return;

  btn.disabled = true;
  try {
    await persistHidden(id);
  } catch {
    btn.disabled = false;
    alert('No se pudo eliminar. Inténtalo de nuevo.');
    return;
  }
  hiddenSet.add(id);
  render();
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML = '<p class="msg">Error al cargar. Recarga la página.</p>';
  console.error('Init failed:', err);
});
