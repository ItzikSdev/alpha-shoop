// Transactional email via Resend — same provider/API key already used by
// this monorepo's internal support-agent backend
// (src/mcp_tools/support_inbox.py's send_reply_via_resend), reused here for
// customer-facing password-reset emails. `from` is the store's own
// support address, matching that existing convention.
const RESEND_URL = 'https://api.resend.com/emails';
const FROM_ADDRESS = 'ALPHA FOR BABY <support@alphaforbaby.com>';

/**
 * @param {Env} env
 * @param {{to: string, resetUrl: string}} input
 */
export async function sendPasswordResetEmail(env, {to, resetUrl}) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    throw new Error('RESEND_API_KEY is not configured.');
  }

  const text =
    `We received a request to reset your ALPHA FOR BABY account password.\n\n` +
    `Reset your password: ${resetUrl}\n\n` +
    `This link expires in 30 minutes. If you didn't request this, you can ignore this email.`;

  const html = `
    <div style="font-family:sans-serif;font-size:14px;line-height:1.6;color:#161616">
      <p>We received a request to reset your ALPHA FOR BABY account password.</p>
      <p>
        <a href="${resetUrl}" style="display:inline-block;padding:12px 24px;background:#161616;color:#fff;text-decoration:none;border-radius:6px">
          Reset your password
        </a>
      </p>
      <p style="color:#8d8d8d;font-size:12px">
        This link expires in 30 minutes. If you didn't request this, you can ignore this email.
      </p>
    </div>
  `;

  const res = await fetch(RESEND_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: FROM_ADDRESS,
      to: [to],
      subject: 'Reset your ALPHA FOR BABY password',
      text,
      html,
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Resend ${res.status}: ${body.slice(0, 300)}`);
  }
}

/** @typedef {import('@shopify/hydrogen').HydrogenEnv} Env */
