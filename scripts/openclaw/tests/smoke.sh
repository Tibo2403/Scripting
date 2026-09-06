#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
command -v jq >/dev/null
mkdir -p "$tmp/bin"
export PATH="$tmp/bin:$PATH"
export OPENCLAW_RUNTIME_DIR="$root/scripts/openclaw"
export OPENCLAW_TEMPLATE_DIR="$root/openclaw-akash-dual-agents"
export OPENCLAW_DATA_DIR="$tmp/data"
export OPENCLAW_STATE_DIR="$tmp/state"
export OPENCLAW_CONFIG_PATH="$tmp/state/openclaw.json"
export OPENCLAW_GATEWAY_TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export DEEPINFRA_API_KEY=fixture GITHUB_TOKEN=fixture TOKEN_BOT_A=111:aaa TOKEN_BOT_B=222:bbb
export QWEN_MODEL_ID=vendor/qwen DEEPSEEK_MODEL_ID=vendor/deepseek REPOSITORIES=acme/one,other/one
export INKLING_API_KEY=fixture INKLING_MODEL=vendor/model
export TEST_LOG="$tmp/log" TEST_DATA="$tmp/data"
cat > "$tmp/bin/openclaw" <<'SH'
#!/usr/bin/env bash
echo "$*" >> "$TEST_LOG"
if [[ "$1" == config ]]; then exit "${SCHEMA_FAILURE:-0}"; fi
SH
cat > "$tmp/bin/curl" <<'SH'
#!/usr/bin/env bash
if [[ "${CURL_FAILURE:-0}" != 0 ]]; then exit 22; fi
printf '%s' "${CATALOG}"
SH
cat > "$tmp/bin/gh" <<'SH'
#!/usr/bin/env bash
[[ "${CLONE_FAILURE:-0}" == 0 ]] || exit 7
mkdir -p "$4/.git"
echo "$3" > "$4/.git/test-origin"
SH
cat > "$tmp/bin/git" <<'SH'
#!/usr/bin/env bash
if [[ "$3" == remote ]]; then
  [[ "${WRONG_ORIGIN:-0}" == 0 ]] || { echo https://github.com/wrong/repo; exit; }
  printf 'https://github.com/%s.git\n' "$(cat "$2/.git/test-origin")"
else
  exit "${FETCH_FAILURE:-0}"
fi
SH
chmod +x "$tmp/bin/"*
export CATALOG='{"data":[{"id":"vendor/qwen"},{"id":"vendor/deepseek"}]}'
dual() { bash "$root/openclaw-akash-dual-agents/scripts/entrypoint.sh"; }
inkling() { sh "$root/openclaw-inkling-akash/entrypoint.sh"; }
fails() {
  : > "$TEST_LOG"
  if "$@" > "$tmp/output" 2>&1; then echo "Expected failure: $*" >&2; exit 1; fi
  if grep -q '^gateway' "$TEST_LOG"; then echo 'Gateway ran after failure' >&2; exit 1; fi
}
dual
test -d "$tmp/data/repos/acme/one/.git"
test -d "$tmp/data/repos/other/one/.git"
echo retained > "$tmp/data/workspaces/agent-qwen/SOUL.md"
dual
test "$(cat "$tmp/data/workspaces/agent-qwen/SOUL.md")" = retained
inkling
export OPENCLAW_IMAGE=ghcr.io/acme/openclaw:1.0
node --input-type=module -e '
  import fs from "node:fs";
  const common = ["OPENCLAW_IMAGE", "OPENCLAW_GATEWAY_TOKEN"];
  const profiles = {
    dual: [...common, "DEEPINFRA_API_KEY", "GITHUB_TOKEN", "TOKEN_BOT_A", "TOKEN_BOT_B", "QWEN_MODEL_ID", "DEEPSEEK_MODEL_ID", "REPOSITORIES"],
    inkling: [...common, "INKLING_API_KEY", "INKLING_MODEL"]
  };
  for (const [profile, keys] of Object.entries(profiles))
    fs.writeFileSync(process.argv[1] + "/" + profile + ".env", keys.map(k => k + "=" + process.env[k]).join("\n"));
' "$tmp"
for profile in dual inkling; do
  project=openclaw-inkling-akash
  [[ "$profile" != dual ]] || project=openclaw-akash-dual-agents
  bash "$root/$project/render-deploy.sh" "$tmp/$profile.env" "$tmp/$profile.yaml"
  grep -q 'global: false' "$tmp/$profile.yaml"
  fails bash "$root/$project/render-deploy.sh" "$tmp/$profile.env" "$tmp/$profile.yaml"
  bash "$root/$project/render-deploy.sh" "$tmp/$profile.env" "$tmp/$profile.yaml" --force
done
export FETCH_FAILURE=9; fails dual; unset FETCH_FAILURE
export WRONG_ORIGIN=1; fails dual; unset WRONG_ORIGIN
export CURL_FAILURE=1; fails dual; unset CURL_FAILURE
export CATALOG='{"data":[]}'; fails dual
export CATALOG='{"data":"malformed"}'; fails dual
export CATALOG='{"data":[{"id":"vendor/qwen"},{"id":"vendor/deepseek"}]}'
export REPOSITORIES=acme/new CLONE_FAILURE=1; fails dual; unset CLONE_FAILURE
export SCHEMA_FAILURE=1; fails inkling; unset SCHEMA_FAILURE
export INKLING_API_KEY=''; fails inkling
echo 'Entrypoint smoke tests passed.'
