# FinAgentLab

FinAgentLab 通过多 Agent 流程，针对指定日期分析一只股票并生成交易建议。本词汇表用于区分股票分析与之后针对实际市场结果进行的评估。

## 分析与评估

**Analysis Run（分析运行）**：
在特定配置下，针对一只股票和一个分析日期执行的一次完整多 Agent 分析。
_避免使用_：策略、评估、分析任务

**Decision Signal（决策信号）**：
Analysis Run 生成的可执行建议，包括交易方向以及支撑该方向的决策属性。
_避免使用_：策略、回测结果

**Decision Signal Snapshot（决策信号快照）**：
Analysis Run 完成时捕获的 Decision Signal 不可变副本，也是后续评估唯一允许使用的评分输入。它必须包含明确解析出的 BUY、SELL 或 HOLD；方向无法解析时 Evaluation Run 失败，不得默认设为 HOLD，也不得人工修正。
_避免使用_：重新解析的决策、当前决策

**Analysis Cutoff（分析截止时点）**：
所选 A 股交易日在中国标准时间下的收盘时点。Historical Replay Evaluation 可以使用该交易日完整的日行情数据，Theoretical Entry Price 从下一个交易日的调整后开盘价开始计算。
_避免使用_：盘中提交时间、仅截至前一日、UTC 市场收盘时间

**Decision Evaluation（交易决策评估）**：
将一次 Analysis Run 的 Decision Signal 与该信号产生后观察到的市场结果进行回顾性比较。
_避免使用_：策略评估、策略回测、风险评估

**Historical Replay Evaluation（历史回顾评估）**：
针对过去的 A 股交易日，使用截至该日可获得的信息重新运行当前分析系统，再利用已经发生的后续市场数据为生成的 Decision Signal 评分。首期版本拒绝非交易日，并且只支持 A 股。
_避免使用_：回测、前瞻跟踪、历史决策评估

**Eligible A-share Security（合格A股证券）**：
在上海、深圳或北京证券交易所上市的人民币普通股；发起 Evaluation 时必须处于正常上市状态，并且从分析日至60个交易日观察期结束期间没有停牌。停牌、退市、退市整理、暂停上市、ST 和 `*ST` 证券均被排除；Evaluation 被接受时即固定其资格，之后状态变化不会修改已完成结果。
_避免使用_：全部历史A股、ETF、当前已退市证券

**Evaluation Run（评估运行）**：
由 Evaluation Operator 独立发起的一次 Decision Evaluation，与其内部 Analysis Run 关联，并绑定一个明确选择的 Evaluation Profile。同一 Evaluation Case 的重复运行保留为不同记录，以衡量决策波动而不是相互覆盖；服务重启中断执行时，该 Run 变为 `failed`，保留已有部分 Execution Trace，必须显式创建新 Run，不自动重放或恢复。首期版本不会自动过期或静默删除 Run 的元数据和产物。
_避免使用_：去重后的评估、最新评估

**Cancellation Request（取消请求）**：
管理员请求以协作方式停止一个待执行或执行中的 Evaluation Run。运行中的 Run 继续保持 `running` 并设置 `cancel_requested=true`，直到引擎到达安全阶段或节点边界、停止启动后续工作、保存部分轨迹后，才变为 `cancelled`。
_避免使用_：立即取消状态、终止进程、评估阶段

**Evaluation Status（评估状态）**：
评估请求稳定的生命周期状态，包括 `pending`、`running`、`completed`、`failed`、`cancelled` 或 `ineligible`。它不同于当前执行阶段和具体工作流节点状态。
_避免使用_：评估阶段、节点状态、分析任务状态

**Pending Evaluation Run（待执行评估）**：
已经被接受、正在持久化队列中等待可用并发容量的 Evaluation Run。它可以在开始执行前取消。
_避免使用_：被拒绝的评估请求、执行中评估

**Rejected Evaluation Request（被拒绝的评估请求）**：
因股票、日期或其他输入违反已声明的资格规则（包括已知的证券异常状态），在创建 Evaluation Run 之前被拒绝的请求。它是 API 请求结果而不是 Evaluation Status，并且不会生成评估历史记录。
_避免使用_：不合格评估尝试、失败的评估运行

**Evaluation Phase（评估阶段）**：
当前所处的评估工作高层阶段，例如资格检查、样本准备、分析、信号捕获、评分或最终处理。
_避免使用_：评估状态、Agent 节点

**Evaluation Case（评估样本）**：
由股票、分析日期、Evaluation Profile、冻结的时点证据以及冻结的后续市场结果组成的不可变组合，可用于比较一个或多个 Evaluation Run。
_避免使用_：评估运行、实时市场查询、用户任务

**Evidence Snapshot（证据快照）**：
Evaluation Case 中实际提供给 Agent 的不可变、带版本内容，包括规范化源数据、时间有效的复权事实、派生指标、已渲染证据、来源信息和完整性哈希。
_避免使用_：实时数据、Agent 状态、评估结果

**Ineligible Evaluation Attempt（不合格评估尝试）**：
已通过请求校验，但后来因必需的历史证据、复权事实或结果数据缺失或时间无效而无法评分的、被保留的 Evaluation Run。它记录明确原因，不产生评分结果，也不进入准确率统计。
_避免使用_：失败的评估运行、降级评估

**Failed Evaluation Run（失败的评估运行）**：
因程序、模型、数据提供方可用性、解析器、轨迹持久化或基础设施故障而未能完成的、已被接受的 Evaluation Run。它保留已有部分 Execution Trace，并与不合格样本严格区分；必需轨迹和证据未持久化成功时，不得完成有效评分结果。
_避免使用_：被拒绝的评估请求、不合格评估尝试

**Evaluation Operator（评估执行者）**：
为验证系统质量而获准创建和取消 Evaluation Run 的管理员。
_避免使用_：普通用户、评估查看者

**Evaluation Viewer（评估查看者）**：
可以查看已发布且状态为 `completed` 或 `ineligible` 的 Evaluation Run，但不能创建、取消或发布 Run 的已登录用户。
_避免使用_：评估执行者、系统评测者

**Evaluation History（评估历史）**：
可搜索的 Evaluation Run 列表。Evaluation Viewer 只能看到已发布的 `completed` 或 `ineligible` Run；Evaluation Operator 可以看到所有状态和未发布 Run，并可按股票、分析日期、Profile、状态、发布状态和主要20日命中结果筛选。
_避免使用_：分析历史、报告历史、评测样本集

**Published Evaluation（已发布评估）**：
由 Evaluation Operator 明确批准、供已登录 Evaluation Viewer 查看的一次不可变 Evaluation Run。只有 `completed` 或 `ineligible` Run 可以发布；`failed` 和 `cancelled` Run 仅管理员可见。执行者可以撤回发布，但不能修改结果或 Execution Trace，也不能硬删除底层审计记录。
_避免使用_：互联网公开结果、自动共享的运行、管理员草稿

**Execution Trace（执行轨迹）**：
Evaluation Run 执行期间捕获并在运行结束后展示的有序、持久化记录。每个节点条目保存时间、状态、输入摘要、节点写入的解析后输出以及错误状态；轨迹还包含进入模型提示词的已脱敏工具调用和经过投影的中间状态变化。首期版本不在执行期间流式传输轨迹；Run 活跃时，Evaluation Operator 可以轮询粗粒度状态、阶段和当前节点元数据。
_避免使用_：实时事件流、原始运行日志、最终评估结果

**Evaluation View State（评估展示状态）**：
专门提供给前端的 Evaluation 执行状态投影。即使其白名单有意暴露大部分业务字段，它仍与内部原始 Agent State 分离；密钥、Token、连接信息、内部路径和其他仅供运行时使用的敏感字段会被排除，但其余业务内容不会被概括缩减。
_避免使用_：原始 Agent 状态、数据库文档、调试转储

**State Change（状态变更）**：
一个已完成工作流节点所修改的、位于 Evaluation View State 白名单中的字段。Execution Trace 保存每个节点的这些变更以及一份最终完整 Evaluation View State 快照，而不是为每个节点重复保存完整状态。
_避免使用_：原始状态变更、每节点完整快照、数据库差异

**Prompt Evidence（提示词证据）**：
Evaluation Run 期间实际提供给模型的、经过脱敏并完整渲染的业务提示词，以及工具输入和结果。平台级隐藏指令和敏感运行时信息不包含在内；首期 Execution Trace 不保存数据提供方原生模型响应，只保留写入状态的解析后节点输出。
_避免使用_：提示词模板、平台系统指令、原始模型响应

**Full-horizon Eligible Date（全期限合格日期）**：
股票和基准已经具备足够后续交易数据、可以计算全部标准5日、20日和60日 Horizon Outcome 的分析日期。首期 Historical Replay Evaluation 仅接受此类日期。
_避免使用_：近期跟踪日期、自然日截止日期

**Evaluation Eligibility（评估资格）**：
Evaluation Profile 要求的全部证据和结果数据，在 Evaluation Run 可以进入正式准确率之前都必须完整且时间有效。不合格尝试会被排除，而不是静默降级。
_避免使用_：低置信度评估、部分证据

**Recorded Decision Evaluation（历史决策评估）**：
直接评估早期 Analysis Run 实际产生的不可变 Decision Signal Snapshot，不使用当前系统重新生成该决策。
_避免使用_：历史回顾评估、重新计算的决策

**Forward Tracking Evaluation（前瞻跟踪评估）**：
一项未来能力：随着近期 Decision Signal 的5日、20日和60日结果逐步可观察，对其进行持续评估。
_避免使用_：历史回顾评估、首期范围

**System Evaluation（系统评测）**：
跨多个 Decision Evaluation 的汇总评测，用于判断某个版本化决策系统的质量。它是未来必须提供的能力，但不属于首期交付；首期止于单次 Evaluation Run、历史记录、结果和 Execution Trace。
_避免使用_：单次决策评估、单个 Agent 准确率、用户风险评估

**System Decision Accuracy（系统决策准确率）**：
最终 Decision Signal 在一组可比较 Evaluation Case 上的准确率。首要指标是20个交易日 Strict Direction Hit 命中率，同时分别报告5日和60日命中率以及绝对和基准相对结果；对于没有独立真实标签的 Agent 输出，不得将其描述成单个 Agent 的准确率。
_避免使用_：Agent 准确率、综合质量分、单次运行正确性

**A-share Prediction Accuracy（A股预测准确率）**：
A 股限定范围内 System Decision Accuracy 的用户界面名称。尽管显示名称较简洁，存储的分母和元数据仍必须标识更窄的 Eligible A-share Security 规则以及 Evaluation Suite 排除项。
_避免使用_：全市场准确率、Agent 准确率、无条件限定的历史准确率

**Evaluation Suite（评测样本集）**：
未来 System Evaluation 使用的、不可变且带版本的股票、分析日期、Evaluation Profile 和抽样规则定义。只有预先声明的 Suite 接纳的 Evaluation Case 才能进入正式 System Decision Accuracy；管理员临时执行的 Run 不会静默进入汇总。
_避免使用_：评估历史、管理员临时选择、全部已完成运行

**Official Evaluation Run（正式评估运行）**：
同一个 Evaluation Case 第一次合格、可以进入正式 System Decision Accuracy 的 Evaluation Run。之后的重复运行用于波动性和一致性诊断，但不能增加正式样本量，也不能替换第一次错误结果。
_避免使用_：最佳运行、最新运行、管理员指定运行

**Evaluation Lineage（评测血缘）**：
将 Decision Signal Snapshot 与生成它的分析输入、参与 Agent、模型、工作流、提示词、解析器和数据配置关联起来的不可变身份及版本信息。
_避免使用_：当前配置、运行时状态

**Evaluation Profile（评估配置档案）**：
对一组可比较 Evaluation Run 所允许的 Agent、证据来源、时间控制、模型、提示词、解析器和评分政策所作的不可变、带版本定义。只有活跃 Profile 可以创建新 Run；已被取代的 Profile 仍永久标识历史结果，但不能编辑、删除或用于新 Run。正式准确率只能合并 Profile 身份和版本完全相同的 Run。
_避免使用_：用户分析设置、当前系统配置

**Tool-grounded Historical Replay（工具证据约束的历史回顾）**：
一种 Historical Replay Evaluation：外部证据被限制为分析日期当时可获得的信息，Agent 也被要求只根据这些证据推理。它可以限制但不能消除模型参数内嵌的未来知识；该限制属于内部可信度模型，但首期查看者界面不主动解释它。
_避免使用_：严格时点回放、不受限制的历史分析

**Evaluation Horizon（评估期限）**：
观察 Decision Signal 后续市场结果的标准5日、20日或60个交易日期限之一；20个交易日是主要比较期限。
_避免使用_：自然日窗口、模型生成的持有期、用户自定义核心期限

**Theoretical Entry Price（理论入场价）**：
Analysis Run 分析日期之后第一个交易日的调整后开盘价，是其 Decision Evaluation 可复现的起始价格。
_避免使用_：分析日收盘价、盘中模拟成交价

**Directional Outcome（绝对方向结果）**：
股票自身从 Theoretical Entry Price 到某个 Evaluation Horizon 结束时的价格变化。
_避免使用_：基准相对结果、策略收益

**Benchmark-relative Outcome（基准相对结果）**：
某个 Evaluation Horizon 内，股票观察收益相对于适用市场基准同期收益的结果。
_避免使用_：绝对方向结果、组合 Alpha

**Market Benchmark（市场基准）**：
计算 Benchmark-relative Outcome 时使用的固定、可投资宽基代理。首期 A 股版本使用代码为 `510300.SS` 的沪深300 ETF 代理，其数据提供方和复权模式保存在 Evaluation Lineage 中。
_避免使用_：动态选择的基准、行业基准

**Strict Direction Hit（严格方向命中）**：
用于判断 BUY 或 SELL Decision Signal 是否与实际股票收益方向符号一致的二元结果；只要价格向相反方向变化即为未命中。HOLD 在绝对收益保持于相应期限 Material Outcome 阈值内时视为命中。
_避免使用_：有效幅度结果、置信度分数

**Direction Prediction（方向预测）**：
首期版本将 BUY、SELL 或 HOLD 解释为对后续价格方向的预期，不依赖用户持仓，也不模拟真实做多或做空交易。
_避免使用_：已执行交易、投资组合建议、空头仓位

**Material Outcome（有效幅度结果）**：
一种根据波动率调整的分类，用于区分市场噪声与有意义的有利或不利变化；确定阈值时只使用分析日期以前的信息。
_避免使用_：严格方向命中、固定百分比区间

**Horizon Outcome（期限结果）**：
Decision Evaluation 中一个 Evaluation Horizon 的结果，包括绝对收益、基准相对收益、Strict Direction Hit 和 Material Outcome。所需市场数据可用后，一次 Decision Evaluation 会得到5日、20日和60日三个 Horizon Outcome。
_避免使用_：独立评估、最终综合分

**Primary Evaluation Outcome（主要评估结果）**：
一次已完成 Decision Evaluation 所突出显示的20个交易日 Strict Direction Hit 命中或未命中结果。5日和60日结果分别作为辅助结果保留；不生成综合分，也不依据单次 Run 判断整个系统通过或不通过。
_避免使用_：综合分、系统质量结论、模型裁判

**Evaluation Core（评估核心）**：
第一个依赖 Feature，负责 Evaluation Profile、Case、Evidence Snapshot、Run、资格校验、历史回顾、评分、权限、发布和结果历史，并记录后续轨迹 Feature 所需的数据。
_避免使用_：执行轨迹查看器、系统评测仪表盘

**Execution Trace Explorer（执行轨迹查看器）**：
依赖 Evaluation Core 的第二个 Feature，让获授权用户查看已结束 Evaluation Run 的节点输出、Prompt Evidence、工具调用和 State Change。首期版本不提供实时事件流。
_避免使用_：评估引擎、实时工作流监控器、原始日志查看器

**First-delivery Evaluation Scope（首期评估范围）**：
由 Evaluation Core 和依赖它的 Execution Trace Explorer 组成，支持创建、排队、协作取消、评分、查看、发布、撤回发布和重新查看单次 A 股 Historical Replay Evaluation。范围不包括实时轨迹、Forward Tracking、Evaluation Suite 执行和汇总仪表盘、跨 Profile 汇总、单个 Agent 准确率、数据提供方原生模型响应、专用导出格式以及普通用户执行 Evaluation。
_避免使用_：系统评测交付、完整评估路线图、准确率阈值

**Decision Diagnostic（决策诊断项）**：
Decision Signal 中保留的目标价、置信度或风险分等属性，可用于解释或在未来校准系统行为，但不决定首期方向正确性。无效诊断项保留原值和原因并标记为不可评估；它既不会使 Run 失败，也不会获得伪造的默认值。
_避免使用_：方向命中、综合准确率分数

**Target-price Outcome（目标价结果）**：
一种 Decision Diagnostic，描述有效 BUY 目标价是否被观察到的调整后最高价触达，或者有效 SELL 目标价是否被调整后最低价触达，并记录首次触达所需的交易日数量。
_避免使用_：方向命中、期限结束价格比较
