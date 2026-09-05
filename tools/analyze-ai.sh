#!/bin/bash
set -e

if [ -z "$INKLING_API_KEY" ]; then
    echo "❌ INKLING_API_KEY manquante"
    exit 1
fi

if [ -z "$INKLING_API_URL" ]; then
    echo "❌ INKLING_API_URL manquante"
    exit 1
fi

python3 tools/analyze_ai.py
