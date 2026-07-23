/**
 * Integration tests: slash command flows.
 *
 * Scope:
 *   - Drives real wiki-tools.ts command handlers via dispatchCommand
 *   - Verifies the FULL exec call shape (positional args + flags)
 *   - Verifies success / error notification paths end-to-end
 *   - Includes wiki_save_page tool execute() which is not covered by
 *     unit-level slash command tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createMockPi,
  createMockCtx,
  dispatchCommand,
} from '../helpers/mockExtensionContext';

const EXTENSION_PATH = '../../.pi/extensions/wiki-tools.ts';

async function loadExtension() {
  const pi = createMockPi();
  const mod = await import(EXTENSION_PATH);
  mod.default(pi);
  return pi;
}

function mockExecOk(pi: any, stdout = 'ok', stderr = '') {
  vi.mocked(pi.exec).mockResolvedValue({ code: 0, stdout, stderr, killed: false });
}

function mockExecFail(pi: any, stdout = '', stderr = 'fail') {
  vi.mocked(pi.exec).mockResolvedValue({ code: 1, stdout, stderr, killed: false });
}

describe('slash command integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('/wiki_test issues src/fandom.py test and routes stdout to a success notify', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, '✓ connected as WikiBot');
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_test', '', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', ['src/fandom.py', 'test']);
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('✓ connected'),
      'info',
    );
  });

  it('/wiki_convert_page dry-run includes --dry-run in exec args', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'preview generated');
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_convert_page', 'page_name="X"', ctx);

    expect(ctx.ui.confirm).not.toHaveBeenCalled();
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'page',
      'X',
      '--dry-run',
    ]);
  });

  it('/wiki_convert_page --confirm drops --dry-run after user accepts', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'saved');
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);

    await dispatchCommand(
      pi,
      'wiki_convert_page',
      'page_name="X" --confirm',
      ctx,
    );

    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'page',
      'X',
    ]);
  });

  it('/wiki_scan rejects --approve-all without invoking exec', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_scan', '--approve-all', ctx);

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('拒绝 --approve-all'),
      'error',
    );
  });

  it('/wiki_fix_links defaults to dry-run mode', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'previewed');
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_fix_links',
      'old_text="A" new_text="B"',
      ctx,
    );

    expect(ctx.ui.confirm).not.toHaveBeenCalled();
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'fix-links',
      'A',
      'B',
      '--dry-run',
    ]);
  });

  it('/wiki_fix_links --confirm commits after user accepts confirm', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'applied');
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);

    await dispatchCommand(
      pi,
      'wiki_fix_links',
      'old_text="A" new_text="B" --confirm',
      ctx,
    );

    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'fix-links',
      'A',
      'B',
    ]);
  });

  it('/wiki_update_cat_refs forwards --from-file in dry-run mode', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'plan ready');
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_update_cat_refs',
      'from_file="cats.txt"',
      ctx,
    );

    expect(ctx.ui.confirm).not.toHaveBeenCalled();
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'update-cat-refs',
      '--from-file',
      'cats.txt',
      '--dry-run',
    ]);
  });

  it('/wiki_test routes exec failure to error notify', async () => {
    const pi = await loadExtension();
    mockExecFail(pi, '', 'connection refused');
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_test', '', ctx);

    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('connection refused'),
      'error',
    );
  });

  describe('wiki_save_page tool flow', () => {
    it('requires ctx.ui.confirm before invoking IPC server', async () => {
      const pi = await loadExtension();
      const ctx = createMockCtx();
      vi.mocked(ctx.ui.confirm).mockResolvedValue(false);

      const handler = pi._toolHandlers['wiki_save_page'];
      const result = await handler(
        'call-1',
        { title: 'X', content: 'valid' },
        undefined,
        undefined,
        ctx,
      );

      expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
      expect(pi.exec).not.toHaveBeenCalled();
      expect(result.details).toMatchObject({
        title: 'X',
        ok: false,
        cancelled: true,
      });
    });

    it('short-circuits on __待填__ without reaching confirm gate', async () => {
      const pi = await loadExtension();
      const ctx = createMockCtx();

      const handler = pi._toolHandlers['wiki_save_page'];
      const result = await handler(
        'call-2',
        { title: 'X', content: 'has __待填__ placeholder' },
        undefined,
        undefined,
        ctx,
      );

      expect(ctx.ui.confirm).not.toHaveBeenCalled();
      expect(result.details).toMatchObject({ title: 'X', ok: false });
      expect(result.content[0].text).toContain('__待填__');
    });
  });
});
