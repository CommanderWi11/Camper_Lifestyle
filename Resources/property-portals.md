# Portales inmobiliarios — Gran Canaria

Lista corta a propósito: a diferencia del mercado europeo de autocaravanas (muy
fragmentado, decenas de sitios nacionales), el mercado inmobiliario español está
concentrado en un puñado de portales grandes. No hace falta una tabla de 160
líneas.

## Orden de recorrido para Stage B

1. **[Idealista.es](https://www.idealista.com/)** — portal principal. Stage A
   (`harvest.py`) ya lo recorre de forma determinista (búsqueda de venta en
   Tafira/Las Palmas de Gran Canaria, filtrada por precio y dormitorios) y entrega
   esos candidatos en `candidates.json`. Aun así, Stage B debe poder navegarlo
   también en vivo: el harvester filtra por facetas estructuradas, y algunos
   anuncios mencionan el jardín (o la zona de despacho) solo en el texto libre,
   no en las facetas — esos se le escapan a Stage A pero no deberían escapársele
   a Stage B.
2. **[Fotocasa.es](https://www.fotocasa.es/)** — búsqueda en vivo, sin scraper
   propio. Cúbrelo con la misma profundidad que Idealista.
3. **[pisos.com](https://www.pisos.com/)** — búsqueda en vivo, sin scraper
   propio. Cúbrelo igual.

No hay más portales en esta lista. Si en el futuro se añade uno nuevo, añádelo
aquí — no lo metas inline en `research-prompt.md`.

## Cómo buscar en cada uno

- Alcance: **venta**, nunca alquiler.
- Provincia: **Las Palmas** (Gran Canaria) — no busques en otras islas ni en la
  península.
- Prioriza el filtro/palabra clave de **Tafira** donde el portal lo soporte
  (Idealista y Fotocasa tienen filtro de zona/barrio dentro de Las Palmas de
  Gran Canaria; pisos.com puede requerir la palabra "Tafira" en la búsqueda
  libre en vez de un filtro dedicado — compruébalo en cada ejecución, no lo
  asumas).
- Si la búsqueda acotada a Tafira da pocos resultados que superen los
  requisitos innegociables, amplía a una búsqueda más general de Las Palmas de
  Gran Canaria — pero cualquier resultado que venga de esa ampliación, y que no
  esté realmente en Tafira, se marca `is_target_area: false` en la salida (ver
  `research-prompt.md`). Nunca lo presentes como si fuera Tafira.
