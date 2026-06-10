#!/usr/bin/env python3
"""
从历史版本恢复页面

当转换出现问题时，可以从历史版本恢复页面。
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot, safe_error

# Bot 编辑时使用的摘要关键词，用于匹配需要跳过的版本
BOT_KEYWORDS = ['转换为简体中文', '更新模板变量', '修复文件名', '改名为简体中文', '更新链接', '更新分类引用']

def restore_page(page_name: str, bot: FandomBot, show_versions: bool = False) -> bool:
    """从历史版本恢复页面到最近一次非 bot 转换的版本。
    
    Args:
        page_name: 要恢复的页面名称
        bot: FandomBot 实例
        show_versions: 是否仅显示历史版本而不恢复
    
    Returns:
        成功返回 True，失败返回 False
    """
    page = bot.get_page(page_name)
    
    if not page.exists:
        print(f"❌ 页面不存在: {page_name}")
        return False
    
    print(f"📜 获取 {page_name} 的历史版本...")
    revisions = list(page.revisions(limit=50, prop='ids|timestamp|user|comment|content'))
    
    if show_versions:
        print(f"\n最近的 {len(revisions)} 个版本:")
        for i, rev in enumerate(revisions, 1):
            timestamp = rev['timestamp']
            time_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d} {timestamp.tm_hour:02d}:{timestamp.tm_min:02d}"
            comment = rev.get('comment', 'N/A')[:50]
            print(f"  {i}. [{rev['revid']}] {time_str} - {rev['user']} - {comment}")
        return True
    
    # 找到合适的版本（跳过最近的转换相关修改）
    target_rev = None
    for rev in revisions:
        comment = rev.get('comment', '')
        if any(keyword in comment for keyword in BOT_KEYWORDS):
            continue
        target_rev = rev
        break
    
    if not target_rev:
        print("⚠️  找不到合适的版本")
        print("💡 使用 --show-versions 查看所有版本")
        return False
    
    original_content = target_rev.get('*', '')
    if not original_content:
        print(f"⚠️  版本 {target_rev['revid']} 没有内容")
        return False
    
    current_content = page.text()
    
    if original_content == current_content:
        print(f"ℹ️  当前内容与版本 {target_rev['revid']} 相同，无需恢复")
        return True
    
    timestamp = target_rev['timestamp']
    time_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d}"
    
    print(f"\n📋 将恢复到版本 {target_rev['revid']} ({time_str})")
    print(f"   用户: {target_rev['user']}")
    print(f"   评论: {target_rev.get('comment', 'N/A')}")
    
    # 恢复内容
    try:
        bot.edit_page(page, original_content, summary=f"恢复到版本 {target_rev['revid']}")
        print(f"✅ 已恢复")
        return True
    except Exception as e:
        print(f"❌ 恢复失败: {safe_error(e)}")
        return False

def main() -> None:
    parser = argparse.ArgumentParser(
        description='从历史版本恢复页面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 恢复单个页面
  %(prog)s "西片"
  
  # 查看页面的历史版本
  %(prog)s "西片" --show-versions
        """
    )
    
    parser.add_argument('page', help='要恢复的页面名称')
    parser.add_argument('--show-versions', action='store_true',
                       help='只显示历史版本，不恢复')
    
    args = parser.parse_args()
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {safe_error(e)}")
        sys.exit(1)
    
    success = restore_page(args.page, bot, args.show_versions)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
