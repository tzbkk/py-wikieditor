# AGENTS.md

This file contains guidelines for agentic coding agents working in this repository.

## Build/Test Commands

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Running Tests
```bash
# Run a simple connection test
python src/fandom.py test
python src/fandom.py test "STARS"

# Test single page conversion (recommended first step)
python src/fandom.py page "页面名" --dry-run

# Test category conversion
python src/fandom.py category "分类名" --dry-run --limit 5

# Test template conversion
python src/fandom.py template "Template:模板名" --test "测试页面名" --dry-run

# Test scan and convert
python src/fandom.py scan --limit 5 --approve-all
```

### Running Scripts
```bash
# Unified entry point (recommended) ⭐
python src/fandom.py <command> [options]

# Direct script execution
python src/convert_page.py "页面名"
python src/convert_category.py "分类名"
python src/convert_template.py "Template:模板名"
python src/restore_from_history.py "页面名"
python src/scan_and_convert.py
python src/scan_category.py
python src/move_category.py "旧分类名" "新分类名"
python src/move_pages.py "页面名"
python src/fix_links.py "舊文本" "新文本"
python src/update_cat_refs.py "分类名"
```

### Running Single File Tests
There is no formal test framework (pytest/unittest). Use dry-run mode to test changes before applying:
```bash
python src/fandom.py page "页面名" --dry-run --show-diff
python src/fandom.py category "分类名" --dry-run --limit 3
python src/fandom.py template "Template:模板名" --test "测试页面名" --dry-run
```

## Code Style Guidelines

### File Structure
Executable scripts use shebang: `#!/usr/bin/env python3`, UTF-8 encoding: `open(file, 'r', encoding='utf-8')`, module-level docstrings

### Import Order
1. Standard library (sys, os, re, argparse, time)
2. Third-party (mwclient, opencc, dotenv)
3. Local (from fandom_bot import ...)

For src/ scripts, add: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`

### Type Hints
Use `typing` module for type hints:
```python
from typing import List, Optional, Callable, Tuple, Dict

def protect_filenames(text: str) -> Tuple[str, Dict[str, str]]:
    """保护所有文件名不被转换"""
    pass

def batch_process_pages(self, pages: List, processor: Callable, show_progress: bool = True):
    pass
```

### Naming Conventions
- Classes: CamelCase (`FandomBot`)
- Functions: snake_case (`convert_page`, `verify_conversion`)
- Variables: snake_case (`page_name`, `new_content`)
- Constants: UPPER_CASE (`FILE_EXTENSIONS`, `VARIABLE_MAPPINGS`)
- Private attributes: single underscore prefix (`_load_from_env`)

### Constants
Module-level constants defined at top:
```python
FILE_EXTENSIONS = r'(?:jpg|jpeg|png|gif|svg|webp|bmp|ico|tiff?|pdf|ogg|mp3|mp4|webm|ogv)'
```

### Function Documentation
Use triple-quoted docstrings:
```python
def convert_page(text, bot):
    """转换单个页面的文本"""
    text, protected = protect_filenames(text)
    text = bot.cc.convert(text)
    text = restore_filenames(text, protected)
    return text
```

### Error Handling
Use try-except for API operations:
```python
try:
    bot.edit_page(page, new_content, summary="转换为简体中文")
    print(f"✅ 页面已保存")
    return True
except Exception as e:
    print(f"❌ 保存失败: {e}")
    return False
```

Handle rate limits:
```python
if 'ratelimited' in str(e).lower():
    print("  ⏳ 遇到速率限制，等待 60 秒...")
    time.sleep(60)
```

### CLI Arguments
Use `argparse` with `RawDescriptionHelpFormatter`:
```python
parser = argparse.ArgumentParser(
    description='Fandom Wiki 通用转换工具',
    formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument('pages', nargs='*', help='要转换的页面名称')
parser.add_argument('--dry-run', action='store_true', help='预览模式')
```

### Progress and Logging
Use print statements with emojis for user feedback:
```python
print(f"📄 转换页面: {page_name}")
print(f"✅ 页面已保存")
print(f"❌ 页面不存在: {page_name}")
print(f"[{i}/{total}] 处理: {page.name}")
```

### Configuration
- Environment variables loaded from `.env` file (not in git)
- Use `python-dotenv` if available, fallback to `config.json`

### File Operations
Always specify UTF-8 encoding:
```python
with open(file_path, 'r', encoding='utf-8') as f:
    page_names = [line.strip() for line in f if line.strip() and not line.startswith('#')]
```

### Testing Workflow
Test before batch operations: use `--dry-run`, test single page, verify filename protection, check Wiki results

### Code Comments
Comments in Chinese, use sparingly, prefer self-documenting code, docstrings for all functions/classes

### Important Safety Notes
Never modify `.env`, never commit credentials, always use `--dry-run` before batch, protect file extensions

**CRITICAL: Scripts only modify Wiki page content, never modify script files.**
- All conversion tools (convert_page.py, convert_category.py, etc.) only read/edit Wiki pages
- They will NOT modify any .py script files or code files
- Never assume running a script will modify code files
- If you need to modify scripts, use a code editor and test before using
