#!/usr/bin/env python3
"""
移动 category 页面的完整流程

按照规矩：
1. 先更新所有引用该 category 的页面
2. 然后移动 category 页面本身
"""

import sys
import os
import time
from typing import Tuple, Any
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, safe_error


def update_category_links(old_name: str, new_name: str, bot: FandomBot,
                          cat_page: Any = None, dry_run: bool = False) -> Tuple[int, int]:
    """更新所有引用该 category 的页面"""
    print(f"\n📋 步骤 1/2: 更新引用 Category:{old_name} 的页面...")

    # 复用已有的 cat_page 对象，避免重复 API 调用
    if cat_page is None:
        cat_page = bot.get_page(f"Category:{old_name}")
    if not cat_page.exists:
        print(f"❌ Category:{old_name} 不存在")
        return 0, 0

    # 获取所有成员页面
    try:
        members = list(cat_page.members())
        print(f"   找到 {len(members)} 个页面引用此分类")
    except Exception as e:
        print(f"   ⚠️  获取成员失败: {safe_error(e)}")
        members = []

    # 获取所有使用该 category 的页面（包括其他页面中的链接）
    try:
        referrers = list(cat_page.backlinks())
        print(f"   找到 {len(referrers)} 个页面包含此分类链接")
    except Exception as e:
        print(f"   ⚠️  获取引用失败: {safe_error(e)}")
        referrers = []

    # 合并所有需要更新的页面（去重）
    all_pages = {}
    for page in members:
        if page.name not in all_pages:
            all_pages[page.name] = page

    for page in referrers:
        if page.name not in all_pages:
            all_pages[page.name] = page

    pages_to_update = list(all_pages.values())
    print(f"   共 {len(pages_to_update)} 个页面需要检查\n")

    updated = 0
    skipped = 0
    failed = 0

    for page in pages_to_update:
        try:
            print(f"  🔍 检查: {page.name}")

            original = page.text()
            new_content = original

            # 替换各种格式的 category 链接
            # [[Category:旧名]]
            new_content = new_content.replace(f'[[Category:{old_name}]]', f'[[Category:{new_name}]]')
            # [[Category:旧名|显示文字]]
            new_content = new_content.replace(f'[[Category:{old_name}|', f'[[Category:{new_name}|')
            # [[分类:旧名]]
            new_content = new_content.replace(f'[[分类:{old_name}]]', f'[[分类:{new_name}]]')
            new_content = new_content.replace(f'[[分类:{old_name}|', f'[[分类:{new_name}|')

            if original != new_content:
                if dry_run:
                    print(f"    📝 将会更新链接（预览模式）")
                    updated += 1
                else:
                    page.edit(new_content, summary=f"更新分类：{old_name} → {new_name}")
                    print(f"    ✓ 链接已更新")
                    updated += 1
                    time.sleep(0.5)
            else:
                print(f"    ℹ️  无需更新")
                skipped += 1

        except Exception as e:
            print(f"    ⚠️  更新失败: {safe_error(e)}")
            failed += 1

    print(f"\n   ✅ 更新完成:")
    print(f"     - 已更新: {updated}")
    print(f"     - 跳过: {skipped}")
    print(f"     - 失败: {failed}")

    return updated, failed


def move_category_page(old_name: str, new_name: str, bot: FandomBot,
                       cat_page: Any = None, dry_run: bool = False) -> bool:
    """移动 category 页面"""
    print(f"\n📝 步骤 2/2: 移动 Category:{old_name} → Category:{new_name}")

    # 复用已有的 cat_page 对象，避免重复 API 调用
    if cat_page is None:
        cat_page = bot.get_page(f"Category:{old_name}")
    if not cat_page.exists:
        print(f"❌ Category:{old_name} 不存在")
        return False

    if old_name == new_name:
        print(f"ℹ️  名称已经是简体，无需移动")
        return True

    # 检查目标分类是否已存在
    target_page = bot.get_page(f"Category:{new_name}")
    if target_page.exists:
        print(f"❌ 目标分类已存在: Category:{new_name}")
        return False

    if dry_run:
        print(f"📝 将会移动（预览模式）")
        return True

    try:
        bot.move_page(cat_page, f"Category:{new_name}", reason="改名为简体中文")
        print(f"✅ 已移动到 Category:{new_name}")
        return True
    except Exception as e:
        print(f"❌ 移动失败: {safe_error(e)}")
        return False


def process_category(old_name: str, new_name: str, bot: FandomBot, dry_run: bool = False) -> bool:
    """完整处理流程"""
    print(f"\n{'='*60}")
    print(f"处理分类: Category:{old_name} → Category:{new_name}")
    print(f"{'='*60}")

    # 获取源分类页面（复用给两个子函数，避免重复 API 调用）
    cat_page = bot.get_page(f"Category:{old_name}")

    # 检查目标分类是否已存在（在更新链接之前）
    target_page = bot.get_page(f"Category:{new_name}")
    if target_page.exists:
        print(f"❌ 目标分类已存在: Category:{new_name}，跳过")
        return False

    # 步骤 1: 更新链接
    _updated, failed = update_category_links(old_name, new_name, bot, cat_page=cat_page, dry_run=dry_run)

    # 步骤 2: 移动页面
    success = move_category_page(old_name, new_name, bot, cat_page=cat_page, dry_run=dry_run)

    print(f"\n{'='*60}")
    print(f"✅ 处理完成: Category:{old_name}")
    print(f"{'='*60}")

    return success and failed == 0


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description='移动 category 页面（先更新链接，再移动页面）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用流程：
  1. 先更新所有引用该 category 的页面
  2. 然后移动 category 页面本身

示例:
  # 移动单个分类
  %(prog)s "舊分類" "新分類"
  
  # 预览移动
  %(prog)s "舊分類" "新分類" --dry-run
  
  # 从文件批量移动
  %(prog)s --from-file categories.txt
  
  文件格式 (每行两个名称，用空格分隔）:
  舊分類 新分類
  舊分類2 新分類2
        """
    )

    parser.add_argument('old_name', nargs='?', help='旧分类名称（不含 Category: 前缀）')
    parser.add_argument('new_name', nargs='?', help='新分类名称（不含 Category: 前缀）')
    parser.add_argument('--from-file', metavar='FILE', help='从文件读取分类列表')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')

    args = parser.parse_args()

    if not args.old_name and not args.from_file:
        parser.print_help()
        sys.exit(1)

    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)

    # 获取分类列表
    categories = []

    if args.from_file:
        try:
            with open(args.from_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            categories.append((parts[0], parts[1]))
        except Exception as e:
            print(f"❌ 读取文件失败: {safe_error(e)}")
            sys.exit(1)
    else:
        categories.append((args.old_name, args.new_name))

    print(f"共 {len(categories)} 个分类需要处理\n")

    # 批量处理
    total_success = 0
    total_failed = 0

    for i, (old_name, new_name) in enumerate(categories, 1):
        print(f"\n[{i}/{len(categories)}]")

        # 自动生成新名称（如果未提供）
        if not new_name:
            new_name = bot.cc.convert(old_name)

        success = process_category(old_name, new_name, bot, args.dry_run)

        if success:
            total_success += 1
        else:
            total_failed += 1

        if i < len(categories):
            time.sleep(1)

    print(f"\n{'='*60}")
    print("📊 总体统计:")
    print(f"  - 成功: {total_success}")
    print(f"  - 失败: {total_failed}")
    print(f"{'='*60}")

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
