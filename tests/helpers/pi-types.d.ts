declare module "@earendil-works/pi-coding-agent" {
  export interface ExtensionAPI {
    registerTool(opts: any): void;
    registerCommand(name: string, opts: any): void;
    registerFlag(name: string, opts: any): void;
    registerShortcut(key: any, opts: any): void;
    on(event: string, handler: (event: any, ctx: ExtensionContext) => Promise<any>): void;
    exec(cmd: string, args: string[]): Promise<{ code: number; stdout: string; stderr: string; killed: boolean }>;
    getFlag(name: string): any;
    getActiveTools(): string[];
    setActiveTools(tools: string[]): void;
    appendEntry(customType: string, data: any): void;
    sendMessage(msg: any): void;
    sendUserMessage(msg: string): void;
  }
  export interface ExtensionContext {
    ui: UI;
    mode: string;
    hasUI: boolean;
    sessionManager: any;
    theme: any;
  }
  export interface UI {
    notify(message: string, level: "info" | "warning" | "error"): void;
    confirm(title: string, message: string): Promise<boolean>;
    select(title: string, options: string[]): Promise<string>;
    custom<T>(render: (tui: any, theme: any, kb: any, done: (v: T) => void) => any): Promise<T>;
    setStatus(key: string, value: string): void;
    setWidget(widget: any): void;
  }
  export const Type: any;
}