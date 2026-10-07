# 领域文档

本文件说明工程 Skills 在探索代码库时应如何读取本仓库的领域文档。

## 探索代码前需要读取的内容

- 仓库根目录下的 **`CONTEXT.md`**；或者
- 如果根目录存在 **`CONTEXT-MAP.md`**，则根据其中的指引，读取与当前任务相关的各个上下文对应的 `CONTEXT.md`。
- **`docs/adr/`**：读取所有涉及当前工作区域的 ADR。在多上下文仓库中，还需要检查 `src/<context>/docs/adr/` 下针对特定上下文的决策。

如果这些文件尚不存在，继续执行任务即可，无需报告文件缺失，也无需预先建议创建。`/domain-modeling` Skill 会在领域术语或架构决策真正得到确认时按需创建这些文件；该 Skill 通常由 `/grill-with-docs` 和 `/improve-codebase-architecture` 调用。

## 文件结构

单上下文仓库（适用于绝大多数仓库）：

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库（根目录存在 `CONTEXT-MAP.md`）：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 特定上下文的决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用领域词汇表中的术语

当输出内容需要命名某个领域概念时，例如 Issue 标题、重构建议、假设或测试名称，应使用 `CONTEXT.md` 中定义的术语。不要改用词汇表明确排除的同义词。

如果词汇表尚未包含所需概念，这是一项需要关注的信号：可能正在使用项目原本不存在的语言，应重新考虑；也可能确实存在领域模型缺口，应记录下来，供 `/domain-modeling` 处理。

## 标记与 ADR 冲突的内容

如果输出内容与现有 ADR 冲突，应明确指出冲突，而不是静默覆盖原有决策：

> _此内容与 ADR-0007（采用事件溯源的订单）冲突，但由于……，值得重新讨论。_
