#!/usr/bin/env bash
set -e

echo "🤖 Inkling Code Analyzer"
echo "========================"

if [ -z "$inkling_api" ]; then
    echo "❌ Secret Codespaces 'inkling_api' absent."
    exit 1
fi

echo "✅ Secret Inkling détecté"

python3 tools/analyze_ai.py
