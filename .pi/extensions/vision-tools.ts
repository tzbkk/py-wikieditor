import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import * as path from "path";

const PYTHON = process.env.PI_WIKI_PYTHON || "python3";
const SCRIPT = path.join(__dirname, "vision_server.py");

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "vision_analyze",
    label: "分析图片",
    description:
      "输入图片路径和分析指令，调用视觉 API 返回文本描述。支持 jpg/jpeg/png/gif/webp/bmp。需要 .env 中配置 VISION_API_KEY。",
    parameters: Type.Object({
      image_path: Type.String({ description: "图片文件的绝对或相对路径" }),
      prompt: Type.Optional(
        Type.String({
          description: "分析指令，例如'描述图片内容'、'提取图中文字'、'这张图有多少人'",
        })
      ),
    }),
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      const prompt = params.prompt || "详细描述这张图片的内容";
      try {
        const result = await pi.exec(PYTHON, [
          SCRIPT,
          "--image",
          params.image_path,
          "--prompt",
          prompt,
        ]);
        const stdout = (result.stdout || "").trim();
        const stderr = (result.stderr || "").trim();
        if (result.code !== 0) {
          return {
            content: [
              { type: "text" as const, text: `❌ ${stderr || "未知错误"}` },
            ],
            details: { image_path: params.image_path, ok: false },
          };
        }
        return {
          content: [{ type: "text" as const, text: stdout }],
          details: { image_path: params.image_path, ok: true },
        };
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        return {
          content: [{ type: "text" as const, text: `❌ ${msg}` }],
          details: { image_path: params.image_path, ok: false },
        };
      }
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("视觉工具已加载（vision_analyze）", "info");
  });
}
