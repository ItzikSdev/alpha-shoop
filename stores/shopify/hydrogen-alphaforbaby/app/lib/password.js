// Password hashing using the Web Crypto API (crypto.subtle) — NOT Node's
// `crypto` module. Oxygen's runtime is Workers-like (based on workerd), so
// Node built-ins such as `crypto.createHash`/`crypto.pbkdf2` are not
// available, but the standard Web Crypto API (`crypto.subtle`) is a global
// in both MiniOxygen (local dev) and production Oxygen. `crypto.randomUUID()`
// is already used elsewhere in this app (see products.$handle.jsx's review
// feature), confirming the global `crypto` object works in this runtime;
// `crypto.subtle` is part of that same global and was smoke-tested directly
// against the local MiniOxygen dev server as part of this change (see the
// register/login Playwright run in the handoff notes) — a real
// register→login round trip only succeeds if hashPassword/verifyPassword
// both work end-to-end inside the actual Oxygen worker, not just in a
// Node script.
//
// Storage format: `pbkdf2$<iterations>$<saltBase64>$<hashBase64>` — the
// iteration count is embedded so it can be increased later without breaking
// verification of previously-hashed passwords.

// Oxygen's production Workers runtime caps Web Crypto PBKDF2 at 100,000
// iterations (confirmed via a live production error: "iteration counts
// above 100000 are not supported") — MiniOxygen's local dev runtime does
// NOT enforce this cap, which is why this only surfaced after deploying.
const PBKDF2_ITERATIONS = 100_000;
const SALT_BYTES = 16;
const HASH_BITS = 256; // 32 bytes

/**
 * @param {Uint8Array} bytes
 */
function toBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * @param {string} base64
 */
function fromBase64(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * @param {string} password
 * @param {Uint8Array} salt
 * @param {number} iterations
 */
async function derivePbkdf2Bits(password, salt, iterations) {
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(password),
    {name: 'PBKDF2'},
    false,
    ['deriveBits'],
  );

  const bits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt,
      iterations,
      hash: 'SHA-256',
    },
    keyMaterial,
    HASH_BITS,
  );

  return new Uint8Array(bits);
}

/**
 * Hashes a plaintext password with a fresh random salt.
 * @param {string} password
 * @returns {Promise<string>} a single string safe to store in a metafield,
 *   e.g. `pbkdf2$120000$<salt>$<hash>`
 */
export async function hashPassword(password) {
  if (!password || typeof password !== 'string') {
    throw new Error('hashPassword requires a non-empty string password.');
  }
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const hashBytes = await derivePbkdf2Bits(password, salt, PBKDF2_ITERATIONS);
  return `pbkdf2$${PBKDF2_ITERATIONS}$${toBase64(salt)}$${toBase64(hashBytes)}`;
}

/**
 * Verifies a plaintext password against a stored hash string produced by
 * `hashPassword`. Uses a constant-time comparison to avoid leaking timing
 * information about how much of the hash matched.
 * @param {string} password
 * @param {string | null | undefined} stored
 * @returns {Promise<boolean>}
 */
export async function verifyPassword(password, stored) {
  if (!password || !stored || typeof stored !== 'string') return false;

  const parts = stored.split('$');
  if (parts.length !== 4 || parts[0] !== 'pbkdf2') return false;

  const iterations = Number(parts[1]);
  if (!Number.isFinite(iterations) || iterations <= 0) return false;

  const salt = fromBase64(parts[2]);
  const expected = fromBase64(parts[3]);

  const actual = await derivePbkdf2Bits(password, salt, iterations);
  if (actual.length !== expected.length) return false;

  // Constant-time comparison.
  let diff = 0;
  for (let i = 0; i < actual.length; i++) {
    diff |= actual[i] ^ expected[i];
  }
  return diff === 0;
}

/**
 * Plain SHA-256 hex digest — used for one-time tokens (password reset),
 * NOT passwords. Tokens are already high-entropy random values, so a fast
 * hash (rather than PBKDF2) is standard practice: it just means a leaked
 * metafield can't be used to log in without also knowing the original
 * emailed link.
 * @param {string} input
 * @returns {Promise<string>}
 */
export async function sha256Hex(input) {
  const encoder = new TextEncoder();
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
