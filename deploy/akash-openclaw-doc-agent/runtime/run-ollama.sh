#!/bin/sh
set -eu

: "${OLLAMA_READY_ATTEMPTS:=60}"
: "${OLLAMA_READY_DELAY_SECONDS:=2}"

case "$OLLAMA_READY_ATTEMPTS" in
    ''|*[!0-9]*|0) echo "OLLAMA_READY_ATTEMPTS must be a positive integer." >&2; exit 2 ;;
esac
case "$OLLAMA_READY_DELAY_SECONDS" in
    ''|*[!0-9]*) echo "OLLAMA_READY_DELAY_SECONDS must be a non-negative integer." >&2; exit 2 ;;
esac

ollama serve &
server_pid=$!

stop_server() {
    kill "$server_pid" 2>/dev/null || true
}

trap 'stop_server; exit 0' INT TERM
trap stop_server EXIT

attempt=0
until ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$OLLAMA_READY_ATTEMPTS" ]; then
        echo "Ollama did not become ready." >&2
        exit 1
    fi
    sleep "$OLLAMA_READY_DELAY_SECONDS"
done

if ! ollama list | awk 'NR > 1 { print $1 }' | grep -Fxq "$OLLAMA_MODEL"; then
    ollama pull "$OLLAMA_MODEL"
fi

wait "$server_pid"
