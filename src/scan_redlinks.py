#!/usr/bin/env python3
"""扫描全 Wiki 的红链（指向不存在页面的链接）。

读取 wiki_dump/index.json，用其中记录的 file 字段定位每个页面文件，
扫描所有 [[链接]]，检查目标页面是否存在，输出红链报告。

用法：
    python src/scan_redlinks.py              # 打印报告
    python src/scan_redlinks.py -o report.txt # 写入文件
"""

import sys
import os
import re
import json
import argparse
from collections import defaultdict

DUMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wiki_dump')

# 跳过的链接前缀（非主空间链接、跨语言链接、外部链接）
SKIP_PREFIXES = (
    'file:', 'image:', 'media:', 'category:', 'en:', 'vi:', 'ko:',
    'special:', 'template:', 'help:', 'module:', 'mediawiki:',
    'project:', 'w:', 'wikipedia:', 'zh:', 'ja:', 'fr:', 'de:',
    'es:', 'it:', 'pt:',
)


def main():
    parser = argparse.ArgumentParser(
        description='扫描全 Wiki 的红链',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-o', '--output', help='输出到文件（默认打印到终端）')
    parser.add_argument('--dump-dir', default=DUMP_DIR, help='dump 目录路径')
    args = parser.parse_args()

    index_path = os.path.join(args.dump_dir, 'index.json')
    with open(index_path, encoding='utf-8') as f:
        idx = json.load(f)

    existing_pages = set(idx.keys())
    red_links = defaultdict(set)  # redlink_target -> {source_page, ...}

    # 过滤噪声源
    NOISE_SUFFIXES = ('/doc', '/preload', '/test', '/testcase', '/sandbox')
    NOISE_PAGES = {'擅长捉弄的高木同学wiki:沙盒'}
    # 工具/框架模板（含示例链接，非内容页面）
    NOISE_TEMPLATES = {
        'Template:Lang', 'Template:StructuredQuote', 'Template:区分',
        'Template:重定向', 'Template:DiscordWidget', 'Template:新闻模块',
        'Template:PortalDesign', 'Template:Documentation',
        'Template:高木漫画章节链接', 'Template:Fallback',
    }
    NOISE_TEMPLATE_PREFIXES = (
        'Template:Languages/', 'Template:Editnotice/',
    )

    for title, info in sorted(idx.items()):
        # 跳过噪声页面
        if any(title.endswith(s) for s in NOISE_SUFFIXES):
            continue
        if title in NOISE_PAGES or title in NOISE_TEMPLATES:
            continue
        if any(title.startswith(p) for p in NOISE_TEMPLATE_PREFIXES):
            continue
        # 跳过 Module 命名空间（代码中的 [[...]] 不是页面链接）
        if info.get('ns') == 828:
            continue

        # 用 index.json 的 file 字段定位文件，兜底用 ns_dir + title
        rel_path = info.get('file', '')
        if rel_path:
            path = os.path.join(args.dump_dir, rel_path)
        else:
            path = os.path.join(args.dump_dir, info.get('ns_dir', 'main'), title + '.wiki')

        if not os.path.exists(path):
            continue

        with open(path, encoding='utf-8') as f:
            text = f.read()

        # 匹配所有 [[target]] 或 [[target|display]] 链接
        for m in re.finditer(r'\[\[([^|\]#:]+)(?:\|[^\]]*)?\]\]', text):
            target = m.group(1).strip()
            if target.lower().startswith(SKIP_PREFIXES):
                continue
            if target not in existing_pages and target != title:
                red_links[target].add(title)

    # 分类
    cats = {
        "原高木漫画卷": [],
        "原高木漫画章节": [],
        "由加里漫画卷": [],
        "漫画章节(.X附录)": [],
        "人物/角色": [],
        "作品/衍生": [],
        "其他": [],
    }
    for target in red_links:
        srcs = sorted(red_links[target])
        entry = (target, len(srcs), srcs)
        if re.match(r'原高木漫画第\d+卷$', target):
            cats["原高木漫画卷"].append(entry)
        elif re.match(r'原高木漫画第[\d.]+章$', target):
            cats["原高木漫画章节"].append(entry)
        elif re.match(r'由加里漫画第\d+卷$', target):
            cats["由加里漫画卷"].append(entry)
        elif re.match(r'漫画第[\d.]+章$', target):
            cats["漫画章节(.X附录)"].append(entry)
        elif len(target) <= 6:
            cats["人物/角色"].append(entry)
        elif '捉弄' in target or 'からかい' in target:
            cats["作品/衍生"].append(entry)
        else:
            cats["其他"].append(entry)

    # 输出
    lines = []
    lines.append(f"全 Wiki 红链报告（共 {len(red_links)} 个）")
    lines.append(f"扫描页面数: {len(idx)}")
    lines.append("")

    for cat_name, items in cats.items():
        if not items:
            continue
        items.sort(key=lambda x: (-x[1], x[0]))
        lines.append(f"{'=' * 50}")
        lines.append(f" {cat_name}（{len(items)}个）")
        lines.append(f"{'=' * 50}")
        for target, cnt, srcs in items:
            src_str = ', '.join(srcs[:4])
            if len(srcs) > 4:
                src_str += f' 等{cnt}个'
            lines.append(f"  {target} ({cnt}次) ← {src_str}")
        lines.append("")

    output = '\n'.join(lines)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 报告已写入 {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
