#!/usr/bin/env python3
"""
Fandom Wiki 转换工具集

统一的命令行工具，提供所有转换功能。

重要：使用前请先用 --test 模式在单个页面上测试！
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, safe_error

def test_connection(bot: FandomBot, page_name: str = 'STARS') -> None:
    """测试连接"""
    print(f"✓ 已登录: {bot.site.username}")
    
    page = bot.get_page(page_name)
    print(f"\n页面标题: {page.name}")
    print(f"是否存在: {page.exists}")
    print(f"\n页面内容:\n{page.text()}")

def get_template_info(bot: FandomBot, template_name: str = 'Template:音樂信息') -> None:
    """获取模板信息"""
    template_page = bot.get_page(template_name)
    print(f"模板页面: {template_page.name}")
    print(f"是否存在: {template_page.exists}")
    print(f"\n模板内容:\n{template_page.text()}")

def main():
    parser = argparse.ArgumentParser(
        description='Fandom Wiki 转换工具集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  page            转换单个或多个页面
  category        转换分类下的所有页面
  template        转换使用模板的所有页面
  restore         从历史版本恢复页面
  scan            扫描所有 main 命名空间页面并交互式转换
  scan-category   扫描所有 category 命名空间页面并交互式转换
  move-category   移动 category 页面（先更新链接，再移动页面）
  fix-links       批量修复链接为简体版本
  update-cat-refs 批量更新分类引用为简体中文
  dump-xml        下载 Wiki 为 MediaWiki XML dump 格式(双模式)
  dump-wiki       下载 Wiki 页面为 wikitext 文本(.wiki 文件)
  test            测试连接
  info            获取模板/页面信息
  
快速开始:
  # 1. 测试连接
  %(prog)s test
  
  # 2. 测试单个页面
  %(prog)s page "西片" --dry-run
  %(prog)s page "西片"
  
  # 3. 检查 Wiki 上的结果
  
  # 4. 批量转换
  %(prog)s category "音乐"
  %(prog)s template "Template:角色信息" --batch
  
  # 5. 扫描并交互式转换所有 main 页面
  %(prog)s scan

更多信息:
  %(prog)s <command> --help
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # page 子命令
    page_parser = subparsers.add_parser('page', help='转换单个或多个页面')
    page_parser.add_argument('pages', nargs='+', help='要转换的页面名称')
    page_parser.add_argument('--from-file', metavar='FILE', help='从文件读取页面列表')
    page_parser.add_argument('--dry-run', action='store_true', help='预览模式')
    page_parser.add_argument('--show-diff', action='store_true', help='显示修改详情')
    page_parser.add_argument('--search', metavar='KEYWORD', help='搜索包含关键词的页面')
    page_parser.add_argument('--filter', help='额外过滤模式')
    page_parser.add_argument('--list', action='store_true', help='只列出页面')
    page_parser.add_argument('--with-subpages', action='store_true', help='同时转换子页面')
    
    # category 子命令
    cat_parser = subparsers.add_parser('category', help='转换分类下的所有页面')
    cat_parser.add_argument('category', nargs='?', help='分类名称')
    cat_parser.add_argument('--page', metavar='NAME', help='转换单个分类页面本身（含移动）')
    cat_parser.add_argument('--list', action='store_true', help='只列出页面')
    cat_parser.add_argument('--dry-run', action='store_true', help='预览模式')
    cat_parser.add_argument('--limit', type=int, metavar='N', help='限制转换数量')
    cat_parser.add_argument('--no-test-first', action='store_true', help='跳过测试')
    
    # template 子命令
    tpl_parser = subparsers.add_parser('template', help='转换使用模板的所有页面')
    tpl_parser.add_argument('template', help='模板名称')
    tpl_parser.add_argument('--list', action='store_true', help='只列出页面')
    tpl_parser.add_argument('--test', metavar='PAGE', help='测试单个页面')
    tpl_parser.add_argument('--batch', action='store_true', help='批量转换')
    tpl_parser.add_argument('--dry-run', action='store_true', help='预览模式')
    tpl_parser.add_argument('--no-test-first', action='store_true', help='跳过测试')
    tpl_parser.add_argument('--no-doc', action='store_true', help='不转换 /doc')
    
    # restore 子命令
    restore_parser = subparsers.add_parser('restore', help='从历史版本恢复页面')
    restore_parser.add_argument('page', help='要恢复的页面名称')
    restore_parser.add_argument('--show-versions', action='store_true', help='显示历史版本')
    
    # scan 子命令
    scan_parser = subparsers.add_parser('scan', help='扫描所有 main 命名空间页面并交互式转换')
    scan_parser.add_argument('--limit', type=int, metavar='N', help='限制处理的页面数量')
    scan_parser.add_argument('--scan-only', action='store_true', help='仅扫描，不进行转换')
    scan_parser.add_argument('--approve-all', action='store_true', help='自动批准所有修改（非交互式）')
    
    # scan-category 子命令
    scan_cat_parser = subparsers.add_parser('scan-category', help='扫描所有 category 命名空间页面并交互式转换')
    scan_cat_parser.add_argument('--limit', type=int, metavar='N', help='限制处理的页面数量')
    scan_cat_parser.add_argument('--scan-only', action='store_true', help='仅扫描，不进行转换')
    scan_cat_parser.add_argument('--approve-all', action='store_true', help='自动批准所有修改（非交互式）')
    
    # test 子命令
    test_parser = subparsers.add_parser('test', help='测试连接')
    test_parser.add_argument('page', nargs='?', help='测试页面名称（默认：STARS）')
    
    # info 子命令
    info_parser = subparsers.add_parser('info', help='获取模板/页面信息')
    info_parser.add_argument('template', nargs='?', help='模板名称（默认：Template:音樂信息）')
    
    # fix-links 子命令
    fix_parser = subparsers.add_parser('fix-links', help='批量修复链接为简体版本')
    fix_parser.add_argument('old_text', help='要替换的旧文本')
    fix_parser.add_argument('new_text', help='替换后的新文本')
    fix_parser.add_argument('--limit', type=int, metavar='N', help='限制处理的页面数量')
    fix_parser.add_argument('--dry-run', action='store_true', help='预览模式')
    
    # update-cat-refs 子命令
    update_parser = subparsers.add_parser('update-cat-refs', help='批量更新分类引用为简体中文')
    update_parser.add_argument('categories', nargs='*', help='要更新的分类名称（不含 Category: 前缀）')
    update_parser.add_argument('--from-file', metavar='FILE', help='从文件读取分类列表')
    update_parser.add_argument('--dry-run', action='store_true', help='预览模式')
    
    # move-category 子命令
    move_cat_parser = subparsers.add_parser('move-category', help='移动 category 页面（先更新链接，再移动页面）')
    move_cat_parser.add_argument('old_name', nargs='?', help='旧分类名称（不含 Category: 前缀）')
    move_cat_parser.add_argument('new_name', nargs='?', help='新分类名称（不含 Category: 前缀）')
    move_cat_parser.add_argument('--from-file', metavar='FILE', help='从文件读取分类列表')
    move_cat_parser.add_argument('--dry-run', action='store_true', help='预览模式')

    # dump-xml 子命令
    dump_xml_parser = subparsers.add_parser('dump-xml', help='下载 Wiki 为 MediaWiki XML dump 格式')
    dump_xml_parser.add_argument('--ns', type=int, nargs='+', help='命名空间 ID 列表')
    dump_xml_parser.add_argument('--mode', choices=['api', 'special'], default='api', help='导出模式: api=快速仅当前版本; special=支持完整 history(默认 api)')
    dump_xml_parser.add_argument('--history', action='store_true', help='包含完整 revision history(仅 --mode special 有效)')
    dump_xml_parser.add_argument('--list-only', action='store_true', help='只列出页面,不下载')
    dump_xml_parser.add_argument('--skip-existing', action='store_true', help='跳过已存在且非空的 XML 文件(断点续传)')
    dump_xml_parser.add_argument('--dump-dir', default='wiki_dump_xml', help='输出目录(默认: wiki_dump_xml)')
    dump_xml_parser.add_argument('--delay', type=float, default=1.0, help='请求间延迟秒数,默认 1.0(Fandom 速率限制)')
    dump_xml_parser.add_argument('--schema', default='0.11', help='XML dump schema 版本(仅 api 模式,默认 0.11)')

    # dump-wiki 子命令
    dump_wiki_parser = subparsers.add_parser('dump-wiki', help='下载 Wiki 页面为 wikitext 文本(.wiki 文件)')
    dump_wiki_parser.add_argument('--ns', type=int, nargs='+', help='指定命名空间 ID（默认下载内容命名空间）')
    dump_wiki_parser.add_argument('--list-only', action='store_true', help='只列出页面标题，不下载内容')
    dump_wiki_parser.add_argument('--skip-existing', action='store_true', help='跳过已存在且非空的本地文件（断点续传）')
    dump_wiki_parser.add_argument('--dump-dir', default='wiki_dump', help='输出目录（默认 wiki_dump/）')

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # test 和 info 命令需要 bot，其他命令由子脚本自行创建
    if args.command == 'test':
        try:
            bot = FandomBot()
        except Exception as e:
            print(f"❌ 登录失败: {safe_error(e)}")
            sys.exit(1)
        test_connection(bot, args.page or 'STARS')
        sys.exit(0)
    
    if args.command == 'info':
        try:
            bot = FandomBot()
        except Exception as e:
            print(f"❌ 登录失败: {safe_error(e)}")
            sys.exit(1)
        get_template_info(bot, args.template or 'Template:音樂信息')
        sys.exit(0)
    
    # 调用相应的脚本
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.command == 'page':
        import convert_page
        sys.argv = ['convert_page.py']
        if args.search:
            sys.argv.extend(['--search', args.search])
            if args.filter:
                sys.argv.extend(['--filter', args.filter])
            if args.list:
                sys.argv.append('--list')
        elif args.from_file:
            sys.argv.extend(['--from-file', args.from_file])
        else:
            sys.argv.extend(args.pages)
        if args.dry_run:
            sys.argv.append('--dry-run')
        if args.show_diff:
            sys.argv.append('--show-diff')
        if args.with_subpages:
            sys.argv.append('--with-subpages')
        convert_page.main()
        
    elif args.command == 'category':
        import convert_category
        sys.argv = ['convert_category.py']
        if args.page:
            sys.argv.extend(['--page', args.page])
        elif args.category:
            sys.argv.append(args.category)
        if args.list:
            sys.argv.append('--list')
        if args.dry_run:
            sys.argv.append('--dry-run')
        if args.limit:
            sys.argv.extend(['--limit', str(args.limit)])
        if args.no_test_first:
            sys.argv.append('--no-test-first')
        convert_category.main()
        
    elif args.command == 'template':
        import convert_template
        sys.argv = ['convert_template.py', args.template]
        if args.list:
            sys.argv.append('--list')
        elif args.test:
            sys.argv.extend(['--test', args.test])
        elif args.batch:
            sys.argv.append('--batch')
        if args.dry_run:
            sys.argv.append('--dry-run')
        if args.no_test_first:
            sys.argv.append('--no-test-first')
        if args.no_doc:
            sys.argv.append('--no-doc')
        convert_template.main()
        
    elif args.command == 'restore':
        import restore_from_history
        sys.argv = ['restore_from_history.py', args.page]
        if args.show_versions:
            sys.argv.append('--show-versions')
        restore_from_history.main()
        
    elif args.command == 'scan':
        import scan_and_convert
        sys.argv = ['scan_and_convert.py']
        if args.limit:
            sys.argv.extend(['--limit', str(args.limit)])
        if args.scan_only:
            sys.argv.append('--scan-only')
        if args.approve_all:
            sys.argv.append('--approve-all')
        scan_and_convert.main()
    
    elif args.command == 'scan-category':
        import scan_category
        sys.argv = ['scan_category.py']
        if args.limit:
            sys.argv.extend(['--limit', str(args.limit)])
        if args.scan_only:
            sys.argv.append('--scan-only')
        if args.approve_all:
            sys.argv.append('--approve-all')
        scan_category.main()
    
    elif args.command == 'move-category':
        import move_category
        sys.argv = ['move_category.py']
        if args.old_name:
            sys.argv.append(args.old_name)
            if args.new_name:
                sys.argv.append(args.new_name)
        if args.from_file:
            sys.argv.extend(['--from-file', args.from_file])
        if args.dry_run:
            sys.argv.append('--dry-run')
        move_category.main()
    
    elif args.command == 'fix-links':
        import fix_links
        sys.argv = ['fix_links.py', args.old_text, args.new_text]
        if args.limit:
            sys.argv.extend(['--limit', str(args.limit)])
        if args.dry_run:
            sys.argv.append('--dry-run')
        fix_links.main()
    
    elif args.command == 'update-cat-refs':
        import update_cat_refs
        sys.argv = ['update_cat_refs.py']
        if args.categories:
            sys.argv.extend(args.categories)
        if args.from_file:
            sys.argv.extend(['--from-file', args.from_file])
        if args.dry_run:
            sys.argv.append('--dry-run')
        update_cat_refs.main()

    elif args.command == 'dump-xml':
        import dump_xml
        sys.argv = ['dump_xml.py']
        if args.ns:
            sys.argv.extend(['--ns'] + [str(n) for n in args.ns])
        if args.mode != 'api':
            sys.argv.extend(['--mode', args.mode])
        if args.history:
            sys.argv.append('--history')
        if args.list_only:
            sys.argv.append('--list-only')
        if args.skip_existing:
            sys.argv.append('--skip-existing')
        if args.dump_dir != 'wiki_dump_xml':
            sys.argv.extend(['--dump-dir', args.dump_dir])
        if args.delay != 1.0:
            sys.argv.extend(['--delay', str(args.delay)])
        if args.schema != '0.11':
            sys.argv.extend(['--schema', args.schema])
        dump_xml.main()

    elif args.command == 'dump-wiki':
        import dump_wiki
        sys.argv = ['dump_wiki.py']
        if args.ns:
            sys.argv.extend(['--ns'] + [str(n) for n in args.ns])
        if args.list_only:
            sys.argv.append('--list-only')
        if args.skip_existing:
            sys.argv.append('--skip-existing')
        if args.dump_dir and args.dump_dir != 'wiki_dump':
            sys.argv.extend(['--dump-dir', args.dump_dir])
        dump_wiki.main()

if __name__ == "__main__":
    main()
