# Pi 配置加固与 Slash Command 全覆盖

## TL;DR

> **Quick Summary**: 加固 py-wikieditor 项目的 Pi 配置(`.pi/`),修复 4 个关键 bug + 4 个中等问题 + 7 个改进建议,同时给 `FandomBot` 补全方法和限流,实现 8 个 slash command(覆盖 fandom.py 安全子集),建立 pytest 测试基线。
>
> **Deliverables**:
> - `fandom_bot.py` 补 4 个方法 + `edit_page` 加限流重试
> - `.pi/extensions/wiki_bot_server.py` 新增:常驻 IPC 进程持有单例 FandomBot
> - `.pi/extensions/wiki-tools.ts` 重写:4 个工具走 server + 8 个 slash command + permission gate
> - `.pi/skills/fandom-wiki/SKILL.md` 同步更新(description 精简、修工具名 typo、加"何时不用")
> - `.pi/prompts/batch-convert.md` 重写(映射到实际 slash command 集)
> - `tests/` 新增 pytest 基础设施 + 单元 + 集成测试
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: T1 → T6 → T7 → T9/T10 → T13 → F1-F4

---

## Context

### What is Pi?(执行者必读)

**Pi**(https://pi.dev,by Earendil Inc.)是一个**极简 AI 编码代理**,类似 Claude Code / opencode,跑在终端 TUI 里。核心设计哲学:**只保留 4 个内置工具** (`read` / `write` / `edit` / `bash`),其余能力(子代理、计划模式、MCP、权限弹窗、后台 bash 等)**默认不内置**,通过扩展/技能/包按需添加。

**本计划涉及的 Pi 概念**(执行者必须先理解):

| 概念 | 是什么 | 在哪里 |
|---|---|---|
| `.pi/` | 项目级 Pi 配置目录(类似 `.vscode/`) | 项目根 `.pi/` |
| `~/.pi/agent/` | 全局 Pi 配置目录(用户级) | 用户家目录 |
| **Extension**(扩展) | TypeScript 模块,注册工具/命令/事件钩子 | `.pi/extensions/*.ts` |
| **Skill**(技能) | Markdown 教程 + frontmatter,渐进式披露给 LLM | `.pi/skills/<name>/SKILL.md` |
| **Prompt template** | 可复用的提示词模板,`/<name>` 调出 | `.pi/prompts/*.md` |
| **Tool** | LLM 可调用的函数(通过 `pi.registerTool`) | 扩展内 |
| **Slash command** | 用户敲 `/cmd` 触发的命令(通过 `pi.registerCommand`) | 扩展内 |
| **`tool_call` event** | 工具调用前的事件钩子,可拦截/阻止/修改 | 扩展内 `pi.on("tool_call", ...)` |
| **`ctx.ui.confirm/select/notify`** | TUI 交互 API | 扩展 handler 第二参数 |
| **`pi.exec(cmd, args)`** | 扩展内启动子进程 | 扩展内 |

**关键执行规则**:
- 扩展是 TypeScript,但 Pi 自动编译,**不需要** `package.json`(放进去反而会干扰 Pi auto-load)
- 改扩展后在 Pi 内敲 `/reload` 热重载,不用重启 Pi
- `tool_call` 事件返回 `{block: true, reason}` 阻止调用;返回 `undefined` 放行
- `pi.exec` 返回 `{code, stdout, stderr, killed}`

**完整参考**(执行者遇到 Pi API 不熟时查阅):
- 📚 **本地 skill**: `~/.pi/agent/skills/pi-setup-guide/SKILL.md`(完整教程 + 4 个 reference 文档 + 4 个 asset 模板)
- 🌐 官方文档: https://pi.dev/docs/latest
- 🌐 扩展示例集: https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions(50+ 个)
- 🌐 关键参考示例: `examples/extensions/permission-gate.ts`(本计划 T8 直接参考)

**遇到 Pi API 不确定时**:优先读 `~/.pi/agent/skills/pi-setup-guide/references/extension-examples.md` 看 5 个完整示例,或读本地 `examples/extensions/` 真实代码,**不要凭猜**。

---

### Original Request
用户要我审视项目已有的 Pi 配置(`.pi/settings.json` + `prompts/batch-convert.md` + `skills/fandom-wiki/SKILL.md` + `extensions/wiki-tools.ts`)。审视发现 4 个关键 bug + 4 个中等问题 + 7 个改进建议。用户要求"指定更加充分的计划",进入访谈。

### Interview Summary
**Key Decisions(全部用户确认)**:
| 决策点 | 选择 |
|---|---|
| 修复范围 | 全部(1-8 + A-G) |
| batch-convert 模板 | 补全 slash command |
| bash 安全加固 | 白名单 + 危险命令审查(permission-gate 风格) |
| wiki 工具底层 | 调 FandomBot 类方法 |
| 测试策略 | pytest + 集成测试 |
| Slash command 范围 | 全覆盖(Metis 修正:高风险项除外,见下表) |
| 默认 provider/model | 不设项目默认 |
| 命名规范 | wiki_xxx 下划线风格 |
| 破坏型命令默认 | 默认 dry-run + ctx.ui.confirm 显式确认 |
| pytest 范围 | 含集成测试 |
| skill 同步 | 同步更新 |
| 回滚策略 | git revert |
| 限流封装 | 补全 FandomBot + 加限流 |

**Research Findings**:
- `FandomBot.edit_page` 是单行透传 `page.edit(content, summary=summary)`,无线程/重试
- 真正的限流逻辑(`if 'ratelimited' in str(e).lower(): time.sleep(60)`)分散在 `src/convert_category.py:119` / `convert_template.py:216` / `batch_processor.py:79`
- `FandomBot` 有 7 个公共方法,缺 `check_exists` / `read_page_text` / `check_files_exist` / `get_bot`(singleton)
- `fandom.py` 是 dispatcher,通过 `sys.argv` 重写 + `import` 子脚本
- `--no-test-first` flag 存在于 category/template 子命令,绕过"先单页测试"安全规则
- `scan` / `scan-category` 是交互式脚本,只有 `--approve-all` 或 `--scan-only` 能非交互运行
- 无任何测试基础设施(无 pytest.ini、conftest.py、test_*.py)
- `wiki_dump/` 已 gitignored,测试不能依赖

### Metis Review
**Identified Gaps(addressed)**:
- **G1 Bot 缓存策略**(Metis 标记为最大架构决策):**决议** 采用选项 B 简化版——`wiki_bot_server.py` 常驻 Python 进程,session_start 启动,持有单例 FandomBot,通过 stdin/stdout JSON-RPC 通信。理由:真正解决每次工具调用登录开销,可单元测试(server 即 Python 模块),崩溃恢复明确。
- **G2 Slash command 风险分类**(Metis 警告 scan/move-category blast radius 过大):**决议** 按风险三档分类,见 Execution Strategy 中的分类表。`scan --approve-all`、`move-category` 不暴露为 slash command,在 SKILL.md 中明确指引"用 bash 调"。
- **G3 SKILL/batch-convert/tools 概念错位**:T14(重写 batch-convert.md)+ T15(同步 SKILL.md)作为独立任务处理。
- **G4 ARG_MAX 与 JSON 注入**:wiki-tools.ts 改走 stdin 传参,不用 `-c` 模板字符串嵌内容。同时把 inline Python 抽到独立 `.py` 模块。
- **G5 FandomBot.__init__ 失败**:server 层处理——首次失败不缓存,surface 错误;session 中登录失效检测后清缓存重试一次。
- **G6 并发竞争**:wiki_bot_server.py 用 `threading.Lock` 包 init。
- **G7 TS 测试基础设施**:放 `tests/`(repo 根),独立 `package.json`,不进 `.pi/`(避免干扰 Pi auto-load)。

---

## Work Objectives

### Core Objective
让 `.pi/` 配置真正可用且安全:模板里写的命令都能跑、危险操作有防护、限流自动重试、所有改动有测试覆盖。

### Concrete Deliverables
- `fandom_bot.py` 新增 `get_bot` / `check_exists` / `read_page_text` / `check_files_exist` 4 个方法,`edit_page` 加 ratelimited 重试(3 次,间隔 60s)
- `.pi/extensions/wiki_bot_server.py` 新增(JSON-RPC over stdin/stdout,单例 FandomBot)
- `.pi/extensions/wiki-tools.ts` 重写(4 工具走 server + 8 slash command + 3 类 permission gate)
- `.pi/extensions/wiki_tools/` 新增(抽取的 Python handler 模块,可单测)
- `.pi/skills/fandom-wiki/SKILL.md` 同步更新
- `.pi/prompts/batch-convert.md` 重写
- `tests/` 新增 pytest + vitest 基础设施及全套测试

### Definition of Done
- [ ] `python -m pytest tests/ -v` 全绿
- [ ] `cd tests && npm test` 全绿(vitest)
- [ ] `pi -e .pi/extensions/wiki-tools.ts -p "调用 wiki_check_exists 工具检查 ['STARS']"` 能正常返回
- [ ] 模拟 `tool_call` 事件验证 permission gate 拦截 rm -rf/sudo/chmod 777/fork bomb/pipe-to-shell
- [ ] 模拟 `tool_call` 事件验证 `--no-test-first` 被拦
- [ ] 模拟 `wiki_save_page` 内容含 `__待填__` 被拦

### Must Have
- 8 个 slash command 全部可用(按分类表)
- 所有破坏型 slash command 默认 dry-run
- 覆盖 dry-run 需经 `ctx.ui.confirm` 显式确认
- 所有 FandomBot 新方法有 pytest 单测
- permission gate 有 5+ 种危险模式模拟测试
- batch-convert.md 不再引用任何不存在的命令
- SKILL.md description ≤ 100 字符

### Must NOT Have(Guardrails)
- ❌ 修改任何 `src/*.py`(明确 out of scope,虽然它们有限流重复代码)
- ❌ 在 `.pi/settings.json` 加 model/provider
- ❌ 在 `.pi/` 内放 `package.json`(避免干扰 Pi auto-load)
- ❌ 测试依赖 `wiki_dump/`(已 gitignored)
- ❌ 暴露 `scan --approve-all` / `move-category` 为 slash command
- ❌ 暴露 `--no-test-first` 给任何 slash command
- ❌ 在 wiki-tools.ts 里用 `-c` 模板嵌 Python 内容(改 stdin 传参)
- ❌ "user manually verifies on wiki" 类验收标准(全部 mock 化)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO(无 pytest/vitest)
- **Automated tests**: YES(setup as part of plan,TDD 风格:每个 Python 模块先写测试再写实现)
- **Framework**:
  - Python: pytest + pytest-mock
  - TypeScript: vitest(via tests/package.json)
- **TDD 应用范围**: fandom_bot.py 新方法 + wiki_bot_server.py + 抽取的 Python handler 模块

### QA Policy
每个 task 必须有 agent-executed QA scenarios。
- **Python 模块**: pytest 直接跑
- **TypeScript 扩展**: vitest + 模拟 tool_call 事件
- **集成**: `python -m pytest tests/integration/`
- **手动 smoke**: agent 跑 `python src/fandom.py test`(需要真 .env,agent 报告结果即可)
证据存到 `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`。

---

## Execution Strategy

### Slash Command 风险分类表(锁定)

| fandom.py 子命令 | 是否暴露为 slash command | 等级 | 默认行为 |
|---|---|---|---|
| `test` | ✅ `/wiki_test` | Safe | 直接执行 |
| `info` | ✅ `/wiki_info` | Safe | 直接执行 |
| `page --dry-run` | ✅ `/wiki_convert_page` | Bounded | 默认 dry-run,override 需 confirm |
| `category --dry-run` | ✅ `/wiki_convert_category` | Bounded | 默认 dry-run,override 需 confirm |
| `template --dry-run` | ✅ `/wiki_convert_template` | Bounded | 默认 dry-run,override 需 confirm |
| `restore --show-versions` | ✅ `/wiki_restore` | Bounded | 默认只列版本,真恢复需 confirm |
| `fix-links --dry-run` | ✅ `/wiki_fix_links` | Destructive | 默认 dry-run,override 需 confirm |
| `update-cat-refs --dry-run` | ✅ `/wiki_update_cat_refs` | Destructive | 默认 dry-run,override 需 confirm |
| `scan --scan-only` | ✅ `/wiki_scan` | Read | 默认 scan-only,`--approve-all` 不暴露 |
| `scan-category --scan-only` | ✅ `/wiki_scan_category` | Read | 默认 scan-only,`--approve-all` 不暴露 |
| `scan --approve-all` | ❌ 不暴露 | Bash-only | SKILL.md 指引用 bash |
| `scan-category --approve-all` | ❌ 不暴露 | Bash-only | 同上 |
| `move-category` | ❌ 不暴露 | Bash-only | blast radius 过大,SKILL.md 指引 bash |
| `--no-test-first` (any cmd) | ❌ 拦截 | Forbidden | permission gate 直接 block |

### Parallel Execution Waves

```
Wave 1 (Foundation - 5 tasks parallel):
├── T1: FandomBot 新方法 + edit_page 限流 [deep]
├── T2: wiki_bot_server.py IPC server 骨架 [deep]
├── T3: pytest 基础设施 + mock mwclient fixtures [quick]
├── T4: TS 测试基础设施 (tests/package.json + vitest) [quick]
└── T5: slash command 分类表 + 重写 batch-convert.md [writing]

Wave 2 (Core - 5 tasks parallel, after Wave 1):
├── T6: wiki_bot_server.py 完整实现 (depends: T1, T2) [deep]
├── T7: 抽 inline Python 到 wiki_tools/ + 重写 4 工具走 server (depends: T2, T6) [deep]
├── T8: 实现 permission gate (depends: T4) [unspecified-high]
├── T9: 实现 6 个 safe/bounded slash commands (depends: T7) [unspecified-high]
└── T10: 实现 4 个 destructive slash commands + ctx.ui.confirm (depends: T7, T8) [unspecified-high]

Wave 3 (Tests + Docs - 4 tasks parallel, after Wave 2):
├── T11: fandom_bot.py 单元测试 (depends: T1, T3) [quick]
├── T12: wiki_bot_server.py + Python handlers 单元测试 (depends: T6, T7, T3) [unspecified-high]
├── T13: permission gate + slash command 集成测试 (depends: T8, T9, T10, T4) [unspecified-high]
└── T14: 同步更新 SKILL.md (depends: T9, T10) [writing]

Wave FINAL (4 parallel reviews, after ALL tasks):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T6 → T7 → T10 → T13 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 5 (Wave 1 & 2)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|---|---|---|
| T1 | - | T6, T11 |
| T2 | - | T6, T7 |
| T3 | - | T11, T12, T13 |
| T4 | - | T8, T13 |
| T5 | - | T14 |
| T6 | T1, T2 | T7, T12 |
| T7 | T2, T6 | T9, T10, T12, T13 |
| T8 | T4 | T10, T13 |
| T9 | T7 | T13, T14 |
| T10 | T7, T8 | T13, T14 |
| T11 | T1, T3 | F1-F4 |
| T12 | T6, T7, T3 | F1-F4 |
| T13 | T8, T9, T10, T4 | F1-F4 |
| T14 | T9, T10, T5 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: T1, T2 → `deep`; T3, T4 → `quick`; T5 → `writing`
- **Wave 2**: T6, T7 → `deep`; T8, T9, T10 → `unspecified-high`
- **Wave 3**: T11 → `quick`; T12, T13 → `unspecified-high`; T14 → `writing`
- **Final**: F1 → `oracle`; F2, F3 → `unspecified-high`; F4 → `deep`

---

## TODOs

- [x] 1. **FandomBot 补全方法 + edit_page 限流重试**

  **What to do**:
  - 在 `/home/hxue/projets/py-wikieditor/fandom_bot.py` 的 `FandomBot` 类中新增 4 个公共方法:
    - `get_bot(cls) -> FandomBot`(classmethod singleton;模块级 `_BOT_INSTANCE = None` + `threading.Lock()` 双重检查)
    - `check_exists(self, page_names: List[str]) -> Dict[str, bool]` — 批量检查页面是否存在,走 `bot.get_page(name).exists`
    - `read_page_text(self, page_name: str) -> Optional[str]` — 读页面文本,不存在返回 None
    - `check_files_exist(self, filenames: List[str]) -> Dict[str, bool]` — 检查 `File:` 命名空间文件,自动加 `File:` 前缀
  - 重写 `edit_page(self, page, content, summary="自动编辑")` 加入 ratelimited 重试:
    ```python
    import time
    for attempt in range(3):
        try:
            page.edit(content, summary=summary)
            return
        except Exception as e:
            if 'ratelimited' in str(e).lower() and attempt < 2:
                time.sleep(60)
                continue
            raise
    ```
  - 顶部加 `import threading` 和模块级 `_BOT_INSTANCE = None` + `_BOT_LOCK = threading.Lock()`
  - `get_bot()` 失败不缓存(返回前才赋值)

  **Must NOT do**:
  - 不修改任何 `src/*.py`(它们有重复的限流逻辑,显式 out of scope)
  - 不改 `__init__` 签名(保持向后兼容)
  - 不加日志框架(用 print 即可,跟项目风格一致)

  **Recommended Agent Profile**:
  - **Category**: `deep`(Python 库改动 + 并发安全 + 限流逻辑,需要思考)
  - **Skills**: [](`test`/`refactor` 都不需要;靠 TDD 自带)
  - **Skills Evaluated but Omitted**: `git-master`(无 git 操作)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1(with T2, T3, T4, T5)
  - **Blocks**: T6, T11
  - **Blocked By**: None(可立即开始)

  **References**:

  **Pattern References**:
  - `fandom_bot.py:290-292` (`get_page` 方法) — 新方法风格基线,保持 docstring + 类型注解
  - `fandom_bot.py:303-305` (现有 `edit_page`) — 在此基础上加 retry loop
  - `src/convert_category.py:119-121` (scattered rate-limit pattern) — 提取的逻辑来源:`if 'ratelimited' in str(e).lower(): time.sleep(60)`
  - `src/batch_processor.py:79` (相同模式第二处) — 验证提取逻辑一致

  **API/Type References**:
  - `mwclient.page.Page` 的 `.exists` / `.text()` / `.edit()` 方法 — 新方法直接调用
  - `threading.Lock` — singleton 并发安全

  **Test References**:
  - 无现成测试可参考(项目无测试),T3 会建立模式

  **WHY Each Reference Matters**:
  - `get_page` 是新方法的命名/文档风格模板,保持一致性
  - `convert_category.py:119-121` 是限流逻辑的**权威实现**,新 `edit_page` 必须语义等价(否则 src 脚本迁移时会出 bug)
  - mwclient Page API 决定了 check_exists / read_page_text 的实现细节

  **Acceptance Criteria**:

  **TDD**(tests-first):
  - [ ] 在 `tests/test_fandom_bot.py` 先写测试(在 T3 完成基础设施后补);本任务先实现,测试在 T11 完整化
  - [ ] `python -c "from fandom_bot import FandomBot; print([m for m in dir(FandomBot) if not m.startswith('_')])"` 输出包含 `get_bot`, `check_exists`, `read_page_text`, `check_files_exist`

  **QA Scenarios**:

  ```
  Scenario: 4 个新方法可被导入且签名正确
    Tool: Bash (python -c)
    Preconditions: .env 存在(用 existing user's .env)
    Steps:
      1. python -c "import inspect; from fandom_bot import FandomBot; print(inspect.signature(FandomBot.check_exists)); print(inspect.signature(FandomBot.read_page_text)); print(inspect.signature(FandomBot.check_files_exist)); print(inspect.signature(FandomBot.get_bot))"
      2. 检查输出包含: (self, page_names: List[str]) -> Dict[str, bool] 等
    Expected Result: 4 行签名全部输出,无 ImportError
    Failure Indicators: ImportError, AttributeError, 签名缺类型注解
    Evidence: .sisyphus/evidence/task-1-methods-signatures.txt

  Scenario: edit_page 在 ratelimited 时重试
    Tool: Bash (python -c with mock)
    Preconditions: 用 unittest.mock.patch 模拟 page.edit
    Steps:
      1. 写一个 inline 脚本:
         from unittest.mock import MagicMock, patch
         import fandom_bot
         page = MagicMock()
         attempts = []
         def fake_edit(content, summary=None):
             attempts.append(summary)
             if len(attempts) < 2:
                 raise Exception("API error: ratelimited")
         page.edit.side_effect = fake_edit
         with patch('fandom_bot.time.sleep') as mock_sleep:
             bot = MagicMock()
             fandom_bot.FandomBot.edit_page(bot, page, "x", summary="test")
             print(f"attempts={len(attempts)} sleep_calls={mock_sleep.call_count} sleep_args={mock_sleep.call_args_list}")
      2. 执行
    Expected Result: attempts=2 sleep_calls=1 sleep_args=[call(60)]
    Failure Indicators: sleep_calls=0(没重试), 或 sleep_args 不是 60
    Evidence: .sisyphus/evidence/task-1-edit-page-retry.txt

  Scenario: get_bot singleton 多次调用只 init 一次
    Tool: Bash (python -c with mock)
    Preconditions: mock FandomBot.__init__
    Steps:
      1. inline 脚本 mock __init__,调用 FandomBot.get_bot() 两次,打印 id() 对比
    Expected Result: 两次 id() 相同, __init__ 调用计数 = 1
    Failure Indicators: id 不同, 或 __init__ 计数 > 1
    Evidence: .sisyphus/evidence/task-1-get-bot-singleton.txt
  ```

  **Commit**: YES(Wave 1 final 一起)
  - Message: `refactor(fandom_bot): add get_bot/check_exists/read_page_text/check_files_exist + edit_page rate-limit retry`
  - Files: `fandom_bot.py`
  - Pre-commit: `python -c "from fandom_bot import FandomBot"`

---

- [x] 2. **wiki_bot_server.py IPC server 骨架**

  **What to do**:
  - 新建 `/home/hxue/projets/py-wikieditor/.pi/extensions/wiki_bot_server.py`
  - 实现 stdin/stdout JSON-RPC 协议(单行 JSON in → 单行 JSON out)
  - 启动时:`from fandom_bot import FandomBot; bot = FandomBot.get_bot()` 持有单例
  - 协议骨架(完整方法在 T6 实现):
    ```python
    # 请求: {"id": "req-1", "method": "edit_page", "args": {"title": "...", "content": "..."}}
    # 响应: {"id": "req-1", "ok": true, "result": "..."} 或 {"id": "req-1", "ok": false, "error": "..."}
    ```
  - 主循环:`for line in sys.stdin: dispatch(json.loads(line))`
  - 错误处理:任何异常都包装成 `{"ok": false, "error": safe_error(e)}`,不崩进程
  - 加 `--help` / `--check` 模式:`python wiki_bot_server.py --check` 自检不启动 server
  - 用 `sys.stdout.write` + `sys.stdout.flush()` 保证即时输出(默认 print 有缓冲)

  **Must NOT do**:
  - 不在 server 内做业务逻辑(只 dispatch)
  - 不用 asyncio(简单同步足够,保持可读性)
  - 不依赖外部包(只用 stdlib + fandom_bot)
  - 不在 .pi/extensions/ 之外创建文件

  **Recommended Agent Profile**:
  - **Category**: `deep`(IPC 协议设计 + 错误处理边界,有思考量)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: T6, T7
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - Pi RPC mode protocol: https://pi.dev/docs/latest/rpc — 同样是 stdin/stdout JSONL 双向,可作为协议设计参考
  - `fandom_bot.py:69-75` (`safe_error`) — 复用此函数处理异常包装,保证不泄露 token/cookie

  **API/Type References**:
  - Python stdlib: `sys`, `json`, `threading`(T1 用了)
  - fandom_bot.FandomBot 公共方法清单(在 T1 完成后):get_bot, convert_text, get_page, get_category_members, get_template_embedded_pages, edit_page, move_page, get_subpages, check_exists, read_page_text, check_files_exist

  **External References**:
  - Pi RPC docs(上文)— 协议形状借鉴

  **WHY Each Reference Matters**:
  - safe_error 决定了 error 字段的格式和安全性(不能泄露 token)
  - Pi RPC 协议形状决定了 wiki-tools.ts 客户端的解析方式

  **Acceptance Criteria**:

  - [ ] `python .pi/extensions/wiki_bot_server.py --check` 退出码 0 且打印 "OK" 或类似
  - [ ] `echo '{"id":"t1","method":"ping","args":{}}' | python .pi/extensions/wiki_bot_server.py` 返回 `{"id":"t1","ok":true,"result":"pong"}` 一行

  **QA Scenarios**:

  ```
  Scenario: --check 模式自检通过
    Tool: Bash
    Preconditions: .env 存在
    Steps:
      1. python .pi/extensions/wiki_bot_server.py --check
    Expected Result: 退出码 0, 输出含 "OK"
    Failure Indicators: 退出码非 0, traceback
    Evidence: .sisyphus/evidence/task-2-server-check.txt

  Scenario: ping/pong 协议握手
    Tool: Bash
    Preconditions: server 能启动
    Steps:
      1. echo '{"id":"t1","method":"ping","args":{}}' | python .pi/extensions/wiki_bot_server.py
      2. 解析第一行 stdout 为 JSON
    Expected Result: JSON 含 id="t1", ok=true, result="pong"
    Failure Indicators: 无输出, 或 JSON 解析失败, 或 ok=false
    Evidence: .sisyphus/evidence/task-2-ping-pong.txt

  Scenario: 未知方法返回结构化错误(不崩进程)
    Tool: Bash
    Steps:
      1. echo '{"id":"t2","method":"nonexistent_method","args":{}}' | python .pi/extensions/wiki_bot_server.py
    Expected Result: JSON {"id":"t2","ok":false,"error":"Unknown method: nonexistent_method"}
    Failure Indicators: 进程崩溃, 输出 traceback, 无 JSON
    Evidence: .sisyphus/evidence/task-2-unknown-method.txt
  ```

  **Commit**: YES(Wave 1 final)
  - Message: `feat(pi): add wiki_bot_server.py IPC scaffold`
  - Files: `.pi/extensions/wiki_bot_server.py`
  - Pre-commit: `python .pi/extensions/wiki_bot_server.py --check`

---

- [x] 3. **pytest 基础设施 + mock mwclient fixtures**

  **What to do**:
  - 在 repo 根创建 `tests/` 目录
  - 创建 `tests/conftest.py`:
    - `mock_site` fixture:用 `unittest.mock.MagicMock()` 模拟 `mwclient.Site`,提供 `.pages[...]` 字典访问、`.login()`、`.categories[...]`、`.allpages(prefix=)`
    - `mock_page` factory fixture:返回一个能配置 `.exists` / `.text()` / `.edit()` / `.move()` / `.name` 的 MagicMock
    - `mock_bot` fixture:实例化 FandomBot 但用 `monkeypatch` 替换 `self.site` 为 mock_site,跳过登录
    - `isolated_env` fixture:复制 `.env.example` 到临时 `.env`,设测试用假凭据
  - 创建 `pytest.ini`(放 repo 根):
    ```ini
    [pytest]
    testpaths = tests
    python_files = test_*.py
    addopts = -v --tb=short
    ```
  - 创建 `tests/__init__.py`(空)
  - 在 `requirements.txt` 追加:`pytest>=7.0` `pytest-mock>=3.0`(如未存在)
  - 写一个 `tests/test_smoke.py` 验证基础设施:
    ```python
    def test_mock_bot(mock_bot):
        assert mock_bot is not None
        assert mock_bot.site is not None
    ```

  **Must NOT do**:
  - 不在 `.pi/` 内创建测试文件
  - 不依赖 `wiki_dump/`(已 gitignored)
  - 不在 conftest 里发任何真实网络请求
  - 不引入 tox/coverage 等额外工具(范围控制)

  **Recommended Agent Profile**:
  - **Category**: `quick`(配置文件 + 标准模板)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: T11, T12, T13
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `fandom_bot.py:190-218` (FandomBot.__init__) — 必须搞清楚哪些步骤要 mock(Site 构造、login、OpenCC)
  - `fandom_bot.py:281-288` (`convert_text`) — 测试可能要用到 OpenCC,需要 mock 或保留真实例

  **API/Type References**:
  - `mwclient.Site` 公共 API:`.pages[name]` 返回 Page、`.categories[name]` 返回 Category、`.login(user, pwd)`、`.allpages(prefix=)`
  - `mwclient.page.Page` 公共 API:`.exists`(bool property)、`.text()`(返回 str)、`.edit(text, summary=)`、`.move(new_name, reason=, no_redirect=)`、`.name`
  - pytest fixtures: `monkeypatch`(标准)、`MagicMock`(标准)

  **Test References**:
  - 无现成 pytest 测试(项目首次引入)

  **WHY Each Reference Matters**:
  - `__init__` 决定 mock 边界:必须 patch `mwclient.Site` 和 `site.login`,不能让 OpenCC 也被 mock(它是纯本地库,可保留)
  - mwclient API 决定 mock 形状(`pages[...]` 是 __getitem__ 调用,不是字典)

  **Acceptance Criteria**:

  - [ ] `python -m pytest tests/ -v` 退出码 0,test_smoke 至少 1 个 PASS
  - [ ] `pytest -m pytest --collect-only tests/` 能列出至少 1 个测试
  - [ ] mock_bot fixture 实例化的 FandomBot 不会触发真实登录(用 capsys/caplog 验证无网络调用)

  **QA Scenarios**:

  ```
  Scenario: pytest 能发现并跑通 smoke 测试
    Tool: Bash
    Preconditions: requirements.txt 已加 pytest
    Steps:
      1. pip install -r requirements.txt(若 agent 没装)
      2. python -m pytest tests/test_smoke.py -v
    Expected Result: 1 passed, 0 failed, 退出码 0
    Failure Indicators: ImportError, 退出码非 0, 0 passed
    Evidence: .sisyphus/evidence/task-3-pytest-smoke.txt

  Scenario: mock_bot 不触发真实网络
    Tool: Bash
    Preconditions: smoke 测试通过
    Steps:
      1. 写一个测试 test_mock_bot_no_network(mock_bot),用 socket.socket monkeypatch 检测任何 socket.connect 调用并 fail
      2. 跑 pytest
    Expected Result: 测试 PASS,无 socket.connect 调用
    Failure Indicators: socket.connect 被调用,测试 fail
    Evidence: .sisyphus/evidence/task-3-no-network.txt
  ```

  **Commit**: YES(Wave 1 final)
  - Message: `test: add pytest infrastructure + mock mwclient fixtures`
  - Files: `tests/`, `pytest.ini`, `requirements.txt`
  - Pre-commit: `python -m pytest tests/ -v`

---

- [x] 4. **TypeScript 测试基础设施 (tests/package.json + vitest)**

  **What to do**:
  - 在 `tests/` 下创建 `package.json`(独立于 Pi 加载链,放 tests/ 而非 .pi/ 避免干扰 auto-load):
    ```json
    {
      "name": "py-wikieditor-pi-tests",
      "private": true,
      "type": "module",
      "scripts": { "test": "vitest run" },
      "devDependencies": {
        "vitest": "^1.0.0",
        "@earendil-works/pi-coding-agent": "*",
        "typebox": "*"
      }
    }
    ```
  - 创建 `tests/vitest.config.ts`:
    ```typescript
    import { defineConfig } from 'vitest/config';
    export default defineConfig({
      test: { include: ['tests/**/*.test.ts'] }
    });
    ```
  - 创建 `tests/tsconfig.json`(strict mode)
  - 创建 `tests/helpers/mockExtensionContext.ts`:提供 `mockPi` 和 `mockCtx` helper,模拟 `ExtensionAPI`(包含 `registerTool`, `registerCommand`, `on`, `exec`, `getActiveTools`, `setActiveTools`, `getFlag`, `registerFlag`, `appendEntry`, `sendMessage`, `sendUserMessage`)和 `ExtensionContext`(包含 `ui.notify/confirm/select/custom/setStatus/setWidget`, `mode`, `hasUI`, `sessionManager`, `theme`)
  - 写 `tests/test_smoke.test.ts`:
    ```typescript
    import { describe, it, expect } from 'vitest';
    describe('smoke', () => { it('loads', () => expect(true).toBe(true)); });
    ```
  - 在 `tests/README.md` 简要说明运行方式

  **Must NOT do**:
  - 不在 `.pi/` 内创建 package.json
  - 不引入 jest(用 vitest,更现代且与 ESM 兼容)
  - 不安装 Pi 真实运行时到 tests/(只需要类型定义)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: YES, Wave 1, blocks T8/T13, blocked by None

  **References**:

  **Pattern References**:
  - Pi 扩展示例 `examples/extensions/permission-gate.ts`(在 GitHub pi 仓库)— 验证 `pi.on('tool_call', ...)` 和 `ctx.ui.confirm` 的真实用法
  - Pi 测试相关文档(若存在)— https://pi.dev/docs/latest 搜 "test"

  **API/Type References**:
  - `@earendil-works/pi-coding-agent` 的 `ExtensionAPI` 和 `ExtensionContext` 类型(从 npm 包获取)
  - vitest 1.x API:`describe`, `it`, `expect`, `vi.mock`, `vi.fn`

  **External References**:
  - vitest docs: https://vitest.dev/guide/

  **WHY Each Reference Matters**:
  - permission-gate.ts 是 mock 形状的权威参考(决定 mockExtensionContext 的方法清单)
  - ExtensionAPI 类型定义决定了 mock 必须实现哪些方法

  **Acceptance Criteria**:

  - [ ] `cd tests && npm install` 成功
  - [ ] `cd tests && npm test` 退出码 0
  - [ ] `mockExtensionContext.ts` 导出 `mockPi` 和 `mockCtx`,各自有完整的方法 stub

  **QA Scenarios**:

  ```
  Scenario: npm install + npm test 全绿
    Tool: Bash
    Steps:
      1. cd tests && npm install
      2. cd tests && npm test
    Expected Result: install 成功, 1 test passed
    Failure Indicators: 依赖装不上, 测试 0 passed
    Evidence: .sisyphus/evidence/task-4-vitest-smoke.txt

  Scenario: mockExtensionContext 完整
    Tool: Bash
    Steps:
      1. cd tests && npx tsc --noEmit helpers/mockExtensionContext.ts
      2. 写测试验证 mockPi.registerTool, mockPi.registerCommand, mockPi.on, mockCtx.ui.confirm 都存在
    Expected Result: tsc 0 errors, helper 方法齐全
    Failure Indicators: 类型错误, 缺方法
    Evidence: .sisyphus/evidence/task-4-mock-context.txt
  ```

  **Commit**: YES(Wave 1 final)
  - Message: `test: add TypeScript test infra (vitest) + mock extension context`
  - Files: `tests/package.json`, `tests/vitest.config.ts`, `tests/tsconfig.json`, `tests/helpers/`, `tests/test_smoke.test.ts`, `tests/README.md`
  - Pre-commit: `cd tests && npm test`

---

- [x] 5. **slash command 分类表 + 重写 batch-convert.md**

  **What to do**:
  - 先在 `.sisyphus/evidence/task-5-slash-map.md` 写出最终 8 个 slash command 的完整规格表(基于 Execution Strategy 中已锁定的分类表):
    - 每个 command:name、对应 fandom.py 子命令、参数列表、默认 dry-run?、是否需要 confirm、安全等级、示例用法
  - 重写 `/home/hxue/projets/py-wikieditor/.pi/prompts/batch-convert.md`:
    - frontmatter 保留 `name: wiki-batch-convert` + `description`
    - 把当前引用的 `/wiki_test` `/wiki_scan` `/wiki_convert_page` 替换为真实存在的 slash command
    - 工作流改为 5 步:
      1. `/wiki_test` 验证连接
      2. `/wiki_scan` scan-only 模式列出待转换页面
      3. `/wiki_convert_page page_name="..."` dry-run 预览单个
      4. 用户审核,确认后 `/wiki_convert_page page_name="..." --confirm` 实际转换
      5. 出问题 `/wiki_restore page_name="..." --show-versions`
    - 加"注意事项"段落,列出**不可用**的命令(scan --approve-all、move-category),指引用 bash

  **Must NOT do**:
  - 不实现 slash command 本身(那是 T9/T10),只写文档
  - 不动 SKILL.md(那是 T14)

  **Recommended Agent Profile**:
  - **Category**: `writing`(纯文档)
  - **Skills**: []

  **Parallelization**: YES, Wave 1, blocks T14, blocked by None

  **References**:

  **Pattern References**:
  - `.pi/prompts/batch-convert.md`(现有)— 在其上修改,保持 frontmatter 风格
  - Pi prompt templates 文档:https://pi.dev/docs/latest/prompt-templates — 验证 frontmatter 字段(`name`, `description`, `argument-hint`)
  - Execution Strategy 章节的"Slash Command 风险分类表"(本计划)— 权威表

  **API/Type References**:
  - Pi prompt template 参数语法:`$1` `$@` `${1:-default}`

  **WHY Each Reference Matters**:
  - 分类表是 command 命名/行为/默认值的 single source of truth,T9/T10 实现必须严格匹配
  - Pi prompt template 文档决定 frontmatter 合法字段

  **Acceptance Criteria**:

  - [ ] `.sisyphus/evidence/task-5-slash-map.md` 存在,包含 8 行(每 command 一行)+ 5 列(name/subcmd/default dry-run/confirm/level)
  - [ ] `batch-convert.md` 中所有 `/wiki_*` 引用都能在分类表里找到
  - [ ] `batch-convert.md` 不再出现 `/wiki_test` `/wiki_scan namespace=main scan_only=true` 这种旧格式(改成真实参数)

  **QA Scenarios**:

  ```
  Scenario: 分类表 8 行齐全
    Tool: Bash (grep)
    Steps:
      1. grep -c "^| \`/" .sisyphus/evidence/task-5-slash-map.md
    Expected Result: 8
    Failure Indicators: < 8(有遗漏)
    Evidence: .sisyphus/evidence/task-5-slash-map.txt

  Scenario: batch-convert.md 不含旧命令
    Tool: Bash (grep)
    Steps:
      1. grep -E "/wiki_(test|scan|convert_page)\s" .pi/prompts/batch-convert.md
    Expected Result: 无匹配(退出码 1) 或匹配项的参数符合新规格
    Failure Indicators: 有旧格式引用
    Evidence: .sisyphus/evidence/task-5-batch-convert-clean.txt

  Scenario: batch-convert.md 5 步流程完整
    Tool: Read (人工 check)
    Steps:
      1. Read .pi/prompts/batch-convert.md
      2. 验证包含: /wiki_test, /wiki_scan, /wiki_convert_page (含 dry_run=true 和 confirm), /wiki_restore
    Expected Result: 4-5 个 slash command 出现且参数合理
    Failure Indicators: 步骤缺漏, 参数错
    Evidence: .sisyphus/evidence/task-5-batch-convert-final.md(复制品)
  ```

  **Commit**: YES(Wave 1 final)
  - Message: `docs(pi): finalize slash command map + rewrite batch-convert.md to match real surface`
  - Files: `.pi/prompts/batch-convert.md`, `.sisyphus/evidence/task-5-slash-map.md`
  - Pre-commit: 无

---

- [x] 6. **wiki_bot_server.py 完整实现**

  **What to do**:
  - 在 T2 骨架基础上,实现完整 method dispatch 表,映射所有 FandomBot 公共方法:
    ```python
    METHODS = {
        "ping": lambda bot, args: "pong",
        "check_exists": lambda bot, args: bot.check_exists(args["page_names"]),
        "read_page_text": lambda bot, args: bot.read_page_text(args["page_name"]),
        "check_files_exist": lambda bot, args: bot.check_files_exist(args["filenames"]),
        "edit_page": lambda bot, args: bot.edit_page_by_name(args["title"], args["content"], args.get("summary", "自动生成页面")),
        "get_category_members": lambda bot, args: [p.name for p in bot.get_category_members(args["category_name"])],
        "get_template_embedded_pages": lambda bot, args: [p.name for p in bot.get_template_embedded_pages(args["template_name"])],
        "convert_text": lambda bot, args: bot.convert_text(args["text"]),
    }
    ```
  - 在 FandomBot 加便捷方法 `edit_page_by_name(self, title, content, summary)`(T1 漏了,本任务补):`page = self.get_page(title); self.edit_page(page, content, summary)`
  - server 主循环:read line → parse JSON → validate `id` and `method` 字段 → dispatch → 包装结果为 `{"id":..., "ok":true, "result":...}` → write line + flush
  - 验证输入 schema(每个 method 列出必填 args)
  - 大输入处理:从 stdin 读 line 时设上限(如 50MB),超限拒绝
  - 会话失效检测:若 edit_page 抛 login 错误,清 `_BOT_INSTANCE` 并重试一次
  - 加 `--method-docs` flag:打印所有 method 的 JSON schema,供 T9/T10 参考

  **Must NOT do**:
  - 不在 server 内做权限控制(那是 wiki-tools.ts 的 responsibility)
  - 不暴露 `__init__` 或任何下划线方法
  - 不缓存 method 结果(每次都走 FandomBot)

  **Recommended Agent Profile**:
  - **Category**: `deep`(协议契约 + 错误恢复)
  - **Skills**: []

  **Parallelization**: YES, Wave 2, blocks T7/T12, blocked by T1 + T2

  **References**:

  **Pattern References**:
  - T2 完成的 server 骨架 — 直接扩展
  - `fandom_bot.py` FandomBot 公共方法(T1 完成后)— 所有 method 必须正确调用

  **API/Type References**:
  - T1 完成后 FandomBot 的方法清单(见 T1 acceptance)
  - Pi RPC 协议形状(JSONL,T2 已实现)

  **WHY Each Reference Matters**:
  - T1 是直接依赖(T6 调用的方法在 T1 实现)
  - T2 是骨架依赖(本任务在 T2 基础上扩展)

  **Acceptance Criteria**:

  - [ ] `python .pi/extensions/wiki_bot_server.py --method-docs` 输出合法 JSON,包含 8 个 method 的 schema
  - [ ] 对每个 method 都有一个手测 echo 命令(写在 evidence 里)能返回 ok=true
  - [ ] 模拟 ratelimited 异常,server 返回 ok=true(因为 edit_page 内部重试了)

  **QA Scenarios**:

  ```
  Scenario: --method-docs 输出合法 JSON schema
    Tool: Bash
    Steps:
      1. python .pi/extensions/wiki_bot_server.py --method-docs > /tmp/methods.json
      2. python -c "import json; d = json.load(open('/tmp/methods.json')); print(len(d), sorted(d.keys()))"
    Expected Result: 8 (or more), keys include ping/check_exists/read_page_text/check_files_exist/edit_page/...
    Failure Indicators: JSON 解析失败, 或 method 数 < 8
    Evidence: .sisyphus/evidence/task-6-method-docs.json

  Scenario: check_exists 端到端(mock mwclient)
    Tool: Bash
    Preconditions: .env 存在但 monkeypatch mwclient.Site 跳过登录
    Steps:
      1. 写 inline 测试启动 server 子进程,stdin 发 check_exists 请求,stdout 收响应
      2. 或更简单: 直接 from wiki_bot_server import handle_request; result = handle_request({"id":"t","method":"check_exists","args":{"page_names":["A","B"]}})
    Expected Result: {"id":"t","ok":true,"result":{"A":True,"B":False}}(假设 mock A exists, B not)
    Failure Indicators: ok=false, 或 result 不是 dict
    Evidence: .sisyphus/evidence/task-6-check-exists.txt

  Scenario: 大输入拒绝(>50MB)
    Tool: Bash
    Steps:
      1. python -c "print('x' * (60 * 1024 * 1024))" | python .pi/extensions/wiki_bot_server.py
    Expected Result: 进程退出码非 0, stderr 含 "input too large"
    Failure Indicators: 进程崩, 或 OOM, 或无任何输出
    Evidence: .sisyphus/evidence/task-6-large-input.txt

  Scenario: 会话失效重试一次
    Tool: Bash (mock)
    Steps:
      1. mock edit_page 第一次抛 "login expired",第二次 ok
      2. monkeypatch FandomBot.get_bot 让 _BOT_INSTANCE 被清后下次返回新 mock
      3. 发 edit_page 请求
    Expected Result: ok=true, FandomBot.__init__ 被调用 2 次
    Failure Indicators: ok=false, 或 init 只调 1 次
    Evidence: .sisyphus/evidence/task-6-session-retry.txt
  ```

  **Commit**: YES(Wave 2 final)
  - Message: `feat(pi): implement wiki_bot_server.py full method dispatch + session retry`
  - Files: `.pi/extensions/wiki_bot_server.py`, `fandom_bot.py`(补 edit_page_by_name)
  - Pre-commit: `python .pi/extensions/wiki_bot_server.py --method-docs`

---

- [x] 7. **抽取 inline Python 到 wiki_tools/ + 重写 wiki-tools.ts 4 个工具走 server**

  **What to do**:
  - 创建 `.pi/extensions/wiki_tools/` 目录(注意:与 `wiki-tools.ts` 同级,名字带下划线区分)
  - 把 wiki-tools.ts 现有 4 个工具的 inline Python 抽到独立模块:
    - `.pi/extensions/wiki_tools/__init__.py`(空)
    - `.pi/extensions/wiki_tools/save_page.py` — 函数 `save_page(bot, title, content, summary)`,内部调 `bot.edit_page_by_name(title, content, summary)`,**不再用 inline mwclient**
    - `.pi/extensions/wiki_tools/check_exists.py` — `check_exists(bot, titles) -> Dict[str, bool]`
    - `.pi/extensions/wiki_tools/check_files.py` — `check_files_exist(bot, filenames) -> Dict[str, bool]`
    - `.pi/extensions/wiki_tools/read_page.py` — `read_page(bot, title) -> Optional[str]`
    - 每个模块加 `if __name__ == "__main__":` 入口,接受 JSON via stdin,输出 JSON via stdout,便于独立调试
  - 重写 `/home/hxue/projets/py-wikieditor/.pi/extensions/wiki-tools.ts`:
    - 启动时(T8 之后):`session_start` 事件里 `pi.exec("python", [".pi/extensions/wiki_bot_server.py"])` 启动 server 子进程,保存 child process handle
    - 实现 `callServer(method, args)` helper:写一行 JSON 到 child stdin,从 stdout 读一行响应,解析返回
    - 4 个工具的 `execute` 函数改为:`return await callServer("check_exists", {page_names: params.titles})` 等
    - 删除所有 inline Python 模板字符串(彻底解决 R2 ARG_MAX + R3 注入问题)
    - session_shutdown 时 kill child process
  - 保留 `__待填__` 拦截(移到工具 execute 内,server 调用前)
  - 保留 `PYTHON = "python3"` 改成 `const PYTHON = process.env.PI_WIKI_PYTHON || "python"`(环境变量可覆盖,默认与 AGENTS.md 一致)

  **Must NOT do**:
  - 不暴露 server 子进程给其他扩展(只是内部 helper)
  - 不在工具 execute 里写 Python 代码(全部走 server 调用)
  - 不删 `__待填__` 拦截

  **Recommended Agent Profile**:
  - **Category**: `deep`(架构调整 + 跨语言协议)
  - **Skills**: []

  **Parallelization**: YES, Wave 2, blocks T9/T10/T12/T13, blocked by T2 + T6

  **References**:

  **Pattern References**:
  - T6 完成的 `wiki_bot_server.py` — 客户端必须严格匹配协议
  - 现有 `.pi/extensions/wiki-tools.ts` — 重写而非重起炉灶,保留安全规则结构
  - Pi 扩展 SDK 示例 `examples/extensions/ssh.ts`(GitHub pi 仓库)— `pi.exec` 用法和 child process 模式参考

  **API/Type References**:
  - Pi `ExtensionAPI.exec(cmd, args)` 返回 `{code, stdout, stderr, killed}`
  - Pi `ExtensionAPI.on("session_start")` / `on("session_shutdown")` 钩子
  - Node.js `child_process.ChildProcess`(若 pi.exec 返回此类型)

  **WHY Each Reference Matters**:
  - server 协议(MUST match)— 任何字段名/类型不一致都会让 4 工具全部失效
  - ssh.ts 是 `pi.exec` + 子进程生命周期的实战参考

  **Acceptance Criteria**:

  - [ ] `.pi/extensions/wiki_tools/` 下有 5 个 .py 文件
  - [ ] wiki-tools.ts 不再包含任何 `page.edit(` / `bot.site.pages[` / inline `import sys` 字符串
  - [ ] 启动 pi 加载扩展后,4 个工具的 description 与原来一致(label/description/parameters)
  - [ ] 调用 wiki_check_exists 返回 {title: bool} 形式

  **QA Scenarios**:

  ```
  Scenario: wiki-tools.ts 不再含 inline mwclient
    Tool: Bash (grep)
    Steps:
      1. grep -E "(bot\.site\.pages|page\.edit\(|import sys)" .pi/extensions/wiki-tools.ts
    Expected Result: 无匹配(退出码 1)
    Failure Indicators: 有匹配
    Evidence: .sisyphus/evidence/task-7-no-inline-mwclient.txt

  Scenario: 4 个 Python handler 模块独立可跑
    Tool: Bash
    Preconditions: mock FandomBot via monkeypatch
    Steps:
      1. echo '{"title":"Test","content":"hello"}' | python .pi/extensions/wiki_tools/save_page.py
      2. 类似 check_exists.py / check_files.py / read_page.py
    Expected Result: 每个 .py 接受 JSON stdin,输出 JSON stdout,无 traceback
    Failure Indicators: ImportError, traceback, 非 JSON 输出
    Evidence: .sisyphus/evidence/task-7-handler-modules.txt

  Scenario: wiki_check_exists 端到端(via mock server)
    Tool: Bash
    Preconditions: 启动 mock wiki_bot_server.py(返回固定 check_exists 结果)
    Steps:
      1. 模拟 Pi 扩展加载(用 vitest)
      2. dispatch tool_call event: toolName="wiki_check_exists", input={titles:["A","B"]}
      3. 断言返回 content[0].text 是 JSON 字符串解析后 {A:true, B:false}
    Expected Result: 工具走 server 并返回正确结构
    Failure Indicators: 工具直连 mwclient, 或返回结构错
    Evidence: .sisyphus/evidence/task-7-tool-via-server.txt

  Scenario: __待填__ 拦截仍在
    Tool: vitest
    Steps:
      1. dispatch tool_call event: toolName="wiki_save_page", input={title:"X", content:"name=__待填__"}
      2. 断言返回 {block: true, reason: /待填/}
    Expected Result: 拦截生效, 不调用 server
    Failure Indicators: 工具真的调了 server
    Evidence: .sisyphus/evidence/task-7-stub-block.txt
  ```

  **Commit**: YES(Wave 2 final)
  - Message: `refactor(pi-extension): extract inline Python to wiki_tools/ + rewrite 4 tools to use IPC server`
  - Files: `.pi/extensions/wiki-tools.ts`, `.pi/extensions/wiki_tools/*.py`
  - Pre-commit: `cd tests && npm test`(基础设施已建)

---

- [x] 8. **实现 permission gate(bash + 路径 + flag 拦截)**

  **What to do**:
  - 在 wiki-tools.ts(或独立文件 `.pi/extensions/permission-gate.ts`)实现 3 类拦截,**全部用 `pi.on("tool_call", ...)`**:
    1. **危险 bash 命令** — 正则匹配 `\brm\s+-rf\b`、`\bsudo\b`、`\bchmod\s+777\b`、`>\s*/dev/sd`、`:\(\)\s*\{\s*:\s*\}` (fork bomb)、`\|\s*(sh|bash)\s*$` (pipe to shell)。匹配后 `await ctx.ui.confirm("⚠️ 危险命令", command)` 弹确认,No 则 `{block: true, reason: "..."}`
    2. **敏感路径写入** — `tool_call` 监听 edit/write/bash,提取所有 string 参数扫描 `(^|/)\.env$`、`config\.json$`、`credentials`、`*.pem`、`*.key`、`*id_rsa*`、`.ssh/`。匹配则直接 block(不需 confirm,因为绝不会是合法操作)
    3. **`--no-test-first` flag 拦截** — 任何 tool_call 的 input 中任意 string 字段含 `--no-test-first` 直接 block
  - 在 wiki-tools.ts 顶部 import permission-gate,或 inline 在同一个扩展文件(后者更简单)
  - 加配置项让用户能查看被拦的命令日志(`/wiki_show_blocks` slash command,只读 list)
  - 所有拦截走同一 `notify` + `confirm` 流程,风格统一

  **Must NOT do**:
  - 不拦截 read/grep/find/ls(只读工具不拦)
  - 不让用户禁用 permission gate(显式 out of scope;若用户坚持,可建议改源码)
  - 不引入外部权限策略库(纯手写,正则即可)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`(安全逻辑,需细致)
  - **Skills**: []

  **Parallelization**: YES, Wave 2, blocks T10/T13, blocked by T4

  **References**:

  **Pattern References**:
  - Pi 官方示例 `examples/extensions/permission-gate.ts`(GitHub pi 仓库)— 完整的 `pi.on("tool_call") + ctx.ui.confirm` 实战代码,直接参考其 `dangerousPatterns` 数组结构
  - 现有 `.pi/extensions/wiki-tools.ts:149-165`(`.env`/`config.json`/`credentials` 拦截)— 在此基础上扩展

  **API/Type References**:
  - Pi `tool_call` 事件:`event.toolName`, `event.input`(可能是任意 object)
  - Pi `ctx.ui.confirm(title, message) -> Promise<bool>`、`ctx.ui.notify(msg, level)`
  - Pi `ctx.ui.select(title, options) -> Promise<string>`

  **External References**:
  - Bash 危险模式参考:https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/permission-gate.ts

  **WHY Each Reference Matters**:
  - 官方 permission-gate 是基线参考,但我们的更严(还拦敏感路径和 --no-test-first)
  - 现有 .env 拦截是改动起点,保留其行为

  **Acceptance Criteria**:

  - [ ] 5 种危险 bash 模式各有 1 个 vitest 模拟测试
  - [ ] 5 种敏感路径各有 1 个 vitest 模拟测试
  - [ ] `--no-test-first` 在任意 string 字段被拦,1 个测试
  - [ ] 普通 read 调用不被拦(回归测试)

  **QA Scenarios**:

  ```
  Scenario: rm -rf 被拦截并 confirm
    Tool: vitest
    Steps:
      1. mock ctx.ui.confirm 返回 false
      2. dispatch tool_call: toolName="bash", input={command:"rm -rf /tmp/foo"}
      3. 断言返回 {block: true, reason: /rm -rf/}
      4. 断言 ctx.ui.confirm 被调用 1 次
    Expected Result: 拦截生效
    Failure Indicators: 未拦, 或 confirm 未被调用
    Evidence: .sisyphus/evidence/task-8-rm-rf-blocked.txt

  Scenario: sudo 被拦截
    Tool: vitest
    Steps:
      1. dispatch tool_call: toolName="bash", input={command:"sudo apt install x"}
      2. mock confirm 返回 true(用户同意)
      3. 断言返回 undefined(放行,因为 confirm=true)
    Expected Result: confirm=true 时放行
    Failure Indicators: 即使 confirm=true 也 block
    Evidence: .sisyphus/evidence/task-8-sudo-confirm-pass.txt

  Scenario: echo > .env 被拦截(无 confirm 直接 block)
    Tool: vitest
    Steps:
      1. dispatch tool_call: toolName="bash", input={command:"echo KEY=val > .env"}
      2. 断言返回 {block: true, reason: /\.env/}
      3. 断言 ctx.ui.confirm 未被调用
    Expected Result: 直接 block(敏感路径不弹 confirm)
    Failure Indicators: 弹了 confirm, 或未拦
    Evidence: .sisyphus/evidence/task-8-env-direct-block.txt

  Scenario: --no-test-first 被拦截
    Tool: vitest
    Steps:
      1. dispatch tool_call: toolName="wiki_convert_category", input={category:"X", flags:"--no-test-first"}
      2. 断言返回 {block: true, reason: /no-test-first/}
    Expected Result: 拦截
    Failure Indicators: 未拦
    Evidence: .sisyphus/evidence/task-8-no-test-first-blocked.txt

  Scenario: 普通 read 不被拦(回归)
    Tool: vitest
    Steps:
      1. dispatch tool_call: toolName="read", input={filePath:"README.md"}
      2. 断言返回 undefined(放行)
    Expected Result: 放行
    Failure Indicators: 误拦
    Evidence: .sisyphus/evidence/task-8-read-passes.txt
  ```

  **Commit**: YES(Wave 2 final)
  - Message: `feat(pi-extension): permission gate (bash danger + sensitive paths + --no-test-first)`
  - Files: `.pi/extensions/wiki-tools.ts`(或新建 `permission-gate.ts`)
  - Pre-commit: `cd tests && npm test`

---

- [x] 9. **实现 6 个 safe/bounded slash commands**

  **What to do**:
  - 在 wiki-tools.ts 用 `pi.registerCommand(name, options)` 注册 6 个命令(基于 T5 锁定的分类表):
    1. `/wiki_test` — 直接调 server ping + 一个 check_exists,验证连接;无需 args
    2. `/wiki_info [template_name]` — 调 server `read_page_text(template_name or "Template:音樂信息")`,打印
    3. `/wiki_convert_page page_name="..." [--confirm]` — 默认 `pi.exec("python", ["src/fandom.py", "page", page_name, "--dry-run"])`;若 `--confirm` 出现,先 `ctx.ui.confirm` 再去掉 --dry-run
    4. `/wiki_convert_category category="..." [--confirm] [--limit N]` — 同上模式
    5. `/wiki_convert_template template="..." [--confirm]` — 同上
    6. `/wiki_restore page_name="..." [--show-versions]` — 默认 `--show-versions` 列版本;真恢复需 `--confirm` + `ctx.ui.confirm` 二次确认
    7. `/wiki_scan [--limit N]` — 只走 `--scan-only`,不接受 `--approve-all`(代码层强制)
    8. `/wiki_scan_category [--limit N]` — 同上
  - **实际是 8 个**(把 T9 范围扩到含 read 类),T10 只管 destructive fix-links/update-cat-refs/save_page 三个
  - 每个命令解析参数(简单 split 或自己写小 parser;若参数复杂可用 `minimist` 但 npm 安装会涉及)
  - 调用 fandom.py 时用 `pi.exec(PYTHON, ["src/fandom.py", ...args])`,把 stdout/stderr 通过 `ctx.ui.notify` 或返回 string 给用户
  - 长 stdout 截断(超过 5000 字符截中间,头尾各保留)
  - 失败时(非零退出码)用 `ctx.ui.notify("❌ " + stderr, "error")`

  **Must NOT do**:
  - 不实现 destructive 命令(T10)
  - 不暴露 `--approve-all` 给 scan(强制代码层拒绝)
  - 不暴露 `--no-test-first`(T8 已拦,但代码层也不接受)
  - 不在 slash command 内做权限控制(permission gate 是统一入口)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`(8 个命令,每个都需考虑参数和错误)
  - **Skills**: []

  **Parallelization**: YES, Wave 2, blocks T13/T14, blocked by T7

  **References**:

  **Pattern References**:
  - T5 锁定的 slash command 分类表(在 `.sisyphus/evidence/task-5-slash-map.md`)— 权威参数表
  - `src/fandom.py` 各子命令 argparse 定义 — 验证参数名/格式
  - Pi 官方示例 `examples/extensions/todo.ts` — `pi.registerCommand` 的真实用法

  **API/Type References**:
  - `pi.registerCommand(name: string, options: { description: string, handler: (args: string, ctx) => Promise<void> })`
  - `pi.exec(cmd: string, args: string[]) -> Promise<{code, stdout, stderr, killed}>`
  - `ctx.ui.notify(message, level)` level ∈ "info" | "warning" | "error"
  - `ctx.ui.confirm(title, message) -> Promise<bool>`

  **WHY Each Reference Matters**:
  - 分类表锁定行为(默认 dry-run?需要 confirm?参数顺序?)
  - fandom.py 子命令定义锁定 `pi.exec` 传入的 args 顺序和拼写

  **Acceptance Criteria**:

  - [ ] wiki-tools.ts 包含 8 个 `pi.registerCommand` 调用
  - [ ] vitest 模拟 `/wiki_test` `--help` 风格调用,返回 ping=pong
  - [ ] 模拟 `/wiki_convert_page page_name="X"` 默认 dry-run,`pi.exec` 调用参数含 `--dry-run`
  - [ ] 模拟 `/wiki_convert_page page_name="X" --confirm`,confirm mock 返回 true,`pi.exec` 不含 `--dry-run`
  - [ ] `/wiki_scan` 传入 `--approve-all` 直接拒绝(在 handler 内检查 args)

  **QA Scenarios**:

  ```
  Scenario: /wiki_test 返回 pong
    Tool: vitest
    Steps:
      1. mock callServer("ping") 返回 "pong"
      2. dispatch /wiki_test command via mockPi.registerCommand handler
      3. 断言 ctx.ui.notify 被调用,消息含 "pong"
    Expected Result: notify 含 pong
    Failure Indicators: 未触发 notify, 或 server 未调用
    Evidence: .sisyphus/evidence/task-9-wiki-test.txt

  Scenario: /wiki_convert_page 默认 dry-run
    Tool: vitest
    Steps:
      1. mockPi.exec = vi.fn().mockResolvedValue({code:0, stdout:"dry-run ok", stderr:""})
      2. dispatch /wiki_convert_page handler with args = 'page_name="测试页"'
      3. 断言 mockPi.exec 调用 args 含 "--dry-run"
    Expected Result: args 含 ["src/fandom.py", "page", "测试页", "--dry-run"]
    Failure Indicators: args 缺 --dry-run, 或参数顺序错
    Evidence: .sisyphus/evidence/task-9-convert-page-dry-run.txt

  Scenario: /wiki_convert_page --confirm 走真改
    Tool: vitest
    Steps:
      1. mockPi.exec = vi.fn().mockResolvedValue({code:0, stdout:"ok", stderr:""})
      2. mock ctx.ui.confirm 返回 true
      3. dispatch handler with args = 'page_name="测试页" --confirm'
      4. 断言 mockPi.exec args 不含 "--dry-run"
      5. 断言 ctx.ui.confirm 被调用 1 次
    Expected Result: 真改,且 confirm 被问
    Failure Indicators: 没问就改, 或仍带 --dry-run
    Evidence: .sisyphus/evidence/task-9-convert-page-confirm.txt

  Scenario: /wiki_scan 拒绝 --approve-all
    Tool: vitest
    Steps:
      1. dispatch handler with args = "--approve-all"
      2. 断言 mockPi.exec 未被调用
      3. 断言 ctx.ui.notify 被调用,level="error"
    Expected Result: 拒绝执行
    Failure Indicators: 调了 pi.exec
    Evidence: .sisyphus/evidence/task-9-scan-rejects-approve.txt

  Scenario: /wiki_convert_category confirm=false 不改
    Tool: vitest
    Steps:
      1. mock ctx.ui.confirm 返回 false
      2. dispatch handler with args = 'category="X" --confirm'
      3. 断言 mockPi.exec 未被调用
    Expected Result: 用户拒绝后中止
    Failure Indicators: 仍调 pi.exec
    Evidence: .sisyphus/evidence/task-9-confirm-false-aborts.txt
  ```

  **Commit**: YES(Wave 2 final)
  - Message: `feat(pi-extension): 8 safe/bounded slash commands (test/info/page/category/template/restore/scan/scan_category)`
  - Files: `.pi/extensions/wiki-tools.ts`
  - Pre-commit: `cd tests && npm test`

---

- [x] 10. **实现 destructive slash commands (fix-links/update-cat-refs/save_page confirm 流程)**

  **What to do**:
  - wiki_save_page 工具的 execute 内加确认:在 `__待填__` 拦截通过后,**调 server 前先 `ctx.ui.confirm("⚠️ 即将覆盖页面: " + title, "内容预览:\n" + content.slice(0, 500))`**,confirm=false 直接返回错误
  - 注册 2 个 destructive slash commands:
    1. `/wiki_fix_links old_text="..." new_text="..." [--confirm] [--limit N]` — 默认 `pi.exec fandom.py fix-links --dry-run`,confirm 后去掉 --dry-run
    2. `/wiki_update_cat_refs [categories...] [--from-file FILE] [--confirm]` — 同模式
  - 所有 destructive 命令的 confirm 提示语统一含 "破坏性操作,影响 N 个页面" 字样
  - 实现一个 helper `withDestructiveConfirm(name, args, ctx, runFn)`:`if (args.includes("--confirm")) { const ok = await ctx.ui.confirm(...); if (!ok) return; } const dryRun = !args.includes("--confirm"); ...`
  - wiki_save_page 不暴露为 slash command(它是 tool,不是 command)

  **Must NOT do**:
  - 不允许 wiki_save_page 工具无 confirm 就执行(即使内容没 `__待填__`)
  - 不接受 `--no-test-first`(T8 已统一拦)
  - 不在 fix-links 里默认批量大改(必须 --confirm)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`(破坏性逻辑,边界多)
  - **Skills**: []

  **Parallelization**: YES, Wave 2, blocks T13/T14, blocked by T7 + T8

  **References**:

  **Pattern References**:
  - T9 实现的 6 个 safe slash command 模式 — destructive 沿用 args parsing + confirm 流程
  - T8 实现的 permission gate — destructive 命令也会被它检查(`--no-test-first` 等)
  - 现有 wiki-tools.ts:168-180 的 `__待填__` 拦截 — 加 confirm 后此拦截保留

  **API/Type References**:
  - `pi.registerCommand`, `ctx.ui.confirm`, `pi.exec`(同 T9)
  - fandom.py `fix-links` / `update-cat-refs` 子命令的 argparse(在 src/fandom.py:131-141)

  **WHY Each Reference Matters**:
  - 复用 T9 模式保证 8+2 个命令 UX 一致
  - fandom.py 子命令决定参数透传

  **Acceptance Criteria**:

  - [ ] wiki_save_page execute 内调 server 前必有 `ctx.ui.confirm`
  - [ ] `/wiki_fix_links` 不带 `--confirm` 时 `pi.exec` args 含 `--dry-run`
  - [ ] `/wiki_fix_links` 带 `--confirm` 但 confirm() 返回 false 时 `pi.exec` 不被调用
  - [ ] `/wiki_update_cat_refs` 同上 2 项

  **QA Scenarios**:

  ```
  Scenario: wiki_save_page 无 confirm 不调 server
    Tool: vitest
    Steps:
      1. mock ctx.ui.confirm 返回 false
      2. dispatch tool_call: toolName="wiki_save_page", input={title:"X", content:"valid"}
      3. 断言 callServer 未被调用
      4. 断言返回含 error/message
    Expected Result: 确认拒绝, 不真改
    Failure Indicators: 仍调 server
    Evidence: .sisyphus/evidence/task-10-save-page-confirm-false.txt

  Scenario: wiki_save_page confirm=true 调 server
    Tool: vitest
    Steps:
      1. mock ctx.ui.confirm 返回 true
      2. dispatch tool_call 同上
      3. 断言 callServer 被调用 1 次,method="edit_page",args 含 title/content
    Expected Result: 走 server 写入
    Failure Indicators: 未调 server, 或 args 缺字段
    Evidence: .sisyphus/evidence/task-10-save-page-confirm-true.txt

  Scenario: /wiki_fix_links 默认 dry-run
    Tool: vitest
    Steps:
      1. dispatch handler with args = 'old_text="A" new_text="B"'
      2. 断言 mockPi.exec args 含 ["fix-links", "A", "B", "--dry-run"]
    Expected Result: 默认 dry-run
    Failure Indicators: 缺 --dry-run
    Evidence: .sisyphus/evidence/task-10-fix-links-dry-run.txt

  Scenario: /wiki_fix_links --confirm confirm=false 不执行
    Tool: vitest
    Steps:
      1. mock ctx.ui.confirm 返回 false
      2. dispatch handler with args = 'old_text="A" new_text="B" --confirm'
      3. 断言 mockPi.exec 未被调用
    Expected Result: 中止
    Failure Indicators: 仍执行
    Evidence: .sisyphus/evidence/task-10-fix-links-confirm-abort.txt

  Scenario: /wiki_update_cat_refs 同模式
    Tool: vitest
    Steps: 同上,但 args = 'categories="X" "Y" --confirm'
    Expected Result: confirm=true 时 pi.exec 含 ["update-cat-refs", "X", "Y"],不含 --dry-run
    Failure Indicators: 参数顺序错或仍带 dry-run
    Evidence: .sisyphus/evidence/task-10-update-cat-refs.txt
  ```

  **Commit**: YES(Wave 2 final)
  - Message: `feat(pi-extension): destructive commands (wiki_save_page confirm + /wiki_fix_links + /wiki_update_cat_refs) with default dry-run`
  - Files: `.pi/extensions/wiki-tools.ts`
  - Pre-commit: `cd tests && npm test`

---

- [x] 11. **fandom_bot.py 单元测试**

  **What to do**:
  - 创建 `tests/test_fandom_bot.py`,覆盖:
    - `TestFandomBotInit`: 用 mock_site 验证 __init__ 不发网络(用 monkeypatch 替换 mwclient.Site)
    - `TestEditPageRetry`: mock `page.edit` 第一次抛 `Exception("ratelimited")`,第二次 ok;调用 `bot.edit_page(page, "x")`;断言 `time.sleep` 调用 1 次参数 60,断言方法正常返回
    - `TestEditPageRetryExhausted`: mock 始终抛 ratelimited,3 次后抛出
    - `TestCheckExists`: mock `bot.site.pages["A"].exists=True, ["B"]=False`;断言 `bot.check_exists(["A","B"]) == {"A":True, "B":False}`
    - `TestReadPageText`: 存在返回 text,不存在返回 None
    - `TestCheckFilesExist`: 自动加 `File:` 前缀
    - `TestGetBotSingleton`: mock __init__,调用两次 `FandomBot.get_bot()`,断言 id 相同 + __init__ 调用 1 次
    - `TestGetBotConcurrentInit`: 用 threading 模拟并发,断言 __init__ 只调一次(lock 生效)
    - `TestGetBotFailureNotCached`: mock __init__ 抛 ValueError,调用两次都抛,__init__ 调用 2 次(失败不缓存)
  - 用 `pytest-mock` 的 `mocker` fixture
  - 用 `monkeypatch` 替换 `mwclient.Site` 为 mock 工厂
  - 所有测试用 `@pytest.mark.usefixtures("mock_site")` 风格

  **Must NOT do**:
  - 不依赖 `wiki_dump/`(已 gitignored)
  - 不在测试中调真实 Fandom API
  - 不测 `convert_text`(OpenCC 是真实库,本身可信,留集成测试)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: YES, Wave 3, blocks F1-F4, blocked by T1 + T3

  **References**:

  **Pattern References**:
  - T3 完成的 `tests/conftest.py` 的 `mock_site` / `mock_page` / `mock_bot` fixtures — 直接用
  - T1 实现的 4 个新方法 + edit_page retry — 测试目标

  **API/Type References**:
  - pytest fixtures: `mocker`(pytest-mock), `monkeypatch`, `capsys`, `tmp_path`
  - `unittest.mock.patch` 的用法:`patch.object(Class, "method")`, `patch("module.func")`

  **WHY Each Reference Matters**:
  - T3 fixtures 是 mock 基础设施
  - T1 的实现是测试目标(行为契约)

  **Acceptance Criteria**:

  - [ ] `python -m pytest tests/test_fandom_bot.py -v` 全绿
  - [ ] 至少 9 个测试方法(对应上述 9 个 Test 类)
  - [ ] coverage fandom_bot.py 新方法 ≥ 90%(用 `pytest --cov=fandom_bot tests/` 若装了 pytest-cov;否则 N/A)

  **QA Scenarios**:

  ```
  Scenario: 全部测试通过
    Tool: Bash
    Steps:
      1. python -m pytest tests/test_fandom_bot.py -v
    Expected Result: 9+ passed, 0 failed
    Failure Indicators: 任何 fail, 或 ImportError
    Evidence: .sisyphus/evidence/task-11-fandom-bot-tests.txt

  Scenario: ratelimited 重试逻辑被测
    Tool: Bash (grep)
    Steps:
      1. grep -A 5 "def test.*retry" tests/test_fandom_bot.py
    Expected Result: 至少 2 个测试(retry success + retry exhausted)
    Failure Indicators: 缺少其中一个
    Evidence: .sisyphus/evidence/task-11-retry-tests-exist.txt

  Scenario: 无网络调用
    Tool: Bash
    Steps:
      1. 在 conftest 的 mock_site 加一个 socket monkeypatch,任何 connect 都 fail
      2. python -m pytest tests/test_fandom_bot.py -v
    Expected Result: 全 PASS(说明 mock 完整)
    Failure Indicators: 测试 fail(说明有真实网络调用)
    Evidence: .sisyphus/evidence/task-11-no-network.txt
  ```

  **Commit**: YES(Wave 3 final)
  - Message: `test(fandom_bot): full unit coverage for new methods + edit_page retry`
  - Files: `tests/test_fandom_bot.py`
  - Pre-commit: `python -m pytest tests/test_fandom_bot.py -v`

---

- [x] 12. **wiki_bot_server.py + Python handlers 单元测试**

  **What to do**:
  - 创建 `tests/test_wiki_bot_server.py`:
    - `TestPing`: 直接调 `handle_request({"id":"t","method":"ping","args":{}})` 返回 pong
    - `TestCheckExists`: mock FandomBot,调 `handle_request({"method":"check_exists","args":{"page_names":["A"]}})`,断言调用了 `bot.check_exists(["A"])`
    - `TestEditPage`: mock,断言 `bot.edit_page_by_name` 被调
    - `TestUnknownMethod`: 返回 `{ok:false, error:"Unknown method: ..."}`
    - `TestLargeInputRejected`: 输入 > 50MB 拒绝
    - `TestSessionRetryOnLoginError`: mock edit_page 第一次抛 login expired,验证 `_BOT_INSTANCE` 被清后重试
    - `TestMethodDocs`: `--method-docs` 输出合法 JSON
  - 创建 `tests/test_wiki_tools_handlers/`:
    - `test_save_page.py`: 测 `wiki_tools/save_page.py` 的 `save_page(bot, ...)` 函数,断言调 `bot.edit_page_by_name`
    - `test_check_exists.py`: 测 `check_exists(bot, ...)`
    - `test_check_files.py`: 测 `check_files_exist(bot, ...)`,断言 filenames 加了 `File:` 前缀
    - `test_read_page.py`: 测 `read_page(bot, ...)`,存在/不存在两个 case
  - 所有测试用 mock_bot fixture(T3 提供)

  **Must NOT do**:
  - 不真启 server 子进程(测试 handle_request 函数即可)
  - 不依赖 .env
  - 不测 server 启动协议(那是 T13 集成测试)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: YES, Wave 3, blocks F1-F4, blocked by T6 + T7 + T3

  **References**:

  **Pattern References**:
  - T6 完成的 `wiki_bot_server.py` 的 `handle_request` 函数 — 单元测试直接调它
  - T7 抽出的 `wiki_tools/*.py` 模块 — 单元测试直接 import

  **API/Type References**:
  - pytest 标准用法
  - mock_bot fixture

  **WHY Each Reference Matters**:
  - handle_request 是 server 的可测入口(避免启子进程)
  - wiki_tools 模块是 wiki-tools.ts inline 的替代,必须独立可测

  **Acceptance Criteria**:

  - [ ] `python -m pytest tests/test_wiki_bot_server.py tests/test_wiki_tools_handlers/ -v` 全绿
  - [ ] 至少 7 + 4 = 11 个测试方法
  - [ ] handler 模块测试断言走 `bot.edit_page_by_name` 等方法,而非 `bot.site.pages[...]`

  **QA Scenarios**:

  ```
  Scenario: 全部测试通过
    Tool: Bash
    Steps:
      1. python -m pytest tests/test_wiki_bot_server.py tests/test_wiki_tools_handlers/ -v
    Expected Result: 11+ passed
    Failure Indicators: 任何 fail
    Evidence: .sisyphus/evidence/task-12-server-handler-tests.txt

  Scenario: handlers 不直连 mwclient
    Tool: Bash (grep + pytest)
    Steps:
      1. grep -r "bot.site.pages" tests/test_wiki_tools_handlers/
      2. 应无匹配(测试不应假设 handler 直连)
      3. grep -r "edit_page_by_name\|check_exists\|check_files_exist\|read_page_text" tests/test_wiki_tools_handlers/
      4. 应有匹配(测试断言走 FandomBot 方法)
    Expected Result: 步骤 1 无匹配, 步骤 3 有匹配
    Failure Indicators: handler 测试假设直连
    Evidence: .sisyphus/evidence/task-12-handlers-use-fandom-bot.txt

  Scenario: --method-docs 输出合法
    Tool: Bash
    Steps:
      1. python .pi/extensions/wiki_bot_server.py --method-docs | python -c "import json, sys; json.load(sys.stdin)"
    Expected Result: 退出码 0
    Failure Indicators: JSON 解析失败
    Evidence: .sisyphus/evidence/task-12-method-docs-valid.txt
  ```

  **Commit**: YES(Wave 3 final)
  - Message: `test(pi): unit coverage for wiki_bot_server + wiki_tools handlers`
  - Files: `tests/test_wiki_bot_server.py`, `tests/test_wiki_tools_handlers/`
  - Pre-commit: `python -m pytest tests/ -v`

---

- [x] 13. **permission gate + slash command 集成测试**

  **What to do**:
  - 创建 `tests/integration/` 目录
  - 创建 `tests/integration/test_permission_gate.test.ts`(vitest):
    - 5 种危险 bash 模式 + 5 种敏感路径 + `--no-test-first` 拦截 + 普通 read 放行 = 至少 12 个测试
    - 用 T4 完成的 `mockExtensionContext` mockPi/mockCtx
    - 直接 import `.pi/extensions/wiki-tools.ts` 的 default export,加载后 dispatch tool_call 事件
    - 注意:.ts 文件需要 vitest 用 esbuild 解析;若 import 路径有问题,改用 `fs.readFileSync` + `eval`(暴力但有效)或调整 vitest config
  - 创建 `tests/integration/test_slash_commands.test.ts`:
    - `/wiki_test` ping 流程
    - `/wiki_convert_page` dry-run vs --confirm
    - `/wiki_scan` 拒绝 --approve-all
    - `/wiki_fix_links` dry-run vs --confirm
    - `/wiki_update_cat_refs` dry-run vs --confirm
    - `wiki_save_page` tool 的 confirm + `__待填__` 拦截
  - 创建 `tests/integration/test_end_to_end.py`:
    - 启动 mock wiki_bot_server.py(用 subprocess)+ mock FandomBot
    - 模拟 Pi dispatch tool_call
    - 断言整个链路:tool → callServer → server → FandomBot
  - 在 conftest.py 加 `integration` marker:`pytest.ini` 加 `markers = integration`

  **Must NOT do**:
  - 不在集成测试里 mock FandomBot 内部(只 mock mwclient 边界)
  - 不调真实 Fandom API
  - 不让集成测试运行超过 30s(超时则失败)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: YES, Wave 3, blocks F1-F4, blocked by T8 + T9 + T10 + T4

  **References**:

  **Pattern References**:
  - T4 完成的 `tests/helpers/mockExtensionContext.ts` — mockPi/mockCtx
  - T8 实现的 permission gate、T9/T10 实现的 slash command — 测试目标

  **API/Type References**:
  - vitest 异步测试:`it('xxx', async () => { ... })`
  - `vi.fn()`, `vi.spyOn`, `expect(...).toHaveBeenCalledWith(...)`
  - Python subprocess.Popen

  **WHY Each Reference Matters**:
  - mockExtensionContext 是测试入口
  - 测试目标是已实现的 T8/T9/T10 代码

  **Acceptance Criteria**:

  - [ ] `cd tests && npm test` 跑通所有 .test.ts
  - [ ] `python -m pytest tests/integration/ -v` 跑通 .py 集成
  - [ ] 总测试数 ≥ 20(integration 12 + slash 8)

  **QA Scenarios**:

  ```
  Scenario: vitest integration 全绿
    Tool: Bash
    Steps:
      1. cd tests && npm test
    Expected Result: all passed
    Failure Indicators: 任何 fail
    Evidence: .sisyphus/evidence/task-13-vitest-integration.txt

  Scenario: pytest integration 全绿
    Tool: Bash
    Steps:
      1. python -m pytest tests/integration/ -v
    Expected Result: all passed
    Failure Indicators: 任何 fail
    Evidence: .sisyphus/evidence/task-13-pytest-integration.txt

  Scenario: 端到端链路验证
    Tool: Bash
    Steps:
      1. python -m pytest tests/integration/test_end_to_end.py -v
    Expected Result: 模拟 wiki_check_exists 从 Pi dispatch 到 mock FandomBot 全链路返回正确结果
    Failure Indicators: 链路任一环节失败
    Evidence: .sisyphus/evidence/task-13-e2e.txt
  ```

  **Commit**: YES(Wave 3 final)
  - Message: `test(pi): integration coverage for permission gate + slash commands + end-to-end`
  - Files: `tests/integration/`
  - Pre-commit: `cd tests && npm test && python -m pytest tests/integration/ -v`

---

- [x] 14. **同步更新 SKILL.md**

  **What to do**:
  - 重写 `/home/hxue/projets/py-wikieditor/.pi/skills/fandom-wiki/SKILL.md`:
    - **frontmatter description** 精简到 ≤ 100 字符,改写为:
      ```
      description: Fandom Wiki 页面拼接工作流。当用户要求批量生成同类页面草稿时激活;仅读单页用 wiki_read_page 或 cat wiki_dump/。
      ```
      (现 ~240 字符,新 ~95 字符)
    - 加 **"何时不用"** 段落:
      ```markdown
      ## 何时不用此技能
      - 用户只想读单个页面 → 用 `wiki_read_page` 工具或 bash `cat wiki_dump/<page>.wiki`
      - 用户要做繁简批量转换 → 用 slash commands `/wiki_convert_page` 等
      - 用户要扫描分类页面 → 用 `/wiki_scan_category`
      - 用户要批量修复链接 → 用 `/wiki_fix_links`
      ```
    - 修正 **line 231 typo**:`wiki_check_file` → `wiki_check_files`
    - 修正 **line 184 误述**:"Extension 层已自动拦截 .env/config.json" → 改为"Extension 层拦截 edit/write/bash 三类工具的敏感路径访问,详见 .pi/extensions/wiki-tools.ts 的 permission-gate 段"
    - 加 **新 slash command 索引** 段落(参考 T5 锁定的分类表),列出 8+2=10 个命令何时用
    - 删除/重写 **"两轮交互"工作流** 中假设的 wiki_save_page 直接调用 → 改为通过 slash command 路径
    - 保留"导航模板/数据提取技巧/常见页面类型速查"等技术内容(仍正确)
    - 加 **"破坏型操作"指引**:scan --approve-all / move-category 必须用 bash,不在 slash command 范围

  **Must NOT do**:
  - 不动 skill 的"Wiki 数据结构""导航模板体系""页面拼接工作流"段落(仍正确)
  - 不增加新 frontmatter 字段(保持兼容)
  - 不删 SKILL.md 里现有的具体数据(模板/字段表格)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**: YES, Wave 3, blocks F1-F4, blocked by T9 + T10 + T5

  **References**:

  **Pattern References**:
  - 现有 `.pi/skills/fandom-wiki/SKILL.md`(全文 258 行)— 在此基础上修订
  - T5 完成的 slash command 分类表 — 命令索引来源
  - Pi skills 文档:https://pi.dev/docs/latest/skills — frontmatter 字段约束

  **API/Type References**:
  - frontmatter `description` ≤ 1024 字符(实际目标 ≤ 100)

  **WHY Each Reference Matters**:
  - SKILL.md 是已写好的详尽文档,只需修订关键部分而非重起炉灶
  - 分类表决定新加的命令索引段内容

  **Acceptance Criteria**:

  - [ ] `head -10 .pi/skills/fandom-wiki/SKILL.md` 显示 description ≤ 100 字符
  - [ ] grep `wiki_check_file` SKILL.md 无匹配(typo 已修)
  - [ ] grep "何时不用" SKILL.md 有匹配
  - [ ] grep "wiki_check_files" SKILL.md 有匹配(正确工具名)

  **QA Scenarios**:

  ```
  Scenario: description 精简到 100 字符内
    Tool: Bash
    Steps:
      1. 提取 frontmatter description 字段,wc -c
    Expected Result: ≤ 100
    Failure Indicators: > 100
    Evidence: .sisyphus/evidence/task-14-description-length.txt

  Scenario: wiki_check_file typo 修正
    Tool: Bash (grep)
    Steps:
      1. grep -n "wiki_check_file[^s]" .pi/skills/fandom-wiki/SKILL.md
    Expected Result: 无匹配
    Failure Indicators: 有匹配(typo 残留)
    Evidence: .sisyphus/evidence/task-14-no-typo.txt

  Scenario: "何时不用"段落存在
    Tool: Bash (grep)
    Steps:
      1. grep -c "何时不用" .pi/skills/fandom-wiki/SKILL.md
    Expected Result: ≥ 1
    Failure Indicators: 0
    Evidence: .sisyphus/evidence/task-14-when-not-to-use.txt

  Scenario: slash command 索引存在
    Tool: Bash (grep)
    Steps:
      1. grep -c "/wiki_" .pi/skills/fandom-wiki/SKILL.md
    Expected Result: ≥ 5(至少 5 个命令被引用)
    Failure Indicators: < 5
    Evidence: .sisyphus/evidence/task-14-command-index.txt
  ```

  **Commit**: YES(Wave 3 final)
  - Message: `docs(skill): sync fandom-wiki SKILL.md to new slash command surface + fix typos + add when-not-to-use`
  - Files: `.pi/skills/fandom-wiki/SKILL.md`
  - Pre-commit: 无

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command, grep code). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan. Verify 8 slash commands present in wiki-tools.ts, verify src/*.py untouched, verify no model in .pi/settings.json.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m pytest tests/ -v` + `cd tests && npm test` + `python src/fandom.py test`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify Python handlers don't use `bot.site.pages[...]` directly (must go through FandomBot methods).
  Output: `Build [PASS/FAIL] | Pytest [N pass/N fail] | Vitest [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Run `pi -e .pi/extensions/wiki-tools.ts -p "test"`. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (slash commands → server → FandomBot). Test edge cases: bad creds, missing .env, long content, concurrent calls. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance: confirm `src/*.py` untouched, no `.pi/package.json`, no `wiki_dump/` refs in tests, `scan --approve-all`/`move-category` not in slash commands. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1 final**: `refactor(fandom_bot): add get_bot/check_exists/read_page_text/check_files_exist + edit_page rate-limit retry` — `fandom_bot.py`
- **Wave 1 final**: `feat(pi): add wiki_bot_server.py IPC scaffold + pytest/TS test infra` — `.pi/extensions/wiki_bot_server.py`, `tests/`, `conftest.py`
- **Wave 2 final**: `refactor(pi-extension): rewrite wiki-tools.ts to use IPC server + add 8 slash commands + permission gate` — `.pi/extensions/wiki-tools.ts`, `.pi/extensions/wiki_tools/`
- **Wave 3 final**: `test(pi): full unit + integration coverage` — `tests/`
- **Wave 3 final**: `docs(pi): sync SKILL.md + rewrite batch-convert.md to match new slash command surface` — `.pi/skills/fandom-wiki/SKILL.md`, `.pi/prompts/batch-convert.md`

Pre-commit gate: `python -m pytest tests/ -v && cd tests && npm test`

---

## Success Criteria

### Verification Commands
```bash
# 测试全绿
python -m pytest tests/ -v                    # Expected: all PASS
cd tests && npm test                          # Expected: all PASS

# Pi 加载扩展
pi -e .pi/extensions/wiki-tools.ts -p "list available tools and commands"
# Expected: 列出 wiki_save_page / wiki_check_exists / wiki_check_files / wiki_read_page + 8 slash commands

# 关键功能 smoke
python src/fandom.py test                     # Expected: ✓ 已登录: <username>
```

### Final Checklist
- [ ] All "Must Have" present(8 slash commands, 4 FandomBot methods, edit_page 重试, permission gate, 测试)
- [ ] All "Must NOT Have" absent(src/*.py 改动, .pi/package.json, wiki_dump/ 测试依赖, scan --approve-all slash, --no-test-first 暴露, -c 模板嵌内容, model 在 settings)
- [ ] `python -m pytest tests/ -v` 全绿
- [ ] `cd tests && npm test` 全绿
- [ ] batch-convert.md 不引用任何不存在的命令
- [ ] SKILL.md description ≤ 100 字符
- [ ] permission gate 模拟测试覆盖 5+ 危险模式
