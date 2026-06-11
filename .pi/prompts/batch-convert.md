---
name: wiki-batch-convert
description: 批量转换工作流。扫描需要转换的页面 → dry-run 预览 → 确认后实际转换。适用于日常 Wiki 维护。
---

# 批量转换工作流

## 步骤

### 1. 测试连接
```
/wiki_test
```

### 2. 扫描需要转换的页面
```
/wiki_scan namespace=main scan_only=true limit=10
```

### 3. 对单个页面预览
```
/wiki_convert_page page_name="页面名" dry_run=true
```

### 4. 确认后实际转换
```
/wiki_convert_page page_name="页面名" dry_run=false
```

## 注意事项

- 始终从 dry-run 开始
- 批量操作先用 limit 测试少量页面
- 转换后到 Wiki 上检查结果
- 出问题用 `wiki_restore` 恢复
