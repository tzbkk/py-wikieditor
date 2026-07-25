# scan_and_convert.py - main 命名空间扫描转换工具

## 功能

扫描所有 main 命名空间（namespace=0）的页面，检测哪些需要转换，并交互式地逐个批准保存修改。

## 用法

```bash
python src/scan_and_convert.py
python src/scan_and_convert.py --limit 5
python src/scan_and_convert.py --scan-only
python src/scan_and_convert.py --approve-all
```

### 参数

- `--limit N`: 限制处理的页面数量
- `--scan-only`: 仅扫描，不进行转换
- `--approve-all`: 自动批准所有修改（非交互式）

## 示例

```bash
# 扫描并交互式转换所有 main 命名空间页面
python src/scan_and_convert.py

# 只扫描前 5 个可转换的页面
python src/scan_and_convert.py --limit 5

# 扫描但不转换（仅查看）
python src/scan_and_convert.py --scan-only

# 自动批准所有修改（非交互式）
python src/scan_and_convert.py --approve-all

# 通过 fandom.py 等价调用
python src/fandom.py scan
python src/fandom.py scan --limit 5 --approve-all
```

## 工作流程

扫描阶段：

1. 遍历所有 main 命名空间的页面
2. 检测每个页面是否包含繁体中文
3. 收集需要转换的页面列表
4. 显示扫描统计

转换阶段：

1. 对于每个需要转换的页面：
   - 显示页面名称和修改预览
   - 验证文件名保护
   - 询问用户是否批准
   - 保存修改（如果批准）

交互式选项：

- `y` - 批准并保存当前页面
- `n` - 跳过当前页面
- `a` - 批准剩余所有页面
- `q` - 退出转换

## 输出示例

```
✓ 已登录: bot_username

🔍 扫描 main 命名空间页面...

✓ 发现可转换页面: 页面1
  - 跳过: 页面2 (无需转换)
✓ 发现可转换页面: 页面3

📊 扫描完成:
   - 总扫描: 3 个页面
   - 可转换: 2 个页面

============================================================
[1/2] 处理: 页面1

📝 页面: 页面1
   总行数: 50, 修改行数: 12

   修改预览（前 3 处更改）:
   行 5:
     原: |名稱 = 值
     新: |名称 = 值

✓ 文件名保护验证通过

是否批准保存此页面的修改？ [y/n/a/q]: y
✅ 页面已保存

============================================================
📊 转换完成统计:
  - 批准并保存: 1
  - 跳过: 0
  - 失败: 0
```

## 特性

- 扫描所有 main 命名空间的页面
- 自动检测需要转换的页面
- 显示详细的修改预览
- 文件名保护验证
- 交互式批准机制
- 支持批量批准剩余页面
- 支持自动批准模式（非交互式）
- 支持仅扫描模式

## 使用场景

- 大范围清理残留的繁体中文
- 逐个审查转换结果
- 批量转换前预览效果
- 自动化转换大量页面
- 验证转换质量

## 注意事项

- 建议先用 --scan-only 查看需要转换的页面
- 交互模式下可以逐个审查
- 文件名保护机制会阻止可能误改文件名的操作
- 使用 --approve-all 时跳过所有交互
- 建议先在小范围测试
- **脚本只修改 Wiki 页面内容，不会修改任何脚本文件**
