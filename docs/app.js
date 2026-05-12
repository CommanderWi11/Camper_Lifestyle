const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let allListings = [];
let commentsByListing = {};
let starredSet = new Set();

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

async function init() {
  const [listings, commentsResult, starsResult] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    supabaseClient.from('camper_comments').select('*').order('created_at', { ascending: true }),
    supabaseClient.from('camper_stars').select('listing_id'),
  ]);

  allListings = listings;

  if (commentsResult.data) {
    for (const comment of commentsResult.data) {
      if (!commentsByListing[comment.listing_id]) {
        commentsByListing[comment.listing_id] = [];
      }
      commentsByListing[comment.listing_id].push(comment);
    }
  }

  if (starsResult.data) {
    for (const row of starsResult.data) {
      starredSet.add(row.listing_id);
    }
  }

  const dates = allListings.map(l => l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    const lastDate = dates[0];
    const daysAgo = Math.floor((Date.now() - new Date(lastDate).getTime()) / 86400000);
    const el = document.getElementById('last-updated');
    let label, cls;
    if (daysAgo === 0) {
      label = `Actualizado hoy (${lastDate})`;
      cls = 'freshness-ok';
    } else if (daysAgo === 1) {
      label = `Actualizado ayer (${lastDate})`;
      cls = 'freshness-ok';
    } else if (daysAgo <= 3) {
      label = `Hace ${daysAgo} días (${lastDate}) — ejecuta buscar.sh`;
      cls = 'freshness-warn';
    } else {
      label = `Desactualizado: ${daysAgo} días sin buscar (${lastDate})`;
      cls = 'freshness-stale';
    }
    el.textContent = label;
    el.className = cls;
  }

  document.getElementById('filter-status').addEventListener('change', render);
  document.getElementById('sort-by').addEventListener('change', render);
  document.getElementById('filter-starred').addEventListener('change', render);
  document.getElementById('listings-grid').addEventListener('click', handleStarToggle);

  render();
}

function render() {
  const statusFilter = document.getElementById('filter-status').value;
  const sortBy = document.getElementById('sort-by').value;
  const starredOnly = document.getElementById('filter-starred').checked;

  let listings = [...allListings];

  if (statusFilter) {
    listings = listings.filter(l => l.status === statusFilter);
  }

  if (starredOnly) {
    listings = listings.filter(l => starredSet.has(l.id));
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

function renderCard(listing) {
  const comments = commentsByListing[listing.id] || [];
  const price = listing.price > 0
    ? `${listing.price.toLocaleString('es-ES')} €`
    : '—';
  const isStarred = starredSet.has(listing.id);

  return `
    <article class="card" data-id="${listing.id}">
      <div class="card-photo-wrapper">
        ${listing.photo
          ? `<img class="card-photo" src="${listing.photo}" alt="${listing.title}" loading="lazy">`
          : `<div class="card-photo card-photo--empty">🚐</div>`
        }
        <button class="star-btn${isStarred ? ' starred' : ''}" data-id="${listing.id}" aria-label="Marcar como favorito">★</button>
      </div>
      <div class="card-body">
        <div class="card-header">
          <h2 class="card-title">
            <a href="${listing.url}" target="_blank" rel="noopener noreferrer">${listing.title}</a>
          </h2>
          <span class="badge ${STATUS_CLASSES[listing.status] || ''}">
            ${STATUS_LABELS[listing.status] || listing.status}
          </span>
        </div>

        <div class="card-meta">
          <span>💶 ${price}</span>
          ${listing.year ? `<span>📅 ${listing.year}</span>` : ''}
          ${listing.km ? `<span>🛣️ ${listing.km.toLocaleString('es-ES')} km</span>` : ''}
          ${listing.bathroom ? `<span class="badge badge-feature">🚿 Baño</span>` : ''}
          ${listing.sleeping ? `<span>🛏️ ${listing.sleeping} plazas</span>` : ''}
          ${listing.location ? `<span>📍 ${listing.location}</span>` : ''}
          <span class="source">${listing.source}</span>
        </div>

        <div class="comments" id="comments-${listing.id}">
          ${comments.map(renderComment).join('')}
        </div>

        <form class="comment-form" data-listing-id="${listing.id}">
          <textarea name="body" placeholder="¿Qué te parece este anuncio?" required maxlength="500" rows="2"></textarea>
          <button type="submit">Comentar</button>
        </form>
      </div>
    </article>
  `;
}

function renderComment(comment) {
  const date = new Date(comment.created_at).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
  return `
    <div class="comment">
      <span class="comment-date">${date}</span>
      <p>${escapeHtml(comment.body)}</p>
    </div>
  `;
}

function escapeHtml(str) {
  str = String(str ?? '');
  return str
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

  if (error) {
    alert('Error al guardar el comentario. Inténtalo de nuevo.');
    return;
  }

  if (!commentsByListing[listingId]) commentsByListing[listingId] = [];
  commentsByListing[listingId].push(data);

  document.getElementById(`comments-${listingId}`).insertAdjacentHTML(
    'beforeend',
    renderComment(data),
  );

  form.reset();
}

async function handleStarToggle(e) {
  const btn = e.target.closest('.star-btn');
  if (!btn) return;

  const id = btn.dataset.id;
  const wasStarred = starredSet.has(id);

  btn.disabled = true;

  if (wasStarred) {
    await supabaseClient.from('camper_stars').delete().eq('listing_id', id);
    starredSet.delete(id);
  } else {
    await supabaseClient.from('camper_stars').insert({ listing_id: id });
    starredSet.add(id);
  }

  btn.classList.toggle('starred', starredSet.has(id));
  btn.disabled = false;

  if (document.getElementById('filter-starred').checked) {
    render();
  }
}

init().catch(err => {
  document.getElementById('listings-grid').innerHTML =
    '<p class="loading">Error al cargar los anuncios. Recarga la página.</p>';
  console.error('Init failed:', err);
});
