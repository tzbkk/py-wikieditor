# Fandom Wiki 自动化转换工具 - 整合版

自动化的 Fandom Wiki 维护工具，主要用于繁体中文到简体中文的批量转换。

## ⚠️ 重要原则

**永远先测试单个页面，再批量应用！**

使用任何工具前，必须先用 `--dry-run` 或在单个页面上测试，确认无误后再批量应用。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的 Wiki 信息
```

### 3. 测试连接

```bash
python src/fandom.py test
python src/fandom.py test "STARS"
```

### 4. 开始使用

**推荐使用统一入口：**

```bash
# 转换单个页面（推荐第一步）
python src/fandom.py page "西片" --dry-run
python src/fandom.py page "西片"

# 检查 Wiki 上的结果

# 转换分类
python src/fandom.py category "音乐" --list
python src/fandom.py category "音乐" --dry-run
python src/fandom.py category "音乐"

# 转换模板
python src/fandom.py template "Template:角色信息" --list
python src/fandom.py template "Template:角色信息" --test "西片"
python src/fandom.py template "Template:角色信息" --batch

# 扫描并转换所有 main 命名空间页面
python src/fandom.py scan --scan-only
python src/fandom.py scan --limit 5 --approve-all

# 修复链接
python src/fandom.py fix-links "舊文本" "新文本" --dry-run

# 更新分类引用
python src/fandom.py update-cat-refs "片頭曲" --dry-run
```

## 工具集

### 工具一览

| 脚本 | 功能 | 模式 |
|------|------|------|
| [fandom.py](src/fandom.py) | 统一入口 | ⭐ 推荐 |
| [dump_xml.py](src/dump_xml.py) | XML dump（双模式） | 只读 |
| [dump_wiki.py](src/dump_wiki.py) | wikitext 文本 dump | 只读 |
| [scan_redlinks.py](src/scan_redlinks.py) | 扫描红链 | 只读 |
| [convert_page.py](src/convert_page.py) | 页面转换 | 修改 Wiki |
| [convert_category.py](src/convert_category.py) | 分类下转换 | 修改 Wiki |
| [convert_template.py](src/convert_template.py) | 模板嵌入转换 | 修改 Wiki |
| [scan_and_convert.py](src/scan_and_convert.py) | 扫描 main 交互转换 | 修改 Wiki |
| [scan_category.py](src/scan_category.py) | 扫描 category 交互转换 | 修改 Wiki |
| [move_pages.py](src/move_pages.py) | 移动页面 | 修改 Wiki |
| [move_category.py](src/move_category.py) | 移动分类（先更新引用） | 修改 Wiki |
| [fix_links.py](src/fix_links.py) | 修复链接 | 修改 Wiki |
| [update_cat_refs.py](src/update_cat_refs.py) | 更新分类引用 | 修改 Wiki |
| [restore_from_history.py](src/restore_from_history.py) | 历史版本恢复 | 修改 Wiki |

详见 [src/README.md](src/README.md) 和 [doc/tools/](doc/tools/)。

### 统一入口（推荐）

```bash
python src/fandom.py <command> [options]
```

**可用命令：**

| 命令 | 功能 |
|------|------|
| `page` | 转换单个或多个页面 |
| `category` | 转换分类下的所有页面 |
| `template` | 转换使用模板的所有页面 |
| `restore` | 从历史版本恢复页面 |
| `scan` | 扫描所有 main 命名空间页面并交互式转换 |
| `scan-category` | 扫描所有 category 命名空间页面并交互式转换 |
| `move-category` | 移动 category 页面（先更新链接，再移动页面） |
| `test` | 测试连接 |
| `info` | 获取模板/页面信息 |
| `fix-links` | 批量修复链接为简体版本 |
| `update-cat-refs` | 批量更新分类引用为简体中文 |

### 独立工具

也可以直接使用独立的工具脚本：

```bash
# 页面转换
python src/convert_page.py "页面名" [选项]

# 分类转换
python src/convert_category.py "分类名" [选项]

# 模板转换
python src/convert_template.py "Template:模板名" [选项]

# 恢复页面
python src/restore_from_history.py "页面名" [选项]

# 扫描转换
python src/scan_and_convert.py [选项]

# 扫描分类
python src/scan_category.py [选项]

# 移动分类
python src/move_category.py "旧分类名" [选项]

# 移动页面
python src/move_pages.py "页面名" [选项]

# 修复链接
python src/fix_links.py "舊文本" "新文本" [选项]

# 更新分类引用
python src/update_cat_refs.py "分类名" [选项]
```

## 功能特性

✅ **文件名保护** - 自动保护 .jpg, .png 等文件名不被修改  
✅ **智能转换** - 使用 OpenCC 进行高质量繁简转换  
✅ **变量名映射** - 自动转换模板变量名  
✅ **测试优先** - 支持先测试单个页面，再批量应用  
✅ **预览模式** - 使用 --dry-run 预览修改  
✅ **安全恢复** - 出错时可从历史版本恢复  
✅ **速率限制处理** - 自动处理 API 速率限制  
✅ **转换验证** - 自动验证文件名保护是否正确  

## 使用场景

### 场景 1：转换单个页面

```bash
python src/fandom.py page "西片" --dry-run
python src/fandom.py page "西片"
```

### 场景 2：转换多个页面

```bash
python src/fandom.py page "西片" "真野" "月本早苗"
python src/fandom.py page --from-file pages.txt
```

### 场景 3：搜索并转换页面

```bash
python src/fandom.py page --search "关键词"
python src/fandom.py page --search "关键词" --filter "过滤文本"
```

### 场景 4：转换页面及其子页面

```bash
python src/fandom.py page "动画第一季" --with-subpages
```

### 场景 5：转换分类下的所有页面

```bash
python src/fandom.py category "音乐" --list
python src/fandom.py category "音乐" --limit 5
python src/fandom.py category "音乐"
```

### 场景 6：转换分类页面本身

```bash
python src/fandom.py category --page "片頭曲" --dry-run
python src/fandom.py category --page "片頭曲"
```

### 场景 7：转换使用模板的所有页面

```bash
python src/fandom.py template "Template:角色信息" --list
python src/fandom.py template "Template:角色信息" --test "西片"
python src/fandom.py template "Template:角色信息" --batch
```

### 场景 8：扫描所有 main 命名空间页面

```bash
python src/fandom.py scan --scan-only
python src/fandom.py scan --limit 5 --approve-all
```

### 场景 9：修复链接

```bash
python src/fandom.py fix-links "舊文本" "新文本" --dry-run
python src/fandom.py fix-links "舊文本" "新文本"
```

### 场景 10：更新分类引用

```bash
python src/fandom.py update-cat-refs "片頭曲" "片尾曲" --dry-run
python src/fandom.py update-cat-refs --from-file categories.txt
```

### 场景 11：移动页面

```bash
python src/move_pages.py "舊頁面名" --dry-run
python src/move_pages.py "舊頁面名"
```

### 场景 12：扫描并转换分类页面

```bash
python src/fandom.py scan-category --scan-only
python src/fandom.py scan-category --limit 5 --approve-all
```

### 场景 13：移动分类页面

```bash
python src/fandom.py move-category "舊分類名" "新分類名" --dry-run
python src/fandom.py move-category "舊分類名" "新分類名"
python src/fandom.py move-category --from-file categories_to_move.txt
```

### 场景 14：恢复页面

```bash
python src/fandom.py restore "页面名" --show-versions
python src/fandom.py restore "页面名"
```

## 目录结构

```
.
├── .env                  # 环境变量配置（私有）
├── .env.example          # 配置示例
├── requirements.txt      # Python 依赖
├── fandom_bot.py         # 核心库
├── README.md             # 本文件
├── AGENTS.md             # Agent 使用指南
├── PROJECT.md            # 项目概览
├── src/                  # 工具脚本
│   ├── fandom.py         # 统一入口（推荐）⭐
│   ├── convert_page.py   # 页面转换
│   ├── convert_category.py  # 分类转换
│   ├── convert_template.py  # 模板转换
│   ├── restore_from_history.py  # 恢复页面
│   ├── scan_and_convert.py    # 扫描转换
│   ├── scan_category.py        # 扫描分类
│   ├── move_category.py        # 移动分类
│   ├── move_pages.py     # 移动页面
│   ├── fix_links.py      # 修复链接
│   ├── update_cat_refs.py     # 更新分类引用
│   ├── dump_xml.py       # XML dump（双模式）
│   ├── dump_wiki.py      # wikitext 文本 dump
│   ├── scan_redlinks.py  # 扫描红链
│   └── batch_processor.py      # 批处理工具模块
└── doc/                  # 文档
```

## 配置说明

### .env 文件

```bash
FANDOM_DOMAIN=your-wiki.fandom.com
FANDOM_PATH=/zh/
FANDOM_USERNAME=YourBot@BotName
FANDOM_PASSWORD=your_bot_password
CONVERSION_MODE=t2s
```

### 数据文件

项目提供示例文件来展示批量操作的格式：

- `pages.txt.example` - 页面列表格式，每行一个页面名称（以 `#` 开头的行会被忽略）
- `categories_to_move.txt` - 分类移动列表格式，每行包含旧名称和新名称

使用 `--from-file` 参数时可以参考这些示例文件。

### 获取 Bot 密码

1. 登录 Fandom Wiki
2. 访问 Special:BotPasswords
3. 创建一个新的 Bot 密码
4. 将用户名和密码填入 .env 文件

## 依赖

- Python 3.6+
- mwclient - MediaWiki API 客户端
- opencc - 繁简转换库
- python-dotenv - 读取 .env 文件（可选）

## 常见问题

### Q: 为什么要先测试？
A: 避免批量修改出错。测试可以让你先在一个页面上验证脚本是否正确工作。

### Q: 文件名会被修改吗？
A: 不会。所有工具都会自动保护文件名（.jpg, .png 等）不被修改，并有验证机制确保保护生效。

### Q: 如果转换出错怎么办？
A: 使用恢复工具可以从历史版本恢复页面：
```bash
python src/fandom.py restore "页面名"
```

### Q: 遇到速率限制怎么办？
A: 脚本会自动检测速率限制并等待 60 秒。如果多次遇到，可以稍后再试。

### Q: 可以转换其他语言吗？
A: 可以修改 .env 中的 CONVERSION_MODE。OpenCC 支持多种转换模式：
- t2s - 繁体到简体
- s2t - 简体到繁体
- 等等

## 安全检查清单

在批量转换前，确认以下事项：

- [ ] 已在单个页面上测试
- [ ] 已到 Wiki 上检查测试结果
- [ ] 变量名转换正确
- [ ] 内容转换为简体中文
- [ ] 文件名未被修改
- [ ] 预览了批量转换的页面列表

全部确认后，再执行批量转换。

## 重要提醒

**⚠️ 转换页面时，脚本只修改 Wiki 页面内容，不会修改任何脚本文件。**

所有转换工具都只用于：
- 读取和修改 Wiki 页面的**内容**
- 移动/重命名 Wiki 页面
- 更新页面中的链接或分类引用

**这些工具不会也不会修改任何 `.py` 脚本文件或代码文件。**

如需修改脚本功能，请使用代码编辑器手动编辑，并确保测试后再使用。

## 许可证

MIT License

## 更多信息

- [项目概览](PROJECT.md)
- [Agent 指南](AGENTS.md)
- [配置说明](doc/CONFIGURATION.md)
