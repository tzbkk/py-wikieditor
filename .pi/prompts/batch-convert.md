---
name: wiki-batch-convert
description: 批量转换工作流。扫描待转换页面 → dry-run 预览 → 确认后实际转换。
---

# 批量转换工作流

## 步骤

### 1. 测试连接
```
/wiki_test
```
验证 Wiki 登录正常。

### 2. 扫描需要转换的页面
```
/wiki_scan --limit 10
```
默认 scan-only 模式，仅列出待转换页面，不会修改任何内容。

### 3. 对单个页面预览（dry-run）
```
/wiki_convert_page page_name="页面名"
```
默认 dry-run，预览转换结果但不实际保存。

### 4. 确认后实际转换
```
/wiki_convert_page page_name="页面名" --confirm
```
`--confirm` 会弹出确认对话框，确认后去掉 --dry-run 实际写入。

### 5. 出问题时恢复
```
/wiki_restore page_name="页面名"
```
默认只列历史版本。加 `--confirm` 选择具体版本恢复。

## 其他可用命令

| 命令 | 用途 | 默认行为 |
|------|------|---------|
| `/wiki_info [template_name]` | 查看模板/页面信息 | 直接执行 |
| `/wiki_convert_category category="..."` | 转换分类下所有页面 | dry-run |
| `/wiki_convert_template template="..."` | 转换使用模板的页面 | dry-run |
| `/wiki_scan_category` | 扫描分类命名空间 | scan-only |
| `/wiki_fix_links old_text="..." new_text="..."` | 批量修复链接 | dry-run |
| `/wiki_update_cat_refs [categories...]` | 更新分类引用 | dry-run |

## 注意事项

- **始终从 dry-run 开始** — 所有破坏型命令默认 dry-run，加 `--confirm` 才会实际执行
- **`--confirm` 会弹确认对话框** — 即使加了 `--confirm`，也需要在对话框中再次确认
- **批量操作先用 `--limit` 测试少量页面**
- **转换后到 Wiki 上检查结果**

## 不可用命令（用 bash 直接调）

以下操作 blast radius 过大，不暴露为 slash command，需要用 bash 手动执行：

- **批量扫描转换** — `python src/fandom.py scan --approve-all`（跳过逐页确认）
- **批量扫描分类** — `python src/fandom.py scan-category --approve-all`
- **移动分类** — `python src/fandom.py move-category "旧分类名" "新分类名"`

⚠️ 使用上述 bash 命令前务必先用 `--dry-run` 测试。

## 安全规则

- 所有 slash command 都被 permission gate 保护
- `--no-test-first` flag 被全局拦截，不可使用
- `wiki_save_page` 工具内容含 `__待填__` 时自动拦截