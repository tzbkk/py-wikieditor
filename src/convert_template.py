#!/usr/bin/env python3
"""
Fandom Wiki 模板转换工具

转换使用特定模板的所有页面从繁体中文到简体中文。

重要：使用前请先用 --test 模式在单个页面上测试！
"""

import sys
import os
import argparse
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional, Any

from fandom_bot import FandomBot, verify_filenames_preserved, safe_error


VARIABLE_MAPPINGS = {
    '名稱': '名称',
    '圖片': '图片',
    '別稱': '别称',
    '羅馬音': '罗马音',
    '性別': '性别',
    '年齡': '年龄',
    '體重': '体重',
    '頭髮顏色': '头发颜色',
    '眼睛顏色': '眼睛颜色',
    '親屬': '亲属',
    '狀態': '状态',
    '班級': '班级',
    '隸屬': '隶属',
    '職業': '职业',
    '日語配音演員': '日语配音演员',
    '中文配音演員': '中文配音演员',
    '英語配音演員': '英语配音演员',
    '漫畫': '漫画',
    '動畫': '动画',
    '角色資料': '角色资料',
    '資料模板': '资料模板',
}


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


def list_template_pages(template_name: str, bot: FandomBot) -> List[Any]:
    """列出所有使用模板的页面"""
    print(f"📋 获取使用 {template_name} 的页面...")
    pages = list(bot.get_template_embedded_pages(template_name))
    print(f"找到 {len(pages)} 个页面\n")
    
    doc_page = bot.get_page(f"{template_name}/doc")
    if doc_page.exists:
        print(f"文档页面: {template_name}/doc\n")
    
    return pages


def test_single_page(page_name: str, template_name: str, bot: FandomBot,
                     dry_run: bool = False) -> bool:
    """测试模式：转换单个页面"""
    print(f"=== 测试模式 ===")
    print(f"页面: {page_name}")
    print(f"模板: {template_name}\n")
    
    page = bot.get_page(page_name)
    if not page.exists:
        print(f"❌ 页面不存在: {page_name}")
        return False
    
    original = page.text()
    new_content = bot.convert_text(original)
    
    if original == new_content:
        print("ℹ️  页面无需修改")
        return True
    
    valid = verify_conversion(original, new_content, page_name)
    
    if not valid:
        print("\n❌ 转换验证失败")
        return False
    
    # 检查所有变量名转换
    print("\n📝 变量名转换检查:")
    for traditional, simplified in VARIABLE_MAPPINGS.items():
        if f'|{traditional}' in original:
            if f'|{simplified}' in new_content and f'|{traditional}' not in new_content:
                print(f"  ✓ {traditional} → {simplified}")
            else:
                print(f"  ⚠️  {traditional} 未正确转换")
    
    if dry_run:
        print("\n🔍 预览模式 - 不会保存更改")
        print("\n前 20 行对比:")
        lines_orig = original.split('\n')
        lines_new = new_content.split('\n')
        for i, (orig, new) in enumerate(zip(lines_orig[:20], lines_new[:20])):
            if orig != new:
                print(f"  行 {i}:")
                print(f"    原: {orig[:80]}")
                print(f"    新: {new[:80]}")
    else:
        print("\n💾 保存更改...")
        try:
            bot.edit_page(page, new_content, summary="转换为简体中文（测试）")
            print("✅ 测试成功！页面已保存")
            print("\n👉 请到 Wiki 上检查页面确认无误后，再使用 --batch 模式")
            return True
        except Exception as e:
            print(f"❌ 保存失败: {safe_error(e)}")
            return False
    
    return True


def batch_convert(template_name: str, bot: FandomBot, dry_run: bool = False,
                  include_doc: bool = True, test_first: bool = True) -> bool:
    """批量模式：转换所有使用模板的页面"""
    print(f"=== 批量转换模式 ===")
    print(f"模板: {template_name}\n")
    
    if dry_run:
        print("🔍 预览模式 - 不会保存更改\n")
    
    # list_template_pages 已返回 list，无需再次 list()
    all_pages = list_template_pages(template_name, bot)
    if include_doc:
        doc_page = bot.get_page(f"{template_name}/doc")
        if doc_page.exists:
            all_pages.append(doc_page)
    
    # 测试第一个页面
    if test_first and not dry_run and all_pages:
        print("🔍 先测试第一个页面...\n")
        first_page = all_pages[0]
        
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
    
    print(f"\n开始批量转换...\n")
    
    converted = 0
    failed = 0
    skipped = 0
    
    for i, page in enumerate(all_pages, 1):
        print(f"[{i}/{len(all_pages)}] {page.name}")
        
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
                
                if i < len(all_pages):
                    time.sleep(1)
                    
        except Exception as e:
            print(f"  ⚠️  失败: {safe_error(e)}")
            failed += 1
            
            if 'ratelimited' in str(e).lower():
                print("  ⏳ 遇到速率限制，等待 60 秒...")
                time.sleep(60)
    
    print(f"\n{'📊 预览' if dry_run else '✅ 完成'}统计:")
    print(f"  - 总页面数: {len(all_pages)}")
    print(f"  - {'将修改' if dry_run else '已修改'}: {converted}")
    print(f"  - 跳过: {skipped}")
    print(f"  - 失败: {failed}")
    
    if dry_run:
        print("\n💡 确认无误后，运行不带 --dry-run 的命令进行实际转换")
    
    return failed == 0


def main():
    parser = argparse.ArgumentParser(
        description='Fandom Wiki 模板转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有使用模板的页面
  %(prog)s "Template:角色信息" --list
  
  # 测试单个页面（推荐第一步）
  %(prog)s "Template:角色信息" --test "西片"
  
  # 预览单个页面的修改
  %(prog)s "Template:角色信息" --test "西片" --dry-run
  
  # 批量转换所有页面（测试成功后）
  %(prog)s "Template:角色信息" --batch
  
  # 预览批量转换
  %(prog)s "Template:角色信息" --batch --dry-run
  
  # 跳过第一个页面测试
  %(prog)s "Template:角色信息" --batch --no-test-first
  
  # 不包含 /doc 页面
  %(prog)s "Template:角色信息" --batch --no-doc
        """
    )
    
    parser.add_argument('template', help='模板名称（包含 Template: 前缀）')
    parser.add_argument('--list', action='store_true', help='只列出页面，不转换')
    parser.add_argument('--test', metavar='PAGE', help='测试模式：转换单个页面')
    parser.add_argument('--batch', action='store_true', help='批量模式：转换所有使用模板的页面')
    parser.add_argument('--dry-run', action='store_true', help='预览模式：显示将要修改但不保存')
    parser.add_argument('--no-test-first', action='store_true', help='跳过第一个页面的测试')
    parser.add_argument('--no-doc', action='store_true', help='不转换 /doc 页面')
    
    args = parser.parse_args()
    
    if not any([args.list, args.test, args.batch]):
        parser.print_help()
        sys.exit(1)
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)
    
    if args.list:
        list_template_pages(args.template, bot)
    elif args.test:
        success = test_single_page(args.test, args.template, bot, args.dry_run)
        sys.exit(0 if success else 1)
    elif args.batch:
        success = batch_convert(
            args.template, 
            bot, 
            dry_run=args.dry_run,
            include_doc=not args.no_doc,
            test_first=not args.no_test_first
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
