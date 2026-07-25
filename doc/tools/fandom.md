# fandom.py - Fandom Wiki 转换工具集

## 功能

统一的命令行工具，提供所有转换功能。封装所有子工具，通过子命令调用，实现单一登录入口和参数转发。

## 用法

```bash
python src/fandom.py <command> [options]
python src/fandom.py --help
python src/fandom.py <command> --help
```

## 子命令清单

| 子命令 | 说明 | 转发到 |
|--------|------|--------|
| `page` | 转换单个或多个页面 | convert_page.py |
| `category` | 转换分类下的所有页面 | convert_category.py |
| `template` | 转换使用模板的所有页面 | convert_template.py |
| `restore` | 从历史版本恢复页面 | restore_from_history.py |
| `scan` | 扫描 main 命名空间页面 | scan_and_convert.py |
| `scan-category` | 扫描 category 命名空间 | scan_category.py |
| `move-category` | 移动 category 页面 | move_category.py |
| `fix-links` | 批量修复链接 | fix_links.py |
| `update-cat-refs` | 批量更新分类引用 | update_cat_refs.py |
| `dump-xml` | 下载 XML dump(双模式) | dump_xml.py |
| `dump-wiki` | 下载 wikitext 文本 | dump_wiki.py |
| `test` | 测试连接 | 内置 |
| `info` | 获取模板/页面信息 | 内置 |

## 示例

```bash
# 测试连接
python src/fandom.py test

# 转换单个页面
python src/fandom.py page "西片"

# 预览页面转换
python src/fandom.py page "西片" --dry-run

# 显示修改详情
python src/fandom.py page "西片" --show-diff

# 转换页面及其子页面
python src/fandom.py page "动画第一季" --with-subpages

# 搜索并转换页面
python src/fandom.py page --search "关键词"

# 转换分类下的所有页面
python src/fandom.py category "音乐"

# 列出使用模板的页面
python src/fandom.py template "Template:角色信息" --list

# 测试单个页面转换
python src/fandom.py template "Template:角色信息" --test "西片"

# 批量转换使用模板的页面
python src/fandom.py template "Template:角色信息" --batch

# 从历史版本恢复页面
python src/fandom.py restore "西片"

# 查看历史版本
python src/fandom.py restore "西片" --show-versions

# 扫描 main 命名空间
python src/fandom.py scan

# 扫描 category 命名空间
python src/fandom.py scan-category

# 移动 category 页面
python src/fandom.py move-category "舊分類" "新分類"

# 批量修复链接
python src/fandom.py fix-links "舊文本" "新文本"

# 批量更新分类引用
python src/fandom.py update-cat-refs "片頭曲" "片尾曲"

# 获取模板信息
python src/fandom.py info "Template:音樂信息"
```

## 工作流程

fandom.py 采用参数转发机制：

1. 解析子命令和参数
2. 对于 `test` 和 `info` 命令：
   - 直接内置处理
   - 调用 FandomBot 获取信息
3. 对于其他子命令：
   - 重写 `sys.argv` 为对应子脚本的参数格式
   - 导入子脚本模块
   - 调用子脚本的 `main()` 函数
4. 子脚本继续处理具体逻辑

这种设计实现了：
- 单一登录入口（只需配置一次凭据）
- 统一的命令行接口
- 参数等价转发
- 子命令独立帮助信息

## 输出示例

### 测试连接
```
✓ 已登录: bot_username

页面标题: STARS
是否存在: True

页面内容:
#redirect [[STARS]]
```

### 获取模板信息
```
模板页面: Template:音樂信息
是否存在: True

模板内容:
{{Infobox song
|名稱 = 歌曲名
|歌手 = 歌手名
...
}}
```

### 帮助信息
```
usage: fandom.py [-h] {page,category,template,restore,scan,scan-category,move-category,fix-links,update-cat-refs,dump-xml,dump-wiki,test,info} ...

Fandom Wiki 转换工具集

positional arguments:
  {page,category,template,restore,scan,scan-category,move-category,fix-links,update-cat-refs,dump-xml,dump-wiki,test,info}
    page            转换单个或多个页面
    category        转换分类下的所有页面
    template        转换使用模板的所有页面
    restore         从历史版本恢复页面
    scan            扫描所有 main 命名空间页面并交互式转换
    scan-category   扫描所有 category 命名空间页面并交互式转换
    move-category   移动 category 页面（先更新链接，再移动页面）
    fix-links       批量修复链接为简体版本
    update-cat-refs 批量更新分类引用为简体中文
    dump-xml        下载 XML dump
    dump-wiki       下载 wikitext 文本
    test            测试连接
    info            获取模板/页面信息

optional arguments:
  -h, --help        show this help message and exit
```

### 子命令帮助
```
usage: fandom.py page [-h] [--from-file FILE] [--dry-run] [--show-diff] [--search KEYWORD] [--filter FILTER] [--list] [--with-subpages] [pages ...]

positional arguments:
  pages                 要转换的页面名称

optional arguments:
  -h, --help            show this help message and exit
  --from-file FILE      从文件读取页面列表
  --dry-run             预览模式
  --show-diff           显示修改详情
  --search KEYWORD      搜索包含关键词的页面
  --filter FILTER       额外过滤模式
  --list                只列出页面
  --with-subpages       同时转换子页面
```

## 特性

- **统一入口**：所有功能通过一个命令访问
- **单一登录**：只需配置一次凭据，所有子命令共享
- **参数转发**：子命令参数等价转发到对应脚本
- **独立帮助**：每个子命令都有独立的 `--help` 信息
- **内置命令**：test 和 info 命令内置处理，无需外部脚本
- **灵活调用**：既可直接调用子脚本，也可通过 fandom.py 调用

## 使用场景

- **日常使用**：通过 fandom.py 作为主要命令行工具
- **批量操作**：使用 scan、category、template 等子命令
- **快速测试**：使用 test 命令验证连接
- **信息查询**：使用 info 命令获取模板/页面信息
- **错误恢复**：使用 restore 命令从历史版本恢复
- **链接修复**：使用 fix-links 命令批量更新链接
- **分类管理**：使用 move-category 和 update-cat-refs 管理分类

## 注意事项

- 建议先使用 `test` 命令验证连接和凭据
- 建议先使用 `--dry-run` 预览修改
- 各子命令的详细参数请使用 `--help` 查看
- 参数转发机制确保子命令参数与直接调用子脚本一致
- test 和 info 命令是内置的，不转发到外部脚本
- dump-xml 和 dump-wiki 命令需要对应脚本支持
- **脚本只修改 Wiki 页面内容，不会修改任何脚本文件**
