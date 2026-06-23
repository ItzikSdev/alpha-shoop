import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
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
