#!/usr/bin/env python3
"""Ingest a manually-researched Top 5 shortlist into docs/history.json.

Luis periodically runs a deep, multi-portal search by hand (or via a separate
Claude session doing live WebFetch/browser research) covering sites the
automated harvester can't reach — mobile.de, AutoScout24, leboncoin,
Marktplaats, Subito, etc. He pastes the result as a markdown table; this
script is where that gets transcribed into structured data and folded into
the dashboard's "history" view.

This is a SEPARATE, additive concept from docs/listings.json's Top 5 +
Favorites model — it does not touch listings.json, board.py, or the daily
automated pipeline at all. history.json is just a per-date archive of these
manual research snapshots, shown on the dashboard below the automated
Top 5 + Favorites. See docs/app.js's history rendering and CLAUDE.md.

Usage: edit SHORTLISTS below with the next dated batch (title/price/km/
location/length_m per entry, transcribed by hand from the pasted markdown —
some of Luis's pasted tables arrive with OCR/copy corruption in cells and
URLs; cross-reference against other dates' mentions of the same listing
before trusting a truncated cell), then run this file. Re-running for a date
already in history.json replaces that date's entries (idempotent).
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from harvest import make_id, fetch_og_image  # noqa: E402

HISTORY_FILE = Path(__file__).parent.parent / "docs" / "history.json"

# 2026-07-24 / 07-25 / 07-27 / 07-28: dated Top-5 shortlists pasted by Luis,
# transcribed here. Rows carried over unchanged across dates (Dethleffs Just Go
# T7055 EB in all four; Etrusco T7400 SBC, Sunlight T680, McLouis MC4 865 and
# Rapido 666F unchanged 07-27->07-28) reuse the exact same URL each time, on
# purpose -- make_id() then produces the same id, so starring/deleting one
# instance collapses across every date.
SHORTLISTS = {
    "2026-07-24": [
        {
            "url": "https://www.camperonline.it/camper-usati/semintegrale-c-i-horon-87-xt_195896",
            "title": "C.I. Horon 87 XT (2025, casi nueva) - ducha separada, litera abatible",
            "price": 64900, "km": 7350, "location": "Monza (MB), Italia", "length_m": 7.45,
        },
        {
            "url": "https://www.caravanmarket.com/camper-mclouis-mc4-373",
            "title": "McLouis MC4 373 (2026, nueva) - 5 plazas homologadas, litera abatible",
            "price": 70580, "km": 0, "location": "Castel San Pietro Terme (BO), Italia", "length_m": 7.45,
        },
        {
            "url": "https://www.trovocamper.it/tessoro-t-463-letti-gemelli-5-posti-annuncio-263710",
            "title": "Benimar Tessoro T463 (2026, nueva) - 5 plazas, 5 literas",
            "price": 64900, "km": 0, "location": "Spinea (VE), Italia", "length_m": 7.43,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - camas gemelas + kit de relleno, automatica",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/lmc-tourer-t-660-g/367233.html",
            "title": "LMC Tourer T 660 G (2025, practicamente nueva) - la mas manejable, bano separado",
            "price": 69900, "km": 10, "location": "Moulay (53), Francia", "length_m": 6.99,
        },
    ],
    "2026-07-25": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - todo confirmado en el anuncio + litera electrica extra",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - 5 plazas homologadas, bano separado",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - camas gemelas + kit de relleno, automatica",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/adria-matrix-plus-670-dl/394781.html",
            "title": "Adria Matrix Plus 670 DL (2021) - la mas espaciosa, bano separado",
            "price": 62350, "km": 27893, "location": "Niort (79), Francia", "length_m": 7.49,
        },
        {
            "url": "https://www.caravan-wendt.de/de/fahrzeuge/carado-t-328-5-personenautomatikvoll-led-scheinwerfer-5f167.html",
            "title": "Carado T 328 (2026, ex-alquiler) - 5 plazas, bano separado, bajada de precio",
            "price": 69555, "km": 32000, "location": "Kremmin, Alemania", "length_m": 6.98,
        },
    ],
    "2026-07-27": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio 4 semanas seguidas",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "McLouis MC4 865 (2026) - 5 plazas confirmadas, la mas barata bien equipada",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - tercera semana sin cambios de precio",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - mejor encaje familiar, sin cambios",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.milanuncios.com/autocaravanas-de-segunda-mano/autocaravana-perfilada-rapido-666f-cam-527648454.htm",
            "title": "Rapido 666F (2025) - primer concesionario espanol encontrado en 3 semanas",
            "price": 81471, "km": None, "location": "Irun, Gipuzkoa, Espana", "length_m": 7.49,
        },
    ],
    "2026-07-28": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio 5 semanas seguidas",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "McLouis MC4 865 (2026) - la mas barata bien equipada, sin cambios",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - cuarta semana sin cambios de precio",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - mejor encaje familiar, sin cambios",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.milanuncios.com/autocaravanas-de-segunda-mano/autocaravana-perfilada-rapido-666f-cam-527648454.htm",
            "title": "Rapido 666F (2025) - unico concesionario espanol encontrado, sin cambios",
            "price": 81471, "km": None, "location": "Irun, Gipuzkoa, Espana", "length_m": 7.49,
        },
    ],
    "2026-07-31": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio, sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "McLouis MC4 865 (2026) - sin cambios, posible alquiler desde octubre (a confirmar con el concesionario)",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - sin cambios, relleno de camas aun por confirmar",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - 5 plazas, bano separado, sin cambios",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.milanuncios.com/autocaravanas-de-segunda-mano/autocaravana-perfilada-rapido-666f-cam-527648454.htm",
            "title": "Rapido 666F 65 anos (2025) - bano separado ahora confirmado por escrito, la mas cara",
            "price": 81471, "km": None, "location": "Irun, Gipuzkoa, Espana", "length_m": 7.49,
        },
    ],
    # 2026-08-01: Luis-pasted Canary Islands shortlist (RentCamper Canarias +
    # Voyenvan stock), with his own purchasing-order ranking folded into each
    # title. Two of his pasted URLs 404'd on verification (merged/corrupted
    # text, same class of paste corruption flagged in this file's docstring) --
    # corrected against the live sites before trusting them:
    #   Challenger 317: "...canariasllenger-317/" -> voyenvan.com/autocaravanas_challenger_canarias/autocaravana-challenger-317/
    #   Benimar T463:   ".../fichimar-tessoro-463-/07287" -> .../ficha-autocaravana/benimar-tessoro-463-/07287
    "2026-08-01": [
        {
            "url": "https://voyenvan.com/autocaravanas_challenger_canarias/autocaravana-challenger-317/",
            "title": "#1 Challenger 317 (2026, nueva) - perfilada ~7,36-7,39m, camas gemelas 90cm, precio a consultar - la mejor opcion nueva SI el concesionario confirma <=75.000EUR todo incluido",
            "price": None, "km": 0, "location": "Tenerife", "length_m": 7.37,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/benimar-mileo-261/826td",
            "title": "#2 Benimar Mileo M261 - RESERVADA/en transporte - 75.850EUR, Fiat 140cv, la mejor calidad del lote - ofrecer 75.000EUR todo incluido para la proxima unidad",
            "price": 75850, "km": None, "location": "Canarias (RentCamper)", "length_m": 6.99,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/benimar-463up/210ge",
            "title": "#3 Benimar Tessoro T463 UP - RESERVADA - 68.999EUR, Ford 165cv, solar 200W - pedir que repitan el precio en la proxima unidad",
            "price": 68999, "km": None, "location": "Tenerife", "length_m": 7.45,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/itineo-pj700-5-plazas-camas-separadas/944ud",
            "title": "#4 Itineo PJ700 - DISPONIBLE - 60.850EUR, perfilada 6,99m, camas gemelares, matriculada ago-2024 (pocos km, no 0km) - mejor relacion calidad-precio confirmada hoy, pendiente inspeccion independiente de humedad/peso/garantia",
            "price": 60850, "km": None, "location": "Fuerteventura", "length_m": 6.99,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/benimar-tessoro-463-/07287",
            "title": "Benimar Tessoro T463 - VENDIDA - 71.380EUR, Ford 165cv, solar 400W - referencia de precio para negociar la proxima unidad identica",
            "price": 71380, "km": None, "location": "Gran Canaria", "length_m": 7.43,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/giottiline-compact-cx66-camas-gemelas/987lt",
            "title": "Giottiline Compact CX66 - en transporte - 69.750EUR - NO reservar hasta que el concesionario confirme longitud >=6,99m por ficha COC",
            "price": 69750, "km": None, "location": "Canarias (en transporte)", "length_m": None,
        },
        {
            "url": "https://www.rentcampercanarias.com/ficha-autocaravana/giottiline-485/839lr",
            "title": "Giottiline 485 - 69.500EUR, Tenerife - cumple longitud y camas gemelas pero es capuchina, no perfilada (tipo de carroceria no preferido)",
            "price": 69500, "km": None, "location": "Tenerife", "length_m": 6.99,
        },
    ],
    # 2026-08-03: Luis-pasted daily re-check + fresh round, Top 5 only (the
    # report's Held/Weaker-leads/Rejected tiers are context, not board cards --
    # matches the per-date Top-5-table pattern this file has followed since
    # 2026-07-24). Two promotions today: Chausson 627 Titanium and Benimar
    # Mileo M263 in; Sunlight T 680 and Rapido 666F dropped to held (not
    # re-added here since only Top 5 is ingested). One URL arrived corrupted,
    # same paste-corruption class flagged in this file's docstring -- fixed
    # against the previously-verified-working URL already on file:
    #   Dethleffs Just Go: "...mobilh702399-dethleffs..." -> .../mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat
    "2026-08-03": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio, sin debilidad identificada, sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#2 McLouis MC4 865 (2026) - sin cambios, restriccion de flota de alquiler persiste (disponible octubre, reservable ya), bano combinado",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#3 Dethleffs Just Go T 7055 EB (2023) - sin cambios, inclusion del kit de relleno en la venta aun por confirmar con el vendedor",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#4 PROMOVIDA HOY Chausson 627 Titanium (2026, ex-demo) - 6,99m y 3.500kg confirmados hoy, 5 plazas, kit a cama king confirmado - bano combinado, km de entrega incierto (12.000-25.000km segun el concesionario)",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
        {
            "url": "https://www.autocaravanasnorte.com/vehiculos-detalle/benimar-mileo-mileo-263-192452/",
            "title": "#5 NUEVA Benimar Mileo M263 (2023) - cumple todos los requisitos duros Y ambas preferencias fuertes (bano separado + 4a/5a plaza), confirmado con ficha de fabricante - la mas cara del top 5 (72.490EUR financiado / 78.990EUR al contado, aclarar con el concesionario)",
            "price": 72490, "km": 29292, "location": "Campillos, Malaga, Espana", "length_m": 7.39,
        },
    ],
    # Manually starred by Luis on 2026-08-04, found on RentCamper Canarias directly
    # (not via a Stage B research pass). Confirmed live on the vehicle's own page:
    # 6.61m, well under the 6.90m hard length gate, and the rear layout is factory
    # bunk beds (literas) with two configurations (twin singles w/ games table, or
    # bunk-over-fixed-double) -- not the twin-beds-convertible-via-infill-kit layout
    # the rubric requires. Flagged INCUMPLE in the title since it fails 2 hard gates;
    # starred anyway per explicit request.
    "2026-08-04": [
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/itineo-cs660-/0990mhw",
            "title": "Itineo CS660 Integral 5pl (2023) - INCUMPLE longitud minima (6.61m < 6.90m) e INCUMPLE camas traseras (literas, no cama doble con kit de relleno) - bano DUO'SPACE",
            "price": 59900, "km": 32575, "location": "Fuerteventura, Espana", "length_m": 6.61,
        },
        # Found via a full-site scan of mundoautocaravanas.com (Tenerife dealer),
        # requested by Luis after the RentCamper Canarias check above. Same model
        # already vetted in the 2026-08-03 manual research (Italy, blocked by a
        # rental-fleet restriction) -- this unit is NEW (0km, temporada 2026) and
        # already in the Canaries. MMA 3.500kg confirmed via McLouis's own spec
        # sheet (not on the dealer page). One gap: neither the dealer listing nor
        # the manufacturer spec confirms the rear twin beds join into a double via
        # a factory infill kit -- needs confirming with the dealer, same open item
        # as the Chausson 627 Titanium on 2026-08-03.
        {
            "url": "https://mundoautocaravanas.com/producto/fiat-ducato-2-2-td-mclouis-mc4-865-temporada-2026/",
            "title": "McLouis MC4 865 (2025, 0km, temporada 2026) - NUEVO y ya en Canarias, mismo modelo validado en investigacion manual del 03 ago (Italia, con restriccion de flota de alquiler) - MMA 3.500kg confirmado (ficha fabricante) - kit de relleno a cama doble SIN CONFIRMAR con el concesionario",
            "price": 77900, "km": 0, "location": "Tenerife, Espana", "length_m": 6.99,
        },
    ],
    # 2026-08-05 -> 2026-08-11: Luis-pasted daily deep-research Top 5, ingested
    # as a full 7-day batch on 2026-08-11 from a combined export. The Top 5
    # itself barely moved all week (only change: Benimar Sport 363 promoted in
    # at #2 on 08-05 after its MAM blocker resolved, replacing the delisted
    # Benimar Mileo M263) -- same carry-forward-by-URL pattern as 07-27->07-31.
    # Per Luis's request, the 08-11 snapshot also folds in the strongest
    # "potential but not 100% confirmed" open items/held leads from that week's
    # reports (Sunlight Adventure T68C, both Bürstner Lyseo TD 728 leads,
    # Etrusco T6900 SB Girona, Rimor Seal 695) -- flagged as such in their
    # titles since none has passed full unit-level verification yet.
    "2026-08-05": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio, sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 PROMOVIDA HOY Benimar Sport 363 (2020) - bloqueo de MMA resuelto (3.500kg confirmado por ficha de fabricante, longitud 7.43m exacta) - ya en Gran Canaria, sin coste de transporte - ducha separada confirmada, WC separado sin confirmar",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - sin cambios, restriccion de flota de alquiler persiste (disponible octubre, reservable ya), bano combinado",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios, inclusion del kit de relleno aun por confirmar con el vendedor",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios, km de entrega incierto (12.000-25.000km segun el concesionario)",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-06": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - sin cambios",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-07": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - NO reverificada hoy (5 intentos fallidos, timeouts/403 en mirror) - datos del 06 ago, pendiente revision manual",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios, ventana de entrega septiembre-octubre 2026",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-08": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - NO reverificada hoy, ahora 8 intentos fallidos seguidos (bloqueo tipo robots.txt) - datos del 06 ago",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-09": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria - posible alternativa mas barata en Tenerife bajo verificacion (ver Burstner Lyseo TD 728 Privilege en items abiertos)",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - cargo correctamente hoy via WebFetch por primera vez tras 8 fallos seguidos - tratar como reconfirmado provisionalmente",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-10": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - segundo exito seguido via WebFetch, tendencia a estable",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios, entrega inmediata (sofort)",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
    ],
    "2026-08-11": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "#1 Etrusco T 7400 SBC (2023) - sin cambios, dia limpio sin bloqueos de scraping en todo el lote",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.rentcampercanarias.com/autocaravana-ocasion/benimar-363/142fb",
            "title": "#2 Benimar Sport 363 (2020) - sin cambios, ya en Gran Canaria, EN STOCK",
            "price": 61000, "km": 14000, "location": "Gran Canaria, Espana", "length_m": 7.43,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "#3 McLouis MC4 865 (2026) - tercer exito seguido via WebFetch, bloqueo de robots.txt parece resuelto",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "#4 Dethleffs Just Go T 7055 EB (2023) - sin cambios",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://ms-reisemobile.de/fahrzeug/chausson-627-titanium-2026-165ps-8g-einzelbetten/",
            "title": "#5 Chausson 627 Titanium (2026, ex-demo) - sin cambios",
            "price": 63778, "km": 12000, "location": "Munster, Alemania", "length_m": 6.99,
        },
        # --- Leads abiertos / POTENCIALES, NO confirmados al 100% (a peticion
        # de Luis) -- ninguno ha pasado verificacion completa a nivel de unidad.
        {
            "url": "https://www.leboncoin.fr/ad/caravaning/3140406512",
            "title": "POTENCIAL, NO CONFIRMADO - Sunlight Adventure T68C (2026, nuevo) - encaje de ficha de fabricante perfecto en todos los requisitos duros + ambas preferencias fuertes (bano separado, 4a/5a plaza abatible) - anuncio de Leboncoin bloqueado para fetch directo, sin verificar a nivel de unidad ni opciones instaladas",
            "price": 72330, "km": 1, "location": "Luc-la-Primaube, Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.coches.net/burstner-lyseo-td-728-privilege---lyseo-en-sta_c_tenerife-52241550-arvo.aspx",
            "title": "POTENCIAL, NO CONFIRMADO - Burstner Lyseo TD 728 Privilege - ya en Tenerife (sin transporte), seria la mas barata del Top 5 si se confirma - coches.net/milanuncios bloquean el fetch automatico desde hace 5 dias seguidos - kilometraje/ano/tipo de vendedor sin confirmar, requiere revision manual o llamada directa",
            "price": 58500, "km": None, "location": "Santa Cruz de Tenerife, Espana", "length_m": 7.49,
        },
        {
            "url": "https://www.autoscout24.de/haendler/caravan-center-suna",
            "title": "POTENCIAL, NO CONFIRMADO - Burstner Lyseo TD 728 G Harmony (2020) - datos cruzados y confirmados via mobile.de y AutoScout24 (63.990EUR, 68.213km, matriculado 05/2020) pero SIN enlace directo a la ficha tras 6 intentos (portal renderiza el permalink via JS) - enlace es la pagina del concesionario, no la ficha individual - requiere clic manual",
            "price": 63990, "km": 68213, "location": "Mulheim an der Ruhr, Alemania", "length_m": 7.49,
        },
        {
            "url": "https://www.coches.net/-autocaravana-etrusco-t6900-sb-abril-2023-en-girona-56800770-arvo.aspx",
            "title": "POTENCIAL, NO CONFIRMADO - Etrusco T6900 SB - MMA 3.499kg confirmado por ficha de fabricante, longitud y plazas ok, pero bano es wet-room COMBINADO (no separado) - compromiso, no encaje limpio",
            "price": 73500, "km": None, "location": "Girona, Espana", "length_m": 7.0,
        },
        {
            "url": "https://www.trovocamper.it/rimor-seal-695-mansardato-letti-gemelli-e-garage-ampio-annuncio-254379",
            "title": "POTENCIAL, NO CONFIRMADO - Rimor Seal 695 mansardato - MMA 3.500kg confirmado via review independiente de CamperOnLine (no la ficha del fabricante, que estaba de pago), bano integrado en la zona de cama (wet-room, compromiso) - precio por debajo de todo el Top 5 actual, plazas homologadas a confirmar (anuncio dice 6 asientos, ambiguo)",
            "price": 54000, "km": None, "location": "Anzola dell'Emilia (Bologna), Italia", "length_m": 7.35,
        },
    ],
}


def source_from_url(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").replace(".", "_")


def build_entry(raw: dict, photo_cache: dict) -> dict:
    url = raw["url"]
    source = source_from_url(url)
    if url not in photo_cache:
        photo_cache[url] = fetch_og_image(url)
    return {
        "id": make_id(source, url),
        "url": url,
        "source": source,
        "title": raw["title"],
        "price": raw["price"],
        "km": raw.get("km"),
        "location": raw["location"],
        "photo": photo_cache[url],
        "specs": {"length_m": raw["length_m"]},
    }


def main():
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    by_date = {h["date"]: h for h in history}
    photo_cache = {}

    for date, raw_entries in SHORTLISTS.items():
        entries = [build_entry(r, photo_cache) for r in raw_entries]
        by_date[date] = {"date": date, "entries": entries}
        print(f"{date}: {len(entries)} entries "
              f"({sum(1 for e in entries if e['photo'])} with photo)")

    history = sorted(by_date.values(), key=lambda h: h["date"], reverse=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {HISTORY_FILE}")


if __name__ == "__main__":
    main()
