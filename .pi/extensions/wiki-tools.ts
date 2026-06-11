import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const PYTHON = "python3";

async function run(
  pi: ExtensionAPI,
  args: string[]
): Promise<{ ok: boolean; output: string }> {
  try {
    const result = await pi.exec(PYTHON, args);
    const output = (result.stdout || "") + (result.stderr || "");
    return { ok: result.code === 0 && !result.killed, output: output.trim() };
  } catch (e: any) {
    return { ok: false, output: String(e.message || e) };
  }
}

export default function (pi: ExtensionAPI) {
  // ============================================================
  // Wiki 读写工具
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
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      const script = `
import sys
sys.path.insert(0, '.')
from fandom_bot import FandomBot
bot = FandomBot()
page = bot.site.pages[${JSON.stringify(params.title)}]
if page.exists:
    print(f"⚠️ 页面已存在，将覆盖: ${params.title.replace(/`/g, "\\`")}")
page.edit(${JSON.stringify(params.content)}, summary=${JSON.stringify(params.summary || "自动生成页面")})
print(f"✅ 已保存: ${params.title.replace(/`/g, "\\`")}")
`;
      const r = await run(pi, ["-c", script]);
      return {
        content: [{ type: "text" as const, text: r.output }],
        details: { title: params.title, ok: r.ok },
      };
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
      const script = `
import sys, json
sys.path.insert(0, '.')
from fandom_bot import FandomBot
bot = FandomBot()
results = {}
for t in ${JSON.stringify(params.titles)}:
    page = bot.site.pages[t]
    results[t] = page.exists
print(json.dumps(results, ensure_ascii=False))
`;
      const r = await run(pi, ["-c", script]);
      return {
        content: [{ type: "text" as const, text: r.output }],
        details: {},
      };
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
      const script = `
import sys, json
sys.path.insert(0, '.')
from fandom_bot import FandomBot
bot = FandomBot()
results = {}
for f in ${JSON.stringify(params.filenames)}:
    page = bot.site.pages[f'File:{f}']
    results[f] = page.exists
print(json.dumps(results, ensure_ascii=False))
`;
      const r = await run(pi, ["-c", script]);
      return {
        content: [{ type: "text" as const, text: r.output }],
        details: {},
      };
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
      const script = `
import sys
sys.path.insert(0, '.')
from fandom_bot import FandomBot
bot = FandomBot()
page = bot.site.pages[${JSON.stringify(params.title)}]
if page.exists:
    print(page.text())
else:
    print(f"❌ 页面不存在: ${params.title.replace(/`/g, "\\`")}")
`;
      const r = await run(pi, ["-c", script]);
      return {
        content: [{ type: "text" as const, text: r.output }],
        details: {},
      };
    },
  });

  // ============================================================
  // 安全策略
  // ============================================================

  // 安全策略：拦截对 .env、config.json、credentials 的写入
  pi.on("tool_call", async (event, _ctx) => {
    if (event.toolName === "edit" || event.toolName === "write") {
      const filePath: string =
        (event.input as any).file_path || (event.input as any).filePath || "";
      if (
        filePath.endsWith(".env") ||
        filePath.endsWith("config.json") ||
        filePath.includes("credentials")
      ) {
        return {
          block: true,
          reason:
            "⛔ 安全策略：禁止修改 .env、config.json 或 credentials 文件。",
        };
      }
    }
  });

  // 拦截含 __待填__ 的页面保存
  pi.on("tool_call", async (event, _ctx) => {
    if (event.toolName === "wiki_save_page") {
      const title = (event.input as any).title || "";
      const content = (event.input as any).content || "";
      if (content.includes("__待填__")) {
        return {
          block: true,
          reason:
            "⛔ 页面内容中仍有 `__待填__` 标记，请先补充所有缺失字段。",
        };
      }
    }
  });

  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("Fandom Wiki 页面拼接工具集已加载", "info");
  });
}
