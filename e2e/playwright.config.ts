import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  expect: {
    timeout: 30000
  },
  use: {
    baseURL: 'http://x8-web:5173'
  }
});
