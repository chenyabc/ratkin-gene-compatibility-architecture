# XML 补丁策略

## 1. Conditional Add/Replace

上游版本不同或其他 Mod 已经修改相同节点时，目标字段有“存在”和“缺失”两种状态。补丁应显式覆盖两者：

```text
目标节点存在？
├─ 否：向稳定的父节点添加完整结构
└─ 是：只替换本项目负责的子结构
```

这比无条件 Add 或 Replace 更适合兼容补丁：

- 无条件 Add 可能产生重复节点；
- 无条件 Replace 在节点缺失时会失败；
- 替换过大的父结构会覆盖其他 Mod 的扩展。

## 2. XPath 收口

定位 BodyAddon 时，应组合多个语义条件，而不是只凭数组位置：

- 所属 RaceSettings；
- 部件标签或等价语义；
- 可接受的路径版本；
- 需要时增加基因、条件或扩展图形约束。

示例文件使用 `ExampleRace` 与 `ExampleEar` 等虚构标识，不对应真实发行数据。

## 3. 颜色与 Shader

颜色修正通常需要同时核对：

- 主颜色来源通道；
- 辅色或 mask 的使用方式；
- Shader 是否支持目标纹理组合。

只改颜色通道而保留不兼容 Shader，可能表现为颜色不生效、透明边缘错误或 mask 未参与。

## 4. 异种数据同步

可选池和生成概率分离存储时，维护者应从同一份内部模型生成二者，避免手工复制漂移：

```text
CompatibilityEntry
├─ id
├─ selectable
├─ pawnKindWeight
├─ factionWeight
└─ optionalDependency
```

发行构建可以把该模型展开成多个 XML 节点；架构仓库不保存真实条目或权重。

## 5. BodyAddon 位置矩阵

位置数据可抽象为：

```text
Offset(part, direction, bodyType, renderContext)
```

其中：

- `part`：左耳、右耳、尾巴或扩展部件；
- `direction`：北、南、东、西；
- `bodyType`：婴儿、儿童及其他体型；
- `renderContext`：世界绘制或肖像绘制。

左右部件存在故意非对称的定位，不能用镜像假设自动合并。具体偏移值属于发行材料，不在本仓库记录。

## 6. 可选依赖门控

只属于某个可选 Mod 的定义，必须由该 Mod 自身的 packageId 或等价直接条件门控。不要以其传递依赖是否存在作为判断，否则在“基础依赖存在、目标扩展缺失”时仍会执行死 XPath。

## 7. 验证清单

- 每个 XPath 是否指向直接拥有该 Def 的 Mod；
- Add 与 Replace 是否覆盖目标节点的两种状态；
- 是否避免替换无关的兄弟节点；
- 可选内容是否有直接依赖门控；
- 可选池与概率映射是否满足同步不变量；
- 左右部件和肖像/世界渲染差异是否被保留；
- 游戏日志中是否存在 Patch operation failed。
