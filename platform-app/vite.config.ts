import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import http from 'node:http';

const FALKOR_TARGET = 'http://localhost:3002';
const FALKOR_MIRROR_PORT = 3009;

// ── Embed the FalkorDB Browser (localhost:3002) inside /graph ────────────────
// It ships `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` (baked into
// its build, not env-configurable — protects against clickjacking from a
// HOSTILE origin; here both ends are the same local machine/operator) AND its
// own login flow does CLIENT-SIDE `router.push('/login')`, which resolves
// against the real browser `window.location`, not any proxy path prefix — the
// app has no `basePath` (also baked in). So a sub-path proxy (`/falkor/*` on
// this dev server) can serve the first response, but the moment the app
// redirects to `/login` that navigation escapes the prefix and lands on THIS
// app's own (nonexistent) `/login` route instead.
// Fix: mirror :3002 onto its OWN port at the root (no path rewriting) so the
// iframe's origin genuinely IS that mirror — every root-relative link the
// embedded app emits (`/login`, `/api/auth/*`, `/_next/*`) then resolves
// correctly, same as visiting it directly. `AUTH_URL`/`NEXTAUTH_URL` on the
// falkordb container (docker-compose.yml) must point at this mirror port.
function falkorMirror(): Plugin {
  return {
    name: 'falkor-mirror',
    configureServer() {
      const server = http.createServer((req, res) => {
        const proxyReq = http.request(
          FALKOR_TARGET + req.url,
          { method: req.method, headers: { ...req.headers, host: 'localhost:3002' } },
          (proxyRes) => {
            const headers = { ...proxyRes.headers };
            delete headers['x-frame-options'];
            if (typeof headers['content-security-policy'] === 'string') {
              // Cross-origin embed (this mirror is its own port, not a
              // sub-path of :5173) — 'self' means the FRAMED document's own
              // origin, which doesn't cover the parent, so name it explicitly.
              headers['content-security-policy'] = headers['content-security-policy'].replace(
                /frame-ancestors[^;]*;?/gi,
                "frame-ancestors http://localhost:5173;",
              );
            }
            res.writeHead(proxyRes.statusCode ?? 502, headers);
            proxyRes.pipe(res);
          },
        );
        proxyReq.on('error', () => res.writeHead(502).end('falkor mirror: upstream unavailable'));
        req.pipe(proxyReq);
      });
      server.on('upgrade', (req, socket, head) => {
        const proxyReq = http.request(FALKOR_TARGET + req.url, {
          method: req.method,
          headers: { ...req.headers, host: 'localhost:3002' },
        });
        proxyReq.on('upgrade', (proxyRes, proxySocket, proxyHead) => {
          socket.write(
            `HTTP/1.1 101 Switching Protocols\r\n` +
              Object.entries(proxyRes.headers)
                .map(([k, v]) => `${k}: ${v}`)
                .join('\r\n') +
              '\r\n\r\n',
          );
          proxySocket.write(proxyHead);
          proxySocket.pipe(socket);
          socket.pipe(proxySocket);
        });
        proxyReq.end(head);
      });
      server.listen(FALKOR_MIRROR_PORT);
    },
  };
}

export default defineConfig({
  plugins: [react(), falkorMirror()],
  // host: true → listen on 0.0.0.0 so a phone on the same Wi-Fi can open
  // http://<mac-lan-ip>:5173. Vite prints the Network URL on start.
  server: {
    port: 5173,
    host: true,
  },
  // mermaid ships as ESM; let Vite pre-bundle it and its deps normally
  optimizeDeps: {
    include: ['mermaid'],
  },
  build: {
    rollupOptions: {
      // Keep mermaid in its own chunk so it doesn't bloat the main bundle
      output: {
        manualChunks: { mermaid: ['mermaid'] },
      },
    },
  },
});
