// Motorhome Lifestyle — the weekly Top 5 board.
//
// listings.json is a BOARD, not a feed: every entry is a past or present winner,
// carrying the week it last won and its rank in that week. Rendering is simply
// "group by week, newest first" — which is what makes a replaced van slide down
// the page instead of disappearing.
//
// Star/discard/status state lives in Supabase so it follows the family across
// devices. If Supabase is unreachable we fall back to localStorage rather than
// breaking the page — a board whose buttons do nothing is worse than useless.

let allListings = [];
let commentsByListing = {};
let starredSet = new Set();
let hiddenSet = new Set();
let statusMap = new Map();
let newSet = new Set();
let newOnly = false;

let supabaseClient = null;
let online = false; // is Supabase actually answering?

const CURRENT_YEAR = new Date().getFullYear();

const SCORE_THRESHOLDS = {
  perYear:       { green: 4000,  amber: 7000  },
  perThousandKm: { green: 400,   amber: 800   },
  kmPerYear:     { green: 10000, amber: 18000 },
};

const STATUS_LABELS = {
  new: 'Nuevo', watching: 'Siguiendo', contacted: 'Contactado',
  discarded: 'Descartado', reference: 'Referencia',
};
const STATUS_CLASSES = {
  new: 'badge-new', watching: 'badge-watching', contacted: 'badge-contacted',
  discarded: 'badge-discarded', reference: 'badge-reference',
};

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

// ---------------------------------------------------------------- persistence
// One shim over "Supabase if it's up, localStorage if it isn't", so every caller
// below can be written as though the backend always works.

const local = {
  get(key) {
    try { return JSON.parse(localStorage.getItem(key) || '[]'); }
    catch { return []; }
  },
  set(key, value) { localStorage.setItem(key, JSON.stringify(value)); },
};

// A dead Supabase host does NOT fail fast — the fetch can hang for a long time,
// and supabase-js retries on top of that. Without this cap the board never renders
// at all, which is exactly what happened when the project was deleted.
const withTimeout = (promise, ms, what) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${what} timed out`)), ms)),
]);

const STATE_TIMEOUT_MS = 5000;

async function loadState() {
  if (typeof SUPABASE_URL === 'string' && SUPABASE_URL && window.supabase) {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    try {
      const [comments, stars, hidden, status] = await withTimeout(Promise.all([
        supabaseClient.from('camper_comments').select('*').order('created_at', { ascending: true }),
        supabaseClient.from('camper_stars').select('listing_id'),
        supabaseClient.from('camper_hidden').select('listing_id'),
        supabaseClient.from('camper_status').select('listing_id, status'),
      ]), STATE_TIMEOUT_MS, 'Supabase');
      // supabase-js RESOLVES on a network failure instead of throwing, so a dead
      // project arrives as an error object, not an exception. Check for it, or the
      // page silently renders with every star and discard missing.
      const failure = comments.error || stars.error || hidden.error || status.error;
      if (failure) throw failure;

      online = true;
      (comments.data || []).forEach(c => { (commentsByListing[c.listing_id] ||= []).push(c); });
      (stars.data  || []).forEach(r => starredSet.add(r.listing_id));
      (hidden.data || []).forEach(r => hiddenSet.add(r.listing_id));
      (status.data || []).forEach(r => statusMap.set(r.listing_id, r.status));
      return;
    } catch (err) {
      console.warn('Supabase unreachable, using localStorage:', err?.message || err);
    }
  }

  online = false;
  document.getElementById('offline-banner').hidden = false;
  local.get('camper_stars').forEach(id => starredSet.add(id));
  local.get('camper_hidden').forEach(id => hiddenSet.add(id));
  local.get('camper_status').forEach(([id, s]) => statusMap.set(id, s));
  local.get('camper_comments').forEach(c => { (commentsByListing[c.listing_id] ||= []).push(c); });
}

async function persistStar(id, starred) {
  if (!online) return local.set('camper_stars', [...starredSet]);
  const { error } = starred
    ? await supabaseClient.from('camper_stars').insert({ listing_id: id })
    : await supabaseClient.from('camper_stars').delete().eq('listing_id', id);
  if (error) throw error;
}

async function persistHidden(id, hidden) {
  if (!online) return local.set('camper_hidden', [...hiddenSet]);
  const { error } = hidden
    ? await supabaseClient.from('camper_hidden').insert({ listing_id: id })
    : await supabaseClient.from('camper_hidden').delete().eq('listing_id', id);
  if (error) throw error;
}

async function persistStatus(id, status) {
  if (!online) return local.set('camper_status', [...statusMap.entries()]);
  const { error } = await supabaseClient.from('camper_status')
    .upsert({ listing_id: id, status, updated_at: new Date().toISOString() },
            { onConflict: 'listing_id' });
  if (error) throw error;
}

// --------------------------------------------------------------------- scoring

const scorePerYear = l => (!l.price || !l.year) ? null
  : Math.round(l.price / Math.max(1, CURRENT_YEAR - l.year));
const scorePerThousandKm = l => (!l.price || !l.km) ? null
  : Math.round(l.price / (l.km / 1000));
const scoreKmPerYear = l => (!l.year || !l.km) ? null
  : Math.round(l.km / Math.max(1, CURRENT_YEAR - l.year));
const colorFor = (v, t) => v <= t.green ? 'green' : v <= t.amber ? 'amber' : 'red';
const getEffectiveStatus = l => statusMap.get(l.id) ?? l.status;

// --------------------------------------------------------------------- startup

async function init() {
  const [listings] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    loadState(),
  ]);
  allListings = listings;

  // Always mark the most recent additions, independent of visit history: a
  // listing whose added_at falls within the current (top) week's run is a
  // genuinely new entry this run, not a returning winner promoted back up —
  // and should show as new even on a fresh browser or after localStorage is
  // cleared, not just "since your last visit" (see below).
  const rankedWeeks = [...new Set(allListings.filter(l => !l.pinned && l.week).map(l => l.week))]
    .sort().reverse();
  const currentWeekItems = allListings.filter(l => l.week === rankedWeeks[0]);
  const currentWeekStart = currentWeekItems[0]?.week_start;
  if (currentWeekStart) {
    for (const l of currentWeekItems) {
      if (l.added_at && l.added_at >= currentWeekStart) newSet.add(l.id);
    }
  }

  const dates = allListings.map(l => l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    const lastDate = dates[0];
    const daysAgo = Math.floor((Date.now() - new Date(lastDate).getTime()) / 86400000);
    const el = document.getElementById('last-updated');
    let label, cls;
    if (daysAgo <= 1)      { label = `Actualizado ${daysAgo ? 'ayer' : 'hoy'} (${lastDate})`;   cls = 'freshness-ok'; }
    else if (daysAgo <= 8) { label = `Hace ${daysAgo} días (${lastDate})`;                       cls = 'freshness-ok'; }
    else                   { label = `Sin actualizar desde hace ${daysAgo} días (${lastDate})`;  cls = 'freshness-stale'; }
    el.textContent = label;
    el.className = cls;
  }

  // "New since your last visit", pinned for the whole session so a reload doesn't
  // instantly mark everything as seen.
  const today = new Date().toISOString().slice(0, 10);
  let sessionLastVisit = sessionStorage.getItem('session_last_visit');
  if (sessionLastVisit === null) {
    sessionLastVisit = localStorage.getItem('last_visit') || '';
    sessionStorage.setItem('session_last_visit', sessionLastVisit);
    localStorage.setItem('last_visit', today);
  }
  if (sessionLastVisit) {
    for (const l of allListings) {
      if (l.added_at && l.added_at > sessionLastVisit) newSet.add(l.id);
    }
  }

  const newCountEl = document.getElementById('new-count');
  if (sessionLastVisit && newSet.size > 0) {
    newCountEl.textContent = `· ${newSet.size} nuevo${newSet.size > 1 ? 's' : ''} desde ${sessionLastVisit}`;
    newCountEl.classList.add('clickable');
    newCountEl.addEventListener('click', () => {
      newOnly = !newOnly;
      newCountEl.classList.toggle('active', newOnly);
      render();
    });
  }

  document.getElementById('filter-status').addEventListener('change', render);
  document.getElementById('filter-starred').addEventListener('change', render);
  document.getElementById('filter-hidden').addEventListener('change', render);

  const grid = document.getElementById('listings-grid');
  grid.addEventListener('click', handleStarToggle);
  grid.addEventListener('click', handleDiscardToggle);
  grid.addEventListener('click', handleStatusChange);

  render();
}

// ------------------------------------------------------------------- rendering

function weekLabel(weekStart) {
  const [, m, d] = weekStart.split('-').map(Number);
  return `${d} de ${MONTHS[m - 1]}`;
}

/** Group the board into week sections, newest first. This IS the feature: the top
 *  section is this week's Top 5, and everything a new winner displaced simply sits
 *  in the section below it. */
function groupByWeek(listings) {
  const pinned = listings.filter(l => l.pinned);
  const ranked = listings.filter(l => !l.pinned && l.week);
  // Anything without a week predates the Top-5 board. Keep it reachable, at the end.
  const legacy = listings.filter(l => !l.pinned && !l.week);

  const weeks = [...new Set(ranked.map(l => l.week))].sort().reverse();
  const sections = weeks.map((week, i) => {
    const items = ranked.filter(l => l.week === week)
                        .sort((a, b) => (a.rank || 99) - (b.rank || 99));
    const start = items[0]?.week_start;
    return {
      title: i === 0 ? `🏆 Top ${items.length} · Semana del ${weekLabel(start)}`
                     : `Semana del ${weekLabel(start)}`,
      current: i === 0,
      items,
    };
  });

  if (legacy.length) sections.push({ title: 'Archivo', current: false, items: legacy });
  return { pinned, sections };
}

function render() {
  const statusFilter = document.getElementById('filter-status').value;
  const starredOnly  = document.getElementById('filter-starred').checked;
  const showHidden   = document.getElementById('filter-hidden').checked;

  let listings = [...allListings];
  if (!showHidden)  listings = listings.filter(l => !hiddenSet.has(l.id) || l.pinned);
  if (statusFilter) listings = listings.filter(l => getEffectiveStatus(l) === statusFilter);
  if (starredOnly)  listings = listings.filter(l => starredSet.has(l.id));
  if (newOnly)      listings = listings.filter(l => newSet.has(l.id));

  const grid = document.getElementById('listings-grid');
  if (!listings.length) {
    grid.innerHTML = '<p class="loading">No hay anuncios con ese filtro.</p>';
    return;
  }

  const { pinned, sections } = groupByWeek(listings);
  let html = '';
  if (pinned.length) {
    html += `<div class="week-grid">${pinned.map(renderCard).join('')}</div>`;
  }
  for (const section of sections) {
    html += `<h2 class="week-heading${section.current ? ' week-heading--current' : ''}">`
          + `${escapeHtml(section.title)}<span class="week-count">${section.items.length}</span></h2>`
          + `<div class="week-grid">${section.items.map(renderCard).join('')}</div>`;
  }
  grid.innerHTML = html;

  grid.querySelectorAll('.comment-form').forEach(f => f.addEventListener('submit', handleCommentSubmit));
}

function renderScoreChips(listing) {
  if (listing.pinned) return '';
  const py = scorePerYear(listing), pkm = scorePerThousandKm(listing), ky = scoreKmPerYear(listing);
  if (py === null && pkm === null && ky === null) return '';
  const T = SCORE_THRESHOLDS;
  return `<div class="score-chips">
    ${py  !== null ? `<span class="score-chip ${colorFor(py,  T.perYear)}">${py.toLocaleString('es-ES')} €/año</span>` : ''}
    ${pkm !== null ? `<span class="score-chip ${colorFor(pkm, T.perThousandKm)}">${pkm.toLocaleString('es-ES')} €/1000km</span>` : ''}
    ${ky  !== null ? `<span class="score-chip ${colorFor(ky,  T.kmPerYear)}">${ky.toLocaleString('es-ES')} km/año</span>` : ''}
  </div>`;
}

// Only the specs that decide whether this van works for two toddlers.
const SPEC_ICONS = {
  seatbelts: v => `🔒 ${v} cinturones`,
  berths:    v => `🛏️ ${v} plazas`,
  layout:    v => `📐 ${v}`,
  bathroom:  v => (v ? '🚿 Baño' : null),
  garage:    v => (v ? '🧳 Garaje' : null),
  length_m:  v => `📏 ${v} m`,
  mma_kg:    v => `⚖️ ${Number(v).toLocaleString('es-ES')} kg`,
};

function renderSpecs(listing) {
  const specs = listing.specs || {};
  const chips = Object.entries(SPEC_ICONS)
    .map(([key, fmt]) => (specs[key] == null ? null : fmt(specs[key])))
    .filter(Boolean)
    .map(label => `<span class="spec-chip">${escapeHtml(label)}</span>`);
  return chips.length ? `<div class="spec-chips">${chips.join('')}</div>` : '';
}

function renderVerdict(listing) {
  if (!listing.verdict) return '';
  const flags = (listing.flags || []).map(f => `<li>${escapeHtml(f)}</li>`).join('');
  return `<div class="verdict">
    <p>${escapeHtml(listing.verdict)}</p>
    ${flags ? `<ul class="flags">${flags}</ul>` : ''}
  </div>`;
}

function renderActionBar(listing) {
  if (listing.pinned) return '';
  const es = getEffectiveStatus(listing);
  return `<div class="action-bar" data-listing-id="${listing.id}">
    <button class="action-btn action-new      ${es === 'new'       ? 'active' : ''}" data-status="new">Nuevo</button>
    <button class="action-btn action-watching ${es === 'watching'  ? 'active' : ''}" data-status="watching">Siguiendo</button>
    <button class="action-btn action-contacted${es === 'contacted' ? 'active' : ''}" data-status="contacted">Contactado</button>
  </div>`;
}

function renderCard(listing) {
  const comments  = commentsByListing[listing.id] || [];
  const price     = listing.price > 0 ? `${listing.price.toLocaleString('es-ES')} €` : '—';
  const isStarred = starredSet.has(listing.id);
  const isHidden  = hiddenSet.has(listing.id);
  const isNew     = newSet.has(listing.id);
  const es        = getEffectiveStatus(listing);

  return `
    <article class="card${isHidden ? ' card--hidden' : ''}" data-id="${listing.id}">
      <div class="card-photo-wrapper">
        ${listing.photo
          ? `<img class="card-photo" src="${listing.photo}" alt="${escapeHtml(listing.title)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
          : ''}
        <div class="card-photo card-photo--empty"${listing.photo ? ' style="display:none"' : ''}>🚐</div>
        ${listing.rank ? `<span class="rank-badge">#${listing.rank}</span>` : ''}
        ${Number.isFinite(listing.score) ? `<span class="score-badge" title="Puntuación familiar">${listing.score}</span>` : ''}
        <button class="star-btn${isStarred ? ' starred' : ''}" data-id="${listing.id}"
                aria-label="Favorito" title="Guardar como favorito">★</button>
        ${!listing.pinned ? `<button class="discard-btn" data-id="${listing.id}"
                aria-label="${isHidden ? 'Recuperar' : 'Descartar'}"
                title="${isHidden ? 'Recuperar esta autocaravana' : 'Descartar — no volverá a salir en próximas búsquedas'}">${isHidden ? '↩' : '🗑'}</button>` : ''}
        ${isNew ? `<span class="new-ribbon">✨ Nuevo</span>` : ''}
      </div>
      <div class="card-body">
        <div class="card-header">
          <h2 class="card-title">
            <a href="${listing.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(listing.title)}</a>
          </h2>
          <span class="badge ${STATUS_CLASSES[es] || ''}">${STATUS_LABELS[es] || es}</span>
        </div>

        <div class="card-meta">
          <span>💶 ${price}</span>
          ${listing.year ? `<span>📅 ${listing.year}</span>` : ''}
          ${listing.km   ? `<span>🛣️ ${listing.km.toLocaleString('es-ES')} km</span>` : ''}
          ${listing.location ? `<span>📍 ${escapeHtml(listing.location)}</span>` : ''}
          <span class="source">${escapeHtml(listing.source || '')}</span>
        </div>

        ${renderSpecs(listing)}
        ${renderVerdict(listing)}
        ${renderScoreChips(listing)}

        <div class="comments" id="comments-${listing.id}">
          ${comments.map(renderComment).join('')}
        </div>

        <form class="comment-form" data-listing-id="${listing.id}">
          <textarea name="body" placeholder="¿Qué te parece?" required maxlength="500" rows="2"></textarea>
          <button type="submit">Comentar</button>
        </form>

        ${renderActionBar(listing)}
      </div>
    </article>`;
}

function renderComment(comment) {
  const date = new Date(comment.created_at).toLocaleDateString('es-ES',
    { day: 'numeric', month: 'short', year: 'numeric' });
  return `<div class="comment"><span class="comment-date">${date}</span><p>${escapeHtml(comment.body)}</p></div>`;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// -------------------------------------------------------------------- handlers

async function handleStarToggle(e) {
  const btn = e.target.closest('.star-btn');
  if (!btn) return;
  const id = btn.dataset.id;
  btn.disabled = true;
  const starred = !starredSet.has(id);
  starred ? starredSet.add(id) : starredSet.delete(id);
  btn.classList.toggle('starred', starred);
  try {
    await persistStar(id, starred);
  } catch {
    starred ? starredSet.delete(id) : starredSet.add(id);
    btn.classList.toggle('starred', !starred);
    alert('No se pudo guardar el favorito.');
  }
  btn.disabled = false;
  if (document.getElementById('filter-starred').checked) render();
}

/** Discard: hide it here AND stop the weekly search from ever surfacing it again.
 *  harvest.py reads this list before it scrapes, so this is a real veto, not a
 *  cosmetic hide. Reversible via the "Ver descartadas" checkbox. */
async function handleDiscardToggle(e) {
  const btn = e.target.closest('.discard-btn');
  if (!btn) return;
  const id = btn.dataset.id;
  btn.disabled = true;
  const hidden = !hiddenSet.has(id);
  hidden ? hiddenSet.add(id) : hiddenSet.delete(id);
  try {
    await persistHidden(id, hidden);
  } catch {
    hidden ? hiddenSet.delete(id) : hiddenSet.add(id);
    alert('No se pudo guardar el descarte.');
  }
  btn.disabled = false;
  render();
}

async function handleStatusChange(e) {
  const btn = e.target.closest('.action-btn');
  if (!btn) return;
  const bar = btn.closest('.action-bar');
  if (!bar) return;

  const listingId = bar.dataset.listingId;
  const newStatus = btn.dataset.status;
  const listing = allListings.find(l => l.id === listingId);
  if (!listing) return;

  const prevStatus = statusMap.get(listingId) ?? listing.status;
  if (newStatus === prevStatus) return;

  statusMap.set(listingId, newStatus);
  bar.querySelectorAll('.action-btn').forEach(b => b.classList.toggle('active', b.dataset.status === newStatus));
  const badge = btn.closest('.card')?.querySelector('.card-header .badge');
  if (badge) {
    badge.className = `badge ${STATUS_CLASSES[newStatus] || ''}`;
    badge.textContent = STATUS_LABELS[newStatus] || newStatus;
  }

  try {
    await persistStatus(listingId, newStatus);
  } catch {
    prevStatus ? statusMap.set(listingId, prevStatus) : statusMap.delete(listingId);
    alert('Error al guardar el estado.');
    render();
    return;
  }
  if (document.getElementById('filter-status').value) render();
}

async function handleCommentSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const listingId = form.dataset.listingId;
  const body = form.body.value.trim();
  const btn = form.querySelector('button');

  btn.disabled = true;
  btn.textContent = 'Guardando...';

  let comment = { listing_id: listingId, author: 'Anónimo', body,
                  created_at: new Date().toISOString() };
  try {
    if (online) {
      const { data, error } = await supabaseClient.from('camper_comments')
        .insert({ listing_id: listingId, author: 'Anónimo', body }).select().single();
      if (error) throw error;
      comment = data;
    } else {
      local.set('camper_comments', [...local.get('camper_comments'), comment]);
    }
  } catch {
    btn.disabled = false;
    btn.textContent = 'Comentar';
    alert('Error al guardar el comentario.');
    return;
  }

  btn.disabled = false;
  btn.textContent = 'Comentar';
  (commentsByListing[listingId] ||= []).push(comment);
  document.getElementById(`comments-${listingId}`)
          .insertAdjacentHTML('beforeend', renderComment(comment));
  form.reset();
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML =
    '<p class="loading">Error al cargar los anuncios. Recarga la página.</p>';
  console.error('Init failed:', err);
});
