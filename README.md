# Home Quest QH

**Top 5** de hoy — viviendas en venta para la familia de Luis, buscadas y
valoradas a diario. Presupuesto **≤500.000€**, **≥3 dormitorios**, **jardín
privado** (no vale acceso a uno comunitario). Zona principal: **Tafira**
(Las Palmas de Gran Canaria), con barrios
cercanos de Las Palmas de Gran Canaria como alternativa solo si Tafira sola no da
suficientes candidatos — y siempre marcados claramente como fuera de Tafira, nunca
mezclados como si fueran de la zona principal.

**Dashboard:** https://commanderwi11.github.io/Home_Quest_QH/

Cada día a las 03:00 el pipeline busca, investiga a fondo los candidatos serios, y
publica las 5 mejores **de hoy**. No hay archivo por semanas: un ganador que deja
de estar en el Top 5 desaparece, salvo que esté marcado como favorito ★ — en ese
caso se queda en la sección de Favoritos aunque ya no gane.

## Cómo funciona

| Etapa | Qué hace | Salida |
|---|---|---|
| **A · Harvest** (`scripts/harvest.py`) | Rastrea Idealista.es. Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca de forma extensiva en Fotocasa/pisos.com, compara con el mercado real, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
| **C · Validación** (`scripts/apply_winners.py`) | Comprueba la salida y la integra en el tablero (Top 5 + Favoritos). Si algo no cuadra, **no publica**. | `docs/listings.json` |
| **D · Publicación** | `git push` → GitHub Pages en ~60s. | |

Orquestado por `scripts/weekly-search.sh`, programado con
`launchd/com.openbob.home-quest-qh-daily.plist`.

## La rúbrica

Filtros innegociables: precio **≤500.000€**, **≥3 dormitorios**, **jardín
privado**. Preferencias (no filtros): **Tafira** gana a una zona
alternativa (marcada como tal); a partir de ahí, se ordena por valor global —
**sin puntuación porcentual inventada**, se clasifica de forma cualitativa, sin
inventar una fórmula ponderada.

Rúbrica completa: `scripts/research-prompt.md`.

## Fuentes

**Determinista (Stage A)** — Idealista, vía Playwright con sesión de Chrome ya
autenticada (Idealista tiene protección anti-bot fuerte).

**En vivo (Stage B)** — Fotocasa y pisos.com como fuentes secundarias, más
cualquier listado directo relevante. Lista completa en
`Resources/property-portals.md` — mucho más corta que la antigua lista de 60+
portales europeos, porque esta es una búsqueda de un solo país con un portal
principal, no un mercado paneuropeo fragmentado.

## Uso

```bash
# Lanzar la búsqueda ahora (idempotente por día natural)
launchctl kickstart -k gui/$(id -u)/com.openbob.home-quest-qh-daily
tail -f ~/Library/Logs/home-quest-qh-daily.log

# Eliminar una vivienda (no volverá a aparecer NI a buscarse)
./scripts/discard.py <listing-id>
./scripts/discard.py --list

# Tests
.venv/bin/python3 -m pytest tests/ -q
```

## Instalación del schedule

```bash
ln -sf "$PWD/launchd/com.openbob.home-quest-qh-daily.plist" ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.openbob.home-quest-qh-daily.plist
```

Corre en el Mac a propósito: **GitHub Actions tiene la IP bloqueada** por estas webs.

**Horario:** el agente se dispara una vez al día, a las 03:00 — un solo intento,
sin reintentos; si falla, no hay tablero nuevo hasta el 03:00 del día siguiente.

## Búsquedas manuales (historial)

Debajo de Top 5 + Favoritos, el dashboard muestra una sección por cada búsqueda
manual pegada por Luis (Fotocasa, pisos.com, o anuncios directos que el harvester
automático no puede leer). Vive en `docs/history.json`, generado por
`scripts/ingest_manual_shortlist.py` — no toca `listings.json` ni el pipeline
diario, es un archivo aparte y aditivo.

## Estado

Ver `MEMORY.md` para el estado y las decisiones actuales del proyecto.
