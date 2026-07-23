
## T10: Destructive slash commands + wiki_save_page confirm gate (2026-07-23)

### What worked
- `parseArgs` from T9 handles `key="value"` (kwarg), `--flag` (flag), bare tokens (positional).
  Slash-command users pass `from_file="cats.txt"` (no `--` prefix) — parser stores it as kwarg.
  Inside the handler we then translate to `cmdArgs.push("--from-file", fromFile)` for fandom.py.
- Section banners (`// =====`) match existing convention in wiki-tools.ts for navigating
  the now-751-line file.
- `createMockCtx` defaults `ctx.ui.confirm` to `false`, which conveniently tests the
  "abort by default" path without explicit mocking — only the `--confirm` tests need
  `vi.mocked(ctx.ui.confirm).mockResolvedValue(true)`.
- `pi._toolHandlers['wiki_save_page']` exposes the tool's execute function directly for
  handler-level tests bypassing tool_call dispatch.
- The __待填__ check in wiki_save_page execute function short-circuits BEFORE the confirm
  gate — intentional ordering (placeholder check is cheaper and more specific).

### Gotcha
- `--from-file="cats.txt"` is parsed as a single flag named `from-file="cats.txt"` by
  parseArgs (because it starts with `--`). Users must pass `from_file="cats.txt"` instead.
  This matches T9's existing convention (e.g. `limit="5"` not `--limit="5"`).

### File sizes
- wiki-tools.ts: 651 → 751 lines (+100 for confirm gate + 2 commands + section banner)
- tests/test_destructive_commands.test.ts: 228 lines, 10 tests (4 fix_links + 4 cat_refs + 2 save_page)
- Total tests: 24 → 34, all passing

## T11 — Integration tests (2026-07-23)

### Test infrastructure facts
- vitest config at `tests/vitest.config.ts` uses `include: ['**/*.test.ts']`, so adding `tests/integration/*.test.ts` files is auto-discovered — no config changes needed.
- pytest.ini already declares `tests/` as testpaths with an `integration` marker pre-registered. New `tests/integration/test_*.py` files are auto-discovered.
- Existing subpackage pattern: `tests/test_wiki_tools_handlers/__init__.py` exists, so added `tests/integration/__init__.py` for consistency.

### Path depth from tests/integration/
- Helpers: `../helpers/mockExtensionContext`
- Extension: `../../.pi/extensions/wiki-tools.ts`

### Python e2e test patterns
- `_bot` module-level singleton in `wiki_bot_server.py` must be reset between tests; `_edit_with_retry` can null it on login errors. Use `autouse=True` fixture that saves/restores `wiki_bot_server._bot`.
- Mock at `wiki_bot_server.get_bot` (the callable), not at `fandom_bot.FandomBot.get_bot`. The retry path calls `get_bot()` again after nulling `_bot`, and our patch returns the same mock both times.
- `safe_error()` is importable from `fandom_bot` and redacts `token=`, `session=`, `cookie=` substrings — useful for asserting security invariants.

### Cross-gate ordering observation
- `dispatchToolCall` iterates handlers in registration order: gate 1 (danger bash, confirm-gated) → gate 2 (sensitive path, hard block) → gate 3 (--no-test-first) → gate 4 (__待填__). For a command matching multiple gates (e.g. `rm -rf > .env`), gate 1 sees confirm=true and passes, then gate 2 hard-blocks — no leak.
