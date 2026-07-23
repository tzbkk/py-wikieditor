# Slash Command Specification

This document defines all 10 slash commands exposed by the wiki-batch-convert prompt template.

## Command Classification Table

| # | Command | fandom.py subcommand | Level | Default | Needs --confirm? | Args |
|---|---------|---------------------|-------|---------|-----------------|------|
| 1 | `/wiki_test` | `test` | Safe | direct exec | No | (none) |
| 2 | `/wiki_info` | `info` | Safe | direct exec | No | `[template_name]` |
| 3 | `/wiki_convert_page` | `page --dry-run` | Bounded | dry-run | Yes (to override) | `page_name="..."` + optional `--confirm` |
| 4 | `/wiki_convert_category` | `category --dry-run` | Bounded | dry-run | Yes | `category="..."` + optional `--confirm` `--limit N` |
| 5 | `/wiki_convert_template` | `template --dry-run` | Bounded | dry-run | Yes | `template="..."` + optional `--confirm` |
| 6 | `/wiki_restore` | `restore --show-versions` | Bounded | show-versions only | Yes (to actually restore) | `page_name="..."` + optional `--confirm` |
| 7 | `/wiki_scan` | `scan --scan-only` | Read | scan-only | N/A | optional `--limit N` (NEVER --approve-all) |
| 8 | `/wiki_scan_category` | `scan-category --scan-only` | Read | scan-only | N/A | optional `--limit N` (NEVER --approve-all) |
| 9 | `/wiki_fix_links` | `fix-links --dry-run` | Destructive | dry-run | Yes | `old_text="..."` `new_text="..."` + optional `--confirm` |
| 10 | `/wiki_update_cat_refs` | `update-cat-refs --dry-run` | Destructive | dry-run | Yes | `[categories...]` or `--from-file FILE` + optional `--confirm` |

## NOT Exposed as Slash Commands

The following operations are NOT exposed as slash commands due to their large blast radius. Use bash directly:

| Operation | Bash Command | Reason |
|-----------|--------------|--------|
| Batch scan and convert | `python src/fandom.py scan --approve-all` | Skips per-page confirmation, too risky |
| Batch scan category | `python src/fandom.py scan-category --approve-all` | Same as above |
| Move category | `python src/fandom.py move-category "旧分类名" "新分类名"` | Affects many pages, high blast radius |

### Blocked by Permission Gate

The `--no-test-first` flag is globally blocked by the permission gate and never available via any slash command.

## Risk Levels Explained

- **Safe**: Read-only operations, no Wiki modifications possible
- **Bounded**: Can modify Wiki but has safeguards (dry-run default, confirm required)
- **Read**: Read-only scanning, but can enumerate large amounts of content
- **Destructive**: Can modify many pages, requires explicit confirmation