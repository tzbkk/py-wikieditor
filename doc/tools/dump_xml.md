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
- `--dump-dir PATH` <str> — 输出目录,默认 'wiki_dump_xml'
- `--delay FLOAT` <float> — 请求间延迟秒数,默认 1.0
- `--schema VERSION` <str> — XML dump schema 版本(仅 api 模式),默认 '0.11'

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
2. 每批最多 500 页,自动翻页累积
3. 仅导出当前版本内容
4. 写入对应命名空间的 XML 文件

### Special 模式 (--mode special)

1. 通过 `Special:Export` 页面 POST 请求导出
2. 使用流式下载,每批 35 页
3. 支持 `--history` 包含完整修订历史
4. 适合大型 Wiki(>10000 页)

## 输出示例

```
🔗 连接 Wiki ...
✓ 已登录: bot_username

📁 命名空间 0 (main/)
[1/50] 雖然不會說出口。 — ✓
[2/50] 愛歌 — ✓
[3/50] STARS — ✓
…
[50/50] 零釐米 — ✓
✅ Namespace main: 1234 pages → wiki_dump_xml/main.xml (4567kb)

📁 命名空间 10 (Template/)
[1/200] Template:角色信息 — ✓
[2/200] Template:区分 — ✓
…
✅ Namespace Template: 200 pages → wiki_dump_xml/Template.xml (2345kb)

🎉 完成！共处理 1434 个页面
```

## 特性

- 双模式导出:API 模式快速,Special 模式支持完整历史
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
- 大型 Wiki(>10000 页)建议使用 special 模式更稳定
- XML 文件可用 `php importDump.php < dump.xml` 导入其他 wiki
- special 模式下 `--history` 会显著增加数据量
- 导出过程中网络中断可使用 `--skip-existing` 断点续传
- 输出目录会自动创建,无需手动准备
- **脚本是只读操作,不会修改任何 Wiki 页面**
