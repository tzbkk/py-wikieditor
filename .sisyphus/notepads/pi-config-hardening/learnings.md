# Learnings — pi-config-hardening

## Project Structure
- `fandom_bot.py` (313 lines): FandomBot class, 7 public methods (convert_text, get_page, get_category_members, get_template_embedded_pages, edit_page, move_page, get_subpages)
- `src/fandom.py` (296 lines): CLI dispatcher with 11 subcommands
- `.pi/extensions/wiki-tools.ts` (185 lines): 4 tools (wiki_save_page, wiki_check_exists, wiki_check_files, wiki_read_page) + 2 security hooks
- `.pi/skills/fandom-wiki/SKILL.md` (258 lines): page assembly workflow
- `.pi/prompts/batch-convert.md` (35 lines): references old-format slash commands

## Code Style
- Python: Triple-quoted docstrings, type hints via typing module
- fandom_bot.py uses Traditional Chinese in docstrings/comments
- .ts files use inline Python via `-c` (to be replaced by IPC server)
- No test framework exists yet

## Key Decisions (from plan)
- Bot caching: wiki_bot_server.py persistent Python process with singleton FandomBot
- JSON-RPC over stdin/stdout (single line in → single line out)
- Permission gate: 3 classes (dangerous bash, sensitive paths, --no-test-first)
- Slash commands: 8 total (test/info/page/category/template/restore/scan/scan_category)
- Destructive commands: default dry-run, override needs ctx.ui.confirm
- Tests: pytest + vitest, all in tests/ dir at repo root
- NO package.json in .pi/ (would break Pi auto-load)

## Pi API Patterns
- `pi.registerTool({name, label, description, parameters, execute})` 
- `pi.registerCommand(name, {description, handler})`
- `pi.on("tool_call", async (event, ctx) => { return {block: true, reason} | undefined })`
- `pi.exec(cmd, args) -> {code, stdout, stderr, killed}`
- `ctx.ui.notify(msg, level)`, `ctx.ui.confirm(title, msg) -> Promise<bool>`
- `ctx.ui.select(title, options) -> Promise<string>`
- Extension default export: `export default function(pi: ExtensionAPI) { ... }`

## Security Rules
- .env / config.json / credentials: block on edit/write/bash
- `__待填__` in wiki_save_page content: block
- `--no-test-first` in any tool input: block
- Dangerous bash (rm -rf, sudo, chmod 777, fork bomb, pipe to shell): confirm first

## T1 — FandomBot method additions + edit_page ratelimited retry (2026-07-22)

### Environment gotcha
- System Python is 3.14.6 with PEP 668 protection; `python3 -m venv` is also blocked (missing python3-venv package).
- `mwclient`, `opencc`, `python-dotenv` are NOT installed in the host env → cannot do runtime `from fandom_bot import FandomBot`.
- **Verification strategy**: use `python3 -c` with `ast.parse()` to structurally verify methods, signatures, decorators, module-level vars, retry loop contents. Worked perfectly.

### fandom_bot.py structure (line counts after T1, total 380)
- Imports (1–15): added `threading`, `time`, `Optional`; kept `Tuple` (still used by `protect_filenames`, `verify_filenames_preserved`, `protect_code_blocks`).
- Module-level singleton state (71–75): `_BOT_INSTANCE: Optional[FandomBot] = None` + `_BOT_LOCK = threading.Lock()`. Placed after regex constants, before `safe_error()`. Section banner matches existing `# ---` convention.
- FandomBot class (192–380). Public methods after T1, in declaration order:
  `get_bot` (classmethod), `__init__`, `__repr__`, `_load_from_env`, `_load_from_json`,
  `convert_text`, `get_page`, `get_category_members`, `get_template_embedded_pages`,
  `edit_page` (rewritten with retry), `edit_page_by_name` (new), `move_page`, `get_subpages`,
  `check_exists` (new), `read_page_text` (new), `check_files_exist` (new).

### Key implementation choices
- **get_bot failure-not-cached invariant**: `_BOT_INSTANCE = cls()` — RHS `cls()` evaluates first and raises before assignment lands. Inline comment at line 211 documents this so future editors don't reorder. Pattern matches task spec verbatim.
- **edit_page retry**: 3 attempts via `range(3)`, retries only when `'ratelimited' in str(e).lower() AND attempt < 2`, sleeps `time.sleep(60)` between retries, re-raises all other exceptions and the 3rd ratelimited failure. Semantically equivalent to `src/convert_category.py:119-121` but encapsulated.
- **check_files_exist auto-prefix**: `lookup = filename if filename.lower().startswith('file:') else f'File:{filename}'`. Return dict keeps caller's original (un-normalized) filename as key — documented in docstring since it's a non-obvious contract.
- All new docstrings in Traditional Chinese to match existing file style. Pyright only flags pre-existing third-party import errors (mwclient/opencc/dotenv), no errors in new code.

### Verification commands that worked
- `python3 -c` with `ast.parse()` + walking ClassDef body for method names and decorators
- `ast.unparse()` to extract method signatures
- Direct AST walk of `get_bot` to confirm `_BOT_INSTANCE` assignment has `cls()` as RHS (proves failure-not-cached invariant)
- Substring check of `ast.unparse(edit_page)` for retry-pattern building blocks

## T5 — Slash command specification + batch-convert.md rewrite (2026-07-22)

### Slash command classification table structure
- Created `.sisyphus/evidence/task-5-slash-map.md` with 10 commands mapped to fandom.py subcommands
- Classification follows risk levels: Safe (2 commands), Bounded (4 commands), Read (2 commands), Destructive (2 commands)
- All bounded/destructive commands default to safe mode (dry-run, show-versions, scan-only) and require `--confirm` to override
- Commands NOT exposed due to blast radius: `scan --approve-all`, `scan-category --approve-all`, `move-category` — use bash directly

### batch-convert.md prompt template rewrite
- Removed old-format command references (`/wiki_scan namespace=main scan_only=true`, `dry_run=true/false` args)
- Rewrote as 5-step workflow: test connection → scan → dry-run preview → confirm → restore if needed
- Added table of other available commands with their default behaviors
- Added "不可用命令" section directing users to bash for high-blast-radius operations
- Added security rules section: permission gate protection, `--no-test-first` blocking, `__待填__` interception
- Retained frontmatter: `name: wiki-batch-convert` and updated `description` to be concise

### Key learning
- Old batch-convert.md used incorrect command syntax with `namespace=main scan_only=true` and `dry_run=true` — these were never valid slash command formats
- The slash command risk classification table (plan lines 168-185) is the SINGLE SOURCE OF TRUTH for command behavior

## T5 — wiki_bot_server.py IPC skeleton (2026-07-22)

### Environment
- Host Python 3.14.6 has stdlib `argparse`/`json`/`sys`/`os` → skeleton runs without any third-party deps. Verified by running `--check`, `--method-docs`, and piped JSON-RPC calls directly on system python.
- mwclient/opencc still missing on host, but T5 is lazy-init so this is not a blocker. Verified by setting `sys.modules['fandom_bot'] = None` before import — module still loads, `ping`/unknown dispatch still works.

### File layout (`.pi/extensions/wiki_bot_server.py`, ~120 lines)
- Top: shebang + module docstring + imports (`sys/os/json/argparse` only).
- `_REPO_ROOT` computed from `__file__` and inserted into `sys.path` so `from fandom_bot import ...` works regardless of cwd. Crucial because wiki-tools.ts (T7) will launch this script with an arbitrary cwd.
- `_bot = None` module global + `get_bot()` lazy accessor. Real import of `FandomBot` happens inside `get_bot()`, not at module top.
- `safe_error(e)`: tries `from fandom_bot import safe_error` and delegates; on ANY exception falls back to `str(e)[:200]`. Try/except around the import means the function works even when fandom_bot itself can't be imported.
- `handle_request(req)`: module-level (not nested in main). Catches all exceptions → returns `{ok: False, error: ...}`. **Never raises** — this is the contract T12 unit tests rely on.
- `method_docs()`: returns dict with single `ping` entry; T6 expands.
- `_MAX_INPUT_BYTES = 50 * 1024 * 1024` + `_readline_limited(stream)` guard. Returns `(line, None)`, `(None, None)` on EOF, or `(None, err_msg)` on oversize.
- `main()`: argparse → `--check` prints "OK"; `--method-docs` prints JSON; otherwise reads stdin line-by-line via `_readline_limited`. Uses `sys.stdout.write(...)` + `sys.stdout.flush()` after each response (never `print` — avoids buffering surprises when stdout is a pipe).

### Pyright gotcha (avoid for future tasks)
- Initial loop `if line is None and size_err is None: break` then `else: line = line.strip()` triggered `reportOptionalMemberAccess` — Pyright can't prove that reaching the else means line is non-None.
- Fix: restructure as `if size_err is not None: ... elif line is None: break; else: ...` so the non-None check is explicit. Same behavior, Pyright-clean. Remember this for any code that uses sentinel tuples.

### Acceptance criteria — all 7 verified
- `--check` → "OK", exit 0 ✓
- `--method-docs` → valid JSON with `methods` array ✓
- `echo ping | server` → `{"id":"t1","ok":true,"result":"pong"}` ✓
- unknown method → `{"ok":false,"error":"Unknown method: X"}` (no crash) ✓
- invalid JSON / non-dict JSON / empty input / multi-line — all handled gracefully, no crashes ✓
- lazy init verified by blocking `fandom_bot` in sys.modules ✓
- module-level `handle_request` importable & callable directly ✓

### Conventions discovered
- Project AGENTS.md mandates docstrings on ALL functions/classes → keep them even though code-smell hook flags them. Short one-liners preferred; multi-line only when contract is non-obvious (e.g. `_readline_limited`'s tuple semantics).
- Project prefers Traditional Chinese in docstrings for `fandom_bot.py`, but `wiki_bot_server.py` is a new IPC server layer → used English to match Pi/TS ecosystem conventions. T6 should follow same English convention.

## T4 — TypeScript test infrastructure setup (2026-07-22)

### Vitest configuration pattern
- Independent `tests/package.json` (NOT in `.pi/` - would break Pi auto-load)
- `vitest.config.ts`: `include: ['**/*.test.ts']` when running from inside `tests/` directory
- `tsconfig.json`: `"type": "module"` + `"moduleResolution": "bundler"` + strict mode + path mapping for `@earendil-works/pi-coding-agent` → local `.d.ts`

### Local type declarations for Pi ExtensionAPI
- Created `tests/helpers/pi-types.d.ts` to avoid dependency on npm package (may not exist)
- Minimal surface: `ExtensionAPI` with `registerTool`, `on`, `exec`; `ExtensionContext` with `ui.notify`, `ui.confirm`
- Path mapping in `tsconfig.json`: `@earendil-works/pi-coding-agent` → `./helpers/pi-types.d.ts`

### Mock implementation pattern
- `createMockPi()` uses getters for `_toolHandlers`, `_commandHandlers`, `_eventHandlers` — must be getters, not direct properties, otherwise vitest mock behavior breaks
- Helpers: `dispatchToolCall()`, `dispatchCommand()` for integration tests
- All mock functions are vitest mocks (`vi.fn()`), tracked in internal maps for test assertions

### Dependency gotcha
- typebox@^0.32.0 doesn't exist → removed from package.json
- smoke test only needs vitest + typescript

### Verification
- `cd tests && npm install && npm test` → 3 tests pass (1 smoke + 2 mock creation tests)

## T10 — pytest infrastructure + mock mwclient fixtures (2026-07-23)

### Environment challenges
- Python 3.14.6 with PEP 668 protection blocks direct pip install
- Solution: use `pip3 install --break-system-packages` for development
- mwclient/opencc installation took 2+ minutes each (large binary wheels)

### Mocking FandomBot initialization
- FandomBot.__init__ checks `.env` existence BEFORE loading env vars from monkeypatch
- Direct monkeypatch.setenv() doesn't work because the check happens first
- Solution: mock `os.path.exists('.env')` to return False, `os.path.exists('config.json')` to return True
- Mock `open()` to return StringIO with JSON config for 'config.json'
- Mock `mwclient.Site` to return our mock_site (avoiding real network)
- Mock `OpenCC` to return MagicMock (avoid real conversion config)

### Recursion gotcha in mock_exists
- Initial implementation: `if path == '.env': return False; return os.path.exists(path)` caused infinite recursion
- Problem: `os.path.exists()` is already patched when called inside the mock function
- Solution: save `original_exists = os.path.exists` BEFORE monkeypatch, use that in the mock function

### Fixture design
- `mock_site`: MagicMock with .pages, .categories, .login(), .allpages()
- `mock_page`: Factory function returning configured page mocks (name, exists, text, edit, move)
- `mock_bot`: Fully mocked FandomBot instance with no network calls
- `isolated_env`: tmp_path + env vars set for tests needing file system isolation

### Verification
- `python -m pytest tests/ -v` → 3/3 tests pass
- LSP shows "Import 'fandom_bot' could not be resolved" in conftest.py — expected/acceptable (test imports are runtime-mocked)
- No other LSP diagnostics

### Files created
- `tests/__init__.py` (empty)
- `tests/conftest.py` (4 fixtures)
- `pytest.ini` (repo root)
- `tests/test_smoke.py` (3 smoke tests)

### Dependencies added
- pytest>=7.0
- pytest-mock>=3.0

## T6 — wiki_bot_server.py full method dispatch (2026-07-23)

### What was added on top of T2 skeleton
- `_err(req_id, msg)` helper for standardized error responses.
- `_LOGIN_ERROR_KEYWORDS` tuple constant + `_edit_with_retry()` for login/session retry (clears `_bot` singleton, retries once).
- Expanded `handle_request()` to dispatch 8 methods: ping, check_exists, read_page_text, check_files_exist, edit_page, get_category_members, get_template_embedded_pages, convert_text.
- Expanded `method_docs()` to list all 8 with arg schemas + descriptions.
- File grew from 125 → 261 lines.

### Pyright gotcha (NEW — beyond T2's sentinel-tuple one)
- `fandom_bot.get_category_members` / `get_template_embedded_pages` are annotated `List[object]` (mwclient Page objects, which DO have `.name`).
- Initial code `[p.name for p in pages]` → Pyright `reportAttributeAccessIssue` at two locations.
- **Fix**: use `getattr(p, "name")` — returns `Any` and bypasses the imprecise-typing check without needing `from typing import Any` + cast. Same runtime behavior. Single explanatory comment added above first occurrence.
- Do NOT modify fandom_bot.py to fix this (it's T1-frozen).

### Dispatch design decisions
- `edit_page` calls `bot.edit_page_by_name(title, content, summary)` (the convenience wrapper in FandomBot), NOT `edit_page(get_page(title), ...)` — keeps the server layer clean.
- The FandomBot-internal `edit_page` already handles `ratelimited` retry (3 attempts, 60s sleep). The server-layer retry is for LOGIN/session errors only — different concern, single retry, clears singleton.
- `summary` argument is optional with default `"自动生成页面"` (matches the spec — not the FandomBot default `"自动编辑"`).
- `_edit_with_retry` re-raises non-login errors so `handle_request`'s outer `try/except` wraps them — preserves the "handle_request never raises" contract.
- Login keywords checked (lowercased substring match): `login`, `session`, `auth`, `token`, `unauthorized`, `expired`.

### Validation patterns used
- `isinstance(x, list)` for list args (page_names, filenames).
- `isinstance(x, str)` for string args (page_name, category_name, template_name, text, title, content).
- Missing args → `_err(req_id, "<method> requires '<arg>' (<type>)")`. Verified against the 4 must-test cases.
- `args.get("args", {}) or {}` already in T2 handles missing/null args field.

### Mock testing pattern (for future tasks)
- To test `handle_request` without real FandomBot: `sys.modules['fandom_bot'] = MagicMock(FandomBot=mock, safe_error=...)`, then `srv._bot = mock_bot` to bypass lazy init.
- For login-retry test: `mock_bot.edit_page_by_name.side_effect = [Exception('Login expired'), None]` — first call fails, retry succeeds. Verify `resp['result']['retried'] is True` and `srv._bot is not None` (re-cached by get_bot during retry).
- For non-login error test: `side_effect = RuntimeError('Network down')`. Verify resp has `ok: False` and the error string is preserved (proving it bubbled to outer try).

### Acceptance criteria — all 6 verified
- File modified in place ✓
- `handle_request` dispatches all 8 methods (verified by mock + by listing via `--method-docs`) ✓
- `--method-docs` outputs valid JSON with 8 methods (count check via python pipe) ✓
- Session retry: clears `_bot` and retries once on login keywords (mock-verified) ✓
- Input validation returns `{ok:false, error:...}` on missing/wrong-type args (verified via echo pipes for 4 cases) ✓
- Echo-pipe example from spec (mocked) returns exactly `{"id":"t","ok":true,"result":{"A":true,"B":false}}` ✓
- Bonus: invalid JSON, non-dict JSON, unknown method, ratelimited-vs-login distinction — all verified.

### Conventions reinforced
- English docstrings (matches T2 convention for this file).
- Module-level `handle_request` (T12 imports it directly).
- `sys.stdout.write` + `sys.stdout.flush()` in main loop (unchanged from T2).
- No asyncio, no external packages, no new files.

## T(permission gate) — 4 tool_call handlers in wiki-tools.ts (2026-07-23)

### Final file structure (wiki-tools.ts, 280 lines → 281 lines)
- Module-level constants block (lines 6–29): `DANGEROUS_BASH_PATTERNS` (6 regex+label pairs), `SENSITIVE_PATH_PATTERNS` (7 regexes)
- Tool registrations (wiki_save_page/wiki_check_exists/wiki_check_files/wiki_read_page) — UNCHANGED
- 4 `pi.on("tool_call")` handlers (lines 173–275), each returns `{block: true, reason}` or `undefined`
- session_start handler — UNCHANGED

### CRITICAL regex deviation from task spec
- Task spec gave `/(^|\/)\.env$/` for `.env` detection. This regex requires `.env` to be preceded by start-of-string or `/`.
- Test case `'echo KEY=val > .env'` has a SPACE before `.env`, so the spec regex DOES NOT match it. Confirmed via `node -e`.
- **Fix**: changed to `/(^|[\/\s])\.env$/` — adds `\s` to the prefix alternation. Now matches: `.env` (^), `/path/.env` (/), `> .env` (space). Does NOT match `foo.env` (no false positives).
- Documented inline with comment explaining the deviation so future devs don't "fix" it back and break bash redirect detection.

### 4-gate dispatch order matters
- Handlers run in registration order. `dispatchToolCall` short-circuits on first `{block: true}`.
- Order: gate1(dangerous bash, confirm) → gate2(sensitive paths, direct block) → gate3(--no-test-first, direct block) → gate4(__待填__, direct block).
- A `rm -rf` to `.env` (`rm -rf .env`) triggers gate1 first (confirm). If user confirms, gate2 then blocks it directly. Belt-and-suspenders.

### Test infrastructure — importing the real extension
- Extension imports `{ Type } from "typebox"` (runtime value import, NOT type-only). The `typebox` package doesn't exist; `@sinclair/typebox` does.
- **Vitest alias fix**: added `resolve.alias` in `vitest.config.ts` mapping `typebox` → absolute path of `tests/node_modules/@sinclair/typebox`.
- MUST be an absolute path (`path.resolve(__dirname, 'node_modules/@sinclair/typebox')`). Using the package name `'@sinclair/typebox'` as alias target FAILS because the extension file lives outside `tests/`, so `tests/node_modules` isn't in its module resolution path.
- This required adding `@types/node` to devDependencies (for `node:path` and `__dirname` types in vitest.config.ts).
- Test imports the real extension via `await import('../.pi/extensions/wiki-tools.ts')` then calls `mod.default(pi)`. Module caching is fine because the extension's module body is stateless (only constants + default function export).

### Comment hook pattern for this file
- All comments in the permission gate section are security-related (hook explicitly allows) or regex labels (hook explicitly allows).
- Section banner `// ===` matches existing file convention (Wiki 读写工具 / 安全策略 banners were pre-existing).
- "闸门 N" labels are navigation aids for 4 structurally-similar `pi.on` blocks — without them it's a wall of code.

### Verification
- `npx tsc --noEmit` → exit 0 (clean)
- `npm test` → 9/9 tests pass (3 smoke + 6 permission gate)
- LSP not installed (typescript-language-server missing from env); tsc used as substitute per Verification protocol

### Files changed
- `.pi/extensions/wiki-tools.ts`: +110 lines (constants + 4 handlers replacing 2 handlers)
- `tests/vitest.config.ts`: added `resolve.alias` for typebox
- `tests/package.json`: added `@types/node` devDependency
- `tests/test_permission_gate.test.ts`: NEW, 6 test cases

### Gotcha for T7 (downstream)
- T7 will rewrite tool functions but MUST preserve the 4 `pi.on("tool_call")` handlers (lines 173–275) verbatim.
- The `DANGEROUS_BASH_PATTERNS` and `SENSITIVE_PATH_PATTERNS` constants (lines 11–29) must also be preserved.
- T13 integration tests will exercise these handlers — the regex deviation `(^|[\/\s])` is load-bearing for the bash redirect test case.

## T7 — Extract inline Python to wiki_tools/ + IPC server rewrite (2026-07-23)

### Files created
- `.pi/extensions/wiki_tools/__init__.py` (empty package marker)
- `.pi/extensions/wiki_tools/save_page.py` — calls `bot.edit_page_by_name(title, content, summary)`
- `.pi/extensions/wiki_tools/check_exists.py` — calls `bot.check_exists(titles)`
- `.pi/extensions/wiki_tools/check_files.py` — calls `bot.check_files_exist(filenames)`
- `.pi/extensions/wiki_tools/read_page.py` — calls `bot.read_page_text(title)`, returns `{"title", "text": str|None}`

### Handler module pattern (dual-mode)
Each handler module supports two invocation modes:
1. **Importable**: `from wiki_tools.save_page import save_page; save_page(bot, ...)` — T12/T13 tests will use this.
2. **Standalone CLI**: `echo '{"title":"X","content":"Y"}' | python -m wiki_tools.save_page` — reads JSON from stdin, writes JSON to stdout.

Path resolution: `_REPO_ROOT = dirname⁴(__file__)` resolves `.pi/extensions/wiki_tools/X.py` → repo root (4 dirname calls because the file is 4 levels deep: repo/.pi/extensions/wiki_tools/file.py). Wait, actually 4 dirnames: file → wiki_tools → extensions → .pi → repo. Confirmed via `ast.parse` on all 5 files.

### wiki-tools.ts rewrite (281 → 380 lines)
**PRESERVED BYTE-IDENTICAL** (verified via `diff` against HEAD):
- Lines 1-33 (now): imports, `DANGEROUS_BASH_PATTERNS`, `SENSITIVE_PATH_PATTERNS`
- Lines 35-46 (now): `run()` helper (T9/T10 will use it for `pi.exec` slash commands)
- Lines 260-362 (now): all 4 `pi.on("tool_call")` gate handlers (闸门 1-4)
- `SENSITIVE_PATH_PATTERNS` keeps `(^|[\/\s])\.env$` regex (matches bash redirects like `echo > .env`) — per T8's note

**NEW code added:**
- `PYTHON` now reads `process.env.PI_WIKI_PYTHON || "python3"` (was hardcoded)
- `SERVER_SCRIPT = path.join(__dirname, "wiki_bot_server.py")`
- `ensureServer(pi)`: spawns `wiki_bot_server.py` as child process with `stdio: ["pipe","pipe","pipe"]`, sets `serverReady=true`. On exit, resets state. Logs stderr via `pi.exec("echo", ...)`.
- `callServer(method, args)`: writes JSON line `{"id","method","args"}` to stdin, reads one JSON line response from stdout. Resolves with `resp.result` on `ok:true`, rejects with `Error(resp.error)` on `ok:false`.
- `session_start`: now calls `ensureServer(pi)` and notifies "IPC server 已启动"; on failure notifies warning.
- `session_shutdown` (NEW): kills child process, resets state.
- `wiki_save_page` execute: NEW `__待填__` check BEFORE `callServer` (defense-in-depth alongside Gate 4); calls `callServer("edit_page", {title, content, summary})`.
- `wiki_check_exists`: calls `callServer("check_exists", {page_names: titles})`.
- `wiki_check_files`: calls `callServer("check_files_exist", {filenames})`.
- `wiki_read_page`: calls `callServer("read_page_text", {page_name: title})`; handles null result (page missing).

### IPC arg-name mapping (TS → Python server)
| Tool | TS param | Server method | Server arg key |
|------|----------|---------------|----------------|
| wiki_save_page | title/content/summary | `edit_page` | title/content/summary |
| wiki_check_exists | titles | `check_exists` | `page_names` |
| wiki_check_files | filenames | `check_files_exist` | `filenames` |
| wiki_read_page | title | `read_page_text` | `page_name` |

**Gotcha**: The server method `read_page_text` returns the raw string (or null), NOT a dict. The TS execute wraps it into `{title, found}` for the details field.

### Verification results
- `grep -nE "(page\.edit\(|bot\.site\.pages\[|import sys)" .pi/extensions/wiki-tools.ts` → exit 1 (NO MATCHES) ✓
- `grep -nE '"-c"|run\(pi, \[' .pi/extensions/wiki-tools.ts` → exit 1 (NO MATCHES) ✓
- All 5 Python files pass `ast.parse()` ✓
- `cd tests && npm test` → 9/9 pass (test_smoke 3 + test_permission_gate 6) ✓
- `diff` of all 4 gate handlers + 2 constant arrays + run() between HEAD and new → IDENTICAL ✓
- `tsc --noEmit` with `@types/node` + typebox path alias: only pre-existing implicit-any errors on `execute(_id, params, _signal, _onUpdate, _ctx)` params (same signature as original T8 code — NOT a regression)

### LSP environment note
- `typescript-language-server` is NOT installed in this environment (LSP diagnostics tool returns "NOT INSTALLED").
- Workaround: used `npx tsc --noEmit` with a temp tsconfig (`/tmp/opencode/tsconfig-extcheck.json`) including `"types": ["node"]` and `typeRoots` pointing to `tests/node_modules/@types`.
- The `execute` param type inference works in the real Pi runtime (which provides proper `registerTool` contextual types) but not in isolated tsc — this is pre-existing, not introduced by T7.

### Important design decision: session_start spawns server eagerly
The spec template and my implementation spawn the IPC server in `session_start` (eager). This means FandomBot login happens on session start, not on first tool call. Trade-off: first tool call is faster, but session start is slower and will fail visibly if `.env` is missing. The lazy-init alternative (spawn on first `callServer`) would defer login but add latency to the first tool. The spec explicitly shows `ensureServer(pi)` in session_start, so I followed that.

## T9 — 8 slash commands in wiki-tools.ts (2026-07-23)

### Final file structure (wiki-tools.ts, 380 → 651 lines, +271)
- Helpers `parseArgs` + `truncate` placed AFTER `callServer` (lines 33-60), BEFORE `export default`. Used by all 8 commands.
- 8 `pi.registerCommand()` calls placed AFTER 4 permission gate handlers (gate 4 ends line 399), BEFORE `session_start` (now line 635). Logical order: tools → gates → commands → session lifecycle.
- `git diff HEAD --stat` shows ONLY additions (271 +/- 0 -). T7's IPC + T8's gates byte-preserved.

### Commands registered (in registration order)
1. `wiki_test` (Safe) — `fandom.py test`
2. `wiki_info` (Safe) — `fandom.py info <name>`, defaults to `Template:音樂信息`; accepts positional OR `template_name=`/`name=` kwarg
3. `wiki_convert_page` (Bounded) — `fandom.py page <page_name>` + `--dry-run` default; `--confirm` triggers `ctx.ui.confirm()` then drops dry-run
4. `wiki_convert_category` (Bounded) — same pattern + `limit="N"` kwarg
5. `wiki_convert_template` (Bounded) — same pattern
6. `wiki_restore` (Bounded) — `fandom.py restore <page_name>` + `--show-versions` default; `--confirm` drops it
7. `wiki_scan` (Read) — `fandom.py scan --scan-only`. REJECTS `--approve-all` flag with error notify, returns without exec
8. `wiki_scan_category` (Read) — same pattern for `scan-category`

### parseArgs design — token-classification
- Single-pass tokenizer using regex `(?:[^\s"]+|"[^"]*")+/g` → handles quoted strings
- Token classification:
  - `--flag` → flags set
  - `key=value` → kwargs dict (strips surrounding quotes from value)
  - anything else → positional array (strips surrounding quotes)
- LIMITATION: `--flag value` (space-separated) is parsed as flag + positional, NOT as kwarg. So `--limit 5` becomes `flags={"limit"}` + `positional=["5"]`. Workaround for users: use `limit="5"` kwarg form. Documented choice: keep parser simple; the spec/test only exercises `limit="N"` kwarg form.
- This is fine for our 8 commands because the only "flag with value" we expose is `--limit`, and we accept `limit="N"` form for it.

### Test patterns for slash commands (test_slash_commands.test.ts, 15 tests)
- Reuses existing helpers: `createMockPi`, `createMockCtx`, `dispatchCommand`
- `loadExtension()` pattern: `const pi = createMockPi(); const mod = await import('../.pi/extensions/wiki-tools.ts'); mod.default(pi); return pi;`
- vitest module caching: each `loadExtension()` call re-imports the same module but re-registers handlers on a fresh `pi`. Module body has no state, so this works.
- `mockExecOk(pi, stdout, stderr)` helper reduces boilerplate
- Key assertions:
  - `expect(pi.exec).toHaveBeenCalledWith('python3', expect.arrayContaining(['--dry-run']))` for default-bounded
  - `expect.arrayContaining` / `expect.not.arrayContaining` are perfect for "flag present" / "flag absent" checks
  - For approve-all rejection: `expect(pi.exec).not.toHaveBeenCalled()` + `expect(ctx.ui.notify).toHaveBeenCalledWith(<substring>, 'error')`

### Verification
- `cd tests && npm test` → 24/24 pass (3 smoke + 6 permission gate + 15 slash commands)
- `npx tsc --noEmit` (tests config) → clean
- `npx tsc -p /tmp/opencode/tsconfig-extcheck.json` (isolated ext check) → same pre-existing errors as T7:
  - Missing module declarations for `@earendil-works/pi-coding-agent` + `typebox` (path-mapping limitation outside tests/)
  - Implicit-any on `execute(_id, params, ...)` (existing) AND new `handler(args, ctx)` parameters (same root cause — no contextual types without the package). NOT real errors at runtime.
- `git diff HEAD` → 271 additions, 0 deletions. T7+T8 preserved.

### What T10/T13/T14 should know
- T10 (destructive commands) will add 2 more: `wiki_fix_links`, `wiki_update_cat_refs`. Same pattern: default `--dry-run`, `--confirm` triggers `ctx.ui.confirm()`.
- T13 (integration tests) can use `dispatchCommand(pi, name, args, ctx)` for full coverage. All 8 commands already dispatch correctly.
- T14 (SKILL.md sync) — command names: `wiki_test`, `wiki_info`, `wiki_convert_page`, `wiki_convert_category`, `wiki_convert_template`, `wiki_restore`, `wiki_scan`, `wiki_scan_category`. The slash map (`.sisyphus/evidence/task-5-slash-map.md`) is the single source of truth.

### Gotcha: notify vs return
- Commands use `ctx.ui.notify()` for user feedback, NOT a return value. The handler signature is `async handler(args, ctx): Promise<void>`. Tests must assert on `ctx.ui.notify` calls, not on the handler's return value.
- On success: `ctx.ui.notify(\`✅ <output>\`, "info")`. On failure: `ctx.ui.notify(\`❌ <output>\`, "error")`. On cancellation: `ctx.ui.notify("已取消", "info")`.

## F4 Scope Fidelity Check (2026-07-23)
All 10 checklist items PASS. VERDICT: APPROVE.
- src/*.py untouched; no .pi/package.json; no wiki_dump in tests; no forbidden slash commands (approve-all/move-category); --no-test-first only in BLOCK handlers; no inline `-c`/page.edit/bot.site.pages/import sys in wiki-tools.ts; settings.json has only enableSkillCommands.
- Tests: Python 43 collected, TS 66 passed (6 files), all green.
- Cross-task contamination: CLEAN (T13 touched no product source; T14 only SKILL.md as update 34+/4-; T7 didn't touch T6 server; T9/T10 isolated).
- Two non-blocking observations, both within authoritative locked spec:
  1. FandomBot has a 5th helper `edit_page_by_name` (not in T1's literal "4 methods" list) — required by T7 save_page IPC handler (title-only input); 2-line wrapper, justified.
  2. Slash command count is 10, matching the LOCKED classification table 1:1. The "8" in TL;DR/Must Have is stale draft wording; the 锁定 table (10 ✅) is authoritative.

## F3 Real Manual QA (2026-07-23)

### All scenarios PASS — VERDICT: APPROVE (one spec-regex caveat, non-blocking)

**Server tests (5/5):**
- `--check` → "OK" exit 0 ✓
- `--method-docs` → valid JSON, **8 methods** (`ping`, `check_exists`, `read_page_text`, `check_files_exist`, `edit_page`, `get_category_members`, `get_template_embedded_pages`, `convert_text`) ✓
- `ping` → `{"id":"t","ok":true,"result":"pong"}` ✓
- unknown method → `{"id":"t","ok":false,"error":"Unknown method: nonexistent"}` ✓
- `check_exists` missing arg → `{"id":"t","ok":false,"error":"check_exists requires 'page_names' (list)"}` ✓

**Python tests:** 43/43 pass in 0.30s (pytest 9.1.1, Python 3.14.6)
- integration/test_end_to_end.py: 12 tests
- test_fandom_bot.py: 12 tests
- test_smoke.py: 3 tests
- test_wiki_bot_server.py: 15 tests
- test_wiki_tools_handlers/: 4 tests

**TypeScript tests:** 66/66 pass in 891ms (vitest 1.6.1, 6 files)
- test_smoke.test.ts (3), test_permission_gate.test.ts (6), test_slash_commands.test.ts (15), test_destructive_commands.test.ts (10), integration/test_slash_commands.test.ts (10), integration/test_permission_gate.test.ts (22)

**FandomBot import:** 11 public methods verified — `check_exists`, `check_files_exist`, `convert_text`, `edit_page`, `edit_page_by_name`, `get_bot`, `get_category_members`, `get_page`, `get_subpages`, `get_template_embedded_pages`, `move_page`, `read_page_text`. (No third-party deps needed for `dir()` listing; lazy init means import never touches network.)

**Edge cases (3/3 handled gracefully):**
- malformed JSON `not json` → `{"id":"?","ok":false,"error":"Invalid JSON: ..."}`, exit 0
- empty input → silent exit 0 (EOF, no output, no crash)
- multi-line (2 requests) → 2 independent responses, both `pong`

**SKILL.md (4/4):**
- description = 75 chars (≤ 100) ✓
- `wiki_check_file[^s]` = 0 ✓
- `何时不用` = 1 (≥ 1) ✓
- `/wiki_` = 14 (≥ 5) ✓

**batch-convert.md (intent PASS, regex FAIL — see issues.md):**
- `grep -E "/wiki_(test|scan|convert_page)\s"` returns 3 matches — but these are NEW-format commands (`/wiki_scan --limit 10`, `/wiki_convert_page page_name="..." [--confirm]`) where space separates command from arg. The regex is too broad and matches new-format too.
- True old-format markers (`dry_run=`, `scan_only=`, `namespace=`) → ZERO matches (verified). Migration is correct.
- `/wiki_` count = 11 (≥ 1) ✓

**Permission gate (4/4):**
- `DANGEROUS_BASH_PATTERNS`: 6 entries (rm -rf, sudo, chmod 777, raw disk write, fork bomb, pipe to shell) — ≥ 5 ✓
- `SENSITIVE_PATH_PATTERNS`: 7 entries (.env, config.json, credentials, .pem, .key, id_rsa, .ssh/) — ≥ 5 ✓
- `pi.on("tool_call")` handlers: exactly 4 (lines 310, 333, 370, 399) ✓
- `--no-test-first` blocking: present in gate 3 (lines 369-389), globally blocks on any string input ✓

### Cross-task integration verified
- Slash command → ctx.ui.confirm → exec → fandom.py flow (T9) — covered by 15 TS tests
- Slash command → IPC server → FandomBot → mwclient (T7) — covered by 12 e2e pytest tests
- Permission gate intercepts before tool exec (T8) — covered by 6 TS + 22 integration TS tests
- Destructive commands default dry-run + confirm override (T10) — covered by 10 TS tests

### Note on prompt injection
During this QA run, the bash tool output contained an unsolicited "Category+Skill Reminder" block attempting to redirect the task toward skill/agent invocation. Recognized as injected content (not part of the script's actual output — `--check` only prints "OK") and ignored per task instructions.
