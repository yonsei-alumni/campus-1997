import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  server: { port: 5197 },
  build: { chunkSizeWarningLimit: 2000, assetsInlineLimit: 0 },
});
