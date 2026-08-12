# Canary Islands Motorhome Selling Sites

**SUPERSEDED 2026-08-11** — Luis restored the project to Europe-wide scope
(used + new). This file is no longer read by `weekly-search.sh` or
`research-prompt.md`; see `europe-motorhome-selling-sites.md` instead. Left
here for reference only in case the Canary-only scope ever comes back.

Added 2026-07-30, replacing `europe-motorhome-selling-sites.md` in the active
pipeline: Luis refocused the project to the Canary Islands only (Gran Canaria,
Tenerife, Lanzarote, Fuerteventura, La Palma, La Gomera, El Hierro, La
Graciosa) — both **used** (segunda mano) and **new** (0km, concesionario)
units. This is the master list Stage B works through, in the order listed:
Canarias-filtered general marketplaces first, then known Canary Islands
dealers, then live search for anything a static list can't capture.

"New" means dealer/concesionario stock (0km or ex-demonstrator); "Used" means
second-hand listings, private or dealer.

## Canarias-filtered general marketplaces

These are national Spanish classifieds — always use the Canarias-filtered
URL/search, never the nationwide one, since the whole point of this list is
staying in-scope.

| Website | Type | Canarias filter |
|---|---|---|
| [Milanuncios](https://www.milanuncios.com/autocaravanas-de-segunda-mano/canarias.htm) | Used, mostly private | `canarias.htm` suffix on the category URL |
| [Coches.net](https://www.coches.net/autocaravanas-y-remolques/canarias/) | Both — dealers post new/0km stock here too | `/canarias/` path segment on the category URL |
| [Wallapop](https://es.wallapop.com/app/search?keywords=autocaravana) | Used, private | Filter by province (Las Palmas / Santa Cruz de Tenerife) in the UI after searching — Wallapop's location filter is a radius-from-point picker, not a URL param, so Stage B must open the search UI and set it, not just append a query string |
| [Autocasion](https://www.autocasion.com/autocaravanas) | Both — has a dedicated "nuevas" filter | Filter by provincia (Las Palmas / Santa Cruz de Tenerife) in the UI |
| [AutoScout24 Spain](https://www.autoscout24.es/lst-caravan) | Both | Filter by ubicación/provincia in the UI |

Milanuncios and Coches.net are also scraped deterministically by
`scripts/harvest.py` (Stage A) — Stage B only needs to fill gaps the harvester
misses (poor card data, pagination limits, listings that appeared since the
last harvest).

## Known Canary Islands dealers

Confirmed real businesses from this project's own history (used as mandatory
Stage B fetch targets before the 2026-07-26 Europe-wide detour, now
reinstated):

- **RentCamper Canarias** — rents and sells autocaravanas, Gran Canaria.
- **Autocaravanas Canarias** — dealer, both new and used stock.

Check both every run even if a search doesn't surface anything new — their
stock turns over and a static list goes stale otherwise.

## New (0km) motorhomes — active search required

There is no reliable static list of every authorized new-vehicle dealer in
the islands, and one will go stale fast. Every run, Stage B must actively
**WebSearch** for current dealers rather than only checking the list above:

- `concesionario autocaravanas nuevas Gran Canaria`
- `concesionario autocaravanas nuevas Tenerife`
- `autocaravanas 0km Canarias`
- `[marca] concesionario Canarias` for each brand in the model-family list in
  `research-prompt.md` (Benimar, Adria, Hymer, Bürstner, Rapido, Chausson,
  Challenger, Knaus, Carado, Sunlight, Dethleffs, Elnagh, Roller Team,
  Etrusco, etc.) — many manufacturers publish an online dealer locator
  ("encuentra tu concesionario") that can be filtered to Canarias.
- Coches.net and Autocasion (above) both carry dealer/0km stock alongside
  used listings — don't skip them assuming they're used-only.

## Important checks specific to the Canary Islands

- Canarias is outside the EU VAT area — sales here carry **IGIC**, not IVA.
  A locally-sold unit (new or used) is already priced/taxed for the local
  market; there is no import/export step to reason about for an in-islands
  purchase. Just note whether the advertised price includes IGIC, and
  whether the seller is a particular or concesionario oficial.
- Inter-island shipping (e.g. a unit listed in Tenerife the family would view
  from Gran Canaria) is a same-territory ferry hop, not a real cost factor —
  don't penalize a candidate for being on a different island than the
  family's.
- A listing that requires shipping the vehicle in from mainland Spain or
  elsewhere in Europe is out of scope for this search — the point of the
  2026-07-30 refocus is units already in the Canary Islands.
