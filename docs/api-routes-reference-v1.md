# FinAgentLab API 路由完整参考 — v1

> **目标**：理解项目中每一个 API 端点——它是什么 HTTP 方法、什么 URL、做了什么业务操作、前后端怎么配合的。
>
> **路由总数**：37 个路由文件，约 180+ 个端点，分为 10 个业务域。

---

## 1. 路由系统是怎么工作的

### 1.1 注册机制

每个路由文件定义一个 `router = APIRouter()`，然后在 `app/main.py` 中统一挂载：

```python
# app/main.py
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
```

**最终 URL = main.py 的 prefix + router 内部的 path**。例如：
- `auth.router` 的内部路径是 `/login`
- main.py 挂载时加了 `prefix="/api/auth"`
- 最终前端访问 `POST /api/auth/login`

### 1.2 业务域分组

```
/api/auth/*           认证与用户管理（登录、注册、Token）
/api/analysis/*       核心业务——提交分析、查结果、取消任务
/api/stocks/*         股票数据查询（行情、K线、基本面）
/api/screening/*      高级股票筛选
/api/config/*         系统配置管理（LLM、数据源、模型目录）
/api/system/*         系统运维（数据库管理、日志、操作审计）
/api/stream/*         实时推送（SSE 进度流）
/api/ws/*             实时推送（WebSocket 通知+进度）
/api/scheduler/*      定时任务管理
/api/paper/*          模拟交易（纸上交易）
/api/*                通用业务（收藏、标签、健康检查等）
```

---

## 2. 认证与用户管理 — `auth_db.py`

**挂载**：`/api/auth` | **业务**：用户身份认证和账号管理

### 2.1 `POST /api/auth/login` — 登录

```
前端：用户输入用户名+密码 → POST /api/auth/login
后端：验证密码 → 生成 JWT access_token + refresh_token → 返回
前端：存 token，后续所有请求带 Authorization: Bearer <token>
```

```python
@router.post("/login")
async def login(credentials: UserLogin):
    user = await auth_service.authenticate(credentials.username, credentials.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    access_token = create_jwt_token(user.id, expires_delta=timedelta(minutes=60))
    refresh_token = create_jwt_token(user.id, expires_delta=timedelta(days=30))
    return {"access_token": access_token, "refresh_token": refresh_token, "user": user}
```

### 2.2 `POST /api/auth/refresh` — 刷新 Token

```
access_token 过期了 → 用 refresh_token 换一个新的 access_token
不用重新登录
```

### 2.3 `POST /api/auth/logout` — 登出

```
把当前 Token 加入 Redis 黑名单，在过期时间内不可再用
```

### 2.4 `GET /api/auth/me` — 获取当前用户信息

```
前端从 Token 解析不出用户名/头像 → 调这个接口获取完整用户信息
```

### 2.5 `PUT /api/auth/me` — 更新个人资料

### 2.6 `POST /api/auth/change-password` — 修改密码

### 2.7 `POST /api/auth/reset-password` — 重置密码（管理员）

### 2.8 `POST /api/auth/create-user` — 创建新用户（管理员）

### 2.9 `GET /api/auth/users` — 用户列表（管理员）

---

## 3. 核心分析 — `analysis.py`

**挂载**：`/api/analysis` | **业务**：股票 AI 分析的全生命周期——提交任务、查进度、拿结果、取消、清理

### 3.1 `POST /api/analysis/single` — 提交单股分析（源码级解析）

**最重要的端点**。用户在前端点击“分析”按钮后，最终进入这里。本节不只说明接口用途，而是按当前源码逐层追踪一次请求从 HTTP 入口到 FinAgentLab 分析引擎的全过程。

> **重要校正**：当前 `/single` 路由实际使用 `SimpleAnalysisService` 和 FastAPI `BackgroundTasks`，并不是直接调用旧版 `AnalysisService.submit_single_analysis()`，也不是在本路由中直接执行 `Redis.LPUSH("global:pending")`。旧版队列接口仍由兼容端点 `/analyze` 使用，详见后文。

#### 3.1.1 源码入口与最终 URL

| 层次 | 文件/位置 | 作用 |
|---|---|---|
| 应用挂载 | `app/main.py:688` | `app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])` |
| 路由函数 | `app/routers/analysis.py:39-91` | `submit_single_analysis()` |
| 请求模型 | `app/models/analysis.py:153-162` | `SingleAnalysisRequest` 和 `get_symbol()` |
| 认证依赖 | `app/routers/auth_db.py` | `Depends(get_current_user)` |
| 任务服务 | `app/services/simple_analysis_service.py:704-781` | `create_analysis_task()` |
| 后台执行 | `app/services/simple_analysis_service.py:783-1035` | `execute_analysis_background()` |

最终请求：

```text
POST /api/analysis/single
Authorization: Bearer <access_token>
Content-Type: application/json
```

典型请求体：

```json
{
  "symbol": "000002",
  "parameters": {
    "market_type": "A股",
    "research_depth": "标准",
    "selected_analysts": ["market", "fundamentals", "news", "social"],
    "quick_analysis_model": "qwen-turbo",
    "deep_analysis_model": "qwen-max"
  }
}
```

#### 3.1.2 总流程图：从 HTTP 请求到最终决策

```text
客户端
  |
  | POST /api/analysis/single
  v
app/main.py 挂载 analysis.router
  |
  v
submit_single_analysis()
  |
  +--> get_current_user() 认证
  +--> SingleAnalysisRequest 参数校验
  +--> request.get_symbol() 归一化股票代码
  |
  v
create_analysis_task(user_id, request)
  |
  +--> 生成 UUID task_id
  +--> MemoryStateManager 创建 pending
  +--> MongoDB analysis_tasks upsert
  |
  v
立即返回 task_id
  |
  v
BackgroundTasks.add_task()
  |
  v
execute_analysis_background(task_id, user_id, request)
  |
  +--> 股票校验与日期处理
  +--> RedisProgressTracker / 内存 / MongoDB 更新进度
  +--> 线程池执行 _run_analysis_sync
  +--> 模型、供应商和分析配置
  |
  v
FinAgentLabGraph.propagate()
  |
  +--> LangGraph 多智能体分析
  +--> 返回 state + decision
  |
  v
保存本地报告和 MongoDB analysis_reports
  |
  v
标记 completed / 发布通知 / 清理 tracker

失败分支：任意后台异常 -> ErrorFormatter -> 内存/MongoDB 标记 failed -> 清理 tracker
```

总流程分成两个时段：

1. **HTTP 请求时段**：认证、参数校验、创建任务、注册后台函数，然后快速返回 `task_id`。
2. **后台执行时段**：股票校验、进度跟踪、模型配置、LangGraph 执行、结果保存和状态收尾。

核心状态流转：

```text
内存状态：PENDING -> RUNNING -> COMPLETED / FAILED
MongoDB：  pending -> processing -> completed / failed
Redis：    任务进度、当前消息、分析阶段详情
```

内存使用 `TaskStatus`，MongoDB 使用 `AnalysisStatus` 字符串值；这是两套状态系统。

#### 3.1.3 模块一：请求接入、挂载和参数归一化

```text
客户端
  |
  | POST /api/analysis/single
  v
FastAPI 路由匹配
  |
  v
get_current_user()
  |
  v
解析 JWT，获取 user
  |
  v
SingleAnalysisRequest Pydantic 校验
  |
  +--> symbol 存在：使用 symbol
  +--> symbol 为空：回退 stock_code
  +--> 两者为空：create_analysis_task 抛出异常
  |
  v
request.get_symbol()
  |
  v
传入 user_id 和 request
```

源码级要点：

- `app/main.py:688` 负责挂载，最终路径是 `/api/analysis` 前缀加 `/single`。
- `submit_single_analysis()` 的 `user` 通过 `Depends(get_current_user)` 注入，认证失败不会进入任务创建。
- `SingleAnalysisRequest` 同时保留 `symbol` 和已废弃的 `stock_code`，`get_symbol()` 返回 `symbol or stock_code or ""`。
- 路由只把 `user["id"]` 和请求对象传给服务层，不直接执行股票分析。

#### 3.1.4 模块二：到底什么叫“创建任务”？

先给出最重要的结论：

> **这里的“创建任务”不是实例化 Agent 分析引擎，也不是开始调用大模型。**
>
> 它只是先创建一张“分析工作单”，为后续真正执行分析准备一个唯一编号和状态容器。此时 `FinAgentLabGraph` 还没有创建，LangGraph 也没有运行，LLM 也没有被调用。

可以把它具体化为两个对象：

```text
对象 A：分析引擎
  FinAgentLabGraph
  作用：真正执行市场分析、基本面分析、多空辩论、风险评估和最终决策
  创建时机：后台执行阶段，_run_analysis_sync() 中的 _get_trading_graph()
  当前阶段：尚未创建

对象 B：分析任务状态
  TaskState
  作用：记录这张分析工作单当前处于什么状态
  创建时机：create_analysis_task() 中的 MemoryStateManager.create_task()
  当前阶段：已经创建
```

真实世界类比：

```text
用户到医院挂号：创建“就诊任务单”，获得排队号
    != 医生已经开始诊断

用户提交股票分析：创建“分析任务单”，获得 task_id
    != Agent 分析引擎已经开始运行
```

##### 任务、引擎和任务状态不是同一个东西

| 对象 | 当前阶段是否创建 | 存放什么 | 是否执行 LLM |
|---|---:|---|---:|
| `task_id` | 是 | 一串 UUID，例如 `abc-123...` | 否 |
| 内存 `TaskState` | 是 | task_id、user_id、stock_code、status、progress 等 | 否 |
| MongoDB `analysis_tasks` 文档 | 通常是 | 任务状态的持久化副本 | 否 |
| `RedisProgressTracker` | 股票校验通过后 | 进度百分比、最近消息、阶段进度 | 否 |
| `FinAgentLabGraph` | 后台分析阶段 | Agent 图、LLM、节点状态 | 是，后续会调用 |

##### 这次“创建任务”具体创建了什么

```text
create_analysis_task(user_id, request)
  |
  v
生成 task_id = uuid.uuid4()
  |
  v
读取 stock_code = request.get_symbol()
  |
  v
查询 stock_name
  |
  v
创建 Python 内存对象 TaskState
  |
  +--> task_id = 唯一任务号
  +--> user_id = 谁提交的
  +--> stock_code = 分析哪只股票
  +--> stock_name = 股票名称
  +--> status = PENDING
  +--> progress = 0
  +--> parameters = 研究深度/分析师/模型等
  +--> start_time = 创建任务的时间
  +--> estimated_duration = 预计耗时
  +--> message = 任务已创建，等待执行
  |
  v
把 TaskState 放入 MemoryStateManager._tasks 字典
  |
  v
把相同任务的初始字段写入 MongoDB analysis_tasks
  |
  v
返回 task_id 给前端
```

源码位置：`app/services/simple_analysis_service.py:704-781`；内存状态类定义在 `app/services/memory_state_manager.py:24-138`。

##### 什么叫“内存任务”

“内存任务”不是一个特殊的 Agent，也不是数据库表。它是当前 FastAPI 进程内 Python 内存中的一个 `TaskState` 数据对象：

```python
# app/services/memory_state_manager.py 中的实际结构
TaskState(
    task_id="任务 UUID",
    user_id="用户 ID",
    stock_code="000002",
    status=TaskStatus.PENDING,
    stock_name="万科A",
    progress=0,
    message="任务已创建，等待执行...",
    current_step="",
    start_time=创建时间,
    result_data=None,
    error_message=None,
    parameters={...},
    estimated_duration=预计秒数,
)
```

这些对象由 `MemoryStateManager._tasks` 字典持有：

```python
self._tasks = {
    "任务 UUID 1": TaskState(...),
    "任务 UUID 2": TaskState(...),
}
```

因此，“创建内存任务”可以翻译成一句更具体的话：

> **实例化一个 `TaskState`，把它放进当前 Python 进程的 `_tasks` 字典，以便后端可以通过 task_id 快速查询和修改任务状态。**

源码中的 `create_task()` 做的事情是：

1. 根据分析参数计算预计耗时。
2. 实例化 `TaskState(...)`。
3. 设置 `status=TaskStatus.PENDING` 和 `progress=0`。
4. 执行 `self._tasks[task_id] = task_state`。
5. 返回这个 `TaskState` 对象。

##### 内存任务和 MongoDB 任务有什么区别

```text
同一张分析工作单
        |
        +--> 内存 TaskState
        |      速度快，当前进程内查询
        |      进程重启后会消失
        |
        +--> MongoDB analysis_tasks 文档
               持久化，可在进程重启后恢复
               查询和写入速度相对更慢
```

它们不是两个不同的分析任务，而是同一个 `task_id` 的两个状态副本：

```text
task_id = abc123
  |
  +--> MemoryStateManager._tasks["abc123"]
  +--> MongoDB.analysis_tasks.find_one({"task_id": "abc123"})
```

当前实现采用“内存优先、MongoDB 兜底”的思路：状态查询先查内存，内存中没有时再查 MongoDB。

##### 这一阶段明确没有发生什么

创建任务完成后，以下事情都**还没有发生**：

- 没有实例化 `FinAgentLabGraph`。
- 没有执行 `FinAgentLabGraph.propagate()`。
- 没有运行市场分析师、基本面分析师或风险管理 Agent。
- 没有调用 LLM API。
- 没有生成最终投资建议。
- 没有写入 `analysis_reports` 最终报告。

当前只完成了：

```text
登记一张工作单 -> 分配 task_id -> 记录 PENDING -> 告诉前端“已收到”
```

##### MongoDB 初始记录

MongoDB 这一步不是保存最终报告，而是保存任务登记信息：

```json
{
  "task_id": "abc123",
  "user_id": "用户 ID",
  "stock_code": "000002",
  "stock_symbol": "000002",
  "stock_name": "万科A",
  "status": "pending",
  "progress": 0,
  "created_at": "创建时间"
}
```

`analysis_tasks` 文档相当于数据库中的“工作单”；真正的分析报告之后写入 `analysis_reports`。

##### 创建任务流程

```text
create_analysis_task(user_id, request)
  |
  v
uuid.uuid4() 生成 task_id
  |
  v
request.get_symbol()
  |
  +--> 为空：抛出“股票代码不能为空”
  +--> 非空：继续
  |
  v
_resolve_stock_name()
  |
  +--> 数据源获取股票名称
  +--> 失败时回退为 股票{code}
  |
  v
MemoryStateManager.create_task()
  |
  v
实例化 TaskState 并放入 _tasks 字典
  |
  v
内存状态：PENDING，progress=0
  |
  v
MongoDB analysis_tasks.update_one()
  |
  v
$setOnInsert + upsert=True
  |
  v
返回 task_id / pending / message
```

路由返回：

```json
{
  "success": true,
  "data": {
    "task_id": "<uuid>",
    "status": "pending",
    "message": "任务已创建，等待执行"
  },
  "message": "分析任务已在后台启动"
}
```

路由返回：

```json
{
  "success": true,
  "data": {
    "task_id": "<uuid>",
    "status": "pending",
    "message": "任务已创建，等待执行"
  },
  "message": "分析任务已在后台启动"
}
```

#### 3.1.5 模块三：BackgroundTasks 到底是什么

先给出具体结论：

> **`BackgroundTasks` 不是 Agent、不是任务状态对象、不是 Redis 队列，也不是一个新的分析引擎。**
>
> 它是 FastAPI 提供的一个“响应发送之后再调用某个函数”的执行安排器。

把它想象成前台工作人员：

```text
前台工作人员：收到分析申请，先给客户一张受理单（task_id）
后台工作人员：HTTP 响应发出去后，继续处理这张受理单
客户：拿着 task_id 离开，不需要一直等待工作人员处理完成
```

在本项目中，`BackgroundTasks` 安排的不是 `FinAgentLabGraph`，而是路由内部定义的普通 Python 异步函数 `run_analysis_task`：

```text
submit_single_analysis()
  |
  +--> create_analysis_task(user_id, request)
  |       |
  |       +--> 返回 task_id
  |
  +--> 定义 run_analysis_task() 函数
  |       |
  |       +--> get_simple_analysis_service()
  |       +--> await execute_analysis_background(task_id, user_id, request)
  |
  +--> background_tasks.add_task(run_analysis_task)
  |
  v
当前路由函数结束
  |
  v
FastAPI 发送 HTTP 响应给客户端
  |
  v
FastAPI 在响应之后调用 run_analysis_task()
  |
  v
execute_analysis_background()
  |
  v
后续才会校验股票、创建进度 tracker、创建 FinAgentLabGraph
```

##### `add_task()` 具体保存了什么

执行下面这句时：

```python
background_tasks.add_task(run_analysis_task)
```

FastAPI 并没有执行 `run_analysis_task()`，也没有执行 Agent。它做的是把下面的信息登记到当前请求的后台任务列表中：

```text
待执行函数：run_analysis_task
函数参数：无（参数已经通过闭包捕获 task_id/user_id/request）
执行时机：当前 HTTP 响应发送之后
```

可以把它近似理解为：

```python
# 不是实际源码，只用于理解
response = make_http_response(task_id)
background_task_list.append(run_analysis_task)
send(response)
for task in background_task_list:
    await task()
```

实际项目中的包装函数大致是：

```python
async def run_analysis_task():
    service = get_simple_analysis_service()
    await service.execute_analysis_background(
        task_id,
        user_id,
        request,
    )
```

##### 时间顺序：客户端什么时候拿到响应

```text
T0 客户端发送 POST /api/analysis/single
  |
T1 FastAPI 验证请求和用户
  |
T2 create_analysis_task 创建 TaskState 和 analysis_tasks 初始文档
  |
T3 add_task(run_analysis_task) 登记后台函数
  |
T4 submit_single_analysis 返回 response 字典
  |
T5 客户端收到 task_id
  |
T6 HTTP 响应发送完成
  |
T7 FastAPI 执行 run_analysis_task()
  |
T8 execute_analysis_background 开始真正的分析准备
  |
T9 后续才创建 FinAgentLabGraph 并调用 LLM
```

所以，前端拿到下面的响应时：

```json
{
  "task_id": "abc123",
  "status": "pending"
}
```

它表达的不是“Agent 已经分析完成”，而是：

> **后端已经登记这张分析工作单，并承诺尝试在后台处理它。**

##### `BackgroundTasks` 和真正的分析引擎的关系

```text
BackgroundTasks
  负责：什么时候调用后台函数
  不负责：股票分析逻辑

execute_analysis_background()
  负责：准备、校验、状态更新、调用同步分析包装器

_execute_analysis_sync() / _run_analysis_sync()
  负责：把真正的同步分析放入线程池执行

FinAgentLabGraph
  负责：构建并运行 Agent 分析图
```

完整关系：

```text
BackgroundTasks
  |
  v
run_analysis_task()
  |
  v
execute_analysis_background()
  |
  v
_execute_analysis_sync()
  |
  v
_run_analysis_sync()
  |
  v
_get_trading_graph()
  |
  v
FinAgentLabGraph.propagate()
  |
  v
真正的 Agent/LLM 分析
```

##### 它不是可靠任务队列

当前 `BackgroundTasks` 依附于运行 FastAPI 的进程：

```text
FastAPI 进程仍然存活
  |
  +--> 后台函数通常可以继续执行

FastAPI 进程崩溃/重启
  |
  +--> 已登记但尚未执行的后台函数可能丢失
  +--> 内存 TaskState 一定会丢失
  +--> MongoDB 初始任务记录可能仍然存在
```

因此它与 Redis Queue + Worker 的区别是：

| 机制 | 具体含义 | 可靠性 |
|---|---|---|
| `BackgroundTasks` | 当前 FastAPI 进程响应后继续调用函数 | 简单，但不持久化 |
| `asyncio.create_task()` | 当前事件循环中创建协程任务 | 进程内并发，不持久化 |
| Redis Queue + Worker | 任务写入 Redis，由独立 Worker 消费 | 可跨进程、可扩展、可增加重试 |

关键点：

- 注册的是路由内部包装函数，不是直接把同步分析函数塞入线程池。
- 包装函数重新调用 `get_simple_analysis_service()`，再 `await execute_analysis_background(...)`。
- `BackgroundTasks` 依赖当前 FastAPI 进程，不是持久化分布式队列。
- 批量 `/batch` 使用 `asyncio.create_task()`，旧兼容 `/analyze` 使用 `QueueService`，三者不能混为一谈。

#### 3.1.6 模块四：股票校验与分析初始化

```text
execute_analysis_background()
  |
  v
request.get_symbol()
  |
  v
读取 market_type 和 analysis_date
  |
  +--> datetime：格式化为 YYYY-MM-DD
  +--> str：解析并重新格式化
  +--> 格式错误：回退当天
  |
  v
prepare_stock_data_async()
  |
  +--> 无效：内存 FAILED -> MongoDB failed -> return
  +--> 有效：记录市场、历史数据和基本信息
  |
  v
进入进度跟踪和 AI 引擎初始化
```

源码位置：`app/services/simple_analysis_service.py:783-873`。

- 默认市场类型是 `A股`，日期来自请求参数；日期格式错误时回退当天。
- `prepare_stock_data_async()` 负责代码合法性、市场类型、历史数据和基本信息验证。
- 校验失败会直接更新失败状态并 `return`，不会创建 `FinAgentLabGraph`。
- 源码中股票校验失败分支把 `AnalysisStatus.FAILED` 传给内存管理器，而内存完成时间判断使用 `TaskStatus`；这是值得记录的枚举边界。

#### 3.1.7 模块五：三套进度系统如何协同

```text
股票校验通过
  |
  v
asyncio.to_thread(create_progress_tracker)
  |
  v
RedisProgressTracker
  |
  +--> 缓存到 _progress_trackers[task_id]
  +--> register_analysis_tracker()
  +--> Redis 进度 10%
  |
  v
内存 TaskStatus.RUNNING
  |
  v
MongoDB AnalysisStatus.PROCESSING
  |
  v
数据准备进度 20%
  |
  v
LangGraph graph_progress_callback()
  |
  +--> Redis：更新百分比和最近消息
  +--> 内存：更新 progress/current_step
  +--> MongoDB：更新 progress/current_step/message
  |
  v
状态接口 / WebSocket 读取进度
```

| 组件 | 主要用途 | 典型字段 |
|---|---|---|
| `MemoryStateManager` | 低延迟进程内任务状态 | `status`、`progress`、`result_data`、`error_message` |
| `RedisProgressTracker` | 分阶段进度和最近消息 | `progress_percentage`、`last_message` |
| MongoDB `analysis_tasks` | 可恢复的持久化状态 | `status`、`progress`、`started_at`、`completed_at`、`last_error` |

创建 tracker 和部分同步操作可能阻塞，因此使用 `asyncio.to_thread()`。`graph_progress_callback` 根据节点名称映射进度，在进度增加时同步内存和 MongoDB。

#### 3.1.8 模块六：模型选择、供应商配置和引擎实例

```text
_run_analysis_sync()
  |
  v
读取 research_depth
  |
  +--> 有用户模型：validate_model_pair()
  |       +--> 不适配：recommend_models_for_depth()
  |       +--> 适配：保留用户模型
  +--> 无用户模型：recommend_models_for_depth()
  |
  v
查询 quick/deep 模型的 provider、backend_url、api_key
  |
  v
create_analysis_config()
  |
  +--> 补充 quick_provider/deep_provider
  +--> 补充 quick_backend_url/deep_backend_url
  |
  v
_get_trading_graph(config)
  |
  v
新建 FinAgentLabGraph
```

源码位置：`app/services/simple_analysis_service.py:1134-1233`。

1. 根据研究深度决定需要的模型能力。
2. 请求指定模型时先用 `validate_model_pair()` 校验，不合适时自动推荐模型。
3. 分别查询快速模型和深度模型的供应商、API 地址和 API Key，因此两者可以来自不同厂家。
4. `create_analysis_config()` 生成配置，并补充混合厂商字段。
5. `_get_trading_graph()` 每次新建 `FinAgentLabGraph`，避免实例中的可变状态在并发任务间串扰。

#### 3.1.9 模块七：线程池、LangGraph 和结果构造

```text
execute_analysis_background()
  |
  v
_execute_analysis_sync()
  |
  v
run_in_executor()
  |
  v
共享 ThreadPoolExecutor（max_workers=3）
  |
  v
_run_analysis_sync()
  |
  +--> update_progress_sync()
  +--> 启动模拟进度线程
  +--> graph_progress_callback()
  |
  v
trading_graph.propagate(stock_code, analysis_date, callback, task_id)
  |
  v
FinAgentLabGraph 创建初始状态
  |
  v
LangGraph graph.stream 执行各 Agent 节点
  |
  +--> 回调更新 Redis/内存/MongoDB
  |
  v
返回 state + decision
  |
  v
提取 reports，格式化 action/target_price/confidence/risk
  |
  v
构造 summary / recommendation / result
```

- `_execute_analysis_sync()` 是异步包装器，将同步 `_run_analysis_sync()` 提交到共享线程池。
- 线程池最大并发数为 3，限制单进程同时执行的同步分析数量。
- `_run_analysis_sync()` 中使用同步 MongoDB 客户端和独立事件循环更新进度，避免在线程中复用主事件循环。
- `trading_graph.propagate()` 接收股票代码、分析日期、进度回调和 `task_id`，返回 `state, decision`。
- `state` 中提取市场、情绪、新闻、基本面、投资计划和最终交易决策；`decision` 被转换成动作、目标价、置信度和风险字段。

> **源码注意点**：`_run_analysis_sync()` 调用 `propagate()` 时使用的是 `request.stock_code`，而前面入口使用的是 `request.get_symbol()`。当请求只传 `symbol` 时，这里存在字段不一致风险。

#### 3.1.10 模块八：结果保存、完成、失败和清理

```text
state + decision 已处理
  |
  v
progress_tracker.mark_completed()
  |
  v
_save_analysis_results_complete()
  |
  +--> 保存 data/analysis_results 模块 Markdown
  +--> 写入 MongoDB analysis_reports
  +--> 更新 analysis_tasks.result
  |
  v
内存 COMPLETED + result_data + progress=100
  |
  v
MongoDB COMPLETED + completed_at
  |
  v
发布 analysis 完成通知
  |
  v
finally：删除 tracker
  |
  v
unregister_analysis_tracker()

异常分支：
任意异常
  |
  v
ErrorFormatter.format_error()
  |
  +--> tracker.mark_failed()
  +--> 内存 FAILED + error_message
  +--> MongoDB FAILED + last_error
  |
  v
finally 清理 tracker
```

成功路径：`simple_analysis_service.py:938-987`；异常路径：`989-1035`。

- 结果保存包括本地模块报告和 MongoDB Web 风格报告；保存异常目前会记录日志，但不会阻止任务被标记为 `completed`。
- 内存状态保存完整 `result_data`，结果接口在进程内可直接返回完整结果。
- 服务重启后，状态和结果接口会尝试从 `analysis_tasks`、`analysis_reports` 恢复。
- 未捕获异常经过 `ErrorFormatter` 转换，再更新 tracker、内存和 MongoDB。
- `finally` 无论成功还是失败都会删除 `_progress_trackers[task_id]` 并注销日志 tracker，避免泄漏。

#### 3.1.11 与状态、结果接口的闭环

```text
客户端
  |
  | POST /single
  v
analysis.py
  |
  +--> MemoryStateManager：创建 PENDING
  +--> MongoDB：analysis_tasks pending
  |
  v
返回 task_id
  |
  +------------------------------+
  |                              |
  v                              v
GET /tasks/{id}/status       GET /tasks/{id}/result
  |                              |
  v                              v
内存优先读取状态             内存优先读取 result_data
  |                              |
  +--> 未找到：MongoDB          +--> 没有结果：查询 analysis_reports
  |       兜底恢复               |
  v                              v
返回 RUNNING/progress         返回 summary/reports/decision

后台进度：
RedisProgressTracker
  +--> 内存 progress/current_step
  +--> MongoDB progress/current_step/message
```

状态接口 `GET /tasks/{task_id}/status` 是内存优先、MongoDB 兜底；结果接口 `GET /tasks/{task_id}/result` 优先取内存 `result_data`，再查询 `analysis_reports`，最后兼容旧任务结果结构。

#### 3.1.12 源码阅读顺序与验证问题

建议按下面顺序打开源码：

```text
1. app/main.py:688
2. app/routers/analysis.py:39-91
3. app/models/analysis.py:32-53, 153-162
4. app/services/simple_analysis_service.py:704-781
5. app/services/simple_analysis_service.py:783-1035
6. app/services/simple_analysis_service.py:1037-1800
7. app/services/memory_state_manager.py
8. app/services/redis_progress_tracker.py
9. finagentlab/graph/trading_graph.py:FinAgentLabGraph.propagate
10. app/routers/analysis.py:104-300
```

阅读后应能回答：

1. 为什么 `/single` 可以快速返回而不等待 LLM？
2. `task_id` 在内存、Redis 和 MongoDB 中分别承担什么作用？
3. 为什么单股接口使用 `BackgroundTasks`，批量接口使用 `asyncio.create_task`？
4. 为什么 `_run_analysis_sync()` 必须放入线程池？
5. `symbol` 和 `stock_code` 兼容逻辑在哪里实现？下游是否都使用了兼容方法？
6. 股票校验失败、模型配置失败、LangGraph 失败和结果保存失败分别产生什么状态？
7. 为什么状态查询需要内存优先、MongoDB 兜底？
8. 如果 MongoDB 初始写入失败，后续状态更新是否会自动创建任务文档？
9. 如果两个任务共享一个 `FinAgentLabGraph` 实例，会产生什么并发问题？
10. 当前“分析完成”是否绝对意味着所有报告都已经成功持久化？

### 3.2 `GET /api/analysis/tasks/{task_id}/status` — 查询任务状态

```
前端每隔 2 秒轮询一次：
  GET /api/analysis/tasks/abc123/status
  → {"status": "processing", "progress": 65, "current_node": "Bull Researcher"}

前端根据 status 显示：
  pending     → "排队中，前面还有 3 个任务"
  processing  → 进度条 + 当前节点名称
  completed   → 跳转到结果页面
  failed      → 显示错误信息
```

### 3.3 `GET /api/analysis/tasks/{task_id}/result` — 获取分析结果

```
分析完成后，前端调此接口获取完整报告：
  → {"action": "买入", "target_price": 18.50, "confidence": 0.85,
      "market_report": "...", "fundamentals_report": "...", ...}
```

### 3.4 `POST /api/analysis/batch` — 提交批量分析

```
一次提交多只股票（最多 10 只），后端创建 batch + 多个 task
每只股票按队列顺序依次分析
```

### 3.5 `POST /api/analysis/tasks/{task_id}/cancel` — 取消任务

```
只有 pending 状态的任务可以取消
Worker 拿到任务后会检查是否已被取消
```

### 3.6 `GET /api/analysis/user/history` — 历史分析记录

```
分页查询用户的所有历史分析（含成功、失败、取消的）
支持按股票代码、日期范围、状态过滤
```

### 3.7 `GET /api/analysis/admin/zombie-tasks` — 僵尸任务

```
有些任务 status 一直是 "processing" 但 Worker 已经死了
"僵尸任务" = 超过 N 小时还没完成的任务
管理员可以批量清理
```

### 3.8 其他端点

| 端点 | 用途 |
|---|---|
| `GET /tasks/all` | 管理员查看所有用户的任务 |
| `GET /tasks` | 当前用户的任务列表 |
| `POST /tasks/{task_id}/mark-failed` | 手动标记失败 |
| `DELETE /tasks/{task_id}` | 删除任务 |
| `GET /user/queue-status` | 当前用户的排队状态 |
| `GET /batches/{batch_id}` | 批次详情 |

---

## 4. 股票数据查询

### 4.1 `stocks.py` — 基础股票接口

**挂载**：`/api/stocks`

| 端点 | 用途 | 数据来源 |
|---|---|---|
| `GET /{code}/quote` | 实时行情（当前价、涨跌幅、成交量） | `market_quotes` 集合 |
| `GET /{code}/fundamentals` | 基本面数据（PE、PB、ROE） | `stock_financial_data` 集合 |
| `GET /{code}/kline` | 历史 K 线数据 | `stock_daily_quotes` 集合 |
| `GET /{code}/news` | 相关新闻 | `stock_news` 集合 |

```python
@router.get("/{code}/quote")
async def get_quote(code: str):
    db = get_mongo_db()
    doc = await db["market_quotes"].find_one({"code": code})
    if not doc:
        raise HTTPException(404, "未找到行情数据")
    return doc
```

### 4.2 `stock_data.py` — 扩展股票数据接口

**挂载**：`/api/stock-data` | **Tags**：`["股票数据"]`

| 端点 | 用途 |
|---|---|
| `GET /basic-info/{symbol}` | 扩展基本信息（含行业、市值、上市日期） |
| `GET /quotes/{symbol}` | 扩展行情（含技术指标） |
| `GET /list` | 分页股票列表（支持按行业/市场过滤） |
| `GET /combined/{symbol}` | 基本信息+行情 合并查询（减少前端请求次数） |
| `GET /search` | 按代码或名称模糊搜索 |
| `GET /markets` | 各市场股票数量统计 |
| `GET /sync-status/quotes` | 行情采集任务运行状态 |

### 4.3 `multi_market_stocks.py` — 跨市场股票查询

**挂载**：`/api/markets` | **Tags**：`["multi-market"]`

```
GET /api/markets                            → 支持的市场列表 ["CN", "HK", "US"]
GET /api/markets/CN/stocks/search?q=万科     → 搜索 A 股
GET /api/markets/HK/stocks/00700/info       → 腾讯基本信息
GET /api/markets/HK/stocks/00700/quote      → 腾讯实时行情
GET /api/markets/US/stocks/AAPL/daily       → 苹果历史 K 线
```

### 4.4 `historical_data.py` — 历史数据查询

**挂载**：`/api/historical-data`

| 端点 | 用途 |
|---|---|
| `GET /query/{symbol}` | 按股票代码查历史 K 线 |
| `POST /query` | 高级查询（POST body 传参数） |
| `GET /latest-date/{symbol}` | 最新数据日期 |
| `GET /statistics` | 历史数据统计 |
| `GET /compare/{symbol}` | 多数据源对比（Tushare vs AKShare 同一天的数据差异） |

### 4.5 `financial_data.py` — 财务数据查询

**挂载**：`/api/financial-data`

| 端点 | 用途 |
|---|---|
| `GET /query/{symbol}` | 查询财务数据（ROE、利润、营收） |
| `GET /latest/{symbol}` | 最新财报数据 |
| `GET /statistics` | 财务数据统计 |
| `POST /sync/start` | 启动财务数据同步 |
| `POST /sync/single` | 同步单只股票财务数据 |

### 4.6 `news_data.py` — 新闻数据查询

**挂载**：`/api/news-data`

| 端点 | 用途 |
|---|---|
| `GET /query/{symbol}` | 查新闻（先读 MongoDB 缓存，没有再调实时 API） |
| `POST /query` | 高级查询（多条件过滤） |
| `GET /latest` | 最新新闻 |
| `GET /search` | 全文搜索新闻 |
| `GET /statistics` | 新闻统计（情感分布、来源分布） |
| `POST /sync/start` | 启动新闻同步 |

### 4.7 `social_media.py` — 社交媒体数据

**挂载**：`/api/social-media`

| 端点 | 用途 |
|---|---|
| `POST /save` | 批量保存舆情消息 |
| `POST /query` | 查询舆情消息 |
| `GET /latest/{symbol}` | 最新舆情 |
| `GET /search` | 搜索舆情 |
| `GET /statistics` | 舆情统计 |
| `GET /platforms` | 支持的平台列表（雪球、东方财富等） |
| `GET /sentiment-analysis/{symbol}` | 情感分析结果 |

---

## 5. 股票筛选 — `screening.py`

**挂载**：`/api/screening` | **业务**：按多维度条件筛选股票

```
用户在前端选条件：行业=房地产, PE<15, 涨跌幅>3%
  → POST /api/screening/enhanced
  → {"conditions": [...], "market": "CN"}
  → 后端查询 stock_screening_view（三表关联视图）
  → 返回符合条件的股票列表
```

```python
@router.post("/enhanced")
async def enhanced_screening(request: ScreeningRequest):
    # 从 stock_screening_view 查询（basic_info + market_quotes + financial_data 已关联好）
    results = await screening_service.run_enhanced_screening(request.conditions, request.market)
    return {"results": results, "total": len(results), "query_time_ms": elapsed}
```

| 端点 | 用途 |
|---|---|
| `GET /fields` | 获取可用的筛选字段列表（前端显示可选项） |
| `POST /run` | 传统格式筛选 |
| `POST /enhanced` | 增强筛选（性能优化版） |
| `POST /validate` | 验证筛选条件是否合法 |
| `GET /industries` | 获取所有行业分类 |

---

## 6. 系统配置管理 — `config.py`

**挂载**：`/api/config` | **业务**：管理 LLM 提供商、模型配置、数据源、系统设置

### 6.1 LLM 提供商管理

```
Web UI 的"设置 → 大模型配置"页面调这些接口：

GET  /api/config/llm/providers          → 列出所有厂家（DeepSeek/OpenAI/千帆...）
POST /api/config/llm/providers          → 添加新厂家
POST /api/config/llm/providers/xxx/test → 测试 API 连通性
```

### 6.2 模型配置管理

```
Web UI 的"设置 → 模型管理"页面：

GET  /api/config/llm              → 当前配了哪些模型
POST /api/config/llm              → 添加一个模型配置（如 deepseek-chat，温度 0.7）
POST /api/config/llm/set-default  → 设为默认模型
```

### 6.3 模型目录

```
Web UI 的"设置 → 模型目录"页面：

GET  /api/config/model-catalog           → 所有厂家的可用模型列表
GET  /api/config/model-catalog/deepseek  → DeepSeek 的模型列表
POST /api/config/model-catalog           → 更新模型目录
POST /api/config/model-catalog/init      → 初始化模型目录
```

### 6.4 数据源配置

```
GET  /api/config/datasource         → 数据源列表（Tushare, AKShare, Finnhub...）
POST /api/config/datasource         → 添加数据源
PUT  /api/config/datasource/tushare → 修改 Tushare 的 Token/超时时间
```

### 6.5 市场分类

```
GET  /api/config/market-categories              → 市场分类列表（A股/港股/美股）
POST /api/config/market-categories              → 添加分类
PUT  /api/config/market-categories/{id}         → 修改分类
POST /api/config/datasource-groupings           → 把数据源关联到市场分类
```

### 6.6 系统设置

```
GET /api/config/settings         → 当前系统设置（日志级别、监控开关、缓存策略...）
PUT /api/config/settings         → 修改系统设置
```

### 6.7 配置导入导出

```
POST /api/config/export  → 导出所有配置为 JSON（备份/迁移用）
POST /api/config/import  → 从 JSON 导入配置
```

**业务场景**：用户从开发环境导出一份配置 → 生产环境导入 → 不用手动重新配。

---

## 7. 系统运维

### 7.1 `database.py` — 数据库管理

**挂载**：`/api/system/database` | **业务**：数据库运维操作

```
GET  /status       → MongoDB + Redis 连接状态（健康检查）
GET  /stats        → 各集合的数据量统计
POST /test         → 测试数据库连接
POST /backup       → 创建数据库备份（导出 JSON）
GET  /backups      → 备份文件列表
DELETE /backups/{id} → 删除备份
POST /import       → 从文件导入数据
POST /export       → 导出数据到文件
POST /cleanup      → 清理 N 天前的旧数据
```

### 7.2 `logs.py` — 日志浏览

**挂载**：`/api/system/logs` | **业务**：在线查看和管理日志文件

```
Web UI 的"系统日志"页面：

GET  /files               → 日志文件列表（webapi.log, worker.log, error.log...）
POST /read                → 读取日志内容（支持按级别/关键词/时间范围过滤）
POST /export              → 导出日志为 zip/txt
GET  /statistics          → 日志统计（各级别数量、最近 N 天趋势）
DELETE /files/{filename}  → 删除日志文件
```

### 7.3 `operation_logs.py` — 操作审计日志

**挂载**：`/api/system/logs`（注意：和 logs.py 不同文件但同 prefix）

| 端点 | 用途 |
|---|---|
| `GET /list` | 操作日志分页列表（谁在什么时间做了什么） |
| `GET /stats` | 操作统计（成功率、操作类型分布、每小时分布） |
| `GET /{log_id}` | 单条日志详情 |
| `POST /clear` | 按条件清空日志（如清空 30 天前的） |
| `POST /create` | 手动创建一条操作日志 |
| `GET /export/csv` | 导出为 CSV 文件 |

### 7.4 `system_config.py` — 系统配置摘要

**挂载**：`/api/system`

```python
@router.get("/config/summary")
async def get_config_summary():
    # 返回配置摘要，敏感值（API Key、密码）自动打码
    return {
        "llm_providers": [...],      # API Key 显示为 "sk-***bc0"
        "data_sources": [...],
        "system_settings": {...}
    }

@router.get("/config/validate")
async def validate_config():
    # 和启动验证相同逻辑，但通过 API 调用
    return {"valid": True, "warnings": [...], "errors": []}
```

---

## 8. 定时任务管理 — `scheduler.py`

**挂载**：`/api/scheduler` | **业务**：管理 24 个定时任务

```
Web UI 的"任务调度"页面：

GET  /jobs                   → 所有定时任务列表（名称/下次执行时间/状态）
GET  /jobs/{job_id}          → 单个任务详情
POST /jobs/{job_id}/pause    → 暂停任务
POST /jobs/{job_id}/resume   → 恢复暂停的任务
POST /jobs/{job_id}/trigger  → 手动立即触发一次执行
GET  /jobs/{job_id}/history  → 任务执行历史（最近几次成功/失败）
GET  /history                → 所有任务的执行历史
GET  /stats                  → 调度器统计（总任务数/运行中/暂停）
```

```python
@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str):
    """管理员手动触发一个定时任务立即执行"""
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    # 触发异步执行，不等待完成
    asyncio.create_task(job.func())
    return {"message": f"任务 {job.name} 已触发"}
```

---

## 9. 实时推送

### 9.1 `sse.py` — Server-Sent Events 进度流

**挂载**：`/api/stream` | **业务**：前端通过 SSE 接收实时分析进度

```
前端代码:
  const eventSource = new EventSource("/api/stream/tasks/abc123")
  eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      // data: {"node": "Market Analyst", "status": "completed"}
      更新进度条
  }

后端代码:
  async def stream_task_progress(task_id):
      async def event_generator():
          while True:
              progress = await redis.get(f"task:{task_id}:progress")
              if progress:
                  yield f"data: {progress}\n\n"
              if await is_task_done(task_id):
                  break
              await asyncio.sleep(1)

      return StreamingResponse(event_generator(), media_type="text/event-stream")
```

| 端点 | 用途 |
|---|---|
| `GET /tasks/{task_id}` | 订阅单个任务的实时进度 |
| `GET /batches/{batch_id}` | 订阅批次的整体进度 |

### 9.2 `websocket_notifications.py` — WebSocket 通知

**挂载**：`/api/ws` | **业务**：双向实时通信

```
前端连接: ws://localhost:8000/api/ws/notifications?token=xxx

后端推送消息:
  · 分析完成 → "000002 分析完成，建议：买入"
  · 系统通知 → "数据同步已完成"
  · 进度更新 → task progress

与 SSE 的区别：WebSocket 是双向的，前端也可以发消息给后端
```

| 端点 | 协议 | 用途 |
|---|---|---|
| `/ws/notifications` | WebSocket | 通知推送 |
| `/ws/tasks/{task_id}` | WebSocket | 任务进度推送 |
| `/ws/stats` | GET | WebSocket 连接统计 |

---

## 10. 模拟交易 — `paper.py`

**挂载**：`/api/paper` | **业务**：纸上交易（模拟买卖，不涉及真实资金）

```
初始给 100 万虚拟资金 → 用户可以"买入"股票 → 持仓跟随真实行情波动 → "卖出"结算盈亏

GET  /account     → 账户信息（总资产、可用资金、持仓市值、总盈亏）
POST /order       → 下单（买入/卖出，股票代码+数量）
GET  /positions   → 当前持仓列表
GET  /orders      → 历史订单
POST /reset       → 重置账户（回到初始 100 万）
```

```python
@router.post("/order")
async def place_order(order: OrderRequest):
    # 1. 获取当前行情价
    quote = await get_quote(order.symbol)

    # 2. 检查资金是否足够
    account = await get_account()
    cost = quote["close"] * order.quantity
    if cost > account["available_cash"]:
        raise HTTPException(400, "可用资金不足")

    # 3. 创建持仓 + 扣减资金
    ...
```

---

## 11. 收藏与标签 — `favorites.py` + `tags.py`

### 11.1 收藏管理

**挂载**：`/api/favorites`

```
用户在行情页面点"加自选" → POST /api/favorites {"stock_code":"000002", "stock_name":"万科A"}
自选股列表 → GET /api/favorites
设置价格预警 → PUT /api/favorites/000002 {"alert_price_high": 12.0, "alert_price_low": 7.0}
```

### 11.2 标签管理

**挂载**：`/api/tags`

```
用户给自选股打标签 → POST /api/tags {"name": "地产股", "color": "#ff0000"}
```

---

## 12. 数据源初始化 — `tushare_init.py` / `akshare_init.py` / `baostock_init.py`

**业务**：首次部署时，初始化数据源——从外部 API 批量拉取全市场股票数据到本地 MongoDB。

```
Web UI "数据源初始化"页面：

GET  /api/tushare-init/status         → 数据库状态（有多少只股票，缺什么数据）
POST /api/tushare-init/start-basic    → 开始基础信息初始化（后台异步）
POST /api/tushare-init/start-full     → 开始全量数据初始化（后台异步）
GET  /api/tushare-init/initialization-status → 初始化进度
POST /api/tushare-init/stop           → 停止初始化
```

三个初始化路由结构完全一致，只是数据源不同（Tushare / AKShare / BaoStock）。

---

## 13. 数据同步 — `sync.py` + `multi_source_sync.py` + `multi_period_sync.py` + `stock_sync.py`

### 13.1 `sync.py` — 简单同步

**挂载**：`/api/sync`

```
POST /stock_basics/run    → 立即触发一次全量股票基础信息同步
GET  /stock_basics/status → 上次同步的状态和时间
```

### 13.2 `multi_source_sync.py` — 多数据源同步

**挂载**：`/api/sync/multi-source`

```
GET  /sources/status   → 各数据源状态（Tushare 可用？AKShare 可用？）
GET  /sources/current   → 当前优先级最高的可用数据源
POST /stock_basics/run  → 多数据源同步（自动回退）
GET  /recommendations   → 推荐的数据源使用方案
GET  /history           → 同步历史记录
```

### 13.3 `multi_period_sync.py` — 多周期同步

**挂载**：`/api/multi-period-sync`

```
POST /start-daily        → 同步日线数据
POST /start-weekly       → 同步周线数据
POST /start-monthly      → 同步月线数据
POST /start-all-history  → 从 1990 年开始的全历史同步
POST /start-incremental  → 增量同步（只补最近几天的）
GET  /period-comparison/{symbol} → 同一股票日/周/月线对比
```

### 13.4 `stock_sync.py` — 单股同步

**挂载**：`/api/stock-sync`

```
POST /single   → 同步单只股票（行情+历史+财务+基础信息）
POST /batch    → 批量同步
GET  /status/{symbol} → 某只股票的数据同步状态
```

---

## 14. 使用统计与模型能力 — `usage_statistics.py` + `model_capabilities.py`

### 14.1 Token 使用统计

**挂载**：`/api/usage`

```
Web UI "使用统计"页面：

GET /records          → 使用记录（每次 LLM 调用的 Token 数、成本）
GET /statistics       → 汇总统计（总次数/总 Token/总成本）
GET /cost/by-provider → 按厂家统计成本
GET /cost/by-model    → 按模型统计成本
GET /cost/daily       → 每日成本趋势
```

### 14.2 模型能力管理

**挂载**：`/api/model-capabilities`

```
POST /recommend              → 根据分析深度推荐模型组合
                              输入: {"depth": "深度"}
                              输出: {"quick_model": "deepseek-chat", "deep_model": "deepseek-reasoner"}
POST /validate               → 验证模型组合是否适合某分析深度
GET  /model/{model_name}     → 查询模型的详细能力（上下文长度、支持的特性）
```

---

## 15. 其他端点

### 15.1 `health.py` — 健康检查

**挂载**：`/api`

```
GET /api/health  → {"status": "ok", "version": "1.0.0"}
GET /api/healthz → Kubernetes liveness probe（存活探针）
GET /api/readyz  → Kubernetes readiness probe（就绪探针）
```

**Kubernetes 怎么用**：`healthz` 只要应用在运行就返回 200（不管数据库连没连上）。`readyz` 检查 MongoDB + Redis 都正常才返回 200——如果数据库断了，`readyz` 返回 503，Kubernetes 停止向这个 Pod 发流量，但不杀 Pod。

### 15.2 `queue.py` — 队列状态

**挂载**：`/api/queue`

```
GET /api/queue/stats → {"pending": 5, "processing": 2, "position": 3}
```

前端用这个显示"你前面还有 N 个任务在排队"。

### 15.3 `reports.py` — 研究报告管理

**挂载**：`/api/reports`

```
GET  /list                                     → 研究报告列表
GET  /{report_id}/detail                       → 报告详情
GET  /{report_id}/content/{module}             → 报告某个模块（如"市场分析"）
DELETE /{report_id}                             → 删除报告
GET  /{report_id}/download?format=markdown     → 下载为 Markdown
GET  /{report_id}/download?format=pdf          → 下载为 PDF
```

### 15.4 `notifications.py` — 通知管理

**挂载**：`/api`

```
GET  /api/notifications                   → 通知列表
GET  /api/notifications/unread_count      → 未读数量（前端红点数字）
POST /api/notifications/{id}/read         → 标记已读
POST /api/notifications/read_all          → 全部已读
```

### 15.5 `cache.py` — 缓存管理

**挂载**：`/api/cache`

```
GET  /stats        → 缓存命中率、使用量
DELETE /cleanup     → 清理过期缓存
DELETE /clear       → 清空所有缓存
```

### 15.6 `internal_messages.py` — Agent 内部消息

**挂载**：`/api/internal-messages`

Agent 在分析过程中产生的中间消息（如"Bull Researcher 认为..."、"Risk Manager 评估为..."）存在这里，前端可以查看分析过程的"聊天记录"。

---

## 16. 快速对照：前端做什么操作 → 调哪个接口

| 用户操作 | HTTP 请求 |
|---|---|
| 登录 | `POST /api/auth/login` |
| 分析一只股票 | `POST /api/analysis/single` |
| 看分析进度 | `GET /api/analysis/tasks/{id}/status`（或 SSE） |
| 看分析结果 | `GET /api/analysis/tasks/{id}/result` |
| 看分析报告 | `GET /api/reports/{id}/detail` |
| 看股票行情 | `GET /api/stocks/000002/quote` |
| 看历史 K 线图 | `GET /api/stocks/000002/kline` |
| 搜索股票 | `GET /api/stock-data/search?q=万科` |
| 筛选股票 | `POST /api/screening/enhanced` |
| 加自选 | `POST /api/favorites` |
| 配 LLM 模型 | `POST /api/config/llm` |
| 看日志 | `POST /api/system/logs/read` |
| 备份数据库 | `POST /api/system/database/backup` |
| 管理定时任务 | `GET /api/scheduler/jobs` |
| 模拟交易 | `POST /api/paper/order` |
| 下载报告 | `GET /api/reports/{id}/download?format=pdf` |
| 看花了多少钱 | `GET /api/usage/cost/daily` |
