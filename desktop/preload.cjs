const { contextBridge } = require("electron");

// 仅暴露渲染层识别桌面环境所需的只读标记，不开放 Node 或 IPC 能力。
contextBridge.exposeInMainWorld(
  "zhiyuDesktop",
  Object.freeze({
    isDesktop: true,
    platform: process.platform,
  }),
);
