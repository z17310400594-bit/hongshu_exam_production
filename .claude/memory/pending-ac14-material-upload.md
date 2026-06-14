---
name: pending-ac14-material-upload
description: AC-14 素材底板上传功能待实现
metadata:
  type: project
---

## 状态

暂缓，V1 后续补充。

## 需求

- 运营上传 PNG/JPG 作为自定义卡片底板
- 上传后在风格选择列表中可选用
- 素材库岗位共享，按文件夹区分
- 对应 PRD AC-14

## 实现要点

- 高级选项「底板素材」下拉目前是静态列表，需改为动态（上传 + 列表）
- 上传后的图片存到 IndexedDB 或后端（H5 用 IndexedDB + base64 即可）
- 选中的底板替换 CSS `--card-bg-gradient` 为 `url(xxx)`

## 关联

- [[taro-core-constraints]] — 注意包体积，图片存 IndexedDB 不打包
- [[external-prd-space]] — PRD 原文
