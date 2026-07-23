import { vi } from 'vitest';
import type { ExtensionAPI, ExtensionContext } from '@earendil-works/pi-coding-agent';

export function createMockPi(): ExtensionAPI & { _toolHandlers: Record<string, Function>; _commandHandlers: Record<string, Function>; _eventHandlers: Record<string, Function[]> } {
  const toolHandlers: Record<string, Function> = {};
  const commandHandlers: Record<string, Function> = {};
  const eventHandlers: Record<string, Function[]> = {};

  const pi: any = {
    get _toolHandlers() {
      return toolHandlers;
    },
    get _commandHandlers() {
      return commandHandlers;
    },
    get _eventHandlers() {
      return eventHandlers;
    },
    registerTool: vi.fn((opts: any) => { toolHandlers[opts.name] = opts.execute; }),
    registerCommand: vi.fn((name: string, opts: any) => { commandHandlers[name] = opts.handler; }),
    registerFlag: vi.fn(),
    registerShortcut: vi.fn(),
    on: vi.fn((event: string, handler: Function) => {
      if (!eventHandlers[event]) eventHandlers[event] = [];
      eventHandlers[event].push(handler);
    }),
    exec: vi.fn().mockResolvedValue({ code: 0, stdout: "", stderr: "", killed: false }),
    getFlag: vi.fn().mockReturnValue(undefined),
    getActiveTools: vi.fn().mockReturnValue([]),
    setActiveTools: vi.fn(),
    appendEntry: vi.fn(),
    sendMessage: vi.fn(),
    sendUserMessage: vi.fn(),
  };
  return pi;
}

export function createMockCtx(overrides?: Partial<ExtensionContext>): ExtensionContext {
  return {
    ui: {
      notify: vi.fn(),
      confirm: vi.fn().mockResolvedValue(false),
      select: vi.fn().mockResolvedValue(""),
      custom: vi.fn(),
      setStatus: vi.fn(),
      setWidget: vi.fn(),
    },
    mode: 'tui',
    hasUI: true,
    sessionManager: { getBranch: vi.fn().mockReturnValue([]) },
    theme: { fg: vi.fn((color: string, text: string) => text) },
    ...overrides,
  };
}

export async function dispatchToolCall(pi: any, toolName: string, input: any, ctx?: any) {
  const handlers = pi._eventHandlers['tool_call'] || [];
  const mockCtx = ctx || createMockCtx();
  for (const handler of handlers) {
    const result = await handler({ toolName, input }, mockCtx);
    if (result && result.block) return result;
  }
  return undefined;
}

export async function dispatchCommand(pi: any, name: string, args: string, ctx?: any) {
  const handler = pi._commandHandlers[name];
  if (!handler) throw new Error(`Command not found: ${name}`);
  const mockCtx = ctx || createMockCtx();
  return handler(args, mockCtx);
}