#!/usr/bin/env python3
"""
批量更新分类引用为简体中文
"""
import sys
import os
import re
from typing import List, Tuple, Optional, Any
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, safe_error
from batch_processor import BatchProcessor


def update_category_ref(cat_name: str, bot: FandomBot,
                        dry_run: bool = False) -> List[Any]:
    """更新单个分类的引用，返回需要更新的页面列表"""
    try:
        pages = bot.get_category_members(cat_name)
        print(f"\n📋 更新引用 Category:{cat_name} 的页面...")
        print(f"   找到 {len(pages)} 个页面")
        return list(pages)
    except Exception as e:
        print(f"  ⚠️  获取分类成员失败: {safe_error(e)}")
        return []


def fix_page_category(page_name: str, cat_name: str, bot: FandomBot,
                      dry_run: bool = False) -> Tuple[Optional[bool], str]:
    """修复单个页面的分类引用"""
    try:
        page = bot.get_page(page_name)
        original = page.text()
        new_content = original

        # 替换分类链接
        pattern = rf'\[\[Category:{re.escape(cat_name)}\]\]'
        replacement = f'[[Category:{bot.cc.convert(cat_name)}]]'
        new_content = re.sub(pattern, replacement, new_content)

        if original != new_content:
            if dry_run:
                return True, '📝 将会修改（预览模式）'
            else:
                page.edit(new_content, summary="更新分类名称为简体中文")
                return True, '✓ 已更新'
        else:
            return None, 'ℹ️  无需修改'
    except Exception as e:
        return False, f'⚠️  失败: {safe_error(e)}'


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description='批量更新分类引用为简体中文',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "片頭曲" "片尾曲"
  %(prog)s --from-file categories.txt
  %(prog)s "片頭曲" --dry-run
        """
    )

    parser.add_argument('categories', nargs='*', help='要更新的分类名称（不含 Category: 前缀）')
    parser.add_argument('--from-file', metavar='FILE', help='从文件读取分类列表')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')

    args = parser.parse_args()

    if not args.categories and not args.from_file:
        parser.print_help()
        sys.exit(1)

    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)

    # 获取分类列表
    if args.from_file:
        try:
            with open(args.from_file, 'r', encoding='utf-8') as f:
                categories = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except Exception as e:
            print(f"❌ 读取文件失败: {safe_error(e)}")
            sys.exit(1)
    else:
        categories = args.categories

    print(f"=== 批量更新分类引用 ===")
    print(f"共 {len(categories)} 个分类\n")

    # 创建一个 BatchProcessor 复用于所有分类，跟踪总体统计
    batch = BatchProcessor(bot, dry_run=args.dry_run, delay=0.3)
    total_updated = 0
    total_failed = 0
    total_skipped = 0

    # 逐个处理分类
    for i, cat_name in enumerate(categories, 1):
        print(f"[{i}/{len(categories)}] {cat_name}")

        # 获取需要更新的页面
        pages_to_update = update_category_ref(cat_name, bot, args.dry_run)

        if not pages_to_update:
            continue

        # 使用 BatchProcessor 批量处理（不打印统计，在外部汇总）
        processor = lambda name, bot: fix_page_category(name, cat_name, bot, args.dry_run)
        batch.process_pages([p.name for p in pages_to_update], processor, show_progress=False)

        total_updated += batch.converted
        total_failed += batch.failed
        total_skipped += batch.skipped

    print(f"\n{'📊 预览' if args.dry_run else '✅ 完成'}统计:")
    print(f"  - 总分类数: {len(categories)}")
    print(f"  - {'将更新' if args.dry_run else '已更新'}: {total_updated}")
    print(f"  - 跳过: {total_skipped}")
    print(f"  - 失败: {total_failed}")

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
