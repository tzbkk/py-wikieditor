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

function mockExecOk(pi: any, stdout = "ok", stderr = "") {
  vi.mocked(pi.exec).mockResolvedValue({
    code: 0,
    stdout,
    stderr,
    killed: false,
  });
}

describe('slash commands', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('/wiki_test calls fandom.py test and notifies success', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, '✓ 已登录');
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_test', '', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'test',
    ]);
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('✓ 已登录'),
      'info',
    );
  });

  it('/wiki_info defaults to Template:音樂信息 when no arg given', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'template info');
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_info', '', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'info',
      'Template:音樂信息',
    ]);
  });

  it('/wiki_info passes positional arg through', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_info', 'Template:角色信息', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'info',
      'Template:角色信息',
    ]);
  });

  it('/wiki_convert_page defaults to dry-run', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'dry-run ok');
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_convert_page',
      'page_name="TestPage"',
      ctx,
    );

    expect(pi.exec).toHaveBeenCalledWith(
      'python3',
      expect.arrayContaining(['--dry-run']),
    );
    expect(ctx.ui.confirm).not.toHaveBeenCalled();
  });

  it('/wiki_convert_page --confirm drops dry-run after confirm=true', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'done');
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);

    await dispatchCommand(
      pi,
      'wiki_convert_page',
      'page_name="TestPage" --confirm',
      ctx,
    );

    expect(ctx.ui.confirm).toHaveBeenCalledTimes(1);
    expect(pi.exec).toHaveBeenCalledWith(
      'python3',
      expect.not.arrayContaining(['--dry-run']),
    );
    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'page',
      'TestPage',
    ]);
  });

  it('/wiki_convert_page --confirm aborts when confirm=false', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(false);

    await dispatchCommand(
      pi,
      'wiki_convert_page',
      'page_name="TestPage" --confirm',
      ctx,
    );

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith('已取消', 'info');
  });

  it('/wiki_convert_page errors when page_name missing', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_convert_page', '', ctx);

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      '❌ 缺少 page_name 参数',
      'error',
    );
  });

  it('/wiki_convert_category passes --limit through', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_convert_category',
      'category="音乐" limit="5"',
      ctx,
    );

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'category',
      '音乐',
      '--dry-run',
      '--limit',
      '5',
    ]);
  });

  it('/wiki_restore defaults to --show-versions', async () => {
    const pi = await loadExtension();
    mockExecOk(pi, 'versions listed');
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_restore',
      'page_name="SomePage"',
      ctx,
    );

    expect(pi.exec).toHaveBeenCalledWith(
      'python3',
      expect.arrayContaining(['--show-versions']),
    );
    expect(ctx.ui.confirm).not.toHaveBeenCalled();
  });

  it('/wiki_restore --confirm drops --show-versions after confirm=true', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();
    vi.mocked(ctx.ui.confirm).mockResolvedValue(true);

    await dispatchCommand(
      pi,
      'wiki_restore',
      'page_name="SomePage" --confirm',
      ctx,
    );

    expect(pi.exec).toHaveBeenCalledWith(
      'python3',
      expect.not.arrayContaining(['--show-versions']),
    );
  });

  it('/wiki_scan rejects --approve-all without calling exec', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_scan', '--approve-all', ctx);

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('拒绝 --approve-all'),
      'error',
    );
  });

  it('/wiki_scan defaults to --scan-only', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_scan', '', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'scan',
      '--scan-only',
    ]);
  });

  it('/wiki_scan_category rejects --approve-all', async () => {
    const pi = await loadExtension();
    const ctx = createMockCtx();

    await dispatchCommand(
      pi,
      'wiki_scan_category',
      '--approve-all',
      ctx,
    );

    expect(pi.exec).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('拒绝 --approve-all'),
      'error',
    );
  });

  it('/wiki_scan_category defaults to scan-category --scan-only', async () => {
    const pi = await loadExtension();
    mockExecOk(pi);
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_scan_category', '', ctx);

    expect(pi.exec).toHaveBeenCalledWith('python3', [
      'src/fandom.py',
      'scan-category',
      '--scan-only',
    ]);
  });

  it('/wiki_test notifies error when exec fails', async () => {
    const pi = await loadExtension();
    vi.mocked(pi.exec).mockResolvedValue({
      code: 1,
      stdout: '',
      stderr: 'login failed',
      killed: false,
    });
    const ctx = createMockCtx();

    await dispatchCommand(pi, 'wiki_test', '', ctx);

    expect(ctx.ui.notify).toHaveBeenCalledWith(
      expect.stringContaining('login failed'),
      'error',
    );
  });
});
