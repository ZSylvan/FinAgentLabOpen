# FinAgentLab 辩论与决策层 — 学习文档 v1

> **目标**：理解从四份分析报告到最终交易决策的完整推理链路 — 牛熊辩论 → 研究经理裁决 → 交易员执行 → 风险三人辩论 → 风险经理终裁。
>
> **核心文件**：
> | 文件 | 行数 | 角色 |
> |---|---|---|
> | `agents/researchers/bull_researcher.py` | 145 | 看涨研究员 — 多方论证 |
> | `agents/researchers/bear_researcher.py` | 136 | 看跌研究员 — 空方论证 |
> | `agents/managers/research_manager.py` | 114 | 研究经理 — 辩论裁判 + 投资计划 |
> | `agents/trader/trader.py` | 119 | 交易员 — 执行计划 |
> | `agents/risk_mgmt/aggresive_debator.py` | 83 | 激进风险辩论者 |
> | `agents/risk_mgmt/conservative_debator.py` | 85 | 保守风险辩论者 |
> | `agents/risk_mgmt/neutral_debator.py` | 87 | 中立风险辩论者 |
> | `agents/managers/risk_manager.py` | 168 | 风险经理 — 最终裁决 |

---

## 1. 整体角色：分析师产出"素材"，辩论层产出"决策"

```
┌───────────────────────────────────────────────────────────────┐
│                      分析阶段（Day 4 已讲）                      │
│                                                               │
│  Market Analyst ──→ market_report                             │
│  Fundamentals Analyst ──→ fundamentals_report                 │
│  News Analyst ──→ news_report                                 │
│  Social Analyst ──→ sentiment_report                          │
│                                                               │
│  输出: 四份独立报告（各自为政，视角单一）                          │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                      辩论与决策阶段（本章）                       │
│                                                               │
│  牛熊辩论 ──→ 研究经理 ──→ 交易员 ──→ 风险三人辩论 ──→ 风险经理  │
│                                                               │
│  输出: final_trade_decision（多层过滤后的最终决策）               │
└───────────────────────────────────────────────────────────────┘
```

**核心设计思想**：不信任单一 Agent 的判断。通过**对立辩论 + 多层裁决**，让决策经过多次质疑和审视后才落地。

---

## 2. Bull & Bear Researcher — 镜像般的对立设计

### 2.1 两者的代码结构几乎完全对称

```
Bull Researcher                          Bear Researcher
═══════════════                          ═══════════════
读取: 四份报告                           读取: 四份报告 ✓ 相同
读取: investment_debate_state["history"] 读取: investment_debate_state["history"] ✓ 相同
读取: investment_debate_state["current_response"] (对方的最新发言)
读取: memory.get_memories(curr_situation) 读取: memory.get_memories(curr_situation) ✓ 相同

Prompt 角色: 看涨分析师                   Prompt 角色: 看跌分析师 ← 唯一差异
Prompt 要求: 论证为什么该买                Prompt 要求: 论证为什么该卖 ← 唯一差异
Prompt 包含: 四份报告 + 辩论历史 + 对方最新发言 + 历史反思

llm.invoke(prompt)                       llm.invoke(prompt)

写入: bull_history += 新发言              写入: bear_history += 新发言
写入: history += 新发言                   写入: history += 新发言
写入: current_response = "Bull Analyst:" 写入: current_response = "Bear Analyst:"
写入: count += 1                          写入: count += 1
                                          ⚠️ 必须显式保留 bull_history
⚠️ 必须显式保留 bear_history
```

### 2.2 关键代码对比：状态写入中的"保留对方历史"

```python
# Bull Researcher 的返回 — 必须显式保留 Bear 的历史
new_investment_debate_state = {
    "history": history + "\n" + argument,                             # 追加自己
    "bull_history": bull_history + "\n" + argument,                   # 追加到多方
    "bear_history": investment_debate_state.get("bear_history", ""),  # ← 保留空方！
    "current_response": argument,                                      # 更新当前发言者
    "count": new_count,
}
```

```python
# Bear Researcher 的返回 — 必须显式保留 Bull 的历史
new_investment_debate_state = {
    "history": history + "\n" + argument,                             # 追加自己
    "bear_history": bear_history + "\n" + argument,                   # 追加到空方
    "bull_history": investment_debate_state.get("bull_history", ""),  # ← 保留多方！
    "current_response": argument,                                      # 更新当前发言者
    "count": new_count,
}
```

**这是 Day 3 已经分析过的嵌套状态合并陷阱**：`investment_debate_state` 是覆盖式更新，每个节点必须在返回的 dict 中显式保留对方的历史字段。

### 2.3 Prompt 中的"辩论"本质

两者都用**对话风格**而非"报告风格"来写 Prompt：

```
Bull:
"以对话风格呈现你的论点，直接回应看跌分析师的观点并进行有效辩论，
而不仅仅是列举数据"

Bear:
"以对话风格呈现你的论点，直接回应看涨分析师的观点并进行有效辩论，
而不仅仅是列举事实"
```

**为什么强调"对话风格"？** 因为辩论是**交替进行的**：Bull 说完 → Bear 看到 Bull 的完整发言 → Bear 必须**逐条反驳**，而不是自说自话。对话框风格（"我认为…"、"你的这个观点忽略了…"）比报告风格更容易实现真正的"辩论"效果。

### 2.4 历史反思的注入

两个研究员都使用记忆系统：

```python
curr_situation = f"{market_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
past_memories = memory.get_memories(curr_situation, n_matches=2)
```

`curr_situation`（四份报告的拼接）作为查询文本，在 ChromaDB 中检索**最相似的 2 个历史情境**及其反思结论。检索结果注入 Prompt：

```
类似情况的反思和经验教训：{past_memory_str}

你还必须处理反思并从过去的经验教训和错误中学习。
```

**这就是 RAG 在 Agent 决策中的实际应用**：当前市场情境 → 向量检索 → 找到历史上类似情境的反思 → 注入当前决策的 Prompt。

### 2.5 两者都使用 `quick_thinking_llm`

```python
# setup.py 中
bull_researcher_node = create_bull_researcher(self.quick_thinking_llm, self.bull_memory)
bear_researcher_node = create_bear_researcher(self.quick_thinking_llm, self.bear_memory)
```

辩论阶段需要**多样性和创造力**（生成有说服力的论点），所以用快速模型（温度 0.7）。深度模型的"谨慎"反而会让辩论变得保守和无聊。

---

## 3. Research Manager（研究经理）— 辩论裁判

### 3.1 与 Bull/Bear 的本质区别

| | Bull/Bear Researcher | Research Manager |
|---|---|---|
| LLM | `quick_thinking_llm` | `deep_thinking_llm` |
| 角色 | 参与者（辩护一个立场） | **裁判**（裁决哪个立场正确） |
| 输入 | 四份报告 + 对方发言 | 四份报告 + **完整辩论历史** |
| 输出 | 一段辩论发言 | **投资计划**（含目标价、时间范围、风险情景） |
| 记忆 | bull_memory / bear_memory | invest_judge_memory |

### 3.2 Prompt 的核心要求

```
作为投资组合经理和辩论主持人，您的职责是批判性地评估这轮辩论并做出明确决策：
支持看跌分析师、看涨分析师，或者仅在基于所提出论点有强有力理由时选择持有。

避免仅仅因为双方都有有效观点就默认选择持有；
要基于辩论中最强有力的论点做出承诺。

📊 目标价格分析：
- 基本面报告中的基本估值
- 新闻对价格预期的影响
- 情绪驱动的价格调整
- 技术支撑/阻力位
- 风险调整价格情景（保守、基准、乐观）
- 价格目标的时间范围（1个月、3个月、6个月）

💰 您必须提供具体的目标价格 - 不要回复"无法确定"或"需要更多信息"。
```

**关键设计决策**：Research Manager 被要求"不要默认持有"——防止 LLM 在均势辩论中偷懒选择最安全的中立答案。这迫使它做实质性判断。

### 3.3 深度模型的使用场景

```python
response = llm.invoke(prompt)  # llm = deep_thinking_llm
```

Research Manager 是**第一个使用深度模型的节点**。原因：
- 它需要综合 4 份报告 + 辩论历史 + 历史反思 → 信息量巨大
- 它需要做**可量化的判断**（目标价、时间范围）→ 不能模糊
- 它是投资决策的**第一道正式关卡** → 错误成本高

---

## 4. Trader（交易员）— 投资计划 → 可执行决策

### 4.1 Trader 节点的特殊之处

Trader 是唯一一个使用 `functools.partial` 创建的节点：

```python
def create_trader(llm, memory):
    def trader_node(state, name):       # ← 多了一个 name 参数！
        ...
    return functools.partial(trader_node, name="Trader")  # ← 预填充
```

**为什么需要 `name` 参数？** LangGraph 要求节点函数签名是 `(state) -> dict`。但 Trader 需要在返回中写入 `sender` 字段。`functools.partial` 把 `name="Trader"` 预先绑定，让最终的节点函数仍满足 `(state) -> dict` 的签名。

### 4.2 Prompt 的"执行者"视角

Trader 的 Prompt 与其他所有 Agent 的根本差异：

```
Bull/Bear/Manager 的 Prompt:
"分析...评估...建议..."        （建议者视角）

Trader 的 Prompt:
"提供具体的买入、卖出或持有建议" （执行者视角）
"🚨 强制要求提供具体数值"
"绝对不允许说'无法确定目标价'或'需要更多信息'"
```

Trader 被强制要求输出**可执行的具体数字**（目标价、置信度、风险评分），因为它的输出会被 `SignalProcessor` 解析为结构化 JSON。

### 4.3 System Prompt 中注入历史交易反思

```python
"请不要忘记利用过去决策的经验教训来避免重复错误。
以下是类似情况下的交易反思和经验教训: {past_memory_str}"
```

Trader 有自己的专属记忆（`trader_memory`），存储历史上交易决策的反思。这与 Bull/Bear 的记忆是**独立的**——每个角色从自己的历史错误中学习。

---

## 5. 风险辩论三人组 — 又一次"对立辩论"

### 5.1 为什么需要第二次辩论？

```
投资辩论 (Bull vs Bear)        → 确定"该不该买/卖"
风险辩论 (Risky vs Safe vs Neutral) → 确定"这个决策的风险是否可控"
```

这是两层不同的判断维度。即使研究经理判断"应该买入"，风险辩论可能发现"但当前风险太高，建议减少仓位或等待更好时机"。

### 5.2 三人的角色定位

| 角色 | 核心关注 | 对交易员计划的态度 |
|---|---|---|
| **Risky Analyst** | 高回报、增长潜力、竞争优势 | 积极支持，强调上涨空间 |
| **Safe Analyst** | 资产保护、低波动、稳定增长 | 批判高风险要素，强调下行风险 |
| **Neutral Analyst** | 平衡视角、风险收益权衡 | 挑战两方的极端观点，倡导温和策略 |

### 5.3 三人的代码结构完全一致

三人的代码差异**仅在于 Prompt 的视角描述和写入的字段名**：

```
Risky:  写入 risky_history   + "latest_speaker": "Risky"
Safe:   写入 safe_history    + "latest_speaker": "Safe"
Neutral: 写入 neutral_history + "latest_speaker": "Neutral"
```

**共享模式**：
```python
# 三人共用的代码骨架
def create_xxx_debator(llm):
    def xxx_node(state) -> dict:
        # 1. 读取 risk_debate_state（含其他两人的最新发言）
        # 2. 读取四份报告 + trader_investment_plan
        # 3. 构造辩论 Prompt（角色视角 + 对方发言 + 四份报告）
        # 4. llm.invoke(prompt)
        # 5. 写入自己的 history + 保留另外两人的 history + count+1
    return xxx_node
```

### 5.4 三人都使用 quick_thinking_llm

```python
# setup.py 中
risky_analyst   = create_risky_debator(self.quick_thinking_llm)
neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
safe_analyst    = create_safe_debator(self.quick_thinking_llm)
```

与 Bull/Bear 同理：辩论需要创造力，快速模型更适合。

---

## 6. Risk Manager（风险经理）— 最终裁决者

### 6.1 这是整个工作流的最后一个节点

```
Risk Judge ──→ END
```

它的输出 `final_trade_decision` 是整个 LangGraph 工作流的最终产物。

### 6.2 为什么是唯一有重试机制的节点？

```python
max_retries = 3
while retry_count < max_retries:
    try:
        response = llm.invoke(prompt)
        if response and hasattr(response, 'content') and response.content:
            break
    except Exception as e:
        response_content = ""
    retry_count += 1
    time.sleep(2)
```

**这是整个项目中唯一有重试逻辑的 Agent 节点。** 原因：
- 它是最终决策节点 → 失败意味着整个分析流水线白跑
- 它使用深度模型 → 深度模型调用时间更长、更容易超时
- 它需要综合的信息量最大 → Prompt 最长 → 更容易触发 API 限制

### 6.3 默认决策兜底

```python
if not response_content:
    response_content = """**默认建议：持有**
由于技术原因无法生成详细分析，基于当前市场状况和风险控制原则，
建议对{company_name}采取持有策略。
注意：此为系统默认建议，建议结合人工分析做出最终决策。"""
```

三次重试全部失败后，返回"持有"而非"买入"或"卖出"——**保守兜底**，避免在系统异常时给出激进建议。

### 6.4 使用 deep_thinking_llm

与 Research Manager 相同的逻辑：最终裁决需要深度推理能力。

---

## 7. 完整辩论决策链路的数据流

```
输入: 四份报告 (market_report, fundamentals_report, news_report, sentiment_report)

┌─ 阶段 1: 投资辩论 ──────────────────────────────────────────┐
│ Bull Researcher (quick_llm)                                   │
│   输入: 四份报告 + "" (首轮无对方发言) + memory              │
│   输出: "Bull Analyst: 万科A作为房地产龙头..."                │
│                                                               │
│ Bear Researcher (quick_llm)                                   │
│   输入: 四份报告 + Bull 的完整发言 + memory                   │
│   输出: "Bear Analyst: 但房地产行业面临融资收紧..."           │
│                                                               │
│ → debate_state.count: 0→1→2                                  │
│ → debate_state.history: Bull发言 + Bear发言                   │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ 阶段 2: 研究经理裁决 ──────────────────────────────────────┐
│ Research Manager (deep_llm)                                   │
│   输入: 四份报告 + 完整辩论历史 + memory                      │
│   输出: "## 投资计划\n建议: 买入\n目标价位: ¥18-20\n..."     │
│                                                               │
│ → debate_state.judge_decision = response.content              │
│ → investment_plan = response.content                          │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ 阶段 3: 交易员执行 ────────────────────────────────────────┐
│ Trader (quick_llm)                                            │
│   输入: investment_plan + 四份报告 + memory                   │
│   输出: "最终交易建议: **买入**\n目标价位: ¥18.50\n..."      │
│                                                               │
│ → trader_investment_plan = response.content                   │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ 阶段 4: 风险三人辩论 ──────────────────────────────────────┐
│ Risky Analyst (quick_llm)                                     │
│   输入: trader_investment_plan + 四份报告 + "" (首轮)        │
│   输出: "Risky Analyst: 激进角度看，应该加大仓位..."         │
│                                                               │
│ Safe Analyst (quick_llm)                                      │
│   输入: trader_investment_plan + 四份报告 + Risky 发言        │
│   输出: "Safe Analyst: 但当前风险过高，建议减半..."          │
│                                                               │
│ Neutral Analyst (quick_llm)                                   │
│   输入: trader_investment_plan + 四份报告 + Risky + Safe 发言 │
│   输出: "Neutral Analyst: 兼顾收益与风险，建议..."           │
│                                                               │
│ → risk_debate_state.count: 0→1→2→3                           │
│ → risk_debate_state.history: 三人发言拼接                     │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ 阶段 5: 风险经理终裁 ──────────────────────────────────────┐
│ Risk Judge (deep_llm, 3次重试)                                │
│   输入: trader_investment_plan + 四份报告 + 三人辩论历史      │
│         + memory                                              │
│   输出: "## 最终交易决策\n操作: 买入\n目标价: ¥18.50\n..."   │
│                                                               │
│ → final_trade_decision = response.content                     │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
    输出给 SignalProcessor 做结构化提取
```

---

## 8. 辩论层的 Prompt 设计对比

| Agent | Prompt 类型 | 核心约束 |
|---|---|---|
| Bull/Bear | 角色扮演 + 辩论 | "直接回应对方的观点""以对话风格呈现""反驳对方逻辑中的弱点" |
| Research Manager | 裁判 + 计划 | "避免默认持有""必须提供具体目标价""基于最强论点做承诺" |
| Trader | 执行者 | "强制提供具体数值""不允许说无法确定""必须包含置信度和风险评分" |
| Risky/Safe/Neutral | 角色扮演 + 辩论 | "批判性地分析对方""指出他们可能忽视的威胁/机会""展示为什么你的视角更优" |
| Risk Manager | 终裁 | "力求清晰和果断""只有在有具体论据时选持有""从过去错误中学习" |

---

## 9. 记忆系统的分层使用

项目中有 **5 个独立的 ChromaDB 记忆实例**，每个角色从自己的历史中学习：

| 记忆实例 | 使用者 | 存储内容 |
|---|---|---|
| `bull_memory` | Bull Researcher | 历史上看涨分析的反思 |
| `bear_memory` | Bear Researcher | 历史上看跌分析的反思 |
| `trader_memory` | Trader | 历史上交易决策的反思 |
| `invest_judge_memory` | Research Manager | 历史上投资裁决的反思 |
| `risk_manager_memory` | Risk Manager | 历史上风险裁决的反思 |

**为什么分开？** 因为"看涨但最终亏了"对 Bull Researcher 是一个教训（为什么我的看涨论点错了？），但对 Bear Researcher 可能是一个成功（我看跌是对的）。同一个回报数据，不同角色的解读完全相反。分开存储才能让每个角色从自己独特的角度学习。

---

## 10. 面试追问

| 问题 | 答题要点 |
|---|---|
| **为什么牛熊辩论只用一轮，而风险辩论要三人轮转？** | 牛熊是二元对立（多 vs 空），两人各说一次就够了；风险是多维判断（激进 vs 保守 vs 中性），需要三个视角全覆盖 |
| **为什么 Trader 在 Research Manager 之后还要单独存在？** | Manager 给的是"投资计划"（策略层面），Trader 给的是"可执行决策"（操作层面，含具体价位和置信度）。关注点分离 |
| **为什么 Risk Manager 有重试而 Research Manager 没有？** | Risk Manager 是整个工作流的最后一步，失败成本最高。Research Manager 失败只会影响中间产物，还有后续节点兜底 |
| **三人和两人的辩论控制公式有什么不同？** | 牛熊：`max=2*rounds`（两人交替，各 round 次）。风险：`max=3*rounds`（三人轮转，各 round 次） |
| **如果 Bull 和 Bear 都说"持有"怎么办？** | Research Manager 的 Prompt 明确要求"避免默认选择持有"，会迫使它找更强的信号做方向判断 |

---

## 11. 建议动手实验

1. **单轮 vs 多轮辩论对比**：分别设 `max_debate_rounds=1` 和 `=3`，对比 Research Manager 的裁决质量
2. **移除记忆系统**：在 config 中设 `memory_enabled=False`，对比 Bull/Bear 的论证是否有历史经验的区别
3. **交换 LLM 角色**：让 Bull 用 `deep_thinking_llm`、Research Manager 用 `quick_thinking_llm`，观察决策质量变化
4. **Trace 辩论中的"反驳率"**：统计 Bear 发言中有多少句直接回应了 Bull 的具体论点（评估辩论是否真的在对话）
5. **风险辩论顺序的敏感性测试**：将图结构中的风险辩论顺序从 `Risky→Safe→Neutral` 改为 `Safe→Risky→Neutral`，观察 Risk Manager 的裁决是否受发言顺序影响

---

> **上一文档**：[分析师 Agent 详解](analyst-agents-deep-dive-v1.md) — Day 4
>
> **下一步**：Day 6 — 风险辩论三人组 + 交易员 + Agent 工具集与记忆系统（`agent_utils.py` / `memory.py` / `reflection.py`）
