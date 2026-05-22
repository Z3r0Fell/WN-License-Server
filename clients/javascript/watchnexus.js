/**
 * WatchNexus Licensing Server - drop-in JavaScript / Node.js client.
 *
 * Works in:
 *   - Node 18+ (uses global fetch)
 *   - Modern browsers (Chrome, Firefox, Safari, Edge)
 *   - Electron / Tauri (via Node bridge)
 *
 * Usage:
 *   import { WatchNexusClient } from './watchnexus.js';
 *
 *   const client = new WatchNexusClient({
 *     baseUrl: 'https://licenses.example.com',
 *     apiKey:  'wnk_...',
 *     licenseKey: 'WNX-...',
 *   });
 *
 *   const token = await client.activate({
 *     hardware_id: '01:23:45:67:89:AB',
 *     domain: 'customer.example.com',
 *     device_name: "Marie’s MacBook Pro",
 *   });
 *
 *   const status = await client.validate(token, {
 *     hardware_id: '01:23:45:67:89:AB',
 *     domain: 'customer.example.com',
 *   });
 *   // { valid: true, mode: 'online' | 'grace' | 'grace_offline' | ... }
 *
 *   await client.deactivate(token);
 *
 * MIT-licensed; copy this file into your codebase.
 */

export class WatchNexusError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message);
    this.name = 'WatchNexusError';
    this.status = status;
    this.payload = payload;
  }
}

export class WatchNexusClient {
  /**
   * @param {{baseUrl: string, apiKey: string, licenseKey?: string, timeoutMs?: number, fetchImpl?: typeof fetch}} opts
   */
  constructor(opts) {
    if (!opts || !opts.baseUrl || !opts.apiKey) {
      throw new Error('WatchNexusClient requires { baseUrl, apiKey }');
    }
    this.baseUrl = String(opts.baseUrl).replace(/\/$/, '');
    this.apiKey = opts.apiKey;
    this.licenseKey = opts.licenseKey || null;
    this.timeoutMs = opts.timeoutMs || 10000;
    this._fetch = opts.fetchImpl || globalThis.fetch;
    if (!this._fetch) {
      throw new Error('No fetch implementation available. Provide opts.fetchImpl on Node <18.');
    }
  }

  async activate({ hardware_id, domain, device_name, license_key } = {}) {
    const key = license_key || this.licenseKey;
    if (!key) throw new Error('license_key required (pass it or set client.licenseKey)');
    return this._post('/api/integrate/activate', {
      license_key: key, hardware_id, domain, device_name,
    });
  }

  /**
   * Validate the activation token. If the network is down AND the locally
   * decoded token still has grace_until ≥ now, return a graceful offline ok.
   */
  async validate(tokenOrObj, { hardware_id, domain, allowOfflineGrace = true } = {}) {
    const activation_token = typeof tokenOrObj === 'string'
      ? tokenOrObj
      : tokenOrObj?.activation_token;
    if (!activation_token) throw new Error('Missing activation_token');
    try {
      return await this._post('/api/integrate/validate',
                              { activation_token, hardware_id, domain });
    } catch (e) {
      if (allowOfflineGrace) {
        const local = decodeActivationTokenLocally(activation_token);
        const now = Math.floor(Date.now() / 1000);
        if (local && (local.grace_until || 0) >= now) {
          return { valid: true, mode: 'grace_offline', claims: local, error: String(e) };
        }
      }
      throw e;
    }
  }

  async deactivate(tokenOrObj, { hardware_id, domain } = {}) {
    const activation_token = typeof tokenOrObj === 'string'
      ? tokenOrObj
      : tokenOrObj?.activation_token;
    return this._post('/api/integrate/deactivate', {
      activation_token, license_key: this.licenseKey, hardware_id, domain,
    });
  }

  async publicKey() {
    const r = await this._fetch(`${this.baseUrl}/api/public-key`, { signal: this._abort() });
    if (!r.ok) throw new WatchNexusError('public-key failed', { status: r.status });
    return (await r.json()).pem;
  }

  async health() {
    const r = await this._fetch(`${this.baseUrl}/api/health`, { signal: this._abort() });
    return r.json();
  }

  // ----- internals -----
  async _post(path, body) {
    const r = await this._fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'X-API-Key': this.apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: this._abort(),
    });
    let payload;
    try { payload = await r.json(); } catch { payload = null; }
    if (!r.ok) {
      throw new WatchNexusError(`${path} failed: ${r.status}`,
                                { status: r.status, payload });
    }
    return payload;
  }

  _abort() {
    if (typeof AbortController === 'undefined') return undefined;
    const c = new AbortController();
    setTimeout(() => c.abort(), this.timeoutMs);
    return c.signal;
  }
}

/**
 * Decode (without cryptographically verifying) the JWT payload of an
 * activation token. Use only to fall back to offline grace when /validate
 * is unreachable.
 */
export function decodeActivationTokenLocally(token) {
  try {
    const part = token.split('.')[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, '+').replace(/_/g, '/')
                    .padEnd(part.length + (4 - (part.length % 4)) % 4, '=');
    const json = typeof atob === 'function'
      ? atob(b64)
      : Buffer.from(b64, 'base64').toString('utf-8');
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export default WatchNexusClient;
