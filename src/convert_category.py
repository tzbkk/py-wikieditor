#!/usr/bin/env python3
"""
Fandom Wiki 分类转换工具

转换分类下的所有页面从繁体中文到简体中文。

重要：使用前请先用 --test 模式在单个页面上测试！
"""

import sys
import os
import argparse
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional, Any

from fandom_bot import FandomBot, verify_filenames_preserved, safe_error


def verify_conversion(original: str, new_content: str, page_name: str) -> bool:
    """验证转换结果"""
    valid, errors = verify_filenames_preserved(original, new_content)
    if not valid:
        print(f"  ⚠️  {page_name} 文件名验证未通过: {errors}")
    return valid


def list_category_pages(category_name: str, bot: FandomBot,
                        limit: Optional[int] = None) -> List[Any]:
    """列出分类下的所有页面"""
    print(f"📋 获取 Category:{category_name} 的页面...")
    pages = list(bot.get_category_members(category_name))
    
    if limit:
        pages = pages[:limit]
    
    print(f"找到 {len(pages)} 个页面\n")
    return pages


def convert_category(category_name: str, bot: FandomBot, dry_run: bool = False,
                     limit: Optional[int] = None, test_first: bool = True) -> bool:
    """转换分类下的所有页面"""
    print(f"=== 转换分类 ===")
    print(f"分类: Category:{category_name}\n")
    
    pages = list_category_pages(category_name, bot, limit)
    
    if not pages:
        print("ℹ️  没有找到页面")
        return True
    
    # 测试第一个页面
    if test_first and not dry_run:
        print("🔍 先测试第一个页面...\n")
        first_page = pages[0]
        print(f"📄 测试: {first_page.name}")
        
        original = first_page.text()
        new_content = bot.convert_text(original)
        
        if original != new_content:
            valid = verify_conversion(original, new_content, first_page.name)
            
            if not valid:
                print("❌ 测试失败：文件名验证未通过")
                print("💡 使用 --no-test-first 跳过测试，或使用 --dry-run 预览")
                return False
            
            print("✓ 测试通过\n")
            print("👉 请到 Wiki 上检查这个页面，确认无误后继续")
            response = input("继续批量转换？(y/n): ")
            if response.lower() != 'y':
                print("已取消")
                return False
        else:
            print("ℹ️  第一个页面无需修改\n")
    
    # 批量转换
    print(f"\n开始批量转换...\n")
    
    converted = 0
    failed = 0
    skipped = 0
    
    for i, page in enumerate(pages, 1):
        print(f"[{i}/{len(pages)}] {page.name}")
        
        try:
            original = page.text()
            new_content = bot.convert_text(original)
            
            if original == new_content:
                print("  - 无需修改")
                skipped += 1
                continue
            
            if not verify_conversion(original, new_content, page.name):
                print("  ⚠️  验证失败，跳过")
                failed += 1
                continue
            
            if dry_run:
                print("  📝 将会修改（预览模式）")
                converted += 1
            else:
                bot.edit_page(page, new_content, summary="转换为简体中文")
                print("  ✓ 已转换")
                converted += 1
                
                if i < len(pages):
                    time.sleep(1)
                    
        except Exception as e:
            print(f"  ⚠️  失败: {safe_error(e)}")
            failed += 1
            
            if 'ratelimited' in str(e).lower():
                print("  ⏳ 遇到速率限制，等待 60 秒...")
                time.sleep(60)
    
    print(f"\n{'📊 预览' if dry_run else '✅ 完成'}统计:")
    print(f"  - 总页面数: {len(pages)}")
    print(f"  - {'将修改' if dry_run else '已修改'}: {converted}")
    print(f"  - 跳过: {skipped}")
    print(f"  - 失败: {failed}")
    
    return failed == 0


def convert_category_page(category_name: str, bot: FandomBot,
                          dry_run: bool = False) -> bool:
    """转换单个分类页面"""
    new_name = bot.cc.convert(category_name)
    
    cat = bot.get_page(f"Category:{category_name}")
    if not cat.exists:
        print(f"❌ 页面不存在: Category:{category_name}")
        return False
    
    content = cat.text()
    new_content = bot.convert_text(content)
    
    # 转换内容
    if content != new_content:
        valid, errors = verify_filenames_preserved(content, new_content)
        if not valid:
            print("⚠️  文件名验证失败:")
            for err in errors:
                print(f"    {err}")
            return False
        
        if dry_run:
            print("  📝 内容将会修改（预览模式）")
        else:
            bot.edit_page(cat, new_content, summary="转换为简体中文")
            print("  ✓ 内容已转换")
    else:
        print("  ℹ️  内容无需转换")
    
    # 移动页面（如果名称不同）
    if category_name != new_name:
        if dry_run:
            print(f"  📝 将会移动到 Category:{new_name}（预览模式）")
        else:
            try:
                bot.move_page(cat, f"Category:{new_name}", reason="改名为简体中文")
                print(f"  ✓ 已移动到 Category:{new_name}")
            except Exception as e:
                print(f"  ⚠️  移动失败: {safe_error(e)}")
                return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Fandom Wiki 分类转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出分类下的页面
  %(prog)s "音乐" --list
  
  # 转换分类下的所有页面
  %(prog)s "音乐"
  
  # 预览转换
  %(prog)s "音乐" --dry-run
  
  # 限制转换数量（用于测试）
  %(prog)s "音乐" --limit 5
  
  # 跳过第一个页面测试
  %(prog)s "音乐" --no-test-first
  
  # 转换分类页面本身（含移动）
  %(prog)s --page "片頭曲"
  %(prog)s --page "片頭曲" --dry-run
        """
    )
    
    parser.add_argument('category', nargs='?', help='分类名称（不需要包含 Category: 前缀）')
    parser.add_argument('--page', metavar='NAME', help='转换单个分类页面本身（含移动）')
    parser.add_argument('--list', action='store_true', help='只列出页面，不转换')
    parser.add_argument('--dry-run', action='store_true', help='预览模式：显示将要修改但不保存')
    parser.add_argument('--limit', type=int, metavar='N', help='限制转换的页面数量')
    parser.add_argument('--no-test-first', action='store_true', help='跳过第一个页面的测试')
    
    args = parser.parse_args()
    
    if not args.category and not args.page:
        parser.print_help()
        sys.exit(1)
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)
    
    if args.page:
        success = convert_category_page(args.page, bot, args.dry_run)
        sys.exit(0 if success else 1)
    
    if args.list:
        pages = list_category_pages(args.category, bot, args.limit)
        print("页面列表:")
        for i, page in enumerate(pages, 1):
            print(f"  {i}. {page.name}")
    else:
        success = convert_category(
            args.category, 
            bot, 
            dry_run=args.dry_run,
            limit=args.limit,
            test_first=not args.no_test_first
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
