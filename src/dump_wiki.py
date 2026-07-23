#!/usr/bin/env python3
"""下载 Wiki 页面到本地 wiki_dump/ 目录。

按命名空间分类存放，并生成 wiki_dump/index.json 索引。
仅读操作，不修改任何 Wiki 页面。

用法：
    python src/dump_wiki.py                 # 下载默认内容命名空间
    python src/dump_wiki.py --ns 0 10       # 指定命名空间 ID
    python src/dump_wiki.py --list-only     # 只列出页面，不下载内容
"""

import sys
import os
import json
import argparse

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


def title_to_relpath(page_title: str) -> str:
    """把纯页面名（不含命名空间前缀）转成相对文件路径。

    子页面分隔符 '/' 保留为子目录，其余字符直接使用（Linux 下均合法）。
    """
    return page_title.replace('\\', '_') + '.wiki'


def main():
    parser = argparse.ArgumentParser(
        description='下载 Wiki 页面到本地 wiki_dump/ 目录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--ns', type=int, nargs='+', help='指定命名空间 ID（默认下载内容命名空间）')
    parser.add_argument('--list-only', action='store_true', help='只列出页面标题，不下载内容')
    parser.add_argument('--skip-existing', action='store_true', help='跳过已存在且非空的本地文件（断点续传）')
    parser.add_argument('--dump-dir', default=DUMP_DIR, help='输出目录（默认 wiki_dump/）')
    args = parser.parse_args()

    print("🔗 连接 Wiki ...")
    bot = FandomBot()
    site = bot.site
    print(f"✓ 已登录: {site.username}")

    # 选择命名空间
    if args.ns:
        targets = [(ns_id, str(site.namespaces.get(ns_id, '')) or f'ns{ns_id}')
                   for ns_id in args.ns]
    else:
        targets = list(DEFAULT_NAMESPACES)

    os.makedirs(args.dump_dir, exist_ok=True)
    index = {}
    total = 0

    for ns_id, dir_name in targets:
        out_dir = os.path.join(args.dump_dir, dir_name)
        print(f"\n📁 命名空间 {ns_id} ({dir_name}/)")

        count = 0
        for page in site.allpages(namespace=ns_id):
            full_title = page.name          # 含命名空间前缀，作为索引键
            page_title = page.page_title    # 纯名，不含前缀
            total += 1

            if args.list_only:
                print(f"  • {full_title}")
                count += 1
                continue

            rel = title_to_relpath(page_title)
            abs_path = os.path.join(out_dir, rel)

            # 断点续传：已存在且非空则跳过 API 请求
            if args.skip_existing and os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    length = len(f.read())
                index[full_title] = {
                    'ns': ns_id,
                    'ns_dir': dir_name,
                    'file': os.path.relpath(abs_path, args.dump_dir),
                    'length': length,
                }
                count += 1
                continue

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            try:
                text = page.text()
            except Exception as e:
                print(f"  ❌ 读取失败 {full_title}: {e}")
                continue

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(text)

            index[full_title] = {
                'ns': ns_id,
                'ns_dir': dir_name,
                'file': os.path.relpath(abs_path, args.dump_dir),
                'length': len(text),
            }
            count += 1
            if count % 50 == 0:
                print(f"  … 已处理 {count} 页")

        print(f"  ✅ {dir_name}/ 共 {count} 页")

    if not args.list_only:
        index_path = os.path.join(args.dump_dir, 'index.json')
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"\n📋 索引已写入 {os.path.relpath(index_path)}（{len(index)} 个页面）")

    print(f"\n🎉 完成！共处理 {total} 个页面")


if __name__ == '__main__':
    main()
