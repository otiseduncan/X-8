import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['x8-web', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': 'http://x8-api:8080'
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/tests/setup.ts'
  }
});
