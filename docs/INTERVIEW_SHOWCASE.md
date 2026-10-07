# FinAgentLab 面试展示说明

这份说明只列出能够由当前仓库的 Issue、提交、代码或测试验证的个人维护工作。多智能体分析核心和其他继承模块不表述为当前维护者原创；其来源见根目录 `THIRD_PARTY_NOTICES.md`。

## 1. 需求建模

当前维护者为 Evaluation 上下文建立了中英文领域文档，明确术语、角色、访问边界和需要验证的行为。

- 证据：提交 `25da3f6`（`docs: add evaluation domain context`）
- 文件：`CONTEXT.md`、`CONTEXT.zh-CN.md`
- 展示重点：先定义“谁可以访问评估能力”和“未授权时系统应如何响应”，再进入实现。

## 2. Evaluation 功能

当前维护者完成了 Evaluation 的可信访问链路，而不是只增加一个展示页面：

- 后端增加认证依赖和 Evaluation 路由。
- 前端增加 Evaluation 页面、导航入口和路由保护。
- 登录恢复过程中保持认证状态一致，未授权请求得到明确处理。

证据：提交 `5fdfe4a`（`feat: establish trustworthy evaluation access (#2)`），关联 GitHub Issue #2。

## 3. 架构改进

该实现把认证判断收敛到可复用依赖和路由边界，并让前端菜单、路由与认证状态使用同一访问规则。可以在面试中解释以下设计取舍：

1. 访问控制放在后端公开接口，而不是只隐藏前端菜单。
2. 前端路由守卫负责用户体验，后端鉴权负责安全边界。
3. Evaluation 页面通过独立路由和组件接入，避免污染现有分析流程。

相关文件包括 `app/dependencies/auth.py`、`app/routers/evaluations.py`、`frontend/src/router/index.ts` 和 `frontend/src/views/Evaluation/index.vue`。

## 4. 测试

提交 `5fdfe4a` 同时增加了：

- `tests/system/test_evaluation_access.py`：验证后端访问控制。
- `frontend/src/stores/__tests__/auth.test.ts`：验证认证状态行为。
- `frontend/src/views/Evaluation/__tests__/index.test.ts`：验证 Evaluation 页面。
- `frontend/vitest.config.ts` 与测试工厂：建立可复用的前端测试基础。

Ticket #9 进一步增加仓库级品牌检查器及其命令行行为测试，验证禁词拦截、法律白名单和旧链接/联系方式拦截。

## 5. 工程化与维护

- 提交 `4111a78` 清理历史文档并建立 Agent、Issue、标签和领域文档约定。
- Ticket #9 统一产品品牌、删除论文与旧维护工具、整理许可来源，并加入自动化品牌一致性检查。
- 所有来源声明遵守真实性边界：产品页面不展示旧营销品牌，必要第三方归属保留在法律通知中，Git 历史不重写。

## 推荐演示脚本

1. 未登录访问 Evaluation，展示前后端共同阻止未授权访问。
2. 登录后从侧边栏进入 Evaluation，说明路由、状态恢复和后端依赖的协作。
3. 运行 Evaluation 的前端测试与后端系统测试。
4. 运行 `python scripts/maintenance/check_brand_consistency.py`，再在临时样例中加入禁词展示检查失败。
5. 打开 `CONTEXT.md`，说明需求术语如何映射到实现与测试。

## 表述边界

可以说“我负责当前仓库的个人维护、Evaluation 可信访问、相关测试和品牌/工程治理”。不要说“我原创了整个多智能体金融分析框架”，也不要把历史贡献者的功能算作个人实现。
