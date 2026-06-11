"""fandom_bot.py — Fandom Wiki 繁體→簡體中文自動轉換機器人的核心庫。

提供 FandomBot 類別，封裝 MediaWiki API 連線、認證、頁面操作，
以及基於 OpenCC 的繁簡轉換功能。同時提供文件名保護、程式碼區塊保護
等安全機制，確保轉換過程中不會破壞圖片連結或程式碼片段。
"""

import mwclient
from opencc import OpenCC
import json
import re
import os
from typing import Dict, List, Tuple

_has_dotenv = False
_load_dotenv_func = None
try:
    from dotenv import load_dotenv as _ld
    _has_dotenv = True
    _load_dotenv_func = _ld
except ImportError:
    pass


__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# 文件擴展名常量
# ---------------------------------------------------------------------------
FILE_EXTENSIONS = r'(?:jpg|jpeg|png|gif|svg|webp|bmp|ico|tiff?|pdf|ogg|mp3|mp4|webm|ogv)'

# ---------------------------------------------------------------------------
# 預編譯正則表達式 — 文件名保護
# ---------------------------------------------------------------------------
_RE_WIKI_FILE_LINK = re.compile(
    rf'\[\[(File|Image|文件|檔案):([^\|\]]+?\.{FILE_EXTENSIONS})([^\]]*?)\]\]',
    re.IGNORECASE,
)

_RE_FILE_PREFIX = re.compile(
    rf'(File|Image|文件|檔案):[^\|\]\[\n]+?\.{FILE_EXTENSIONS}',
    re.IGNORECASE,
)

_RE_GALLERY_FILE = re.compile(
    rf'^([^\|\]\[=\n]+?\.{FILE_EXTENSIONS})(?=\s*$|\s*\|)',
    re.MULTILINE | re.IGNORECASE,
)

_RE_VALUE_FILE = re.compile(
    rf'=([^\|\]\[\n=]+?\.{FILE_EXTENSIONS})(?=\s*$|\s*[\|\]])',
    re.IGNORECASE,
)

_RE_VERIFY_FILENAME = re.compile(
    rf'[^\s\[\]|=]*?\.{FILE_EXTENSIONS}',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 預編譯正則表達式 — 程式碼區塊保護
# ---------------------------------------------------------------------------
_RE_CODE_BLOCK = re.compile(
    r'(<(?:source|syntaxhighlight|code|pre|nowiki)(?:\s[^>]*)?>)(.*?)(</(?:source|syntaxhighlight|code|pre|nowiki)>)',
    re.DOTALL | re.IGNORECASE,
)


def safe_error(e: Exception) -> str:
    """清理異常訊息，移除敏感資訊後回傳安全顯示字串"""
    msg = str(e)
    msg = re.sub(r'(token|session|cookie)[=:]\s*\S+', '[REDACTED]', msg, flags=re.IGNORECASE)
    if len(msg) > 200:
        msg = msg[:200] + '...'
    return msg


# ---------------------------------------------------------------------------
# 文件名保護
# ---------------------------------------------------------------------------
def protect_filenames(text: str) -> Tuple[str, Dict[str, str]]:
    """保護所有文件名不被轉換，支持帶空格的文件名"""
    protected = {}
    counter = [0]

    def get_placeholder():
        placeholder = f'__PROTECTED_FILE_{counter[0]}__'
        counter[0] += 1
        return placeholder

    # [[File:xxx.jpg|...]] 或 [[Image:xxx.jpg|...]] - 只保護文件名部分
    def replace_wiki_file_link(match):
        placeholder = get_placeholder()
        prefix = match.group(1)
        filename = match.group(2)
        params = match.group(3) if match.lastindex >= 3 else ''
        protected[placeholder] = f'{prefix}:{filename}'
        return f'[[{placeholder}{params}]]'

    text = _RE_WIKI_FILE_LINK.sub(replace_wiki_file_link, text)

    # File:xxx.jpg 或 Image:xxx.jpg（不含方括號，支持帶空格）
    def replace_file_prefix(match):
        placeholder = get_placeholder()
        protected[placeholder] = match.group(0)
        return placeholder

    text = _RE_FILE_PREFIX.sub(replace_file_prefix, text)

    # gallery 標籤中的純文件名（行首開始，支持帶空格）
    def replace_gallery_file(match):
        placeholder = get_placeholder()
        protected[placeholder] = match.group(1)
        return placeholder

    text = _RE_GALLERY_FILE.sub(replace_gallery_file, text)

    # =xxx.jpg 形式的文件名值（= 後面直接是文件名，支持帶空格）
    def replace_value_file(match):
        placeholder = get_placeholder()
        protected[placeholder] = match.group(1)
        return '=' + placeholder

    text = _RE_VALUE_FILE.sub(replace_value_file, text)

    return text, protected


def restore_filenames(text: str, protected: Dict[str, str]) -> str:
    """恢復保護的文件名，使用單次正則替換確保效率"""
    if not protected:
        return text
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(protected, key=len, reverse=True)))
    return pattern.sub(lambda m: protected[m.group()], text)


def verify_filenames_preserved(original: str, converted: str) -> Tuple[bool, List[str]]:
    """驗證文件名是否被正確保護"""
    files_orig = set(_RE_VERIFY_FILENAME.findall(original))
    files_new = set(_RE_VERIFY_FILENAME.findall(converted))

    if files_orig == files_new:
        return True, []

    errors = []
    if files_orig - files_new:
        errors.append(f"丢失: {files_orig - files_new}")
    if files_new - files_orig:
        errors.append(f"新增: {files_new - files_orig}")

    return False, errors


# ---------------------------------------------------------------------------
# 程式碼區塊保護
# ---------------------------------------------------------------------------
def protect_code_blocks(text: str) -> Tuple[str, Dict[str, str]]:
    """保護 <source>/<syntaxhighlight>/<code>/<pre>/<nowiki> 標籤內容不被轉換"""
    protected = {}
    counter = [0]

    def replace_block(match):
        placeholder = f'__PROTECTED_CODE_{counter[0]}__'
        counter[0] += 1
        protected[placeholder] = match.group(0)
        return placeholder

    text = _RE_CODE_BLOCK.sub(replace_block, text)
    return text, protected


def restore_code_blocks(text: str, protected: Dict[str, str]) -> str:
    """恢復被保護的程式碼區塊"""
    if not protected:
        return text
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(protected, key=len, reverse=True)))
    return pattern.sub(lambda m: protected[m.group()], text)


# ---------------------------------------------------------------------------
# FandomBot 類別
# ---------------------------------------------------------------------------
class FandomBot:
    """Fandom Wiki 機器人核心類別。

    封裝 MediaWiki API 連線、認證、頁面讀寫與繁簡轉換功能。
    支援從 .env 環境變數或 config.json 檔案載入設定。
    """

    def __init__(self, config_file: str = "config.json"):
        if _has_dotenv and os.path.exists('.env'):
            assert _load_dotenv_func is not None
            _load_dotenv_func()
            self.config = self._load_from_env()
        elif os.path.exists(config_file):
            self.config = self._load_from_json(config_file)
        else:
            raise FileNotFoundError(
                "未找到配置文件！\n"
                "请创建 .env 文件或 config.json 文件。\n"
                "参考 config.json.example 示例。"
            )

        domain = self.config['site']['domain']
        if domain.startswith('http://'):
            raise ValueError(
                f"不安全的域名配置 '{domain}'，僅允許 HTTPS 連線。"
                "请移除 'http://' 前綴，直接提供域名（如 example.fandom.com）。"
            )
        if domain.startswith('https://'):
            domain = domain[len('https://'):]
        domain = domain.rstrip('/')

        self.site = mwclient.Site(domain, path=self.config['site']['path'])
        self.site.login(
            self.config['auth']['username'],
            self.config['auth']['password']
        )

        # 登入成功後清除密碼
        del self.config['auth']['password']

        self.cc = OpenCC(self.config['conversion']['mode'])

    def __repr__(self):
        return f"FandomBot(site={self.config['site']['domain']})"

    def _load_from_env(self) -> Dict[str, Dict[str, str]]:
        """從環境變數載入配置，若缺少必要變數則拋出 ValueError"""
        domain = os.getenv('FANDOM_DOMAIN')
        username = os.getenv('FANDOM_USERNAME')
        password = os.getenv('FANDOM_PASSWORD')

        missing = []
        if not domain:
            missing.append('FANDOM_DOMAIN')
        if not username:
            missing.append('FANDOM_USERNAME')
        if not password:
            missing.append('FANDOM_PASSWORD')

        if missing:
            raise ValueError(
                f"缺少必要的環境變數: {', '.join(missing)}\n"
                "请在 .env 文件中設定這些變數。"
            )

        assert domain is not None
        assert username is not None
        assert password is not None

        return {
            'site': {
                'domain': domain,
                'path': os.getenv('FANDOM_PATH', '/zh/')
            },
            'auth': {
                'username': username,
                'password': password
            },
            'conversion': {
                'mode': os.getenv('CONVERSION_MODE', 't2s'),
            }
        }

    def _load_from_json(self, config_file: str) -> Dict[str, Dict[str, str]]:
        """從 JSON 配置文件載入設定"""
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config = {k: v for k, v in config.items() if not k.startswith('_')}

        for section in config.values():
            if isinstance(section, dict):
                keys_to_remove = [k for k in section.keys() if k.startswith('_')]
                for k in keys_to_remove:
                    del section[k]

        return config

    def convert_text(self, text: str) -> str:
        """將文字從繁體中文轉換為簡體中文，保護文件名和程式碼區塊"""
        text, code_protected = protect_code_blocks(text)
        text, file_protected = protect_filenames(text)
        text = self.cc.convert(text)
        text = restore_filenames(text, file_protected)
        text = restore_code_blocks(text, code_protected)
        return text

    def get_page(self, page_name: str) -> 'mwclient.page.Page':
        """根據頁面名稱取得頁面物件"""
        return self.site.pages[page_name]

    def get_category_members(self, category_name: str) -> List[object]:
        """取得分類下的所有頁面成員"""
        cat = self.site.categories[category_name]
        return list(cat.members())

    def get_template_embedded_pages(self, template_name: str) -> List[object]:
        """取得使用指定模板的所有頁面"""
        return list(self.site.pages[template_name].embeddedin())

    def edit_page(self, page, content: str, summary: str = "自动编辑") -> None:
        """編輯頁面，寫入新內容"""
        page.edit(content, summary=summary)

    def move_page(self, page, new_name: str, reason: str = "页面移动", no_redirect: bool = True) -> None:
        """移動頁面到新名稱"""
        page.move(new_name, reason=reason, no_redirect=no_redirect)

    def get_subpages(self, prefix: str) -> List[object]:
        """取得指定前綴的所有子頁面"""
        return list(self.site.allpages(prefix=prefix + '/'))
