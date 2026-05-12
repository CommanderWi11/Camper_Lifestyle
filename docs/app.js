const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let allListings = [];
let commentsByListing = {};
let starredSet = new Set();
let hiddenSet = new Set();
let statusMap = new Map();
let newSet = new Set();
let newOnly = false;

const CURRENT_YEAR = new Date().getFullYear();

const SCORE_THRESHOLDS = {
  perYear:       { green: 4000,  amber: 7000  },
  perThousandKm: { green: 400,   amber: 800   },
  kmPerYear:     { green: 10000, amber: 18000 },
};

const STATUS_LABELS = {
  new: 'Nuevo',
  watching: 'Siguiendo',
  contacted: 'Contactado',
  discarded: 'Descartado',
  reference: 'Referencia',
};

const STATUS_CLASSES = {
  new: 'badge-new',
  watching: 'badge-watching',
  contacted: 'badge-contacted',
  discarded: 'badge-discarded',
  reference: 'badge-reference',
};

// Score helpers
function scorePerYear(listing) {
  if (!listing.price || !listing.year) return null;
  return Math.round(listing.price / Math.max(1, CURRENT_YEAR - listing.year));
}
function scorePerThousandKm(listing) {
  if (!listing.price || !listing.km) return null;
  return Math.round(listing.price / (listing.km / 1000));
}
function scoreKmPerYear(listing) {
  if (!listing.year || !listing.km) return null;
  return Math.round(listing.km / Math.max(1, CURRENT_YEAR - listing.year));
}
function colorFor(value, t) {
  return value <= t.green ? 'green' : value <= t.amber ? 'amber' : 'red';
}
function getEffectiveStatus(listing) {
  return statusMap.get(listing.id) ?? listing.status;
}

async function init() {
  const [listings, commentsResult, starsResult, hiddenResult, statusResult] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    supabaseClient.from('camper_comments').select('*').order('created_at', { ascending: true }),
    supabaseClient.from('camper_stars').select('listing_id'),
    supabaseClient.from('camper_hidden').select('listing_id'),
    supabaseClient.from('camper_status').select('listing_id, status'),
  ]);

  allListings = listings;

  if (commentsResult.data) {
    for (const comment of commentsResult.data) {
      if (!commentsByListing[comment.listing_id]) commentsByListing[comment.listing_id] = [];
      commentsByListing[comment.listing_id].push(comment);
    }
  }
  if (starsResult.data)  starsResult.data.forEach(r => starredSet.add(r.listing_id));
  if (hiddenResult.data) hiddenResult.data.forEach(r => hiddenSet.add(r.listing_id));
  if (statusResult.data) statusResult.data.forEach(r => statusMap.set(r.listing_id, r.status));

  // Staleness label
  const dates = allListings.map(l => l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    const lastDate = dates[0];
    const daysAgo = Math.floor((Date.now() - new Date(lastDate).getTime()) / 86400000);
    const el = document.getElementById('last-updated');
    let label, cls;
    if (daysAgo === 0)      { label = `Actualizado hoy (${lastDate})`;                              cls = 'freshness-ok'; }
    else if (daysAgo === 1) { label = `Actualizado ayer (${lastDate})`;                             cls = 'freshness-ok'; }
    else if (daysAgo <= 3)  { label = `Hace ${daysAgo} días (${lastDate}) — ejecuta buscar.sh`;    cls = 'freshness-warn'; }
    else                    { label = `Desactualizado: ${daysAgo} días sin buscar (${lastDate})`;   cls = 'freshness-stale'; }
    el.textContent = label;
    el.className = cls;
  }

  // "New since last visit" — preserve the original lastVisit for this session
  const today = new Date().toISOString().slice(0, 10);
  let sessionLastVisit = sessionStorage.getItem('session_last_visit');
  if (!sessionLastVisit) {
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
  document.getElementById('sort-by').addEventListener('change', render);
  document.getElementById('filter-starred').addEventListener('change', render);
  document.getElementById('filter-hidden').addEventListener('change', render);

  const grid = document.getElementById('listings-grid');
  grid.addEventListener('click', handleStarToggle);
  grid.addEventListener('click', handleHideToggle);
  grid.addEventListener('click', handleStatusChange);

  render();
}

function render() {
  const statusFilter = document.getElementById('filter-status').value;
  const sortBy = document.getElementById('sort-by').value;
  const starredOnly = document.getElementById('filter-starred').checked;
  const showHidden = document.getElementById('filter-hidden').checked;

  let listings = [...allListings];

  if (!showHidden) {
    listings = listings.filter(l => !hiddenSet.has(l.id) || l.pinned);
  }

  if (statusFilter) {
    listings = listings.filter(l => getEffectiveStatus(l) === statusFilter);
  }

  if (starredOnly) {
    listings = listings.filter(l => starredSet.has(l.id));
  }

  if (newOnly) {
    listings = listings.filter(l => newSet.has(l.id));
  }

  listings.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    if (sortBy === 'price') return a.price - b.price;
    return (b.added_at || '').localeCompare(a.added_at || '');
  });

  const grid = document.getElementById('listings-grid');
  grid.innerHTML = listings.length
    ? listings.map(renderCard).join('')
    : '<p class="loading">No hay anuncios con ese filtro.</p>';

  grid.querySelectorAll('.comment-form').forEach(form => {
    form.addEventListener('submit', handleCommentSubmit);
  });
}

function renderScoreChips(listing) {
  if (listing.pinned) return '';
  const py  = scorePerYear(listing);
  const pkm = scorePerThousandKm(listing);
  const ky  = scoreKmPerYear(listing);
  if (py === null && pkm === null && ky === null) return '';
  const T = SCORE_THRESHOLDS;
  return `
    <div class="score-chips">
      ${py  !== null ? `<span class="score-chip ${colorFor(py,  T.perYear)}">${py.toLocaleString('es-ES')} €/año</span>` : ''}
      ${pkm !== null ? `<span class="score-chip ${colorFor(pkm, T.perThousandKm)}">${pkm.toLocaleString('es-ES')} €/1000km</span>` : ''}
      ${ky  !== null ? `<span class="score-chip ${colorFor(ky,  T.kmPerYear)}">${ky.toLocaleString('es-ES')} km/año</span>` : ''}
    </div>`;
}

function renderActionBar(listing) {
  if (listing.pinned) return '';
  const es = getEffectiveStatus(listing);
  return `
    <div class="action-bar" data-listing-id="${listing.id}">
      <button class="action-btn action-new      ${es === 'new'       ? 'active' : ''}" data-status="new">Nuevo</button>
      <button class="action-btn action-watching ${es === 'watching'  ? 'active' : ''}" data-status="watching">Siguiendo</button>
      <button class="action-btn action-contacted${es === 'contacted' ? 'active' : ''}" data-status="contacted">Contactado</button>
      <button class="action-btn action-discarded${es === 'discarded' ? 'active' : ''}" data-status="discarded">Descartado</button>
    </div>`;
}

function renderCard(listing) {
  const comments = commentsByListing[listing.id] || [];
  const price = listing.price > 0 ? `${listing.price.toLocaleString('es-ES')} €` : '—';
  const isStarred = starredSet.has(listing.id);
  const isHidden  = hiddenSet.has(listing.id);
  const isNew     = newSet.has(listing.id);
  const es = getEffectiveStatus(listing);

  return `
    <article class="card${isHidden ? ' card--hidden' : ''}" data-id="${listing.id}">
      <div class="card-photo-wrapper">
        ${listing.photo
          ? `<img class="card-photo" src="${listing.photo}" alt="${escapeHtml(listing.title)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
          : ''
        }
        <div class="card-photo card-photo--empty"${listing.photo ? ' style="display:none"' : ''}>🚐</div>
        <button class="star-btn${isStarred ? ' starred' : ''}" data-id="${listing.id}" aria-label="Favorito">★</button>
        ${!listing.pinned ? `<button class="hide-btn" data-id="${listing.id}" aria-label="${isHidden ? 'Mostrar' : 'Ocultar'}">${isHidden ? '👁' : '✕'}</button>` : ''}
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
          ${listing.bathroom ? `<span class="badge badge-feature">🚿 Baño</span>` : ''}
          ${listing.sleeping ? `<span>🛏️ ${listing.sleeping} plazas</span>` : ''}
          ${listing.location ? `<span>📍 ${escapeHtml(listing.location)}</span>` : ''}
          <span class="source">${listing.source}</span>
        </div>

        ${renderScoreChips(listing)}

        <div class="comments" id="comments-${listing.id}">
          ${comments.map(renderComment).join('')}
        </div>

        <form class="comment-form" data-listing-id="${listing.id}">
          <textarea name="body" placeholder="¿Qué te parece este anuncio?" required maxlength="500" rows="2"></textarea>
          <button type="submit">Comentar</button>
        </form>

        ${renderActionBar(listing)}
      </div>
    </article>`;
}

function renderComment(comment) {
  const date = new Date(comment.created_at).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
  return `
    <div class="comment">
      <span class="comment-date">${date}</span>
      <p>${escapeHtml(comment.body)}</p>
    </div>`;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function handleCommentSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const listingId = form.dataset.listingId;
  const body = form.body.value.trim();
  const btn = form.querySelector('button');

  btn.disabled = true;
  btn.textContent = 'Guardando...';

  const { data, error } = await supabaseClient
    .from('camper_comments')
    .insert({ listing_id: listingId, author: 'Anónimo', body })
    .select()
    .single();

  btn.disabled = false;
  btn.textContent = 'Comentar';

  if (error) { alert('Error al guardar el comentario.'); return; }

  if (!commentsByListing[listingId]) commentsByListing[listingId] = [];
  commentsByListing[listingId].push(data);
  document.getElementById(`comments-${listingId}`).insertAdjacentHTML('beforeend', renderComment(data));
  form.reset();
}

async function handleStarToggle(e) {
  const btn = e.target.closest('.star-btn');
  if (!btn) return;
  const id = btn.dataset.id;
  btn.disabled = true;
  if (starredSet.has(id)) {
    await supabaseClient.from('camper_stars').delete().eq('listing_id', id);
    starredSet.delete(id);
  } else {
    await supabaseClient.from('camper_stars').insert({ listing_id: id });
    starredSet.add(id);
  }
  btn.classList.toggle('starred', starredSet.has(id));
  btn.disabled = false;
  if (document.getElementById('filter-starred').checked) render();
}

async function handleHideToggle(e) {
  const btn = e.target.closest('.hide-btn');
  if (!btn) return;
  const id = btn.dataset.id;
  btn.disabled = true;
  if (hiddenSet.has(id)) {
    await supabaseClient.from('camper_hidden').delete().eq('listing_id', id);
    hiddenSet.delete(id);
  } else {
    await supabaseClient.from('camper_hidden').insert({ listing_id: id });
    hiddenSet.add(id);
  }
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

  // Optimistic update
  statusMap.set(listingId, newStatus);
  bar.querySelectorAll('.action-btn').forEach(b => b.classList.toggle('active', b.dataset.status === newStatus));
  const badge = btn.closest('.card')?.querySelector('.card-header .badge');
  if (badge) {
    badge.className = `badge ${STATUS_CLASSES[newStatus] || ''}`;
    badge.textContent = STATUS_LABELS[newStatus] || newStatus;
  }

  const { error } = await supabaseClient
    .from('camper_status')
    .upsert({ listing_id: listingId, status: newStatus, updated_at: new Date().toISOString() }, { onConflict: 'listing_id' });

  if (error) {
    // Revert
    prevStatus ? statusMap.set(listingId, prevStatus) : statusMap.delete(listingId);
    alert('Error al guardar el estado.');
    render();
    return;
  }

  if (document.getElementById('filter-status').value) render();
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML =
    '<p class="loading">Error al cargar los anuncios. Recarga la página.</p>';
  console.error('Init failed:', err);
});
