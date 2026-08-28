# Ratkin Gene Compatibility Architecture

本仓库记录「鼠族基因兼容补丁」的实现原理、模块边界和兼容策略。它不是完整 Mod 源码仓库，也不提供可直接安装、构建或还原发行包的材料。

## 仓库定位

完整 Mod 需要同时处理多个上游 Mod 的定义、纹理、渲染行为和版本差异。部分发行材料来源于第三方项目，许可范围并不适合通过 GitHub 再分发。因此，本仓库只保留由维护者整理的技术架构：

- 兼容问题如何分层处理；
- 静态 XML 补丁与运行时修正如何协作；
- 如何降低对上游实现细节的耦合；
- 如何做到目标收口、失败降级和安全刷新；
- 哪些材料被明确排除在本仓库之外。

## 架构概览

```text
上游 Def 与种族配置
        │
        ▼
静态定义修正层 ──► 颜色通道、着色器、扩展图形映射
        │
        ▼
数据协调层 ──────► 可选异种池、生成概率、条件化阵营配置
        │
        ▼
运行时兼容层 ────► 目标 Pawn 判定、最终 Graphic 颜色兜底
        │
        ▼
生命周期刷新层 ──► 初始化、地图载入、角色配置页刷新
```

详细说明：

- [总体架构](docs/ARCHITECTURE.md)
- [运行时颜色修正管线](docs/RUNTIME_COLOR_PIPELINE.md)
- [XML 补丁策略](docs/XML_PATCH_STRATEGY.md)
- [兼容矩阵](docs/COMPATIBILITY_MATRIX.md)
- [Clean-room 与材料边界](docs/CLEAN_ROOM_BOUNDARY.md)
- [第三方参考项目](THIRD_PARTY_REFERENCES.md)

## 不包含的内容

本仓库明确不包含：

- 来自参考 Mod 的纹理、宣传图及其他第三方美术材料；
- DLL、调试符号及完整 C# 源码；
- 完整、可运行的 RimWorld XML 补丁；
- 真实 DefName、完整 XPath、纹理路径白名单；
- 具体异种名单、生成概率和 BodyAddon 偏移坐标；
- `About/PublishedFileId.txt` 等 Steam 创意工坊发行包元数据文件，或可直接组装发行包的目录结构。

`examples/` 中的内容仅为虚构名称和占位值构成的概念示例，不能直接用于游戏。

## 完整 Mod

玩家版本通过 [Steam 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=3728889366) 发布。本仓库不提供 GitHub 手动安装或自行构建方式。架构文档描述设计与边界，不逐行对应发行版本。

## 许可

本仓库内原创文档与概念示例采用 [MIT License](LICENSE)。项目名称、第三方 Mod 名称、事实性引用及链接不因此获得 MIT 授权。参见 [第三方参考说明](THIRD_PARTY_REFERENCES.md)。
