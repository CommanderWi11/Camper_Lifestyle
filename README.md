# Motorhome Lifestyle

**Top 5** semanal de integrales y perfiladas en Canarias, para una familia de 4 con dos
peques — refrescado a diario.

**Dashboard:** https://commanderwi11.github.io/Motorhome_Search/

Cada día a las 07:00 el pipeline busca en todas las fuentes, investiga a fondo los
candidatos serios, y actualiza las 5 mejores **de esta semana**. El tablero sigue
organizado por semana (una posición por semana ISO): el run diario simplemente lo
mantiene fresco en vez de fijarlo el lunes y no tocarlo hasta el siguiente. Las que
quedan desplazadas no desaparecen: bajan a la sección de su semana, y siguen ahí si
haces scroll.

## Cómo funciona

| Etapa | Qué hace | Salida |
|---|---|---|
| **A · Harvest** (`scripts/harvest.py`) | Rastrea todas las fuentes. Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca fallos conocidos y humedades, compara con el precio real de mercado, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
| **C · Validación** (`scripts/apply_winners.py`) | Comprueba la salida y la integra en el tablero. Si algo no cuadra, **no publica**. | `docs/listings.json` |
| **D · Publicación** | `git push` → GitHub Pages en ~60s. | |

Orquestado por `scripts/weekly-search.sh`, programado con
`launchd/com.openbob.motorhome-search-daily.plist`.

## La rúbrica

Familia de 4, dos niños pequeños. Filtros innegociables: **≥4 plazas de viaje con
cinturón de 3 puntos** (el dato que descarta a la mayoría de perfiladas baratas — las
sillitas infantiles lo necesitan), ≥4 plazas para dormir, baño con ducha, ≤3.500 kg
(carnet B), en Canarias, integral o perfilada.

Después se puntúa: habitabilidad familiar (40% — las **literas traseras** son oro; una
cama que hay que montar cada noche con dos peques dormidos es un defecto serio),
relación calidad-precio (35%), estado y riesgo (15% — las **humedades** son el asesino
número uno de una autocaravana usada), y practicidad canaria (10% — ≤7 m por las
carreteras y los ferries).

Rúbrica completa: `scripts/research-prompt.md`.

## Fuentes

**JSON APIs** (sólidas): Autocaravanas DM (Shopify), Mundo Autocaravanas (WooCommerce).
**Playwright** (con anti-bot): Milanuncios, Coches.net, Wallapop.
**HTML estático**: Campermax, caravanas.net.
**Vía `claude -p` + WebFetch** (markup hostil, se leen como texto): **RentCamper
Canarias** y Autocaravanas Canarias — flotas de alquiler que venden su stock. RentCamper
es la mejor fuente familiar de Canarias (literas para niños) y aportó **3 de las 5
ganadoras** de la primera semana.

**Callejones sin salida ya comprobados** (no los reimplementes): `autocasion.com` y
`autoscout24.es` ignoran silenciosamente el filtro de provincia y devuelven resultados
de la península. `coches.com` no tiene categoría de autocaravanas.

El mercado canario es diminuto — **35-45 unidades en todo el archipiélago**. Algunas
semanas habrá menos de 5 que merezcan la pena, y el pipeline devolverá 3 antes que
rellenar con basura.

## Uso

```bash
# Lanzar la búsqueda ahora (idempotente por día natural, no por semana)
launchctl kickstart -k gui/$(id -u)/com.openbob.motorhome-search-daily
tail -f ~/Library/Logs/motorhome-daily.log

# Descartar una autocaravana (no volverá a aparecer NI a buscarse)
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

Corre en el Mac a propósito: **GitHub Actions tiene la IP bloqueada** por estas webs (el
antiguo `weekly-search.yml` tenía un cron los lunes y no produjo ni un solo anuncio en su
vida; está borrado). Si el Mac está dormido a las 07:00, launchd lo ejecuta al despertar.

**Reintentos:** el agente se dispara todos los días a las 07:00, 13:00 y 19:00 (antes solo
los lunes; cambiado a diario el 2026-07-21). Solo se escribe `.state/<fecha>.done` cuando
la publicación ha salido bien, así que si el run de las 07:00 funciona, los otros dos salen
inmediatamente sin hacer nada. Si falla (límite de sesión de Claude, web caída, sin red al
despertar), hay dos oportunidades más el mismo día en vez de quedarse sin tablero fresco.

## Estado conocido

- **Supabase está caído** — el proyecto fue borrado (NXDOMAIN). La web usa localStorage
  como respaldo y la búsqueda diaria lee `scripts/blocklist.json`, así que nada está
  roto, pero no sincroniza entre dispositivos. Para restaurarlo: `docs/supabase-setup.sql`.
- **Wallapop devuelve 0** — cambiaron el DOM de búsqueda. El harvester lo avisa en el log
  (`<-- ZERO, check selectors`). Aportaba 1 anuncio; las fuentes nuevas aportan 48.
