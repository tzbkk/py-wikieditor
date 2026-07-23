import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawn, ChildProcess } from "child_process";
import * as path from "path";

const PYTHON = process.env.PI_WIKI_PYTHON || "python3";
const SERVER_SCRIPT = path.join(__dirname, "wiki_bot_server.py");

// ============================================================
// 权限闸门 — 危险命令 / 敏感路径 模式定义
// ============================================================

// 危险 bash 命令：触发 ctx.ui.confirm() 二次确认
const DANGEROUS_BASH_PATTERNS: { regex: RegExp; label: string }[] = [
  { regex: /\brm\s+-rf\b/, label: "rm -rf (recursive force delete)" },
  { regex: /\bsudo\b/, label: "sudo (privilege escalation)" },
  { regex: /\bchmod\s+777\b/, label: "chmod 777 (world-writable)" },
  { regex: />\s*\/dev\/sd/, label: "write to raw disk device" },
  { regex: /:\s*\(\)\s*\{\s*:\s*\|/, label: "fork bomb" },
  { regex: /\|\s*(sh|bash)\s*$/, label: "pipe to shell" },
];

// 敏感路径：直接阻止（无 confirm），用于 edit/write/bash 的字符串入参。
// 注意：\.env 前缀允许空白字符以匹配 bash 重定向（例如 `echo > .env`）。
const SENSITIVE_PATH_PATTERNS: RegExp[] = [
  /(^|[\/\s])\.env$/, // .env files (path or bash redirect target)
  /config\.json$/, // config.json
  /credentials/i, // anything with "credentials"
  /\.pem$/, // PEM certificates
  /\.key$/, // private keys
  /id_rsa/, // SSH private keys
  /\/\.ssh\//, // .ssh directory
];

// ============================================================
// IPC Server 生命周期管理 — 持久化的 wiki_bot_server.py 子进程
// ============================================================
let serverProc: ChildProcess | null = null;
let serverReady = false;

async function ensureServer(pi: ExtensionAPI): Promise<void> {
  if (serverProc && serverReady) return;
  serverProc = spawn(PYTHON, [SERVER_SCRIPT], {
    stdio: ["pipe", "pipe", "pipe"],
    cwd: process.cwd(),
  });
  serverProc.stderr?.on("data", (data) => {
    pi.exec("echo", [data.toString()]).catch(() => {});
  });
  serverProc.on("exit", () => {
    serverProc = null;
    serverReady = false;
  });
  serverReady = true;
}

async function callServer(
  method: string,
  args: Record<string, unknown>
): Promise<any> {
  if (!serverProc || !serverProc.stdin || !serverProc.stdout) {
    throw new Error("IPC server not started");
  }
  const request =
    JSON.stringify({ id: Date.now().toString(), method, args }) + "\n";
  serverProc.stdin.write(request);
  return new Promise((resolve, reject) => {
    const onData = (data: Buffer) => {
      const lines = data.toString().split("\n").filter((l) => l.trim());
      if (lines.length > 0) {
        serverProc!.stdout!.off("data", onData);
        try {
          const resp = JSON.parse(lines[0]);
          if (resp.ok) resolve(resp.result);
          else reject(new Error(resp.error || "Server error"));
        } catch (e: any) {
          reject(new Error(`Invalid server response: ${lines[0]}`));
        }
      }
    };
    serverProc!.stdout!.once("data", onData);
  });
}

// ============================================================
// 斜杠命令辅助函数 — 参数解析与输出截断
// ============================================================

/** 解析 slash 命令原始参数字符串：返回位置参数、标志集合、键值对。 */
function parseArgs(raw: string): {
  positional: string[];
  flags: Set<string>;
  kwargs: Record<string, string>;
} {
  const positional: string[] = [];
  const flags = new Set<string>();
  const kwargs: Record<string, string> = {};
  const tokens = raw.match(/(?:[^\s"]+|"[^"]*")+/g) || [];
  for (const token of tokens) {
    if (token.startsWith("--")) {
      flags.add(token.slice(2));
    } else if (token.includes("=")) {
      const eqIdx = token.indexOf("=");
      const key = token.slice(0, eqIdx);
      const val = token.slice(eqIdx + 1).replace(/^"|"$/g, "");
      kwargs[key] = val;
    } else {
      positional.push(token.replace(/^"|"$/g, ""));
    }
  }
  return { positional, flags, kwargs };
}

/** 截断过长输出，保留首尾各一半。 */
function truncate(s: string, maxLen = 5000): string {
  if (s.length <= maxLen) return s;
  const head = Math.floor(maxLen / 2);
  const tail = maxLen - head;
  return s.slice(0, head) + "\n... (truncated) ...\n" + s.slice(-tail);
}

export default function (pi: ExtensionAPI) {
  // ============================================================
  // Wiki 读写工具 — 通过 IPC server 调用 FandomBot
  // ============================================================

  pi.registerTool({
    name: "wiki_save_page",
    label: "保存 Wiki 页面",
    description:
      "将内容保存到 Wiki 页面。⚠️ 这是破坏性操作，必须经过用户明确确认后才能调用。如果页面已存在会被覆盖。",
    parameters: Type.Object({
      title: Type.String({ description: "Wiki 页面标题" }),
      content: Type.String({ description: "页面 wikitext 内容" }),
      summary: Type.Optional(
        Type.String({ description: "编辑摘要", default: "自动生成页面" })
      ),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      if (params.content.includes("__待填__")) {
        return {
          content: [
            {
              type: "text" as const,
              text: "⛔ 页面内容中仍有 `__待填__` 标记，请先补充。",
            },
          ],
          details: { title: params.title, ok: false },
        };
      }
      // T10: 保存前必须经过用户二次确认（即使没有 __待填__）
      const preview = params.content.slice(0, 500);
      const ok = await ctx.ui.confirm(
        "⚠️ 即将覆盖页面",
        `页面: ${params.title}\n\n内容预览:\n${preview}${params.content.length > 500 ? "..." : ""}`,
      );
      if (!ok) {
        return {
          content: [{ type: "text" as const, text: "❌ 用户取消了保存" }],
          details: { title: params.title, ok: false, cancelled: true },
        };
      }
      try {
        await ensureServer(pi);
        const result = await callServer("edit_page", {
          title: params.title,
          content: params.content,
          summary: params.summary || "自动生成页面",
        });
        return {
          content: [
            { type: "text" as const, text: `✅ 已保存: ${params.title}` },
          ],
          details: result,
        };
      } catch (e: any) {
        return {
          content: [
            { type: "text" as const, text: `❌ 保存失败: ${e.message}` },
          ],
          details: { title: params.title, ok: false, error: e.message },
        };
      }
    },
  });

  pi.registerTool({
    name: "wiki_check_exists",
    label: "检查页面是否存在",
    description:
      "检查 Wiki 上一组页面是否存在。返回每个页面的存在状态。用于在生成页面前确认不会覆盖已有内容。",
    parameters: Type.Object({
      titles: Type.Array(Type.String(), {
        description: "要检查的页面标题列表",
      }),
    }),
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      try {
        await ensureServer(pi);
        const result = await callServer("check_exists", {
          page_names: params.titles,
        });
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(result, null, 2),
            },
          ],
          details: result,
        };
      } catch (e: any) {
        return {
          content: [{ type: "text" as const, text: `❌ ${e.message}` }],
          details: {},
        };
      }
    },
  });

  pi.registerTool({
    name: "wiki_check_files",
    label: "检查图片文件是否存在",
    description:
      "检查 Wiki 上 File: 命名空间的图片文件是否存在。用于验证按命名规律推断的图片文件名是否已上传。",
    parameters: Type.Object({
      filenames: Type.Array(Type.String(), {
        description: "文件名列表（不含 File: 前缀）",
      }),
    }),
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      try {
        await ensureServer(pi);
        const result = await callServer("check_files_exist", {
          filenames: params.filenames,
        });
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(result, null, 2),
            },
          ],
          details: result,
        };
      } catch (e: any) {
        return {
          content: [{ type: "text" as const, text: `❌ ${e.message}` }],
          details: {},
        };
      }
    },
  });

  pi.registerTool({
    name: "wiki_read_page",
    label: "读取 Wiki 页面内容",
    description:
      "从 Wiki 上读取指定页面的最新内容。当 wiki_dump/ 中的本地缓存可能过期时使用。",
    parameters: Type.Object({
      title: Type.String({ description: "Wiki 页面标题" }),
    }),
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      try {
        await ensureServer(pi);
        const result = await callServer("read_page_text", {
          page_name: params.title,
        });
        const text =
          result && typeof result === "string" ? result : null;
        return {
          content: [
            {
              type: "text" as const,
              text:
                text === null
                  ? `❌ 页面不存在: ${params.title}`
                  : text,
            },
          ],
          details: { title: params.title, found: text !== null },
        };
      } catch (e: any) {
        return {
          content: [{ type: "text" as const, text: `❌ ${e.message}` }],
          details: {},
        };
      }
    },
  });

  // ============================================================
  // 权限闸门 — 4 道 tool_call 拦截
  // ============================================================

  // 闸门 1：危险 bash 命令 — 二次确认后才放行
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;
    const cmd = (event.input as any)?.command || "";
    for (const { regex, label } of DANGEROUS_BASH_PATTERNS) {
      if (regex.test(cmd)) {
        if (ctx.hasUI) {
          ctx.ui.notify(`⚠️ 检测到危险命令: ${label}`, "warning");
          const ok = await ctx.ui.confirm(
            "⚠️ 危险命令确认",
            `命令包含 ${label}:\n${cmd}\n\n确定要执行吗？`,
          );
          if (!ok) {
            return { block: true, reason: `用户拒绝了危险命令: ${label}` };
          }
        } else {
          return { block: true, reason: `非交互模式下阻止危险命令: ${label}` };
        }
      }
    }
    return undefined;
  });

  // 闸门 2：敏感路径写入 — 直接阻止（无 confirm）
  pi.on("tool_call", async (event, ctx) => {
    if (!["edit", "write", "bash"].includes(event.toolName)) return undefined;
    const input = event.input as Record<string, unknown>;

    // bash 命令：检测重定向目标（例如 echo > .env）
    if (event.toolName === "bash") {
      const cmd = (input as any)?.command || "";
      for (const pattern of SENSITIVE_PATH_PATTERNS) {
        if (pattern.test(cmd)) {
          if (ctx.hasUI) ctx.ui.notify("⛔ 禁止修改敏感路径", "error");
          return {
            block: true,
            reason: `检测到敏感路径访问: ${cmd.match(pattern)?.[0]}`,
          };
        }
      }
    }

    // edit/write：扫描所有字符串入参
    const strings = Object.values(input).filter(
      (v): v is string => typeof v === "string",
    );
    for (const str of strings) {
      for (const pattern of SENSITIVE_PATH_PATTERNS) {
        if (pattern.test(str)) {
          if (ctx.hasUI) ctx.ui.notify("⛔ 禁止修改敏感路径", "error");
          return {
            block: true,
            reason: `检测到敏感路径: ${str.match(pattern)?.[0]}`,
          };
        }
      }
    }
    return undefined;
  });

  // 闸门 3：--no-test-first 标志 — 全局直接阻止
  pi.on("tool_call", async (event, ctx) => {
    const input = event.input as Record<string, unknown>;
    const checkString = (s: string): boolean => s.includes("--no-test-first");
    for (const val of Object.values(input)) {
      if (typeof val === "string" && checkString(val)) {
        if (ctx.hasUI)
          ctx.ui.notify("⛔ --no-test-first 被全局禁止", "error");
        return {
          block: true,
          reason: "--no-test-first flag is globally blocked",
        };
      }
      if (Array.isArray(val)) {
        for (const item of val) {
          if (typeof item === "string" && checkString(item)) {
            if (ctx.hasUI)
              ctx.ui.notify("⛔ --no-test-first 被全局禁止", "error");
            return {
              block: true,
              reason: "--no-test-first flag is globally blocked",
            };
          }
        }
      }
    }
    return undefined;
  });

  // 闸门 4：含 __待填__ 的页面保存 — 直接阻止
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "wiki_save_page") {
      const content = (event.input as any)?.content || "";
      if (content.includes("__待填__")) {
        if (ctx.hasUI) ctx.ui.notify("⛔ 页面内容含 __待填__ 标记", "error");
        return {
          block: true,
          reason: "页面内容中仍有 `__待填__` 标记，请先补充所有缺失字段。",
        };
      }
    }
    return undefined;
  });

  // ============================================================
  // 斜杠命令 — 8 个 safe / bounded / read 命令
  // ============================================================

  pi.registerCommand("wiki_test", {
    description: "测试 Wiki 连接 (Safe)",
    async handler(_args, ctx) {
      const result = await pi.exec(PYTHON, ["src/fandom.py", "test"]);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200) || "连接成功"}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_info", {
    description: "获取模板/页面信息 (Safe)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const name =
        parsed.kwargs.template_name ||
        parsed.kwargs.name ||
        parsed.positional[0] ||
        "Template:音樂信息";
      const result = await pi.exec(PYTHON, [
        "src/fandom.py",
        "info",
        name,
      ]);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`ℹ️ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_convert_page", {
    description: "转换单个页面 (Bounded, 默认 dry-run)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const pageName = parsed.kwargs.page_name || parsed.positional[0];
      if (!pageName) {
        ctx.ui.notify("❌ 缺少 page_name 参数", "error");
        return;
      }
      const dryRun = !parsed.flags.has("confirm");
      if (!dryRun) {
        const ok = await ctx.ui.confirm(
          "⚠️ 确认实际转换",
          `即将实际转换页面: ${pageName}\n(非 dry-run)`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "page", pageName];
      if (dryRun) cmdArgs.push("--dry-run");
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_convert_category", {
    description: "转换分类下所有页面 (Bounded, 默认 dry-run)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const category = parsed.kwargs.category || parsed.positional[0];
      if (!category) {
        ctx.ui.notify("❌ 缺少 category 参数", "error");
        return;
      }
      const dryRun = !parsed.flags.has("confirm");
      if (!dryRun) {
        const ok = await ctx.ui.confirm(
          "⚠️ 确认实际转换",
          `即将实际转换分类: ${category}\n(非 dry-run)`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "category", category];
      if (dryRun) cmdArgs.push("--dry-run");
      const limit = parsed.kwargs.limit;
      if (limit) cmdArgs.push("--limit", String(limit));
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_convert_template", {
    description: "转换使用模板的所有页面 (Bounded, 默认 dry-run)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const template = parsed.kwargs.template || parsed.positional[0];
      if (!template) {
        ctx.ui.notify("❌ 缺少 template 参数", "error");
        return;
      }
      const dryRun = !parsed.flags.has("confirm");
      if (!dryRun) {
        const ok = await ctx.ui.confirm(
          "⚠️ 确认实际转换",
          `即将实际转换模板: ${template}\n(非 dry-run)`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "template", template];
      if (dryRun) cmdArgs.push("--dry-run");
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_restore", {
    description: "从历史版本恢复页面 (Bounded, 默认仅显示版本)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const pageName = parsed.kwargs.page_name || parsed.positional[0];
      if (!pageName) {
        ctx.ui.notify("❌ 缺少 page_name 参数", "error");
        return;
      }
      const showOnly = !parsed.flags.has("confirm");
      if (!showOnly) {
        const ok = await ctx.ui.confirm(
          "⚠️ 确认实际恢复",
          `即将从历史版本实际恢复页面: ${pageName}\n(非预览)`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "restore", pageName];
      if (showOnly) cmdArgs.push("--show-versions");
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_scan", {
    description: "扫描 main 命名空间页面 (Read, 永不 approve-all)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      if (parsed.flags.has("approve-all")) {
        ctx.ui.notify(
          "⛔ /wiki_scan 拒绝 --approve-all，请直接使用 bash 并谨慎操作",
          "error",
        );
        return;
      }
      const cmdArgs = ["src/fandom.py", "scan", "--scan-only"];
      const limit = parsed.kwargs.limit;
      if (limit) cmdArgs.push("--limit", String(limit));
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  pi.registerCommand("wiki_scan_category", {
    description: "扫描 category 命名空间页面 (Read, 永不 approve-all)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      if (parsed.flags.has("approve-all")) {
        ctx.ui.notify(
          "⛔ /wiki_scan_category 拒绝 --approve-all，请直接使用 bash 并谨慎操作",
          "error",
        );
        return;
      }
      const cmdArgs = ["src/fandom.py", "scan-category", "--scan-only"];
      const limit = parsed.kwargs.limit;
      if (limit) cmdArgs.push("--limit", String(limit));
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      if (result.code === 0) {
        ctx.ui.notify(`✅ ${output.slice(0, 200)}`, "info");
      } else {
        ctx.ui.notify(`❌ ${output.slice(0, 200)}`, "error");
      }
    },
  });

  // ============================================================
  // 破坏性斜杠命令 — 默认 dry-run，--confirm 必须经 ctx.ui.confirm
  // ============================================================

  pi.registerCommand("wiki_fix_links", {
    description: "批量修复链接为简体 (默认 dry-run, --confirm 实际执行)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const oldText = parsed.kwargs.old_text;
      const newText = parsed.kwargs.new_text;
      if (!oldText || !newText) {
        ctx.ui.notify("❌ 需要 old_text 和 new_text 参数", "error");
        return;
      }
      const dryRun = !parsed.flags.has("confirm");
      if (!dryRun) {
        const ok = await ctx.ui.confirm(
          "⚠️ 破坏性操作确认",
          `即将批量替换链接:\n  "${oldText}" → "${newText}"\n\n这会影响多个页面。确定继续？`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "fix-links", oldText, newText];
      if (dryRun) cmdArgs.push("--dry-run");
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      ctx.ui.notify(
        result.code === 0
          ? `✅ ${output.slice(0, 200)}`
          : `❌ ${output.slice(0, 200)}`,
        result.code === 0 ? "info" : "error",
      );
    },
  });

  pi.registerCommand("wiki_update_cat_refs", {
    description:
      "更新分类引用为简体中文 (默认 dry-run, --confirm 实际执行)",
    async handler(args, ctx) {
      const parsed = parseArgs(args);
      const categories = parsed.positional;
      const fromFile = parsed.kwargs.from_file;
      if (categories.length === 0 && !fromFile) {
        ctx.ui.notify(
          "❌ 需要至少一个分类名或 --from-file 参数",
          "error",
        );
        return;
      }
      const dryRun = !parsed.flags.has("confirm");
      if (!dryRun) {
        const target = fromFile
          ? `文件: ${fromFile}`
          : `分类: ${categories.join(", ")}`;
        const ok = await ctx.ui.confirm(
          "⚠️ 破坏性操作确认",
          `即将批量更新分类引用:\n  ${target}\n\n这会影响多个页面。确定继续？`,
        );
        if (!ok) {
          ctx.ui.notify("已取消", "info");
          return;
        }
      }
      const cmdArgs = ["src/fandom.py", "update-cat-refs"];
      if (fromFile) {
        cmdArgs.push("--from-file", fromFile);
      } else {
        cmdArgs.push(...categories);
      }
      if (dryRun) cmdArgs.push("--dry-run");
      const result = await pi.exec(PYTHON, cmdArgs);
      const output = truncate(
        ((result.stdout || "") + (result.stderr || "")).trim(),
      );
      ctx.ui.notify(
        result.code === 0
          ? `✅ ${output.slice(0, 200)}`
          : `❌ ${output.slice(0, 200)}`,
        result.code === 0 ? "info" : "error",
      );
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    try {
      await ensureServer(pi);
      ctx.ui.notify("Fandom Wiki 工具集已加载 (IPC server 已启动)", "info");
    } catch (e: any) {
      ctx.ui.notify(`⚠️ Wiki IPC server 启动失败: ${e.message}`, "warning");
    }
  });

  pi.on("session_shutdown", async () => {
    if (serverProc) {
      serverProc.kill();
      serverProc = null;
      serverReady = false;
    }
  });
}
