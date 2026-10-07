# FinAgentLab 分析师 Agent 详解 — 学习文档 v1

> **目标**：逐个读懂 5 个分析师 Agent 的实现，理解它们的共性模式和各自的特殊设计。
>
> **核心文件**（均位于 `finagentlab/agents/analysts/`）：
> | 文件 | 行数 | 角色 | 绑定工具数 | max_tool_calls |
> |---|---|---|---|---|
> | `market_analyst.py` | 511 | 市场行情/技术分析 | 1（统一工具） | 3 |
> | `fundamentals_analyst.py` | 698 | 基本面/财务分析 | 1（统一工具） | 1 |
> | `news_analyst.py` | 413 | 新闻事件/情绪分析 | 1（统一工具） | 3 |
> | `social_media_analyst.py` | 234 | 社交媒体舆情分析 | 1（统一工具） | 3 |
> | `china_market_analyst.py` | 291 | A 股专用深度分析 | 3（多功能） | 无独立计数器 |

---

## 1. 所有分析师共享的代码骨架

在深入每个分析师之前，先理解他们**共同遵循的模板**：

```python
def create_xxx_analyst(llm, toolkit):
    """工厂函数：接收 LLM 实例和 Toolkit，返回一个 LangGraph 节点函数"""

    def xxx_analyst_node(state: AgentState) -> dict:
        # ═══════════════════════════════════════════════
        # 阶段 1: 读取状态 — 从 state 中提取需要的字段
        # ═══════════════════════════════════════════════
        tool_call_count = state.get("xxx_tool_call_count", 0)
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # ═══════════════════════════════════════════════
        # 阶段 2: 股票识别 — 获取市场信息 + 公司名称
        # ═══════════════════════════════════════════════
        market_info = StockUtils.get_market_info(ticker)
        company_name = _get_company_name(ticker, market_info)

        # ═══════════════════════════════════════════════
        # 阶段 3: 工具选择 — 选择合适的工具
        # ═══════════════════════════════════════════════
        tools = [toolkit.get_xxx_unified]

        # ═══════════════════════════════════════════════
        # 阶段 4: Prompt 构造 — 系统提示 + 模板变量
        # ═══════════════════════════════════════════════
        system_message = (...)  # 角色定位 + 分析要求 + 输出格式
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        prompt = prompt.partial(tool_names=..., ticker=..., company_name=..., ...)

        # ═══════════════════════════════════════════════
        # 阶段 5: LLM 调用 — chain = prompt | llm.bind_tools(tools)
        # ═══════════════════════════════════════════════
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke({"messages": state["messages"]})

        # ═══════════════════════════════════════════════
        # 阶段 6: 结果处理 — Google 模型 vs 标准模型
        # ═══════════════════════════════════════════════
        if GoogleToolCallHandler.is_google_model(llm):
            report, messages = GoogleToolCallHandler.handle_google_tool_calls(...)
        else:
            if len(result.tool_calls) == 0:
                report = result.content      # LLM 直接输出文本
            else:
                # 执行工具 → 拼接结果 → 二次 LLM 调用 → 生成报告

        # ═══════════════════════════════════════════════
        # 阶段 7: 写入状态 — 返回增量 dict
        # ═══════════════════════════════════════════════
        return {
            "messages": [result],
            "xxx_report": report,
            "xxx_tool_call_count": tool_call_count + 1,
        }

    return xxx_analyst_node
```

**为什么用工厂函数 `create_xxx_analyst(llm, toolkit)` 而非直接定义函数？**
- `llm` 和 `toolkit` 在运行时才确定（用户可能切换 LLM 提供商）
- 工厂函数**捕获**这些依赖到闭包中，返回的节点函数签名干净（只接受 `state`）
- 这是**依赖注入**的一种轻量实现

---

## 1B. 核心代码详解：`chain = prompt | llm.bind_tools(tools)` 和 `chain.invoke(...)`

这两个语句是所有分析师 Agent 真正"调用 LLM"的地方，理解它们对于理解整个项目至关重要。

### 1B.1 先理解 `|` 操作符 — LCEL（LangChain Expression Language）

`|` 是 LangChain 的核心设计：**管道操作符**。它把多个组件串成一个链。

```python
chain = prompt | llm.bind_tools(tools)
#        ^^^^^^   ^^^^^^^^^^^^^^^^^^^^
#        组件A         组件B
#
# 语义: 组件A 的输出 → 自动成为 组件B 的输入
```

**底层原理**：LangChain 的 `Runnable` 协议。

LangChain 中所有组件（`ChatPromptTemplate`、`ChatOpenAI`、`bind_tools` 返回的对象等）都实现了 `Runnable` 接口。`Runnable` 协议定义了两个核心方法：

```python
class Runnable:
    def invoke(self, input: dict) -> Any:      # 同步执行
        ...

    def __or__(self, other: Runnable) -> RunnableSequence:  # 管道连接
        return RunnableSequence(self, other)
```

`__or__` 是 Python 的魔术方法，当你写 `A | B` 时 Python 自动调用 `A.__or__(B)`。

所以：
```python
chain = prompt | llm.bind_tools(tools)
# 等价于
chain = RunnableSequence(prompt, llm.bind_tools(tools))
```

**管道的数据流向**：
```
输入 dict ──→ prompt ──→ 格式化后的消息列表 ──→ llm.bind_tools(tools) ──→ AIMessage
             (ChatPromptTemplate)              (绑定了工具的 ChatModel)
```

### 1B.2 第一个组件：`ChatPromptTemplate`（prompt）

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一位专业的股票技术分析师...当前日期：{current_date}..."),
    MessagesPlaceholder(variable_name="messages"),
])

prompt = prompt.partial(current_date="2025-07-04", ticker="000002", ...)
```

**`ChatPromptTemplate.from_messages()` 做了什么？**

它创建了一个**消息模板对象**，定义 LLM 输入的结构：

| 参数 | 类型 | 作用 |
|---|---|---|
| `("system", "...")` | 元组 | 系统提示词模板，可含 `{variable}` 占位符 |
| `MessagesPlaceholder(variable_name="messages")` | 占位符 | 运行时把 `state["messages"]` 的消息列表**展开插入**到这个位置 |

**`prompt.partial()` 做了什么？**

**部分填充**模板变量。每次 `.partial(key=value)` 返回一个新对象，填充掉一个变量：

```python
# 原始模板中有 {current_date}, {ticker}, {company_name}, {tool_names} 等占位符
prompt = prompt.partial(current_date="2025-07-04")   # 填充 current_date
prompt = prompt.partial(ticker="000002")              # 填充 ticker
prompt = prompt.partial(company_name="万科A")          # 填充 company_name
# ... 填充完所有占位符后，模板中只剩下 {messages} 这个 MessagesPlaceholder
```

**为什么用 `partial()` 而不是直接传参？**

`partial()` 是**分步填充**：先填已知的配置值（日期、股票代码、公司名），最后 `invoke()` 时再传入唯一剩余的 `messages`。这是一种**柯里化 (currying)** 模式：把一个多参数函数逐步固定参数，变成单参数函数。

### 1B.3 第二个组件：`llm.bind_tools(tools)`

```python
llm.bind_tools(tools)
```

`llm` 是一个 `ChatOpenAI` 实例（或 `ChatAnthropic`、`ChatGoogleOpenAI` 等）。

**`bind_tools()` 方法干了什么？**

它是一个 LangChain ChatModel 方法，将工具列表"绑定"到 LLM 上：

```python
# 伪代码表示 bind_tools 的效果
class ChatOpenAI:
    def bind_tools(self, tools: list) -> ChatOpenAI:
        """
        返回一个新的 ChatModel 实例，其每次调用都会自动在 API 请求中
        携带 tools 参数（即 OpenAI 的 function calling / tool use 能力）
        """
        new_instance = self.copy()
        new_instance.tools = self._format_tools_for_api(tools)
        return new_instance
```

**实际效果**：当你调用 `bind_tools(tools)` 后：

1. LangChain 检查每个 tool 的函数签名（参数名、类型、描述）
2. 将它们转换为 LLM API 要求的 JSON Schema 格式
3. 之后的每次 `invoke()`，请求 body 中都会包含 `"tools": [...]` 字段
4. LLM 可以选择**返回文本**（无 tool_calls）或**返回 tool_calls**（要求调用工具）

**举例**：假设 `tools = [toolkit.get_stock_market_data_unified]`，转化后的 API 请求大致为：

```json
{
  "model": "gpt-4",
  "messages": [...],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_stock_market_data_unified",
        "description": "获取股票市场行情数据，自动识别A股/港股/美股...",
        "parameters": {
          "type": "object",
          "properties": {
            "ticker": {"type": "string", "description": "股票代码"},
            "start_date": {"type": "string", "description": "起始日期"},
            "end_date": {"type": "string", "description": "结束日期"}
          },
          "required": ["ticker", "start_date", "end_date"]
        }
      }
    }
  ]
}
```

LLM 的两种可能响应：

```
情况 A: LLM 认为需要数据
→ AIMessage(
    content="",                           # 空文本
    tool_calls=[{                         # 要求调用工具
      "name": "get_stock_market_data_unified",
      "args": {"ticker": "000002", "start_date": "2024-07-04", "end_date": "2025-07-04"},
      "id": "call_abc123"
    }]
  )

情况 B: LLM 认为不需要数据/已有足够信息
→ AIMessage(
    content="## 万科A 技术分析报告\n当前价格：¥15.23...",  # 直接输出文本
    tool_calls=[]                          # 空列表
  )
```

### 1B.4 管道的数据流完整演示

把两者串起来，一次完整的 `chain.invoke()` 过程：

```python
chain = prompt | llm.bind_tools(tools)
result = chain.invoke({"messages": state["messages"]})
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ 步骤 1: prompt.invoke({"messages": state["messages"]})              │
│                                                                     │
│ 输入:                                                                │
│   {"messages": [HumanMessage("请对股票 000002 进行全面分析...")]}     │
│                                                                     │
│ ChatPromptTemplate 操作:                                             │
│   1. 从 partial() 中取出已填充的变量:                                  │
│      current_date="2025-07-04", ticker="000002", company_name="万科A" │
│      tool_names="get_stock_market_data_unified", ...                │
│   2. 将 system 模板中的 {variable} 替换为实际值                        │
│   3. MessagesPlaceholder 处，展开 state["messages"] 的消息列表          │
│                                                                     │
│ 输出:                                                                │
│   [                                                                 │
│     SystemMessage("你是一位专业的股票技术分析师...                       │
│                    当前日期：2025-07-04...                            │
│                    可用工具：get_stock_market_data_unified..."),     │
│     HumanMessage("请对股票 000002 进行全面分析...")                    │
│   ]                                                                 │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ 管道: 输出自动传给下一个组件
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 步骤 2: llm.bind_tools(tools).invoke([SystemMessage, HumanMessage]) │
│                                                                     │
│ 1. 将消息列表 + tools JSON Schema 打包为 API 请求                     │
│ 2. 发送 HTTP POST 到 LLM API（如 https://api.openai.com/v1/chat/...） │
│ 3. 等待 LLM 返回响应                                                 │
│ 4. 将 API 响应包装为 AIMessage 对象                                   │
│                                                                     │
│ 输出:                                                                │
│   AIMessage(                                                        │
│     content="",                                                     │
│     tool_calls=[{"name":"get_stock_market_data_unified", ...}]      │
│   )                                                                 │
│   → 赋值给 result                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1B.5 `chain.invoke()` vs `chain.stream()` vs `chain.batch()`

LangChain Runnable 提供了三种执行方式：

| 方法 | 行为 | 本项目中的使用 |
|---|---|---|
| `chain.invoke(input)` | **同步执行**，等待完成后返回完整结果 | 所有分析师 Agent 内部使用 |
| `chain.stream(input)` | **流式执行**，逐 token 返回 | `FinAgentLabGraph.propagate()` 使用 `graph.stream()` |
| `chain.batch([input1, input2])` | **批量并发**，多个输入同时处理 | 本项目未使用 |

`invoke()` 方法签名：
```python
def invoke(self, input: dict, config: dict | None = None) -> Any:
    """
    Args:
        input:  输入数据 dict，key 必须匹配 prompt 中剩余的未填充变量
                （本例中只剩 "messages" 未填充，所以必须传 {"messages": ...}）
        config: 可选的运行时配置（callback、tags、metadata 等）
    Returns:
        链的最终输出（本例中是 AIMessage 对象）
    """
```

**为什么 `invoke` 传的是 `{"messages": state["messages"]}` 而不是直接传 `state["messages"]`？**

因为 `ChatPromptTemplate` 需要**按变量名匹配**。模板中有一个 `MessagesPlaceholder(variable_name="messages")`，它期望从 invoke 的 dict 中查找 key `"messages"`。如果直接传 `state["messages"]`（一个 list），LangChain 不知道这个 list 对应哪个占位符。

### 1B.6 一个常见误解：`bind_tools` 不执行工具

```python
chain = prompt | llm.bind_tools(tools)
result = chain.invoke(...)
# result 是 AIMessage，可能包含 tool_calls，但工具尚未被执行！
```

**`bind_tools` 只是告知 LLM "你可以调用这些工具"，并不自动执行工具**。工具执行是另外的步骤：

```python
# 选项 1: LangGraph 的 ToolNode 执行（自动）
# setup.py 中注册了 tools_market 节点 → 条件路由自动跳转

# 选项 2: Market Analyst 节点内手动执行（如 market_analyst.py 所示）
for tool_call in result.tool_calls:
    tool_result = tool.invoke(tool_args)
    tool_messages.append(ToolMessage(content=str(tool_result), ...))
```

这两种方式在本项目中**同时存在**：Market Analyst 用方式 2，Social/News Analyst 用方式 1，Fundamentals Analyst 两种都用。

### 1B.7 一句话总结

```
chain = prompt | llm.bind_tools(tools)
result = chain.invoke({"messages": state["messages"]})

等价于人类语言:

"把系统指令和对话历史格式化为消息列表，
 发送给一个知道可以调用哪些工具的 LLM，
 等它返回结果（可能是文本，也可能是要求调用某个工具）。"
```

---

## 2. Market Analyst（市场分析师）— 最完整的参考实现

### 2.1 工具选择

```python
tools = [toolkit.get_stock_market_data_unified]
```

只绑定 **1 个工具**，但这个统一工具内部覆盖了 A 股/港股/美股三条路径。

### 2.2 核心 Prompt 结构

Market Analyst 的 Prompt 设计最为完整，分为四个区域：

```
┌─────────────────────────────────────────┐
│ 📋 分析对象（模板变量注入）              │
│   公司名称、股票代码、市场、货币、日期    │
├─────────────────────────────────────────┤
│ 🔧 工具使用（工作流指令）                │
│   1. 无 ToolMessage → 立即调用工具       │
│   2. 有 ToolMessage → 立即生成报告       │
│   3. 不重复调用工具                      │
├─────────────────────────────────────────┤
│ 📝 输出格式要求（模板式标题）             │
│   ## 📊 股票基本信息                     │
│   ## 📈 技术指标分析                     │
│   ## 📉 价格趋势分析                     │
│   ## 💭 投资建议                         │
├─────────────────────────────────────────┤
│ ⚠️ 重要提醒（约束条件）                  │
│   使用中文、使用正确货币、不越权给最终建议│
└─────────────────────────────────────────┘
```

### 2.3 工具执行 + 二次 LLM 调用的细节

```python
if len(result.tool_calls) == 0:
    report = result.content        # 路径 A: LLM 直接输出（无工具调用）
else:
    # 路径 B: 有工具调用
    # B1. 手动执行每个 tool_call
    for tool_call in result.tool_calls:
        tool_result = tool.invoke(tool_args)
        tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))

    # B2. 构造二次分析 Prompt（包含工具数据 + 格式要求）
    analysis_prompt = f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。
    **输出格式要求（必须严格遵守）：**
    # **{company_name}（{ticker}）技术分析报告**
    ## 一、股票基本信息
    ## 二、技术指标分析
    ## 三、价格趋势分析
    ## 四、投资建议
    ...
    """

    # B3. 拼接消息序列: 历史消息 + AIMessage(tool_calls) + ToolMessages + HumanMessage(分析指令)
    messages = state["messages"] + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]

    # B4. 第二次 LLM 调用（不绑定工具），生成最终报告
    final_result = llm.invoke(messages)
    report = final_result.content

    # B5. 返回 3 个消息：tool_calls + tool_results + final_report
    return {
        "messages": [result] + tool_messages + [final_result],
        "market_report": report,
        "market_tool_call_count": tool_call_count + 1
    }
```

**为什么 Market Analyst 在节点内部手动执行工具（而不全靠 LangGraph 的 ToolNode）？**

这是一个**双路径设计**：
- **路径 B（工具路径）**：在节点内手动执行工具 → 立即用第二次 LLM 调用生成格式化报告 → 返回最终报告 + 完整的消息序列 → 条件路由检测到 `len(report) > 100` → 直接到 Msg Clear
- **路径 A（无工具）**：LLM 直接输出文本 → 同样检测到 report 已完成 → 直接到 Msg Clear

这样做的效果是：**工具调用和报告生成在同一个节点内完成**，不需要通过条件边 `→ tools_market → Market Analyst（第二轮）`。这减少了图节点跳转次数，但代码复杂度更高。

**结果**：Market Analyst 实际上**可能只执行一次图节点**就完成分析（如果 LLM 第一次就调用了工具），而循环路径只在 LLM 不调用工具时才触发。

### 2.4 报告长度 > 100 的"完成"判断

Market Analyst 写入的 `market_report` 是格式化后的完整报告（约 2000+ 字符），远超 100 字符阈值。条件路由读到后直接跳往 Msg Clear。

---

## 3. Fundamentals Analyst（基本面分析师）— 最复杂的防御设计

Fundamentals Analyst 是五个分析师中**代码最长、防御逻辑最多**的，原因在于基本面数据获取的特殊性：一次工具调用应该获取全部数据，LLM 不应该重复调用。

### 3.1 独特的计数器更新方式

```python
# 与其他分析师不同的地方：通过 ToolMessage 数量推断调用次数
messages = state.get("messages", [])
tool_message_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))
tool_call_count = state.get("fundamentals_tool_call_count", 0)

# 如果检测到新的 ToolMessage，更新计数器
if tool_message_count > tool_call_count:
    tool_call_count = tool_message_count
```

**为什么不用简单的 `+1`？** 因为 Fundamentals Analyst 有多个返回路径（正常流程、强制报告生成、强制工具调用），每个路径的计数逻辑不同。通过直接统计 ToolMessage 数量来推断调用次数更可靠。

### 3.2 三层防御体系

```
┌────────────────────────────────────────────────────────────────┐
│ 第一层: 检测已有 ToolMessage                                    │
│   if has_tool_result and len(result.tool_calls) > 0:          │
│       → 工具已返回数据，但 LLM 仍想调用工具                     │
│       → 强制生成报告（用不含工具的 prompt 重新调用 LLM）         │
│       → 返回 fundamentals_report，不新增 tool_call             │
├────────────────────────────────────────────────────────────────┤
│ 第二层: 检测 tool_call_count 超限                               │
│   elif tool_call_count >= max_tool_calls (1):                 │
│       → 达到上限但无工具结果（异常）                             │
│       → 返回简化的 fallback 报告                                │
├────────────────────────────────────────────────────────────────┤
│ 第三层: 正常首次调用                                             │
│   else:                                                        │
│       → 返回 AIMessage(tool_calls)，让 LangGraph ToolNode 执行   │
│       → 计数器不在这里递增！（等下次进入节点时统计 ToolMessage）  │
└────────────────────────────────────────────────────────────────┘
```

**注意返回差异**：
- 正常首次调用返回 `{"messages": [result]}` — **没有 `fundamentals_report` 字段**
- 第二次进入时 ToolMessage 已存在 → 进入第一层 → 返回 `{"fundamentals_report": report}`
- 这意味着 Fundamentals Analyst **至少执行 2 次图节点**才能完成

### 3.3 多路径返回汇总

```python
# 路径 A: Google 模型 → 统一处理器 → 直接返回报告
return {"fundamentals_report": report}

# 路径 B: 有 tool_calls + 已有 ToolMessage → 强制生成报告
return {
    "fundamentals_report": report,
    "messages": [force_result],
    "fundamentals_tool_call_count": tool_call_count
}

# 路径 C: 有 tool_calls + 无 ToolMessage + 未超限 → 等待工具执行
return {"messages": [result]}    # ⚠️ 注意: 没有 fundamentals_report!

# 路径 D: 有 tool_calls + 无 ToolMessage + 已超限 → fallback
return {
    "messages": [result],
    "fundamentals_report": fallback_report,
    "fundamentals_tool_call_count": tool_call_count
}

# 路径 E: 无 tool_calls + 已有 ToolMessage/分析内容 → 直接用内容当报告
return {
    "fundamentals_report": report,
    "messages": [result],
    "fundamentals_tool_call_count": tool_call_count
}

# 路径 F: 无 tool_calls + 无任何数据 → 强制调用工具 + 用工具数据生成报告
return {
    "fundamentals_report": report,
    "fundamentals_tool_call_count": tool_call_count
}

# 路径 G: 兜底（理论上不应到达）
return {
    "messages": [result],
    "fundamentals_report": result.content if ... else str(result),
    "fundamentals_tool_call_count": tool_call_count
}
```

**这是整个项目中分歧最多的一个函数**。理解它需要跟踪 `has_tool_result` 和 `current_tool_calls` 两个布尔值的 4 种组合。

### 3.4 阿里百炼模型特殊处理

```python
if is_qwen_like:
    fresh_llm = create_llm_client(provider="qwen", model=model_name, ...).get_llm()
else:
    fresh_llm = llm
```

阿里百炼/通义千问模型存在工具调用缓存问题，会导致后续调用仍然尝试调用工具。解决方案是**每次创建新的 LLM 实例**（`fresh_llm`），避免缓存污染。

### 3.5 `max_tool_calls=1` 的原因

基本面数据（PE、PB、ROE、营收、利润等）通过 `get_stock_fundamentals_unified` 一次性批量返回，不需要多次调用。1 次就够，设为 1 可以最快触发死循环防护。

---

## 4. News Analyst（新闻分析师）— 预处理优化模式

### 4.1 核心创新：模型感知的预处理

```python
# 🚨 DashScope/DeepSeek/Zhipu 预处理
if ('DashScope' in llm.__class__.__name__
    or 'DeepSeek' in llm.__class__.__name__
    or 'Zhipu' in llm.__class__.__name__):
    # 在这些模型上，LLM 经常不主动调用工具
    # 解决方案：在节点内预先调用工具，直接把数据喂给 LLM
    pre_fetched_news = unified_news_tool(stock_code=ticker, max_news=10, model_info=model_info)

    if pre_fetched_news and len(pre_fetched_news.strip()) > 100:
        # 直接用预处理数据构造 prompt，绑定工具的 LLM 调用
        result = llm.invoke([
            {"role": "system", "content": analysis_system_prompt},
            {"role": "user", "content": enhanced_prompt}
        ])
        # 直接返回，跳过后续所有标准流程
        return {
            "messages": [AIMessage(content=report)],
            "news_report": report,
            "news_tool_call_count": tool_call_count + 1
        }
```

**设计动机**：某些 LLM（特别是 DashScope、DeepSeek、智谱）不主动调用工具，导致条件路由循环空转。预处理方案**绕过 LLM 的工具调用决策**，直接由代码获取数据。

### 4.2 News vs Market 的区别

| | Market Analyst | News Analyst |
|---|---|---|
| 工具执行 | 节点内部手动执行 | 模型路由差异：预处理模式节点内部执行，标准模式靠 LangGraph ToolNode |
| 二次 LLM 调用 | 有（工具结果 → LLM → 格式化报告） | 预处理路径有，标准路径靠 ToolNode 循环 |
| 返回的 messages | 完整序列（AIMsg + ToolMsgs + 最终 AIMsg） | 仅最终报告的清洁 AIMessage |
| 强制工具调用 | 靠 Prompt 中的强制指令 | 代码级预处理 |

### 4.3 `clean_message` 技巧

```python
clean_message = AIMessage(content=report)
return {
    "messages": [clean_message],   # 只返回最终报告，不包含 tool_calls
    "news_report": report,
    ...
}
```

关键：`AIMessage(content=report)` **没有 `tool_calls` 属性**。条件路由 `should_continue_news` 检查 `last_message.tool_calls` 时返回 `False`，所以直接走到 `Msg Clear News`。这是**主动欺骗条件路由来终止循环**。

---

## 5. Social Media Analyst（社交媒体分析师）— 最简实现

### 5.1 代码结构

Social Media Analyst 是五个中最短的（234 行），核心逻辑只有约 60 行：

```python
def social_media_analyst_node(state):
    tool_call_count = state.get("sentiment_tool_call_count", 0)
    ticker = state["company_of_interest"]
    market_info = StockUtils.get_market_info(ticker)
    company_name = _get_company_name_for_social_media(ticker, market_info)

    tools = [toolkit.get_stock_sentiment_unified]

    # ... Prompt 构造 ...

    chain = prompt | llm.bind_tools(tools)
    result = chain.invoke({"messages": state["messages"]})

    if GoogleToolCallHandler.is_google_model(llm):
        report, messages = GoogleToolCallHandler.handle_google_tool_calls(...)
    else:
        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

    return {
        "messages": [result],
        "sentiment_report": report,
        "sentiment_tool_call_count": tool_call_count + 1
    }
```

### 5.2 与其他分析师的最大区别

**没有节点内手动执行工具的逻辑**。`tool_calls` 不为空时，它返回的 `result` 仍包含 `tool_calls`，LangGraph 的条件路由检测到后会走到 `tools_social` → 再回到 Social Analyst。这是**完全依赖 LangGraph ToolNode 循环**的模式。

### 5.3 非 Google 模型的 report 可能为空

```python
if len(result.tool_calls) == 0:
    report = result.content
# 如果有 tool_calls，report 保持 ""
```

当 `tool_calls` 不为空时，`report=""` → 条件路由 `should_continue_social` 检测 `len(sentiment_report)=0` → 走 tools。这种设计的假设是：**ToolNode 执行后，第二轮 LLM 调用会生成报告文本**。

---

## 6. China Market Analyst（中国市场分析师）— 未被集成到标准流程

### 6.1 特殊性

`china_market_analyst.py` 定义了**两个**工厂函数：

| 函数 | 节点名 | 用途 |
|---|---|---|
| `create_china_market_analyst` | `china_market_analyst_node` | A 股全面分析 |
| `create_china_stock_screener` | `china_stock_screener_node` | A 股股票筛选 |

但在 `setup.py` 的 `setup_graph()` 中，**China Market Analyst 没有被注册到图结构中**。标准流程使用的是 `market_analyst`（通用版），China Market Analyst 仅作为备用和独立调用。

### 6.2 与其他分析师的关键差异

| 方面 | Market Analyst | China Market Analyst |
|---|---|---|
| 工具数量 | 1（统一） | **3**：`get_china_stock_data`, `get_china_market_overview`, `get_YFin_data` |
| 工具调用计数 | 有 `market_tool_call_count` | **无独立计数器** |
| 返回字段 | `market_report` | `china_market_report` |
| sender 字段 | 无 | `"ChinaMarketAnalyst"` |
| Prompt 焦点 | 技术指标分析 | A 股独特性（涨跌停、T+1、板块轮动、政策面） |

### 6.3 Prompt 中的"卖出建议"指令

China Market Analyst 的 system prompt 中有这段：
```
- 涨跌停板限制对交易策略的影响
- ST股票的特殊风险和机会
- 科创板、创业板的差异化分析
```

这是唯一一个提及 A 股市场微观结构（涨跌停、ST、科创板）的分析师。如果要分析 A 股，这个分析师的观点比通用 Market Analyst 更精准。

---

## 7. 五个分析师的模式对比总览

### 7.1 工具调用执行方式

```
Market:         节点内手动执行 → 二次 LLM → 完整报告（一次节点可能完成）
Fundamentals:   优先 LangGraph ToolNode 循环，但有 7 个返回路径做防御
News:           模型路由：DashScope/DeepSeek/Zhipu 走预处理，其他走 ToolNode 循环
Social:         完全依赖 ToolNode 循环（最简洁）
China Market:   依赖 ToolNode 循环，但无独立的工具调用计数器
```

### 7.2 报告生成时机

```
Market:         同一次节点内（手动执行工具后立即生成）
Fundamentals:   第二次进入节点时（第一次=返回 tool_calls，第二次=检测到 ToolMessage 后生成）
News(预处理):    同一次节点内（预获取数据后直接生成）
News(标准):      第二次进入节点时
Social:          第二次进入节点时
China Market:   第二次进入节点时
```

### 7.3 Prompt 设计复杂度

```
Market:         ★★★★★  最详细，包含四段式结构 + 格式模板
Fundamentals:   ★★★★★  双重 prompt（system_prompt + system_message），含强制工具调用指令
News:           ★★★★   双层（预处理路径和标准路径各有一套 prompt）
Social:         ★★★    单层，较简洁的社交媒体分析指令
China Market:   ★★★    单层，聚焦 A 股市场特性
```

### 7.4 防御机制复杂度

```
Market:         ★★     基础：tool_call_count + report 长度
Fundamentals:   ★★★★★  7 个返回路径、ToolMessage 统计、强制报告生成、fallback
News:           ★★★★   预处理绕过 + clean_message 欺骗 + 强制补救
Social:         ★★     基础：tool_call_count + ToolNode 循环
China Market:   ★      无独立计数器，依赖 LangGraph 默认行为
```

---

## 8. 跨分析师的共享模式

### 8.1 `_get_company_name()` 函数

**全部 5 个分析师都有各自的 `_get_company_name` 实现**，而且代码几乎完全相同（约 80 行），这是明显的**代码重复**：

```
market_analyst.py         → _get_company_name()
fundamentals_analyst.py   → _get_company_name_for_fundamentals()
news_analyst.py           → _get_company_name()  (内联)
social_media_analyst.py   → _get_company_name_for_social_media()
china_market_analyst.py   → _get_company_name_for_china_market()
```

**重构建议**：提取为 `agents/utils/company_name_resolver.py` 中的公共函数。

### 8.2 Google 模型特殊处理

```python
if GoogleToolCallHandler.is_google_model(llm):
    report, messages = GoogleToolCallHandler.handle_google_tool_calls(...)
```

Google Gemini 的 tool_calls 响应格式与其他模型不同，需要专门的解析和消息序列优化。所有 5 个分析师都有这个分支。

### 8.3 `MessagesPlaceholder` 的使用

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
])
```

`MessagesPlaceholder` 是 LangChain 的消息注入机制：运行时把 `state["messages"]`（HumanMessage + AIMessage + ToolMessage 的完整历史）插入到 system prompt 之后，形成完整的 LLM 输入序列。

### 8.4 `prompt.partial()` 的模板变量注入

```python
prompt = prompt.partial(tool_names=", ".join(tool_names))
prompt = prompt.partial(current_date=current_date)
prompt = prompt.partial(ticker=ticker)
prompt = prompt.partial(company_name=company_name)
prompt = prompt.partial(market_name=market_info['market_name'])
prompt = prompt.partial(currency_name=market_info['currency_name'])
prompt = prompt.partial(currency_symbol=market_info['currency_symbol'])
prompt = prompt.partial(instrument_context=instrument_context)
```

`partial()` 是 LangChain 的**模板预填充**方法。每个变量注入后返回新对象（不可变模式），链式调用创建最终的 Prompt 模板。

---

## 9. 面试可能的追问

| 问题 | 答题要点 |
|---|---|
| **为什么 Fundamentals 的 max_tool_calls=1 而 Market 的=3？** | 基本面数据是一次性批量返回；市场技术数据可能需要分维度多轮获取 |
| **为什么 Market Analyst 在节点内手动执行工具？** | 减少图节点跳转次数，工具调用+报告生成一次完成，提升效率 |
| **预处理模式解决什么问题？** | 某些 LLM（DashScope/DeepSeek/智谱）不主动调用工具 → 预处理绕过 LLM 的"判断"步骤，直接由代码获取数据 |
| **`_get_company_name` 5 份重复代码怎么优化？** | 提取为公共工具函数，放在 `agents/utils/` 下，所有分析师共享 |
| **clean_message 技巧的原理？** | 用无 tool_calls 属性的 AIMessage 替换含 tool_calls 的消息，让条件路由误判为"分析已完成" |
| **为什么 Social Analyst 最简单的却最稳定？** | 简单 = 少的分支 = 少的状态组合 = 少的 bug 面；复杂的防御（如 Fundamentals）是 bug 的来源 |

---

## 10. 建议动手实验

1. **对比 Market Analyst 的两种路径**：分别用 OpenAI 和 DeepSeek 跑同一天同一只股票，观察 OpenAI 走"节点内工具执行"路径还是"ToolNode 循环"路径
2. **追踪 Fundamentals 的 7 个返回路径**：在 log 中为每个 return 语句加唯一标记（如 `"path":"B"`），统计一次分析中走了哪个路径
3. **为 Social Analyst 添加节点内工具执行**：参考 Market Analyst 的实现，让 Social Analyst 也在一轮内完成工具调用+报告生成
4. **提取重复代码**：把 5 个 `_get_company_name` 合并为一个公共函数，验证所有分析师仍正常工作
5. **对比 China Market vs Market Analyst 的输出**：同一只 A 股，对比两个分析师的报告质量和侧重点

---

> **上一文档**：[条件路由与状态传播](langgraph-conditional-propagation-v1.md) — Day 3
>
> **下一步**：Day 5 — 牛熊辩论 + 研究经理（`bull_researcher.py` / `bear_researcher.py` / `research_manager.py`）
