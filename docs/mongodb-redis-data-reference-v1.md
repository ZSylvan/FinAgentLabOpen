# FinAgentLab 数据库与缓存数据参考 — v1

> **目标**：知道 MongoDB 每个集合存了什么、Redis 每个 key 干什么，以及它们分别由谁写入、被谁读取。

---

## 1. MongoDB

数据库名：`finagentlab`（由 `.env` 的 `MONGODB_DATABASE` 指定）

### 1.1 集合总览

```
finagentlab/
├── ===== 股票数据（Agent 引擎用）=====
├── stock_basic_info         股票基本信息（代码/名称/行业/市值）
├── stock_daily_quotes       日线行情（开高低收量/技术指标）
├── stock_financial_data     财务数据（ROE/利润/现金流）
├── financial_data_cache     财务数据缓存（Agent 读的副本）
├── market_quotes            实时行情快照（前端展示用）
├── stock_news               股票新闻（标题/来源/情感）
├── social_media_messages    社交媒体舆情（前端展示用）
│
├── ===== 配置与管理（Web UI 操作）=====
├── system_configs           系统配置（LLM 列表 / 数据源 / 系统设置）
├── llm_providers            LLM 厂家定义（API 地址/密钥/别名）
├── datasource_groupings     数据源与市场的分组关系
│
├── ===== 业务数据（运行时产生）=====
├── users                    用户账号（登录信息/偏好/自选股）
├── analysis_tasks           分析任务（task_id/状态/结果）
├── analysis_batches         批量分析批次
├── operation_logs           操作审计日志
├── notifications            用户通知（读完/未读）
├── favorites                用户自选股（代码/预警价/标签）
│
├── ===== 缓存（Agent 引擎写入）=====
├── stock_data               行情数据缓存（MongoDB 作为缓存后端时）
├── news_data                新闻数据缓存（MongoDB 作为缓存后端时）
├── fundamentals_data        基本面数据缓存（MongoDB 作为缓存后端时）
├── cache                    通用键值缓存（三层缓存中的 MongoDB 层）
│
├── ===== 运维=====
├── quotes_ingestion_status  行情入库任务运行状态
└── token_usage              Token 使用统计记录
```

---

### 1.2 股票数据集合（Agent 引擎读这些做分析）

#### `stock_basic_info` — 股票基本信息

| 谁写入 | 定时同步任务（多数据源：Tushare/AKShare/BaoStock） |
|---|---|
| 谁读取 | 前端股票搜索/筛选、Agent 分析时获取公司名称 |

**存储内容**：

```json
{
  "code": "000002",
  "name": "万科A",
  "source": "akshare",
  "industry": "房地产开发",
  "area": "深圳",
  "market": "A股",
  "list_date": "1991-01-29",
  "total_mv": 123456789000,       // 总市值（元）
  "circ_mv": 98765432100,        // 流通市值（元）
  "pe": 8.5,                     // 市盈率
  "pb": 0.9,                     // 市净率
  "pe_ttm": 7.8,                 // 滚动市盈率
  "pb_mrq": 0.85,                // 最近一季市净率
  "turnover_rate": 2.1,          // 换手率（%）
  "volume_ratio": 1.2,           // 量比
  "updated_at": "2025-07-08T06:30:00"
}
```

**索引**：`(code, source)` 唯一索引、`(industry)`、`(total_mv)` 降序、`(pe)`、`(pb)`

#### `stock_daily_quotes` — 个股日线行情

| 谁写入 | Tushare/AKShare/BaoStock 的历史数据同步任务 |
|---|---|
| 谁读取 | Agent 市场分析师获取技术指标、`market_quotes` 冷启动兜底 |

**存储内容**：

```json
{
  "symbol": "000002",
  "trade_date": "2025-07-04",
  "period": "daily",
  "data_source": "akshare",
  "open": 8.82,
  "high": 8.89,
  "low": 8.68,
  "close": 8.87,
  "volume": 123456789,
  "amount": 1098765432,
  "pct_chg": 2.1,               // 涨跌幅（%）
  "pre_close": 8.69,            // 前收盘价
  "ma5": 9.20,                  // 5 日均线
  "ma10": 8.76,                 // 10 日均线
  "ma20": 8.02,                 // 20 日均线
  "ma60": 8.45,                 // 60 日均线
  "dif": 0.3839,                // MACD DIF
  "dea": 0.1909,                // MACD DEA
  "macd": 0.3859,               // MACD 柱
  "rsi6": 56.64,                // RSI（同花顺风格）
  "rsi12": 61.08,
  "rsi24": 55.51,
  "boll_up": 9.88,              // 布林带上轨
  "boll_mid": 8.02,             // 布林带中轨
  "boll_low": 6.16              // 布林带下轨
}
```

> **注意**：技术指标（MA/MACD/RSI/BOLL）是数据同步时预计算的，不是 Agent 分析时实时算的。Agent 直接读已有数据即可。

#### `market_quotes` — 实时/近实时行情快照（前端展示）

| 谁写入 | 定时采集任务（每 N 秒）+ 启动期兜底补数 |
|---|---|
| 谁读取 | 前端行情页面、前端股票筛选、Agent 分析时获取当前价 |

**存储内容**：

```json
{
  "code": "000002",
  "symbol": "000002",
  "close": 8.87,                // 最新价
  "open": 8.82,
  "high": 8.89,
  "low": 8.68,
  "pct_chg": 2.1,               // 涨跌幅
  "amount": 1098765432,          // 成交额（元）
  "volume": 123456789,           // 成交量（股）
  "pre_close": 8.69,
  "trade_date": "20250704",
  "updated_at": "2025-07-08T15:30:06+08:00"
}
```

**和 `stock_daily_quotes` 的区别**：`stock_daily_quotes` 每只股票每天一条，存全量历史 + 技术指标。`market_quotes` 每只股票只有一条（最新快照），只存行情核心字段，前端打开页面能毫秒级读到全市场 5000+ 只股票的当前价。

#### `stock_financial_data` — 财务报表数据（原始）

| 谁写入 | 财务数据同步任务（Tushare/AKShare） |
|---|---|
| 谁读取 | `stock_screening_view` 视图、`OptimizedChinaDataProvider` 基本面分析 |

**存储内容**：

```json
{
  "code": "000002",
  "data_source": "tushare",
  "report_period": "2024Q3",
  "roe": 8.5,                   // 净资产收益率（%）
  "roa": 2.3,                   // 总资产收益率（%）
  "netprofit_margin": 12.1,      // 净利润率（%）
  "gross_margin": 25.6,          // 毛利率（%）
  "total_revenue": 12345678900,  // 营业总收入（元）
  "net_profit": 1234567890,      // 净利润（元）
  "eps": 0.85,                   // 每股收益
  "bvps": 8.20,                  // 每股净资产
  "updated_at": "2025-07-08T03:00:00"
}
```

#### `financial_data_cache` — 财务数据缓存（Agent 引擎读的副本）

| 谁写入 | `OptimizedChinaDataProvider._generate_fundamentals_report()` |
|---|---|
| 谁读取 | Fundamentals Analyst 的 `get_stock_fundamentals_unified()` 工具 |

**存储内容**：

```json
{
  "code": "000002",
  "cached_at": "2025-07-08T15:30:00",
  "data_source": "akshare",
  "fundamentals_report": "## 万科A 基本面分析\nPE: 8.5\nPB: 0.9\n..."  // 预计算的文本报告
}
```

> **和 `stock_financial_data` 的区别**：`stock_financial_data` 存的是结构化原始数据（ROE=8.5、EPS=0.85），`financial_data_cache` 存的是**已经格式化为 LLM 可读文本的缓存**。Agent 工具读后者，不用每次从原始数据重新生成报告文本。

#### `stock_news` — 股票新闻

| 谁写入 | 新闻同步任务（只同步自选股） |
|---|---|
| 谁读取 | News Analyst 的 `get_stock_news_unified()` 工具 |

**存储内容**：

```json
{
  "symbol": "000002",
  "title": "万科A获机构增持评级",
  "content": "全文...",
  "source": "东方财富",
  "url": "https://...",
  "publish_time": "2025-07-04T10:30:00",
  "sentiment": "positive",          // positive / negative / neutral
  "created_at": "2025-07-04T15:00:00"
}
```

#### `social_media_messages` — 社交媒体舆情

| 谁写入 | 定时新闻/情绪同步任务 |
|---|---|
| 谁读取 | 前端舆情展示页面 |

**存储内容**：

```json
{
  "symbol": "000002",
  "platform": "雪球",
  "content": "万科今天这个走势...",
  "sentiment": "negative",
  "publish_time": "2025-07-04T11:00:00",
  "created_at": "2025-07-04T15:00:00"
}
```

#### `stock_screening_view` — 股票筛选视图（MongoDB View）

| 谁创建 | `init_database_views_and_indexes()` 启动时 |
|---|---|
| 谁读取 | 前端股票多条件筛选 API |
| 说明 | **不是真正的集合**，是 MongoDB 视图。通过 `$lookup` 把 `stock_basic_info` + `market_quotes` + `stock_financial_data` 三表关联成一张虚拟表，前端筛选时不用做 JOIN，直接从这个视图查询即可。 |

---

### 1.3 配置与管理集合

#### `system_configs` — 系统配置主表

| 谁写入 | Web UI 配置管理页面 |
|---|---|
| 谁读取 | `config_service` → `ConfigProvider` → 桥接时写入 `os.environ` |

**存储内容**：

```json
{
  "config_name": "default",
  "config_type": "system",
  "is_active": true,
  "version": 5,

  "llm_configs": [
    {
      "provider": "deepseek",
      "model_name": "deepseek-chat",
      "api_key": "sk-xxx",
      "max_tokens": 4000,
      "temperature": 0.7,
      "timeout": 180,
      "enabled": true,
      "input_price_per_1k": 0.002,
      "output_price_per_1k": 0.008,
      "currency": "CNY",
      "suitable_roles": ["quick_analysis"],
      "features": ["tool_calling", "cost_effective"]
    }
  ],

  "data_source_configs": [
    {
      "name": "Tushare",
      "type": "tushare",
      "api_key": "xxx",
      "timeout": 30,
      "rate_limit": 100,
      "enabled": true
    }
  ],

  "system_settings": {
    "log_level": "INFO",
    "enable_monitoring": true,
    "ta_use_app_cache": true,
    "app_timezone": "Asia/Shanghai",
    "enable_cost_tracking": true
  }
}
```

#### `llm_providers` — LLM 厂家定义

| 谁写入 | 初始化脚本 (`app/scripts/init_providers.py`) |
|---|---|
| 谁读取 | 配置桥接时读取 API Key、Web UI 展示厂家列表 |

**存储内容**：

```json
{
  "name": "deepseek",
  "display_name": "DeepSeek",
  "description": "DeepSeek 大模型",
  "website": "https://platform.deepseek.com/",
  "is_active": true,
  "default_base_url": "https://api.deepseek.com",
  "api_key": "sk-xxx",
  "aliases": ["ds", "deepseek-chat"],
  "supported_features": ["tool_calling", "long_context"],
  "is_aggregator": false
}
```

> **和 `system_configs.llm_configs` 的区别**：`llm_providers` 定义的是**厂家本身**（叫什么、API 地址是什么），`system_configs.llm_configs` 定义的是**你用该厂家的哪个模型 + 什么参数**。一个厂家可以有多个模型配置（如 DeepSeek 的 `deepseek-chat` 和 `deepseek-reasoner` 是两个 `LLMConfig`）。

#### `datasource_groupings` — 数据源分组

| 谁写入 | Web UI 数据源配置 |
|---|---|
| 谁读取 | `DataSourceManager` 选择数据源时决定优先级 |

```json
{
  "data_source_name": "tushare",
  "market_category_id": "china_a",
  "priority": 1,
  "enabled": true
}
```

用于管理"分析 A 股时用哪个数据源、分析美股时用哪个数据源"的映射关系。

---

### 1.4 业务数据集合

#### `users` — 用户账号

```json
{
  "_id": ObjectId("..."),
  "username": "admin",
  "email": "admin@example.com",
  "hashed_password": "$2b$12$...",
  "is_active": true,
  "is_admin": true,
  "daily_quota": 1000,
  "concurrent_limit": 3,
  "total_analyses": 156,
  "preferences": {
    "default_market": "A股",
    "default_depth": "3",
    "ui_theme": "light"
  },
  "favorite_stocks": [
    {
      "stock_code": "000002",
      "stock_name": "万科A",
      "market": "A股",
      "tags": ["地产"],
      "alert_price_high": 12.0,
      "alert_price_low": 7.0
    }
  ],
  "created_at": "2025-01-01T00:00:00+08:00",
  "last_login": "2025-07-08T15:00:00+08:00"
}
```

#### `analysis_tasks` — 分析任务

| 谁写入 | `analysis_service` 提交分析 → Worker 更新状态和结果 |
|---|---|
| 谁读取 | 前端查询分析进度和结果 |

```json
{
  "_id": ObjectId("..."),
  "task_id": "task_abc123",
  "user_id": ObjectId("..."),
  "symbol": "000002",
  "stock_name": "万科A",
  "status": "completed",           // pending / processing / completed / failed / cancelled
  "progress": 100,                  // 0-100
  "parameters": {
    "market_type": "A股",
    "research_depth": "标准",
    "selected_analysts": ["market", "fundamentals", "news", "social"]
  },
  "result": {
    "summary": "基于多智能体综合分析，建议买入万科A...",
    "recommendation": "买入",
    "confidence_score": 0.85,
    "risk_level": "medium",
    "tokens_used": 24500,
    "execution_time": 128.5,
    "model_info": "deepseek-chat / deepseek-reasoner"
  },
  "retry_count": 0,
  "created_at": "2025-07-08T15:30:00+08:00",
  "completed_at": "2025-07-08T15:32:10+08:00"
}
```

#### `analysis_batches` — 批量分析批次

```json
{
  "batch_id": "batch_xyz789",
  "user_id": ObjectId("..."),
  "title": "地产板块分析",
  "status": "completed",
  "total_tasks": 5,
  "completed_tasks": 5,
  "failed_tasks": 0,
  "progress": 100,
  "created_at": "2025-07-08T15:30:00+08:00",
  "completed_at": "2025-07-08T15:40:00+08:00"
}
```

#### `operation_logs` — 操作审计日志

| 谁写入 | `OperationLogMiddleware` 拦截 POST/PUT/DELETE 请求 |
|---|---|
| 谁读取 | Web UI 操作日志页面、管理员审计 |

```json
{
  "user_id": "admin",
  "username": "admin",
  "action_type": "stock_analysis",
  "action": "创建单股分析任务",
  "details": {
    "method": "POST",
    "path": "/api/analysis/single",
    "status_code": 200
  },
  "success": true,
  "duration_ms": 50,
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "timestamp": "2025-07-08T15:30:00+08:00"
}
```

#### `notifications` — 用户通知

| 谁写入 | Worker 分析完成/失败时、系统维护通知 |
|---|---|
| 谁读取 | 前端通知中心 |

```json
{
  "user_id": "admin",
  "type": "analysis",              // analysis / alert / system
  "title": "分析完成",
  "content": "000002 万科A 分析完成，建议：买入",
  "status": "unread",              // unread / read
  "severity": "success",           // info / success / warning / error
  "link": "/analysis/task_abc123",
  "created_at": "2025-07-08T15:32:10+08:00"
}
```

#### `favorites` — 用户自选股

| 谁写入 | 前端自选股操作 |
|---|---|
| 谁读取 | 前端自选股列表 |

> **注意**：`favorites` 是一个独立集合（用于 API 查询），但 `users` 文档里也有 `favorite_stocks` 嵌入数组。两者可能同时存在，是历史演进导致的冗余。

---

### 1.5 缓存集合（Agent 引擎三层缓存中的 MongoDB 层）

这三个集合只在缓存策略为 `integrated` 或 `adaptive` 时使用（配置项 `TA_CACHE_STRATEGY=integrated`）：

| 集合 | 存的什么 | 过期策略 |
|---|---|---|
| `stock_data` | 行情数据缓存（`{_id: "000002_2025-07-04", data: ..., created_at: ...}`） | 按 `created_at` 过期清理 |
| `news_data` | 新闻数据缓存（`{_id: "000002_news_latest", data: ..., created_at: ...}`） | 同上 |
| `fundamentals_data` | 基本面数据缓存（`{_id: "000002_fundamentals", data: ..., created_at: ...}`） | 同上 |
| `cache` | 通用键值缓存（三层缓存中的 MongoDB 层，`adaptive.py` 使用） | 按 `expires_at` 过期 |

---

### 1.6 运维集合

#### `quotes_ingestion_status` — 行情入库状态

```json
{
  "job": "quotes_ingestion",
  "last_sync_time": "2025-07-08T15:30:06+08:00",
  "success": true,
  "data_source": "tushare",
  "records_count": 5440,
  "interval_seconds": 360,
  "error_message": null
}
```

#### `token_usage` — Token 使用统计

```json
{
  "timestamp": "2025-07-08T15:30:00+08:00",
  "provider": "deepseek",
  "model_name": "deepseek-chat",
  "input_tokens": 15000,
  "output_tokens": 9500,
  "cost": 0.106,
  "currency": "CNY",
  "session_id": "task_abc123",
  "analysis_type": "stock_analysis",
  "stock_code": "000002"
}
```

---

## 2. Redis

### 2.1 Key 全景

Redis 在这个项目里不做持久化存储——所有 key 都有 TTL（过期时间），重启后数据消失。它是"桌面"而不是"仓库"。

所有 Key 的命名前缀定义在 `app/core/redis_client.py` 的 `RedisKeys` 类中。

#### 任务队列

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `user:{user_id}:pending` | List | 用户待执行的分析任务（JSON 字符串） | 无（消费后删除） |
| `user:{user_id}:processing` | Set | 用户正在执行的任务 ID | 即时 |
| `global:pending` | List | 全局待执行的分析任务队列 | 无（消费后删除） |
| `global:processing` | Set | 全局正在执行的任务 ID | 即时 |

**入队/出队流程**：

```
路由 POST /api/analysis/single
  → Redis.LPUSH("global:pending", task_json)
  → Redis.LPUSH("user:user123:pending", task_json)

Worker 循环:
  → Redis.BRPOP("global:pending", timeout=5)  // 阻塞等待
  → 拿到任务 → Redis.SADD("global:processing", task_id)
  → 执行分析
  → Redis.SREM("global:processing", task_id)
```

#### 任务状态

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `task:{task_id}:progress` | String(JSON) | 任务进度 `{"node": "Market Analyst", "pct": 25}` | 分析完成后 1 小时 |
| `task:{task_id}:result` | String(JSON) | 任务结果（和 MongoDB 里存的同结构） | 分析完成后 1 小时 |
| `task:{task_id}:lock` | String | 分布式锁（防止重复执行） | 30 秒 |

#### 批次

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `batch:{batch_id}:progress` | String(JSON) | 批次整体进度 `{"done": 3, "total": 5}` | 完成后 1 小时 |
| `batch:{batch_id}:tasks` | Set | 批次包含的所有 task_id | 完成后 1 小时 |
| `batch:{batch_id}:lock` | String | 批次分布式锁 | 30 秒 |

#### 限流 & 配额

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `rate_limit:{user_id}:{endpoint}` | String(整数) | 用户某端点最近一分钟的请求次数 | 60 秒 |

**工作原理**：

```
每次请求:
  Redis.INCR("rate_limit:admin:/api/analysis/single")  → 返回 5
  Redis.EXPIRE("rate_limit:admin:/api/analysis/single", 60)  → 续 60 秒
  5 < 10(限制)  → 放行

第 11 次:
  Redis.INCR → 返回 11
  11 > 10  → 429 Too Many Requests
```

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `quota:{user_id}:{date}` | String(整数) | 用户今日已使用的分析次数 | 86400 秒（24h） |

#### 会话

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `session:{session_id}` | String(JSON) | 用户登录会话信息 `{"user_id": "admin", "expires_at": ...}` | Token 有效期 |

#### 缓存

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `screening:{cache_key}` | String(JSON) | 股票筛选结果缓存 | 1800 秒（30min） |
| `analysis:{cache_key}` | String(JSON) | 分析结果缓存 | 3600 秒（1h） |

#### 系统控制

| Key 模式 | 类型 | 内容 | TTL |
|---|---|---|---|
| `system:config` | String(JSON) | 系统运行时配置快照 | 60 秒 |
| `queue:stats` | String(JSON) | 队列统计（总任务数/处理中/完成） | 实时 |
| `worker:{worker_id}:heartbeat` | String | Worker 心跳时间戳 | 30 秒 |

**`worker:{worker_id}:heartbeat`**：每个 Worker 进程每 30 秒写一次心跳。如果某个 Worker 超过 30 秒没更新，调度器认为该 Worker 已死，重新把它的任务放回队列。

---

## 3. 快速对照：需要什么数据 → 去哪里找

| 我想查 | 去 MongoDB 哪个集合 | 或 Redis 哪个 key |
|---|---|---|
| 一只股票叫什么名字、什么行业 | `stock_basic_info` | — |
| 一只股票的历史行情数据 | `stock_daily_quotes` | — |
| 前端展示的当前行情 | `market_quotes` | — |
| 一只股票的 PE/PB/ROE | `stock_financial_data` 或 `financial_data_cache` | — |
| 一只股票的最新新闻 | `stock_news` | — |
| 分析任务到哪一步了 | `analysis_tasks` | `task:{task_id}:progress` |
| 用户今天分析了多少次 | `analysis_tasks`（count） | `quota:{user_id}:{date}` |
| 队列里还有多少个任务在排队 | — | `global:pending`（LLEN） |
| 谁在什么时候登录了 | `operation_logs` | — |
| 这个请求为什么被拒绝了 | `operation_logs` | `rate_limit:{user_id}:{endpoint}` |
| LLM 模型配置在哪改 | `system_configs`（Web UI） | — |
| 这次分析花了多少钱 | `token_usage` | — |
