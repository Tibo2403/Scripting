import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { buildConfig, writeConfig } from '../config.mjs';
import { parseEnv, render, saveManifest } from '../render.mjs';

const dual = { OPENCLAW_GATEWAY_TOKEN: 'a'.repeat(40), OPENCLAW_IMAGE: 'ghcr.io/acme/review:1.0',
  DEEPINFRA_API_KEY: 'fixture-key', GITHUB_TOKEN: 'fixture-github', TOKEN_BOT_A: '111:aaa',
  TOKEN_BOT_B: '222:bbb', QWEN_MODEL_ID: 'vendor/qwen', DEEPSEEK_MODEL_ID: 'vendor/deepseek',
  REPOSITORIES: 'acme/one,other/one' };
const inkling = { OPENCLAW_GATEWAY_TOKEN: dual.OPENCLAW_GATEWAY_TOKEN,
  OPENCLAW_IMAGE: dual.OPENCLAW_IMAGE, INKLING_API_KEY: 'fixture-key', INKLING_MODEL: 'vendor/model' };

test('both profiles keep secrets as references and disable periodic activity', () => {
  for (const [profile, env] of [['dual', dual], ['inkling', inkling]]) {
    const config = buildConfig(profile, env);
    assert.equal(config.gateway.port, 18789);
    assert.equal(config.gateway.auth.token, '${OPENCLAW_GATEWAY_TOKEN}');
    assert.equal(config.cron.enabled, false);
    assert.equal(config.agents.defaults.heartbeat.every, '0m');
    assert.ok(!JSON.stringify(config).includes('fixture-key'));
  }
  const config = buildConfig('dual', dual);
  assert.equal(config.agents.list.length, 2);
  assert.deepEqual(config.agents.list[0].tools.allow, ['read']);
  assert.equal(config.channels.telegram.groupPolicy, 'disabled');
  assert.equal(config.bindings[1].match.accountId, 'deepseek');
});

test('invalid required settings cannot produce a config', () => {
  for (const key of Object.keys(dual).filter(k => k !== 'OPENCLAW_IMAGE')) {
    assert.throws(() => buildConfig('dual', { ...dual, [key]: '' }));
  }
  for (const patch of [
    { OPENCLAW_GATEWAY_TOKEN: 'short' }, { TOKEN_BOT_B: dual.TOKEN_BOT_A },
    { REPOSITORIES: '../escape' }, { REPOSITORIES: 'acme/one,ACME/ONE' },
    { REPOSITORIES: 'acme/repo.git' }, { OPENCLAW_PORT: '70000' },
    { OPENCLAW_PORT: '1e4' }, { QWEN_MODEL_ID: dual.DEEPSEEK_MODEL_ID },
    { GITHUB_TOKEN: 'replace-me' },
  ]) assert.throws(() => buildConfig('dual', { ...dual, ...patch }));
  for (const url of ['http://host/v1', 'https://secret@host/v1', 'https://host/v1?key=x', 'broken']) {
    assert.throws(() => buildConfig('inkling', { ...inkling, INKLING_BASE_URL: url }));
  }
});

test('env input is literal and ambiguous assignments are rejected', () => {
  assert.equal(parseEnv('INKLING_API_KEY=$(touch sentinel)\n').INKLING_API_KEY, '$(touch sentinel)');
  for (const input of ['export A=x', 'A=x\nA=y', 'A="quoted"', 'A=x\rvalue']) {
    assert.throws(() => parseEnv(input));
  }
});

test('SDL quotes values, stays private and refuses unsupported values', () => {
  for (const [profile, env] of [['dual', dual], ['inkling', inkling]]) {
    const output = render(profile, { ...env, OPENCLAW_GATEWAY_TOKEN: 'a'.repeat(40) + '" # $(id)' });
    assert.match(output, /global: false/);
    assert.ok(!output.includes('{{'));
    const entries = output.split('\n').filter(line => line.startsWith('      - "'));
    assert.ok(entries.map(line => JSON.parse(line.trim().slice(2))).includes('OPENCLAW_GATEWAY_TOKEN=' + 'a'.repeat(40) + '" # $(id)'));
    assert.throws(() => render(profile, { ...env, OPENCLAW_IMAGE: 'acme/image:latest' }));
    assert.throws(() => render(profile, { ...env, UNKNOWN: 'x' }));
    assert.throws(() => render(profile, { ...env, OPENCLAW_PORT: '19000' }));
  }
});

test('manifest writes refuse clobber; config replacement preserves valid JSON', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-test-'));
  try {
    const out = path.join(dir, 'deploy.yaml');
    saveManifest('first', out);
    assert.throws(() => saveManifest('second', out), { code: 'EEXIST' });
    assert.equal(fs.readFileSync(out, 'utf8'), 'first');
    saveManifest('second', out, true);
    assert.equal(fs.readFileSync(out, 'utf8'), 'second');
    writeConfig(buildConfig('inkling', inkling), path.join(dir, 'state/config.json'));
    writeConfig(buildConfig('dual', dual), path.join(dir, 'state/config.json'));
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir, 'state/config.json'))).agents.list.length, 2);
    assert.deepEqual(fs.readdirSync(dir).sort(), ['deploy.yaml', 'state']);
    if (process.platform !== 'win32') assert.equal(fs.statSync(out).mode & 0o777, 0o600);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('invalid CLI input fails without printing secret values or writing output', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-cli-'));
  try {
    const out = path.join(dir, 'config.json');
    const result = spawnSync(process.execPath, ['scripts/openclaw/config.mjs', 'dual', out],
      { env: { ...process.env, ...dual, GITHUB_TOKEN: '', DEEPINFRA_API_KEY: 'do-not-print-me' }, encoding: 'utf8' });
    assert.equal(result.status, 1);
    assert.ok(!result.stderr.includes('do-not-print-me'));
    assert.ok(!fs.existsSync(out));
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
