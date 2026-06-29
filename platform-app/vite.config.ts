import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // host: true → listen on 0.0.0.0 so a phone on the same Wi-Fi can open
  // http://<mac-lan-ip>:5173. Vite prints the Network URL on start.
  server: { port: 5173, host: true },
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
