#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔍 Buscando nuevos anuncios..."
source .venv/bin/activate
python3 scripts/search.py

echo "📤 Subiendo resultados..."
git add docs/listings.json
git diff --cached --quiet && echo "Sin novedades." || (
  git commit -m "chore: listings update $(date +%Y-%m-%d)" &&
  git push &&
  echo "✅ Dashboard actualizado."
)
