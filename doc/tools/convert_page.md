# convert_page.py - 通用页面转换工具

## 功能

将任意页面从繁体中文转换为简体中文。支持单个页面、批量处理、搜索模式和子页面转换。

## 用法

```bash
python src/convert_page.py [page1] [page2] ...
python src/convert_page.py --from-file pages.txt
python src/convert_page.py --search "关键词"
```

### 参数

- `page1, page2, ...`: 要转换的页面名称列表
- `--from-file FILE`: 从文件读取页面列表
- `--search KEYWORD`: 搜索包含关键词的页面
- `--filter PATTERN`: 额外过滤模式（只保留包含此字符串的页面）
- `--list`: 只列出页面，不转换（配合 --search 使用）
- `--dry-run`: 预览模式，不实际保存
- `--show-diff`: 显示修改详情（前 30 行）
- `--with-subpages`: 同时转换子页面

## 示例

```bash
# 转换单个页面
python src/convert_page.py "西片"

# 预览单个页面的修改
python src/convert_page.py "西片" --dry-run

# 显示修改详情
python src/convert_page.py "西片" --show-diff

# 转换多个页面
python src/convert_page.py "西片" "真野" "月本早苗"

# 从文件读取页面列表
python src/convert_page.py --from-file pages.txt

# 搜索包含关键词的页面
python src/convert_page.py --search "关键词"

# 搜索模式 + 预览
python src/convert_page.py --search "关键词" --dry-run

# 转换页面及其子页面
python src/convert_page.py "动画第一季" --with-subpages

# 通过 fandom.py 等价调用
python src/fandom.py page "西片"
python src/fandom.py page "西片" --show-diff
python src/fandom.py page "西片" --with-subpages --dry-run
```

## 工作流程

对于每个页面：

1. 获取页面内容
2. 将繁体转换为简体
3. 验证文件名保护（确保文件名未被误改）
4. 显示转换统计（总行数、修改行数）
5. 可选显示修改详情（--show-diff）
6. 保存修改（非预览模式）

带子页面模式：

1. 转换主页面
2. 获取所有子页面列表
3. 逐个转换子页面
4. 显示统计信息

## 输出示例

```
✓ 已登录: bot_username

📄 转换页面: 西片

📊 转换统计 - 西片
  - 总行数: 50
  - 修改行数: 12
  ✓ 文件名保护正常

✅ 页面已保存
```

```
✓ 已登录: bot_username

=== 批量转换页面 ===
共 3 个页面

[1/3] 西片
  ✓ 已转换

[2/3] 真野
  ℹ️  无需修改

[3/3] 月本早苗
  ✓ 已转换

✅ 完成统计:
  - 总页面数: 3
  - 已修改: 2
  - 跳过: 1
  - 失败: 0
```

## 特性

- 支持单个页面、批量处理、搜索模式
- 从命令行参数或文件读取页面列表
- 自动文件名保护验证
- 预览模式查看将要执行的修改
- 显示修改详情（--show-diff）
- 支持子页面转换（--with-subpages）
- 搜索和过滤功能
- 统计信息显示成功/失败/跳过数量

## 使用场景

- 转换单个页面内容
- 批量转换多个页面
- 搜索特定关键词的页面并转换
- 转换页面及其所有子页面
- 预览修改后再实际保存

## 注意事项

- 建议先使用 --dry-run 预览修改
- 建议先使用 --show-diff 查看具体变更
- 文件名保护机制会阻止可能误改文件名的操作
- 操作不可逆，建议先备份
- 不会移动页面，只转换内容
- **脚本只修改 Wiki 页面内容，不会修改任何脚本文件**
