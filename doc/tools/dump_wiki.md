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
- `--list-only` — 只列出页面标题,不下载内容(增量模式下打印变更事件而非下载)
- `--skip-existing` — 跳过已存在且非空的本地文件(断点续传,仅全量模式生效)
- `--dump-dir PATH` <str> — 输出目录(默认 `wiki_dump/`)
- `--incremental` — 增量模式:基于 `index.json` 的 `_meta.last_dump_timestamp` 拉 `recentchanges` 增量更新(需先跑一次全量 dump 建立基线)

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

# 增量更新(首次必须先跑全量建立 _meta.last_dump_timestamp)
python src/dump_wiki.py --incremental

# 增量预览:只列出会处理的变更事件,不下载/写文件
python src/dump_wiki.py --incremental --list-only

# 仅对指定命名空间做增量
python src/dump_wiki.py --incremental --ns 0 10
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
  "_meta": {
    "schema_version": 2,
    "dump_mode": "full",
    "last_dump_timestamp": "2026-07-25T10:30:00Z"
  },
  "雖然不會說出口。": {
    "file": "main/雖然不會說出口。。wiki",
    "length": 1234,
    "ns": 0,
    "ns_dir": "main",
    "touched": "2024-01-01T00:00:00Z"
  },
  "愛歌": {
    "file": "main/愛歌.wiki",
    "length": 567,
    "ns": 0,
    "ns_dir": "main",
    "touched": "2024-02-15T12:34:56Z"
  },
  "Template:角色信息": {
    "file": "Template/Template:角色信息.wiki",
    "length": 2345,
    "ns": 10,
    "ns_dir": "Template",
    "touched": "2024-03-10T08:00:00Z"
  }
}
```

**字段说明**

- `_meta`(v2 起新增):索引元数据,记录 schema 版本、上次 dump 模式与时间戳
  - `schema_version`:固定为 2
  - `dump_mode`:`full`(全量)或 `incremental`(增量)
  - `last_dump_timestamp`:ISO 8601 UTC,作为下次 `--incremental` 的 `rcstart` 起点
- `touched`(v2 起新增):单页最后修改时间(来自 MediaWiki API),ISO 8601 UTC

**向下兼容**:读取旧版 `index.json`(无 `_meta`)时,全量模式自动升级格式;增量模式会要求先跑一次全量建立基线。

## 工作流程

### 全量模式(默认)

1. 连接 Wiki 并登录
2. 按命名空间遍历所有页面
3. 使用 `page.text()` 获取 wikitext 内容
4. 写入对应命名空间目录下的 `.wiki` 文件
5. 生成 `index.json` 索引文件,记录所有页面的元信息(含 `_meta` 与每页 `touched`)

### 增量模式(--incremental)

1. 读取 `index.json` 的 `_meta.last_dump_timestamp` 作为起点(无则报错退出)
2. 调用 `list=recentchanges&rcstart=<ts>&rcdir=newer` 拉每个命名空间的变更事件:
   - `rctype=edit|new|move` — 拉编辑/新建/移动事件
   - `rctype=log` + `rc_log_type=delete` — 单独拉删除事件
   - `list=logevents&letype=move` — 单独拉移动事件的 from/to 配对(避免 recentchanges 中 move 的 title 歧义)
3. 按事件类型处理:
   - `edit`/`new`/`move` 目标 title → 重新拉 `page.text()` 覆盖本地 `.wiki` 文件,更新 index
   - `delete` title → 删除本地 `.wiki` 文件,从 index 移除
   - `move` 源 title → 删除本地源文件,目标由上述步骤已刷新
4. 全部成功后更新 `_meta.last_dump_timestamp` 为当前时间(避免半成功状态丢失时间锚点)

**速率限制**:`ratelimited` 自动 sleep 60 秒后重试一次,其它异常打印 ❌ 后继续下一页,不中断流程。

**MediaWiki 窗口限制**:recentchanges 默认 30 天窗口。距上次 dump > 25 天时会打印 warning 提示窗口风险,但仍尝试执行(由用户决定是否先跑全量)。

## 输出示例

### 全量模式

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

### 增量模式

```
🔗 连接 Wiki ...
✓ 已登录: bot_username
🕐 增量起点: 2026-07-25T05:10:42Z

📁 命名空间 0 (main/)
  ✏️  更新: 某页面
  ➕ 新页面: 另一页面
  ➖ 已删除: 旧页面

📁 命名空间 10 (Template/)

============================================================
📊 增量 dump 总结
============================================================
命名空间处理数: 5
变更事件: edit=3 new=1 move=0 delete=1
本地文件: 新增=1 更新=3 删除=1
新 last_dump_timestamp: 2026-07-25T05:11:02Z
```

### `--incremental --list-only` 预览模式

```
📁 命名空间 0 (main/)
  • [edit] 某页面
  • [new] 另一页面
  • [delete] 旧页面

📋 --list-only 模式，未写入任何文件
```

## 特性

- 按命名空间自动分类存放
- 生成 JSON 索引便于快速查找
- 支持断点续传(--skip-existing)
- 支持增量更新(--incremental,基于 recentchanges)
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
- **增量模式要求先跑一次全量**建立 `_meta.last_dump_timestamp` 基线
- **脚本是只读操作,不会修改任何 Wiki 页面**
