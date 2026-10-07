## Agent Skills

### 实现前置检查

开始实现任何 Ticket 之前：

1. 先询问用户：当前 Ticket 应在专用分支上实现，还是直接在 `main` 上修改。创建分支或修改代码前必须等待用户明确选择。默认推荐使用 `codex/issue-<编号>-<简述>` 命名专用分支；如果用户选择 `main`，实现前应确认当前已切换到 `main`。
2. 先在沙箱内依次使用 `gh --version`、`gh auth status` 和仓库访问检查验证 GitHub CLI。如果授权或仓库访问失败是因为沙箱无法读取 GitHub CLI 配置、Windows 凭据管理器、系统密钥环或网络，应申请受控的提升权限，并在沙箱外将相同的只读检查重试一次。提升权限后的检查成功即视为已授权，不要要求用户重新登录。仅当 `gh` 缺失或提升权限后的检查仍失败时，才在修改代码前停止，并要求用户安装、授权或修复 GitHub CLI。该配置由用户完成；不要改用临时 CLI 或 Token 变通方案，不要把凭据复制进仓库，也不要全局削弱沙箱。
3. 使用 `conda run -n agent python --version` 验证 Conda 环境。所有 Python、后端、测试、迁移和项目脚本命令都必须在 `agent` 环境中执行，优先采用 `conda run -n agent ...`；不得使用 base、全局或其他 Python 环境。
4. 所有新增 Python 包都必须安装到 `agent` 环境。如果它属于项目依赖，必须在同一次改动中同步更新仓库依赖声明。如果 Conda 或 `agent` 环境不可用，应停止并要求用户创建或修复环境。

前端工具可以使用仓库的 Node.js 环境，但前端或构建脚本调用的 Python 仍必须解析到 `agent` 环境。

### 问题跟踪系统

本仓库通过 GitHub Issues 跟踪问题。详情参见 `docs/agents/issue-tracker.zh-CN.md`。

### Triage 标签

Triage 使用五个默认的标准标签。详情参见 `docs/agents/triage-labels.zh-CN.md`。

### 领域文档

本仓库采用单上下文（single-context）领域文档结构。详情参见 `docs/agents/domain.zh-CN.md`。
