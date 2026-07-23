import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createMockPi,
  createMockCtx,
  dispatchCommand,
} from './helpers/mockExtensionContext';

const EXTENSION_PATH = '../.pi/extensions/wiki-tools.ts';

async function loadExtension() {
  const pi = createMockPi();
  const mod = await import(EXTENSION_PATH);
  mod.default(pi);
  return pi;
}

function mockExecOk(pi: any, stdout = 'ok', stderr = '') {
  vi.mocked(pi.exec).mockResolvedValue({
    code: 0,
    stdout,
    stderr,
    killed: false,
  });
}

describe('destructive commands', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('/wiki_fix_links defaults to dry-run and skips confirm', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'preview done');
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

  it('/wiki_fix_links --confirm drops dry-run after confirm=true', async () => {
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
    expect(pi.exec).toHaveBeenCalledWith(
      'python3',
      expect.not.arrayContaining(['--dry-run']),
    );
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'fix-links',
      'A',
      'B',
    ]);
  });

  it('/wiki_fix_links --confirm aborts when confirm=false', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(false);

    await dispatchCommand(
      pi,
      'wiki_fix_links',
      'old_text="A" new_text="B" --confirm',
      ctx,
    );

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith('已取消', 'info');
  });

  it('/wiki_fix_links errors when old_text or new_text missing', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_fix_links', 'old_text="A"', ctx);

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      '❌ 需要 old_text 和 new_text 参数',
      'error',
    );
  });

  it('/wiki_update_cat_refs defaults to dry-run with positional categories', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_update_cat_refs',
      '片頭曲 片尾曲',
      ctx,
    );

    expect(ctx.ui.confirm).not.toHaveBeenCalled();
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'update-cat-refs',
      '片頭曲',
      '片尾曲',
      '--dry-run',
    ]);
  });

  it('/wiki_update_cat_refs --confirm drops dry-run after confirm=true', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);

    await dispatchCommand(
      pi,
      'wiki_update_cat_refs',
      '片頭曲 --confirm',
      ctx,
    );

    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'update-cat-refs',
      '片頭曲',
    ]);
  });

  it('/wiki_update_cat_refs --from-file passes through and defaults to dry-run', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_update_cat_refs',
      'from_file="cats.txt"',
      ctx,
    );

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'update-cat-refs',
      '--from-file',
      'cats.txt',
      '--dry-run',
    ]);
  });

  it('/wiki_update_cat_refs errors when neither categories nor --from-file given', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_update_cat_refs', '', ctx);

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      '❌ 需要至少一个分类名或 --from-file 参数',
      'error',
    );
  });

  it('wiki_save_page returns cancelled response when confirm=false', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(false);

    const handler = pi._toolHandlers['wiki_save_page'];
    const result = await handler(
      'id',
      { title: 'X', content: 'valid content' },
      undefined,
      undefined,
      ctx,
    );

    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
    expect(result.details).toMatchObject({
      title: 'X',
      ok: false,
      cancelled: true,
    });
    expect(result.content[0].text).toContain('用户取消了保存');
    expect(pi.exec).not.toHaveBeenCalled();
  });

  it('wiki_save_page blocks on __待填__ before confirm gate', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    const handler = pi._toolHandlers['wiki_save_page'];
    const result = await handler(
      'id',
      { title: 'X', content: 'has __待填__ placeholder' },
      undefined,
      undefined,
      ctx,
    );

    // __待填__ short-circuits before confirm is reached
    expect(ctx.ui.confirm).not.toHaveBeenCalled();
    expect(pi.exec).not.toHaveBeenCalled();
    expect(result.details).toMatchObject({ title: 'X', ok: false });
    expect(result.content[0].text).toContain('__待填__');
  });
});
