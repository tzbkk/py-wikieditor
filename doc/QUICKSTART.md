# 快速使用指南

## 1. 首次使用

### 1.1 安装依赖
```bash
pip install -r requirements.txt
```

### 1.2 配置

**方式1：使用 .env 文件（推荐）**
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

`.env` 文件内容：
```bash
FANDOM_DOMAIN=your-wiki.fandom.com
FANDOM_PATH=/zh/
FANDOM_USERNAME=YourBot@BotName
FANDOM_PASSWORD=your_bot_password
CONVERSION_MODE=t2s
```

**方式2：使用 config.json 文件**
```bash
cp config.json.example config.json
# 编辑 config.json 文件
```

### 1.3 测试连接
```bash
# 使用统一入口测试
python src/fandom.py test

# 或直接运行
python src/fandom.py test "STARS"
```

## 2. 常用场景

### 场景1: 转换模板及其引用的页面
```bash
# 列出使用模板的页面
python src/fandom.py template "Template:音樂信息" --list

# 测试单个页面
python src/fandom.py template "Template:音樂信息" --test "西片"

# 批量转换
python src/fandom.py template "Template:音樂信息" --batch
```

### 场景2: 转换分类
```bash
# 列出分类下的页面
python src/fandom.py category "音樂" --list

# 转换分类下的所有页面
python src/fandom.py category "音樂"

# 转换单个分类页面本身（含移动）
python src/fandom.py category --page "片頭曲"
```

### 场景3: 转换单个或多个页面
```bash
# 转换单个页面
python src/fandom.py page "西片"

# 转换多个页面
python src/fandom.py page "西片" "真野" "月本早苗"

# 从文件批量转换
python src/fandom.py page --from-file pages.txt

# 搜索并转换页面
python src/fandom.py page --search "关键词"

# 转换页面及其子页面
python src/fandom.py page "动画第一季" --with-subpages
```

### 场景4: 批量移动页面
```bash
# 移动指定页面
python src/move_pages.py "頁面1" "頁面2" "頁面3"

# 从文件批量移动
python src/move_pages.py --from-file pages.txt
```

### 场景5: 修复链接
```bash
# 修复单个链接
python src/fandom.py fix-links "舊文本" "新文本"

# 限制处理数量
python src/fandom.py fix-links "舊文本" "新文本" --limit 5

# 预览修复
python src/fandom.py fix-links "舊文本" "新文本" --dry-run
```

### 场景6: 更新分类引用
```bash
# 更新单个分类引用
python src/fandom.py update-cat-refs "片頭曲"

# 批量更新多个分类
python src/fandom.py update-cat-refs "片頭曲" "片尾曲"

# 从文件批量更新
python src/fandom.py update-cat-refs --from-file categories.txt
```

### 场景7: 扫描转换
```bash
# 仅扫描，查看可转换页面
python src/fandom.py scan --scan-only

# 扫描并转换（限制数量）
python src/fandom.py scan --limit 5 --approve-all

# 扫描并交互式转换
python src/fandom.py scan
```

### 场景8: 错误恢复
```bash
# 查看历史版本
python src/fandom.py restore "页面名" --show-versions

# 恢复页面
python src/fandom.py restore "页面名"
```

### 场景9: 获取信息
```bash
# 测试连接
python src/fandom.py test

# 获取模板信息
python src/fandom.py info "Template:模板名"
```

## 3. 工作流程建议

### 新 Wiki 转换流程
1. 测试连接 → `python src/fandom.py test`
2. 转换模板 → `python src/fandom.py template "Template:模板名" --batch`
3. 转换分类 → `python src/fandom.py category "分类名"`
4. 转换其他页面 → `python src/fandom.py page --from-file pages.txt`
5. 扫描转换 → `python src/fandom.py scan --limit 10 --approve-all`
6. 修复链接 → `python src/fandom.py fix-links "舊文本" "新文本"`
7. 更新分类引用 → `python src/fandom.py update-cat-refs --from-file categories.txt`

### 日常维护
- 单个页面修改：`python src/fandom.py page "页面名"`
- 批量重命名：`python src/move_pages.py "頁面1" "頁面2"`
- 查看模板：`python src/fandom.py info "Template:模板名"`
- 错误恢复：`python src/fandom.py restore "页面名"`

### 安全操作流程
1. 使用 `--dry-run` 预览修改
2. 在单个页面上测试
3. 到 Wiki 上检查结果
4. 确认无误后再批量转换

## 4. 重要选项说明

### 预览模式
所有转换工具都支持 `--dry-run` 选项，用于预览修改而不保存：
```bash
python src/fandom.py page "页面名" --dry-run
python src/fandom.py category "分类名" --dry-run
python src/fandom.py template "Template:模板名" --batch --dry-run
```

### 限制数量
用于测试或分批处理：
```bash
python src/fandom.py category "分类名" --limit 5
python src/fandom.py scan --limit 10
python src/fandom.py fix-links "舊文本" "新文本" --limit 20
```

### 从文件读取
支持从文件批量处理：
```bash
# 页面列表格式（pages.txt）
页面1
页面2
页面3
# 以 # 开头的行会被忽略

# 使用文件
python src/fandom.py page --from-file pages.txt
python src/move_pages.py --from-file pages.txt
python src/fandom.py update-cat-refs --from-file categories.txt
```

## 5. 注意事项

- ⚠️ **永远先测试单个页面，再批量应用！**
- 所有工具都会自动保护文件名不被修改
- 移动页面时不创建重定向
- 建议先在小范围测试
- 操作前确认配置正确
- 遇到速率限制时，工具会自动等待 60 秒

## 6. 快速参考

| 功能 | 命令 |
|------|------|
| 测试连接 | `python src/fandom.py test` |
| 转换页面 | `python src/fandom.py page "页面名"` |
| 转换分类 | `python src/fandom.py category "分类名"` |
| 转换模板 | `python src/fandom.py template "Template:模板名" --batch` |
| 扫描转换 | `python src/fandom.py scan --limit 5 --approve-all` |
| 扫描分类 | `python src/fandom.py scan-category --limit 5 --approve-all` |
| 移动分类 | `python src/fandom.py move-category "旧分类名" "新分类名"` |
| 修复链接 | `python src/fandom.py fix-links "舊文本" "新文本"` |
| 更新分类引用 | `python src/fandom.py update-cat-refs "分类名"` |
| 移动页面 | `python src/move_pages.py "舊頁面名"` |
| 恢复页面 | `python src/fandom.py restore "页面名"` |
| 获取信息 | `python src/fandom.py info "Template:模板名"` |

## 7. 常见问题

### Q: 如何查看所有可用命令？
A: 运行 `python src/fandom.py --help`

### Q: 转换出错怎么办？
A: 使用 `python src/fandom.py restore "页面名"` 从历史版本恢复

### Q: 文件名会被修改吗？
A: 不会，所有工具都会自动保护文件名

### Q: 可以只预览不修改吗？
A: 可以，使用 `--dry-run` 选项

### Q: 如何限制处理数量？
A: 使用 `--limit N` 选项

## 8. 更多帮助

- [主文档](../README.md)
- [项目概览](../PROJECT.md)
- [Agent 指南](../AGENTS.md)
- [详细文档](./README.md)
