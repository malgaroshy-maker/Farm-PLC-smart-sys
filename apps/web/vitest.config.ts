import { defineConfig } from 'vitest/config';

// Kept separate from vite.config.ts: unit tests cover pure logic and need no plugins.
export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
});
