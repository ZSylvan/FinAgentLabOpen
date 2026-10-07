# FinAgentLab Day 9 学习指南：核心分析路由

## 九、Day 9：核心分析路由（`app/routers/analysis.py`）

> **学习目标**：从 HTTP 请求入口出发，完整理解“提交分析任务 → 后台执行 → 查询状态 → 获取结果 → 实时推送 → 任务清理”的 API 生命周期，掌握 FastAPI 路由层如何编排认证、服务、任务状态和 WebSocket。
>
> **建议用时**：2.5～4 小时
>
> **核心文件**：`app/routers/analysis.py`（约 1259 行）
>
> **配套文件**：`app/models/analysis.py`、`app/services/simple_analysis_service.py`、`app/services/analysis_service.py`、`app/services/queue_service.py`、`app/services/websocket_manager.py`、`app/routers/auth_db.py`

### 9.1 先建立路由层的职责边界

`analysis.py` 不是实际执行股票分析的地方，它主要承担四类职责：

1. **协议层**：定义 HTTP/WebSocket 路径、请求参数、响应结构和状态码。
2. **安全层**：通过 `Depends(get_current_user)` 获取当前用户，并进行任务所有权校验。
3. **编排层**：调用分析服务、队列服务和 WebSocket 管理器，不直接实现 LangGraph 细节。
4. **兼容层**：同时保留新版异步分析接口和旧版 `/analyze`、`/analyze/batch` 接口。

可以把这一层理解为：

```text
HTTP/WebSocket 请求
        |
        v
app/routers/analysis.py
        |
        +--> auth_db.get_current_user()
        +--> simple_analysis_service
        +--> analysis_service
        +--> queue_service
        +--> websocket_manager
        |
        v
MongoDB / Redis / FinAgentLab
```

**阅读原则**：路由函数只看“输入、权限、调用哪个服务、返回什么”；具体的任务执行和数据访问要跳转到 Service 层继续追踪。

### 9.2 第一条主链路：提交单股分析

重点阅读 `submit_single_analysis()`（`POST /single`）：

```text
客户端
  |
  | POST /analysis/single
  v
SingleAnalysisRequest 参数校验
  |
  v
get_current_user() 认证
  |
  v
create_analysis_task(user_id, request)
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
  v
FinAgentLab 分析图
```

需要重点理解：

- `SingleAnalysisRequest` 由 Pydantic 校验股票代码和分析参数。
- 任务记录先创建，接口不等待 LLM 分析完成，因此能够快速响应。
- 返回值包含 `success`、`data` 和 `message`，其中 `data.task_id` 是后续查询的关键。
- 后台函数重新获取 Service 实例，并捕获异常记录日志，避免后台异常直接影响已返回的 HTTP 响应。
- `BackgroundTasks` 适合轻量后台任务；它不是独立的分布式任务队列，进程退出时任务可能丢失。

**要回答的问题**：为什么接口不能直接 `await execute_analysis_background()`？

因为分析过程包含数据源访问、多个 Agent 和 LLM 调用，耗时不可控。如果同步等待，HTTP 请求会长时间占用连接；异步提交可以让客户端先拿到 `task_id`，再通过状态接口或实时通道观察任务进度。

### 9.3 第二条主链路：任务状态查询与结果恢复

重点阅读：

- `get_task_status_new()`（`GET /tasks/{task_id}/status`）
- `get_task_result()`（`GET /tasks/{task_id}/result`）

状态查询采用“内存优先、MongoDB 兜底”的恢复策略：

```text
查询 task_id
    |
    v
内存状态管理器
    |
    +--> 找到：直接返回实时状态
    |
    +--> 未找到：查询 MongoDB.analysis_tasks
                    |
                    +--> 找到：恢复进行中的任务状态
                    |
                    +--> 未找到：查询 MongoDB.analysis_reports
                                      |
                                      +--> 找到：按已完成任务返回
                                      +--> 未找到：404
```

这部分要特别观察：

- 任务状态通常包含 `pending`、`running/processing`、`completed`、`failed` 等阶段。
- 返回数据同时兼容 `symbol`、`stock_code`、`stock_symbol` 等历史字段。
- 已完成报告可以被重新包装成 100% 进度的任务状态，保证服务重启后仍能查询历史结果。
- `analysis_tasks` 更偏运行时任务记录；`analysis_reports` 更偏最终分析结果。
- 状态接口和结果接口分离，前者适合轮询进度，后者只在完成后读取完整报告。

### 9.4 第三条主链路：批量分析与并发模型

重点阅读 `submit_batch_analysis()`（`POST /batch`）。它与单股分析有三个重要差异：

1. 最多接收 10 个股票代码。
2. 先为每只股票创建独立的 `task_id`。
3. 使用 `asyncio.create_task()` 和 `asyncio.gather()` 并发执行任务。

```text
BatchAnalysisRequest
        |
        v
校验股票数量（1～10）
        |
        v
为每只股票创建单股任务
        |
        v
asyncio.create_task(run_single_analysis(...))
        |
        +--> task A
        +--> task B
        +--> task C
        |
        v
asyncio.gather(*tasks, return_exceptions=True)
```

需要辨析两种后台执行方式：

| 方式 | 特点 | 当前用途 |
|---|---|---|
| `BackgroundTasks` | FastAPI 请求生命周期内的后台任务，调用简单，适合轻量任务 | 单股 `/single` |
| `asyncio.create_task` | 当前事件循环中主动创建并发协程 | 批量 `/batch` |
| Redis Queue + Worker | 可持久化、可重试、可跨进程扩展 | 兼容旧版队列接口和后续工程化方向 |

**注意**：`asyncio.create_task()` 只解决当前进程内的并发，不等同于可靠的分布式任务队列。若要支持多实例部署、崩溃恢复和任务重试，应进一步使用 `QueueService` 和 `app/worker.py`。

### 9.5 兼容接口与路由演进

文件中同时存在两套接口：

```text
新版：
POST /single
POST /batch
GET  /tasks/{task_id}/status
GET  /tasks/{task_id}/result

兼容旧版：
POST /analyze
POST /analyze/batch
GET  /batches/{batch_id}
```

旧版 `/analyze` 直接调用 `QueueService.enqueue_task()`，新版 `/single` 则通过 `SimpleAnalysisService` 创建分析任务并使用 FastAPI `BackgroundTasks` 执行。

阅读时要关注：

- 为什么不能随意删除旧接口：已有 CLI、前端或外部调用方可能仍在使用。
- 为什么请求模型有 `SingleAnalyzeRequest` 和 `SingleAnalysisRequest` 两套：这是 API 演进过程中的兼容设计。
- 为什么部分字段同时出现 `symbol`、`stock_code`：数据库和客户端存在历史字段，需要逐步迁移而不是一次性破坏兼容性。
- 为什么代码中有注释掉的旧路由：动态路径 `/tasks/{task_id}` 容易与 `/tasks/{task_id}/status` 等路径产生匹配或维护冲突。

### 9.6 任务控制、历史与管理接口

继续阅读以下端点，理解任务的完整生命周期：

| 端点 | 作用 | 关键点 |
|---|---|---|
| `POST /tasks/{task_id}/cancel` | 取消任务 | 先验证任务属于当前用户 |
| `GET /user/queue-status` | 查看用户队列状态 | 由 `QueueService` 返回排队/运行信息 |
| `GET /user/history` | 查询个人分析历史 | 支持状态、日期、股票代码、市场和分页筛选 |
| `GET /tasks/{task_id}/details` | 获取任务详情 | 使用队列服务并再次校验所有权 |
| `DELETE /tasks/{task_id}` | 删除任务 | 任务生命周期的清理操作 |
| `GET /admin/zombie-tasks` | 查询僵尸任务 | 仅管理员可访问 |
| `POST /admin/cleanup-zombie-tasks` | 清理僵尸任务 | 将长时间未完成任务标记为失败 |
| `POST /tasks/{task_id}/mark-failed` | 手动标记失败 | 同时更新内存状态和 MongoDB |

这里体现了一个重要的后端设计原则：**任何涉及用户任务的读取和修改，都必须同时考虑认证、资源所有权、状态一致性和幂等性。**

### 9.7 WebSocket 进度通道

重点阅读 `websocket_task_progress()`（`WebSocket /ws/task/{task_id}`）：

```text
WebSocket 连接
      |
      v
websocket_manager.connect(websocket, task_id)
      |
      v
发送 connection_established
      |
      v
循环接收客户端心跳
      |
      +--> WebSocketDisconnect：退出
      +--> 异常：记录并退出
      |
      v
finally: websocket_manager.disconnect(...)
```

要理解的工程细节：

- WebSocket 连接按 `task_id` 分组，便于向关注同一任务的客户端广播。
- 连接建立后立即发送确认消息，前端可以据此更新连接状态。
- `while True` 中接收客户端消息，通常承担心跳或保活作用。
- `WebSocketDisconnect` 必须单独处理，避免把正常断开记录为系统错误。
- `finally` 中统一释放连接，防止连接泄漏。
- 真正的进度发布由 `websocket_manager` 或分析服务完成，路由本身主要负责连接生命周期。

### 9.8 Day 9 实战任务

#### 任务 A：画出单股分析时序图

至少包含以下角色：浏览器、`analysis.py`、认证依赖、分析服务、后台任务、MongoDB、FinAgentLab。

```text
Browser -> POST /single -> create_analysis_task -> return task_id
Browser -> GET /tasks/{id}/status -> memory/MongoDB
BackgroundTask -> execute_analysis_background -> FinAgentLab
FinAgentLab -> MongoDB -> analysis report
Browser -> GET /tasks/{id}/result -> final report
```

#### 任务 B：做一次端点分类

把 `analysis.py` 中所有路由按以下类别归类：

- 创建任务
- 查询任务
- 获取结果
- 批量处理
- 任务控制
- 历史查询
- 实时通信
- 管理员维护
- 兼容接口

然后标注每个端点是否需要：

- 用户认证
- 任务所有权校验
- 管理员权限
- Redis
- MongoDB

#### 任务 C：追踪一个 `task_id`

选择一次实际分析，沿着下面的调用链设置断点或搜索日志：

```text
submit_single_analysis
  -> create_analysis_task
  -> execute_analysis_background
  -> get_task_status
  -> get_task_result
```

记录每一步的：

- 状态变化
- 数据保存位置
- 关键字段名称
- 异常处理方式
- 前端如何获得下一步信息

#### 任务 D：思考并发边界

回答以下问题：

1. 为什么批量分析使用 `asyncio.create_task()` 而不是循环 `await`？
2. 如果同一用户同时提交 20 个批量任务，在哪里限制并发？
3. 如果 FastAPI 进程重启，哪些任务状态会丢失，哪些可以从 MongoDB 恢复？
4. 如果同一个 `task_id` 重复调用取消接口，接口应该返回什么？
5. 如果用户访问别人的 `task_id`，应该在哪一层阻止？

### 9.9 Day 9 面试要点

- **问：路由层为什么不直接调用 LangGraph？**
  - 路由层只负责协议、认证和请求编排；分析执行属于 Service/Agent 层。分层后便于测试、复用和替换执行方式。

- **问：如何让长时间分析不阻塞 HTTP 请求？**
  - 先创建任务并返回 `task_id`，后台异步执行；客户端通过状态查询、SSE 或 WebSocket 获取进度。

- **问：`BackgroundTasks` 和真正的任务队列有什么区别？**
  - `BackgroundTasks` 依附于当前 FastAPI 进程，适合轻量任务；Redis Queue + Worker 支持跨进程、持久化、重试和更可靠的故障恢复。

- **问：为什么批量分析不能简单地循环 `await`？**
  - 循环 `await` 会串行等待每只股票完成；`asyncio.create_task()` 配合 `gather()` 才能在 I/O 等待期间并发推进多个分析任务。

- **问：如何保证任务接口的安全性？**
  - 通过 `get_current_user` 认证身份，再以 `user_id` 校验任务所有权；管理员接口额外检查管理员权限。

- **问：为什么状态查询要有内存和 MongoDB 两套来源？**
  - 内存适合低延迟实时状态，MongoDB 提供进程重启后的持久化恢复能力；两者结合可以兼顾实时性和可靠性。

- **问：WebSocket 断开时为什么必须清理？**
  - 不清理会残留连接对象，造成内存泄漏、广播异常和任务订阅关系失真；因此要在 `finally` 中执行 disconnect。

### 9.10 Day 9 完成检查清单

```text
□ 能解释 POST /single 的完整调用链
□ 能说明 BackgroundTasks 与 Redis Worker 的区别
□ 能画出 task_id 从创建到完成的状态流转
□ 能解释内存状态与 MongoDB 兜底恢复策略
□ 能区分单股、批量、兼容接口的执行方式
□ 能说明任务取消、删除和标记失败的边界
□ 能解释用户认证、任务所有权和管理员权限的关系
□ 能说明 WebSocket 的连接、心跳、断开和清理流程
□ 能指出 analysis.py 中兼容性代码带来的维护成本
□ 能回答批量并发和进程重启场景下的可靠性问题
```

### 9.11 Day 9 输出物

完成学习后，应产出以下内容：

1. 一张“分析 API 全链路”时序图。
2. 一张 `analysis.py` 端点分类表。
3. 一份真实 `task_id` 的状态追踪记录。
4. 对 `BackgroundTasks`、`asyncio.create_task` 和 Redis Queue 的对比总结。
5. 三条对当前路由设计的改进建议，例如：统一响应模型、抽取任务权限校验、将批量任务迁移到可靠队列。

> **Day 9 核心结论**：`app/routers/analysis.py` 的价值不在于“有很多 API”，而在于它把认证、任务创建、异步执行、状态恢复、并发控制、实时通信和生命周期管理连接成了完整的业务入口。读懂它，就能把前端请求、FastAPI 服务、Redis/MongoDB 和 FinAgentLab 分析引擎串成一条可解释的调用链。

---

## 十、Day 10 预告：队列与 Worker 系统

下一天重点阅读：

- `app/services/queue_service.py`
- `app/worker.py`
- `app/services/analysis_service.py`
- `app/services/scheduler_service.py`

重点问题：

- Redis List 如何实现任务入队、出队和确认？
- Worker 如何避免重复消费和任务丢失？
- 用户级并发限制与全局并发限制如何实现？
- 优雅关闭时，正在执行的分析任务如何处理？
- `analysis.py` 中的后台任务如何逐步迁移到可靠的 Worker 架构？

