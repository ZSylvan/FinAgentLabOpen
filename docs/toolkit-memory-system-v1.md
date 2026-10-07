# FinAgentLab Agent 工具集与记忆系统 — 学习文档 v1

> **目标**：理解 Agent 的"手"（Toolkit — 28 个工具）和"脑"（FinancialSituationMemory — ChromaDB 向量记忆），这是 Agent 能感知世界和自我进化的基础设施。
>
> **核心文件**：
> | 文件 | 行数 | 角色 |
> |---|---|---|
> | `agents/utils/agent_utils.py` | 1380 | Toolkit 类 — 28+ 个 `@tool` 方法 + `create_msg_delete` |
> | `agents/utils/memory.py` | 701 | FinancialSituationMemory — ChromaDB + Embedding + 多 LLM 适配 |
> | `agents/utils/google_tool_handler.py` | 751 | Google 模型工具调用统一处理器 |
> | `agents/utils/instrument_utils.py` | 7 | 股票代码约束上下文 |
> | `graph/reflection.py` | 126 | 反思机制（Day 2 已讲，本章仅回顾与记忆系统的关联） |

---

## 1. 先说清楚：Toolkit 在 Agent 架构中的位置

```
                    ┌─────────────────────┐
                    │   LangGraph 工作流    │
                    │                     │
                    │  Market Analyst ────→ toolkit.get_stock_market_data_unified
                    │  Fund Analyst ──────→ toolkit.get_stock_fundamentals_unified
                    │  News Analyst ──────→ toolkit.get_stock_news_unified
                    │  Social Analyst ────→ toolkit.get_stock_sentiment_unified
                    │                     │
                    │  ToolNode ──────────→ toolkit.xxx  (LangGraph 自动执行)
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Toolkit 类         │
                    │   agent_utils.py    │
                    │                     │
                    │   28+ @tool 方法     │
                    │   每个方法:           │
                    │   1. 接收参数        │
                    │   2. 调用 dataflows  │
                    │   3. 返回格式化文本   │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   dataflows/ 层      │
                    │                     │
                    │   interface.py      │ ← 统一入口
                    │   providers/        │ ← A股/港股/美股
                    │   cache/            │ ← 文件/Redis/MongoDB
                    └─────────────────────┘
```

**Toolkit 不是 Agent，是 Agent 的"工具箱"。** Agent（如 Market Analyst）通过 LangChain 的 `bind_tools(tools)` 机制被告知"你可以用这些工具"，然后 LLM 自主决定何时调用哪个工具。

---

## 2. Toolkit 类的设计

### 2.1 类结构

```python
class Toolkit:
    _config = DEFAULT_CONFIG.copy()    # 类级别共享配置

    @classmethod
    def update_config(cls, config):    # 运行时更新配置
        cls._config.update(config)

    def __init__(self, config=None):
        if config:
            self.update_config(config)

    @staticmethod
    @tool
    def get_reddit_news(curr_date: str) -> str:   # 28+ 个工具方法
        ...

    @staticmethod
    @tool
    def get_stock_market_data_unified(ticker, start_date, end_date) -> str:
        ...
```

**三个设计决策**：

1. **`@staticmethod` + `@tool`**：工具方法不需要访问 `self`（配置通过 `Toolkit._config` 类变量访问）。LangChain 的 `@tool` 装饰器要求函数签名干净（参数类型注解 → JSON Schema），用 staticmethod 确保函数是"纯粹的工具"。

2. **类级别配置 `_config`**：所有 Agent 共享同一个配置（LLM 提供商、数据深度级别等），避免每个工具方法各自维护配置。

3. **`@log_tool_call` 装饰器**：几个统一工具（`get_stock_fundamentals_unified` 等）额外套了 `@log_tool_call(tool_name="xxx", log_args=True)` 用于日志记录。这是项目自己的装饰器，位于 `finagentlab/utils/tool_logging.py`。

### 2.2 `@tool` 装饰器详解

```python
from langchain_core.tools import tool

@staticmethod
@tool
def get_reddit_news(
    curr_date: Annotated[str, "Date you want to get news for in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve global news from Reddit within a specified time frame.
    Args:
        curr_date (str): Date you want to get news for in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the latest global news from Reddit
    """
    global_news_result = interface.get_reddit_global_news(curr_date, 7, 5)
    return global_news_result
```

**`@tool` 做了什么？**

LangChain 的 `@tool` 是一个装饰器，它自动完成以下转换：

```
Python 函数                         LLM tool definition (JSON Schema)
══════════════                       ═════════════════════════════════
函数名 →                            "name": "get_reddit_news"
docstring →                         "description": "Retrieve global news from Reddit..."
参数类型注解 Annotated[str, "描述"] →  "parameters": {
                                       "type": "object",
                                       "properties": {
                                         "curr_date": {
                                           "type": "string",
                                           "description": "Date you want to..."
                                         }
                                       },
                                       "required": ["curr_date"]
                                     }
```

**`Annotated[str, "描述"]` 的作用**：Python 的 `typing.Annotated` 允许在类型注解上附加元数据。LangChain 读取这个元数据作为参数的 description，生成 JSON Schema 的 `properties.xxx.description` 字段。这样 LLM 就能理解每个参数的含义。

### 2.3 `@tool` vs `# @tool  # 已移除`：工具的生命周期管理

```python
# 活跃工具（被 Agent 使用）
@staticmethod
@tool
def get_stock_market_data_unified(...):  ...

# 已废弃工具（保留代码但移除 @tool 装饰器）
@staticmethod
# @tool  # 已移除：请使用 get_stock_fundamentals_unified
def get_china_fundamentals(...):  ...

@staticmethod
# @tool  # 已移除：请使用 get_stock_fundamentals_unified 或 get_stock_market_data_unified
def get_china_stock_data(...):  ...
```

注释掉 `@tool` 就意味着这些方法**不再是 LangChain 工具**，LLM 看不到它们，但代码仍然保留（向后兼容、备用调用）。这是"软废弃"而非删除。

---

## 3. 28+ 工具方法全览

### 3.1 按类型分类

| 类别 | 工具方法 | 用途 |
|---|---|---|
| **统一工具（主力）** | `get_stock_market_data_unified` | 三市场通用行情 + 技术指标 |
| | `get_stock_fundamentals_unified` | 三市场通用基本面（PE/PB/ROE/财报） |
| | `get_stock_news_unified` | 三市场通用新闻（东方财富/Google News/Finnhub） |
| | `get_stock_sentiment_unified` | 三市场通用情绪（Reddit/中文社区） |
| **美股新闻** | `get_reddit_news` | Reddit 全球新闻 |
| | `get_finnhub_news` | Finnhub 公司新闻 |
| | `get_google_news` | Google News 搜索 |
| | `get_stock_news_openai` | OpenAI 新闻 API |
| | `get_global_news_openai` | OpenAI 宏观经济新闻 |
| **美股情绪** | `get_reddit_stock_info` | Reddit 个股讨论 |
| | `get_chinese_social_sentiment` | 中国社交平台情绪（雪球/东方财富） |
| **美股数据** | `get_YFin_data` | Yahoo Finance 离线数据 |
| | `get_YFin_data_online` | Yahoo Finance 在线数据 |
| **美股基本面** | `get_finnhub_company_insider_sentiment` | 内部人情绪（SEC 数据） |
| | `get_finnhub_company_insider_transactions` | 内部人交易（SEC 数据） |
| | `get_simfin_balance_sheet` | SimFin 资产负债表 |
| | `get_simfin_cashflow` | SimFin 现金流 |
| | `get_simfin_income_stmt` | SimFin 利润表 |
| **技术指标** | `get_stockstats_indicators_report` | 技术指标分析（离线） |
| | `get_stockstats_indicators_report_online` | 技术指标分析（在线） |
| **A股专用** | `get_china_stock_data` | A 股行情（已软废弃） |
| | `get_china_market_overview` | 中国大盘概览 |
| | `get_china_fundamentals` | A 股基本面（已软废弃） |
| **实时新闻** | `get_realtime_stock_news` | 15-30 分钟内的最新新闻 |
| **港股** | `get_hk_stock_data_unified` | 港股统一数据（AKShare/Yahoo 回退） |
| **已废弃** | `get_fundamentals_openai` | 旧版 OpenAI 基本面（已软废弃） |

### 3.2 统一工具的设计思想

四个 `_unified` 工具是项目架构演进的终点：把"By Market"的分支逻辑从 Agent Prompt 层面下沉到工具代码层面。

```
旧设计: Agent 需要自己判断"这是 A 股，用 AKShare；这是美股，用 YFinance"
        → Agent Prompt 里要写大量分支指令
        → 不同 LLM 理解能力不同，容易出错

新设计: Agent 只需要调用 get_stock_market_data_unified(ticker, start, end)
        → 工具内部自动判断股票类型、选择数据源、做回退
        → Agent Prompt 简洁，LLM 不易出错
```

统一工具的三市场分支（以 `get_stock_market_data_unified` 为例）：

```python
if is_china:
    from finagentlab.dataflows.interface import get_china_stock_data_unified
    stock_data = get_china_stock_data_unified(ticker, start_date, end_date)
elif is_hk:
    from finagentlab.dataflows.interface import get_hk_stock_data_unified
    hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)
else:  # 美股
    from finagentlab.dataflows.providers.us.optimized import get_us_stock_data_cached
    us_data = get_us_stock_data_cached(ticker, start_date, end_date)
```

### 3.3 `get_stock_fundamentals_unified` 的五级分析深度

```python
if research_depth == "快速":   data_depth = "basic"
elif research_depth == "基础":  data_depth = "standard"
elif research_depth == "标准":  data_depth = "standard"
elif research_depth == "深度":  data_depth = "full"
elif research_depth == "全面":  data_depth = "comprehensive"
```

这是用户可配置的分析深度参数，影响工具获取的数据量和分析模块数量：

| 级别 | analysis_modules | 效果 |
|---|---|---|
| 快速 | basic | 仅基础财务指标 |
| 基础/标准 | standard | 标准财务分析 |
| 深度 | full | 完整基本面分析 |
| 全面 | comprehensive | 最全面的综合分析 |

**实现注意**：数字等级（1-5）也可以自动映射为中文等级，这是为了兼容前端传过来的数值参数。

---

## 4. `create_msg_delete()` — 消息清理机制

### 4.1 代码

```python
def create_msg_delete():
    def delete_messages(state):
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages
```

### 4.2 `RemoveMessage` 是什么？

`RemoveMessage` 是 LangGraph 内置的特殊消息类型。当节点的返回 dict 的 `messages` 字段中包含 `RemoveMessage` 时，LangGraph 的消息 reducer 会**从消息列表中删除**对应 id 的消息：

```python
# LangGraph 内部逻辑（简化版）
for item in node_return["messages"]:
    if isinstance(item, RemoveMessage):
        state["messages"].remove_by_id(item.id)   # 删除
    else:
        state["messages"].append(item)             # 追加
```

所以 `[RemoveMessage(id=m.id) for m in messages]` 的效果是：**删除消息列表中的所有消息**。

### 4.3 为什么删除后还要加 `HumanMessage(content="Continue")`？

这是为了 **Anthropic Claude 兼容性**。Claude API 要求消息列表不能为空（至少要有 1 条消息），且最后一条消息必须是 user 角色。加一个空的 `HumanMessage(content="Continue")` 满足这个约束，同时也给下一个 Agent 一个"继续执行"的信号。

### 4.4 消息清理的时间点

从图结构看，每个分析师结束后都会走 `Msg Clear` 节点：

```
Market Analyst → Msg Clear Market → Fundamentals Analyst → Msg Clear Fundamentals → ...
```

这确保：
- 每个分析师看到的 `messages` 都很短（只有上一条清理后的残量 + 当前分析师的交互）
- 不会出现消息列表无限膨胀的问题
- 四个分析报告已被写入**独立字段**（`market_report` 等），后续 Agent 不依赖 messages 中的历史

---

## 5. FinancialSituationMemory — 金融情境记忆系统

这是项目中最复杂的单个模块之一（701 行），核心是 **ChromaDB 向量数据库 + 多 LLM 提供商的 Embedding 适配**。

### 5.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│             FinancialSituationMemory                     │
│                                                         │
│  add_situations([(situation, advice), ...])             │
│  ┌──────────────────────────────────────────┐           │
│  │ 1. 对每个 situation 调用 get_embedding() │           │
│  │ 2. 存入 ChromaDB:                        │           │
│  │    - documents: [situation]              │           │
│  │    - embeddings: [向量]                  │           │
│  │    - metadatas: [{"recommendation": advice}]│        │
│  └──────────────────────────────────────────┘           │
│                                                         │
│  get_memories(current_situation, n_matches=2)           │
│  ┌──────────────────────────────────────────┐           │
│  │ 1. get_embedding(current_situation)     │           │
│  │ 2. ChromaDB.query(embedding, n_results) │           │
│  │ 3. 返回相似度排序的记忆列表               │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

这是标准的 **RAG（检索增强生成）** 架构：
- **存入**：情境 → 向量嵌入 → ChromaDB 存储
- **检索**：当前情境 → 向量嵌入 → ChromaDB 相似搜索 → 返回历史反思 → 注入 Prompt

### 5.2 Embedding 的多 LLM 适配策略

项目需要支持十几种 LLM 提供商，但并不是每个都有 Embedding API。记忆系统采用**回退链**策略：

```
首选: 阿里百炼 DashScope (text-embedding-v3)
  │
  ├── 千帆/文心一言 → 没有自己的 Embedding → 回退到 DashScope
  ├── DeepSeek → 尝试 DashScope → 不行就 OpenAI (text-embedding-3-small)
  ├── Google AI → DashScope（带 OpenAI 降级）
  ├── OpenRouter → DashScope
  ├── Ollama (localhost) → nomic-embed-text
  └── 默认 → OpenAI text-embedding-3-small

所有路径都失败 → self.client = "DISABLED" → 返回零向量 → 记忆功能静默降级
```

**关键设计决策**：记忆功能降级时**不抛异常**，而是返回 `[0.0] * 1024`（1024 维零向量）。`get_memories()` 检测到零向量后返回空列表 `[]`。这让整个系统在记忆不可用时**优雅降级**——决策质量下降但不中断。

### 5.3 `ChromaDBManager` — 单例模式

```python
class ChromaDBManager:
    _instance = None
    _lock = threading.Lock()
    _collections: Dict[str, any] = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

**为什么用单例？** ChromaDB 的 `create_collection` 不是幂等的——并发创建同名集合会报错。单例 + 线程锁确保：
1. 整个进程只有 1 个 ChromaDB 客户端
2. 集合创建/获取是线程安全的
3. 已创建的集合被缓存在 `_collections` dict 中

### 5.4 五个独立记忆实例

```python
# trading_graph.py: __init__
self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)
```

每个实例对应 ChromaDB 中的一个**独立集合**（collection），数据完全隔离。

**为什么 5 个独立记忆？** 因为在 Day 5 中分析过的：同一回报数据，Bull 认为是教训、Bear 认为是成功。混在一起会导致语义混乱。

### 5.5 记忆的写入路径（Reflection → Memory）

回顾 `reflection.py` 的调用链：

```python
# reflection.py
def reflect_bull_researcher(self, current_state, returns_losses, bull_memory):
    # 1. 拼接四份报告为 situation
    situation = f"{market_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

    # 2. 用 LLM 做反思分析（分析 Bull 为什么对了/错了）
    result = llm.invoke([
        ("system", reflection_system_prompt),
        ("human", f"Returns: {returns_losses}\n\nAnalysis/Decision: {bull_history}\n\nContext: {situation}")
    ])

    # 3. 把 (情境, 反思) 存入 ChromaDB
    bull_memory.add_situations([(situation, result)])
```

一次反思产生一个 `(situation, reflection_result)` 元组存入 ChromaDB。

### 5.6 记忆的检索路径（Memory → Agent）

在 Bull Researcher 的 Prompt 中：

```python
curr_situation = f"{market_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
past_memories = memory.get_memories(curr_situation, n_matches=2)

past_memory_str = ""
for rec in past_memories:
    past_memory_str += rec["recommendation"] + "\n\n"

prompt = f"""...类似情况的反思和经验教训：{past_memory_str}
你还必须处理反思并从过去的经验教训和错误中学习。"""
```

**注意**：这里的 `curr_situation` 和写入时的 `situation` 完全相同（四份报告的拼接）。这意味着检索是**同构匹配**——"当前的四份报告" vs "历史上的四份报告"的向量相似度。

---

## 6. GoogleToolCallHandler — Google 模型的适配层

### 6.1 为什么需要这个模块？

Google Gemini 的 API 行为与其他模型有差异：

| 行为 | OpenAI/其他 | Google Gemini |
|---|---|---|
| `result.content` 有 tool_calls 时 | 通常为空字符串 `""` | **可能为空**（不一定生成文本），也可能**直接输出分析文本** |
| tool_calls 格式 | 标准的 `{"name": ..., "args": {...}, "id": "..."}` | 可能格式不同（需要 `_validate_tool_call` + `_fix_tool_call`） |
| 消息序列要求 | 宽松 | 对消息顺序和格式更敏感 |

`GoogleToolCallHandler` 封装了所有 Google 模型的特殊处理逻辑，让 5 个分析师只需统一调用：

```python
if GoogleToolCallHandler.is_google_model(llm):
    report, messages = GoogleToolCallHandler.handle_google_tool_calls(...)
```

### 6.2 核心方法 `handle_google_tool_calls()` 的流程

```
输入: result (AIMessage), llm, tools, state
│
├─ [检查 1] 是 Google 模型吗？ → 不是 → 直接返回 result.content
│
├─ [检查 2] 有 tool_calls 吗？
│   ├─ 有 tool_calls:
│   │   ├─ 验证每个 tool_call (_validate_tool_call)
│   │   ├─ 尝试修复格式错误的 tool_call (_fix_tool_call)
│   │   ├─ 手动执行每个 tool (防止重复调用)
│   │   ├─ 构建精简的消息序列 (不累积历史)
│   │   ├─ 第二次 LLM 调用 (基于工具结果生成报告)
│   │   └─ 返回 (报告, [原始AIMsg + ToolMsgs + 最终AIMsg])
│   │
│   └─ 无 tool_calls:
│       ├─ 检查 result.content 是否看起来像分析报告 (长度>200 + 3+关键词)
│       ├─ 是 → 直接用当报告
│       └─ 否 → 返回原始内容
│
└─ 所有失败 → 降级报告 (基于工具结果的简单摘要)
```

### 6.3 工具调用的验证和修复

```python
@staticmethod
def _validate_tool_call(tool_call, index, analyst_name):
    # 检查: 是 dict 格式? 有 name/args/id 字段? name 非空? args 是 dict? id 有效?
    ...

@staticmethod
def _fix_tool_call(tool_call, index, analyst_name):
    # 尝试修复 OpenAI 格式 → LangChain 标准格式
    # {"function": {"name": "xxx", "arguments": "{\"ticker\":\"AAPL\"}"}}
    # → {"name": "xxx", "args": {"ticker": "AAPL"}, "id": "call_abc123"}
    ...
```

### 6.4 重复工具调用的去重

```python
executed_tools = set()
for tool_call in tool_calls:
    tool_signature = f"{tool_name}_{hash(str(tool_args))}"
    if tool_signature in executed_tools:
        logger.warning(f"跳过重复工具调用: {tool_name}")
        continue
    executed_tools.add(tool_signature)
```

Google 模型有时会在单次响应中生成**重复的 tool_calls**（相同工具 + 相同参数），这个方法防止重复执行。

---

## 7. `instrument_utils.py` — 股票代码约束

```python
def build_instrument_context(ticker: str) -> str:
    return (
        f"当前分析标的的精确股票代码是 `{ticker}`。"
        "在所有工具调用、分析报告、交易建议和最终结论中，"
        "都必须使用这个完全一致的股票代码。"
        "如果代码带有交易所后缀，例如 `.HK`、`.TO`、`.L`、`.T`，"
        "必须原样保留，绝对不能省略、改写或替换。"
    )
```

这个 7 行的函数看似简单，但解决了 LLM 的一个常见问题：**股票代码篡改**。LLM 有时会"自作聪明"地去掉 `.HK` 后缀或将 `000002.SZ` 改为 `000002`，导致后续数据查询失败。把这个约束**硬编码到每个 Prompt 的开头**是最直接有效的解决方案。

---

## 8. 完整数据流：从工具调用到记忆闭环

```
[分析阶段]
Market Analyst → toolkit.get_stock_market_data_unified()
                   → interface.py → providers/china/akshare.py
                   → 返回: "当前价 ¥15.23, PE: 8.5, MACD: ..."
                   → 写入 state.market_report

[决策阶段]
Bull Researcher → memory.get_memories(curr_situation, n_matches=2)
                   → get_embedding(curr_situation)
                   → ChromaDB.query(embedding)
                   → 返回: [{"recommendation": "上次类似情境中高估了政策利好...", "similarity": 0.87}]
                   → 注入 Prompt
                   → llm.invoke(prompt)
                   → 写入 investment_debate_state

[反思阶段]（事后，非实时）
用户获得实际回报 returns_losses
    → reflector.reflect_bull_researcher(state, returns_losses, bull_memory)
    → LLM 反思: "这次看涨失败的原因是对政策收紧信号反应不够快"
    → bull_memory.add_situations([(curr_situation, reflection)])
    → 存入 ChromaDB（下次分析可用）
```

---

## 9. 面试追问

| 问题 | 答题要点 |
|---|---|
| **`@tool` 装饰器的原理？** | 把 Python 函数转为 LangChain Tool 对象：函数名→name、docstring→description、Annotated 参数类型→JSON Schema 的 properties |
| **为什么 Embedding 要支持多个提供商？** | LLM 和 Embedding 可能不是同一家（用户用 DeepSeek 做推理但用阿里百炼做向量化），需要灵活组合 |
| **记忆功能降级的设计哲学？** | 优雅降级：记忆不可用 → 返回空向量 → 返回空记忆列表 → Agent 仍能工作（只是没有历史经验参考）。宁可少一个功能，不中断主流程 |
| **为什么 5 个独立记忆而不是 1 个共享？** | 同一回报数据对不同角色的含义相反（Bull 的教训 = Bear 的成功），共享会造成语义污染 |
| **`create_msg_delete` 为什么加 `HumanMessage("Continue")`？** | Anthropic 兼容性：Claude API 要求最后一条消息必须是 user 角色。`"Continue"` 满足约束且不产生实质性影响 |
| **统一工具 vs 分散工具的权衡？** | 统一工具降低 Agent Prompt 复杂度（LLM 不需要判断市场类型），但工具代码变复杂（内部 if-else）；是一种"把复杂性从 Prompt 移到代码"的策略 |

---

## 10. 建议动手实验

1. **追踪一个工具的完整调用链**：从 Market Analyst 的 `chain.invoke()` → LLM 返回 tool_calls → `get_stock_market_data_unified` 执行 → `interface.py` → `akshare.py` → 返回数据 → 写入 `market_report`
2. **禁用记忆功能观察决策差异**：`memory_enabled=False`，对同一只股票做两次分析，对比第一次和第二次的决策是否有差异（正常应该是没记忆=每次都一样，有记忆=第二次可能受第一次反思影响）
3. **添加一个新工具**：在 Toolkit 中加一个 `get_industry_comparison` 方法，用 `@tool` 装饰，注册到某个分析师的 tools 列表，验证 LLM 是否会调用它
4. **测试记忆的多 LLM 适配**：分别用 DeepSeek 和 OpenAI 运行，观察 ChromaDB 中 embedding 的维度和质量
5. **截断测试**：构造一个超长的 situation（>50K 字符），观察 `get_embedding` 的截断或跳过逻辑

---

> **上一文档**：[辩论与决策层](debate-decision-layer-v1.md) — Day 5
>
> **下一步**：Day 7 — FastAPI 启动流程 + 中间件（`app/main.py` + `app/middleware/*.py`），进入第 2 周后端工程阶段
