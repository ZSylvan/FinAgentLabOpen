# FinAgentLab 行情兜底 + 定时任务调度器 — 零基础版 v1

> **目标**：理解启动流程的第 7、8 步——为什么启动时要拉一次行情数据、24 个定时任务各自干什么、调度器怎么管理它们。

---

## 1. 第 7 步：行情数据兜底

### 1.1 问题场景

```
场景 A：全新部署
  数据库是空的 → 前端打开行情页面 → 空白
  用户：这软件是不是坏的？

场景 B：周一早上重启了服务器
  上周五收盘后服务就停了 → 周末两天没有任何行情采集
  → market_quotes 集合里的数据还停留在上周五
  → 前端显示的是周五的旧数据（甚至可能为空）

场景 C：正常重启（交易时段内）
  定时任务每 6 分钟采集一次，重启瞬间落后了最多 6 分钟
  → 前端短暂缺少数据，但 6 分钟后定时任务会补上
  → 影响最小
```

**兜底做的事情**：不管什么场景，启动时检查 `market_quotes` 集合，如果缺数据就主动拉一次，保证前端打开就有数据看。

### 1.2 入口代码

```python
# app/main.py lifespan 中
if settings.QUOTES_BACKFILL_ON_STARTUP:       # .env 中默认为 true
    qi = QuotesIngestionService()
    await qi.ensure_indexes()                 # 创建 code 唯一索引 + updated_at 索引
    await qi.backfill_last_close_snapshot_if_needed()  # 核心逻辑
```

### 1.3 `backfill_last_close_snapshot_if_needed()` 的决策树

```python
async def backfill_last_close_snapshot_if_needed(self):
    # 判断 1：集合是不是空的？
    is_empty = await self._collection_empty()   # estimated_document_count() == 0 ?

    if is_empty:
        # → 分支 A：从历史数据批量导入
        await self.backfill_from_historical_data()
        return

    # 判断 2：集合里最新的 trade_date 落后于实际最新交易日？
    manager = DataSourceManager()
    latest_td = manager.find_latest_trade_date_with_fallback()  # 比如返回 20250707
    if await self._collection_stale(latest_td):
        # → 分支 B：调用外部 API 获取最新行情
        await self.backfill_last_close_snapshot()
```

三个分支对应三种场景：

| 场景 | 集合状态 | 走哪个分支 | 做什么 |
|---|---|---|---|
| 全新部署 | `market_quotes` 空 | 分支 A | 从 `stock_daily_quotes` 读全量数据，批量写入 `market_quotes` |
| 停了好几天 | 集合不空，但数据过时 | 分支 B | 调外部 API（Tushare/AKShare）拉最新快照 |
| 正常重启 | 集合不空，数据也是最新的 | 直接跳过 | 什么都不做，最快 |

### 1.4 分支 A：从历史数据批量导入（冷启动）

```python
async def backfill_from_historical_data(self):
    # 1. 确定最新交易日是哪天
    latest_trade_date = manager.find_latest_trade_date_with_fallback()

    # 2. 从 stock_daily_quotes 集合读出该日全量数据
    daily_quotes_collection = db["stock_daily_quotes"]
    cursor = daily_quotes_collection.find({
        "trade_date": latest_trade_date,
        "period": "daily"
    })
    docs = await cursor.to_list(length=None)   # 5000+ 条

    # 3. 逐条转换为 market_quotes 格式
    for doc in docs:
        code = doc.get("symbol") or doc.get("code")
        quotes_map[code] = {
            "close": doc.get("close"),
            "pct_chg": doc.get("pct_chg"),
            "amount": doc.get("amount"),
            "volume": doc.get("volume"),
            "open/high/low/pre_close": ...
        }

    # 4. 批量 upsert 到 market_quotes
    await self._bulk_upsert(quotes_map, latest_trade_date, "historical_data")
```

**为什么从 `stock_daily_quotes` 读而不是调 API？** 调外部 API 获取 5000+ 只股票的单日行情非常慢（几分钟甚至更长），而历史数据同步任务可能已经跑过，`stock_daily_quotes` 里有现成的数据，批量读 MongoDB 只需几秒。

**如果 `stock_daily_quotes` 也是空的？** 那就是首次部署且定时同步还没跑过。`backfill_from_historical_data()` 会打 warning 并跳过。此时需要手动触发一次历史数据同步。

### 1.5 分支 B：调外部 API 获取最新行情（数据过时）

```python
async def backfill_last_close_snapshot(self):
    # 1. 按优先级尝试：Tushare rt_k → AKShare 东方财富 → AKShare 新浪财经
    quotes_map, source = manager.get_realtime_quotes_with_fallback()

    # 2. 写入 market_quotes
    await self._bulk_upsert(quotes_map, trade_date, source)
```

**休市期调用也能拿到数据吗？** 能。Tushare 的 `rt_k` 接口和 AKShare 的行情接口在休市期返回的是**上一个交易日的收盘数据**，不是空。所以即使周日晚重启，也能拿到周五的收盘价。

### 1.6 `_bulk_upsert()` — MongoDB 批量写入

```python
async def _bulk_upsert(self, quotes_map, trade_date, source):
    ops = []
    for code, q in quotes_map.items():
        ops.append(
            UpdateOne(
                {"code": code},           # 查找条件
                {"$set": {                # 更新内容
                    "close": q["close"],
                    "pct_chg": q["pct_chg"],
                    "trade_date": trade_date,
                    "updated_at": now,
                    ...
                }},
                upsert=True               # 存在就更新，不存在就插入
            )
        )
    await coll.bulk_write(ops, ordered=False)   # 5000+ 条并发写入
```

**`ordered=False`**：每条 upsert 独立执行，某一条失败（比如某个股票数据缺失）不影响其他条。

**`upsert=True`**：不管集合里之前有没有这只股票的数据，都能写入。

### 1.7 为什么启动时要兜底？定时任务不能保证吗？

```
定时任务的局限：
  · 只在交易时段执行（9:30-15:30）
  · 每 360 秒（6 分钟）触发一次
  · 如果服务在休市期重启 → 定时任务不触发 → 数据永远不会有

启动兜底的作用：
  · 不管什么时间启动，都检查一次
  · 保证只要服务在运行，market_quotes 就有数据
```

---

## 2. 第 8 步：启动定时任务调度器

### 2.1 APScheduler 是什么

APScheduler（Advanced Python Scheduler）是一个 Python 定时任务框架。它不依赖操作系统（不像 Linux cron），进程内运行，支持"每 N 秒执行一次"、"每天几点执行"、"每周几执行"等触发方式。

```python
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

# 每 360 秒执行一次
scheduler.add_job(my_task, IntervalTrigger(seconds=360))

# 每天 06:30 执行
scheduler.add_job(my_task, CronTrigger(hour=6, minute=30))

scheduler.start()   # 开始调度
```

**为什么用 `AsyncIOScheduler` 而不是普通 `Scheduler`？** 因为所有任务函数都是 `async def`（调外部 API、写 MongoDB），需要异步调度器来 `await` 它们。

### 2.2 先注册再暂停的设计

```python
# 每个任务都先注册
scheduler.add_job(run_tushare_basic_info_sync, ..., id="tushare_basic_info_sync")

# 然后根据配置开关决定是否实际运行
if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_BASIC_INFO_SYNC_ENABLED):
    scheduler.pause_job("tushare_basic_info_sync")
```

**为什么先注册再暂停，而不是根本不注册？**

- 注册后保留 job 定义 → 可以在运行时通过 API **动态启用**
- 如果根本不注册 → 要启用就必须改代码重启

**实际效果**：管理员可以在 Web UI 里看到一个任务列表，每个旁边有一个"启用/暂停"开关。开关背后调的就是 `scheduler.resume_job()` / `scheduler.pause_job()`。

### 2.3 24 个定时任务全景

```
APScheduler
│
├── [启动时立即执行一次] 股票基础信息同步（多数据源）
│    asyncio.create_task(run_sync_with_sources())
│    不阻塞启动，后台跑
│
├── [定时-00] 股票基础信息每日同步（多数据源）
│    每天 06:30（或按 CRON）
│    从 Tushare/AKShare/BaoStock 同步全市场股票的代码/名称/行业/市值
│    → 写入 stock_basic_info
│
├── [定时-01] 实时行情入库
│    每 N 秒（默认 360s = 6 分钟）
│    内部判断是否交易时段（9:30-11:30, 13:00-15:00）
│    交易时段：调用 Tushare/AKShare → 写入 market_quotes
│    非交易时段：如果开启了休市补数，检查是否需要回填
│    → 写入 market_quotes
│
├── Tushare × 5 ────────────────────────────────
│   ├── [定时-02] 基础信息同步
│   │    CRON: 0 2 * * *（每天凌晨 2 点）
│   │    → 写入 stock_basic_info
│   │
│   ├── [定时-03] 实时行情同步
│   │    CRON: */5 9-15 * * 1-5（工作日交易时段每 5 分钟）
│   │    → 写入 stock_daily_quotes
│   │
│   ├── [定时-04] 历史数据同步
│   │    CRON: 0 16 * * 1-5（工作日 16:00）
│   │    → 写入 stock_daily_quotes
│   │
│   ├── [定时-05] 财务数据同步
│   │    CRON: 0 3 * * 0（周日凌晨 3 点）
│   │    → 写入 stock_financial_data
│   │
│   └── [定时-06] 数据源状态检查
│        CRON: 0 * * * *（每小时）
│        → 检查 Tushare API 是否可用，写入 quotes_ingestion_status
│
├── AKShare × 5 ─────────────────────────────────
│   ├── [定时-07] 基础信息同步（每天 03:00）
│   ├── [定时-08] 实时行情同步（工作日交易时段每 30 分钟）
│   ├── [定时-09] 历史数据同步（工作日 17:00）
│   ├── [定时-10] 财务数据同步（周日 04:00）
│   └── [定时-11] 状态检查（每小时第 30 分钟）
│
├── BaoStock × 4 ────────────────────────────────
│   ├── [定时-12] 基础信息同步（每天 04:00）
│   ├── [定时-13] 日K线同步（工作日 16:00，不支持实时行情）
│   ├── [定时-14] 历史数据同步（工作日 18:00）
│   └── [定时-15] 状态检查（每小时第 45 分钟）
│
└── 新闻 × 1 ────────────────────────────────────
    └── [定时-16] 新闻数据同步
         CRON: 按配置（默认每天）
         只同步自选股的新闻，不是全市场
         → 写入 stock_news
```

**总共 21 个注册的定时任务 + 1 个启动时立即执行的异步任务**。

### 2.4 每个 Tushare/AKShare 任务的具体工作

以 Tushare 的任务为例，它们在 `app/worker/tushare_sync_service.py` 中定义：

| 函数 | 调了什么 API | 存到哪个集合 |
|---|---|---|
| `run_tushare_basic_info_sync` | `stock_basic`（全市场股票列表） | `stock_basic_info` |
| `run_tushare_quotes_sync` | 实时行情接口 | `stock_daily_quotes`（当日） |
| `run_tushare_historical_sync` | 历史日线接口 | `stock_daily_quotes`（补全历史） |
| `run_tushare_financial_sync` | 财务报表接口（利润表/资产负债表） | `stock_financial_data` |
| `run_tushare_status_check` | ping / 简单查询 | `quotes_ingestion_status` |

AKShare 和 BaoStock 的任务结构相同，只是调用的 API 不同。

### 2.5 任务时间为什么是错开的

```
Tushare 基础信息  02:00
AKShare 基础信息  03:00
BaoStock 基础信息 04:00
```

**原因**：
1. 避免三个数据源同时全量请求，减少 CPU 和网络瞬时压力
2. 后执行的可以"覆盖"先执行的结果（Tushare 失败 → AKShare 成功 → 最终数据来自 AKShare）

### 2.6 实时行情入库任务的交易时段判断

```python
def _is_trading_time(self, now=None):
    now = now or datetime.now(self.tz)
    if now.weekday() > 4:          # 周六日
        return False

    t = now.time()
    morning  = dtime(9, 30) <= t <= dtime(11, 30)
    afternoon = dtime(13, 0) <= t <= dtime(15, 30)   # 含收盘后 30 分钟缓冲

    return morning or afternoon
```

**收盘后缓冲 30 分钟**：15:00 收盘后继续采到 15:30，确保一定拿到收盘价。假设 6 分钟一次，最多增加 3 次同步机会。

### 2.7 接口轮换机制

```python
def _get_next_source(self):
    # rotation_sources = ["tushare", "akshare_eastmoney", "akshare_sina"]
    current = self._rotation_sources[self._rotation_index]
    self._rotation_index = (self._rotation_index + 1) % 3

    if current == "tushare":
        return "tushare", None
    elif current == "akshare_eastmoney":
        return "akshare", "eastmoney"
    else:
        return "akshare", "sina"
```

**每次调用都在三个接口之间轮换**：

```
第 1 次采集: Tushare
第 2 次采集: AKShare 东方财富
第 3 次采集: AKShare 新浪财经
第 4 次采集: Tushare
...
```

**好处**：避免单一接口被限流（Tushare 免费用户每小时只能调 2 次 `rt_k`）。三次才轮到一次 Tushare，每小时最多调用 `60/6/3 = 3.3` 次左右。

### 2.8 Tushare 免费用户的限流保护

```python
# 用双端队列记录最近一小时的调用时间
self._tushare_call_times = deque()

def _can_call_tushare(self):
    if self._tushare_has_premium:    # 付费用户不限
        return True

    now = datetime.now(self.tz)
    one_hour_ago = now - timedelta(hours=1)

    # 清理 1 小时前的记录
    while self._tushare_call_times and self._tushare_call_times[0] < one_hour_ago:
        self._tushare_call_times.popleft()

    # 最近 1 小时调用超过 2 次？
    if len(self._tushare_call_times) >= 2:
        return False   # 跳过 Tushare，让轮换机制用 AKShare

    return True
```

### 2.9 启动时立即执行一次数据同步

```python
async def run_sync_with_sources():
    await multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources)

asyncio.create_task(run_sync_with_sources())
```

**`asyncio.create_task()`** 创建一个"后台任务"——不阻塞启动流程，在后台跑。效果是：应用已经开始接受请求了，数据同步可能还在跑，但不影响用户使用。

**`force=False`**：增量同步，只更新变化的数据，不全量刷新。首次部署时已有全量历史数据不需要重新拉取。

### 2.10 关闭时的清理

```python
finally:
    if scheduler:
        scheduler.shutdown(wait=False)   # 不等正在执行的任务完成，直接停
```

`wait=False`：收到关闭信号后，正在执行的定时任务不会等完成。因为关闭流程本身很快，不需要等一个可能跑几十秒的数据同步任务。

---

## 3. 总结

| 步骤 | 核心目的 | 最简单理解 |
|---|---|---|
| **第 7 步：行情兜底** | 保证 `market_quotes` 不为空 | "不管什么时候重启，前端打开就有行情看" |
| **第 8 步：定时任务** | 自动化数据同步和行情采集 | "不需要人去手动更新数据，系统自己按时跑" |

---

> **上一文档**：[数据库初始化 + 配置桥接 + 动态设置](startup-db-config-bridge-v1.md)
>
> **下一文档**：[启动完成，应用就绪](backend-comprehensive-guide-v1.md#9-总结)
