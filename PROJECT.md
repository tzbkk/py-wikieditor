# Fandom Wiki 转换工具项目概览

## 项目定位

这是一个通用的 Fandom Wiki 繁简转换工具，可以安全地将任意页面从繁体中文转换为简体中文。

## 核心价值

1. **通用性** - 可以转换任意页面、分类或模板
2. **安全性** - 自动保护文件名，先测试再批量应用
3. **易用性** - 统一的命令行界面，清晰的帮助信息
4. **可靠性** - 转换验证、历史恢复、错误处理

## 技术架构

```
fandom_bot.py (核心库)
    ↓
src/ (工具层)
    ├── fandom.py (统一入口) ⭐
    ├── convert_page.py
    ├── convert_category.py
    ├── convert_template.py
    ├── restore_from_history.py
    ├── scan_and_convert.py
    ├── scan_category.py
    ├── move_category.py
    ├── move_pages.py
    ├── fix_links.py
    ├── update_cat_refs.py
    └── batch_processor.py (批处理模块)
    ↓
用户 (命令行)
```

## 核心机制

### 1. 文件名保护

使用正则表达式匹配并保护文件名：
- 识别 `File:xxx.jpg` 格式
- 识别独立文件名（在 gallery 中）
- 使用占位符替换
- 转换后恢复
- 验证文件名未被修改

### 2. 繁简转换

使用 OpenCC 库进行高质量转换：
- 支持多种转换模式
- 保留原有格式
- 保护特殊内容

### 3. 安全机制

- **测试模式** - 单个页面测试
- **预览模式** - --dry-run 预览
- **自动测试** - 批量前测试第一个
- **转换验证** - 检查文件名保护
- **历史恢复** - 出错可恢复

### 4. 错误处理

- 速率限制自动等待
- 详细的错误信息
- 失败页面跳过
- 统计成功/失败数量

## 使用场景

### 场景 1: 日常维护

定期将新增的繁体页面转换为简体：

```bash
# 列出分类下的页面
python src/fandom.py category "音乐" --list

# 转换新增页面
python src/fandom.py page "新页面1" "新页面2"
```

### 场景 2: 批量转换

将整个分类或模板的页面转换：

```bash
# 转换分类
python src/fandom.py category "角色"

# 转换模板
python src/fandom.py template "Template:角色信息" --batch
```

### 场景 3: 错误恢复

转换出错后恢复页面：

```bash
# 查看历史
python src/fandom.py restore "页面名" --show-versions

# 恢复
python src/fandom.py restore "页面名"
```

### 场景 4: 扫描转换

扫描所有 main 命名空间页面并交互式转换：

```bash
# 仅扫描
python src/fandom.py scan --scan-only

# 扫描并转换（限制数量）
python src/fandom.py scan --limit 5 --approve-all
```

### 场景 5: 搜索转换

搜索包含关键词的页面并转换：

```bash
# 搜索并转换
python src/fandom.py page --search "关键词"

# 搜索并过滤
python src/fandom.py page --search "关键词" --filter "过滤文本"
```

### 场景 6: 链接修复

批量修复链接为简体版本：

```bash
# 修复链接
python src/fandom.py fix-links "舊文本" "新文本"

# 预览修复
python src/fandom.py fix-links "舊文本" "新文本" --dry-run
```

### 场景 7: 分类引用更新

批量更新分类引用为简体中文：

```bash
# 更新分类引用
python src/fandom.py update-cat-refs "片頭曲" "片尾曲"

# 从文件批量更新
python src/fandom.py update-cat-refs --from-file categories.txt
```

### 场景 8: 扫描分类页面

扫描所有 category 命名空间页面并交互式转换：

```bash
# 仅扫描
python src/fandom.py scan-category --scan-only

# 扫描并转换（限制数量）
python src/fandom.py scan-category --limit 5 --approve-all
```

### 场景 9: 移动分类页面

移动 category 页面（先更新链接，再移动页面）：

```bash
# 移动单个分类
python src/fandom.py move-category "舊分類名" "新分類名"

# 从文件批量移动
python src/fandom.py move-category --from-file categories_to_move.txt

# 预览移动
python src/fandom.py move-category "舊分類名" "新分類名" --dry-run
```

## 扩展性

### 添加新的变量名映射

编辑 `src/convert_template.py` 中的 `VARIABLE_MAPPINGS` 字典。

### 添加新的保护规则

修改 `fandom_bot.py` 中的 `protect_filenames()` 函数，添加新的正则表达式模式。

### 支持其他转换模式

修改 `.env` 中的 `CONVERSION_MODE`。

### 扩展批处理功能

使用 `batch_processor.py` 中的 `BatchProcessor` 类创建新的批处理工具。

## 维护指南

### 日常维护

1. 定期检查工具是否正常工作
2. 更新变量名映射（如果 Wiki 添加了新模板）
3. 收集用户反馈，改进工具

### 版本更新

1. 测试新功能
2. 更新文档
3. 标记版本号

### 问题排查

1. 查看错误日志
2. 使用 --dry-run 预览
3. 检查文件名保护
4. 验证转换结果

## 未来计划

- [ ] Web UI 界面
- [ ] 更多转换模式
- [ ] 批量操作队列
- [ ] 进度保存和恢复
- [ ] 更详细的统计报告
- [ ] 自动检测需要转换的页面
- [ ] 支持更多 Wiki 平台
- [ ] 并发处理提高效率

## 贡献

欢迎贡献代码、报告问题或提出建议！

## 许可证

MIT License
