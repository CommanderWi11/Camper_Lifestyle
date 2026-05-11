const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let allListings = [];
let commentsByListing = {};

const STATUS_LABELS = {
  new: 'Nuevo',
  watching: 'Siguiendo',
  contacted: 'Contactado',
  discarded: 'Descartado',
};

const STATUS_CLASSES = {
  new: 'badge-new',
  watching: 'badge-watching',
  contacted: 'badge-contacted',
  discarded: 'badge-discarded',
};

async function init() {
  const [listings, commentsResult] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    supabaseClient.from('camper_comments').select('*').order('created_at', { ascending: true }),
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

  const dates = allListings.map(l => l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    document.getElementById('last-updated').textContent = `Actualizado: ${dates[0]}`;
  }

  document.getElementById('filter-status').addEventListener('change', render);
  document.getElementById('sort-by').addEventListener('change', render);

  render();
}

function render() {
  const statusFilter = document.getElementById('filter-status').value;
  const sortBy = document.getElementById('sort-by').value;

  let listings = [...allListings];

  if (statusFilter) {
    listings = listings.filter(l => l.status === statusFilter);
  }

  if (sortBy === 'price') {
    listings.sort((a, b) => a.price - b.price);
  } else {
    listings.sort((a, b) => (b.added_at || '').localeCompare(a.added_at || ''));
  }

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

  return `
    <article class="card" data-id="${listing.id}">
      ${listing.photo
        ? `<img class="card-photo" src="${listing.photo}" alt="${listing.title}" loading="lazy">`
        : `<div class="card-photo card-photo--empty">🚐</div>`
      }
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
          <input name="author" placeholder="Tu nombre" required maxlength="50" autocomplete="name">
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
      <strong>${escapeHtml(comment.author)}</strong>
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
  const author = form.author.value.trim();
  const body = form.body.value.trim();
  const btn = form.querySelector('button');

  btn.disabled = true;
  btn.textContent = 'Guardando...';

  const { data, error } = await supabaseClient
    .from('camper_comments')
    .insert({ listing_id: listingId, author, body })
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

init().catch(err => {
  document.getElementById('listings-grid').innerHTML =
    '<p class="loading">Error al cargar los anuncios. Recarga la página.</p>';
  console.error('Init failed:', err);
});
