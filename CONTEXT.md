# FinAgentLab

FinAgentLab analyzes a stock for a specified date through a multi-agent process and produces a trade recommendation. This glossary distinguishes an analysis from the later evaluation of its observed outcome.

## Analysis and evaluation

**Analysis Run（分析运行）**:
A single multi-agent analysis of one stock for one analysis date under a particular configuration.
_Avoid_: Strategy, Evaluation, Analysis Task

**Decision Signal（决策信号）**:
The actionable recommendation produced by an Analysis Run, including its direction and supporting decision attributes.
_Avoid_: Strategy, Backtest Result

**Decision Signal Snapshot（决策信号快照）**:
The immutable copy of a Decision Signal captured when its Analysis Run completes and used as the sole scoring input for later evaluation. It must contain an explicitly parsed BUY, SELL, or HOLD direction; an unparseable direction fails the Evaluation Run and is never defaulted to HOLD or repaired manually.
_Avoid_: Reparsed Decision, Current Decision

**Analysis Cutoff（分析截止时点）**:
The end of the selected A-share trading day in China Standard Time. A Historical Replay Evaluation may use that day's completed daily market data, and its Theoretical Entry Price begins at the next trading day's adjusted open.
_Avoid_: Intraday Submission Time, Previous-day-only Cutoff, UTC Market Close

**Decision Evaluation（交易决策评估）**:
A retrospective comparison between one Analysis Run's Decision Signal and the market outcome observed after that signal.
_Avoid_: Strategy Evaluation, Strategy Backtest, Risk Assessment

**Historical Replay Evaluation（历史回顾评估）**:
A Decision Evaluation that reruns the current analysis system for a past A-share trading date using only information available by that date, then scores the resulting Decision Signal against already-known subsequent market data. The first delivery rejects non-trading analysis dates and supports A-share stocks only.
_Avoid_: Backtest, Forward Tracking, Recorded Decision Evaluation

**Eligible A-share Security（合格A股证券）**:
A renminbi-denominated common stock listed on the Shanghai, Shenzhen, or Beijing stock exchange that is normally listed when an Evaluation is requested and remained free of suspension throughout the analysis date through the 60-trading-day observation window. Suspended, delisted, delisting-period, listing-suspended, ST, and `*ST` securities are excluded. Eligibility is fixed when the Evaluation is accepted; a later status change does not mutate a completed result.
_Avoid_: All Historical A-shares, ETF, Currently Delisted Security

**Evaluation Run（评估运行）**:
One independently executed Decision Evaluation initiated by an Evaluation Operator, linked to its internal Analysis Run, and bound to an explicitly selected Evaluation Profile. Repeated runs for the same Evaluation Case remain distinct records so that decision variability can be measured rather than overwritten. If execution is interrupted by a service restart, the run becomes failed, preserves its partial Execution Trace, and requires an explicit new run rather than automatic replay or resume. First-delivery Run metadata and artifacts have no automatic expiration or silent deletion.
_Avoid_: Deduplicated Evaluation, Latest Evaluation

**Cancellation Request（取消请求）**:
An administrator's cooperative request to stop a pending or running Evaluation Run. A running Run remains `running` with `cancel_requested=true` until the engine reaches a safe stage or node boundary, stops before starting further work, preserves its partial trace, and then becomes `cancelled`.
_Avoid_: Immediate Cancelled Status, Process Kill, Evaluation Phase

**Evaluation Status（评估状态）**:
The stable lifecycle condition of an evaluation request: pending, running, completed, failed, cancelled, or ineligible. It is distinct from the current execution phase and specific workflow node.
_Avoid_: Evaluation Phase, Node Status, Analysis Task Status

**Pending Evaluation Run（待执行评估）**:
An accepted Evaluation Run waiting in a persistent queue for capacity under a configurable concurrency limit. It may be cancelled before execution begins.
_Avoid_: Rejected Evaluation Request, Running Evaluation

**Rejected Evaluation Request（被拒绝的评估请求）**:
A request rejected before an Evaluation Run is created because its stock, date, or other input violates declared eligibility rules, including a known abnormal security status. It is an API outcome rather than an Evaluation Status and creates no evaluation history record.
_Avoid_: Ineligible Evaluation Attempt, Failed Evaluation Run

**Evaluation Phase（评估阶段）**:
The current high-level portion of evaluation work, such as eligibility checking, case preparation, analysis, signal capture, scoring, or finalization.
_Avoid_: Evaluation Status, Agent Node

**Evaluation Case（评估样本）**:
The immutable combination of a stock, analysis date, Evaluation Profile, frozen point-in-time evidence, and frozen subsequent market outcomes against which one or more Evaluation Runs can be compared.
_Avoid_: Evaluation Run, Live Market Query, User Task

**Evidence Snapshot（证据快照）**:
The immutable, versioned contents actually made available to agents in an Evaluation Case, including normalized source data, temporal adjustment facts, derived indicators, rendered evidence, provenance, and integrity hashes.
_Avoid_: Live Data, Agent State, Evaluation Result

**Ineligible Evaluation Attempt（不合格评估尝试）**:
A preserved Evaluation Run that passed request validation but later proved unscorable because required historical evidence, adjustment facts, or outcome data was missing or temporally invalid. It records explicit reasons, does not produce a scored result, and is excluded from accuracy statistics.
_Avoid_: Failed Evaluation Run, Degraded Evaluation

**Failed Evaluation Run（失败的评估运行）**:
An accepted Evaluation Run that could not finish because of a program, model, provider-availability, parser, trace-persistence, or infrastructure failure. It preserves its partial Execution Trace and is distinct from an ineligible sample. A valid scored result cannot be completed unless its required trace and evidence were durably stored.
_Avoid_: Rejected Evaluation Request, Ineligible Evaluation Attempt

**Evaluation Operator（评估执行者）**:
An administrator authorized to create and cancel Evaluation Runs as part of validating system quality.
_Avoid_: Ordinary User, Evaluation Viewer

**Evaluation Viewer（评估查看者）**:
A signed-in user authorized to inspect published completed or ineligible Evaluation Runs without creating, cancelling, or publishing them.
_Avoid_: Evaluation Operator, System Evaluator

**Evaluation History（评估历史）**:
The searchable list of Evaluation Runs. An Evaluation Viewer sees only published completed or ineligible Runs; an Evaluation Operator sees every status and unpublished Run and may filter by stock, analysis date, Profile, status, publication state, and primary 20-day hit result.
_Avoid_: Analysis History, Report History, Evaluation Suite

**Published Evaluation（已发布评估）**:
An immutable Evaluation Run that an Evaluation Operator has explicitly approved for authenticated Evaluation Viewers. Only completed or ineligible runs may be published; failed and cancelled runs remain administrator-only. An operator may unpublish it, but may not edit its result or Execution Trace, and the underlying audit record is not hard-deleted.
_Avoid_: Public Internet Result, Automatically Shared Run, Administrator Draft

**Execution Trace（执行轨迹）**:
The ordered, persistent record captured during an Evaluation Run and displayed after the run has finished. Each node entry records timing, status, an input summary, the parsed output written by the node, and any error state. It also includes sanitized tool calls that contributed to model prompts and projected intermediate state changes. The first delivery does not stream this trace while execution is in progress; an Evaluation Operator may poll coarse status, phase, and current-node metadata while the run is active.
_Avoid_: Live Event Stream, Raw Runtime Log, Final Evaluation Result

**Evaluation View State（评估展示状态）**:
The explicit frontend-facing projection of Evaluation execution state. It is separate from the raw internal Agent State even when its allowlist intentionally exposes most business fields. Secrets, tokens, connection details, internal paths, and other runtime-only sensitive fields are excluded without summarizing away the remaining business content.
_Avoid_: Raw Agent State, Database Document, Debug Dump

**State Change（状态变更）**:
The allowlisted Evaluation View State fields changed by one completed workflow node. Execution Trace stores these per-node changes plus one final complete Evaluation View State snapshot instead of duplicating the full state after every node.
_Avoid_: Raw State Mutation, Full Snapshot per Node, Database Diff

**Prompt Evidence（提示词证据）**:
The sanitized, fully rendered business prompt content and tool inputs and results that were actually supplied to a model during an Evaluation Run. Platform-level hidden instructions and sensitive runtime details are excluded. Provider-native raw model responses are not part of the first-delivery Execution Trace; the trace preserves the parsed node output written into state.
_Avoid_: Prompt Template, Platform System Instruction, Raw Model Response

**Full-horizon Eligible Date（全期限合格日期）**:
An analysis date for which the stock and benchmark already have sufficient subsequent trading data to calculate all standard 5-, 20-, and 60-trading-day Horizon Outcomes. First-delivery Historical Replay Evaluations accept only these dates.
_Avoid_: Recent Tracking Date, Calendar-day Cutoff

**Evaluation Eligibility（评估资格）**:
The requirement that every piece of evidence and outcome data mandated by an Evaluation Profile is complete and temporally valid before an Evaluation Run can contribute to official accuracy. An ineligible attempt is excluded rather than silently degraded.
_Avoid_: Reduced-confidence Evaluation, Partial Evidence

**Recorded Decision Evaluation（历史决策评估）**:
A Decision Evaluation of the immutable Decision Signal Snapshot that was actually produced by an earlier Analysis Run, without regenerating that decision under the current system.
_Avoid_: Historical Replay Evaluation, Recomputed Decision

**Forward Tracking Evaluation（前瞻跟踪评估）**:
A future capability that evaluates a recent Decision Signal as its 5-, 20-, and 60-trading-day outcomes become observable over time.
_Avoid_: Historical Replay Evaluation, First-delivery Scope

**System Evaluation（系统评测）**:
An aggregate assessment across many Decision Evaluations used to judge the quality of a versioned decision system. It is a mandatory future capability but is not part of the first delivery, which stops at individual Evaluation Runs, history, results, and Execution Traces.
_Avoid_: Single Decision Evaluation, Individual Agent Accuracy, User Risk Assessment

**System Decision Accuracy（系统决策准确率）**:
The accuracy of final Decision Signals across comparable Evaluation Cases. Its primary first metric is 20-trading-day Strict Direction Hit rate, with 5- and 60-trading-day rates and absolute and benchmark-relative outcomes reported separately. It must not be described as the accuracy of an individual Agent whose output has no independent ground-truth label.
_Avoid_: Agent Accuracy, Composite Quality Score, Single-run Correctness

**A-share Prediction Accuracy（A股预测准确率）**:
The user-facing name for System Decision Accuracy in the A-share-only scope. Its stored denominator and metadata still identify the narrower Eligible A-share Security rules and Evaluation Suite exclusions even though the display label is concise.
_Avoid_: All-market Accuracy, Agent Accuracy, Unqualified Historical Accuracy

**Evaluation Suite（评测样本集）**:
An immutable, versioned specification of the stocks, analysis dates, Evaluation Profile, and sampling rules used by a future System Evaluation. Only Evaluation Cases admitted by a predeclared suite may contribute to its official System Decision Accuracy; ad hoc administrator runs do not silently enter the aggregate.
_Avoid_: Evaluation History, Administrator Selection, All Completed Runs

**Official Evaluation Run（正式评估运行）**:
The first eligible Evaluation Run for an Evaluation Case that may contribute to official System Decision Accuracy. Later repeated runs are retained for variability and consistency diagnostics but cannot increase the official sample count or replace an incorrect first result.
_Avoid_: Best Run, Latest Run, Administrator-selected Run

**Evaluation Lineage（评测血缘）**:
The immutable identity and version information that ties a Decision Signal Snapshot to the analysis inputs, participating agents, models, workflow, prompts, parser, and data configuration that produced it.
_Avoid_: Current Configuration, Runtime State

**Evaluation Profile（评估配置档案）**:
An immutable, versioned definition of the agents, evidence sources, temporal controls, models, prompts, parser, and scoring policy allowed in a comparable group of Evaluation Runs. Only an active Profile may create new Runs. A superseded Profile remains permanently identifiable for historical results but cannot be edited, deleted, or used for new Runs. Official accuracy combines only Runs with an exactly matching Profile identity and version.
_Avoid_: User Analysis Settings, Current System Configuration

**Tool-grounded Historical Replay（工具证据约束的历史回顾）**:
A Historical Replay Evaluation whose external evidence is constrained to information available by the analysis date and whose agents are instructed to reason only from that evidence. It limits but cannot eliminate future knowledge embedded in model parameters. This limitation remains part of the internal assurance model, although the first-delivery viewer interface does not proactively explain it.
_Avoid_: Strict Point-in-Time Replay, Unrestricted Historical Analysis

**Evaluation Horizon（评估期限）**:
One of the standard 5-, 20-, or 60-trading-day periods over which a Decision Signal's subsequent market outcome is observed; 20 trading days is the primary comparison horizon.
_Avoid_: Calendar-day Window, Model-generated Holding Period, User-defined Core Horizon

**Theoretical Entry Price（理论入场价）**:
The adjusted opening price on the first trading day after an Analysis Run's analysis date, used as the reproducible starting price for its Decision Evaluation.
_Avoid_: Analysis-date Close, Intraday Simulated Fill

**Directional Outcome（绝对方向结果）**:
The observed movement of the stock itself from the Theoretical Entry Price through an Evaluation Horizon.
_Avoid_: Benchmark-relative Outcome, Strategy Return

**Benchmark-relative Outcome（基准相对结果）**:
The stock's observed return over an Evaluation Horizon relative to the return of its applicable market benchmark over the same period.
_Avoid_: Directional Outcome, Portfolio Alpha

**Market Benchmark（市场基准）**:
The fixed investable broad-market proxy used for Benchmark-relative Outcomes. The first A-share delivery uses the CSI 300 ETF proxy identified as `510300.SS`, with its data provider and adjustment mode preserved in Evaluation Lineage.
_Avoid_: Dynamically Selected Benchmark, Industry Benchmark

**Strict Direction Hit（严格方向命中）**:
A binary judgment of whether a BUY or SELL Decision Signal matched the sign of the observed stock return; any movement in the opposite direction is a miss. HOLD is a hit when the absolute return remains within the applicable Material Outcome threshold for that horizon.
_Avoid_: Material Outcome, Confidence Score

**Direction Prediction（方向预测）**:
The first-version interpretation of BUY, SELL, or HOLD as an expectation about subsequent price direction, independent of the user's holdings and without simulating a long or short trade.
_Avoid_: Executed Trade, Portfolio Recommendation, Short Position

**Material Outcome（有效幅度结果）**:
A volatility-adjusted classification that distinguishes market noise from a meaningful favorable or adverse movement, using only information available by the analysis date to set the threshold.
_Avoid_: Strict Direction Hit, Fixed Percentage Band

**Horizon Outcome（期限结果）**:
The result for one Evaluation Horizon within a Decision Evaluation, including absolute and benchmark-relative returns, Strict Direction Hit, and Material Outcome. A Decision Evaluation gains 5-, 20-, and 60-day Horizon Outcomes as the required market data becomes available.
_Avoid_: Separate Evaluation, Final Aggregate Score

**Primary Evaluation Outcome（主要评估结果）**:
The 20-trading-day Strict Direction Hit or miss highlighted for one completed Decision Evaluation. The 5- and 60-trading-day outcomes remain separate supporting results; no composite score or single-run system pass/fail judgment is created.
_Avoid_: Composite Score, System Quality Verdict, Model Judge

**Evaluation Core（评估核心）**:
The first dependent feature that owns Evaluation Profiles, Cases, Evidence Snapshots, Runs, eligibility, historical replay, scoring, authorization, publication, and result history. It records the trace data required by the later trace feature.
_Avoid_: Execution Trace Explorer, System Evaluation Dashboard

**Execution Trace Explorer（执行轨迹查看器）**:
The second feature, dependent on Evaluation Core, that lets authorized users inspect a finished Evaluation Run's node outputs, Prompt Evidence, tool calls, and State Changes. It does not provide live event streaming in the first delivery.
_Avoid_: Evaluation Engine, Live Workflow Monitor, Raw Log Viewer

**First-delivery Evaluation Scope（首期评估范围）**:
The Evaluation Core and dependent Execution Trace Explorer required to create, queue, cooperatively cancel, score, inspect, publish, unpublish, and revisit individual A-share Historical Replay Evaluations. It excludes realtime trace streaming, Forward Tracking, Evaluation Suite execution and aggregate dashboards, cross-Profile aggregation, individual-Agent accuracy, provider-native raw model responses, dedicated export formats, and Evaluation execution by ordinary users.
_Avoid_: System Evaluation Delivery, Full Evaluation Roadmap, Accuracy Threshold

**Decision Diagnostic（决策诊断项）**:
A preserved Decision Signal attribute such as target price, confidence, or risk score that helps explain or later calibrate system behavior but does not determine first-version directional correctness. An invalid diagnostic retains its original value and reason and is marked not evaluable; it neither fails the run nor receives a fabricated default.
_Avoid_: Direction Hit, Composite Accuracy Score

**Target-price Outcome（目标价结果）**:
A Decision Diagnostic describing whether a valid BUY target was reached by an observed adjusted high, or a valid SELL target by an observed adjusted low, and the number of trading days until first reach.
_Avoid_: Direction Hit, End-of-horizon Price Comparison
