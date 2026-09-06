import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { settings } from './settings.mjs';

export function buildConfig(profile, env) {
  const s = settings(profile, env);
  const config = {
    gateway: { mode: 'local', bind: 'lan', port: s.port,
      auth: { mode: 'token', token: '${OPENCLAW_GATEWAY_TOKEN}' },
      controlUi: { enabled: false } },
    cron: { enabled: false },
    agents: { defaults: { heartbeat: { every: '0m' }, maxConcurrent: 1,
      memorySearch: { enabled: false }, sandbox: { mode: 'off' } } },
  };
  if (profile === 'inkling') {
    config.models = { mode: 'merge', providers: { inkling: {
      baseUrl: s.baseUrl, apiKey: '${INKLING_API_KEY}', api: 'openai-completions',
      models: [{ id: s.model, name: 'Inkling', input: ['text'],
        contextWindow: 32768, maxTokens: 4096 }],
    } } };
    config.agents.defaults.model = { primary: `inkling/${s.model}` };
    config.tools = { profile: 'minimal' };
  } else {
    config.models = { mode: 'merge', providers: { deepinfra: {
      baseUrl: 'https://api.deepinfra.com/v1/openai', apiKey: '${DEEPINFRA_API_KEY}',
      api: 'openai-completions', models: s.models.map(id => ({ id, name: id,
        input: ['text'], contextWindow: 32768, maxTokens: 4096 })),
    } } };
    config.agents.list = ['agent-qwen', 'agent-deepseek'].map((id, i) => ({
      id, ...(i === 0 ? { default: true } : {}), workspace: `/data/workspaces/${id}`,
      model: { primary: `deepinfra/${s.models[i]}` },
      // Reading checked-out code is the initial supported workflow. No shell or remote writes.
      tools: { allow: ['read'], deny: ['exec', 'process', 'write', 'edit', 'browser', 'message'] },
    }));
    config.channels = { telegram: { enabled: true, dmPolicy: 'pairing', groupPolicy: 'disabled',
      accounts: { qwen: { botToken: '${TOKEN_BOT_A}', dmPolicy: 'pairing' },
        deepseek: { botToken: '${TOKEN_BOT_B}', dmPolicy: 'pairing' } } } };
    config.bindings = ['qwen', 'deepseek'].map(name => ({ agentId: `agent-${name}`,
      match: { channel: 'telegram', accountId: name } }));
    config.session = { dmScope: 'per-account-channel-peer' };
  }
  return config;
}

export function writeConfig(config, destination) {
  const parent = path.dirname(destination);
  fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
  const temporary = fs.mkdtempSync(path.join(parent, '.config-'));
  try {
    const file = path.join(temporary, 'openclaw.json');
    fs.writeFileSync(file, JSON.stringify(config, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
    fs.renameSync(file, destination);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const [profile, destination] = process.argv.slice(2);
    if (!destination) throw new Error('Usage: node config.mjs dual|inkling OUTPUT');
    writeConfig(buildConfig(profile, process.env), destination);
  } catch (error) {
    // Filesystem errors can contain paths, but validation errors never contain secret values.
    console.error(`Configuration failed: ${error.code || error.message}`);
    process.exitCode = 1;
  }
}
