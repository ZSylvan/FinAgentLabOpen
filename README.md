# FinAgentLab

FinAgentLab 是一个面向学习、研究与工程实验的多智能体金融分析平台。它把行情、基本面、新闻与风险分析组织为可观察的协作流程，帮助使用者理解大模型如何参与研究工作。项目不提供实盘交易指令，也不构成投资建议。

[文档](./docs/)

## 项目目标

- 用结构化的多智能体流程完成股票研究与观点交叉检查。
- 支持 A 股、港股和美股的学习与实验场景。
- 提供可配置的模型、数据源、缓存和报告导出能力。
- 通过 Evaluation 入口、自动化测试和运行日志提高结果的可验证性。

## 架构

| 层次 | 目录 | 职责 |
| --- | --- | --- |
| Web 前端 | `frontend/` | Vue 3、Vite 与 Element Plus 单页应用 |
| API 与任务 | `app/` | FastAPI 接口、认证、任务编排和后台服务 |
| 分析核心 | `finagentlab/` | 多智能体图、分析工具、模型和数据源适配 |
| 命令行 | `cli/` | 交互式研究与配置入口 |
| 运维与部署 | `scripts/`、`docker-compose.yml` | 初始化、诊断、启动和容器化 |
| 数据服务 | MongoDB、Redis | 持久化、队列和缓存 |

## 快速运行

### Docker Compose

```bash
docker compose up -d
```

### 本地开发

Python 3.10+、Node.js 18+、MongoDB 和 Redis 可用后：

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

另开终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

也可以使用仓库启动脚本：

```bash
python scripts/startup/start_backend.py
python scripts/startup/start_web.py
```

环境变量示例见 [`.env.example`](./.env.example)，详细指南见 [`docs/guides/`](./docs/guides/)。

