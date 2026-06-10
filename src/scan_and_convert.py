#!/usr/bin/env python3
"""
扫描并转换所有 main 命名空间页面

功能：
1. 扫描所有 main 命名空间（namespace=0）的页面
2. 检测哪些页面需要转换（包含繁体中文）
3. 显示每个页面的更改预览
4. 逐个询问是否批准保存修改
"""

import sys
import os
import argparse
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, protect_filenames, restore_filenames, verify_filenames_preserved, safe_error


def needs_conversion(text: str, bot: FandomBot) -> bool:
    """检查页面是否需要转换"""
    return bot.convert_text(text) != text


def show_changes_preview(original: str, new_content: str, page_name: str, max_lines: int = 20) -> None:
    """显示更改预览"""
    lines_orig = original.split('\n')
    lines_new = new_content.split('\n')
    
    changed_indices = [i for i, (o, n) in enumerate(zip(lines_orig, lines_new)) if o != n]
    
    print(f"\n📝 页面: {page_name}")
    print(f"   总行数: {len(lines_orig)}, 修改行数: {len(changed_indices)}")
    
    if not changed_indices:
        print("   ℹ️  无需修改")
        return
    
    print(f"\n   修改预览（前 {min(max_lines, len(changed_indices))} 处更改）:")
    for idx in changed_indices[:max_lines]:
        orig = lines_orig[idx]
        new = lines_new[idx]
        print(f"   行 {idx + 1}:")
        print(f"     原: {orig[:100]}{'...' if len(orig) > 100 else ''}")
        print(f"     新: {new[:100]}{'...' if len(new) > 100 else ''}")


def scan_main_namespace(bot: FandomBot, limit: Optional[int] = None) -> List[str]:
    """扫描所有 main 命名空间的页面"""
    print("🔍 扫描 main 命名空间页面...\n")
    
    pages_to_convert: List[str] = []
    count = 0
    
    try:
        for page in bot.site.allpages(namespace='0'):
            count += 1
            
            try:
                original = page.text()
                
                if needs_conversion(original, bot):
                    pages_to_convert.append(page.name)
                    print(f"✓ 发现可转换页面: {page.name}")
                else:
                    print(f"  - 跳过: {page.name} (无需转换)")
                
                if limit and len(pages_to_convert) >= limit:
                    break
                
                if count % 10 == 0:
                    print(f"   已扫描 {count} 个页面...")
            
            except Exception as e:
                print(f"  ⚠️  处理 {page.name} 时出错: {safe_error(e)}")
                continue
        
        print(f"\n📊 扫描完成:")
        print(f"   - 总扫描: {count} 个页面")
        print(f"   - 可转换: {len(pages_to_convert)} 个页面")
        
        return pages_to_convert
    
    except Exception as e:
        print(f"❌ 扫描失败: {safe_error(e)}")
        return []


def interactive_convert(page_names: List[str], bot: FandomBot, approve_all: bool = False) -> Tuple[int, int, int]:
    """交互式转换：逐个询问是否保存"""
    print(f"\n🎯 开始{'自动' if approve_all else '交互式'}转换")
    print(f"共 {len(page_names)} 个页面需要处理\n")
    
    approved = 0
    skipped = 0
    failed = 0
    
    for i, page_name in enumerate(page_names, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(page_names)}] 处理: {page_name}")
        
        try:
            page = bot.get_page(page_name)
            if not page.exists:
                print("❌ 页面不存在，跳过")
                skipped += 1
                continue
            
            original = page.text()
            new_content = bot.convert_text(original)
            
            if original == new_content:
                print("ℹ️  页面无需修改，跳过")
                skipped += 1
                continue
            
            show_changes_preview(original, new_content, page_name)
            
            # 验证文件名保护
            valid, errors = verify_filenames_preserved(original, new_content)
            if not valid:
                print("\n⚠️  文件名保护验证失败:")
                for err in errors:
                    print(f"     {err}")
                print("   为安全起见，跳过此页面")
                failed += 1
                continue
            
            print(f"\n✓ 文件名保护验证通过")
            
            # 如果是自动批准模式，直接保存
            if approve_all:
                try:
                    bot.edit_page(page, new_content, summary="转换为简体中文")
                    print("✅ 页面已保存（自动批准）")
                    approved += 1
                except Exception as e:
                    print(f"❌ 保存失败: {safe_error(e)}")
                    failed += 1
                continue
            
            # 询问是否批准（交互式）
            try:
                while True:
                    response = input("\n是否批准保存此页面的修改？ [y/n/a/q]: ").strip().lower()
                    
                    if response == 'y':
                        try:
                            bot.edit_page(page, new_content, summary="转换为简体中文")
                            print("✅ 页面已保存")
                            approved += 1
                        except Exception as e:
                            print(f"❌ 保存失败: {safe_error(e)}")
                            failed += 1
                        break
                    
                    elif response == 'n':
                        print("⏭️  跳过此页面")
                        skipped += 1
                        break
                    
                    elif response == 'a':
                        # 批准剩余所有页面
                        print(f"📋 将批准剩余 {len(page_names) - i} 个页面...")
                        remaining = page_names[i:]
                        for pn in remaining:
                            try:
                                p = bot.get_page(pn)
                                if p.exists:
                                    orig = p.text()
                                    nc = bot.convert_text(orig)
                                    bot.edit_page(p, nc, summary="转换为简体中文")
                                    approved += 1
                                    print(f"  ✓ {pn}")
                            except Exception as e:
                                print(f"  ✗ {pn}: {safe_error(e)}")
                                failed += 1
                        print(f"\n✅ 批量转换完成")
                        return approved, skipped, failed
                    
                    elif response == 'q':
                        print("🛑 退出转换")
                        return approved, skipped, failed
                    
                    else:
                        print("无效输入，请输入 y/n/a/q")
            
            except EOFError:
                print("⚠️  无法读取输入（非交互式环境），请使用 --approve-all 选项")
                return approved, skipped, failed
        
        except Exception as e:
            print(f"❌ 处理页面时出错: {safe_error(e)}")
            failed += 1
    
    print(f"\n{'='*60}")
    print("📊 转换完成统计:")
    print(f"  - 批准并保存: {approved}")
    print(f"  - 跳过: {skipped}")
    print(f"  - 失败: {failed}")
    
    return approved, skipped, failed


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(
        description='扫描并转换所有 main 命名空间页面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用流程:
  1. 扫描所有 main 命名空间页面
  2. 显示每个需要转换的页面的更改预览
  3. 逐个询问是否批准保存修改
     y - 批准并保存
     n - 跳过此页面
     a - 批准剩余所有页面
     q - 退出

示例:
  # 扫描并转换所有 main 命名空间页面
  %(prog)s
  
  # 只扫描前 5 个可转换的页面
  %(prog)s --limit 5
  
  # 扫描但不转换（仅查看）
  %(prog)s --scan-only
        """
    )
    
    parser.add_argument('--limit', type=int, metavar='N', help='限制处理的页面数量')
    parser.add_argument('--scan-only', action='store_true', help='仅扫描，不进行转换')
    parser.add_argument('--approve-all', action='store_true', help='自动批准所有修改（非交互式）')
    
    args = parser.parse_args()
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)
    
    # 扫描 main 命名空间
    pages_to_convert = scan_main_namespace(bot, args.limit)
    
    if not pages_to_convert:
        print("\n✅ 没有发现需要转换的页面")
        sys.exit(0)
    
    if args.scan_only:
        print("\n🔍 仅扫描模式，不进行转换")
        sys.exit(0)
    
    # 交互式转换或自动批准
    print(f"\n{'='*60}")
    approved, skipped, failed = interactive_convert(pages_to_convert, bot, approve_all=args.approve_all)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
