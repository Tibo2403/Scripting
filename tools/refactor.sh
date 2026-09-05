#!/bin/bash
set -e

echo "🔎 Analyse"
ruff check . || true

echo "🔧 Refactor"
ruff check . --fix
ruff format .

echo "🧪 Tests"
pytest || true

echo "📋 Changements"
git diff