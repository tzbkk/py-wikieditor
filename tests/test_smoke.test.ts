import { describe, it, expect } from 'vitest';
import { createMockPi, createMockCtx } from './helpers/mockExtensionContext';

describe('test infrastructure', () => {
  it('loads', () => {
    expect(true).toBe(true);
  });
  it('creates mock pi', () => {
    const pi = createMockPi();
    expect(pi.registerTool).toBeDefined();
    expect(pi.registerCommand).toBeDefined();
    expect(pi.on).toBeDefined();
  });
  it('creates mock ctx', () => {
    const ctx = createMockCtx();
    expect(ctx.ui.confirm).toBeDefined();
    expect(ctx.ui.notify).toBeDefined();
  });
});