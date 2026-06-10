# src/ 目录说明

这是项目的主要工具目录，包含所有 Wiki 操作工具。

## 主要工具

### 统一入口（推荐）⭐

**fandom.py** - 统一的命令行工具，提供所有转换功能

```bash
python src/fandom.py <command> [options]
```

**命令：**
- `page` - 转换单个或多个页面
- `category` - 转换分类下的所有页面
- `template` - 转换使用模板的所有页面
- `restore` - 从历史版本恢复页面
- `scan` - 扫描所有 main 命名空间页面并交互式转换
- `scan-category` - 扫描所有 category 命名空间页面并交互式转换
- `move-category` - 移动 category 页面（先更新链接，再移动页面）
- `test` - 测试连接
- `info` - 获取模板/页面信息
- `fix-links` - 批量修复链接为简体版本
- `update-cat-refs` - 批量更新分类引用为简体中文

### 页面转换

**convert_page.py** - 转换单个或多个页面

```bash
python src/convert_page.py "页面名" [选项]
```

**选项：**
- `--dry-run` - 预览模式
- `--show-diff` - 显示修改详情
- `--from-file FILE` - 从文件读取页面列表
- `--search KEYWORD` - 搜索包含关键词的页面
- `--filter PATTERN` - 额外过滤模式
- `--list` - 只列出页面（搜索模式）
- `--with-subpages` - 同时转换子页面

### 分类转换

**convert_category.py** - 转换分类下的所有页面

```bash
python src/convert_category.py "分类名" [选项]
```

**选项：**
- `--list` - 只列出页面
- `--dry-run` - 预览模式
- `--limit N` - 限制转换数量
- `--no-test-first` - 跳过测试
- `--page NAME` - 转换单个分类页面本身（含移动）

### 模板转换

**convert_template.py** - 转换使用模板的所有页面

```bash
python src/convert_template.py "Template:模板名" [选项]
```

**选项：**
- `--list` - 只列出页面
- `--test PAGE` - 测试单个页面
- `--batch` - 批量转换
- `--dry-run` - 预览模式
- `--no-doc` - 不转换 /doc

### 页面恢复

**restore_from_history.py** - 从历史版本恢复页面

```bash
python src/restore_from_history.py "页面名" [选项]
```

**选项：**
- `--show-versions` - 显示历史版本

### 扫描转换

**scan_and_convert.py** - 扫描所有 main 命名空间页面并交互式转换

```bash
python src/scan_and_convert.py [选项]
```

**选项：**
- `--limit N` - 限制处理的页面数量
- `--scan-only` - 仅扫描，不进行转换
- `--approve-all` - 自动批准所有修改（非交互式）

### 页面移动

**move_pages.py** - 批量移动/重命名页面

```bash
python src/move_pages.py "页面1" "页面2" ...
```

**选项：**
- `--from-file FILE` - 从文件读取页面列表
- `--dry-run` - 预览模式

### 链接修复

**fix_links.py** - 批量修复链接为简体版本

```bash
python src/fix_links.py "舊文本" "新文本" [选项]
```

**选项：**
- `--limit N` - 限制处理的页面数量
- `--dry-run` - 预览模式

### 分类引用更新

**update_cat_refs.py** - 批量更新分类引用为简体中文

```bash
python src/update_cat_refs.py "分类名" [选项]
```

**选项：**
- `--from-file FILE` - 从文件读取分类列表
- `--dry-run` - 预览模式

## 辅助模块

### batch_processor.py

批处理工具模块，提供通用的批量处理功能。

主要功能：
- `BatchProcessor` 类 - 批量处理页面
- `read_page_list()` - 从文件读取页面列表
- `create_batch_parser()` - 创建标准的批处理命令行解析器
- `parse_page_args()` - 解析页面参数

## 使用建议

### 日常使用

对于日常的繁简转换任务，推荐使用统一入口：

```bash
# 测试连接
python src/fandom.py test

# 转换页面
python src/fandom.py page "页面名"

# 转换分类
python src/fandom.py category "分类名"

# 转换模板
python src/fandom.py template "Template:模板名" --batch
```

### 快速测试

```bash
# 测试连接
python src/fandom.py test

# 预览转换
python src/fandom.py page "页面名" --dry-run

# 获取模板信息
python src/fandom.py info "Template:模板名"
```

### 批量操作

```bash
# 从文件批量转换
python src/fandom.py page --from-file pages.txt

# 转换分类（限制数量）
python src/fandom.py category "分类名" --limit 10

# 扫描并转换
python src/fandom.py scan --limit 5 --approve-all

# 修复链接
python src/fandom.py fix-links "舊文本" "新文本"

# 更新分类引用
python src/fandom.py update-cat-refs --from-file categories.txt
```

## 核心特性

所有主要工具都支持：

- ✅ **文件名保护** - 自动保护 .jpg, .png 等文件名
- ✅ **转换验证** - 验证文件名未被修改
- ✅ **测试模式** - 先测试单个页面
- ✅ **预览模式** - 使用 --dry-run 预览
- ✅ **安全恢复** - 可从历史版本恢复
- ✅ **速率限制处理** - 自动处理 API 限制

## 重要原则

**⚠️ 永远先测试单个页面，再批量应用！**

1. 使用 `--dry-run` 预览修改
2. 在单个页面上测试
3. 到 Wiki 上检查结果
4. 确认无误后再批量转换

## 文件清单

```
src/
├── fandom.py                      # 统一入口 ⭐
├── convert_page.py                # 页面转换
├── convert_category.py            # 分类转换
├── convert_template.py            # 模板转换
├── restore_from_history.py        # 恢复页面
├── scan_and_convert.py           # 扫描转换
├── scan_category.py              # 扫描分类
├── move_category.py              # 移动分类
├── move_pages.py                  # 移动页面
├── fix_links.py                   # 修复链接
├── update_cat_refs.py             # 更新分类引用
├── batch_processor.py             # 批处理工具模块
└── README.md                      # 本文档
```

## 更多信息

- [主文档](../README.md)
- [项目概览](../PROJECT.md)
- [Agent 指南](../AGENTS.md)
