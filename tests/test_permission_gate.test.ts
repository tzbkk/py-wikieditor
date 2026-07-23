import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createMockPi,
  createMockCtx,
  dispatchToolCall,
} from './helpers/mockExtensionContext';

const EXTENSION_PATH = '../.pi/extensions/wiki-tools.ts';

async function loadExtension() {
  const pi = createMockPi();
  const mod = await import(EXTENSION_PATH);
  mod.default(pi);
  return pi;
}

describe('permission gate', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('blocks rm -rf when confirm returns false', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(false);
    const result = await dispatchToolCall(
      pi,
      'bash',
      { command: 'rm -rf /tmp/foo' },
      ctx,
    );
    expect(result?.block).toBe(true);
    expect(result?.reason).toMatch(/rm -rf/);
    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
  });

  it('allows rm -rf when confirm returns true', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);
    const result = await dispatchToolCall(
      pi,
      'bash',
      { command: 'rm -rf /tmp/foo' },
      ctx,
    );
    expect(result).toBeUndefined();
  });

  it('blocks echo > .env without confirm', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    const result = await dispatchToolCall(
      pi,
      'bash',
      { command: 'echo KEY=val > .env' },
      ctx,
    );
    expect(result?.block).toBe(true);
    expect(ctx.ui.confirm).not.toHaveBeenCalled();
  });

  it('blocks --no-test-first in any string field', async () => {
    const pi = await loadExtension();
    const result = await dispatchToolCall(pi, 'wiki_convert_category', {
      category: 'X',
      flags: '--no-test-first',
    });
    expect(result?.block).toBe(true);
    expect(result?.reason).toMatch(/no-test-first/);
  });

  it('blocks __待填__ in wiki_save_page', async () => {
    const pi = await loadExtension();
    const result = await dispatchToolCall(pi, 'wiki_save_page', {
      title: 'X',
      content: 'name=__待填__',
    });
    expect(result?.block).toBe(true);
  });

  it('allows read tool without blocking', async () => {
    const pi = await loadExtension();
    const result = await dispatchToolCall(pi, 'read', {
      filePath: 'README.md',
    });
    expect(result).toBeUndefined();
  });
});
