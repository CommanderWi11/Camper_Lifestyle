# Motorhome Lifestyle

**Top 5** de hoy — autocaravanas **nuevas y de segunda mano** en venta en
**toda Europa** para una familia de 4 (2 adultos + 2 peques), buscadas y
valoradas a diario.

**Dashboard:** https://commanderwi11.github.io/Motorhome_Search/

Cada día a las 03:00 el pipeline busca en todas las fuentes, investiga a fondo los
candidatos serios, y publica las 5 mejores **de hoy**. No hay archivo por semanas: un
ganador que deja de estar en el Top 5 desaparece, salvo que esté marcado como
favorito ★ — en ese caso se queda en la sección de Favoritos aunque ya no gane.

## Cómo funciona

| Etapa | Qué hace | Salida |
|---|---|---|
| **A · Harvest** (`scripts/harvest.py`) | Rastrea Milanuncios y Coches.net a nivel nacional (España). Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca de forma extensiva por toda Europa (nuevas y de segunda mano), compara con el mercado real, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
| **C · Validación** (`scripts/apply_winners.py`) | Comprueba la salida y la integra en el tablero (Top 5 + Favoritos). Si algo no cuadra, **no publica**. | `docs/listings.json` |
| **D · Publicación** | `git push` → GitHub Pages en ~60s. | |

Orquestado por `scripts/weekly-search.sh`, programado con
`launchd/com.openbob.motorhome-search-daily.plist`.

## La rúbrica

Familia de 4 (2 adultos, un niño de 2,5 años y un bebé de 3 meses). Búsqueda
**por toda Europa** (2026-08-11: restaurada tras un breve paréntesis
Canarias-only) — **nuevas (0km/concesionario) y de segunda mano por igual**.

Filtros innegociables: MMA ≤3.500 kg (carnet B), **longitud ≥ 6,90 m**, camas gemelas
traseras convertibles en doble vía kit de fábrica, **volante a la izquierda**, ≥4
plazas homologadas con cinturón de 3 puntos. El baño separado y la 4ª/5ª plaza
infantil son preferencias fuertes, no filtros.

Rúbrica completa: `scripts/research-prompt.md`.

## Fuentes

**Deterministas (Stage A)** — Milanuncios y Coches.net, vía Playwright (con
anti-bot en Coches.net), a nivel nacional (España).

**Europa, en vivo (Stage B)** — el resto de portales europeos (mobile.de,
AutoScout24, leboncoin, Marktplaats, Subito, Autocasion...) más búsqueda activa
de concesionarios de vehículos nuevos por país. Sin scraper dedicado todavía —
lista completa en `Resources/europe-motorhome-selling-sites.md`.

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

**Horario:** el agente se dispara una vez al día, a las 03:00 (2026-07-30: antes
eran 07:00 + reintentos a las 13:00/19:00; ahora solo hay un intento — si falla,
no hay tablero nuevo hasta el 03:00 del día siguiente).

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
