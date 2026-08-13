// Plumbing shared by both pages — index.html (Top 5 + Favoritos) and
// manual.html (Añadidos a mano, the relocated history view). Split out of
// app.js 2026-08-13 when the manual snapshots moved to their own page.
//
// Contract with the per-page scripts: each page defines its own global
// render() (classic scripts, shared global scope) and calls loadData() +
// wireGrid() from its init. The star/discard handlers here re-render by
// calling that page's render().

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

async function loadData() {
  const [listings, history] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    fetch('history.json').then(r => r.ok ? r.json() : []).catch(() => []),
    loadState(),
  ]);
  allListings = listings;
  historySnapshots = history;
}

function wireGrid() {
  const grid = document.getElementById('listings-grid');
  grid.addEventListener('click', handleStarToggle);
  grid.addEventListener('click', handleDiscardToggle);
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

const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function formatDateEs(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return `${d} ${MONTHS_ES[m - 1]} ${y}`;
}

// Bespoke line-art camper mark shown when a listing has no photo (~1 in 5 in
// practice — og:image backfill fails often enough that a bare emoji reads as
// clip-art at that frequency). Single inline SVG, no external asset.
const CAMPER_ICON = `<svg viewBox="0 0 48 32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">
  <path d="M2 22V9a2 2 0 0 1 2-2h21l10 8v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z"/>
  <path d="M25 7v10h10"/>
  <path d="M2 15h23"/>
  <circle cx="12" cy="25.5" r="3.2"/>
  <circle cx="33" cy="25.5" r="3.2"/>
</svg>`;

function renderCard(listing, index) {
  const price = listing.price > 0 ? `${listing.price.toLocaleString('es-ES')} €` : '—';
  const isStarred = starredSet.has(listing.id);
  const size = listing.specs?.length_m ? `${String(listing.specs.length_m).replace('.', ',')} m` : null;
  const km = listing.km != null ? `${listing.km.toLocaleString('es-ES')} km` : null;
  const rankBadge = listing.rank ? `<span class="rank-badge">${String(listing.rank).padStart(2, '0')}</span>` : '';
  const titleText = escapeHtml(listing.title);

  return `
    <article class="card" style="--stagger:${index || 0}" data-id="${listing.id}">
      <div class="photo-frame">
        ${rankBadge}
        <a class="photo-link" href="${listing.url}" target="_blank" rel="noopener noreferrer">
          ${listing.photo
            ? `<img class="photo" src="${listing.photo}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
            : ''}
          <div class="photo photo--empty"${listing.photo ? ' style="display:none"' : ''}>${CAMPER_ICON}</div>
        </a>
      </div>
      <div class="card-body">
        <a class="title" href="${listing.url}" target="_blank" rel="noopener noreferrer" title="${titleText}">${titleText}</a>
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
