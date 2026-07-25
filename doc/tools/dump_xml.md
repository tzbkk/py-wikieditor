# dump_xml.py - MediaWiki XML 导出工具

## 功能

以 MediaWiki XML dump 格式批量导出 Wiki 页面,产物格式与 `Special:Export` / `dumpBackup.php` 兼容,可用 `mwxml` 库或 `php importDump.php` 处理。

## 用法

```bash
python src/dump_xml.py
python src/dump_xml.py --ns 0 10 14 --mode special --history
```

### 参数

- `--ns N [N ...]` <int> — 命名空间 ID 列表,默认 `[0, 10, 14, 828, 4]`
- `--mode {api,special}` <str> — 导出模式:api=快速仅当前版本;special=流式支持完整历史,默认 'api'
- `--history` — 包含完整 revision history(仅 `--mode special` 有效)
- `--list-only` — 只列出页面,不下载
- `--skip-existing` — 跳过已存在且非空的 XML 文件
- `--force` — 忽略已有 progress 和文件,强制重新下载
- `--dump-dir PATH` <str> — 输出目录,默认 'wiki_dump_xml'
- `--delay FLOAT` <float> — 请求间延迟秒数,默认 1.0
- `--schema VERSION` <str> — XML dump schema 版本(仅 api 模式),默认 '0.11'
- `--incremental` — 增量 dump 模式(仅 `--mode special`):基于 recentchanges + revid 高水位,产出 `<NS>.delta.<ts>.xml` 独立文件

## 示例

```bash
# 默认下载(全部内容命名空间,api 模式)
python src/dump_xml.py

# 指定命名空间(仅主命名空间和模板)
python src/dump_xml.py --ns 0 10

# 完整历史导出(使用 special 模式)
python src/dump_xml.py --mode special --history

# 只列出页面,不实际下载
python src/dump_xml.py --list-only

# 断点续传(跳过已下载的文件)
python src/dump_xml.py --skip-existing

# 通过 fandom.py dump-xml 子命令调用
python src/fandom.py dump-xml --ns 0 10

# 自定义输出目录和延迟
python src/dump_xml.py --dump-dir my_dump --delay 2.0

# 导出指定命名空间的完整历史
python src/dump_xml.py --ns 14 --mode special --history --skip-existing

# 增量 dump(必须先跑一次全量 special --history 建立 baseline)
python src/dump_xml.py --mode special --history --incremental

# 仅对指定命名空间做增量
python src/dump_xml.py --mode special --history --incremental --ns 0 10

# 强制重跑全量(忽略已有 progress)
python src/dump_xml.py --mode special --history --force
```

### 文件格式

输出为标准 MediaWiki XML 格式,每命名空间一个文件:

```xml
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <page>
    <title>页面名称</title>
    <ns>0</ns>
    <id>1</id>
    <revision>
      <id>1234</id>
      <timestamp>2024-01-01T00:00:00Z</timestamp>
      <contributor><username>用户名</username></contributor>
      <text>页面内容</text>
    </revision>
  </page>
</mediawiki>
```

## 工作流程

### API 模式 (--mode api)

1. 通过 `action=query&export=1&exportnowrap=1` 接口批量获取页面
2. 每批 50 个 title,流式写盘(flush+fsync)
3. 仅导出当前版本内容
4. 写入对应命名空间的 XML 文件

### Special 模式 (--mode special)

> **注意**:Fandom 用 Cloudflare 拦截真正的 `Special:Export` 端点(返回 403 "Just a moment..." JS challenge),所以本模式不走传统 `index.php` POST 路径。改用 `api.php` 的 `prop=revisions` API 拉每个页面的全部 revisions,然后按 MediaWiki export-0.11 schema 手动构造等价 XML。

1. 通过 `list=allpages` 拉命名空间全部页面 `[(pageid, title), ...]`
2. 对每个 pageid 单独调用 `prop=revisions&rvlimit=500` 翻页(MW 硬限制:rvlimit>1 时只能查单页)
3. 流式写入 `<page>` 元素,每页 fsync 到磁盘
4. `.progress.json` 记录 `last_completed_idx` 支持断点续传
5. `--history` 时包含完整 revision history(本模式默认就是完整历史)

### 增量模式 (--mode special --history --incremental)

> 仅 special 模式可用(api 模式无完整历史,无 revid 高水位概念)

1. 读取 `<NS>.xml.progress.json` 中的 `last_full_dump_timestamp` 与 `last_full_dump_max_revid` 作为 baseline(无则报错退出,要求先跑全量)
2. 调用 `list=recentchanges&rcstart=<ts>&rcdir=newer` 拉事件:
   - `rctype=edit|new|move` — 编辑/新建/移动事件
   - `rctype=log` + `rc_log_type=delete` — 删除事件(写入 `.deleted.<ts>.txt`)
3. 按 pageid 聚合事件:
   - `edit` → `prop=revisions&rvstartid=<last_max_revid+1>&rvdir=newer` 只拉新于 baseline 的 revisions(`rvstartid` 是 inclusive,+1 排除已 dump 的最后一个)
   - `new` → `_fetch_all_revisions` 拉全部 revisions(新页面无 baseline)
   - `move` → 记入 `.deleted.<ts>.txt`(importDump 不支持 move 语义)
4. 写入独立的 `<NS>.delta.<UTC ts>.xml`(含完整 EXPORT_HEADER/FOOTER,可直接 `importDump.php` 导入)
5. 同时产出 `<NS>.deleted.<UTC ts>.txt`(仅当有删除/移动事件时)
6. 更新 progress 的 `last_incremental_timestamp` 与 `last_incremental_max_revid`(不动 `last_full_*`)

**MediaWiki 窗口限制**:recentchanges 默认 30 天窗口。距上次 dump > 25 天时会打印 warning。

**向后兼容**:旧版 progress(无 `last_full_dump_*`)在 `--incremental` 时会自动从 XML 扫描最大 revid 推断 baseline 并补写字段。

## 输出示例

### 全量模式 (api 或 special)

```
🔗 连接 Wiki ...
✓ 已登录: bot_username

📁 命名空间 0 (main/) → wiki_dump_xml/main.xml
  [1/50] batch ✓
  [51/50] batch ✓
  ✅ Namespace main: 1234 pages → wiki_dump_xml/main.xml (4567kb)

📁 命名空间 10 (Template/) → wiki_dump_xml/Template.xml
  [1/200] 25 revs total
  [26/200] 130 revs total
  ✅ Namespace Template: 200 pages → wiki_dump_xml/Template.xml (2345kb)

🎉 完成!处理 5/5 个命名空间,1434 个页面,总 6912 kb XML
```

### 增量模式 (special --history --incremental)

```
🔗 连接 Wiki ...
✓ 已登录: bot_username

📁 命名空间 0 (main/) → wiki_dump_xml/main.xml
  📄 拉 recentchanges since 2026-07-25T05:10:42Z (ns=0) ...
  📊 12 个 edit/new/move 事件, 1 个 delete 事件
  ✅ 某页面: +1 revs
  ✅ 另一页面: +3 revs
  ✅ main delta: 5 页, +12 revs → wiki_dump_xml/main.delta.20260725-051102.xml (12kb)
  🗑️  删除/移动清单: wiki_dump_xml/main.deleted.20260725-051102.txt (1 项)
  📊 新 max_revid: 12345

🎉 增量完成!处理 5/5 个命名空间,23 个变更页,+89 个新 revision,
    3 个删除/移动事件,总 145 kb delta XML
```

### 进度文件 `<NS>.xml.progress.json`

```json
{
  "first_pageid": 1,
  "last_pageid": 1234,
  "last_completed_idx": 1233,
  "done": true,
  "ns_id": 0,
  "total": 1234,
  "timestamp": 1753438000.5,
  "last_full_dump_timestamp": "2026-07-25T05:10:42Z",
  "last_full_dump_max_revid": 12340,
  "last_incremental_timestamp": "2026-07-25T06:00:00Z",
  "last_incremental_max_revid": 12400
}
```

## 特性

- 双模式导出:API 模式快速,Special 模式支持完整历史
- 增量更新(special 模式):基于 recentchanges + revid 高水位,产出独立 delta XML
- 按命名空间分类输出
- 支持断点续传(--skip-existing)
- 列表模式(--list-only)快速预览
- 可调节请求延迟(--delay)适应不同速率限制
- 兼容标准 MediaWiki XML 格式
- 可通过 fandom.py 子命令调用

## 使用场景

- 定期备份 Wiki 内容
- 批量迁移 Wiki 数据到其他站点
- 离线分析 Wiki 内容结构
- 使用 mwxml 库进行批量文本处理
- 准备数据导入到其他 MediaWiki 实例
- 建立完整的历史版本归档

## 注意事项

- API 模式不支持完整 history 导出(技术限制)
- Fandom 速率限制默认 1 req/s,可通过 `--delay` 调整
- Fandom 用 Cloudflare 拦截 `Special:Export` 端点,special 模式实际走 `prop=revisions` API
- XML 文件可用 `php importDump.php < dump.xml` 导入其他 wiki
- special 模式下 `--history` 会显著增加数据量(本模式默认就是完整历史)
- 导出过程中网络中断可使用 `--skip-existing` 断点续传
- 输出目录会自动创建,无需手动准备
- **增量模式要求先跑一次全量** special --history,在 `.progress.json` 中建立 `last_full_dump_*` baseline
- 增量产出的 `<NS>.delta.<ts>.xml` 是独立文件,不修改原 `<NS>.xml`
- **脚本是只读操作,不会修改任何 Wiki 页面**
