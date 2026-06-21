import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const openWebUiTarget = process.env.VITE_OPENWEBUI_PROXY_TARGET || process.env.OPENWEBUI_PROXY_TARGET || 'http://host.docker.internal:3000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: './app/App',
        replacement: fileURLToPath(new URL('./src/app/MirrorApp.tsx', import.meta.url))
      }
    ]
  },
  server: {
    allowedHosts: ['x8-web', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': 'http://x8-api:8080',
      '/openwebui': {
        target: openWebUiTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/openwebui/, '') || '/',
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            delete proxyRes.headers['x-frame-options'];
            delete proxyRes.headers['content-security-policy'];
          });
        }
      }
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/tests/setup.ts'
  }
});
