# FinAgentLab 数据库初始化 + 配置桥接 + 动态设置 — 零基础版 v1

> **目标**：理解启动流程的第 3、4、5 步——数据库怎么连、Agent 引擎怎么拿到 Web UI 配的模型参数、日志级别怎么被用户配置覆盖。

---

## 1. 第 3 步：连接数据库（`init_db()`）

### 1.1 到底连了什么

`app/main.py` 的 `lifespan` 里：

```python
await init_db()
```

这一行连了两个数据库：

```
init_db()
  ├── init_mongodb()  → AsyncIOMotorClient("mongodb://localhost:27017")
  │                     ↓
  │                     创建连接池 (min=10, max=100)
  │                     ↓
  │                     ping() 测试连接 → _mongo_healthy = True
  │
  ├── init_redis()    → redis.asyncio.ConnectionPool.from_url("redis://localhost:6379")
  │                     ↓
  │                     创建连接池 (max=20)
  │                     ↓
  │                     ping() 测试连接 → _redis_healthy = True
  │
  └── init_database_views_and_indexes()  # 创建 MongoDB 视图和索引
```

### 1.2 MongoDB 连接的细节

```python
async def init_mongodb(self):
    self.mongo_client = AsyncIOMotorClient(
        settings.MONGO_URI,
        maxPoolSize=100,            # 最多 100 个连接
        minPoolSize=10,             # 最少保持 10 个
        maxIdleTimeMS=30000,        # 30 秒空闲后回收
        serverSelectionTimeoutMS=5000,   # 选服务器最多等 5 秒
        connectTimeoutMS=30000,          # 连接最多等 30 秒
        socketTimeoutMS=60000,           # 数据操作最多等 60 秒
    )

    self.mongo_db = self.mongo_client[settings.MONGO_DB]  # 选择数据库
    await self.mongo_client.admin.command('ping')         # 测试连通性
```

**`AsyncIOMotorClient` 是什么？** Motor 是 MongoDB 官方推荐的 Python **异步**驱动。它把 MongoDB 的网络操作全部改成 `async/await` 模式，不会阻塞 FastAPI 的事件循环。

**连接池是什么？** 每次请求不需要新建连接（TCP 握手很慢）。从池子里拿一个现有连接，用完放回去。`min=10` 表示哪怕没有人访问，也保持 10 个热连接随时可用；`max=100` 表示高并发时最多开到 100 个。

**几个超时参数的含义**：

| 参数 | 默认值 | 场景 |
|---|---|---|
| `serverSelectionTimeoutMS` | 5000ms | MongoDB 集群有多个节点，选一个可用的主节点最多等 5 秒 |
| `connectTimeoutMS` | 30000ms | TCP 三次握手最多等 30 秒 |
| `socketTimeoutMS` | 60000ms | 一条查询发出去后，最多等 60 秒必须返回结果 |

### 1.3 Redis 连接的细节

```python
async def init_redis(self):
    self.redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=20,
        retry_on_timeout=True,         # 超时自动重试
        decode_responses=True,         # 自动把 bytes 解码成 str
        socket_connect_timeout=5,      # 5 秒连接超时
        socket_timeout=10,             # 10 秒读写超时
        socket_keepalive=True,         # TCP keepalive
        health_check_interval=30,      # 每 30 秒检查连接是否还活着
    )
    self.redis_client = Redis(connection_pool=self.redis_pool)
    await self.redis_client.ping()
```

**`decode_responses=True`**：Redis 默认存的是 bytes。设为 True 后，读出来的 `b"hello"` 自动变成 `"hello"`，代码不需要手动 decode。

**TCP keepalive 参数**：

```python
# 60 秒没数据交互 → 开始发 keepalive 探测包
# 每 10 秒发一次 → 最多发 3 次
# 总共 60 + 10*3 = 90 秒没响应 → 判定连接已死，关闭重连
```

**`health_check_interval=30`**：每 30 秒在连接池后台 ping 一次，提前剔除死连接，不等业务请求时才发现。

### 1.4 连接之后做了什么：初始化视图和索引

```
init_database_views_and_indexes()
  │
  ├── create_stock_screening_view(db)
  │   创建 MongoDB 视图 "stock_screening_view"
  │   把 stock_basic_info + market_quotes + stock_financial_data 三表关联
  │   前端股票筛选直接读这个视图，不用每次做 JOIN
  │
  └── create_database_indexes(db)
      给常用查询字段建索引：
        stock_basic_info:  (code+source 唯一索引), (industry), (total_mv 降序), (pe), (pb)
        market_quotes:     (code 唯一索引), (pct_chg 降序), (amount 降序), (updated_at 降序)
```

**为什么索引存在 `init_db()` 里而不是启动时手动建？** 索引只需要创建一次。代码里 `create_index` 对已存在的索引不会重复创建（MongoDB 自动跳过）。放在启动流程里确保每次部署都是最新状态，不需要运维手动操作。

### 1.5 全局变量：让所有文件都能拿到连接

```python
# app/core/database.py 顶部 — 模块级全局变量
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db: Optional[AsyncIOMotorDatabase] = None
redis_client: Optional[Redis] = None

# 启动时赋值
async def init_database():
    global mongo_client, mongo_db, redis_client
    mongo_client = db_manager.mongo_client
    mongo_db = db_manager.mongo_db
    redis_client = db_manager.redis_client
    redis_pool = db_manager.redis_pool

# 其他文件用的时候
from app.core.database import get_mongo_db, get_redis_client
db = get_mongo_db()
redis = get_redis_client()
```

`get_mongo_db()` 做的事非常简单：

```python
def get_mongo_db():
    if mongo_db is None:
        raise RuntimeError("MongoDB数据库未初始化")  # 启动顺序保证不会走到这里
    return mongo_db
```

### 1.6 RedisService：对 Redis 操作的高级封装

`app/core/redis_client.py` 中的 `RedisService` 类封装了常用操作：

| 方法 | 做什么 | 什么时候用 |
|---|---|---|
| `set_with_ttl(key, value, ttl)` | 写缓存，N 秒后自动过期 | 缓存股票数据 |
| `get_json(key)` / `set_json(key, dict)` | 读写 JSON（自动序列化/反序列化） | 缓存复杂对象 |
| `increment_with_ttl(key, ttl)` | 原子递增 + 设过期 | 限流计数器 |
| `add_to_queue(key, item)` / `pop_from_queue(key)` | LPUSH / BRPOP | 分析任务队列 |
| `acquire_lock(key, timeout)` / `release_lock(key)` | 分布式锁 | 防止并发冲突 |
| `add_to_set(key, value)` / `is_in_set(key, value)` | 集合操作 | 处理中任务追踪 |

### 1.7 关闭时清理

```python
async def close_database():
    await db_manager.close_connections()

    # 关闭顺序很重要：先关连接，再清池
    # MongoDB: client.close()
    # Redis:    client.close() → pool.disconnect()

    # 全局变量置 None，防止误用
    mongo_client = mongo_db = redis_client = redis_pool = None
```

---

## 2. 第 4 步：配置桥接（`bridge_config_to_env()`）

### 2.1 问题：两套配置系统互相看不见

```
┌─────────────────────────────┐   ┌──────────────────────────────┐
│   FastAPI 后端                │   │   Agent 核心引擎               │
│   (app/)                     │   │   (finagentlab/)            │
│                              │   │                              │
│   配置存储:                    │   │   配置来源:                    │
│   · MongoDB (Web UI 配的)      │   │   · os.environ (环境变量)     │
│   · .env 文件                 │   │   · DEFAULT_CONFIG (硬编码)    │
│   · Pydantic Settings         │   │                              │
│                              │   │   用户在 Web UI 改了 LLM 配置    │
│   问题: 不知道 Agent 引擎       │   │   问题: 读不到 MongoDB 里的新值  │
│   需要告诉它                   │   │                              │
└─────────────────────────────┘   └──────────────────────────────┘
```

**配置桥接**就是中间人：把 MongoDB 里的配置 → 写入 `os.environ` → Agent 引擎通过 `os.getenv()` 就能读到了。

### 2.2 `bridge_config_to_env()` 的 7 个子步骤

```
bridge_config_to_env()
    │
    ├─[1] 基础存储配置
    │     USE_MONGODB_STORAGE=true
    │     MONGODB_CONNECTION_STRING → os.environ
    │     MONGODB_DATABASE_NAME     → os.environ
    │
    ├─[2] LLM 厂家的 API Key 配置
    │     从 MongoDB llm_providers 集合读所有厂家配置
    │     对每个启用的厂家:
    │       如果 .env 里有有效的 API Key → 用 .env 的
    │       否则 → 用 MongoDB 里的
    │       写入如: DEEPSEEK_API_KEY, OPENAI_API_KEY, ...
    │
    ├─[3] 默认模型配置
    │     FINAGENTLAB_DEFAULT_MODEL → "deepseek-chat"
    │     FINAGENTLAB_QUICK_MODEL   → "deepseek-chat"
    │     FINAGENTLAB_DEEP_MODEL    → "deepseek-reasoner"
    │
    ├─[4] 数据源 API Key 配置
    │     TUSHARE_TOKEN  → 数据库优先，不行就用 .env
    │     FINNHUB_API_KEY → 同上
    │
    ├─[5] 数据源细节配置
    │     {SOURCE}_TIMEOUT, {SOURCE}_RATE_LIMIT
    │     {SOURCE}_MAX_RETRIES, {SOURCE}_CACHE_TTL
    │
    ├─[6] 系统运行时配置
    │     TA_HK_MIN_REQUEST_INTERVAL_SECONDS
    │     TA_USE_APP_CACHE, ENABLE_COST_TRACKING
    │     APP_TIMEZONE, CURRENCY_PREFERENCE
    │
    └─[7] 重新初始化 finagentlab 的 MongoDB 存储
          + 同步定价配置到 config/pricing.json（后台异步）
```

### 2.3 第 1 子步骤：基础存储配置

```python
# .env 里有 USE_MONGODB_STORAGE? → 用。没有? → 默认 true
os.environ["USE_MONGODB_STORAGE"] = os.getenv("USE_MONGODB_STORAGE", "true")

# MongoDB 连接字符串 — Agent 引擎需要它来写 token 使用记录
os.environ["MONGODB_CONNECTION_STRING"] = os.getenv("MONGODB_CONNECTION_STRING")

# 数据库名
os.environ["MONGODB_DATABASE_NAME"] = mongodb_db_name
```

### 2.4 第 2 子步骤：LLM 厂家的 API Key（关键逻辑）

```python
# 从 MongoDB 的 llm_providers 集合读取
providers_collection = db.llm_providers
providers = [LLMProvider(**data) for data in providers_collection.find()]

for provider in providers:
    if not provider.is_active:
        continue    # 没启用的厂家跳过

    env_key = f"{provider.name.upper()}_API_KEY"    # 例如: DEEPSEEK_API_KEY
    existing_env_value = os.getenv(env_key)

    # 优先级：.env 文件 > 数据库
    if existing_env_value and not existing_env_value.startswith("your_"):
        # .env 里有有效值 → 直接用，不覆盖
        logger.info(f"使用 .env 文件中的 {env_key}")
    elif provider.api_key and not provider.api_key.startswith("your_"):
        # .env 里没有 / 是占位符 → 用数据库里的
        os.environ[env_key] = provider.api_key
        logger.info(f"使用数据库中的 {env_key}")
    else:
        # 两边都没有 → 跳过（Agent 引擎会报错提示用户配置）
        logger.debug(f"{env_key} 未配置有效的 API Key")
```

**优先级规则**：`.env 文件 > MongoDB 数据库配置`。也就是说，如果你在 `.env` 里设了 `DEEPSEEK_API_KEY=sk-xxx`，Web UI 里再改什么都不会覆盖它。只有当 `.env` 里是占位符或没设，才会用数据库里的值。

### 2.5 第 7 子步骤：为什么要在桥接的最后重新初始化 MongoDB 存储？

```python
# finagentlab 框架在模块 import 时就创建了全局 config_manager 实例
# 那时环境变量还没被桥接，MongoDB 连不上

from finagentlab.config.config_manager import config_manager
from finagentlab.config.mongodb_storage import MongoDBStorage

# 现在环境变量已经有了，重新创建 MongoDB 存储实例
config_manager.mongodb_storage = MongoDBStorage(
    connection_string=mongodb_conn,
    database_name=mongodb_db
)
```

**时间线**：

```
import 时:  finagentlab/__init__.py → config_manager = ConfigManager()
           → config_manager._init_mongodb_storage()
           → USE_MONGODB_STORAGE 还是 "false"（桥接还没执行）
           → MongoDB 存储初始化失败 → 回退到 JSON 文件存储

启动后:    bridge_config_to_env()
           → os.environ["USE_MONGODB_STORAGE"] = "true"
           → 重新创建 MongoDBStorage → 成功连上
```

### 2.8 配置桥接失败会怎样？

```python
except Exception as e:
    logger.error(f"配置桥接失败: {e}")
    logger.warning("FinAgentLab 将使用 .env 文件中的配置")
    return False   # 返回 False，但不抛异常，不阻止启动
```

桥接是整个启动流程中**唯一的非关键步骤**——失败了只警告，继续启动。Agent 引擎会用 `.env` 里的配置兜底。

---

## 3. 第 5 步：应用动态设置

### 3.1 代码

```python
# app/main.py lifespan 中
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

### 3.2 为什么日志要调两次？

```
[步骤 1] setup_logging()
          此时用 logging.toml 里的默认级别（INFO）
          因为 MongoDB 还没连，读不到用户配置

[步骤 3] init_db()
          MongoDB 连上了

[步骤 5] get_effective_system_settings()
          从 MongoDB 读出用户配的 log_level
          可能用户在 Web UI 里设了 "DEBUG"
          
          setup_logging(log_level="DEBUG")   ← 第二次调用，覆盖为 DEBUG
          logging.getLogger("webapi").setLevel("DEBUG")
          logging.getLogger("worker").setLevel("DEBUG")
          ...
```

### 3.3 `ConfigProvider` — 配置的来源和缓存

```python
class ConfigProvider:
    def __init__(self, ttl_seconds=60):
        self._cache_settings = None   # 缓存
        self._cache_time = None       # 缓存时间
        self._ttl = timedelta(seconds=60)  # 60 秒过期

    async def get_effective_system_settings(self):
        # 缓存没过期 → 直接返回
        if self._is_cache_valid():
            return self._cache_settings

        # 缓存过期了 → 从 MongoDB 重新读
        cfg = await config_service.get_system_config()
        base = dict(cfg.system_settings) if cfg else {}

        # 优先级：环境变量 > MongoDB
        # 环境变量里有的 key → 覆盖 MongoDB 的值
        for key in base:
            if key in os.environ:
                base[key] = os.environ[key]

        self._cache_settings = base
        self._cache_time = datetime.now(timezone.utc)
        return base
```

**60 秒 TTL 缓存**：不会每次请求都查 MongoDB——启动时查一次，之后 60 秒内的请求直接用缓存。如果用户通过 Web UI 改了设置，最多等 60 秒生效（或者调用 `invalidate()` 立即使缓存失效）。

### 3.4 为什么放在 init_db 之后？

```
依赖链:
  ConfigProvider.get_effective_system_settings()
    → config_service.get_system_config()
    → MongoDB 查询
    → 需要 init_db() 先完成
```

---

## 4. 三步之间的关系图

```
┌────────────────────────────────────────────────────────────────┐
│ 第 3 步: init_db()                                              │
│ ┌──────────────┐    ┌──────────────┐                           │
│ │ MongoDB 连接池 │    │ Redis 连接池   │  ← 后续所有操作的基础     │
│ │ min=10 max=100│    │ max=20       │                           │
│ └──────┬───────┘    └──────┬───────┘                           │
│        │                   │                                    │
│        └────────┬──────────┘                                    │
│                 ▼                                               │
│  创建视图(stock_screening_view) + 索引(6个)                      │
└────────────────────────────────────────────────────────────────┘
        │
        │ MongoDB 已可用
        ▼
┌────────────────────────────────────────────────────────────────┐
│ 第 4 步: bridge_config_to_env()                                  │
│                                                                 │
│  MongoDB 里的配置          →  os.environ                        │
│  · LLM API Key (DeepSeek)  →  DEEPSEEK_API_KEY                  │
│  · 默认模型                →  FINAGENTLAB_DEFAULT_MODEL        │
│  · 数据源 Token            →  TUSHARE_TOKEN                     │
│  · 系统运行时参数          →  TA_HK_TIMEOUT, TA_USE_APP_CACHE   │
│                                                                 │
│  效果: Agent 引擎通过 os.getenv() 就能读到 Web UI 配的模型参数     │
│  失败: 只警告，不阻止启动（用 .env 兜底）                         │
└────────────────────────────────────────────────────────────────┘
        │
        │ 环境变量已就绪
        ▼
┌────────────────────────────────────────────────────────────────┐
│ 第 5 步: 应用动态设置                                            │
│                                                                 │
│  从 MongoDB 读 system_settings:                                 │
│    log_level          → 覆盖步骤 1 的默认日志级别                  │
│    enable_monitoring  → 开关操作日志中间件                        │
│                                                                 │
│  效果: 用户通过 Web UI 改的日志级别在重启后生效                    │
│  失败: 只警告，继续（用默认值）                                    │
└────────────────────────────────────────────────────────────────┘
```

---

## 5. 总结

| 步骤 | 做什么 | 失败了怎样 |
|---|---|---|
| **init_db** | 创建 MongoDB 连接池 + Redis 连接池 + 建立索引和视图 | **抛异常，阻止启动**（数据库是核心依赖） |
| **bridge_config** | 把 MongoDB 里的模型/数据源配置写入 `os.environ` | 警告，继续启动（Agent 用 .env 兜底） |
| **动态设置** | 用 MongoDB 里的用户配置覆盖日志级别和监控开关 | 警告，继续（用默认值） |

**一句话**：第 3 步是**核心依赖**（没数据库啥都干不了），第 4 步是**配置传递**（让 Agent 引擎感知到 Web UI 的配置），第 5 步是**运行时调整**（让用户偏好生效）。

---

> **上一文档**：[启动配置验证](startup-validation-deep-dive-v1.md)
>
> **相关文档**：[日志系统详解](logging-system-deep-dive-v1.md) · [后端全景指南](backend-comprehensive-guide-v1.md)
