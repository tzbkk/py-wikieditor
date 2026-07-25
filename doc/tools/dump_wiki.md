# dump_wiki.py - Wiki 页面文本导出工具

## 功能

将 Wiki 页面以纯 wikitext 格式导出到本地文件系统,按命名空间分类存放,并生成索引文件。与 `dump_xml.py` 的区别在于产物是 `.wiki` 纯文本文件而非 XML 格式。

## 用法

```bash
python src/dump_wiki.py
python src/dump_wiki.py --ns 0 10 --list-only
```

### 参数

- `--ns N [N ...]` <int> — 指定命名空间 ID(默认下载内容命名空间)
- `--list-only` — 只列出页面标题,不下载内容
- `--skip-existing` — 跳过已存在且非空的本地文件(断点续传)
- `--dump-dir PATH` <str> — 输出目录(默认 `wiki_dump/`)

## 示例

```bash
# 下载默认内容命名空间
python src/dump_wiki.py

# 指定命名空间(仅主命名空间和模板)
python src/dump_wiki.py --ns 0 10

# 只列出页面,不下载内容
python src/dump_wiki.py --list-only

# 断点续传(跳过已下载的文件)
python src/dump_wiki.py --skip-existing

# 自定义输出目录
python src/dump_wiki.py --dump-dir my_wiki_dump

# 列出指定命名空间的页面
python src/dump_wiki.py --ns 14 --list-only
```

### 文件格式

#### 页面文件

每个页面保存为 `.wiki` 纯文本文件,包含完整的 wikitext 内容:

```
wiki_dump/
├── main/
│   ├── 雖然不會說出口。。wiki
│   ├── 愛歌.wiki
│   └── ...
├── Template/
│   ├── Template:角色信息.wiki
│   └── ...
└── index.json
```

#### 索引文件(index.json)

```json
{
  "雖然不會說出口。": {
    "file": "main/雖然不會說出口。。wiki",
    "length": 1234,
    "ns": 0,
    "ns_dir": "main"
  },
  "愛歌": {
    "file": "main/愛歌.wiki",
    "length": 567,
    "ns": 0,
    "ns_dir": "main"
  },
  "Template:角色信息": {
    "file": "Template/Template:角色信息.wiki",
    "length": 2345,
    "ns": 10,
    "ns_dir": "Template"
  }
}
```

## 工作流程

1. 连接 Wiki 并登录
2. 按命名空间遍历所有页面
3. 使用 `page.text()` 获取 wikitext 内容
4. 写入对应命名空间目录下的 `.wiki` 文件
5. 生成 `index.json` 索引文件,记录所有页面的元信息

## 输出示例

```
🔗 连接 Wiki ...
✓ 已登录: bot_username

📁 命名空间 0 (main/)
  • 雖然不會說出口。
  • 愛歌
  • STARS
  …
  • 零釐米
  ✅ main/ 共 1234 页

📁 命名空间 10 (Template/)
  • Template:角色信息
  • Template:区分
  …
  • Template:新闻模块
  ✅ Template/ 共 200 页

📋 索引已写入 wiki_dump/index.json(1434 个页面)

🎉 完成！共处理 1434 个页面
```

## 特性

- 按命名空间自动分类存放
- 生成 JSON 索引便于快速查找
- 支持断点续传(--skip-existing)
- 列表模式(--list-only)快速预览
- 子页面自动创建子目录
- 纯文本格式易于阅读和编辑
- 与 scan_redlinks.py 配合使用

## 使用场景

- 离线浏览和编辑 Wiki 内容
- 批量文本搜索和替换
- 配合 scan_redlinks.py 扫描红链
- 准备数据进行文本分析
- 快速备份核心内容
- 本地开发 Wiki 功能

## 与 dump_xml.py 的区别

| 特性 | dump_wiki.py | dump_xml.py |
|------|--------------|-------------|
| 输出格式 | `.wiki` 纯文本 | XML 格式 |
| 是否包含元数据 | 仅 index.json | 完整 XML 元数据 |
| 适用场景 | 文本处理、快速备份 | 迁移、导入、归档 |
| 工具配合 | scan_redlinks.py | importDump.php |

## 注意事项

- 默认下载内容命名空间:main(0)、Template(10)、Category(14)、Module(828)、Project(4)
- 输出目录会自动创建,无需手动准备
- 子页面分隔符 '/' 会保留为子目录
- 与 dump_xml.py 相比更轻量,适合文本处理
- scan_redlinks.py 依赖此脚本产生的 `wiki_dump/index.json`
- 建议定期运行以保持本地数据同步
- **脚本是只读操作,不会修改任何 Wiki 页面**
