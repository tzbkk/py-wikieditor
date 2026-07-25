#!/usr/bin/env python3
"""dump_xml.py — 下载 Wiki 页面为 MediaWiki XML dump 格式。

支持两种模式:
  --mode api     走 action=query&export API,仅当前版本,速度快(默认)
  --mode special 走 prop=revisions API,完整 revision history

产物:wiki_dump_xml/<Namespace>.xml(每个命名空间一个文件),
      格式同 dumpBackup.php / Special:Export,可用 mwxml / importDump.php 处理。
      仅读操作,不修改任何 Wiki 页面。

注意:Fandom 用 Cloudflare 拦截真正的 Special:Export 端点(403 "Just a moment..."),
      因此 special 模式实际走 prop=revisions API,手动构造等价的 XML dump。

流式写入 + 断点续传:
  - 每页拉完立即 fsync 到磁盘,内存只保留当前页的 revisions
  - .progress.json 记录 last_completed_idx(基于 pageid 列表顺序)
  - 重跑时若 progress 未完成,自动从断点续;若已完成,默认 skip(除非 --force)

用法:
    python src/dump_xml.py                          # 默认下载内容命名空间,api 模式
    python src/dump_xml.py --ns 0 10 --mode api     # 指定命名空间
    python src/dump_xml.py --mode special --history # 完整历史版本
    python src/dump_xml.py --list-only              # 只列出页面,不下载
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot


DEFAULT_NAMESPACES = [
    (0,   'main'),
    (10,  'Template'),
    (14,  'Category'),
    (828, 'Module'),
    (4,   'Project'),
]

DUMP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'wiki_dump_xml',
)

EXPORT_HEADER = (
    '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"\n'
    '           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
    '           xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.11/ '
    'http://www.mediawiki.org/xml/export-0.11.xsd"\n'
    '           version="0.11" xml:lang="zh">\n'
)
EXPORT_FOOTER = '</mediawiki>\n'

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
API_TITLES_BATCH = 50


def _api_url(site) -> str:
    return f'{site.scheme}://{site.host}{site.path}api.php'


def _index_url(site) -> str:
    return f'{site.scheme}://{site.host}{site.path}index.php'


def _resolve_ns_name(site, ns_id: int) -> str:
    ns = site.namespaces.get(ns_id)
    if ns is None:
        return f'ns{ns_id}'
    name = str(ns).strip() or f'ns{ns_id}'
    return name.replace('/', '_')


def _http_get(session, url: str, params: dict, timeout: int = 300):
    last_err: Exception = RuntimeError('unreachable')
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF ** attempt
                print(f'  ⚠️  GET 失败({e.__class__.__name__}),{wait}s 后重试', flush=True)
                time.sleep(wait)
    raise last_err


def _extract_page_elements(xml_chunk: str) -> str:
    """从一个 <mediawiki>...</mediawiki> 片段中提取所有 <page> 元素的字符串。

    exportnowrap=1 返回完整 <mediawiki> 根,直接拼接会得到多根 XML(无效)。
    提取 <page> 子元素,最后统一包裹。
    """
    if not xml_chunk or not xml_chunk.strip():
        return ''

    try:
        root = ET.fromstring(xml_chunk)
        ns_uri = ''
        if root.tag.startswith('{'):
            ns_uri = root.tag[1:root.tag.index('}')]
        page_tag = f'{{{ns_uri}}}page' if ns_uri else 'page'
        parts = [ET.tostring(page, encoding='unicode') for page in root.findall(page_tag)]
        if parts:
            return '\n'.join(parts)
    except ET.ParseError:
        pass

    matches = re.findall(r'<page[\s>].*?</page>', xml_chunk, re.DOTALL)
    return '\n'.join(matches)


def list_pages(site, ns_id: int) -> list:
    """JSON API 拉取命名空间全部页面标题(支持分页)。"""
    url = _api_url(site)
    titles = []
    apfrom = None
    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'apnamespace': str(ns_id),
            'aplimit': '500',
            'format': 'json',
        }
        if apfrom:
            params['apfrom'] = apfrom
        r = _http_get(site.connection, url, params)
        data = r.json()
        titles.extend(p['title'] for p in data.get('query', {}).get('allpages', []))
        cont = data.get('continue') or {}
        apfrom = cont.get('apcontinue') or cont.get('apfrom')
        if not apfrom:
            break
        time.sleep(0.2)
    return titles


def list_pages_with_ids(site, ns_id: int) -> list:
    """同 list_pages,但返回 [(pageid, title), ...](special 模式用)。

    Fandom 的 prop=revisions 拒绝 titles= 参数(返回空 pages),必须用 pageids=。
    """
    url = _api_url(site)
    pages = []
    apfrom = None
    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'apnamespace': str(ns_id),
            'aplimit': '500',
            'format': 'json',
        }
        if apfrom:
            params['apfrom'] = apfrom
        r = _http_get(site.connection, url, params)
        data = r.json()
        for p in data.get('query', {}).get('allpages', []):
            pages.append((p.get('pageid'), p.get('title')))
        cont = data.get('continue') or {}
        apfrom = cont.get('apcontinue') or cont.get('apfrom')
        if not apfrom:
            break
        time.sleep(0.2)
    return pages


def _build_revision_xml(rev: dict) -> str:
    """从 prop=revisions 的单个 revision dict 构造 <revision> XML 字符串。

    schema 参考 https://www.mediawiki.org/xml/export-0.11/
    """
    parts = ['    <revision>']
    revid = rev.get('revid')
    parts.append(f'      <id>{revid}</id>')
    parentid = rev.get('parentid', 0)
    if parentid:
        parts.append(f'      <parentid>{parentid}</parentid>')
    parts.append(f'      <timestamp>{rev.get("timestamp", "")}</timestamp>')

    user = rev.get('user', '') or ''
    userid = rev.get('userid', 0) or 0
    if user:
        if userid and userid > 0:
            parts.append('      <contributor>')
            parts.append(f'        <username>{_xml_escape(user)}</username>')
            parts.append(f'        <id>{userid}</id>')
            parts.append('      </contributor>')
        else:
            parts.append(f'      <contributor><ip>{_xml_escape(user)}</ip></contributor>')

    comment = rev.get('comment', '') or ''
    if comment:
        parts.append(f'      <comment>{_xml_escape(comment)}</comment>')

    if rev.get('minor'):
        parts.append('      <minor/>')

    model = rev.get('contentmodel', 'wikitext') or 'wikitext'
    fmt = rev.get('contentformat', 'text/x-wiki') or 'text/x-wiki'
    parts.append(f'      <model>{_xml_escape(model)}</model>')
    parts.append(f'      <format>{_xml_escape(fmt)}</format>')

    text = rev.get('*', '') or ''
    bytes_len = len(text.encode('utf-8'))
    parts.append(f'      <text xml:space="preserve" bytes="{bytes_len}">{_xml_escape(text)}</text>')

    sha1 = rev.get('sha1')
    if sha1:
        parts.append(f'      <sha1>{sha1}</sha1>')

    parts.append('    </revision>')
    return '\n'.join(parts)


def _build_page_xml(pageid, title: str, ns: int, revisions: list) -> str:
    """构造 <page>...</page> XML 字符串。"""
    parts = ['  <page>']
    parts.append(f'    <title>{_xml_escape(title)}</title>')
    parts.append(f'    <ns>{ns}</ns>')
    if pageid:
        parts.append(f'    <id>{pageid}</id>')
    for rev in revisions:
        parts.append(_build_revision_xml(rev))
    parts.append('  </page>')
    return '\n'.join(parts)


def _fetch_all_revisions(site, pageid: int, delay: float) -> list:
    """拉单个 pageid 的全部 revisions,翻页直到无 rvcontinue。"""
    url = _api_url(site)
    revisions = []
    rvcontinue = None
    while True:
        params = {
            'action': 'query',
            'pageids': str(pageid),
            'prop': 'revisions',
            'rvprop': 'ids|timestamp|user|userid|comment|content|flags|size|sha1',
            'rvlimit': '500',
            'format': 'json',
        }
        if rvcontinue:
            params['rvcontinue'] = rvcontinue
        r = _http_get(site.connection, url, params)
        data = r.json()
        p = data.get('query', {}).get('pages', {}).get(str(pageid), {})
        revisions.extend(p.get('revisions', []))
        rvcontinue = (data.get('continue') or {}).get('rvcontinue')
        if not rvcontinue:
            break
        time.sleep(delay * 0.3)
    return revisions


def _fsync_file(f) -> None:
    f.flush()
    os.fsync(f.fileno())


def _atomic_write_json(path: str, data: dict) -> None:
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        _fsync_file(f)
    os.replace(tmp, path)


def _load_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _strip_footer_if_present(output_path: str) -> bool:
    """如果文件尾部有 </mediawiki> 闭标签,截断掉前面的空白 + 闭标签。返回是否截过。"""
    if not os.path.exists(output_path):
        return False
    size = os.path.getsize(output_path)
    if size == 0:
        return False
    with open(output_path, 'rb+') as f:
        f.seek(max(0, size - 2048))
        tail = f.read().decode('utf-8', errors='ignore')
        footer_idx = tail.rfind('</mediawiki>')
        if footer_idx < 0:
            return False
        abs_truncate = size - len(tail.encode('utf-8')) + footer_idx
        while abs_truncate > 0:
            f.seek(abs_truncate - 1)
            ch = f.read(1)
            if ch.isspace():
                abs_truncate -= 1
            else:
                break
        f.truncate(abs_truncate)
        _fsync_file(f)
    return True


def export_via_api(site, ns_id: int, output_path: str,
                   schema: str = '0.11', delay: float = 1.0) -> tuple:
    """流式写当前版本 XML dump 到 output_path。

    走 action=query&export=1&exportnowrap=1 API,绕过 mwclient 的 format=json 强制包装。
    每批 50 个 title,响应 XML 直接写文件 + flush,内存仅留当前 batch。

    返回 (n_pages, size_bytes)。
    """
    titles = list_pages(site, ns_id)
    if not titles:
        return 0, 0

    url = _api_url(site)
    total = len(titles)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(EXPORT_HEADER)
        _fsync_file(f)

        for i in range(0, total, API_TITLES_BATCH):
            batch = titles[i:i + API_TITLES_BATCH]
            params = {
                'action': 'query',
                'titles': '|'.join(batch),
                'export': '1',
                'exportnowrap': '1',
                'exportschema': schema,
            }
            r = _http_get(site.connection, url, params)
            chunk = _extract_page_elements(r.text)
            if chunk:
                f.write(chunk)
                f.write('\n')
                _fsync_file(f)
            done = min(i + API_TITLES_BATCH, total)
            print(f'  [{done}/{total}] batch ✓', flush=True)
            if done < total:
                time.sleep(delay)

        f.write(EXPORT_FOOTER)
        _fsync_file(f)

    return total, os.path.getsize(output_path)


def export_via_special(site, ns_id: int, output_path: str,
                       history: bool = True, delay: float = 1.0) -> tuple:
    """流式写完整 history XML dump 到 output_path,支持断点续传。

    Fandom 用 Cloudflare 完全拦截 Special:Export 端点(403 + JS challenge),
    无法走传统 POST index.php 路径。改用 api.php 的 prop=revisions 拉每个页面的
    全部 revisions,然后按 MediaWiki export-0.11 schema 手动构造 XML。

    MediaWiki 硬限制:prop=revisions + rvlimit > 1 时只能查单页(invalidparammix),
    所以必须每页单独请求。682 页 × delay ≈ 几分钟。

    流式策略:
      - 每页拉完 revisions → 立即写文件 + fsync → 释放内存
      - .progress.json 记录 last_completed_idx(基于 pages 列表 enumerate 顺序)
      - resume:progress.first/last pageid 校验 pages 顺序未变,从 last_idx + 1 继续

    参数 history 仅作接口兼容:本模式总是拉完整 history(否则应走 api 模式)。

    返回 (n_pages_written, size_bytes)。
    """
    pages = list_pages_with_ids(site, ns_id)
    if not pages:
        return 0, 0

    total = len(pages)
    progress_path = output_path + '.progress.json'
    progress = _load_json(progress_path)

    if progress and progress.get('done') and os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f'  ⏭️  已完成({size // 1024}kb)', flush=True)
        return total, size

    last_idx = -1
    if progress and not progress.get('done'):
        saved_first = progress.get('first_pageid')
        saved_last = progress.get('last_pageid')
        if saved_first == pages[0][0] and saved_last == pages[-1][0]:
            last_idx = int(progress.get('last_completed_idx', -1))
            print(f'  ↩️  resume 自 {last_idx + 1}/{total}', flush=True)
            _strip_footer_if_present(output_path)
        else:
            print('  ⚠️  pages 顺序变化,从头开始', flush=True)

    is_fresh = (last_idx == -1)
    open_mode = 'w' if is_fresh else 'a'

    n_revisions_total = 0
    n_pages_written = last_idx + 1

    with open(output_path, open_mode, encoding='utf-8') as f:
        if is_fresh:
            f.write(EXPORT_HEADER)
            _fsync_file(f)

        for idx, (pid, title) in enumerate(pages):
            if idx <= last_idx:
                continue

            revisions = _fetch_all_revisions(site, pid, delay)
            revisions.sort(key=lambda r: r.get('revid', 0))

            f.write(_build_page_xml(pid, title, ns_id, revisions))
            f.write('\n')
            _fsync_file(f)

            n_revisions_total += len(revisions)
            n_pages_written = idx + 1
            last_idx = idx

            _atomic_write_json(progress_path, {
                'first_pageid': pages[0][0],
                'last_pageid': pages[-1][0],
                'last_completed_idx': last_idx,
                'done': False,
                'ns_id': ns_id,
                'total': total,
                'timestamp': time.time(),
            })

            if (idx + 1) % 25 == 0 or idx == total - 1:
                print(f'  [{idx + 1}/{total}] {n_revisions_total} revs total', flush=True)

            if idx < total - 1:
                time.sleep(delay)

        f.write(EXPORT_FOOTER)
        _fsync_file(f)

    _atomic_write_json(progress_path, {
        'first_pageid': pages[0][0],
        'last_pageid': pages[-1][0],
        'last_completed_idx': total - 1,
        'done': True,
        'ns_id': ns_id,
        'total': total,
        'timestamp': time.time(),
    })

    return n_pages_written, os.path.getsize(output_path)


def main():
    parser = argparse.ArgumentParser(
        description='下载 Wiki 页面为 MediaWiki XML dump 格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--ns', type=int, nargs='+',
                        help='命名空间 ID 列表(默认下载内容命名空间: 0 10 14 828 4)')
    parser.add_argument('--mode', choices=['api', 'special'], default='api',
                        help='导出模式: api=快速仅当前版本; special=支持完整 history(默认 api)')
    parser.add_argument('--history', action='store_true',
                        help='包含完整 revision history(仅 --mode special 有效)')
    parser.add_argument('--list-only', action='store_true',
                        help='只列出页面,不下载')
    parser.add_argument('--skip-existing', action='store_true',
                        help='跳过已存在且 .progress.json 标记 done 的 XML 文件')
    parser.add_argument('--force', action='store_true',
                        help='忽略已有 progress 和文件,强制重新下载')
    parser.add_argument('--dump-dir', default=DUMP_DIR,
                        help=f'输出目录(默认: {DUMP_DIR})')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='请求间延迟秒数,默认 1.0(Fandom 速率限制)')
    parser.add_argument('--schema', default='0.11',
                        help='XML dump schema 版本(仅 api 模式,默认 0.11)')
    args = parser.parse_args()

    print('🔗 连接 Wiki ...')
    bot = FandomBot()
    site = bot.site
    print(f'✓ 已登录: {site.username}')

    if args.ns:
        targets = [(ns_id, _resolve_ns_name(site, ns_id)) for ns_id in args.ns]
    else:
        targets = [(ns_id, _resolve_ns_name(site, ns_id) or name)
                   for ns_id, name in DEFAULT_NAMESPACES]

    os.makedirs(args.dump_dir, exist_ok=True)

    if args.list_only:
        total = 0
        for ns_id, dir_name in targets:
            print(f'\n📁 命名空间 {ns_id} ({dir_name}/)')
            titles = list_pages(site, ns_id)
            for t in titles:
                print(f'  • {t}')
            print(f'  ✅ {dir_name}/ 共 {len(titles)} 页')
            total += len(titles)
        print(f'\n🎉 共 {total} 页')
        return

    total_pages = 0
    total_size = 0
    processed_ns = 0

    for ns_id, dir_name in targets:
        output_path = os.path.join(args.dump_dir, f'{dir_name}.xml')
        print(f'\n📁 命名空间 {ns_id} ({dir_name}/) → {output_path}')

        progress_path = output_path + '.progress.json'
        if args.force:
            for p in (output_path, progress_path):
                if os.path.exists(p):
                    os.remove(p)
            print('  🧹 --force,清理旧文件', flush=True)
        elif args.skip_existing:
            progress = _load_json(progress_path)
            if progress and progress.get('done') and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                print(f'  ⏭️  skip-existing,已完成({size // 1024}kb)', flush=True)
                total_pages += progress.get('total', 0)
                total_size += size
                processed_ns += 1
                continue

        try:
            if args.mode == 'api':
                n_pages, size = export_via_api(site, ns_id, output_path,
                                                args.schema, args.delay)
            else:
                n_pages, size = export_via_special(site, ns_id, output_path,
                                                    args.history, args.delay)

            if n_pages == 0:
                print(f'  ℹ️  命名空间 {dir_name} 无页面')
                continue

            print(f'  ✅ Namespace {dir_name}: {n_pages} pages → '
                  f'{os.path.relpath(output_path)} ({size // 1024}kb)')
            total_pages += n_pages
            total_size += size
            processed_ns += 1

        except Exception as e:
            print(f'  ❌ 命名空间 {dir_name} 失败: {e}')

    print(f'\n🎉 完成!处理 {processed_ns}/{len(targets)} 个命名空间,'
          f'{total_pages} 个页面,总 {total_size // 1024} kb XML')


if __name__ == '__main__':
    main()
