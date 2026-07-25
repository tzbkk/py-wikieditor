# src/ 目录说明

这是项目的主要工具目录，包含所有 Wiki 操作工具。每个工具有独立的详细文档，见 [doc/tools/](../doc/tools/)。

## 统一入口

**[fandom.py](fandom.py)** - 统一命令行入口，封装所有子工具。详见 [doc/tools/fandom.md](../doc/tools/fandom.md)。

```bash
python src/fandom.py <command> [options]
```

子命令（共 13 个）：`page`、`category`、`template`、`restore`、`scan`、`scan-category`、`move-category`、`fix-links`、`update-cat-refs`、`dump-xml`、`dump-wiki`、`test`、`info`。

## 独立工具一览

按用途分类，每个工具的详细文档在 [doc/tools/](../doc/tools/) 下。

### 📥 数据导出 / 备份（只读）

| 脚本 | 功能 | 文档 |
|------|------|------|
| [dump_xml.py](dump_xml.py) | MediaWiki XML dump 格式（双模式 api\|special） | [doc/tools/dump_xml.md](../doc/tools/dump_xml.md) |
| [dump_wiki.py](dump_wiki.py) | wikitext 文本 dump（.wiki 文件） | [doc/tools/dump_wiki.md](../doc/tools/dump_wiki.md) |
| [scan_redlinks.py](scan_redlinks.py) | 扫描红链（指向不存在页面的链接） | [doc/tools/scan_redlinks.md](../doc/tools/scan_redlinks.md) |

### 🔄 繁简转换

| 脚本 | 功能 | 文档 |
|------|------|------|
| [convert_page.py](convert_page.py) | 通用页面转换 | [doc/tools/convert_page.md](../doc/tools/convert_page.md) |
| [convert_category.py](convert_category.py) | 分类下页面转换 | [doc/tools/convert_category.md](../doc/tools/convert_category.md) |
| [convert_template.py](convert_template.py) | 模板嵌入页面转换 | [doc/tools/convert_template.md](../doc/tools/convert_template.md) |
| [scan_and_convert.py](scan_and_convert.py) | 扫描 main 命名空间并交互转换 | [doc/tools/scan_and_convert.md](../doc/tools/scan_and_convert.md) |
| [scan_category.py](scan_category.py) | 扫描 category 命名空间并交互转换 | [doc/tools/scan_category.md](../doc/tools/scan_category.md) |

### 🚚 页面移动 / 链接修复

| 脚本 | 功能 | 文档 |
|------|------|------|
| [move_pages.py](move_pages.py) | 批量移动/重命名页面 | [doc/tools/move_pages.md](../doc/tools/move_pages.md) |
| [move_category.py](move_category.py) | 移动 category 页面（先更新引用） | [doc/tools/move_category.md](../doc/tools/move_category.md) |
| [fix_links.py](fix_links.py) | 批量修复链接为简体 | [doc/tools/fix_links.md](../doc/tools/fix_links.md) |
| [update_cat_refs.py](update_cat_refs.py) | 批量更新分类引用 | [doc/tools/update_cat_refs.md](../doc/tools/update_cat_refs.md) |

### 🛠️ 恢复 / 辅助

| 脚本 | 功能 | 文档 |
|------|------|------|
| [restore_from_history.py](restore_from_history.py) | 从历史版本恢复页面 | [doc/tools/restore_from_history.md](../doc/tools/restore_from_history.md) |
| [batch_processor.py](batch_processor.py) | 批处理工具模块（辅助） | [doc/tools/batch_processor.md](../doc/tools/batch_processor.md) |

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
├── fandom.py                    # 统一入口 ⭐
├── dump_xml.py                  # XML dump（双模式）
├── dump_wiki.py                 # wikitext 文本 dump
├── scan_redlinks.py             # 红链扫描
├── convert_page.py              # 页面转换
├── convert_category.py          # 分类转换
├── convert_template.py          # 模板转换
├── restore_from_history.py      # 恢复页面
├── scan_and_convert.py          # 扫描 main 命名空间
├── scan_category.py             # 扫描 category 命名空间
├── move_category.py             # 移动分类
├── move_pages.py                # 移动页面
├── fix_links.py                 # 修复链接
├── update_cat_refs.py           # 更新分类引用
├── batch_processor.py           # 批处理工具模块
└── README.md                    # 本文档
```

## 更多信息

- [主文档](../README.md)
- [工具详细文档](../doc/tools/)
- [项目概览](../doc/PROJECT.md)
- [Agent 指南](../AGENTS.md)