# CLAUDE.md — 项目规范（自动注入）

考前刷题（Exam Practice）是一个**纯前端、零依赖、单文件可部署**的刷题 PWA，部署在 GitHub Pages。

## 硬性约束（不要破坏）
1. **保持 `index.html` 单文件可直接部署**：不引入框架、打包步骤、外部 CSS/JS/字体。题库走 `data/*.json`（`fetch`）。
2. **所有样式用 CSS 变量**，定义在 `<style id="app-css">` 的 `:root` / `[data-theme="dark"]`。禁止写死十六进制色值。
3. **答题引擎只有一份**：`<script type="text/plain" id="engine-js">`，主程序注入执行、离线版原样嵌入。改逻辑/样式只改这一处，在线与离线版同步。
4. **深浅色都要支持**：主题手动切换，记忆在 `localStorage('exam-practice:theme')`，首次跟随系统。
5. **多端适配**：手机竖屏 / 平板 / 桌面 / 横屏共用一套布局；热区 ≥44px；输入框字号 ≥16px。

## 设计来源
所有视觉与交互规范以 **`docs/design-system.md`** 为唯一标准。改 UI 前先读它；新增 token / 组件先在该文件登记再实现。

## 改动前自检
- 颜色只引用变量？
- 深色 + 浅色都试过？
- 手机竖屏 / 平板 / 桌面 / 横屏都试过？
- 键盘、触控、鼠标都能操作？（注意：覆盖层未激活时必须 `pointer-events:none`）
- 离线版（`buildOfflineHTML`）是否同步生效？

## 小改动原则
用户要求改某处时，只改那一处，保留其余布局 / 间距 / 配色 / 文案不动。
