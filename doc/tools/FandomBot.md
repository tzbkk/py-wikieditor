# FandomBot - 基础机器人类库

## 概述

`fandom_bot.py` 是整个工具集的核心库，提供了操作 Fandom Wiki 的基础功能。

## 类说明

### FandomBot

主要的机器人类，封装了常用的 Wiki 操作。

#### 初始化

```python
from fandom_bot import FandomBot

bot = FandomBot(config_file="config.json")
```

#### 主要方法

##### convert_text(text)
将文本从繁体转换为简体中文。

- **参数**:
  - `text`: 要转换的文本
- **返回**: 转换后的文本

```python
content = bot.convert_text("這是繁體字")
```

##### get_page(page_name)
获取页面对象。

```python
page = bot.get_page("STARS")
```

##### get_category_members(category_name)
获取分类下的所有页面。

```python
pages = bot.get_category_members("音樂")
```

##### get_template_embedded_pages(template_name)
获取引用指定模板的所有页面。

```python
pages = bot.get_template_embedded_pages("Template:音樂信息")
```

##### edit_page(page, content, summary="自动编辑")
编辑页面内容。

```python
bot.edit_page(page, new_content, summary="转换为简体中文")
```

##### move_page(page, new_name, reason="页面移动", no_redirect=True)
移动/重命名页面。

```python
bot.move_page(page, "新页面名", reason="改名为简体中文")
```

##### replace_in_page(page, pattern, replacement, summary="文本替换")
在页面中进行正则替换。

```python
bot.replace_in_page(page, r'\[\[Category:音樂\]\]', '[[Category:音乐]]')
```

##### batch_process_pages(pages, processor, show_progress=True)
批量处理页面。

```python
def process_func(page):
    content = page.text()
    new_content = bot.convert_text(content)
    bot.edit_page(page, new_content)

bot.batch_process_pages(pages, process_func)
```

##### get_subpages(prefix)
获取指定前缀的所有子页面。

```python
subpages = bot.get_subpages("动画第一季")
```

## 属性

- `site`: mwclient.Site 对象
- `cc`: OpenCC 转换器对象
- `config`: 配置字典

## 使用示例

```python
from fandom_bot import FandomBot

bot = FandomBot()

# 获取页面并转换
page = bot.get_page("STARS")
original = page.text()
new_content = bot.convert_text(original)

if original != new_content:
    bot.edit_page(page, new_content, summary="转换为简体中文")
```

## 配置说明

### 方式1：使用 .env 文件（推荐）

创建 `.env` 文件：

```bash
# Wiki 站点配置
FANDOM_DOMAIN=your-wiki.fandom.com
FANDOM_PATH=/zh/

# 机器人账号
FANDOM_USERNAME=YourBot@BotName
FANDOM_PASSWORD=your_bot_password

# 转换模式
CONVERSION_MODE=t2s
```

### 方式2：使用 config.json 文件

创建 `config.json` 文件（参考 config.json.example）：

```json
{
  "site": {
    "domain": "your-wiki.fandom.com",
    "path": "/zh/"
  },
  "auth": {
    "username": "YourBot@BotName",
    "password": "your_bot_password"
  },
  "conversion": {
    "mode": "t2s",
    "skip_fields": ["图片", "圖片"]
  }
}
```

### 配置优先级

1. 如果存在 `.env` 文件，优先使用环境变量
2. 否则使用 `config.json` 文件
3. 都不存在则报错
