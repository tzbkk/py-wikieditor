#!/usr/bin/env python3
"""
通用批处理工具模块

提供批量处理页面时的通用功能，减少代码重复
"""
import time
import argparse
import sys
from typing import List, Callable, Dict, Tuple, Optional

from fandom_bot import FandomBot, safe_error


class BatchProcessor:
    """批处理器类，提供通用的批量页面处理功能"""
    
    def __init__(self, bot: FandomBot, dry_run: bool = False, delay: float = 0.5) -> None:
        """
        初始化批处理器
        
        Args:
            bot: FandomBot 实例
            dry_run: 是否为预览模式
            delay: 每次处理之间的延迟秒数
        """
        self.bot = bot
        self.dry_run = dry_run
        self.delay = delay
        self.converted = 0
        self.failed = 0
        self.skipped = 0
    
    def process_pages(self, pages: List[str], processor: Callable[[str, FandomBot], Tuple[Optional[bool], str]],
                      title: str = "批量处理", show_progress: bool = True) -> bool:
        """
        批量处理页面
        
        Args:
            pages: 页面名称列表
            processor: 处理函数，签名为 processor(page_name, bot) -> (result, message)
                      result: True/False/None (成功/失败/跳过)
                      message: str (处理结果描述)
            title: 处理标题
            show_progress: 是否显示进度
        
        Returns:
            是否全部成功
        """
        if show_progress:
            print(f"=== {title} ===")
            print(f"共 {len(pages)} 个页面\n")
        
        self.converted = 0
        self.failed = 0
        self.skipped = 0
        
        for i, page_name in enumerate(pages, 1):
            if show_progress:
                print(f"[{i}/{len(pages)}] {page_name}")
            
            try:
                result, message = processor(page_name, self.bot)
                
                if show_progress:
                    print(f"  {message}")
                
                if result is None:
                    self.skipped += 1
                elif result:
                    self.converted += 1
                else:
                    self.failed += 1
                
                if i < len(pages) and self.delay > 0:
                    time.sleep(self.delay)
                    
            except Exception as e:
                if 'ratelimited' in str(e).lower():
                    if show_progress:
                        print("  ⏳ 遇到速率限制，等待 60 秒后重试...")
                    time.sleep(60)
                    try:
                        result, message = processor(page_name, self.bot)
                        if show_progress:
                            print(f"  {message}")
                        if result is None:
                            self.skipped += 1
                        elif result:
                            self.converted += 1
                        else:
                            self.failed += 1
                    except Exception as e2:
                        if show_progress:
                            print(f"  ⚠️  重试失败: {safe_error(e2)}")
                        self.failed += 1
                    continue
                
                if show_progress:
                    print(f"  ⚠️  失败: {safe_error(e)}")
                self.failed += 1
        
        if show_progress:
            self.print_statistics()
        
        return self.failed == 0
    
    def print_statistics(self, extra_stats: Optional[Dict[str, int]] = None) -> None:
        """
        打印统计信息
        
        Args:
            extra_stats: 额外的统计信息
        """
        mode = "📊 预览" if self.dry_run else "✅ 完成"
        print(f"\n{mode}统计:")
        print(f"  - 已处理: {self.converted}")
        print(f"  - 跳过: {self.skipped}")
        print(f"  - 失败: {self.failed}")
        
        if extra_stats:
            for key, value in extra_stats.items():
                print(f"  - {key}: {value}")


def read_page_list(file_path: str) -> List[str]:
    """
    从文件读取页面列表
    
    Args:
        file_path: 文件路径
    
    Returns:
        页面名称列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            pages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return pages
    except Exception as e:
        raise Exception(f"读取文件失败: {e}") from e


def create_batch_parser(description: str, epilog: Optional[str] = None) -> argparse.ArgumentParser:
    """
    创建标准的批处理命令行解析器
    
    Args:
        description: 工具描述
        epilog: 帮助信息尾部
    
    Returns:
        argparse.ArgumentParser
    """
    if epilog is None:
        epilog = """
示例:
  %(prog)s "页面1" "页面2"
  %(prog)s --from-file pages.txt
  %(prog)s "页面1" --dry-run
        """
    
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    
    parser.add_argument('pages', nargs='*', help='要处理的页面名称')
    parser.add_argument('--from-file', metavar='FILE', help='从文件读取页面列表')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')
    
    return parser


def parse_page_args(parser: argparse.ArgumentParser) -> Tuple[argparse.Namespace, Optional[List[str]], bool]:
    """
    解析页面参数（命令行或文件）
    
    Args:
        parser: argparse.ArgumentParser
    
    Returns:
        (args, page_names, should_exit)
        如果 should_exit 为 True，表示应该退出程序
    """
    args = parser.parse_args()
    
    if not args.pages and not args.from_file:
        parser.print_help()
        return args, None, True
    
    page_names = args.pages if args.pages else read_page_list(args.from_file)
    
    return args, page_names, False
