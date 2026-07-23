import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    include: ['**/*.test.ts'],
    globals: true,
  },
  resolve: {
    alias: {
      // wiki-tools.ts imports `{ Type } from "typebox"`; we map it to the
      // @sinclair/typebox package installed under tests/node_modules using an
      // absolute path so resolution works even though the extension file lives
      // outside the tests/ directory.
      typebox: path.resolve(__dirname, 'node_modules/@sinclair/typebox'),
    },
  },
});