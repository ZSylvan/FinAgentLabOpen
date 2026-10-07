# FinAgentLab LangGraph 图构建 — 学习文档 v1

> **目标**：理解基于 LangGraph 的多智能体股票分析工作流是如何从零搭建、编排和执行的。
>
> **核心文件**（均位于 `finagentlab/graph/`）：
> | 文件 | 行数 | 职责 |
> |---|---|---|
> | `trading_graph.py` | 1175 | 顶层编排器：LLM 初始化、组件装配、图执行、性能统计 |
> | `setup.py` | 267 | 图结构构建：节点注册 + 边连接 + 编译 |
> | `conditional_logic.py` | 243 | 条件路由：决定图中每个分支点的下一步走向 |
> | `propagation.py` | 68 | 状态初始化：构建工作流的起始状态 |
> | `reflection.py` | 126 | 反思机制：基于投资回报的 LLM 自省 + 记忆更新 |
> | `signal_processing.py` | 337 | 信号解析：从 LLM 输出中提取结构化交易决策 |
> | `agent_states.py` | 86 | 类型定义：LangGraph 工作流中所有状态的 TypedDict |

---

## 1. 整体架构：谁创建谁？谁持有谁？

```
FinAgentLabGraph  (顶层编排器)
├── quick_thinking_llm  ──── 快速模型（分析师、辩论者、交易员）
├── deep_thinking_llm  ───── 深度模型（研究经理、风险经理）
├── toolkit  ─────────────── 28 个工具方法的数据访问层
├── tool_nodes  ───────────── 4 组 ToolNode（market/social/news/fundamentals）
├── 5 个 FinancialSituationMemory ── ChromaDB 向量记忆
├── ConditionalLogic  ────── 条件路由决策器
├── GraphSetup  ──────────── 图结构构建器 → 产出 compiled graph
├── Propagator  ──────────── 初始状态工厂
├── Reflector  ───────────── 反思 + 记忆更新
├── SignalProcessor  ─────── 交易信号 → 结构化决策
└── self.graph  ──────────── 编译后的 StateGraph（核心可执行对象）
```

**关键设计模式**：
- `FinAgentLabGraph` 是 **Facade（外观模式）** — 对外暴露 `propagate(company_name, trade_date)` 一个方法即可驱动整个工作流
- `GraphSetup` 是 **Builder（建造者模式）** — 负责分步骤构建 StateGraph 对象
- `ConditionalLogic` 是 **Strategy（策略模式）** — 每个条件判断方法对应一个路由策略

---

## 2. 状态设计（`agent_states.py`）— 工作流的"血液"

LangGraph 的核心概念是 **StateGraph**：所有节点共享同一个状态字典，节点通过读写状态来协作。本项目的状态分三层：

### 2.1 顶层：`AgentState`

```python
class AgentState(MessagesState):       # 继承 LangGraph 内置的 MessagesState
    # ── 输入信息 ──
    company_of_interest: str           # 分析目标股票代码
    trade_date: str                    # 分析日期

    # ── 四个分析师报告 ──
    market_report: str                 # 市场分析师产出
    sentiment_report: str              # 社交媒体分析师产出
    news_report: str                   # 新闻分析师产出
    fundamentals_report: str           # 基本面分析师产出

    # ── 死循环防护 ──
    market_tool_call_count: int        # 每个分析师的工具调用计数器
    news_tool_call_count: int
    sentiment_tool_call_count: int
    fundamentals_tool_call_count: int

    # ── 嵌套子状态（TypedDict） ──
    investment_debate_state: InvestDebateState   # 牛熊辩论状态
    risk_debate_state: RiskDebateState           # 风险讨论状态

    # ── 中间产出 ──
    investment_plan: str              # 投资计划
    trader_investment_plan: str       # 交易员投资计划
    final_trade_decision: str         # 最终决策
```

### 2.2 辩论子状态：`InvestDebateState`

```python
class InvestDebateState(TypedDict):
    bull_history: str       # 多方所有历史发言
    bear_history: str       # 空方所有历史发言
    history: str            # 完整辩论记录
    current_response: str   # 当前发言者身份（"Bull Researcher" / "Bear Researcher"）
    judge_decision: str     # 研究经理最终裁决
    count: int              # 已发言轮次（一次 Bull + 一次 Bear = 2 次 count）
```

### 2.3 风险子状态：`RiskDebateState`

```python
class RiskDebateState(TypedDict):
    risky_history: str                # 激进派历史发言
    safe_history: str                 # 保守派历史发言
    neutral_history: str              # 中立派历史发言
    history: str                      # 完整讨论记录
    latest_speaker: str               # 最后发言者（用于轮转）
    current_risky_response: str       # 激进派最新发言
    current_safe_response: str
    current_neutral_response: str
    judge_decision: str               # 风险经理最终裁决
    count: int                        # 已发言次数
```

**设计要点**：
- `MessagesState` 自带 `messages: list` 字段（LangGraph 内部用），存储 LangChain 消息对象
- `Annotated[str, "描述"]` 是 LangGraph 的 reducer 注解语法，这里只用 str 所以是覆盖式更新
- `count` 字段是条件路由的关键 — 通过 count 决定辩论是否继续

---

## 3. 图结构（`setup.py`）— 工作流的"骨架"

### 3.1 `GraphSetup.__init__` 的参数清单

| 参数 | 类型 | 用途 |
|---|---|---|
| `quick_thinking_llm` | `ChatOpenAI` | 快速推理模型（分析师、辩论者用） |
| `deep_thinking_llm` | `ChatOpenAI` | 深度推理模型（研究经理、风险经理用） |
| `toolkit` | `Toolkit` | 28 个工具方法的集合 |
| `tool_nodes` | `Dict[str, ToolNode]` | 4 组预构建的 LangGraph ToolNode |
| `bull/bear/trader/invest_judge/risk_manager_memory` | `FinancialSituationMemory` | 5 个 ChromaDB 记忆实例 |
| `conditional_logic` | `ConditionalLogic` | 条件路由逻辑 |
| `config` | `Dict` | 配置字典（LLM 提供商等） |

### 3.2 `setup_graph()` 方法的三段式构建

#### 第一段：创建 Agent 节点（分析层）

```python
# 可选的四种分析师，按配置动态加载
analyst_nodes = {}        # 分析师 LLM 节点
delete_nodes = {}         # 消息清理节点（防止上下文溢出）
tool_nodes = {}           # 工具执行节点

if "market" in selected_analysts:
    analyst_nodes["market"]    = create_market_analyst(llm, toolkit)
    delete_nodes["market"]     = create_msg_delete()
    tool_nodes["market"]       = self.tool_nodes["market"]
# ... social, news, fundamentals 同理
```

每个分析师配对 **三个节点**：
```
Market Analyst  ←──→  tools_market
       │
       └──→  Msg Clear Market
```

- **Analyst 节点**：LangChain Runnable，LLM + 绑定的工具列表，生成 tool_calls
- **tools_xxx 节点**：LangGraph 内置 `ToolNode`，执行 LLM 产生的 tool_calls
- **Msg Clear 节点**：清理上轮消息，只保留最终报告，减少上下文长度

#### 第二段：创建辩论与决策节点（决策层）

```python
# 牛熊对立研究员（快速模型）
bull_researcher_node  = create_bull_researcher(quick_llm, bull_memory)
bear_researcher_node  = create_bear_researcher(quick_llm, bear_memory)

# 研究经理（深度模型 — 需要综合判断）
research_manager_node = create_research_manager(deep_llm, invest_judge_memory)

# 交易员（快速模型）
trader_node = create_trader(quick_llm, trader_memory)

# 三个风险辩论者（快速模型）
risky_analyst    = create_risky_debator(quick_llm)
neutral_analyst  = create_neutral_debator(quick_llm)
safe_analyst     = create_safe_debator(quick_llm)

# 风险经理（深度模型 — 需要最终裁决）
risk_manager_node = create_risk_manager(deep_llm, risk_manager_memory)
```

**为什么研究经理和风险经理用深度模型，而其他用快速模型？**
- 研究经理需要综合牛熊双方论点做出 **最终投资判断** → 需要深度推理
- 风险经理需要在三种风险偏好中做 **最终风险裁决** → 需要深度推理
- 分析师和辩论者只需生成报告或发表单一观点 → 快速模型足够

#### 第三段：构建 StateGraph 并连线

```python
workflow = StateGraph(AgentState)

# 注册所有节点
workflow.add_node("Market Analyst", node)       # 分析师 × N
workflow.add_node("tools_market", tool_node)    # 工具节点 × N
workflow.add_node("Msg Clear Market", delete)   # 清理节点 × N
workflow.add_node("Bull Researcher", ...)       # 研究员
workflow.add_node("Bear Researcher", ...)
workflow.add_node("Research Manager", ...)
workflow.add_node("Trader", ...)
workflow.add_node("Risky Analyst", ...)         # 风险辩论
workflow.add_node("Neutral Analyst", ...)
workflow.add_node("Safe Analyst", ...)
workflow.add_node("Risk Judge", ...)

# 连线逻辑（详见图解）
workflow.add_edge(START, "Market Analyst")
# ... 条件边 + 普通边 ...
workflow.add_edge("Risk Judge", END)

return workflow.compile()
```

### 3.3 完整的图拓扑结构

```
                              ┌─────────────────────────────────────┐
                              │          分析阶段（顺序执行）          │
                              │                                     │
START ──→ Market Analyst ──┬──→ tools_market ──→ Market Analyst     │
                           │       (循环直到无tool_call)              │
                           ├──→ Msg Clear Market                     │
                           │       │                                 │
                           ├──→ Fundamentals Analyst ──┬──→ tools    │
                           │       │                    ├──→ Msg Clr │
                           │                           │            │
                           ├──→ News Analyst ──┬──→ tools           │
                           │       │            ├──→ Msg Clear       │
                           │                           │            │
                           └──→ Social Analyst ──┬──→ tools         │
                                   │              ├──→ Msg Clear     │
                                                   │                │
                              ┌────────────────────┘                │
                              │          辩论阶段（往复循环）          │
                              ▼                                     │
                    Bull Researcher ◄──────────────────┐            │
                           │                           │            │
                           ▼                           │            │
                    Bear Researcher ───────────────────┘            │
                           │    (count >= max → Research Manager)   │
                           ▼                                        │
                    Research Manager                                │
                           │                                        │
                           ▼          决策阶段                       │
                         Trader                                     │
                           │                                        │
                           ▼          风险评估阶段（轮转循环）         │
                    Risky Analyst ──→ Safe Analyst                   │
                           ▲              │                          │
                           │              ▼                          │
                           └──── Neutral Analyst                     │
                              (count >= max → Risk Judge)           │
                                                                     │
                           ▼                                        │
                       Risk Judge ──→ END                           │
                              └─────────────────────────────────────┘
```

### 3.4 边的类型详解

**普通边（`add_edge`）**：确定性的，无条件跳转
```python
workflow.add_edge(START, "Market Analyst")     # 图入口
workflow.add_edge(current_tools, current_analyst)  # 工具执行后回到分析师
workflow.add_edge("Research Manager", "Trader")    # 顺序执行
workflow.add_edge("Trader", "Risky Analyst")       # 顺序执行
workflow.add_edge("Risk Judge", END)               # 图出口
```

**条件边（`add_conditional_edges`）**：根据状态动态选择下一节点
```python
# 分析师循环：是调用工具还是结束分析？
workflow.add_conditional_edges(
    "Market Analyst",
    self.conditional_logic.should_continue_market,   # 返回 "tools_market" 或 "Msg Clear Market"
    ["tools_market", "Msg Clear Market"]             # 可能的去向
)

# 辩论循环：继续辩论还是交给研究经理？
workflow.add_conditional_edges(
    "Bull Researcher",
    self.conditional_logic.should_continue_debate,   # 返回 "Bear Researcher" 或 "Research Manager"
    {"Bear Researcher": "Bear Researcher", "Research Manager": "Research Manager"}
)

# 风险循环：轮转到下一个风险分析者还是交给风险经理？
workflow.add_conditional_edges(
    "Risky Analyst",
    self.conditional_logic.should_continue_risk_analysis,  # 返回下一个发言者或 "Risk Judge"
    {"Safe Analyst": "Safe Analyst", "Risk Judge": "Risk Judge"}
)
```

---

## 4. 条件路由（`conditional_logic.py`）— 工作流的"大脑"

### 4.1 分析师循环：`should_continue_xxx`

四个分析师（market/social/news/fundamentals）的条件逻辑**完全相同**，核心判断链：

```
1. tool_call_count >= max_tool_calls?  ──→ 强制结束（死循环防护）
2. report 长度 > 100?                  ──→ 结束（分析已完成）
3. last_message 有 tool_calls?         ──→ 继续调用工具
4. 其他情况                            ──→ 结束
```

**关键设计**：
- 每个分析师有独立的 `xxx_tool_call_count` 计数器
- `max_tool_calls` 在 market/social/news 中 = **3**，在 fundamentals 中 = **1**（因为基本面数据可一次获取）
- 计数器存在 `AgentState` 中，由 Agent 节点内部递增
- 报告长度 > 100 字符即认为完成 → 这是一种启发式判断

### 4.2 辩论循环：`should_continue_debate`

```python
def should_continue_debate(self, state):
    current_count = state["investment_debate_state"]["count"]
    max_count = 2 * self.max_debate_rounds    # 一轮 = Bull + Bear 各一次

    if current_count >= max_count:
        return "Research Manager"             # 辩论结束

    # 交替发言
    next_speaker = "Bear Researcher" if current.startswith("Bull") else "Bull Researcher"
    return next_speaker
```

**关键公式**：`max_count = 2 × max_debate_rounds`
- `max_debate_rounds=1`（默认）→ 共 2 次发言 → Bull 一次 + Bear 一次
- `max_debate_rounds=3` → 共 6 次发言 → Bull、Bear 各 3 次

### 4.3 风险讨论循环：`should_continue_risk_analysis`

```python
def should_continue_risk_analysis(self, state):
    current_count = state["risk_debate_state"]["count"]
    max_count = 3 * self.max_risk_discuss_rounds  # 一轮 = 三人各一次

    if current_count >= max_count:
        return "Risk Judge"

    # 轮转顺序：Risky → Safe → Neutral → Risky → ...
    if latest_speaker.startswith("Risky"):
        return "Safe Analyst"
    elif latest_speaker.startswith("Safe"):
        return "Neutral Analyst"
    else:
        return "Risky Analyst"
```

---

## 5. 状态初始化（`propagation.py`）— 工作流的"起跑线"

```python
class Propagator:
    def create_initial_state(self, company_name, trade_date) -> Dict:
        return {
            "messages": [HumanMessage(content=f"请对股票 {company_name} 进行全面分析...")],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),

            # 嵌套子状态 — 全部用空字符串和 0 初始化
            "investment_debate_state": InvestDebateState(
                {"history": "", "current_response": "", "count": 0}
            ),
            "risk_debate_state": RiskDebateState(
                {"history": "", "latest_speaker": "", "count": 0, ...}
            ),

            # 四个报告 — 全部空字符串
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
        }
```

**关键设计**：
- 第一条消息是 `HumanMessage`，包含明确的自然语言分析请求 — 这样无论什么 LLM（DeepSeek/OpenAI/Claude）都能理解任务
- 所有报告字段初始化为 `""` — 条件路由通过检查报告长度 > 100 来判断是否完成

`get_graph_args()` 方法控制 LangGraph 的 stream 模式：
- 有进度回调 → `"updates"` 模式（节点级别增量）
- 无进度回调 → `"values"` 模式（完整状态）
- `recursion_limit` 默认为 100（防止无限循环）

---

## 6. 顶层编排器（`trading_graph.py`）— 工作流的"指挥"

### 6.1 LLM 初始化：双模型架构

```python
class FinAgentLabGraph:
    def __init__(self, selected_analysts, debug, config):
        # 1. 从 config 读取模型参数
        quick_max_tokens = quick_config.get("max_tokens", 4000)
        quick_temperature = quick_config.get("temperature", 0.7)

        # 2. 支持混合模式：快速模型和深度模型可以来自不同厂商！
        if quick_provider != deep_provider:
            self.quick_thinking_llm = create_llm_by_provider(quick_provider, ...)
            self.deep_thinking_llm = create_llm_by_provider(deep_provider, ...)

        # 3. 单厂商模式：分支覆盖 10+ 种 LLM 提供商
        elif provider == "google":    ...
        elif provider == "deepseek":  ...
        elif provider == "anthropic": ...
        # ... 等等
```

**支持的 LLM 提供商**：OpenAI / Anthropic / Google / DeepSeek / 阿里百炼(DashScope) / 千帆 / 智谱 / SiliconFlow / OpenRouter / AiHubMix / Ollama / 自定义 OpenAI 兼容端点

### 6.2 工具节点创建：`_create_tool_nodes()`

每组 ToolNode 都包含三层回退策略：
```python
"market": ToolNode([
    self.toolkit.get_stock_market_data_unified,        # 统一工具（推荐）
    self.toolkit.get_YFin_data_online,                 # 在线工具（备用）
    self.toolkit.get_stockstats_indicators_report_online,
    self.toolkit.get_YFin_data,                        # 离线工具（备用）
    self.toolkit.get_stockstats_indicators_report,
])
```

**设计思想**：ToolNode 包含**所有可能的工具**，由 LLM 自己选择调用哪个。统一工具优先，在线/离线作为回退。

### 6.3 核心执行方法：`propagate()`

```python
def propagate(self, company_name, trade_date, progress_callback=None, task_id=None):
    # 1. 创建初始状态
    init_agent_state = self.propagator.create_initial_state(company_name, trade_date)

    # 2. Stream 执行图
    for chunk in self.graph.stream(init_agent_state, **args):
        # 记录每个节点的执行时间
        # 发送进度更新到前端

    # 3. 打印性能报告
    self._print_timing_summary(node_timings, total_elapsed)

    # 4. 解析最终决策信号
    decision = self.process_signal(final_state["final_trade_decision"], company_name)

    # 5. 持久化状态日志
    self._log_state(trade_date, final_state)

    return final_state, decision
```

**Stream 执行模式**：
- 使用 `graph.stream()` 而非 `graph.invoke()` — 可以获取每个节点的执行结果
- `updates` 模式：`chunk = {"Market Analyst": {增量状态}}`
- `values` 模式：`chunk = {完整状态}`

**性能统计**：`_build_performance_data()` 将节点执行时间分为 7 类：
1. 分析师团队
2. 工具调用
3. 消息清理
4. 研究团队
5. 交易团队
6. 风险管理团队
7. 其他

### 6.4 进度回调：`_send_progress_update()`

将 LangGraph 内部节点名称映射为用户友好的中文消息：
```python
node_mapping = {
    'Market Analyst':       "📊 市场分析师",
    'Bull Researcher':      "🐂 看涨研究员",
    'Bear Researcher':      "🐻 看跌研究员",
    'Trader':               "💼 交易员决策",
    'Risky Analyst':        "🔥 激进风险评估",
    # ...
}
```

工具节点和消息清理节点映射为 `None`（跳过，不推送进度）。

---

## 7. 反思机制（`reflection.py`）— Agent 的"自我进化"

### 7.1 反思流程

```
执行 propagate() 获得 final_state
         │
         ▼ 用户获得实际投资回报
reflect_and_remember(returns_losses)
         │
         ├──→ reflect_bull_researcher()   → bull_memory.add_situations()
         ├──→ reflect_bear_researcher()   → bear_memory.add_situations()
         ├──→ reflect_trader()             → trader_memory.add_situations()
         ├──→ reflect_invest_judge()       → invest_judge_memory.add_situations()
         └──→ reflect_risk_manager()       → risk_manager_memory.add_situations()
```

### 7.2 `_reflect_on_component` 的核心逻辑

```python
def _reflect_on_component(self, component_type, report, situation, returns_losses):
    messages = [
        ("system", self.reflection_system_prompt),  # 详细的反思指令
        ("human", f"Returns: {returns_losses}\n\nAnalysis/Decision: {report}\n\nContext: {situation}"),
    ]
    return self.quick_thinking_llm.invoke(messages).content
```

**反思 Prompt 的四个维度**：
1. **Reasoning** — 分析决策正确/错误的原因（市场情报、技术指标、价格走势、新闻、社交媒体、基本面）
2. **Improvement** — 针对错误决策提出修正建议
3. **Summary** — 总结经验教训
4. **Query** — 压缩为 ≤1000 tokens 的关键洞察

### 7.3 记忆系统

反思结果通过 `FinancialSituationMemory.add_situations()` 存入 ChromaDB：
- 以 `(situation, reflection_result)` 元组形式存储
- `situation` = 四份分析报告拼接（市场 + 情绪 + 新闻 + 基本面）
- `reflection_result` = LLM 生成的反思分析
- 下次分析时，Agent 可以从 ChromaDB 检索相似历史情境作为参考

**这是典型的 RAG（检索增强生成）模式的 Agent 记忆**：历史经验 → 向量嵌入 → 相似检索 → 注入当前决策的上下文。

---

## 8. 信号处理（`signal_processing.py`）— 从自然语言到结构化数据

### 8.1 处理流程

```
Trader 产出自由文本决策
         │
         ▼
SignalProcessor.process_signal(full_signal, stock_symbol)
         │
         ├── LLM 调用（system prompt 要求返回 JSON）
         │      prompt 包含：股票市场信息、货币类型
         │
         ├── 正则提取 JSON
         │      re.search(r'\{.*\}', response, re.DOTALL)
         │
         ├── 验证 + 标准化
         │      action → 必须是 "买入"/"持有"/"卖出"
         │      target_price → 数值修复、多模式正则提取
         │
         ├── 智能价格推算（回退方案）
         │      从文本提取 current_price × (1 + 预估涨跌幅)
         │
         └── 返回:
              {
                  'action': '买入' | '持有' | '卖出',
                  'target_price': float | None,
                  'confidence': 0.0-1.0,
                  'risk_score': 0.0-1.0,
                  'reasoning': str
              }
```

### 8.2 三层回退策略

1. **LLM JSON 解析**（主路径）→ LLM 按要求返回 JSON
2. **`_extract_simple_decision()`**（备用）→ 纯正则从原始文本提取
3. **`_get_default_decision()`**（兜底）→ 返回 `action='持有', confidence=0.5`

### 8.3 价格提取的精细设计

`_smart_price_estimation()` 是一个巧妙的设计：
- 先从文本中提取当前价格和涨跌幅
- 根据 action 类型估算目标价：
  - 买入 → `current_price × (1 + percentage_change)`
  - 卖出 → `current_price × (1 - percentage_change)`
  - 无涨跌幅 → 使用默认乘数（A 股 15%，美股 12%）

---

## 9. 一次完整分析的数据流（全链路追踪）

> 以下追踪以 `company_name="000002"`（万科A），`trade_date="2025-07-04"`，`selected_analysts=["market", "fundamentals", "news", "social"]`，`max_debate_rounds=1`，`max_risk_discuss_rounds=1` 为例。

### 9.0 阶段 0：状态初始化

```
Propagator.create_initial_state("000002", "2025-07-04")
│
│  输入: company_name="000002", trade_date="2025-07-04"
│
│  过程: 构建第一条 HumanMessage + 初始化所有空字段
│
│  输出: AgentState {
│    messages: [HumanMessage("请对股票 000002 进行全面分析，交易日期为 2025-07-04。")],
│    company_of_interest: "000002",
│    trade_date: "2025-07-04",
│    market_report: "",           sentiment_report: "",
│    news_report: "",             fundamentals_report: "",
│    market_tool_call_count: 0,   news_tool_call_count: 0,
│    sentiment_tool_call_count: 0,fundamentals_tool_call_count: 0,
│    investment_debate_state: {history:"", bull_history:"", bear_history:"",
│                               current_response:"", judge_decision:"", count:0},
│    risk_debate_state: {history:"", risky_history:"", safe_history:"",
│                         neutral_history:"", latest_speaker:"",
│                         current_risky_response:"", current_safe_response:"",
│                         current_neutral_response:"", judge_decision:"", count:0},
│    investment_plan: "",         trader_investment_plan: "",
│    final_trade_decision: ""
│  }
```

### 9.1 阶段 1：Market Analyst 循环

```
┌──────────────────────────────────────────────────────────────────────┐
│ 节点 1a: Market Analyst（第一轮）                                      │
│                                                                      │
│ 读取:                                                                 │
│   state["trade_date"] → "2025-07-04"                                 │
│   state["company_of_interest"] → "000002"                            │
│   state["messages"] → [HumanMessage("请对股票 000002 进行全面分析...")]│
│   state["market_tool_call_count"] → 0                                │
│                                                                      │
│ 过程:                                                                 │
│   1. 调用 StockUtils.get_market_info("000002") → 判定为 A 股          │
│   2. 获取公司名称: "万科A"                                            │
│   3. 构造 ChatPromptTemplate（系统提示含分析要求 + 工具名称）           │
│   4. 构建 chain = prompt | llm.bind_tools([get_stock_market_data_unified])│
│   5. chain.invoke({"messages": state["messages"]})                   │
│   6. LLM 返回 AIMessage，含 tool_calls:                               │
│      [{"name": "get_stock_market_data_unified",                       │
│        "args": {"ticker": "000002", ...}}]                            │
│                                                                      │
│ 写入（返回给 StateGraph 做增量合并）:                                  │
│   messages: [AIMessage(tool_calls=[...])]   ← 追加到消息列表          │
│   market_report: ""                         ← 尚未生成报告            │
│   market_tool_call_count: 1                 ← 递增计数器              │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: should_continue_market() 判断
         │ → last_message 有 tool_calls → 路由到 "tools_market"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点 1b: tools_market                                                 │
│                                                                      │
│ 读取:                                                                 │
│   state["messages"][-1] → AIMessage(tool_calls=[...])                │
│     → 提取 tool_calls[0]: {name:"get_stock_market_data_unified", ...} │
│                                                                      │
│ 过程:                                                                 │
│   1. ToolNode 解析 tool_calls 列表                                    │
│   2. 调用 toolkit.get_stock_market_data_unified(ticker="000002", ...) │
│   3. 工具返回 A 股行情数据文本（价格、涨跌幅、成交量、技术指标等）      │
│                                                                      │
│ 写入:                                                                 │
│   messages: [ToolMessage(content="股票数据: 当前价 ¥15.23...",         │
│             tool_call_id="call_xxx")]  ← 追加工具执行结果              │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 普通边: tools_market ──→ Market Analyst（固定回到分析师）
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点 1c: Market Analyst（第二轮）                                      │
│                                                                      │
│ 读取:                                                                 │
│   state["messages"] → [HumanMessage, AIMessage(tool_calls),          │
│                         ToolMessage(行情数据)]                        │
│   state["market_tool_call_count"] → 1                                │
│                                                                      │
│ 过程:                                                                 │
│   1. 检测 messages 中已有 ToolMessage（工具结果）                      │
│   2. LLM 不再生成 tool_calls，直接基于工具数据分析                     │
│   3. 输出最终技术分析报告文本                                          │
│                                                                      │
│ 写入:                                                                 │
│   messages: [AIMessage(content="## 股票基本信息\n- 公司名称：万科A...")]
│   market_report: "## 万科A（000002）技术分析报告\n..." (约 2000+ 字符) │
│   market_tool_call_count: 2                                           │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: should_continue_market() 判断
         │ → len(market_report) > 100 → 路由到 "Msg Clear Market"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点 1d: Msg Clear Market                                             │
│                                                                      │
│ 读取:                                                                 │
│   state["messages"] → 完整消息列表（含中间 tool_call/tool_result）     │
│                                                                      │
│ 过程:                                                                 │
│   清除非最终报告消息，减少上下文长度（实现为 create_msg_delete()）      │
│                                                                      │
│ 写入:                                                                 │
│   messages: [精简后的消息列表]  ← 保留 report 的 AIMessage，删除中间消息│
└──────────────────────────────────────────────────────────────────────┘
```

### 9.2 阶段 2：Fundamentals / News / Social Analyst（三个分析师的循环同理）

> 以下三个分析师与 Market Analyst 结构完全一致，仅工具和报告字段不同：

```
Fundamentals Analyst ⇄ tools_fundamentals (tool_call_count 上限=1，一次调用即可获取全部基本面数据)
│
│  读取: state["company_of_interest"], state["trade_date"],
│        state["messages"], state["fundamentals_tool_call_count"]
│
│  工具: toolkit.get_stock_fundamentals_unified
│        → 返回 PE、PB、ROE、营收、利润等财务数据
│
│  写入: fundamentals_report = "## 万科A（000002）基本面分析报告\n..."
│        fundamentals_tool_call_count 递增
│
Msg Clear Fundamentals

───────────────────────────────────────────

News Analyst ⇄ tools_news (tool_call_count 上限=3)
│
│  读取: state["company_of_interest"], state["trade_date"],
│        state["messages"], state["news_tool_call_count"]
│
│  工具: toolkit.get_stock_news_unified
│        → 返回相关新闻标题、来源、情感极性
│
│  写入: news_report = "## 万科A（000002）新闻分析报告\n..."
│        news_tool_call_count 递增
│
Msg Clear News

───────────────────────────────────────────

Social Analyst ⇄ tools_social (tool_call_count 上限=3)
│
│  读取: state["company_of_interest"], state["trade_date"],
│        state["messages"], state["sentiment_tool_call_count"]
│
│  工具: toolkit.get_stock_sentiment_unified
│        → 返回社交媒体舆情、Reddit/微博讨论热度、情感评分
│
│  写入: sentiment_report = "## 万科A（000002）舆情分析报告\n..."
│        sentiment_tool_call_count 递增
│
Msg Clear Social
```

此时状态中的四份报告全部就绪：
```
state.market_report       = "## 万科A 技术分析报告..."     (2000+ chars)
state.fundamentals_report = "## 万科A 基本面分析报告..."    (1500+ chars)
state.news_report         = "## 万科A 新闻分析报告..."      (800+ chars)
state.sentiment_report    = "## 万科A 舆情分析报告..."      (700+ chars)
```

### 9.3 阶段 3：投资辩论（牛熊对立）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Bull Researcher（看涨研究员，第一轮）                            │
│                                                                      │
│ 读取:                                                                 │
│   state["market_report"]        → 技术分析报告全文                    │
│   state["sentiment_report"]     → 舆情分析报告全文                    │
│   state["news_report"]          → 新闻分析报告全文                    │
│   state["fundamentals_report"]  → 基本面分析报告全文                  │
│   state["investment_debate_state"]["history"]         → "" (首轮为空) │
│   state["investment_debate_state"]["current_response"] → ""           │
│   state["investment_debate_state"]["count"]           → 0             │
│   memory.get_memories(curr_situation, n_matches=2)   → [] 或历史反思  │
│                                                                      │
│ 过程:                                                                 │
│   1. 拼接四份报告为 curr_situation                                    │
│   2. 从 ChromaDB 检索相似历史情境的反思经验                            │
│   3. 构造 Prompt（角色：看涨分析师，需反驳看跌观点）                    │
│   4. llm.invoke(prompt) → 生成看涨论点                                 │
│                                                                      │
│ 写入:                                                                 │
│   investment_debate_state: {                                          │
│     bull_history:  "Bull Analyst: 万科A作为房地产龙头..."  ← 新增     │
│     bear_history:  ""                                  ← 不变         │
│     history:       "Bull Analyst: 万科A作为房地产龙头..." ← 追加     │
│     current_response: "Bull Analyst: ..."               ← 更新        │
│     count: 1                                            ← 递增        │
│   }                                                                   │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: should_continue_debate() 判断
         │ → count=1 < max_count=2(2×1) → 路由到 "Bear Researcher"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Bear Researcher（看跌研究员，第一轮）                            │
│                                                                      │
│ 读取:                                                                 │
│   同上四份报告 +                                                      │
│   state["investment_debate_state"]["history"]         → 含 Bull 发言  │
│   state["investment_debate_state"]["current_response"] → Bull 最新发言│
│   state["investment_debate_state"]["count"]           → 1             │
│                                                                      │
│ 过程:                                                                 │
│   1. Prompt 角色是看跌分析师 → 需直接回应 Bull 的看涨论点并反驳        │
│   2. llm.invoke(prompt) → 生成看跌论点                                │
│                                                                      │
│ 写入:                                                                 │
│   investment_debate_state: {                                          │
│     bull_history:  "Bull Analyst: ..."                 ← 不变         │
│     bear_history:  "Bear Analyst: 但房地产行业面临..."  ← 新增        │
│     history:       "...\nBear Analyst: 但房地产行业..." ← 追加        │
│     current_response: "Bear Analyst: ..."              ← 更新         │
│     count: 2                                            ← 递增        │
│   }                                                                   │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: should_continue_debate() 判断
         │ → count=2 >= max_count=2 → 路由到 "Research Manager"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Research Manager（研究经理，深度模型）                           │
│                                                                      │
│ 读取:                                                                 │
│   state["market_report"], state["sentiment_report"],                 │
│   state["news_report"], state["fundamentals_report"]                 │
│   state["investment_debate_state"]["history"]  → Bull+Bear 完整辩论   │
│   memory.get_memories(curr_situation, n_matches=2)                   │
│                                                                      │
│ 过程:                                                                 │
│   1. 拼接所有素材构造 Prompt                                          │
│   2. 要求 LLM（deep_thinking_llm）做最终裁决：                        │
│      - 总结双方关键论点                                                │
│      - 明确决策（买入/卖出/持有）                                     │
│      - 制定投资计划（含目标价、时间范围、风险情景）                     │
│                                                                      │
│ 写入:                                                                 │
│   investment_debate_state: {                                          │
│     judge_decision: "综合辩论结果，建议买入万科A..."                   │
│     history: 辩论历史 (已保留), count: 2 (不变)                       │
│   }                                                                   │
│   investment_plan: "## 投资计划\n目标价位: ¥18-20\n..."               │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.4 阶段 4：交易决策

```
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Trader（交易员，快速模型）                                       │
│                                                                      │
│ 读取:                                                                 │
│   state["company_of_interest"] → "000002"                            │
│   state["investment_plan"]      → 研究经理的投资计划                  │
│   state["market_report"]        → 四份报告（拼接为 curr_situation）    │
│   state["fundamentals_report"], state["news_report"],                │
│   state["sentiment_report"]                                           │
│   memory.get_memories(curr_situation) → 历史交易反思                   │
│                                                                      │
│ 过程:                                                                 │
│   1. 构造 system prompt（角色：专业交易员，必须给出具体目标价）         │
│   2. 注入历史交易反思经验（past_memory_str）                          │
│   3. llm.invoke(messages) → 生成具体交易计划                          │
│                                                                      │
│ 写入:                                                                 │
│   messages: [AIMessage(content="最终交易建议: **买入**\n...")]         │
│   trader_investment_plan: "最终交易建议: **买入**\n目标价位: ¥18.50..."│
│   sender: "Trader"                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.5 阶段 5：风险辩论（三人轮转）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Risky Analyst（激进型，快速模型，count=0）                       │
│                                                                      │
│ 读取:                                                                 │
│   state["trader_investment_plan"] → 交易员的投资计划                   │
│   state["risk_debate_state"]["history"] → "" (首轮为空)               │
│   state["risk_debate_state"]["count"] → 0                            │
│                                                                      │
│ 过程: 从高风险承受角度评估交易计划                                     │
│                                                                      │
│ 写入:                                                                 │
│   risk_debate_state: {                                                │
│     risky_history:   "Risky Analyst: 激进角度看..."  ← 新增          │
│     current_risky_response: "Risky Analyst: ..."     ← 更新          │
│     latest_speaker: "Risky Analyst", count: 1        ← 更新          │
│   }                                                                   │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: should_continue_risk_analysis()
         │ → count=1 < max_count=3(3×1) → latest="Risky" → "Safe Analyst"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Safe Analyst（保守型，快速模型，count=1）                        │
│                                                                      │
│ 读取: 同上 + risk_debate_state (含 Risky 发言)                        │
│ 过程: 从低风险保守角度评估，回应激进观点                                │
│ 写入: safe_history 更新, latest_speaker="Safe Analyst", count=2       │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: count=2 < 3 → latest="Safe" → "Neutral Analyst"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Neutral Analyst（中立型，快速模型，count=2）                     │
│                                                                      │
│ 读取: 同上 + risk_debate_state (含 Risky+Safe 发言)                   │
│ 过程: 从平衡角度评估，回应前两人的观点                                  │
│ 写入: neutral_history 更新, latest_speaker="Neutral Analyst", count=3 │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ 条件边: count=3 >= 3 → "Risk Judge"
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 节点: Risk Judge（风险经理，深度模型）                                  │
│                                                                      │
│ 读取:                                                                 │
│   state["risk_debate_state"] → 三人完整辩论历史                       │
│   state["trader_investment_plan"] → 交易员的投资计划                   │
│                                                                      │
│ 过程:                                                                 │
│   1. deep_thinking_llm 综合三人观点                                    │
│   2. 对投资计划做最终风险裁决                                          │
│                                                                      │
│ 写入:                                                                 │
│   risk_debate_state.judge_decision: "综合风险评估: 建议..."            │
│   final_trade_decision: "## 最终交易决策\n操作: 买入\n目标价: ¥18.50\n置信度: 0.85\n..." │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.6 阶段 6：后处理

```
┌──────────────────────────────────────────────────────────────────────┐
│ 步骤: SignalProcessor.process_signal(final_trade_decision, "000002")  │
│                                                                      │
│ 输入:                                                                 │
│   full_signal: "## 最终交易决策\n操作: 买入\n目标价: ¥18.50\n..."      │
│   stock_symbol: "000002"                                             │
│                                                                      │
│ 过程:                                                                 │
│   1. StockUtils.get_market_info("000002") → A股, CNY, ¥              │
│   2. LLM 调用（system prompt 要求返回 JSON）                          │
│   3. 正则匹配 JSON: {"action": "买入", "target_price": 18.50, ...}    │
│   4. 验证 action 在中文字典中，target_price 为有效数值                 │
│                                                                      │
│ 输出:                                                                 │
│   {                                                                   │
│     "action": "买入",                                                 │
│     "target_price": 18.50,                                            │
│     "confidence": 0.85,                                               │
│     "risk_score": 0.35,                                               │
│     "reasoning": "房地产龙头估值修复+政策利好+技术面底部放量"           │
│   }                                                                   │
└──────────────────────────────────────────────────────────────────────┘

最终返回:
  propagate() → (final_state, decision)
    final_state: AgentState (完整的状态字典，含所有中间产物)
    decision:    {"action":"买入", "target_price":18.50, ...}
```

### 9.7 各节点读取/写入状态字段的总览表

| 节点 | 读取字段 | 写入字段 |
|---|---|---|
| **Market Analyst** | `trade_date`, `company_of_interest`, `messages`, `market_tool_call_count` | `messages`, `market_report`, `market_tool_call_count` |
| **tools_market** | `messages[-1].tool_calls` | `messages` (追加 ToolMessage) |
| **Msg Clear Market** | `messages` | `messages` (精简) |
| **Fundamentals Analyst** | `trade_date`, `company_of_interest`, `messages`, `fundamentals_tool_call_count` | `messages`, `fundamentals_report`, `fundamentals_tool_call_count` |
| **tools_fundamentals** | `messages[-1].tool_calls` | `messages` (追加 ToolMessage) |
| **Msg Clear Fundamentals** | `messages` | `messages` (精简) |
| **News Analyst** | `trade_date`, `company_of_interest`, `messages`, `news_tool_call_count` | `messages`, `news_report`, `news_tool_call_count` |
| **Social Analyst** | `trade_date`, `company_of_interest`, `messages`, `sentiment_tool_call_count` | `messages`, `sentiment_report`, `sentiment_tool_call_count` |
| **Bull Researcher** | 四份报告, `investment_debate_state` 全部字段, memory | `investment_debate_state` (bull_history, history, current_response, count) |
| **Bear Researcher** | 四份报告, `investment_debate_state` 全部字段, memory | `investment_debate_state` (bear_history, history, current_response, count) |
| **Research Manager** | `company_of_interest`, 四份报告, `investment_debate_state.history`, memory | `investment_debate_state` (judge_decision), `investment_plan` |
| **Trader** | `company_of_interest`, `investment_plan`, 四份报告, memory | `messages`, `trader_investment_plan`, `sender` |
| **Risky/Safe/Neutral Analyst** | `trader_investment_plan`, `risk_debate_state` 全部字段 | `risk_debate_state` (对应 history, latest_speaker, count) |
| **Risk Judge** | `trader_investment_plan`, `risk_debate_state` 全部字段 | `risk_debate_state` (judge_decision), `final_trade_decision` |

### 9.8 关键状态字段的生命周期

```
company_of_interest ──── ◆ ──────────────────────────────── ◆ ────→ 全程不变
trade_date          ──── ◆ ──────────────────────────────── ◆ ────→ 全程不变

market_report       ──── "" ────── ◆ (Market Analyst 写入) ──────→ 之后不变
fundamentals_report ──── "" ────── ◆ (Fund Analyst 写入) ────────→ 之后不变
news_report         ──── "" ────── ◆ (News Analyst 写入) ────────→ 之后不变
sentiment_report    ──── "" ────── ◆ (Social Analyst 写入) ──────→ 之后不变

investment_debate_state.count ── 0 ──→ 1(Bull) ──→ 2(Bear) ──→ 不变
investment_debate_state.history ── "" ──→ Bull发言 ──→ +Bear发言 ──→ 不变
investment_plan     ──── "" ───────────────────── ◆ (Research Mgr) ──→ 不变
trader_investment_plan ─ "" ───────────────────────────── ◆ (Trader) ──→ 不变

risk_debate_state.count ── 0 ──→ 1(Risky) ──→ 2(Safe) ──→ 3(Neutral) ──→ 不变
final_trade_decision ─── "" ───────────────────────────────────── ◆ (Risk Judge)

messages 长度 ── 1 ──→ 增长(工具调用) ──→ 精简(Msg Clear) ──→ 重复 ×4 ──→ 累积(辩论+决策)
```

---

## 10. 关键设计决策与学习要点

### 10.1 双 LLM 模型策略
- **快速模型**（高温度 0.7）：分析师、辩论者、交易员 → 需要多样性和创造力
- **深度模型**（通常更低温度）：研究经理、风险经理 → 需要准确判断

### 10.2 条件边 vs 普通边的选择原则
- **条件边**：下一步有多种可能，取决于当前状态（有无 tool_calls？辩论次数够了没？）
- **普通边**：确定性步骤（分析完 → 开始辩论 → 经理裁决 → 交易员 → 风险评估 → 结束）

### 10.3 死循环防护机制
- 每个分析师独立的 `tool_call_count` 计数器
- 报告长度 > 100 字符的启发式判断
- `max_tool_calls` 硬上限（market/social/news=3, fundamentals=1）
- `recursion_limit=100` 作为 LangGraph 级别的总循环上限

### 10.4 消息清理节点的作用
- 每个分析师在报告完成后执行 `Msg Clear`
- 只保留最终报告文本，删除中间的 tool_call/tool_result 消息
- **目的**：防止上下文窗口溢出，让后续 Agent 看到的上下文更干净

### 10.5 反思与记忆的分离设计
- 反思（`Reflector`）：基于实际回报的 LLM 自省，**事后执行**
- 记忆（`FinancialSituationMemory`）：ChromaDB 向量存储，**跨分析持久化**
- 两者分离的好处：反思逻辑可独立迭代，记忆后端可替换

---

## 11. 面试可能被问到的深度问题

| 问题 | 答案要点 |
|---|---|
| **为什么用 StateGraph 而不是 Chain？** | StateGraph 支持条件分支和循环，适合多 Agent 协作的非线性流程 |
| **ToolNode 是如何工作的？** | LangGraph 预置组件，接收 AIMessage 中的 tool_calls，执行对应函数，返回 ToolMessage |
| **消息清理节点的必要性？** | 防止上下文溢出；让后续 Agent 看到的是"报告摘要"而非"工具调用日志" |
| **辩论轮次如何控制？** | `count` 字段 + `max_debate_rounds` 配置，条件边中硬上限判断 |
| **混合 LLM 厂商模式的挑战？** | 不同厂商 API 差异；通过 `create_llm_by_provider()` 统一工厂 + LangChain 适配层解决 |
| **反思机制和 RAG 的关系？** | 反思生成洞察 → ChromaDB 向量嵌入 → 下次类似情境检索 → 注入决策上下文，正是 RAG 模式 |

---

## 12. 建议动手实验

1. **修改辩论轮次**：在 config 中将 `max_debate_rounds` 从 1 改为 3，观察决策质量变化
2. **添加一个新的分析师**：比如添加一个"Technical Analyst"，体验节点注册和连线流程
3. **修改条件路由逻辑**：在 `ConditionalLogic` 中添加自定义的判断条件（比如基于置信度阈值）
4. **Trace 单个节点的输入输出**：在 debug 模式下打印每个节点的 messages 数量和内容
5. **关闭反思机制**：对比有无记忆的决策质量差异

---

> **下一步**：接下来可以深入学习第 3 天的内容——条件路由与状态传播的细节，或者直接进入第 4 天——逐个分析 5 个分析师 Agent 的实现。
