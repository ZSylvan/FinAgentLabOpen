# FinAgentLab FastAPI 启动流程与中间件 — 学习文档 v1

> **目标**：理解 FastAPI 后端的启动全流程 — 从 `uvicorn.run()` 到第一个请求被处理的完整链路，以及中间件链的洋葱模型。
>
> **核心文件**：
> | 文件 | 行数 | 角色 |
> |---|---|---|
> | `app/main.py` | 764 | 应用入口：lifespan、中间件注册、路由注册 |
> | `app/middleware/request_id.py` | 76 | 请求 ID — 全链路追踪的"身份证" |
> | `app/middleware/error_handler.py` | 89 | 错误处理 — 统一异常 → JSON 响应 |
> | `app/middleware/rate_limit.py` | 177 | 限流 — 请求频率 + 每日配额双控 |
> | `app/middleware/operation_log_middleware.py` | 313 | 审计日志 — 用户操作的完整记录 |
> | `app/core/startup_validator.py` | 354 | 启动验证 — 缺配置时友好报错 |

---

## 1. 启动全景：从 `uvicorn.run()` 到第一个请求

```
uvicorn.run("app.main:app", host=..., port=8000, reload=...)
         │
         ├─[1] 导入 app 模块
         │      → app/main.py 顶层代码执行
         │      → 创建 FastAPI() 实例
         │      → 注册所有中间件（CORS / OperationLog / RequestID）
         │      → 注册所有路由（35+ 个 router）
         │      → 注册全局异常 handler
         │
         ├─[2] FastAPI 调用 lifespan(app) 异步上下文管理器
         │      │
         │      ├── ENTER ──────────────────────────────────
         │      │   ├── setup_logging()                    # 日志初始化
         │      │   ├── validate_startup_config()          # 配置验证（失败则抛异常阻止启动）
         │      │   ├── init_db()                          # MongoDB + Redis 连接
         │      │   ├── bridge_config_to_env()             # 统一配置 → 环境变量
         │      │   ├── 应用动态系统设置（日志级别、监控开关）
         │      │   ├── _print_config_summary()            # 打印配置摘要
         │      │   ├── 启动 APScheduler                   # 定时任务调度器
         │      │   │   ├── 股票基础信息同步（多数据源）
         │      │   │   ├── 实时行情入库（每 N 秒）
         │      │   │   ├── Tushare × 5 个定时任务
         │      │   │   ├── AKShare × 5 个定时任务
         │      │   │   ├── BaoStock × 4 个定时任务
         │      │   │   └── 新闻数据同步
         │      │   └── yield  # ← 应用开始接受请求
         │      │
         │      └── EXIT ───────────────────────────────────
         │          ├── scheduler.shutdown()               # 停止调度器
         │          ├── user_service.close()               # 关闭用户服务
         │          └── close_db()                         # 关闭 MongoDB + Redis
         │
         └─[3] 应用正常运行，接收 HTTP 请求
                │
                ├── RequestIDMiddleware     ← 最外层（生成 trace_id）
                ├── TrustedHostMiddleware  ← 安全：验证 Host 头
                ├── CORSMiddleware         ← 跨域
                ├── @app.middleware("http") log_requests  ← 请求日志
                ├── RateLimitMiddleware    ← 频率限制
                ├── QuotaMiddleware        ← 每日配额
                ├── OperationLogMiddleware ← 操作审计日志
                ├── ErrorHandlerMiddleware ← 异常捕获
                └── 路由处理器              ← 最内层（业务逻辑）
```

---

## 2. Lifespan — `@asynccontextmanager` 模式

### 2.1 核心代码

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ═══ ENTER: 启动时执行 ═══
    setup_logging()
    validate_startup_config()    # 失败会阻止启动
    await init_db()              # MongoDB + Redis 连接池
    bridge_config_to_env()       # 统一配置 → 环境变量
    # ... 启动调度器 ...
    scheduler.start()

    yield  # ← 分界线：应用在此刻开始接受请求

    # ═══ EXIT: 关闭时执行 ═══
    scheduler.shutdown()
    await close_db()
```

### 2.2 `@asynccontextmanager` 是什么？

Python 标准库 `contextlib` 的装饰器。把一个生成器函数变成异步上下文管理器：

```python
# 等价于手写:
class Lifespan:
    async def __aenter__(self):
        ... # yield 之前的代码
    async def __aexit__(self, ...):
        ... # yield 之后的代码

app = FastAPI(lifespan=Lifespan())
```

**好处**：`yield` 之前的初始化代码和之后的清理代码在同一个函数里，一目了然。

### 2.3 `validate_startup_config()` — 为什么在 `init_db()` 之前？

启动验证不依赖数据库。它在内存中检查环境变量是否齐全，早发现问题早报错，避免连上 MongoDB 后才发现缺配置。

```python
def validate_startup_config() -> ValidationResult:
    validator = StartupValidator()
    result = validator.validate()      # 检查必需/推荐/安全配置
    validator.raise_if_failed()        # 缺必需配置 → ConfigurationError
    return result
```

**四种验证结果**：

| 类型 | 举例 | 后果 |
|---|---|---|
| 缺必需配置 | `JWT_SECRET` 未设置或太短 | **抛异常，阻止启动** |
| 缺推荐配置 | `DEEPSEEK_API_KEY` 为空/占位符 | 警告，不阻止启动 |
| 安全警告 | `JWT_SECRET` 用默认值 | 警告，不阻止启动 |
| 配置无效 | `MONGODB_PORT=abc` | **抛异常，阻止启动** |

### 2.4 Lifespan 启动流程逐步解析

以下是 `lifespan` 函数中 `yield` 之前每个步骤的详细拆解：

---

**步骤 1：`setup_logging()` — 初始化日志系统**

```python
setup_logging()
logger = logging.getLogger("app.main")
```

调用 `app/core/logging_config.py` 中的 `setup_logging()`。它做的事：
- 读取 `logging.toml`（或 Docker 环境的 `logging_docker.toml`）配置文件
- 配置日志格式、输出目标（控制台 + 文件）、日志轮转策略
- 不同模块设置不同日志级别（`webapi`、`worker`、`uvicorn`、`fastapi`）

**为什么是第一步？** 后续所有步骤都需要日志来记录启动状态。日志没初始化好，启动失败时连错误信息都看不到。

---

**步骤 2：`validate_startup_config()` — 验证启动配置**

```python
from app.core.startup_validator import validate_startup_config
validate_startup_config()  # 失败直接抛 ConfigurationError，阻止启动
```

对应 `app/core/startup_validator.py`。验证三类配置：
- **必需配置**：`MONGODB_HOST/PORT/DATABASE`、`REDIS_HOST/PORT`、`JWT_SECRET`（长度 ≥ 16）。缺一个就阻止启动。
- **推荐配置**：`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`TUSHARE_TOKEN`。缺了只警告，不阻止启动。还会检查是不是占位符（`your_xxx_here`）。
- **安全警告**：`JWT_SECRET` 和 `CSRF_SECRET` 是否用的默认值（生产环境风险）。

**为什么在数据库初始化之前？** 早发现问题早报错。先验证环境变量，再尝试网络连接。如果 MongoDB 地址压根没配，不需要等到连接超时才报错。

---

**步骤 3：`init_db()` — 初始化 MongoDB + Redis 连接池**

```python
await init_db()
```

对应 `app/core/database.py` 中的 `init_db()`。它做的事：
- 创建 MongoDB 异步客户端（Motor），配置连接池参数（`minPoolSize=10`、`maxPoolSize=100`、超时时间）
- 创建 Redis 异步客户端（`redis.asyncio`），配置连接池和重试策略
- 初始化 MongoDB 视图和索引（如果还没创建）
- 将连接实例挂载到全局/模块级别，供路由和服务使用

**MongoDB 连接池参数（从 .env 读取）**：
```
MONGO_CONNECT_TIMEOUT_MS=30000         # 连接超时 30 秒
MONGO_SOCKET_TIMEOUT_MS=60000          # 套接字超时 60 秒
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000 # 服务器选择超时 5 秒
```

---

**步骤 4：`bridge_config_to_env()` — 配置桥接**

```python
from app.core.config_bridge import bridge_config_to_env
bridge_config_to_env()
```

**问题背景**：项目有两套配置系统 — FastAPI 后端用 Pydantic `Settings`（`app/core/config.py`），Agent 核心引擎从 `os.environ` 读配置。用户通过 Web UI 修改的 LLM 配置存在 MongoDB 里，核心引擎看不到。

**桥接做的事**：从 MongoDB 中读取用户配置的 LLM 提供商、模型名称、API Key、数据源配置等，写入 `os.environ`：
```python
# 伪代码：桥接的核心逻辑
os.environ["LLM_PROVIDER"] = mongo_config.llm_provider
os.environ["OPENAI_API_KEY"] = mongo_config.api_key
os.environ["DEEPSEEK_BASE_URL"] = mongo_config.backend_url
# ... 等等
```

如果桥接失败（MongoDB 没连上或没配置），只打 warning，不阻止启动。此时核心引擎使用 `.env` 文件中的配置作为兜底。

---

**步骤 5：应用动态系统设置 — 日志级别 + 监控开关**

```python
from app.services.config_provider import provider as config_provider
eff = await config_provider.get_effective_system_settings()

# 5a. 动态调整日志级别
desired_level = str(eff.get("log_level", "INFO")).upper()
setup_logging(log_level=desired_level)
for name in ("webapi", "worker", "uvicorn", "fastapi"):
    logging.getLogger(name).setLevel(desired_level)

# 5b. 动态开关操作日志记录
from app.middleware.operation_log_middleware import set_operation_log_enabled
set_operation_log_enabled(bool(eff.get("enable_monitoring", True)))
```

为什么日志要调两次？`setup_logging()` 在步骤 1 已经调过一次（用默认级别）。这一步从 MongoDB 中读取用户配置的 `log_level`（可能是 `DEBUG`），**覆盖**之前的级别。如果用户通过 Web UI 将日志级别调成 `DEBUG`，重启后生效。

---

**步骤 6：`_print_config_summary()` — 打印配置摘要**

```python
await _print_config_summary(logger)
```

向控制台输出一段格式化的启动信息，包括：
- `.env` 文件的位置和大小
- Pydantic Settings 类名和配置来源
- 关键配置值及其来源（环境变量 vs 默认值）：`HOST`、`PORT`、`DEBUG`、`MONGODB_HOST`、`REDIS_HOST`
- 当前环境（开发 vs 生产）
- MongoDB 和 Redis 的连接地址
- 代理配置（HTTP_PROXY / NO_PROXY）
- 已启用的 LLM 清单（从 MongoDB 读取，最多显示 3 个）
- 已启用的数据源清单（Tushare / AKShare / BaoStock）

输出示例：
```
======================================================================
📋 FinAgentLab Configuration Summary
======================================================================
Environment: Development
MongoDB: localhost:27017/finagentlab
Redis: localhost:6379/0
Proxy: Not configured (direct connection)
Enabled LLMs: 1
  • deepseek: deepseek-chat
Enabled Data Sources: Using default (AKShare)
======================================================================
```

---

**步骤 7：启动期休市兜底补数 — 行情快照回填**

```python
if settings.QUOTES_BACKFILL_ON_STARTUP:
    qi = QuotesIngestionService()
    await qi.ensure_indexes()
    await qi.backfill_last_close_snapshot_if_needed()
```

对应 `.env` 中的 `QUOTES_BACKFILL_ON_STARTUP=true`（默认开启）。这是为了解决一个实际问题：

**场景**：用户在周六早上重启了服务器。此时不在交易时段（A 股交易日是周一至周五 9:30-15:00），定时采集任务不会触发，前端打开的行情页面是**空的**。用户看不到任何股票价格。

**兜底补数做的事**：启动时检查 MongoDB 的 `market_quotes` 集合（前端行情展示的数据源）。如果集合为空（冷启动）或数据落后于最新交易日，就**主动拉一次行情数据**写入该集合，保证前端有数据可显示。

下面拆解这个功能的完整执行链路。

#### 7.1 入口：`backfill_last_close_snapshot_if_needed()`

```python
async def backfill_last_close_snapshot_if_needed(self) -> None:
    # 判断 1: 集合是否为空？
    is_empty = await self._collection_empty()

    if is_empty:
        # 空集合 → 走"从历史数据导入"路径
        await self.backfill_from_historical_data()
        return

    # 判断 2: 数据是否落后于最新交易日？
    manager = DataSourceManager()
    latest_td = manager.find_latest_trade_date_with_fallback()
    if await self._collection_stale(latest_td):
        # 数据陈旧 → 走"实时接口补数"路径
        await self.backfill_last_close_snapshot()
```

两个分支对应两个典型场景：

| 场景 | 触发条件 | 走哪个分支 |
|---|---|---|
| **首次部署**（冷启动） | `market_quotes` 集合为空，count=0 | `backfill_from_historical_data()` |
| **服务停了几天** | 集合不为空，但 `trade_date` 落后于最新交易日（如停在上周五，现在已周三） | `backfill_last_close_snapshot()` |

**注意**：如果集合不为空且数据是最新的（如刚在交易时段跑过采集），则**什么都不做**，直接跳过。

#### 7.2 分支 A：从历史数据导入（冷启动场景）

```python
async def backfill_from_historical_data(self) -> None:
    # 1. 确定最新交易日
    latest_trade_date = manager.find_latest_trade_date_with_fallback()

    # 2. 从 stock_daily_quotes 集合读取该交易日的数据
    daily_quotes_collection = db["stock_daily_quotes"]
    cursor = daily_quotes_collection.find({
        "trade_date": latest_trade_date,
        "period": "daily"
    })
    docs = await cursor.to_list(length=None)  # 全量读取

    # 3. 逐条转换为 market_quotes 格式
    for doc in docs:
        quotes_map[code] = {
            "close": doc.get("close"),
            "pct_chg": doc.get("pct_chg"),
            "amount": doc.get("amount"),
            "volume": doc.get("volume"),
            "open/high/low/pre_close": ...
        }

    # 4. 批量 upsert 到 market_quotes（约 5000+ 条记录）
    await self._bulk_upsert(quotes_map, latest_trade_date, "historical_data")
```

**数据来源**：`stock_daily_quotes` → 这是定时同步任务（Tushare/AKShare 的历史数据同步）写入的集合。它已经有每个股票每天的开高低收、成交量等完整数据。

**关键假设**：这个方法**依赖** `stock_daily_quotes` 集合里已经有数据。如果两个集合都为空（全新部署，定时同步还没跑过），补数会失败，前端仍是空的。此时需要先手动触发一次历史数据同步。

**为什么不直接调外部 API 而要从 stock_daily_quotes 读？**

- 5000+ 只股票逐个调 API 获取行情 → 非常慢（几分钟甚至更长）
- 历史数据同步任务可能已经跑过，`stock_daily_quotes` 里有现成的数据，直接读 MongoDB 秒级完成

#### 7.3 分支 B：实时接口补数（数据陈旧场景）

```python
async def backfill_last_close_snapshot(self) -> None:
    # 1. 调用 DataSourceManager 的实时行情接口（带回退）
    quotes_map, source = manager.get_realtime_quotes_with_fallback()

    # 2. 写入 market_quotes
    await self._bulk_upsert(quotes_map, trade_date, source)
```

**数据来源**：外部 API 实时调用 → `DataSourceManager.get_realtime_quotes_with_fallback()` → 按优先级尝试 Tushare rt_k → AKShare 东方财富 → AKShare 新浪财经。

**休市期调用的兼容性**：即使当前不在交易时段，Tushare 的 `rt_k` 接口和 AKShare 的快照接口也会返回**上一个交易日的收盘数据**。休市期调用不等于空数据，只是拿到的是"过时但准确"的收盘快照。

#### 7.4 写入方式：`_bulk_upsert()` — MongoDB 批量 upsert

```python
async def _bulk_upsert(self, quotes_map, trade_date, source) -> None:
    ops = []
    for code, q in quotes_map.items():
        ops.append(
            UpdateOne(
                {"code": code},
                {"$set": {
                    "code": code,
                    "close": q.get("close"),
                    "pct_chg": q.get("pct_chg"),
                    "open/high/low/pre_close": ...,
                    "trade_date": trade_date,
                    "updated_at": datetime.now(tz),
                }},
                upsert=True,   # ← 存在则更新，不存在则插入
            )
        )
    await coll.bulk_write(ops, ordered=False)
```

`ordered=False` 意味着 5000+ 条 upsert 并发执行，某一条失败不影响其他条。`upsert=True` 保证不论集合中是否已有该股票，都能写入。

#### 7.5 `market_quotes` 集合的用途

```
market_quotes (MongoDB 集合)
├── 前端行情展示      ← 自选股列表实时价格
├── 前端股票筛选      ← 按涨跌幅/成交量等条件筛选
├── AI 分析参考       ← Agent 可能需要当前价格做判断
└── 定时采集任务续写   ← 交易时段每秒/每N秒更新一次
```

前端 API（如 `/api/stocks/realtime`）不会每次都去调外部数据源，而是直接读 `market_quotes` 集合。这个集合是**前端行情展示的唯一数据源**，所以启动时必须保证它不是空的。

#### 7.6 定时任务中也有相同的补数逻辑

```python
async def run_once(self) -> None:
    # 非交易时段
    if not self._is_trading_time():
        if settings.QUOTES_BACKFILL_ON_OFFHOURS:
            # 每天的第 361 秒（6分钟），定时任务也会检查是否需要补数
            await self.backfill_last_close_snapshot_if_needed()
        else:
            logger.info("⏭️ 非交易时段，跳过行情采集")
        return

    # 交易时段 → 正常采集 → 写入 market_quotes
    quotes_map, source = self._fetch_quotes_from_source(...)
    await self._bulk_upsert(quotes_map, trade_date, source)
```

所以补数有两道防线：

| 防线 | 触发时间 | 覆盖场景 |
|---|---|---|
| 启动期补数 | 服务启动时 | 冷启动、重启后 |
| 定时补数 | 每次定时任务触发时（如每 360 秒） | 运行中的服务，休市期数据过期 |

#### 7.7 完整的数据流图

```
┌─ 启动期 ───────────────────────────────────────────────────────┐
│                                                                 │
│  QUOTES_BACKFILL_ON_STARTUP=true                               │
│         │                                                       │
│         ▼                                                       │
│  backfill_last_close_snapshot_if_needed()                      │
│         │                                                       │
│         ├── market_quotes 为空？                                │
│         │   └── YES → backfill_from_historical_data()          │
│         │            │                                          │
│         │            ├── find_latest_trade_date()              │
│         │            ├── 从 stock_daily_quotes 读该日全量数据    │
│         │            └── _bulk_upsert → market_quotes (5000+条)│
│         │                                                       │
│         └── market_quotes 不为空但数据陈旧？                      │
│             └── YES → backfill_last_close_snapshot()           │
│                      │                                          │
│                      ├── get_realtime_quotes_with_fallback()   │
│                      │   ├── 尝试 Tushare rt_k                 │
│                      │   ├── 尝试 AKShare 东方财富              │
│                      │   └── 尝试 AKShare 新浪财经              │
│                      └── _bulk_upsert → market_quotes          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─ 运行时（每 360 秒）───────────────────────────────────────────┐
│                                                                 │
│  run_once() 被 APScheduler 触发                                 │
│         │                                                       │
│         ├── _is_trading_time()?                                │
│         │   ├── YES → 调用外部 API → _bulk_upsert              │
│         │   └── NO  → QUOTES_BACKFILL_ON_OFFHOURS?            │
│         │            ├── YES → backfill_last_close_snapshot    │
│         │            └── NO  → 跳过                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 7.8 相关 .env 配置项

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `QUOTES_BACKFILL_ON_STARTUP` | `true` | 启动时是否检查并回填行情数据 |
| `QUOTES_BACKFILL_ON_OFFHOURS` | `true` | 定时任务在非交易时段是否也检查回填 |
| `QUOTES_INGEST_INTERVAL_SECONDS` | `360` | 定时采集间隔（秒） |
| `QUOTES_ROTATION_ENABLED` | `true` | 是否启用接口轮换（避免单接口限流） |
| `QUOTES_TUSHARE_HOURLY_LIMIT` | `2` | Tushare 免费用户每小时限调次数 |
| `QUOTES_AUTO_DETECT_TUSHARE_PERMISSION` | `true` | 首次运行自动检测付费权限 |

---

**步骤 8：启动 `APScheduler` — 注册 24 个定时任务**

```python
scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)  # Asia/Shanghai

# 8a. 启动后立刻跑一次股票基础信息同步（不阻塞）
multi_source_service = MultiSourceBasicsSyncService()
asyncio.create_task(run_sync_with_sources())

# 8b. 注册股票基础信息每日同步（多数据源，优先 Tushare > AKShare > BaoStock）
scheduler.add_job(..., CronTrigger.from_crontab(...), id="basics_sync_service")

# 8c. 注册实时行情入库（每 N 秒，默认 360s，内部自判交易时段）
scheduler.add_job(..., IntervalTrigger(seconds=360), id="quotes_ingestion_service")

# 8d. 注册 Tushare × 5 个任务（基础信息/行情/历史/财务/状态检查）
# 8e. 注册 AKShare × 5 个任务
# 8f. 注册 BaoStock × 4 个任务（基础信息/日K线/历史/状态检查）
# 8g. 注册新闻数据同步（仅同步自选股）

# 8h. 根据 ENABLED 开关决定是否实际执行
if not settings.TUSHARE_UNIFIED_ENABLED or not settings.TUSHARE_BASIC_INFO_SYNC_ENABLED:
    scheduler.pause_job("tushare_basic_info_sync")  # 注册但不运行，可通过 API 动态启用

scheduler.start()
set_scheduler_instance(scheduler)  # 暴露给 API，允许前端动态管理任务
```

调度器启动时 `asyncio.create_task()` 会触发一次立即同步（不阻塞启动），之后按 CRON 表达式定期执行。每个任务默认注册但根据开关决定是否 `pause`。

---

**步骤 9：`yield` — 应用就绪，开始接受请求**

```python
try:
    yield  # ← FastAPI 在此刻开始监听端口，接受 HTTP 请求
finally:
    # 关闭时的清理逻辑（见步骤 10）
```

`yield` 之后，FastAPI 开始绑定端口（如 `0.0.0.0:8000`），接受 HTTP 请求。在此之前的所有 8 个步骤如果任何一个抛了未捕获异常，应用都不会启动。

---

**步骤 10（关闭时）：清理资源**

```python
finally:
    scheduler.shutdown(wait=False)     # 停止所有定时任务
    user_service.close()               # 关闭 UserService 的 MongoDB 连接
    await close_db()                   # 关闭 MongoDB + Redis 连接池
```

当应用收到关闭信号（SIGTERM / Ctrl+C）时：
- 先停止调度器，不再触发新任务
- 关闭用户服务的数据库连接
- 关闭 MongoDB 和 Redis 的连接池，释放网络资源

**启动 vs 关闭的对称性**：

```
启动                         关闭
══════                      ══════
setup_logging()              —
validate_startup_config()    —
init_db()          ←→       close_db()
bridge_config_to_env()       —
应用动态设置                   —
_print_config_summary()      —
行情回填                       —
scheduler.start()  ←→       scheduler.shutdown()
yield (接受请求)    ←→       yield 后执行清理
```

### 2.5 9 步启动流程全景图

```
┌─ uvicorn.run("app.main:app") ─────────────────────────────────────┐
│                                                                    │
│  [1] setup_logging()                    初始化日志系统             │
│        │                                    │                      │
│        ▼                                    │ 失败 → 后续日志不生效│
│  [2] validate_startup_config()           验证启动配置              │
│        │                                    │                      │
│        ├── ✅ 通过 ─────────────────────────┘                      │
│        └── ❌ 失败 → ConfigurationError → 应用不启动              │
│                                                                    │
│  [3] await init_db()                     MongoDB + Redis 连接池   │
│        │                                    │                      │
│        └── ❌ 失败 → 抛异常 → 应用不启动                           │
│                                                                    │
│  [4] bridge_config_to_env()              配置桥接（MongoDB→环境变量）│
│        │                                    │                      │
│        └── ❌ 失败 → 警告，继续（用 .env 兜底）                     │
│                                                                    │
│  [5] 应用动态设置                         日志级别 / 监控开关       │
│        │                                    │                      │
│        └── ❌ 失败 → 警告，继续（用默认值）                         │
│                                                                    │
│  [6] _print_config_summary()             打印启动摘要到控制台      │
│                                                                    │
│  [7] 行情回填（可选）                     休市期补上一日收盘快照     │
│                                                                    │
│  [8] scheduler.start()                   注册 24 个定时任务        │
│        │   ├── 立即触发一次股票同步（不阻塞）                       │
│        │   ├── Tushare × 5 / AKShare × 5 / BaoStock × 4           │
│        │   └── ❌ 失败 → 抛异常 → 应用不启动（raise）              │
│                                                                    │
│  [9] yield                               ✅ 应用就绪！              │
│       │                                                            │
│       ▼  正常运行时...                                              │
│  ┌────────────────────────────┐                                    │
│  │  中间件链处理 HTTP 请求     │                                    │
│  │  RequestID → CORS → Log   │                                    │
│  │  → RateLimit → Quota      │                                    │
│  │  → OpLog → 路由处理器      │                                    │
│  └────────────────────────────┘                                    │
│       │                                                            │
│       ▼  收到关闭信号 (SIGTERM / Ctrl+C)                            │
│  [10] finally:                                                     │
│       ├── scheduler.shutdown()                                     │
│       ├── user_service.close()                                     │
│       └── await close_db()                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 中间件链 — 洋葱模型

FastAPI/Starlette 的中间件是**洋葱模型**（每个中间件包裹内层）：

```
     REQUEST →
    ┌──────────────────────────────────────────┐
    │  RequestIDMiddleware                      │  ← 最外层：生成 trace_id
    │  ┌────────────────────────────────────┐   │
    │  │  TrustedHostMiddleware             │   │  ← 安全：验证 Host
    │  │  ┌──────────────────────────────┐  │   │
    │  │  │  CORSMiddleware              │  │   │  ← 跨域
    │  │  │  ┌────────────────────────┐  │  │   │
    │  │  │  │  log_requests           │  │  │   │  ← 函数式中间件
    │  │  │  │  ┌──────────────────┐  │  │  │   │
    │  │  │  │  │  RateLimit       │  │  │  │   │  ← 频率限制
    │  │  │  │  │  ┌────────────┐  │  │  │  │   │
    │  │  │  │  │  │  Quota     │  │  │  │  │   │  ← 每日配额
    │  │  │  │  │  │  ┌──────┐  │  │  │  │  │   │
    │  │  │  │  │  │  │ OpLog│  │  │  │  │  │   │  ← 审计日志
    │  │  │  │  │  │  │ ┌──┐ │  │  │  │  │  │   │
    │  │  │  │  │  │  │ │EP│ │  │  │  │  │  │   │  ← 路由处理器 (endpoint)
    │  │  │  │  │  │  │ └──┘ │  │  │  │  │  │   │
    │  │  │  │  │  │  └──────┘  │  │  │  │  │   │
    │  │  │  │  │  └────────────┘  │  │  │  │   │
    │  │  │  │  └──────────────────┘  │  │  │   │
    │  │  │  └────────────────────────┘  │  │   │
    │  │  └──────────────────────────────┘  │   │
    │  └────────────────────────────────────┘   │
    └──────────────────────────────────────────┘
     ← RESPONSE
```

### 3.1 类中间件 vs 函数式中间件

两种注册方式在项目中并存：

```python
# 类中间件：add_middleware(SomeMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=..., ...)
app.add_middleware(OperationLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# 函数式中间件：@app.middleware("http")
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {time.time()-start_time:.3f}s")
    return response
```

**区别**：类中间件继承 `BaseHTTPMiddleware`，通过 `dispatch()` 方法处理；函数式中间件直接用 async 函数。类中间件可以做更复杂的逻辑（如访问其他服务、修改请求体），函数式中间件适合简单场景（如日志）。

### 3.2 注册顺序 = 执行顺序

```python
app.add_middleware(CORSMiddleware, ...)       # 第 1 层
app.add_middleware(OperationLogMiddleware)    # 第 2 层
app.add_middleware(RequestIDMiddleware)       # 第 3 层（最外层）

@app.middleware("http")                       # 第 4 层（在类中间件之后）
async def log_requests(request, call_next):
```

**先注册 = 更外层**。RequestID 最后注册 → 最外层 → 请求最先经过它 → 响应最后经过它。

---

## 4. 四个中间件逐个详解

### 4.1 `RequestIDMiddleware` — 全链路追踪的"身份证"

```python
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = str(uuid.uuid4())           # 1. 生成唯一 ID
        request.state.request_id = trace_id

        token = trace_id_var.set(trace_id)     # 2. 写入 contextvars
        start_time = time.time()

        response = await call_next(request)    # 3. 执行内层

        response.headers["X-Trace-ID"] = trace_id    # 4. 响应头
        response.headers["X-Process-Time"] = f"{time.time()-start_time:.3f}"

        trace_id_var.reset(token)              # 5. 清理（防泄露）
        return response
```

**`contextvars` 的作用**：`trace_id_var` 是 Python 3.7+ 的 `ContextVar`。它能在异步任务中自动传递值，不需要显式传参。项目中所有 logger 通过 `logging_context.py` 的 filter 自动在日志中追加 `trace_id`：

```python
# app/core/logging_context.py
trace_id_var = ContextVar("trace_id", default="-")

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True
```

这样每条日志都会自动带上 `[trace_id=abc123]`，一个请求的所有日志可以通过 trace_id 串联起来。

### 4.2 `RateLimitMiddleware` — 端点级频率限制

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_rate_limit=100):
        self.endpoint_limits = {
            "/api/analysis/single": 10,    # 单股分析：每分钟 10 次
            "/api/analysis/batch": 5,      # 批量分析：每分钟 5 次
            "/api/auth/login": 5,          # 登录：每分钟 5 次
        }

    async def check_rate_limit(self, user_id, endpoint):
        rate_key = f"rate_limit:{user_id}:{endpoint}"
        current_count = await redis_service.increment_with_ttl(rate_key, ttl=60)

        if current_count > rate_limit:
            raise HTTPException(status_code=429, detail="请求过于频繁")
```

**工作原理**：Redis 的 `INCR` + `EXPIRE` 组合。每个用户每端点一个 key，60 秒自动过期。

```
请求 → INCR rate_limit:user_123:/api/analysis/single → 返回 1
                    ↓ 60秒内
请求 → INCR rate_limit:user_123:/api/analysis/single → 返回 2
                    ↓ ... 到第 11 次
请求 → INCR → 返回 11 > 10 → 429 Too Many Requests
```

**Redis 不可用时不阻塞**：`except Exception: pass` — 限流失败时放行请求，避免 Redis 故障导致整个 API 不可用。

### 4.3 `QuotaMiddleware` — 每日配额控制

```python
class QuotaMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, daily_quota=1000):
        self.quota_endpoints = {
            "/api/analysis/single",
            "/api/analysis/batch",
        }

    async def check_daily_quota(self, user_id):
        today = datetime.date.today().isoformat()
        quota_key = f"daily_quota:{user_id}:{today}"
        current_usage = await redis_service.increment_with_ttl(quota_key, ttl=86400)

        if current_usage > self.daily_quota:
            raise HTTPException(status_code=429, detail="今日配额已用完")
```

**和 RateLimit 的区别**：

| | RateLimitMiddleware | QuotaMiddleware |
|---|---|---|
| 维度 | 每分钟 | 每天 |
| 范围 | 按端点分别计数 | 跨端点合并计数 |
| 未认证用户 | 用 IP 识别 | 跳过（不限制） |

### 4.4 `OperationLogMiddleware` — 操作审计日志

```python
class OperationLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        self.skip_paths = ["/health", "/docs", "/api/stream/", ...]
        self.path_action_mapping = {
            "/api/analysis/": ActionType.STOCK_ANALYSIS,
            "/api/screening/": ActionType.SCREENING,
            "/api/config/": ActionType.CONFIG_MANAGEMENT,
            "/api/auth/login": ActionType.USER_LOGIN,
        }

    async def dispatch(self, request, call_next):
        if self._should_skip_logging(request):
            return await call_next(request)   # 健康检查、静态资源、GET 请求不记录

        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        await self._log_operation(
            user_info, method, path, response, duration_ms, ...
        )
        return response
```

**跳过条件**：健康检查 / 文档页 / 静态资源 / GET 请求 / SSE 流 / 日志 API 自身。

**只记录写操作**：`request.method not in ["POST", "PUT", "DELETE", "PATCH"]` 直接跳过。GET 请求再多也不记日志。

---

## 5. 错误处理 — 三层防御

### 5.1 第一层：`@app.exception_handler(Exception)`

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error occurred",
            "request_id": getattr(request.state, "request_id", None)
        }
    })
```

这是 FastAPI 的**最后兜底**。任何未被路由处理器捕获的异常都会到这里，返回统一的 500 JSON 而不是 HTML 错误页。

### 5.2 第二层：`ErrorHandlerMiddleware`（类中间件）

```python
class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            return await self.handle_error(request, exc)

    async def handle_error(self, request, exc):
        if isinstance(exc, ValueError):
            return JSONResponse(400, {"error": {"code": "VALIDATION_ERROR", ...}})
        elif isinstance(exc, PermissionError):
            return JSONResponse(403, {"error": {"code": "PERMISSION_DENIED", ...}})
        elif isinstance(exc, FileNotFoundError):
            return JSONResponse(404, {"error": {"code": "RESOURCE_NOT_FOUND", ...}})
        else:
            return JSONResponse(500, {"error": {"code": "INTERNAL_SERVER_ERROR", ...}})
```

**注意**：虽然代码存在，但 `main.py` 中**没有注册** `ErrorHandlerMiddleware`。实际的错误处理走了第三层。

### 5.3 第三层（实际生效）：`@app.exception_handler(Exception)` + 路由内的 try/except

项目实际依赖 `global_exception_handler` 和各路由内部的 try/except 来捕获错误。

---

## 6. 配置桥接 — `bridge_config_to_env()`

```python
from app.core.config_bridge import bridge_config_to_env
bridge_config_to_env()
```

**问题**：FastAPI 后端使用 Pydantic `Settings` 管理配置（`app/core/config.py`），而 `finagentlab/` 核心引擎从环境变量和 `DEFAULT_CONFIG` 中读配置。两者之间没有自动同步。

**解决**：`bridge_config_to_env()` 在启动时将 Pydantic Settings 中的值回写到 `os.environ`，确保核心引擎能看到最新的配置。这是一个**适配器模式**的实现。

---

## 7. 调度器 — 24 个定时任务

项目使用 **APScheduler**（`AsyncIOScheduler`）管理定时任务：

```
APScheduler
├── 股票基础信息同步（多数据源）       每日 06:30
├── 实时行情入库                     每 N 秒（默认 360s）
│
├── Tushare × 5
│   ├── 基础信息同步                  每日 02:00
│   ├── 实时行情同步                  交易时间 每 5 分钟
│   ├── 历史数据同步                  工作日 16:00
│   ├── 财务数据同步                  周日 03:00
│   └── 状态检查                      每小时
│
├── AKShare × 5
│   ├── 基础信息同步                  每日 03:00
│   ├── 实时行情同步                  交易时间 每 30 分钟
│   ├── 历史数据同步                  工作日 17:00
│   ├── 财务数据同步                  周日 04:00
│   └── 状态检查                      每小时 30 分
│
├── BaoStock × 4
│   ├── 基础信息同步                  每日 04:00
│   ├── 日K线同步                     工作日 16:00
│   ├── 历史数据同步                  工作日 18:00
│   └── 状态检查                      每小时 45 分
│
└── 新闻数据同步                      按 CRON 配置
```

**任务启用/暂停机制**：所有任务默认注册，但根据 `.env` 中的 `*_ENABLED` 开关决定是否实际运行：

```python
scheduler.add_job(run_tushare_basic_info_sync, ..., id="tushare_basic_info_sync")
if not (TUSHARE_UNIFIED_ENABLED and TUSHARE_BASIC_INFO_SYNC_ENABLED):
    scheduler.pause_job("tushare_basic_info_sync")
```

先添加再暂停（而非根本不添加）的好处：运行时可以通过 API **动态启用/暂停/触发**任务（`scheduler_router`）。

---

## 8. 路由注册 — 35+ 个 Router

```python
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
# ... 35+ 个
```

**路由分组设计原则**：

| prefix | 示例 | 说明 |
|---|---|---|
| `/api/auth/*` | `/api/auth/login` | 认证相关（需 JWT） |
| `/api/analysis/*` | `/api/analysis/single` | 核心业务（分析提交/查询） |
| `/api/system/*` | `/api/system/database/backup` | 系统管理（管理员） |
| `/api/stream/*` | `/api/stream/progress/{task_id}` | 实时流（SSE） |
| `/api/*` | `/api/favorites` | 通用业务 |
| `/` | `/` | 根路径（版本信息） |

---

## 9. 面试追问

| 问题 | 答题要点 |
|---|---|
| **`@asynccontextmanager` 和 `async with` 的关系？** | `@asynccontextmanager` 把生成器函数变成异步上下文管理器，`yield` 前是 `__aenter__`，`yield` 后是 `__aexit__`。FastAPI 的 lifespan 参数就是一个异步上下文管理器 |
| **中间件的洋葱模型是什么？** | 外层中间件的 dispatch 先执行 → 调用 `call_next(request)` → 进入内层中间件 → 到达路由处理器 → 响应原路返回。每个中间件可以修改 request 和 response |
| **RateLimit 和 Quota 的区别？** | RateLimit 是每分钟频率限制（防突发），Quota 是每天总量限制（防滥用）。Redis INCR + TTL 实现 |
| **为什么 `contextvars` 比全局变量好？** | 全局变量在 asyncio 并发时会被覆盖。`ContextVar` 每个协程独立副本，自动隔离 |
| **APScheduler 的 pause_job 为什么不用 remove_job？** | pause 保留 job 定义，可以通过 API 动态启用。remove 后无法恢复 |
| **配置桥接的必要性？** | FastAPI 用 Pydantic Settings，Agent 引擎用 os.environ。桥接确保两边看到同一份配置 |

---

> **上一文档**：[Agent 工具集与记忆系统](toolkit-memory-system-v1.md) — Day 7
>
> **下一步**：Day 9 — 核心分析路由 `app/routers/analysis.py`（1259 行，19 个端点）
