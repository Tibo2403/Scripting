import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { required, settings } from './settings.mjs';

export function parseEnv(text) {
  const env = Object.create(null);
  for (const [i, raw] of text.replace(/^\uFEFF/, '').split(/\r?\n/).entries()) {
    if (!raw.trim() || raw.trimStart().startsWith('#')) continue;
    const match = /^([A-Z][A-Z0-9_]*)=(.*)$/.exec(raw);
    if (!match || Object.hasOwn(env, match[1])) throw new Error(`Invalid or duplicate .env assignment at line ${i + 1}`);
    const [, key, value] = match;
    if (/^["']|[\0\r]/.test(value)) throw new Error(`Use unquoted Docker env-file syntax at line ${i + 1}`);
    env[key] = value;
  }
  return env;
}

export function render(profile, env) {
  settings(profile, env);
  const image = required(env, 'OPENCLAW_IMAGE');
  if (!/^[a-z0-9][a-z0-9./_-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*(?:@sha256:[a-f0-9]{64})?$/.test(image)
      || /:latest(?:@|$)/.test(image) || /(?:^|\/)USER\//i.test(image)) {
    throw new Error('OPENCLAW_IMAGE: use a registry image with an explicit version tag (not latest)');
  }
  if (env.OPENCLAW_PORT && env.OPENCLAW_PORT !== '18789') throw new Error('Akash SDL requires OPENCLAW_PORT=18789');
  const keys = profile === 'dual'
    ? ['DEEPINFRA_API_KEY', 'GITHUB_TOKEN', 'TOKEN_BOT_A', 'TOKEN_BOT_B', 'OPENCLAW_GATEWAY_TOKEN', 'QWEN_MODEL_ID', 'DEEPSEEK_MODEL_ID', 'REPOSITORIES']
    : ['INKLING_API_KEY', 'INKLING_BASE_URL', 'INKLING_MODEL', 'OPENCLAW_GATEWAY_TOKEN'];
  const allowed = new Set([...keys, 'OPENCLAW_IMAGE', 'OPENCLAW_PORT']);
  for (const key of Object.keys(env)) if (!allowed.has(key)) throw new Error(`Unsupported .env key: ${key}`);
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const project = profile === 'dual' ? 'openclaw-akash-dual-agents' : 'openclaw-inkling-akash';
  const template = fs.readFileSync(path.join(root, project, 'deploy.yaml.tpl'), 'utf8');
  const entries = keys.filter(key => env[key] !== undefined).map(key => `      - ${JSON.stringify(`${key}=${env[key]}`)}`).join('\n');
  return template.replace('{{IMAGE}}', JSON.stringify(image)).replace('{{ENV}}', entries);
}

export function saveManifest(text, output, force = false) {
  const parent = path.dirname(path.resolve(output));
  const temporary = fs.mkdtempSync(path.join(parent, '.manifest-'));
  try {
    const file = path.join(temporary, 'deploy.yaml');
    fs.writeFileSync(file, text, { mode: 0o600, flag: 'wx' });
    if (force) fs.renameSync(file, output);
    else fs.linkSync(file, output); // Atomic creation: never clobber an existing manifest.
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const [profile, input, output, option, ...extra] = process.argv.slice(2);
    if (!input || !output || extra.length || (option && option !== '--force')) {
      throw new Error('Usage: node scripts/openclaw/render.mjs dual|inkling INPUT.env OUTPUT.yaml [--force]');
    }
    const contents = render(profile, parseEnv(fs.readFileSync(input, 'utf8')));
    if (path.resolve(input) === path.resolve(output)) throw new Error('Input and output must differ');
    saveManifest(contents, output, option === '--force');
    console.log('Manifest created (contains secrets; do not commit or share it).');
  } catch (error) {
    console.error(`Manifest failed: ${error.code || error.message}`);
    process.exitCode = 1;
  }
}
