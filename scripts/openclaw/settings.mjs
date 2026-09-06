// Shared by the two deployment images and the local manifest renderer.
export function required(env, name) {
  const value = env[name];
  if (typeof value !== 'string' || !value.trim() || /[\r\n\0]/.test(value)
      || /^(change[-_]?me|replace|your[-_]|example)/i.test(value)) {
    throw new Error(`${name}: supply a real, nonempty single-line value`);
  }
  return value;
}

export function settings(profile, env) {
  if (!['dual', 'inkling'].includes(profile)) throw new Error('Unknown deployment profile');
  const token = required(env, 'OPENCLAW_GATEWAY_TOKEN');
  if (token.length < 32) throw new Error('OPENCLAW_GATEWAY_TOKEN: at least 32 characters required');
  const portText = env.OPENCLAW_PORT || '18789';
  if (!/^\d+$/.test(portText) || +portText < 1024 || +portText > 65535) {
    throw new Error('OPENCLAW_PORT: expected an integer from 1024 to 65535');
  }
  const result = { port: +portText };
  if (profile === 'inkling') {
    required(env, 'INKLING_API_KEY');
    const baseUrl = env.INKLING_BASE_URL || 'https://ai-gateway.vercel.sh/v1';
    let url;
    try { url = new URL(baseUrl); } catch { throw new Error('INKLING_BASE_URL: invalid URL'); }
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) {
      throw new Error('INKLING_BASE_URL: HTTPS URL without credentials, query or fragment required');
    }
    const model = required(env, 'INKLING_MODEL');
    if (!/^[\w./:-]+$/.test(model)) throw new Error('INKLING_MODEL: invalid model identifier');
    return { ...result, baseUrl, model };
  }
  for (const key of ['DEEPINFRA_API_KEY', 'GITHUB_TOKEN', 'TOKEN_BOT_A', 'TOKEN_BOT_B']) required(env, key);
  if (env.TOKEN_BOT_A === env.TOKEN_BOT_B) throw new Error('Use two different Telegram bot tokens');
  const models = ['QWEN_MODEL_ID', 'DEEPSEEK_MODEL_ID'].map(key => {
    const model = required(env, key);
    if (!/^[\w./:-]+$/.test(model)) throw new Error(`${key}: invalid model identifier`);
    return model;
  });
  if (models[0] === models[1]) throw new Error('Choose two different model identifiers');
  const repositories = required(env, 'REPOSITORIES').split(',').map(repo => repo.trim());
  if (repositories.some(repo => !/^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(repo)
      || repo.endsWith('.git')) || new Set(repositories.map(repo => repo.toLowerCase())).size !== repositories.length) {
    throw new Error('REPOSITORIES: unique owner/name entries required (without .git)');
  }
  return { ...result, models, repositories };
}
