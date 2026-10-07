# FinAgentLab 日志系统详解 — 零基础版 v1

> **目标**：理解这个项目如何记录日志 — 日志配置在哪、启动时做了什么、代码中怎么打日志、日志文件怎么组织、出了问题怎么通过日志排查。

---

## 1. 日志是什么？为什么要看它？

### 1.1 一句话

```
日志就是程序在运行过程中"说"的话。

没有日志:
  程序崩了 → 你什么都不知道 → 只能猜
  分析跑了 3 分钟 → 中间发生了什么？不知道

有日志:
  程序崩了 → 看日志最后一行 → 知道哪行代码炸了
  分析跑了 3 分钟 → 看日志时间戳 → "Market Analyst 花了 45 秒"
```

### 1.2 这个项目里日志长什么样

```
2026-07-08 15:30:01 | app.main              | INFO     | 🔄 POST /api/analysis/single - 开始处理 trace=a1b2c3d4
2026-07-08 15:30:01 | finagentlab.agents  | INFO     | 📈 市场分析师节点开始 trace=a1b2c3d4
2026-07-08 15:30:08 | finagentlab.agents  | INFO     | ✅ 市场分析师完成，报告长度: 2432 字符 trace=a1b2c3d4
2026-07-08 15:30:45 | finagentlab.agents  | INFO     | 🐂 看涨研究员完成 trace=a1b2c3d4
2026-07-08 15:32:10 | app.main              | INFO     | ✅ POST /api/analysis/single - 状态: 200 - 耗时: 129.5s trace=a1b2c3d4
```

**关键信息**：时间、哪个模块、什么级别（INFO/WARNING/ERROR）、说了什么、`trace=` 后面的 ID 是什么。

---

## 2. 两套日志系统：它们是什么关系？

这个项目中**两套日志系统共存**，服务于不同层面：

| | FastAPI 后端日志 | Agent 引擎日志 |
|---|---|---|
| 配置文件 | `app/core/logging_config.py` | `finagentlab/utils/logging_manager.py` |
| 配置来源 | `config/logging.toml` | `config/logging.toml`（同一文件！） |
| 日志器名称 | `webapi`, `worker`, `uvicorn`, `fastapi` | `finagentlab`, `agents`, `dataflows` |
| 输出到哪里 | `logs/webapi.log`, `logs/worker.log` | `logs/finagentlab.log` |
| 谁调用 | `app/main.py` 的 `lifespan` | Agent 模块 import 时自动初始化 |
| 特色功能 | `trace_id` 全链路追踪 | 彩色控制台、装饰器、结构化日志 |

**它们的初始化是独立的**：

```
FastAPI 启动:
  lifespan → setup_logging() (app/core/logging_config.py)
           → dictConfig(token_logging_config)
           → 配置 webapi/worker/uvicorn/fastapi 日志器

Agent 引擎首次被 import:
  finagentlab/__init__.py → 触发 finagentlab/utils/__init__.py
  → 模块级别 get_logger() 调用 → FinAgentLabLogger 自动创建
  → 配置 finagentlab/agents/dataflows 日志器
```

**但它们用同一份 TOML 配置文件**（`config/logging.toml`），所以级别、格式是一致的。

### 2.1 优先级

**FastAPI 的 `setup_logging()` 调得更晚**（在 `lifespan` 里），所以它的 `dictConfig` 会覆盖 Agent 系统之前配置的 root logger。最终生效的是 FastAPI 的配置。但 Agent 系统的日志器名称（如 `finagentlab`、`agents`）如果不在 FastAPI 配置的 loggers 列表里，就会继承 root logger 的设置。

---

## 3. 配置文件：`config/logging.toml` 详解

这是整个日志系统的"控制面板"。不需要改代码，改这个文件就能调整日志行为。

```toml
[logging]
level = "INFO"              # 全局日志级别

[logging.format]
console = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
file = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
file_json = true            # 文件日志用 JSON 格式

[logging.handlers.console]
enabled = true              # 控制台输出：开
level = "INFO"

[logging.handlers.file]
enabled = true              # 文件输出：开
level = "DEBUG"             # 文件里记 DEBUG 级别（比控制台详细）
max_size = "10MB"           # 单个文件最大 10MB
backup_count = 5            # 保留 5 个历史文件
directory = "./logs"        # 存放目录

[logging.handlers.error]
enabled = true
level = "WARNING"           # 只记 WARNING 及以上（WARNING, ERROR, CRITICAL）
filename = "error.log"

[logging.loggers.finagentlab]
level = "INFO"              # Agent 引擎日志级别

[logging.loggers.streamlit]
level = "WARNING"           # 第三方库：降低噪音
[logging.loggers.urllib3]
level = "WARNING"
```

### 3.1 日志级别的含义

```
DEBUG    → 最详细，所有细节都记（开发调试用）
INFO     → 重要流程节点（生产环境默认）
WARNING  → 可能有问题但不影响运行
ERROR    → 出错了
CRITICAL → 严重错误，系统可能不可用
```

**举例**：

```python
logger.debug("工具参数为: ticker=000002, start_date=2025-06-28")  ← DEBUG，只在文件里
logger.info("📈 市场分析师完成，报告 2432 字符")                   ← INFO，控制台 + 文件
logger.warning("⚠️ AKShare 数据获取失败，回退到 Tushare")         ← WARNING，控制台 + 文件 + error.log
logger.error("❌ LLM 调用超时")                                  ← ERROR，控制台 + 文件 + error.log
```

### 3.2 日志轮转（RotatingFileHandler）

```
日志写到 logs/webapi.log
  → 文件到达 10MB
  → webapi.log 被重命名为 webapi.log.1
  → 创建新的 webapi.log 继续写
  → 再次到达 10MB
  → webapi.log.1 → webapi.log.2
  → webapi.log → webapi.log.1
  → 新 webapi.log

保留 5 个历史文件: webapi.log + webapi.log.1 ~ .5
```

---

## 3B. `logging.toml` vs `logging_docker.toml` — 两个配置文件的区别

项目根目录下的 `config/` 里有两份日志配置文件。程序启动时 `resolve_logging_cfg_path()` 决定用哪个：

```python
def resolve_logging_cfg_path() -> Path:
    is_docker_env = (
        os.environ.get("DOCKER", "").lower() in {"1", "true", "yes"}
        or Path("/.dockerenv").exists()
    )
    # Docker 环境 → logging_docker.toml，普通环境 → logging.toml
    cfg = "config/logging_docker.toml" if is_docker_env else "config/logging.toml"
    return Path(cfg)
```

**判断逻辑**：检查环境变量 `DOCKER=1` 或文件 `/.dockerenv` 是否存在（Docker 容器内都有这个文件）。

### 3B.1 为什么要两份配置？

```
本地开发（logging.toml）:
  日志写在项目的 logs/ 目录下
  控制台有 emoji 和颜色 → 人类直接看

Docker 容器（logging_docker.toml）:
  日志写在 /app/logs/ 目录下（容器内路径）
  控制台无颜色 → Docker logs 命令不认 ANSI 颜色码
  文件更大（100MB vs 10MB）→ 容器环境不便频繁手动清理
  结构化日志开启 → 便于 ELK/Filebeat 采集
```

### 3B.2 逐项对比

| 配置项 | `logging.toml`（本地） | `logging_docker.toml`（容器） | 为什么不同 |
|---|---|---|---|
| **日志目录** | `./logs` | `/app/logs` | 容器内的项目代码在 `/app`，不能用相对路径 |
| **控制台颜色** | `colored = true` | `colored = false` | Docker logs 输出不支持 ANSI 颜色码，开了反而显示乱码 |
| **控制台格式** | `%(asctime)s \| %(name)-20s \| ...` | `%(asctime)s \| %(levelname)-8s \| %(name)s \| ...` | Docker 版更紧凑，字段顺序也不同（级别在前） |
| **文件最大大小** | `10MB` | `100MB` | 容器里清理历史文件更麻烦，一次给够空间 |
| **handler 定义方式** | 只有 `file` handler（路径由代码从 directory + filename 拼接） | 显式 `main`/`webapi`/`worker` handler（每个直接指定完整路径） | Docker 版把路径写死在 TOML 里，更直观、不依赖代码拼接逻辑 |
| **结构化日志** | `enabled = false` | `enabled = true` | Docker 环境通常有日志采集工具（ELK/Loki），需要 JSON 格式 |
| **`file_json`** | `true` | 无此字段 | 本地开发可能也需要 JSON 日志排查 |
| **`[logging.docker]`** | `enabled = false` | `enabled = true` | 标记当前环境类型 |
| **`stdout_only`** | `true` | `false` | 本地开发 `logging.toml` 写着 `true` 但代码里 Docker 环境才会走 `stdout_only` 分支 |
| **慢操作阈值** | `5.0 秒` | `10.0 秒` | 容器通常用 CPU 限制，LLM 调用本就慢，阈值放宽避免误报 |

### 3B.3 handler 结构差异（核心区别）

**本地 `logging.toml` 的 handler 设计**：

```toml
[logging.handlers]
# 只定义了 console / file / error 三个 handler 的元数据
# 具体的 main/webapi/worker 日志文件路径在 Python 代码里拼接

[logging.handlers.file]
enabled = true
level = "DEBUG"
max_size = "10MB"
directory = "./logs"           # ← 只有目录，具体文件名由代码决定
```

对应 Python 代码里的处理（`setup_logging()`）：

```python
# 代码从 TOML 读 directory + 从 handlers.main 读 filename
main_log = str(Path(file_dir) / "finagentlab.log")
webapi_log = str(Path(file_dir) / "webapi.log")
worker_log = str(Path(file_dir) / "worker.log")
```

**Docker `logging_docker.toml` 的 handler 设计**：

```toml
[logging.handlers.main]
enabled = true
filename = "/app/logs/finagentlab.log"   # ← 完整路径写死在 TOML 里

[logging.handlers.webapi]
filename = "/app/logs/webapi.log"

[logging.handlers.worker]
filename = "/app/logs/worker.log"

[logging.handlers.error]
filename = "/app/logs/error.log"
```

**为什么不同？** 本地版把路径拼接逻辑放在 Python 代码里，TOML 保持简洁；Docker 版把完整路径写死在 TOML 里，运维人员可以直接改 TOML 文件调整日志路径，不需要动代码。这符合 **配置与代码分离** 原则 — 运行环境的信息（如容器内绝对路径）属于配置，不属于代码。

### 3B.4 Docker 环境中日志的完整生命周期

```
1. 容器启动 → Dockerfile 中 ENV DOCKER=1
2. Python 启动 → resolve_logging_cfg_path() 检测到 DOCKER=1
3. 使用 config/logging_docker.toml
4. 日志写入 /app/logs/（容器内部路径）
5. Docker volume 挂载 /app/logs → 宿主机的 ./logs
6. docker logs 命令可以看到控制台输出（无颜色，纯文本）
7. 日志采集工具（Filebeat/Promtail）监控 /app/logs/*.log
```

---

## 4. 启动时 `setup_logging()` 做了什么

`app/core/logging_config.py` 中的 `setup_logging()` 是 FastAPI 启动的第一步。

### 4.1 整体流程

```
setup_logging("INFO")
    │
    ├─[1] 确定用哪个配置文件
    │      Docker环境 → config/logging_docker.toml
    │      普通环境    → config/logging.toml
    │
    ├─[2] 读取 TOML 文件
    │      解析 level / format / handlers / loggers 配置段
    │
    ├─[3] 构建 dict 配置（Python 标准 logging 格式）
    │      · formatters: 控制台格式、文件格式、JSON格式
    │      · filters: 注入 trace_id 到每条日志
    │      · handlers: console、main_file、webapi_file、worker_file、error_file
    │      · loggers: 每个日志器的级别和输出目标
    │
    ├─[4] 调用 logging.config.dictConfig(config_dict)
    │      Python 内置函数，一次性配置整个日志系统
    │
    └─[5] 写入一条测试日志
           "finagentlab logger → 测试主日志文件写入"
```

### 4.2 关键设计：5 个日志文件 + 1 个控制台

| 输出目标 | 日志文件 | 级别 | 内容 |
|---|---|---|---|
| 控制台 | `stdout` | INFO | 所有模块（实时查看） |
| 主日志 | `logs/finagentlab.log` | INFO | 全项目汇总 |
| WebAPI 日志 | `logs/webapi.log` | DEBUG | HTTP 请求、路由处理 |
| Worker 日志 | `logs/worker.log` | DEBUG | 后台任务执行、数据同步 |
| 错误日志 | `logs/error.log` | WARNING | 只有警告和错误 |

**一条日志出现在哪些地方？** 取决于这条日志是哪个 logger 打的：

```python
# agents 模块的日志 → 控制台 + finagentlab.log + error.log（如果是 WARNING+）
logger = logging.getLogger("agents")
logger.info("分析完成")    # → 控制台 + finagentlab.log
logger.error("工具调用失败") # → 控制台 + finagentlab.log + error.log

# webapi 模块的日志 → 控制台 + webapi.log + finagentlab.log + error.log
logger = logging.getLogger("webapi")
logger.info("POST /api/analysis")  # → 控制台 + webapi.log + finagentlab.log
```

### 4.3 日志格式详解

**控制台格式**：
```
%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s

2026-07-08 15:30:01,234 | app.main              | INFO     | 🔄 POST /api/analysis/single trace=a1b2c3d4
```

**文件格式**（多出源码位置）：
```
%(asctime)s | %(name)-20s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s

2026-07-08 15:30:01,234 | app.main              | INFO     | main:lifespan:650 | 🔄 server started trace=a1b2c3d4
```

文件格式多出 `%(module)s:%(funcName)s:%(lineno)d` — 直接告诉你日志是哪个文件哪个函数哪一行打出来的，排查问题非常有用。

### 4.4 JSON 格式（`file_json = true`）

当 `file_json = true` 时，文件日志使用 JSON 格式：

```json
{
  "time": "2026-07-08 15:30:01",
  "name": "app.main",
  "level": "INFO",
  "trace_id": "a1b2c3d4-e5f6-...",
  "message": "POST /api/analysis/single - 开始处理"
}
```

**好处**：JSON 可以被日志分析工具（ELK、Splunk 等）直接解析，方便生产环境做日志搜索和监控。

### 4.5 Windows 特殊处理

```python
if _IS_WINDOWS and concurrent_log_handler:
    # 使用 ConcurrentRotatingFileHandler
    # 而不是标准库的 RotatingFileHandler
```

Windows 上文件锁机制不同，多进程同时写同一个日志文件会报错。`ConcurrentRotatingFileHandler` 解决了这个问题。

---

## 5. trace_id：一条请求的"身份证"

### 5.1 是什么

每次 HTTP 请求到达时，`RequestIDMiddleware` 生成一个 UUID：

```python
trace_id = str(uuid.uuid4())  # "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

这个 ID 贯穿整个请求生命周期，出现在**所有相关日志**中。

### 5.2 怎么传递的 — contextvars

```python
# app/core/logging_context.py
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

class LoggingContextFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()   # 自动注入到每条日志
        return True
```

**`ContextVar` 是什么？** Python 3.7+ 的"协程局部变量"。在 asyncio 环境中，多个请求并发处理，但每个请求有自己的 trace_id。`ContextVar` 保证协程 A 不会读到协程 B 的 trace_id — 不需要手动传参。

**工作原理**：

```
请求 1 到达 → trace_id_var.set("aaaa-bbbb")
  协程处理请求 1：
    logger.info("分析开始")  →  日志自动带上 trace=aaaa-bbbb
    logger.info("分析完成")  →  日志自动带上 trace=aaaa-bbbb
  trace_id_var.reset()  ← 清理

请求 2 到达（与请求 1 并发）→ trace_id_var.set("cccc-dddd")
  协程处理请求 2：
    logger.info("查询数据")  →  日志自动带上 trace=cccc-dddd
```

**排查问题时的用法**：在日志文件里搜索 `trace=aaaa-bbbb`，就能看到这个请求的一生：

```
$ grep "aaaa-bbbb" logs/finagentlab.log

15:30:01 | middleware       | 🔄 POST /api/analysis/single 开始        trace=aaaa-bbbb
15:30:01 | analysis_service | 📝 创建分析任务 task_123               trace=aaaa-bbbb
15:30:02 | worker           | 🚀 开始执行分析 000002                 trace=aaaa-bbbb
15:30:08 | market_analyst   | ✅ 市场分析师完成 2432 字符            trace=aaaa-bbbb
15:30:45 | bull_researcher  | 🐂 看涨研究员完成                     trace=aaaa-bbbb
...
15:32:10 | worker           | ✅ 分析完成                            trace=aaaa-bbbb
```

---

## 6. 代码中怎么打日志

### 6.1 最简单的方式

```python
import logging

# 创建本模块的日志器
logger = logging.getLogger(__name__)

# 用
logger.info("开始分析")
logger.debug(f"参数: ticker={ticker}")
logger.error(f"分析失败: {e}", exc_info=True)  # exc_info=True 会附带完整堆栈
```

### 6.2 项目中实际使用的两种方式

**方式 1：用 `get_logger("名称")`（Agent 引擎侧）**

```python
# finagentlab/agents/analysts/market_analyst.py
from finagentlab.utils.logging_init import get_logger
logger = get_logger("default")
# 或者
from finagentlab.utils.logging_manager import get_logger
logger = get_logger('agents')
```

`get_logger("default")` 和 `get_logger("agents")` 都通过 `FinAgentLabLogger.get_logger()` 获取，内部就是 `logging.getLogger(name)`。

**方式 2：直接 `logging.getLogger(__name__)`（FastAPI 侧）**

```python
# app/main.py
logger = logging.getLogger("app.main")
# app/middleware/rate_limit.py
logger = logging.getLogger(__name__)
```

### 6.3 exc_info=True 的用法

```python
try:
    result = tool.invoke(args)
except Exception as e:
    logger.error(f"工具调用失败: {e}", exc_info=True)
```

`exc_info=True` 会在日志中附上完整的堆栈跟踪（traceback），和直接在控制台看到的报错信息一样。这对于排查"哪里出了错"至关重要。

---

## 7. 日志装饰器：自动记录，不用手写

项目有一套日志装饰器（`finagentlab/utils/tool_logging.py`），让你不用在每个函数里手动加日志。

### 7.1 `@log_tool_call` — 记录工具调用

```python
@log_tool_call(tool_name="get_stock_fundamentals_unified", log_args=True)
def get_stock_fundamentals_unified(ticker, start_date, end_date, curr_date):
    ...
```

**自动产生的日志**：
```
🔧 [工具调用] get_stock_fundamentals_unified - 开始
✅ [工具调用] get_stock_fundamentals_unified - 完成 (耗时: 1.23s)
```

### 7.2 `@log_analyst_module` — 记录分析模块

```python
# fundamentals_analyst.py
@log_analyst_module("fundamentals")
def fundamentals_analyst_node(state):
    ...
```

**自动产生的日志**：
```
📊 [模块开始] fundamentals_analyst - 股票: 000002
📊 [模块完成] fundamentals_analyst - ✅ 成功 - 耗时: 8.23s
```

这个装饰器自动从 `state` 字典中提取 `company_of_interest`（股票代码），不需要你手动传。

### 7.3 `@log_llm_call` — 记录 LLM 调用

```python
@log_llm_call(provider="deepseek", model="deepseek-chat")
def invoke_llm(prompt):
    ...
```

### 7.4 `@log_data_source_call` — 记录数据源调用

```python
@log_data_source_call(source_name="akshare")
def get_stock_data(ticker):
    ...
```

### 7.5 所有装饰器自动做三件事

1. 记录开始时间 + 输入参数
2. 执行函数
3. 记录结束时间 + 耗时 + 是否成功

---

## 8. 日志文件组织

### 8.1 `logs/` 目录结构

```
logs/
├── finagentlab.log      ← 全项目汇总。100MB/个，保留 5 个
├── finagentlab.log.1
├── finagentlab.log.2
├── webapi.log             ← HTTP 请求 + 路由处理。100MB/个，保留 5 个
├── worker.log             ← 后台任务 + 数据同步。100MB/个，保留 5 个
├── error.log              ← 所有 WARNING 及以上级别。100MB/个，保留 5 个
└── finagentlab_app.log  ← Streamlit 的日志（如果有）
```

### 8.2 各日志文件的用途

| 文件 | 排查什么问题 |
|---|---|
| `finagentlab.log` | Agent 分析全流程：分析师做了什么、辩论过程、决策结果 |
| `webapi.log` | HTTP 请求：谁在什么时间调了什么 API、返回了什么状态码 |
| `worker.log` | 后台任务：数据同步是否成功、分析队列是否卡住 |
| `error.log` | 错误汇总：只看出错的日志，不用在几千行里找 ERROR |

---

## 9. 实操：怎么看日志排查问题

### 9.1 场景 1：分析任务提交了但一直没有结果

```bash
# 步骤 1：在 webapi.log 里确认请求收到了
grep "analysis/single" logs/webapi.log
# → 2026-07-08 15:30:01 | ... | POST /api/analysis/single - 开始处理 trace=a1b2c3d4

# 步骤 2：用 trace_id 在 finagentlab.log 里追踪
grep "a1b2c3d4" logs/finagentlab.log
# → 看 Worker 有没有开始执行分析

# 步骤 3：如果 finagentlab.log 里有错误
grep "ERROR" logs/error.log | grep "a1b2c3d4"
# → 看具体是什么错了
```

### 9.2 场景 2：分析报告质量差，想看 Agent 内部做了什么

```bash
# 先改配置，打开 DEBUG
# logging.toml: level = "DEBUG"

# 重启后分析一只股票，然后：
grep "market_analyst" logs/finagentlab.log | tail -30
# → 看 Market Analyst 的每一步：收到了什么消息、调了什么工具、返回了什么
```

### 9.3 场景 3：LLM 调用很慢，想知道哪个 Agent 最慢

```bash
# 搜索所有带"耗时"的日志
grep "耗时" logs/finagentlab.log
# → 2026-07-08 15:30:08 | market_analyst   | 耗时: 6.23 秒
# → 2026-07-08 15:30:45 | fundamentals     | 耗时: 8.45 秒
# → 2026-07-08 15:31:30 | bull_researcher  | 耗时: 12.30 秒  ← 最慢！
```

---

## 10. 总结：三层日志系统

```
                   ┌──────────────────────────────┐
                   │   config/logging.toml          │  ← 控制面板
                   │   level / format / handlers    │
                   └──────────────┬───────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ FastAPI 日志     │   │ Agent 引擎日志   │   │ 装饰器日志       │
│ logging_config  │   │ logging_manager │   │ tool_logging    │
│ webapi/worker   │   │ finagentlab   │   │ @log_tool_call  │
│ 日志器           │   │ 日志器           │   │ @log_analyst   │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  实际输出            │
                    │  · 控制台 (stdout)   │
                    │  · finagentlab.log │
                    │  · webapi.log        │
                    │  · worker.log        │
                    │  · error.log         │
                    └─────────────────────┘
```

**你只需要记住**：

1. 改日志级别 → 改 `config/logging.toml`
2. 看 HTTP 请求 → `logs/webapi.log`
3. 看 Agent 分析过程 → `logs/finagentlab.log`
4. 看后台任务 → `logs/worker.log`
5. 只看错误 → `logs/error.log`
6. 追踪一个请求的所有日志 → 搜索 `trace=xxx`
7. 写代码时打日志 → `logger = getLogger(__name__); logger.info("...")`
8. 想让函数自动有日志 → 在函数上加 `@log_analyst_module` 之类的装饰器

---

> **相关文档**：[后端全景指南](backend-comprehensive-guide-v1.md)
