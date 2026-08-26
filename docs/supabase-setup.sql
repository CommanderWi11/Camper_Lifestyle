-- Home_Quest_QH — Supabase schema.
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
-- keeps the daily search honouring discards. Nothing is broken; it just doesn't
-- sync across devices.
--
-- On RLS: there is no auth here. The anon key is public (it ships in config.js to
-- every visitor) and the policies below are permissive. That is a deliberate,
-- accepted trade-off for a private family tool with an unguessable URL — but it does
-- mean anyone who finds the URL could write to these tables. Don't put anything
-- sensitive in a comment.

-- Favourites (the ★ button).
create table if not exists house_stars (
  listing_id  text primary key,
  created_at  timestamptz not null default now()
);

-- Discards (the 🗑 button). harvest.py READS this before it scrapes, so a row here
-- means the property is never surfaced again — not merely hidden in the UI.
create table if not exists house_hidden (
  listing_id  text primary key,
  created_at  timestamptz not null default now()
);

alter table house_stars  enable row level security;
alter table house_hidden enable row level security;

do $$
declare t text;
begin
  foreach t in array array['house_stars','house_hidden']
  loop
    execute format('drop policy if exists anon_all on %I', t);
    execute format(
      'create policy anon_all on %I for all to anon using (true) with check (true)', t);
  end loop;
end $$;
