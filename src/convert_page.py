#!/usr/bin/env python3
"""
Fandom Wiki 通用转换工具

将任意页面从繁体中文转换为简体中文。

重要：使用前请先用 --test 模式在单个页面上测试！
"""

import sys
import os
import argparse
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Tuple, Optional, List

from fandom_bot import FandomBot, verify_filenames_preserved, safe_error
from batch_processor import BatchProcessor


def verify_conversion(original: str, new_content: str, page_name: str) -> bool:
    """验证转换结果"""
    
    print(f"\n📊 转换统计 - {page_name}")
    
    lines_orig = original.split('\n')
    lines_new = new_content.split('\n')
    changed_lines = sum(1 for o, n in zip(lines_orig, lines_new) if o != n)
    print(f"  - 总行数: {len(lines_orig)}")
    print(f"  - 修改行数: {changed_lines}")
    
    valid, errors = verify_filenames_preserved(original, new_content)
    
    if valid:
        print(f"  ✓ 文件名保护正常")
        return True
    else:
        print(f"  ⚠️  文件名可能有问题:")
        for err in errors:
            print(f"    {err}")
        return False


def convert_single_page(page_name: str, bot: FandomBot, dry_run: bool = False,
                        show_diff: bool = False) -> bool:
    """转换单个页面"""
    print(f"📄 转换页面: {page_name}")
    
    page = bot.get_page(page_name)
    if not page.exists:
        print(f"❌ 页面不存在: {page_name}")
        return False
    
    original = page.text()
    new_content = bot.convert_text(original)
    
    if original == new_content:
        print("ℹ️  页面无需修改")
        return True
    
    # 验证转换
    valid = verify_conversion(original, new_content, page_name)
    
    if not valid:
        print("\n❌ 转换验证失败，不会保存")
        return False
    
    if show_diff:
        print("\n📝 修改预览:")
        lines_orig = original.split('\n')
        lines_new = new_content.split('\n')
        for i, (orig, new) in enumerate(zip(lines_orig[:30], lines_new[:30])):
            if orig != new:
                print(f"  行 {i}:")
                print(f"    原: {orig[:80]}")
                print(f"    新: {new[:80]}")
    
    if dry_run:
        print("\n🔍 预览模式 - 不会保存更改")
        return True
    
    try:
        bot.edit_page(page, new_content, summary="转换为简体中文")
        print(f"✅ 页面已保存")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {safe_error(e)}")
        return False


def convert_page_with_subpages(page_name: str, bot: FandomBot,
                               dry_run: bool = False) -> Tuple[bool, int, int, int]:
    """转换单个页面及其子页面"""
    print(f"\n📄 转换页面: {page_name}")
    
    page = bot.get_page(page_name)
    if not page.exists:
        print(f"❌ 页面不存在: {page_name}")
        return False, 0, 0, 0
    
    # 转换主页面
    original = page.text()
    new_content = bot.convert_text(original)
    
    converted = 0
    failed = 0
    skipped = 0
    
    if original != new_content:
        valid, errors = verify_filenames_preserved(original, new_content)
        if not valid:
            print("  ⚠️  验证失败，跳过")
            failed += 1
        else:
            if dry_run:
                print("  📝 将会修改（预览模式）")
                converted += 1
            else:
                bot.edit_page(page, new_content, summary="转换为简体中文")
                print("  ✓ 已转换")
                converted += 1
    else:
        print("  ℹ️  无需修改")
        skipped += 1
    
    # 获取子页面列表
    try:
        subpages = bot.get_subpages(page_name)
        print(f"  找到 {len(subpages)} 个子页面")
    except Exception as e:
        print(f"  ⚠️  获取子页面失败: {safe_error(e)}")
        return (failed == 0), converted, failed, skipped
    
    # 处理子页面
    for j, subpage in enumerate(subpages, 1):
        print(f"  [{j}/{len(subpages)}] {subpage.name}")
        try:
            orig = subpage.text()
            new = bot.convert_text(orig)
            
            if orig != new:
                valid, errors = verify_filenames_preserved(orig, new)
                if not valid:
                    print("    ⚠️  验证失败，跳过")
                    failed += 1
                else:
                    if dry_run:
                        print("    📝 将会修改（预览模式）")
                        converted += 1
                    else:
                        bot.edit_page(subpage, new, summary="转换为简体中文")
                        print("    ✓ 已转换")
                        converted += 1
            else:
                print("    ℹ️  无需修改")
                skipped += 1
        except Exception as e:
            print(f"    ⚠️  编辑子页面失败: {safe_error(e)}")
            failed += 1
        
        if j < len(subpages):
            time.sleep(0.3)
    
    return (failed == 0), converted, failed, skipped


def process_batch_page(name: str, bot: FandomBot,
                       dry_run: bool = False) -> Tuple[Optional[bool], str]:
    """批处理单个页面"""
    try:
        page = bot.get_page(name)
        if not page.exists:
            return None, f'ℹ️  页面不存在: {name}'
        original = page.text()
        new_content = bot.convert_text(original)
        if original == new_content:
            return None, 'ℹ️  无需修改'
        valid, errors = verify_filenames_preserved(original, new_content)
        if not valid:
            return False, f'⚠️  文件名验证失败: {errors}'
        if not dry_run:
            bot.edit_page(page, new_content, summary="转换为简体中文")
        return True, '✓ 已转换'
    except Exception as e:
        return False, f'❌ 失败: {safe_error(e)}'


def search_pages(bot: FandomBot, keyword: str,
                 filter_pattern: Optional[str] = None) -> List[str]:
    """搜索包含关键词的页面"""
    print(f"正在搜索: {keyword}")
    
    pages: List[str] = []
    
    try:
        for result in bot.site.search(keyword, namespace='0'):
            page_name = result.get('title', '') if hasattr(result, 'get') else str(result)
            
            if filter_pattern:
                if filter_pattern in page_name:
                    pages.append(page_name)
                    print(f"  找到: {page_name}")
            else:
                pages.append(page_name)
                print(f"  找到: {page_name}")
    except Exception as e:
        print(f"搜索出错: {safe_error(e)}")
    
    print(f"\n共找到 {len(pages)} 个页面")
    return pages


def main():
    parser = argparse.ArgumentParser(
        description='Fandom Wiki 通用转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换单个页面
  %(prog)s "西片"
  
  # 预览单个页面的修改
  %(prog)s "西片" --dry-run
  
  # 显示修改详情
  %(prog)s "西片" --show-diff
  
  # 转换多个页面
  %(prog)s "西片" "真野" "月本早苗"
  
  # 从文件读取页面列表
  %(prog)s --from-file pages.txt
  
  # 搜索并转换页面
  %(prog)s --search "关键词"
  %(prog)s --search "关键词" --filter "过滤文本"
  
  # 转换页面及其子页面
  %(prog)s "动画第一季" --with-subpages
  
  # 预览批量转换
  %(prog)s "西片" "真野" --dry-run

页面列表文件格式 (pages.txt):
  西片
  真野
  月本早苗
  # 以 # 开头的行会被忽略
        """
    )
    
    parser.add_argument('pages', nargs='*', help='要转换的页面名称')
    parser.add_argument('--from-file', metavar='FILE', help='从文件读取页面列表')
    parser.add_argument('--search', metavar='KEYWORD', help='搜索包含关键词的页面')
    parser.add_argument('--filter', help='额外过滤模式（只保留包含此字符串的页面）')
    parser.add_argument('--list', action='store_true', help='只列出页面，不转换')
    parser.add_argument('--dry-run', action='store_true', help='预览模式：显示将要修改但不保存')
    parser.add_argument('--show-diff', action='store_true', help='显示修改详情')
    parser.add_argument('--with-subpages', action='store_true', help='同时转换子页面')
    
    args = parser.parse_args()
    
    if not args.pages and not args.from_file and not args.search:
        parser.print_help()
        sys.exit(1)
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)
    
    # 搜索模式
    page_names: Optional[List[str]] = None
    if args.search:
        pages = search_pages(bot, args.search, args.filter)
        if args.list:
            sys.exit(0)
        if not pages:
            print("没有找到需要处理的页面")
            sys.exit(0)
        page_names = pages
    
    # 获取页面列表
    if not page_names:
        if args.from_file:
            try:
                with open(args.from_file, 'r', encoding='utf-8') as f:
                    page_names = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            except Exception as e:
                print(f"❌ 读取文件失败: {safe_error(e)}")
                sys.exit(1)
        else:
            page_names = args.pages
    
    # 类型收窄：此处 page_names 保证非 None（搜索/文件/命令行参数必有其一）
    assert page_names is not None

    # 带子页面转换
    if args.with_subpages:
        print(f"=== 批量转换页面及子页面 ===")
        print(f"共 {len(page_names)} 个主页面\n")
        
        total_converted = 0
        total_failed = 0
        total_skipped = 0
        
        for i, page_name in enumerate(page_names, 1):
            print(f"[{i}/{len(page_names)}] {page_name}")
            success, converted, failed, skipped = convert_page_with_subpages(page_name, bot, args.dry_run)
            total_converted += converted
            total_failed += failed
            total_skipped += skipped
            
            if i < len(page_names):
                time.sleep(0.5)
        
        print(f"\n{'📊 预览' if args.dry_run else '✅ 完成'}统计:")
        print(f"  - 总页面数: {len(page_names)}")
        print(f"  - {'将修改' if args.dry_run else '已修改'}: {total_converted}")
        print(f"  - 跳过: {total_skipped}")
        print(f"  - 失败: {total_failed}")
        
        sys.exit(0 if total_failed == 0 else 1)
    
    # 普通页面转换
    if len(page_names) == 1:
        success = convert_single_page(page_names[0], bot, args.dry_run, args.show_diff)
    else:
        batch = BatchProcessor(bot, dry_run=args.dry_run, delay=0.5)
        # 使用闭包捕获 dry_run，因为 BatchProcessor 不会在 processor 内处理 dry_run
        processor = lambda name, bot_arg: process_batch_page(name, bot_arg, args.dry_run)
        success = batch.process_pages(page_names, processor, "批量转换页面")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
