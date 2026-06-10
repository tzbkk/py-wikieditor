# 代码简化和解耦总结

**注意：本文档中提到的部分脚本（convert_cat_page.py, convert_cat_ending.py, convert_seasons.py）已在后续重构中删除。这些脚本的功能已整合到其他脚本中。**

## 主要改进

### 1. 识别的重复功能

经过分析，发现以下功能在多个脚本中重复出现：

- **批量处理循环** - 8个脚本中有类似的循环逻辑
- **统计信息收集** - converted/failed/skipped 统计
- **进度显示** - `[i/total] page_name` 格式
- **错误处理和速率限制** - `ratelimited` 检测和 60 秒等待
- **文件读取** - 从文件读取页面列表
- **CLI 参数解析** - 相同的 `--from-file`、`--dry-run` 等参数
- **统计输出** - 相同的统计信息格式

### 2. 创建的通用模块

**新增 `batch_processor.py` 模块**，提供以下功能：

- `BatchProcessor` 类 - 统一的批处理器
- `read_page_list()` - 文件读取函数
- `create_batch_parser()` - 标准化的命令行解析器
- `parse_page_args()` - 参数解析辅助函数

### 3. 简化的脚本

#### move_pages.py
- **行数**: 108 → 65 (-43)
- **改进**:
  - 移除硬编码的页面列表
  - 支持从命令行参数或文件读取
  - 统一的错误处理和速率限制
  - 统一的统计输出

#### convert_cat_page.py
- **行数**: 128 → 70 (-58)
- **改进**:
  - 移除硬编码的页面列表
  - 使用 BatchProcessor 简化逻辑
  - 统一的批处理流程

#### fix_links.py
- **行数**: 103 → 93 (-10)
- **改进**:
  - 统一的批处理流程
  - 更清晰的函数结构

#### convert_cat_ending.py
- **行数**: 138 → 88 (-50)
- **改进**:
  - 移除硬编码的分类列表
  - 使用 BatchProcessor 简化逻辑
  - 更清晰的转换和移动逻辑

### 4. 代码质量提升

#### 消除的重复代码
- 8处速率限制处理 → 1处
- 7处文件读取逻辑 → 1处
- 多处批处理循环 → 统一的 BatchProcessor
- 多处统计输出 → 统一的 print_statistics()

#### 改进的接口
- 所有脚本统一支持 `--from-file` 参数
- 所有脚本统一支持 `--dry-run` 参数
- 统一的错误处理和用户反馈
- 统一的进度显示和统计输出

#### 更好的可维护性
- 通用功能集中在 `batch_processor.py`
- 新增脚本可快速复用现有代码
- 修改批处理逻辑只需修改一个地方
- 类型提示提高了代码可读性

## 使用示例

### 创建新的批处理脚本

```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fandom_bot import FandomBot
from batch_processor import create_batch_parser, parse_page_args, BatchProcessor


def process_page(page_name: str, bot: FandomBot, dry_run: bool = False):
    """处理单个页面"""
    # 你的处理逻辑
    return True, "✓ 处理成功"


def main():
    parser = create_batch_parser('脚本描述', '帮助信息')
    args, page_names, should_exit = parse_page_args(parser)
    if should_exit or page_names is None:
        sys.exit(1)
    
    try:
        bot = FandomBot()
        print(f"✓ 已登录: {bot.site.username}\n")
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        sys.exit(1)
    
    processor = lambda name, bot: process_page(name, bot, args.dry_run)
    batch = BatchProcessor(bot, dry_run=args.dry_run, delay=0.5)
    
    success = batch.process_pages(page_names, processor, "处理标题")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

## 统计数据

- **总节省行数**: 161 行（不计入 batch_processor.py）
- **消除重复**: 8+ 处重复代码块
- **新增模块**: 1 个（batch_processor.py，174 行）
- **简化的脚本**: 4 个

## 未来优化建议

1. 可以进一步简化的脚本：
   - `convert_category.py` - 可使用 BatchProcessor
   - `convert_page.py` - 可使用 BatchProcessor
   - `convert_template.py` - 可使用 BatchProcessor
   - `convert_seasons.py` - 子页面处理逻辑可以更清晰

2. 可能的进一步解耦：
   - 创建专门的错误处理模块
   - 创建专门的验证模块
   - 统一所有脚本的输出格式

3. 功能整合：
   - 考虑是否可以合并某些功能相似的脚本
   - 例如：`convert_cat_page.py` 和 `convert_category.py` 功能重叠
