import { defineConfig } from 'vite';

export default defineConfig({
  build: { assetsDir: 'static' },
  server: { proxy: { '/api': 'http://127.0.0.1:8080' } },
});
