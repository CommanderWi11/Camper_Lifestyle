# Motorhome Lifestyle

**Top 5** de hoy — autocaravanas en venta por toda Europa para una familia de 4 (2
adultos + 2 peques), buscadas y valoradas a diario.

**Dashboard:** https://commanderwi11.github.io/Motorhome_Search/

Cada día a las 07:00 el pipeline busca en todas las fuentes, investiga a fondo los
candidatos serios, y publica las 5 mejores **de hoy**. No hay archivo por semanas: un
ganador que deja de estar en el Top 5 desaparece, salvo que esté marcado como
favorito ★ — en ese caso se queda en la sección de Favoritos aunque ya no gane.

## Cómo funciona

| Etapa | Qué hace | Salida |
|---|---|---|
| **A · Harvest** (`scripts/harvest.py`) | Rastrea Milanuncios y Coches.net (España, nacional). Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca por toda Europa (mobile.de, AutoScout24, leboncoin, Subito.it, etc.), compara con el mercado real, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
| **C · Validación** (`scripts/apply_winners.py`) | Comprueba la salida y la integra en el tablero (Top 5 + Favoritos). Si algo no cuadra, **no publica**. | `docs/listings.json` |
| **D · Publicación** | `git push` → GitHub Pages en ~60s. | |

Orquestado por `scripts/weekly-search.sh`, programado con
`launchd/com.openbob.motorhome-search-daily.plist`.

## La rúbrica

Familia de 4 (2 adultos, un niño de 2,5 años y un bebé de 3 meses). Búsqueda por toda
Europa — la vuelta hasta el sur de España es un viaje por carretera que la familia
hace por gusto, así que solo el ferry a Canarias cuenta como coste real de logística.

Filtros innegociables: MMA ≤3.500 kg (carnet B), **longitud ≥ 6,90 m**, camas gemelas
traseras convertibles en doble vía kit de fábrica, **volante a la izquierda**, ≥4
plazas homologadas con cinturón de 3 puntos. El baño separado y la 4ª/5ª plaza
infantil son preferencias fuertes, no filtros.

Rúbrica completa: `scripts/research-prompt.md`.

## Fuentes

Exactamente las que pide el encargo (`scripts/research-prompt.md` §5) — nada más.
2026-07-26: se eliminaron 5 fuentes (Wallapop, Autocaravanas DM, Mundo
Autocaravanas, Campermax, caravanas.net) y 2 fetches obligatorios en Stage B
(RentCamper Canarias, Autocaravanas Canarias) — ninguna estaba en el encargo; eran
herencia de un proyecto anterior, solo-Canarias, ajeno a este.

**Deterministas (Stage A)** — Milanuncios y Coches.net, vía Playwright (con
anti-bot en Coches.net), a nivel nacional (no solo Canarias).

**Europa (Stage B, en vivo)** — mobile.de, AutoScout24 (DE/AT/NL/BE), Marktplaats,
leboncoin, La Centrale, Subito.it, CamperOnLine, Autocasion, OLX (PL/PT), páginas de
stock de fabricantes. Sin scraper dedicado todavía — es la fase 2 pendiente (ver
`scripts/harvest.py`, docstring del módulo).

## Uso

```bash
# Lanzar la búsqueda ahora (idempotente por día natural)
launchctl kickstart -k gui/$(id -u)/com.openbob.motorhome-search-daily
tail -f ~/Library/Logs/motorhome-daily.log

# Eliminar una autocaravana (no volverá a aparecer NI a buscarse)
./scripts/discard.py <listing-id>
./scripts/discard.py --list

# Tests
.venv/bin/python3 -m pytest tests/ -q
```

## Instalación del schedule

```bash
ln -sf "$PWD/launchd/com.openbob.motorhome-search-daily.plist" ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.openbob.motorhome-search-daily.plist
```

Corre en el Mac a propósito: **GitHub Actions tiene la IP bloqueada** por estas webs.

**Reintentos:** el agente se dispara todos los días a las 07:00, 13:00 y 19:00. Solo se
escribe `.state/<fecha>.done` cuando la publicación ha salido bien, así que si el run
de las 07:00 funciona, los otros dos salen inmediatamente sin hacer nada.

## Búsquedas manuales (historial)

Debajo de Top 5 + Favoritos, el dashboard muestra una sección por cada búsqueda
manual pegada por Luis (portales que el harvester automático no puede leer:
mobile.de, AutoScout24, leboncoin, Marktplaats, Subito, sitios de
concesionarios individuales...). Vive en `docs/history.json`, generado por
`scripts/ingest_manual_shortlist.py` — no toca `listings.json` ni el pipeline
diario, es un archivo aparte y aditivo.

## Estado conocido

- **Supabase** — ver `docs/supabase-setup.sql` para el schema (`camper_stars`,
  `camper_hidden`; `camper_comments`/`camper_status` siguen en el schema pero ya no
  los usa el dashboard). Sin conexión, la web usa localStorage y `harvest.py` lee
  `scripts/blocklist.json`, así que nada se rompe — solo deja de sincronizar entre
  dispositivos.
