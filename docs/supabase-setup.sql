-- Camper Lifestyle — Supabase schema.
--
-- WHY THIS FILE EXISTS: on 2026-07-13 the project this dashboard pointed at
-- (voirsxfjdayhhvwviaqt.supabase.co) had been deleted — the hostname returned
-- NXDOMAIN. Stars, discards, comments and status had all been silently dead for
-- some time, because supabase-js resolves rather than throws on a network failure,
-- so the page just rendered with everything missing. Three of the four tables had
-- no committed schema anywhere, so there was nothing to restore FROM. Now there is.
--
-- TO RESTORE:
--   1. Create a Supabase project (free tier is fine).
--   2. Paste this whole file into the SQL editor and run it.
--   3. Put the new project URL + anon key into docs/config.js.
--   4. Reload the dashboard — the "Sin conexión con Supabase" banner should vanish.
--
-- Until then the dashboard falls back to localStorage, and scripts/blocklist.json
-- keeps the weekly search honouring discards. Nothing is broken; it just doesn't
-- sync across devices.
--
-- On RLS: there is no auth here. The anon key is public (it ships in config.js to
-- every visitor) and the policies below are permissive. That is a deliberate,
-- accepted trade-off for a private family tool with an unguessable URL — but it does
-- mean anyone who finds the URL could write to these tables. Don't put anything
-- sensitive in a comment.

-- Comments on a listing.
create table if not exists camper_comments (
  id          uuid primary key default gen_random_uuid(),
  listing_id  text        not null,
  author      text        not null,
  body        text        not null check (char_length(body) between 1 and 500),
  created_at  timestamptz not null default now()
);
create index if not exists camper_comments_listing_idx on camper_comments (listing_id);

-- Favourites (the ★ button).
create table if not exists camper_stars (
  listing_id  text primary key,
  created_at  timestamptz not null default now()
);

-- Discards (the 🗑 button). harvest.py READS this before it scrapes, so a row here
-- means the vehicle is never surfaced again — not merely hidden in the UI.
create table if not exists camper_hidden (
  listing_id  text primary key,
  created_at  timestamptz not null default now()
);

-- Triage state (Nuevo / Siguiendo / Contactado).
create table if not exists camper_status (
  listing_id  text primary key,
  status      text        not null check (status in ('new','watching','contacted','discarded')),
  updated_at  timestamptz not null default now()
);

alter table camper_comments enable row level security;
alter table camper_stars    enable row level security;
alter table camper_hidden   enable row level security;
alter table camper_status   enable row level security;

do $$
declare t text;
begin
  foreach t in array array['camper_comments','camper_stars','camper_hidden','camper_status']
  loop
    execute format('drop policy if exists anon_all on %I', t);
    execute format(
      'create policy anon_all on %I for all to anon using (true) with check (true)', t);
  end loop;
end $$;
