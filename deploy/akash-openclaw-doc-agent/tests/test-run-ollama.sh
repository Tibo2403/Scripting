#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_directory=$(mktemp -d)
trap 'rm -rf "$test_directory"' EXIT

cat >"$test_directory/ollama" <<'EOF'
#!/bin/sh
set -eu
case "$1" in
    serve)
        trap 'exit 0' INT TERM
        while :; do sleep 1; done
        ;;
    list)
        if [ "${FAKE_LIST_MODE:-ready}" = "unready" ]; then
            exit 1
        fi
        printf 'NAME ID SIZE\n'
        if [ "${FAKE_LIST_MODE:-ready}" = "ready" ]; then
            printf '%s fake-id 1GB\n' "$OLLAMA_MODEL"
        fi
        ;;
    pull)
        printf '%s\n' "$2" >"$FAKE_PULL_RECORD"
        exit "${FAKE_PULL_EXIT:-0}"
        ;;
    *) exit 64 ;;
esac
EOF
chmod +x "$test_directory/ollama"

PATH="$test_directory:$PATH"
export PATH
export OLLAMA_MODEL="test-model:q4"
export FAKE_PULL_RECORD="$test_directory/pulled-model"

FAKE_LIST_MODE=ready "$project_root/runtime/run-ollama.sh" &
ready_pid=$!
sleep 1
kill -TERM "$ready_pid"
wait "$ready_pid"
test ! -e "$FAKE_PULL_RECORD"

FAKE_LIST_MODE=missing "$project_root/runtime/run-ollama.sh" &
missing_pid=$!
attempt=0
while [ ! -e "$FAKE_PULL_RECORD" ] && [ "$attempt" -lt 20 ]; do
    attempt=$((attempt + 1))
    sleep 1
done
test "$(cat "$FAKE_PULL_RECORD")" = "$OLLAMA_MODEL"
kill -TERM "$missing_pid"
wait "$missing_pid"

if FAKE_LIST_MODE=unready OLLAMA_READY_ATTEMPTS=2 OLLAMA_READY_DELAY_SECONDS=0 \
    "$project_root/runtime/run-ollama.sh"; then
    echo "Expected readiness exhaustion to fail." >&2
    exit 1
fi

if OLLAMA_READY_ATTEMPTS=invalid "$project_root/runtime/run-ollama.sh"; then
    echo "Expected invalid readiness configuration to fail." >&2
    exit 1
fi

echo "Ollama runtime tests passed."
