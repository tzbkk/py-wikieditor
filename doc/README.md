# Fandom Wiki 自动化工具集

## 概述

本工具集用于自动化操作 Fandom Wiki，主要功能包括：
- 繁体中文转简体中文
- 批量页面转换
- 模板和分类处理
- 页面移动和重命名

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 或手动安装
pip install mwclient opencc python-dotenv

# 激活虚拟环境（如果使用）
source venv/bin/activate
```

## 配置说明

### 方式1：使用 .env 文件（推荐）

1. 复制示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：
```bash
# Wiki 站点配置
FANDOM_DOMAIN=your-wiki.fandom.com
FANDOM_PATH=/zh/

# 机器人账号（在 Special:BotPasswords 创建）
FANDOM_USERNAME=YourBot@BotName
FANDOM_PASSWORD=your_bot_password

# 转换模式（t2s=繁体转简体，s2t=简体转繁体）
CONVERSION_MODE=t2s

# 跳过的字段名（逗号分隔，可选）
# SKIP_FIELDS=图片,圖片
```

### 方式2：使用 config.json 文件

1. 复制示例文件：
```bash
cp config.json.example config.json
```

2. 编辑 `config.json` 文件，根据注释说明填入你的配置。

### 获取机器人密码

1. 登录你的 Fandom Wiki
2. 访问 `Special:BotPasswords`
3. 创建一个新的机器人密码
4. 记下用户名（格式：YourName@BotName）和密码
