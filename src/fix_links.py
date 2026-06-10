#!/usr/bin/env python3
"""
批量修复链接为简体版本
"""

import sys
import os
from typing import List, Tuple, Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, safe_error
from batch_processor import BatchProcessor


def search_pages_to_fix(old_text: str, new_text: str, bot: FandomBot,
                        dry_run: bool = False) -> List[str]:
    """搜索并返回需要修复链接的页面"""
    print(f'搜索包含「{old_text}」的页面...')

    try:
        results = list(bot.site.search(old_text, what='text'))
        pages = []

        for result in results:
            if hasattr(result, 'get'):
                page_name = result.get('title', '')
            else:
                page_name = str(result)

            # 排除自己
            if page_name and page_name != old_text:
                pages.append(page_name)

        print(f'\n找到 {len(pages)} 个页面\n')
        return pages
    except Exception as e:
        print(f'搜索出错: {safe_error(e)}')
        return []


def fix_page(page_name: str, bot: FandomBot, old_text: str, new_text: str,
             dry_run: bool = False) -> Tuple[Optional[bool], str]:
    """修复单个页面的链接"""
    try:
        page = bot.get_page(page_name)
        original = page.text()
        new_content = original

        # 智能替换各种格式的链接
        # 1. [[页面名]]
        new_content = new_content.replace(f'[[{old_text}]]', f'[[{new_text}]]')
        # 2. [[页面名|显示文字]]
        new_content = new_content.replace(f'[[{old_text}|', f'[[{new_text}|')
        # 3. [[ 链接]]（带空格）
        new_content = new_content.replace(f'[[ {old_text}]]', f'[[ {new_text}]]')
        new_content = new_content.replace(f'[[ {old_text}|', f'[[ {new_text}|')
        # 4. |链接]] 格式（链接作为参数）
        new_content = new_content.replace(f'|{old_text}]]', f'|{new_text}]]')
        # 5. Category:页面名
        new_content = new_content.replace(f'Category:{old_text}', f'Category:{new_text}')
        # 6. Template:页面名
        new_content = new_content.replace(f'Template:{old_text}', f'Template:{new_text}')
        new_content = new_content.replace(f'模板:{old_text}', f'模板:{new_text}')
        # 7. File:页面名
        new_content = new_content.replace(f'File:{old_text}', f'File:{new_text}')
        new_content = new_content.replace(f'文件:{old_text}', f'文件:{new_text}')

        if original != new_content:
            if dry_run:
                return True, '📝 将会修改（预览模式）'
            else:
                page.edit(new_content, summary=f'修复链接：{old_text} → {new_text}')
                return True, '✓ 已修复'
        else:
            return None, 'ℹ️  无需修改'
    except Exception as e:
        return False, f'⚠️  失败: {safe_error(e)}'


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description='批量修复链接为简体版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "擅長捉弄的(原)高木同學" "擅长捉弄的(原)高木同学"
  %(prog)s "舊文本" "新文本" --limit 5
  %(prog)s "舊文本" "新文本" --dry-run
        """
    )

    parser.add_argument('old_text', help='要替换的旧文本')
    parser.add_argument('new_text', help='替换后的新文本')
    parser.add_argument('--limit', type=int, metavar='N', help='限制处理的页面数量')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')

    args = parser.parse_args()

    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)

    # 搜索需要修复的页面
    pages = search_pages_to_fix(args.old_text, args.new_text, bot, args.dry_run)

    if args.limit:
        pages = pages[:args.limit]
        print(f'限制处理数量: {args.limit} 页\n')

    if not pages:
        print('没有找到需要修复的页面')
        sys.exit(0)

    # 创建处理器并批量处理
    processor = lambda name, bot: fix_page(name, bot, args.old_text, args.new_text, args.dry_run)
    batch = BatchProcessor(bot, dry_run=args.dry_run, delay=0.5)

    success = batch.process_pages(pages, processor, "批量修复链接")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
