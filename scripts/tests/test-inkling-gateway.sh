#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="${BASH_SOURCE[0]%/*}"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIRECTORY/../.." && pwd)"
cd "$REPOSITORY_ROOT"

unset INKLING_API_KEY LITELLM_MASTER_KEY
bash .devcontainer/start-inkling-gateway.sh --allow-missing-secrets >/dev/null

if bash .devcontainer/start-inkling-gateway.sh >/dev/null 2>&1; then
  printf 'ERROR: startup unexpectedly succeeded without required secrets.\n' >&2
  exit 1
fi

DUMMY_INKLING_KEY="test-inkling-secret-do-not-use"
DUMMY_MASTER_KEY="test-master-secret-do-not-use"
dry_run="$({
  INKLING_API_KEY="$DUMMY_INKLING_KEY" \
    LITELLM_MASTER_KEY="$DUMMY_MASTER_KEY" \
    bash scripts/bash/deploy_inkling_akash.sh --dry-run
} 2>/dev/null)"

[[ "$dry_run" == *"https://ai-gateway.vercel.sh/v1"* ]]
[[ "$dry_run" == *"thinkingmachines/inkling"* ]]
[[ "$dry_run" == *"<redacted-inkling-api-key>"* ]]
[[ "$dry_run" == *"<redacted-litellm-master-key>"* ]]
[[ "$dry_run" != *"$DUMMY_INKLING_KEY"* ]]
[[ "$dry_run" != *"$DUMMY_MASTER_KEY"* ]]

printf 'Inkling gateway shell smoke tests passed.\n'
