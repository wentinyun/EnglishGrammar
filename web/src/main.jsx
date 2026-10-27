import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import "./app-shell.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// 安装到主屏后由 Service Worker 接管静态资源；本地开发不注册，避免缓存干扰
if ("serviceWorker" in navigator && !window.location.port.startsWith("517")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      // 主动查一次更新：否则旧 sw 可能挂几天不换，图标和静态资源一直是旧的
      .then((reg) => reg.update().catch(() => {}))
      .catch(() => {});
  });
}
