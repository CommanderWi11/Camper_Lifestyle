// Plumbing shared by both pages — index.html (Top 5 + Favoritos, now with two
// track tabs: Tafira / Gran Canaria) and manual.html (Añadidos a mano, the
// relocated history view — Tafira-only, no tabs, see allKnownEntries() below).
// Split out of app.js 2026-08-13 when the manual snapshots moved to their own
// page; extended 2026-08-28 for the two-track tabs.
//
// Contract with the per-page scripts: each page defines its own global
// render() (classic scripts, shared global scope) and calls loadData() +
// wireGrid() from its init. The star/discard handlers here re-render by
// calling that page's render(). `allListings` always points at the ACTIVE
// track's board (see setActiveTrack()) — manual.html never calls
// setActiveTrack, so it stays on the default ("tafira") the whole time, which
// is what its Top-5-exclusion check in manual.js needs.

let allListingsByTrack = { tafira: [], gc: [] };
let archiveByTrack = { tafira: [], gc: [] };
let activeTrack = 'tafira';
let allListings = [];
let archiveSnapshots = [];
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
        supabaseClient.from('house_stars').select('listing_id, created_at'),
        supabaseClient.from('house_hidden').select('listing_id'),
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
  local.get('house_stars').forEach(id => starredSet.add(id));
  local.get('house_hidden').forEach(id => hiddenSet.add(id));
}

async function persistStar(id, starred) {
  if (!online) return local.set('house_stars', [...starredSet]);
  const { error } = starred
    ? await supabaseClient.from('house_stars').insert({ listing_id: id })
    : await supabaseClient.from('house_stars').delete().eq('listing_id', id);
  if (error) throw error;
}

async function persistHidden(id) {
  if (!online) return local.set('house_hidden', [...hiddenSet]);
  const { error } = await supabaseClient.from('house_hidden').insert({ listing_id: id });
  if (error) throw error;
}

async function loadData() {
  const [tafira, gc, tafiraArchive, gcArchive, history] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    fetch('listings-gc.json').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch('archive.json').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch('archive-gc.json').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch('history.json').then(r => r.ok ? r.json() : []).catch(() => []),
    loadState(),
  ]);
  allListingsByTrack = { tafira, gc };
  archiveByTrack = { tafira: tafiraArchive, gc: gcArchive };
  allListings = allListingsByTrack[activeTrack];
  archiveSnapshots = archiveByTrack[activeTrack];
  historySnapshots = history;
}

/** Switches which track's board `allListings`/`archiveSnapshots` point at
 *  (see the module comment above). Only called from index.html's tab
 *  buttons — manual.html never calls this, so it stays on the default
 *  'tafira' track. */
function setActiveTrack(track) {
  activeTrack = track;
  allListings = allListingsByTrack[track] || [];
  archiveSnapshots = archiveByTrack[track] || [];
}

function wireGrid() {
  const grid = document.getElementById('listings-grid');
  grid.addEventListener('click', handleStarToggle);
  grid.addEventListener('click', handleDiscardToggle);
}

/** Every listing this dashboard knows about for the ACTIVE track — today's
 *  board, that track's "previous searches" archive, and (Tafira only) the
 *  manual "Añadidos a mano" history — keyed by id, so a favorite can be
 *  starred from any of them and Favoritos/the discard confirm dialog can
 *  still find it. archiveSnapshots and historySnapshots are both
 *  newest-first, so on a shared id (the same house reappearing across dated
 *  searches) the most recent snapshot's copy wins. */
function allKnownEntries() {
  const known = new Map();
  for (const l of allListings) known.set(l.id, l);
  for (const snapshot of archiveSnapshots) {
    for (const e of snapshot.entries) {
      if (!known.has(e.id)) known.set(e.id, e);
    }
  }
  if (activeTrack === 'tafira') {
    for (const snapshot of historySnapshots) {
      for (const e of snapshot.entries) {
        if (!known.has(e.id)) known.set(e.id, e);
      }
    }
  }
  return known;
}

const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function formatDateEs(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return `${d} ${MONTHS_ES[m - 1]} ${y}`;
}

// Bespoke line-art house mark shown when a listing has no photo (~1 in 5 in
// practice — og:image backfill fails often enough that a bare emoji reads as
// clip-art at that frequency). Single inline SVG, no external asset.
const HOUSE_ICON = `<svg viewBox="0 0 48 32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">
  <path d="M6 16 24 4l18 12"/>
  <path d="M9 14v14a2 2 0 0 0 2 2h26a2 2 0 0 0 2-2V14"/>
  <path d="M20 30V20h8v10"/>
</svg>`;

function renderCard(listing, index) {
  const price = listing.price > 0 ? `${listing.price.toLocaleString('es-ES')} €` : '—';
  const isStarred = starredSet.has(listing.id);
  const bedrooms = listing.specs?.bedrooms != null ? `${listing.specs.bedrooms}` : null;
  const size = listing.specs?.size_m2 != null ? `${listing.specs.size_m2} m²` : null;
  const hasGarden = listing.specs?.has_garden === true;
  const hasOffice = listing.specs?.has_office_room === true;
  const hasDeskArea = !hasOffice && Boolean(listing.specs?.office_notes);
  const rankBadge = listing.rank ? `<span class="rank-badge">${String(listing.rank).padStart(2, '0')}</span>` : '';
  const titleText = escapeHtml(listing.title);
  const outsideTafira = listing.is_target_area === false;

  return `
    <article class="card" style="--stagger:${index || 0}" data-id="${listing.id}">
      <div class="photo-frame">
        ${rankBadge}
        <a class="photo-link" href="${listing.url}" target="_blank" rel="noopener noreferrer">
          ${listing.photo
            ? `<img class="photo" src="${listing.photo}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
            : ''}
          <div class="photo photo--empty"${listing.photo ? ' style="display:none"' : ''}>${HOUSE_ICON}</div>
        </a>
      </div>
      <div class="card-body">
        <a class="title" href="${listing.url}" target="_blank" rel="noopener noreferrer" title="${titleText}">${titleText}</a>
        <div class="price">${price}</div>
        <div class="meta">
          ${listing.location ? `<span>📍 ${escapeHtml(listing.location)}</span>` : ''}
          ${outsideTafira ? `<span class="badge-outside-area">Fuera de Tafira</span>` : ''}
          ${bedrooms ? `<span>🛏 ${bedrooms}</span>` : ''}
          ${size ? `<span>📐 ${size}</span>` : ''}
          ${hasGarden ? `<span>🌳 Jardín</span>` : ''}
          ${hasOffice ? `<span>🏢 Despacho</span>` : hasDeskArea ? `<span>🖥 Zona de escritorio</span>` : ''}
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
    || archiveSnapshots.flatMap(s => s.entries).find(e => e.id === id)
    || historySnapshots.flatMap(s => s.entries).find(e => e.id === id);
  if (!confirm(`¿Eliminar "${listing ? listing.title : 'esta vivienda'}"? No volverá a aparecer.`)) return;

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
