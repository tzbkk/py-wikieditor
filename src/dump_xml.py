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

增量 dump (--incremental,仅 --mode special):
  - 基于 list=recentchanges API + revision ID 高水位
  - 读 .progress.json 里的 last_full_dump_* / last_incremental_* 作为 baseline
  - 产出独立 delta XML: <Namespace>.delta.<YYYYMMDD-HHMMSS>.xml (UTC,含头尾)
  - 同时产出删除/移动清单: <Namespace>.deleted.<YYYYMMDD-HHMMSS>.txt (仅有事件时)
  - 不修改原 <Namespace>.xml;仅追加 last_incremental_* 字段到 progress.json
  - recentchanges 默认 30 天窗口,超过 25 天会 warning

用法:
    python src/dump_xml.py                          # 默认下载内容命名空间,api 模式
    python src/dump_xml.py --ns 0 10 --mode api     # 指定命名空间
    python src/dump_xml.py --mode special --history # 完整历史版本
    python src/dump_xml.py --list-only              # 只列出页面,不下载
    python src/dump_xml.py --mode special --history --incremental
                                                     # 增量 dump (基于上次 full/incremental)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


def _http_get_json(session, url: str, params: dict,
                   timeout: int = 300) -> Dict[str, Any]:
    """_http_get + JSON 解析 + MediaWiki ratelimited 检测。

    MediaWiki 读 API 偶发 ratelimited 时返回 200 + errors[].code='ratelimited',
    HTTP 层抓不到,这里显式 sleep 60s 后重试,最多 MAX_RETRIES 次。
    """
    data: Dict[str, Any] = {}
    for attempt in range(MAX_RETRIES):
        r = _http_get(session, url, params, timeout)
        data = r.json() or {}
        errs = data.get('errors') or []
        if any('ratelimited' in str(e.get('code', '')).lower() for e in errs):
            print('  ⏳ 遇到速率限制,等待 60 秒...', flush=True)
            time.sleep(60)
            if attempt < MAX_RETRIES - 1:
                continue
        return data
    return data


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


def _find_max_revid_in_xml(path: str) -> int:
    """流式扫描已写好的 XML dump,返回最大的 <revision><id> 值。

    用行级状态机避免加载整个文件到内存。需区分三种 <id>:
      - <page><id>           (page id,跳过)
      - <revision><id>       (revision id,要的就是它)
      - <revision><contributor><id>  (user id,跳过 —— 远大于 revid,
                                      会污染 max)

    靠 in_revision + in_contributor 双状态:revid 必须在 revision 内但
    contributor 外。同时处理 contributor 单行(<contributor>\\n...</contributor>)
    与同行(<contributor><ip>x</ip></contributor>)两种格式。
    """
    max_id = 0
    if not os.path.exists(path):
        return max_id
    try:
        with open(path, 'r', encoding='utf-8') as f:
            in_revision = False
            in_contributor = False
            for line in f:
                stripped = line.strip()
                if stripped == '<revision>':
                    in_revision = True
                    in_contributor = False
                    continue
                if stripped == '</revision>':
                    in_revision = False
                    in_contributor = False
                    continue
                if stripped.startswith('<contributor'):
                    in_contributor = True
                    # 同行开闭(如 anon: <contributor><ip>x</ip></contributor>)
                    if '</contributor>' in stripped:
                        in_contributor = False
                    continue
                if stripped == '</contributor>':
                    in_contributor = False
                    continue
                if (in_revision and not in_contributor
                        and stripped.startswith('<id>')
                        and stripped.endswith('</id>')):
                    inner = stripped[4:-5]
                    try:
                        rid = int(inner)
                        if rid > max_id:
                            max_id = rid
                    except ValueError:
                        pass
    except OSError:
        pass
    return max_id


def _augment_full_dump_progress(output_path: str) -> None:
    """成功完成 fresh full dump 后,补充 last_full_dump_* 字段到 progress.json。

    仅当 progress.done=True 时执行;只增字段不删字段,旧 progress 不破坏。
    给后续 --incremental 模式提供 baseline。
    """
    progress_path = output_path + '.progress.json'
    progress = _load_json(progress_path)
    if not progress or not progress.get('done'):
        return
    if progress.get('last_full_dump_max_revid'):
        return
    max_revid = _find_max_revid_in_xml(output_path)
    if max_revid <= 0:
        return
    ts_raw = progress.get('timestamp')
    if isinstance(ts_raw, (int, float)) and ts_raw > 0:
        iso = datetime.fromtimestamp(
            ts_raw, tz=timezone.utc
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    progress['last_full_dump_timestamp'] = iso
    progress['last_full_dump_max_revid'] = max_revid
    _atomic_write_json(progress_path, progress)


def _fetch_recent_changes(site, ns_id: int, rcstart: str, delay: float,
                          rctype: str = 'edit|new|move',
                          log_type_filter: Optional[str] = None
                          ) -> List[Dict[str, Any]]:
    """拉 recentchanges 列表,支持 rccontinue 翻页。

    rcstart: ISO 8601 UTC 时间戳,从此时刻向 newer 方向查。
    rctype: 类型过滤,默认 'edit|new|move'。delete 事件用 rctype='log'。
    log_type_filter: 若设,从返回结果中按 logtype 字段二次过滤(防御性)。
    """
    url = _api_url(site)
    items: List[Dict[str, Any]] = []
    rccontinue: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            'action': 'query',
            'list': 'recentchanges',
            'rcnamespace': str(ns_id),
            'rcstart': rcstart,
            'rcdir': 'newer',
            'rctype': rctype,
            'rcprop': ('ids|title|timestamp|sizes|user|userid|comment|flags'
                       '|revid|old_revid|loginfo'),
            'rclimit': '500',
            'format': 'json',
        }
        if rccontinue:
            params['rccontinue'] = rccontinue
            params.pop('rcstart', None)
        data = _http_get_json(site.connection, url, params)
        batch = (data.get('query') or {}).get('recentchanges', []) or []
        items.extend(batch)
        cont = data.get('continue') or {}
        rccontinue = cont.get('rccontinue')
        if not rccontinue:
            break
        time.sleep(delay * 0.3)
    if log_type_filter:
        items = [it for it in items if it.get('logtype') == log_type_filter]
    return items


def _fetch_new_revisions(site, pageid: int, last_max_revid: int,
                         delay: float) -> List[Dict[str, Any]]:
    """拉单页面 revid > last_max_revid 的所有新 revisions。

    用 prop=revisions + rvdir=newer + rvstartid(inclusive),所以传
    last_max_revid + 1 排除已 dump 过的最后一个。rvcontinue 翻页。

    页面已删除时(API 返回 missing/invalid under key '-1'),返回空列表。
    """
    url = _api_url(site)
    revisions: List[Dict[str, Any]] = []
    rvcontinue: Optional[str] = None
    rvstartid = last_max_revid + 1
    while True:
        params: Dict[str, Any] = {
            'action': 'query',
            'pageids': str(pageid),
            'prop': 'revisions',
            'rvprop': 'ids|timestamp|user|userid|comment|content|flags|size|sha1',
            'rvlimit': '500',
            'rvdir': 'newer',
            'rvstartid': str(rvstartid),
            'format': 'json',
        }
        if rvcontinue:
            params['rvcontinue'] = rvcontinue
            params.pop('rvstartid', None)
            params.pop('rvdir', None)
        data = _http_get_json(site.connection, url, params)
        pages_dict = (data.get('query') or {}).get('pages', {}) or {}
        p = pages_dict.get(str(pageid))
        if p is None:
            if any((v.get('missing') is not None
                    or v.get('invalid') is not None)
                   for v in pages_dict.values()):
                return []
            p = {}
        revisions.extend(p.get('revisions', []) or [])
        rvcontinue = (data.get('continue') or {}).get('rvcontinue')
        if not rvcontinue:
            break
        time.sleep(delay * 0.3)
    return revisions


def export_incremental_via_special(site, ns_id: int, output_path: str,
                                    delay: float = 1.0) -> Dict[str, Any]:
    """对单个 namespace 做增量 dump,基于 recentchanges + revid 高水位。

    流程:
      1. 读 <output_path>.progress.json 的 last_full/incremental_* 作为 baseline
      2. recentchanges 拉 edit|new|move 事件,再单独拉 log type=delete 事件
      3. 按 pageid 聚合(最后事件类型胜出):
         - edit  → _fetch_new_revisions (rvstartid = last_max+1)
         - new   → _fetch_all_revisions (页面无 baseline,全拉)
         - move  → 仅记入 deleted.txt (importDump 不支持 move 语义)
      4. 写 <Namespace>.delta.<UTC ts>.xml (含 EXPORT_HEADER/FOOTER)
      5. 有删除/移动事件时,写 <Namespace>.deleted.<UTC ts>.txt
      6. 更新 progress.json 的 last_incremental_* (不动 last_full_*)

    若 progress 缺 last_full_dump_* 但 done=True 且 XML 存在,从 XML 推断 baseline
    (向后兼容旧版 progress)。否则抛 RuntimeError 提示先跑全量。

    返回 summary dict: delta_path / delta_size / deleted_path / 计数 / 新 max_revid。
    """
    progress_path = output_path + '.progress.json'
    progress = _load_json(progress_path) or {}

    last_ts = (progress.get('last_incremental_timestamp')
               or progress.get('last_full_dump_timestamp'))
    last_max_revid = int(progress.get('last_incremental_max_revid')
                         or progress.get('last_full_dump_max_revid') or 0)

    if not last_ts:
        if progress.get('done') and os.path.exists(output_path):
            max_revid = _find_max_revid_in_xml(output_path)
            if max_revid > 0:
                ts_raw = progress.get('timestamp')
                if isinstance(ts_raw, (int, float)) and ts_raw > 0:
                    iso = datetime.fromtimestamp(
                        ts_raw, tz=timezone.utc
                    ).strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                progress['last_full_dump_timestamp'] = iso
                progress['last_full_dump_max_revid'] = max_revid
                _atomic_write_json(progress_path, progress)
                last_ts = iso
                last_max_revid = max_revid
                print(f'  ℹ️  从现有 XML 推断 baseline: '
                      f'max_revid={max_revid}, ts={iso}', flush=True)

    if not last_ts:
        raise RuntimeError(
            f'命名空间 {ns_id} 缺少 last_full_dump_timestamp,无法增量。'
            f' 请先跑全量: python src/dump_xml.py --mode special --history '
            f'--ns {ns_id} --force'
        )

    try:
        last_dt = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
        age_days = (datetime.now(timezone.utc) - last_dt).days
        if age_days > 25:
            print(f'  ⚠️  last dump 距今 {age_days} 天,recentchanges 窗口'
                  f' 可能截断(MW 默认 30 天)', flush=True)
    except (ValueError, TypeError):
        pass

    print(f'  📄 拉 recentchanges since {last_ts} (ns={ns_id}) ...',
          flush=True)
    rc_items = _fetch_recent_changes(site, ns_id, last_ts, delay)
    delete_items = _fetch_recent_changes(
        site, ns_id, last_ts, delay,
        rctype='log', log_type_filter='delete',
    )
    print(f'  📊 {len(rc_items)} 个 edit/new/move 事件, '
          f'{len(delete_items)} 个 delete 事件', flush=True)

    seen: Dict[int, Dict[str, Any]] = {}
    for rc in rc_items:
        pid = rc.get('pageid') or 0
        if pid <= 0:
            continue
        seen[pid] = {
            'type': rc.get('type', ''),
            'title': rc.get('title', ''),
            'old_revid': rc.get('old_revid'),
            'revid': rc.get('revid'),
        }

    max_revid_seen = last_max_revid
    delta_chunks: List[Tuple[int, str, List[Dict[str, Any]]]] = []
    deleted_lines: List[str] = []
    n_new_revisions = 0

    for pid, info in seen.items():
        title = info['title']
        rctype = info['type']
        if rctype == 'move':
            deleted_lines.append(
                f'{title}\t# move event (pageid={pid}, '
                f'old_revid={info.get("old_revid")}, manual handling)'
            )
            continue
        try:
            if rctype == 'new':
                revs = _fetch_all_revisions(site, pid, delay)
            else:
                revs = _fetch_new_revisions(site, pid, last_max_revid, delay)
        except Exception as e:
            print(f'  ❌ pageid={pid} ({title}) 拉取失败: {e}', flush=True)
            continue

        if not revs:
            deleted_lines.append(
                f'{title}\t# no new revisions (pageid={pid}, likely deleted)'
            )
            continue

        revs.sort(key=lambda r: r.get('revid', 0))
        for r in revs:
            rid = int(r.get('revid', 0) or 0)
            if rid > max_revid_seen:
                max_revid_seen = rid

        delta_chunks.append((pid, title, revs))
        n_new_revisions += len(revs)
        print(f'  ✅ {title}: +{len(revs)} revs', flush=True)
        time.sleep(delay)

    for d in delete_items:
        title = d.get('title', '')
        logtype = d.get('logtype', 'delete')
        logaction = d.get('logaction', '')
        logid = d.get('logid', '')
        deleted_lines.append(
            f'{title}\t# log {logtype}/{logaction} (logid={logid})'
        )

    now = datetime.now(timezone.utc)
    ts_file = now.strftime('%Y%m%d-%H%M%S')
    iso_ts = now.strftime('%Y-%m-%dT%H:%M:%SZ')

    dump_dir = os.path.dirname(output_path) or '.'
    base = os.path.basename(output_path)
    if base.endswith('.xml'):
        base = base[:-4]
    delta_path = os.path.join(dump_dir, f'{base}.delta.{ts_file}.xml')

    with open(delta_path, 'w', encoding='utf-8') as f:
        f.write(EXPORT_HEADER)
        _fsync_file(f)
        for pid, title, revs in delta_chunks:
            f.write(_build_page_xml(pid, title, ns_id, revs))
            f.write('\n')
            _fsync_file(f)
        f.write(EXPORT_FOOTER)
        _fsync_file(f)
    delta_size = os.path.getsize(delta_path)

    deleted_path: Optional[str] = None
    if deleted_lines:
        deleted_path = os.path.join(dump_dir, f'{base}.deleted.{ts_file}.txt')
        with open(deleted_path, 'w', encoding='utf-8') as f:
            for line in sorted(set(deleted_lines)):
                f.write(line + '\n')
            _fsync_file(f)

    progress['last_incremental_timestamp'] = iso_ts
    progress['last_incremental_max_revid'] = max_revid_seen
    _atomic_write_json(progress_path, progress)

    return {
        'delta_path': delta_path,
        'delta_size': delta_size,
        'deleted_path': deleted_path,
        'n_changed_pages': len(delta_chunks),
        'n_new_revisions': n_new_revisions,
        'n_deleted': len(deleted_lines),
        'new_max_revid': max_revid_seen,
        'timestamp': iso_ts,
    }


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
    parser.add_argument('--incremental', action='store_true',
                        help='增量 dump 模式(仅 --mode special): 基于 '
                             'recentchanges + revid 高水位,产出 '
                             '<NS>.delta.<ts>.xml 独立文件')
    args = parser.parse_args()

    if args.incremental and args.mode != 'special':
        print('⚠️  --incremental 仅支持 --mode special(api 模式无完整历史)。'
              '请加 --mode special。')
        sys.exit(1)

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
    total_delta_revs = 0
    total_deleted = 0

    for ns_id, dir_name in targets:
        output_path = os.path.join(args.dump_dir, f'{dir_name}.xml')
        print(f'\n📁 命名空间 {ns_id} ({dir_name}/) → {output_path}')

        progress_path = output_path + '.progress.json'

        if args.incremental:
            try:
                result = export_incremental_via_special(
                    site, ns_id, output_path, args.delay,
                )
                processed_ns += 1
                total_pages += result['n_changed_pages']
                total_size += result['delta_size']
                total_delta_revs += result['n_new_revisions']
                total_deleted += result['n_deleted']
                print(f"  ✅ {dir_name} delta: {result['n_changed_pages']} 页, "
                      f"+{result['n_new_revisions']} revs → "
                      f"{os.path.relpath(result['delta_path'])} "
                      f"({result['delta_size'] // 1024}kb)")
                if result['deleted_path']:
                    print(f"  🗑️  删除/移动清单: "
                          f"{os.path.relpath(result['deleted_path'])} "
                          f"({result['n_deleted']} 项)")
                print(f"  📊 新 max_revid: {result['new_max_revid']}")
            except Exception as e:
                print(f'  ❌ 命名空间 {dir_name} 增量失败: {e}')
            continue

        if args.force:
            for p in (output_path, progress_path):
                if os.path.exists(p):
                    os.remove(p)
            print('  🧹 --force,清理旧文件', flush=True)
        elif args.skip_existing:
            progress = _load_json(progress_path)
            if progress and progress.get('done') and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                if ('last_full_dump_max_revid' not in progress
                        and args.mode == 'special'):
                    _augment_full_dump_progress(output_path)
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
                if n_pages > 0:
                    _augment_full_dump_progress(output_path)

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

    if args.incremental:
        print(f'\n🎉 增量完成!处理 {processed_ns}/{len(targets)} 个命名空间,'
              f'{total_pages} 个变更页,+{total_delta_revs} 个新 revision,'
              f'{total_deleted} 个删除/移动事件,'
              f'总 {total_size // 1024} kb delta XML')
    else:
        print(f'\n🎉 完成!处理 {processed_ns}/{len(targets)} 个命名空间,'
              f'{total_pages} 个页面,总 {total_size // 1024} kb XML')


if __name__ == '__main__':
    main()
