#!/bin/sh
set -eu

ollama serve &
server_pid=$!

stop_server() {
    kill "$server_pid" 2>/dev/null || true
}

trap stop_server INT TERM EXIT

attempt=0
until ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        echo "Ollama did not become ready." >&2
        exit 1
    fi
    sleep 2
done

if ! ollama list | awk 'NR > 1 { print $1 }' | grep -Fxq "$OLLAMA_MODEL"; then
    ollama pull "$OLLAMA_MODEL"
fi

wait "$server_pid"
