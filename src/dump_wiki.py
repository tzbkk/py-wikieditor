#!/usr/bin/env python3
"""下载 Wiki 页面到本地 wiki_dump/ 目录（全量或增量模式）。

按命名空间分类存放 .wiki 文件，并生成 index.json 索引。
仅读操作，不修改任何 Wiki 页面。

模式:
    全量（默认）: 通过 list=allpages 遍历所有页面，写入 .wiki + index.json
    增量（--incremental）: 基于 list=recentchanges 拉自上次 dump 以来的变更，
                          直接覆盖本地 .wiki 文件（仅最新版本，无历史），
                          并维护 _meta.last_dump_timestamp

index.json 格式（schema v2）:
    {
        "_meta": {
            "schema_version": 2,
            "dump_mode": "full|incremental",
            "last_dump_timestamp": "2026-07-25T10:30:00Z"
        },
        "<title>": {
            "ns": 0,
            "ns_dir": "main",
            "file": "main/foo.wiki",
            "length": 1234,
            "touched": "2026-07-25T10:00:00Z"
        },
        ...
    }

向下兼容: 读取旧格式 index.json（无 _meta）时自动识别；全量模式自动升级；
         增量模式要求 _meta.last_dump_timestamp 必须存在，否则报错并提示先跑一次全量。

用法:
    python src/dump_wiki.py                            # 全量 dump 默认命名空间
    python src/dump_wiki.py --ns 0 10                  # 指定命名空间
    python src/dump_wiki.py --list-only                # 只列出页面标题
    python src/dump_wiki.py --skip-existing            # 全量断点续传
    python src/dump_wiki.py --dump-dir /path           # 自定义输出目录
    python src/dump_wiki.py --incremental              # 增量 dump（基于 recentchanges）
    python src/dump_wiki.py --incremental --ns 0       # 增量仅指定 ns
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot


# 默认下载的内容命名空间：(ns_id, 本地目录名)
DEFAULT_NAMESPACES = [
    (0,   'main'),
    (10,  'Template'),
    (14,  'Category'),
    (828, 'Module'),
    (4,   'Project'),
]

DUMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wiki_dump')

# 增量 dump 相关常量
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
RECENT_CHANGES_LIMIT = 500
RC_WINDOW_WARN_DAYS = 25  # recentchanges 默认 30 天窗口，>25 天警告
INDEX_SCHEMA_VERSION = 2
RATE_LIMIT_SLEEP = 60


def title_to_relpath(page_title: str) -> str:
    """把纯页面名（不含命名空间前缀）转成相对文件路径。

    子页面分隔符 '/' 保留为子目录，其余字符直接使用（Linux 下均合法）。
    """
    return page_title.replace('\\', '_') + '.wiki'


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def _api_url(site) -> str:
    """构造 site 的 api.php URL。"""
    return f'{site.scheme}://{site.host}{site.path}api.php'


def _http_get(session, url: str, params: dict, timeout: int = 300):
    """带重试的 GET 请求，指数退避，最多 MAX_RETRIES 次。

    仿照 dump_xml.py 的模式独立实现，本文件自包含。
    """
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
                print(f'  ⚠️  GET 失败({e.__class__.__name__}), {wait}s 后重试', flush=True)
                time.sleep(wait)
    raise last_err


def _now_utc_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串（带 Z 后缀）。"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _check_rc_window(ts_str: str) -> None:
    """如果 ts_str 距今超过 RC_WINDOW_WARN_DAYS 天，打印 recentchanges 30 天窗口警告。"""
    try:
        ts = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return
    age_days = (datetime.now(timezone.utc) - ts).days
    if age_days > RC_WINDOW_WARN_DAYS:
        print(f'⚠️  last_dump_timestamp 距今 {age_days} 天，'
              f'超过 recentchanges 默认 30 天窗口，可能丢数据！建议先跑一次全量 dump。')


def _load_index(dump_dir: str) -> Dict:
    """读取 index.json；不存在或解析失败返回空 dict。"""
    idx_path = os.path.join(dump_dir, 'index.json')
    if not os.path.exists(idx_path):
        return {}
    try:
        with open(idx_path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        print('⚠️  index.json 不是 dict，视为空索引')
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f'⚠️  index.json 解析失败: {e}，视为空索引')
        return {}


def _save_index(dump_dir: str, index: Dict) -> None:
    """原子写 index.json（先写 .tmp 再 rename，避免半写状态）。

    Sanity check: _meta 是保留键，其它以 '_' 开头的键视为异常并发出警告
    （mwclient 命名约束下真实页面不会以 _ 开头）。
    """
    reserved = [k for k in index if k.startswith('_') and k != '_meta']
    if reserved:
        print(f'⚠️  index.json 出现非 _meta 的下划线键: {reserved}，可能数据异常')
    idx_path = os.path.join(dump_dir, 'index.json')
    tmp_path = idx_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, idx_path)


def _page_touched_iso(page) -> str:
    """从 mwclient Page 读取最新 revision 时间戳并格式化为 ISO 8601。

    page.text() 调用后，mwclient 把 rev['timestamp'] 存到 page.last_rev_time
    （time.struct_time）。此函数转回 'YYYY-MM-DDTHH:MM:SSZ' 字符串。失败返回 ''。
    """
    last_rev = getattr(page, 'last_rev_time', None)
    if last_rev is None:
        return ''
    try:
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', last_rev)
    except (TypeError, ValueError):
        return ''


# ---------------------------------------------------------------------------
# 增量 dump: recentchanges / deletions / moves 拉取
# ---------------------------------------------------------------------------

def _fetch_recent_changes(site, ns_id: int, rcstart: str) -> List[dict]:
    """拉 recentchanges（rctype=edit|new|move）原始 item 列表。

    通过 rcstart + rcdir=newer 自上次 dump 时间向现在方向翻页拉，
    每页 RECENT_CHANGES_LIMIT 条，循环直到 response 无 rccontinue。
    """
    url = _api_url(site)
    items: List[dict] = []
    rccontinue: Optional[str] = None
    while True:
        params: Dict[str, str] = {
            'action': 'query',
            'list': 'recentchanges',
            'rcnamespace': str(ns_id),
            'rcstart': rcstart,
            'rcdir': 'newer',
            'rctype': 'edit|new|move',
            'rcprop': 'ids|title|timestamp|sizes|user|flags',
            'rclimit': str(RECENT_CHANGES_LIMIT),
            'format': 'json',
        }
        if rccontinue:
            params['rccontinue'] = rccontinue
        r = _http_get(site.connection, url, params)
        data = r.json()
        batch = (data.get('query') or {}).get('recentchanges') or []
        items.extend(batch)
        rccontinue = (data.get('continue') or {}).get('rccontinue')
        if not rccontinue:
            break
        time.sleep(0.2)
    return items


def _fetch_deletions(site, ns_id: int, rcstart: str) -> List[str]:
    """拉 recentchanges 删除事件（rctype=log 过滤 rc_log_type=delete & action=delete）。

    返回被删除的页面 full title 列表（可能含重复，调用方负责去重）。
    单独走 rctype=log 而非 rctype=edit|new|move|log，避免与编辑事件混淆。
    """
    url = _api_url(site)
    titles: List[str] = []
    rccontinue: Optional[str] = None
    while True:
        params: Dict[str, str] = {
            'action': 'query',
            'list': 'recentchanges',
            'rcnamespace': str(ns_id),
            'rcstart': rcstart,
            'rcdir': 'newer',
            'rctype': 'log',
            'rcprop': 'title|timestamp|ids|user',
            'rclimit': str(RECENT_CHANGES_LIMIT),
            'format': 'json',
        }
        if rccontinue:
            params['rccontinue'] = rccontinue
        r = _http_get(site.connection, url, params)
        data = r.json()
        for item in (data.get('query') or {}).get('recentchanges') or []:
            if (item.get('rc_log_type') == 'delete'
                    and item.get('rc_log_action') == 'delete'):
                full = item.get('title') or item.get('rc_title', '')
                if full:
                    titles.append(full)
        rccontinue = (data.get('continue') or {}).get('rccontinue')
        if not rccontinue:
            break
        time.sleep(0.2)
    return titles


def _fetch_moves(site, ns_id: int, lestart: str) -> List[Tuple[str, str]]:
    """拉 logevents letype=move 移动事件，返回 [(from_title, to_title), ...]。

    lenamespace=ns_id 按源 ns 过滤，ledir=newer 自上次 dump 时间向现在方向翻页，
    循环直到无 lecontinue。移动事件的 from 在 log item 的 title 字段，
    to 在 params.target_title（MediaWiki 1.25+）或旧字段 moveto。
    """
    url = _api_url(site)
    moves: List[Tuple[str, str]] = []
    lecontinue: Optional[str] = None
    while True:
        params: Dict[str, str] = {
            'action': 'query',
            'list': 'logevents',
            'letype': 'move',
            'lenamespace': str(ns_id),
            'lestart': lestart,
            'ledir': 'newer',
            'lelimit': str(RECENT_CHANGES_LIMIT),
            'leprop': 'type|title|timestamp|details',
            'format': 'json',
        }
        if lecontinue:
            params['lecontinue'] = lecontinue
        r = _http_get(site.connection, url, params)
        data = r.json()
        for item in (data.get('query') or {}).get('logevents') or []:
            from_title = item.get('title', '')
            params_dict = item.get('params', {}) or {}
            to_title = (params_dict.get('target_title', '')
                        or params_dict.get('moveto', ''))
            if from_title and to_title:
                moves.append((from_title, to_title))
        lecontinue = (data.get('continue') or {}).get('lecontinue')
        if not lecontinue:
            break
        time.sleep(0.2)
    return moves


# ---------------------------------------------------------------------------
# 文件 / index 操作
# ---------------------------------------------------------------------------

def _write_page_file(dump_dir: str, dir_name: str, page_title: str,
                     text: str) -> Tuple[str, str]:
    """写 .wiki 文件到 dump_dir/dir_name/<page_title>.wiki。

    自动创建子目录。返回 (abs_path, rel_path relative to dump_dir)。
    """
    abs_path = os.path.join(dump_dir, dir_name, title_to_relpath(page_title))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return abs_path, os.path.relpath(abs_path, dump_dir)


def _remove_page_file(dump_dir: str, file_rel: str) -> bool:
    """删除 .wiki 文件（基于 index 中记录的相对路径）；不存在返回 False。"""
    if not file_rel:
        return False
    abs_path = os.path.join(dump_dir, file_rel)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
            return True
        except OSError as e:
            print(f'  ❌ 删除文件失败 {abs_path}: {e}')
            return False
    return False


# ---------------------------------------------------------------------------
# 增量主流程
# ---------------------------------------------------------------------------

def _refresh_page_incremental(site, index: Dict, dump_dir: str, title: str,
                              ns_id: int, dir_name: str,
                              stats: Dict[str, int]) -> None:
    """重新拉单个 title 的内容覆盖本地 .wiki 文件，更新 index 条目。

    若 API 显示页面已不存在，从 index 移除并删除本地文件。
    单页失败不中断：ratelimited 自动 sleep 60s 重试一次，其它异常打印 ❌ 后继续。
    """
    page = site.pages[title]  # 1 次 API 调用 (prop=info)
    if not page.exists:
        if title in index:
            info = index[title]
            if _remove_page_file(dump_dir, info.get('file', '')):
                stats['files_deleted'] += 1
            del index[title]
            print(f'  ➖ 已删除: {title}')
        else:
            print(f'  ⏭️  本地无此页面，跳过: {title}')
        return

    try:
        text = page.text()  # 1 次 API 调用 (prop=revisions)
    except Exception as e:
        if 'ratelimited' in str(e).lower():
            print('  ⏳ 遇到速率限制，等待 60 秒...')
            time.sleep(RATE_LIMIT_SLEEP)
            try:
                text = page.text()
            except Exception as e2:
                print(f'  ❌ 读取失败 {title}: {e2}')
                return
        else:
            print(f'  ❌ 读取失败 {title}: {e}')
            return

    touched = _page_touched_iso(page)
    page_title = page.page_title
    is_new = title not in index

    _, rel = _write_page_file(dump_dir, dir_name, page_title, text)
    index[title] = {
        'ns': ns_id,
        'ns_dir': dir_name,
        'file': rel,
        'length': len(text),
        'touched': touched,
    }
    if is_new:
        stats['files_added'] += 1
        print(f'  ➕ 新页面: {title}')
    else:
        stats['files_updated'] += 1
        print(f'  ✏️  更新: {title}')


def _apply_incremental(site, dump_dir: str, targets: List[Tuple[int, str]],
                       old_ts: str, list_only: bool = False
                       ) -> Tuple[Dict, Dict[str, int]]:
    """增量 dump 主流程：返回 (updated_index, stats)。

    每个 target ns 独立拉一次 recentchanges（edit|new|move）+ deletions + moves：
      - edit/new/move 的 title → 重新拉 page.text() 覆盖本地
      - delete 的 title → 删除本地 .wiki 文件 + 移出 index
      - move 的 from_title → 删除本地源文件（目标已由 recentchanges 阶段刷新）
    """
    index = _load_index(dump_dir)
    stats: Dict[str, int] = {
        'edit': 0, 'new': 0, 'move': 0, 'delete': 0,
        'files_added': 0, 'files_updated': 0, 'files_deleted': 0,
        'ns_processed': 0,
    }

    for ns_id, dir_name in targets:
        print(f'\n📁 命名空间 {ns_id} ({dir_name}/)')

        rc_items = _fetch_recent_changes(site, ns_id, old_ts)
        deletions = _fetch_deletions(site, ns_id, old_ts)
        moves = _fetch_moves(site, ns_id, old_ts)

        # 同 title 去重（保留最新一条事件，避免对同一页面重复刷新）
        latest_by_title: Dict[str, dict] = {}
        for item in rc_items:
            t = item.get('title', '')
            if t:
                latest_by_title[t] = item

        # 处理 edit|new|move（recentchanges 中 move 的 title 是新 title）
        for title, item in latest_by_title.items():
            rctype = item.get('type', '')
            if rctype == 'new':
                stats['new'] += 1
            elif rctype == 'edit':
                stats['edit'] += 1
            elif rctype == 'move':
                stats['move'] += 1
            else:
                continue

            if list_only:
                print(f'  • [{rctype}] {title}')
                continue

            _refresh_page_incremental(site, index, dump_dir, title,
                                      ns_id, dir_name, stats)

        # 处理 delete（rc_log_type=delete & rc_log_action=delete）
        seen_del: set = set()
        for title in deletions:
            if title in seen_del:
                continue
            seen_del.add(title)
            stats['delete'] += 1
            if list_only:
                print(f'  • [delete] {title}')
                continue
            if title in index:
                info = index[title]
                if _remove_page_file(dump_dir, info.get('file', '')):
                    stats['files_deleted'] += 1
                del index[title]
                print(f'  ➖ 已删除: {title}')

        # 处理 move（清理源文件，目标由 recentchanges 阶段已刷新）
        for from_title, to_title in moves:
            if list_only:
                print(f'  • [move] {from_title} → {to_title}')
                continue
            if from_title in index:
                info = index[from_title]
                if _remove_page_file(dump_dir, info.get('file', '')):
                    stats['files_deleted'] += 1
                del index[from_title]
                print(f'  ↪️  移走源文件: {from_title} → {to_title}')

        stats['ns_processed'] += 1

    return index, stats


def _run_incremental_dump(site, dump_dir: str, targets: List[Tuple[int, str]],
                          list_only: bool) -> None:
    """增量 dump 入口：读 _meta.last_dump_timestamp → 处理变更 → 更新时间戳。

    顺序：先记录 old_ts，做完整轮询（用 old_ts 作为 rcstart），
    全成功后才写 new_ts；避免半成功状态丢失时间锚点。
    """
    raw_index = _load_index(dump_dir)
    meta = raw_index.get('_meta')
    old_ts = (meta.get('last_dump_timestamp')
              if isinstance(meta, dict) else None)

    if not old_ts:
        print('❌ index.json 缺少 _meta.last_dump_timestamp。')
        print('   请先运行一次全量 dump（不带 --incremental）建立基线。')
        sys.exit(1)

    print(f'🕐 增量起点: {old_ts}')
    _check_rc_window(old_ts)

    os.makedirs(dump_dir, exist_ok=True)
    index, stats = _apply_incremental(site, dump_dir, targets, old_ts,
                                      list_only=list_only)

    if list_only:
        print('\n📋 --list-only 模式，未写入任何文件')
        print(f'\n🎉 完成！扫描 {stats["ns_processed"]} 个命名空间')
        return

    # 全部成功后再更新 _meta（避免半成功状态丢失时间锚点）
    new_ts = _now_utc_iso()
    index.setdefault('_meta', {})
    index['_meta']['schema_version'] = INDEX_SCHEMA_VERSION
    index['_meta']['dump_mode'] = 'incremental'
    index['_meta']['last_dump_timestamp'] = new_ts
    _save_index(dump_dir, index)

    # 总结打印
    print('\n' + '=' * 60)
    print('📊 增量 dump 总结')
    print('=' * 60)
    print(f'命名空间处理数: {stats["ns_processed"]}')
    print(f'变更事件: edit={stats["edit"]} new={stats["new"]} '
          f'move={stats["move"]} delete={stats["delete"]}')
    print(f'本地文件: 新增={stats["files_added"]} 更新={stats["files_updated"]} '
          f'删除={stats["files_deleted"]}')
    print(f'新 last_dump_timestamp: {new_ts}')


# ---------------------------------------------------------------------------
# 全量主流程（保留原行为 + 新增 _meta + touched）
# ---------------------------------------------------------------------------

def _run_full_dump(site, dump_dir: str, targets: List[Tuple[int, str]],
                   list_only: bool, skip_existing: bool) -> None:
    """全量 dump：site.allpages 遍历 + 写 .wiki + 写 index.json（含 _meta）。

    保留原有行为（按 ns 迭代 allpages、断点续传、list-only），
    仅在写 index 时新增 _meta 字段和每个页面条目的 touched 字段。
    """
    os.makedirs(dump_dir, exist_ok=True)
    index: Dict[str, dict] = {}
    total = 0

    for ns_id, dir_name in targets:
        out_dir = os.path.join(dump_dir, dir_name)
        print(f'\n📁 命名空间 {ns_id} ({dir_name}/)')

        count = 0
        for page in site.allpages(namespace=ns_id):
            full_title = page.name          # 含命名空间前缀，作为索引键
            page_title = page.page_title    # 纯名，不含前缀
            total += 1

            if list_only:
                print(f'  • {full_title}')
                count += 1
                continue

            rel = title_to_relpath(page_title)
            abs_path = os.path.join(out_dir, rel)

            # 断点续传：已存在且非空则跳过 API 请求（touched 留空，下次增量会刷新）
            if skip_existing and os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    existing_text = f.read()
                index[full_title] = {
                    'ns': ns_id,
                    'ns_dir': dir_name,
                    'file': os.path.relpath(abs_path, dump_dir),
                    'length': len(existing_text),
                    'touched': '',
                }
                count += 1
                continue

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            try:
                text = page.text()
                touched = _page_touched_iso(page)
            except Exception as e:
                if 'ratelimited' in str(e).lower():
                    print('  ⏳ 遇到速率限制，等待 60 秒...')
                    time.sleep(RATE_LIMIT_SLEEP)
                    try:
                        text = page.text()
                        touched = _page_touched_iso(page)
                    except Exception as e2:
                        print(f'  ❌ 读取失败 {full_title}: {e2}')
                        continue
                else:
                    print(f'  ❌ 读取失败 {full_title}: {e}')
                    continue

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(text)

            index[full_title] = {
                'ns': ns_id,
                'ns_dir': dir_name,
                'file': os.path.relpath(abs_path, dump_dir),
                'length': len(text),
                'touched': touched,
            }
            count += 1
            if count % 50 == 0:
                print(f'  … 已处理 {count} 页')

        print(f'  ✅ {dir_name}/ 共 {count} 页')

    if not list_only:
        index['_meta'] = {
            'schema_version': INDEX_SCHEMA_VERSION,
            'dump_mode': 'full',
            'last_dump_timestamp': _now_utc_iso(),
        }
        _save_index(dump_dir, index)
        idx_path = os.path.join(dump_dir, 'index.json')
        n_pages = max(0, len(index) - 1)  # 减去 _meta
        print(f'\n📋 索引已写入 {os.path.relpath(idx_path)}（{n_pages} 个页面）')

    print(f'\n🎉 完成！共处理 {total} 个页面')


def main():
    parser = argparse.ArgumentParser(
        description='下载 Wiki 页面到本地 wiki_dump/ 目录（全量或增量）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--ns', type=int, nargs='+',
                        help='指定命名空间 ID（默认下载内容命名空间）')
    parser.add_argument('--list-only', action='store_true',
                        help='只列出页面标题，不下载内容（增量模式下列出变更事件）')
    parser.add_argument('--skip-existing', action='store_true',
                        help='跳过已存在且非空的本地文件（断点续传；仅全量模式生效）')
    parser.add_argument('--dump-dir', default=DUMP_DIR,
                        help=f'输出目录（默认: {DUMP_DIR}）')
    parser.add_argument('--incremental', action='store_true',
                        help='增量模式：基于 index.json 的 _meta.last_dump_timestamp '
                             '拉 recentchanges 增量更新（需先跑一次全量 dump 建立基线）')
    args = parser.parse_args()

    print('🔗 连接 Wiki ...')
    bot = FandomBot()
    site = bot.site
    print(f'✓ 已登录: {site.username}')

    # 选择命名空间
    if args.ns:
        targets = [(ns_id, str(site.namespaces.get(ns_id, '')) or f'ns{ns_id}')
                   for ns_id in args.ns]
    else:
        targets = list(DEFAULT_NAMESPACES)

    if args.incremental:
        if args.skip_existing:
            print('ℹ️  --skip-existing 在增量模式下无效，忽略')
        _run_incremental_dump(site, args.dump_dir, targets, args.list_only)
    else:
        _run_full_dump(site, args.dump_dir, targets,
                       args.list_only, args.skip_existing)


if __name__ == '__main__':
    main()
