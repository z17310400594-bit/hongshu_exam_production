---
name: taro-tech-stack
description: Taro 项目核心技术栈：框架、编译器、状态管理、样式方案等
metadata:
  type: project
---

## 技术栈

- **框架**: Taro 4.x + React 18 + TypeScript 5
- **编译器**: Webpack 5 + Babel（持久化缓存，增量编译 3-5s）
- **目标端**: 微信小程序 / H5
- **包管理**: npm
- **状态管理**: Zustand（轻量，无 Provider 嵌套）
- **HTTP**: 基于 `Taro.request` 封装的拦截器，统一 token 注入、错误弹窗
- **样式**: SCSS Modules（`xxx.module.scss`）
- **日期**: dayjs
- **代码规范**: ESLint + Prettier + Taro 官方规则

**Why:** 技术栈在项目初始化时已锁定，所有代码必须遵守这些选型。上下文压缩后可能丢失细节。

**How to apply:** 新建任何文件/组件/页面时，先确认使用的库和方案符合上述选型。不确定时回查根目录 CLAUDE.md。
