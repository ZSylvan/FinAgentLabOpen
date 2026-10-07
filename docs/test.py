"""
LangGraph Human-in-the-Loop 最小可运行示例。

运行：
    pip install -U langgraph
    python test.py

流程：
    1. 自动生成一个模拟交易建议
    2. 在 human_review 节点调用 interrupt() 暂停
    3. 用户在终端批准、拒绝或修改
    4. 使用相同的 thread_id 和 Command(resume=...) 恢复图
    5. 输出最终状态

说明：
    - 本示例不调用真实 LLM，也不会执行真实交易。
    - InMemorySaver 只适合本地测试，程序退出后检查点会丢失。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


ReviewAction = Literal["approve", "reject", "edit"]


class TradeState(TypedDict):
    company: str
    requested_quantity: int
    proposed_action: NotRequired[dict[str, Any]]
    reviewed_action: NotRequired[dict[str, Any]]
    review_status: NotRequired[ReviewAction]
    rejection_reason: NotRequired[str]
    final_result: NotRequired[str]


def generate_trade_proposal(state: TradeState) -> dict[str, Any]:
    """生成模拟交易建议；这里可替换成你的 Trader/LLM 节点。"""
    proposal = {
        "action": "BUY",
        "symbol": state["company"].upper(),
        "quantity": state["requested_quantity"],
        "reason": "这是一个用于演示人工审批的模拟建议",
    }

    print("\n[节点] generate_trade_proposal 执行完成")
    print(json.dumps(proposal, ensure_ascii=False, indent=2))

    return {"proposed_action": proposal}


def human_review(state: TradeState) -> dict[str, Any]:
    """暂停图并等待人工批准、拒绝或修改交易建议。"""
    proposal = state["proposed_action"]

    # interrupt() 的参数会暴露给调用方。
    # 使用 Command(resume=...) 恢复时，resume 中的值会成为此函数的返回值。
    human_decision = interrupt(
        {
            "type": "trade_approval",
            "message": "请审核交易建议",
            "proposal": proposal,
            "allowed_actions": ["approve", "reject", "edit"],
        }
    )

    action = human_decision.get("action")

    if action == "approve":
        return {
            "review_status": "approve",
            "reviewed_action": proposal,
        }

    if action == "reject":
        return {
            "review_status": "reject",
            "rejection_reason": human_decision.get(
                "reason", "人工审核未通过"
            ),
        }

    if action == "edit":
        edited_proposal = human_decision.get("proposal")
        if not isinstance(edited_proposal, dict):
            raise ValueError("edit 操作必须提供 proposal 字典")

        return {
            "review_status": "edit",
            "reviewed_action": edited_proposal,
        }

    raise ValueError(f"不支持的审核操作：{action!r}")


def execute_trade(state: TradeState) -> dict[str, str]:
    """根据人工审核结果执行模拟操作。"""
    if state["review_status"] == "reject":
        reason = state.get("rejection_reason", "未提供原因")
        result = f"交易已取消：{reason}"
        print(f"\n[节点] execute_trade：{result}")
        return {"final_result": result}

    proposal = state["reviewed_action"]

    # 这里仅打印，不调用真实券商或交易接口。
    result = (
        "模拟执行成功："
        f"{proposal['action']} "
        f"{proposal['quantity']} 股 "
        f"{proposal['symbol']}"
    )
    print(f"\n[节点] execute_trade：{result}")
    return {"final_result": result}


def build_graph():
    """构建并编译带 checkpointer 的 LangGraph。"""
    builder = StateGraph(TradeState)

    builder.add_node("generate_trade_proposal", generate_trade_proposal)
    builder.add_node("human_review", human_review)
    builder.add_node("execute_trade", execute_trade)

    builder.add_edge(START, "generate_trade_proposal")
    builder.add_edge("generate_trade_proposal", "human_review")
    builder.add_edge("human_review", "execute_trade")
    builder.add_edge("execute_trade", END)

    # interrupt() 需要 checkpointer 来保存暂停时的状态。
    return builder.compile(checkpointer=InMemorySaver())


def extract_interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    """从 graph.invoke() 的结果中读取第一个 interrupt payload。"""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None

    first = interrupts[0]

    # LangGraph 的 Interrupt 通常通过 .value 暴露 payload。
    value = getattr(first, "value", None)
    if isinstance(value, dict):
        return value

    # 为不同版本/序列化形式保留兼容处理。
    if isinstance(first, dict):
        nested_value = first.get("value")
        if isinstance(nested_value, dict):
            return nested_value
        return first

    return {"message": str(value if value is not None else first)}


def ask_human(payload: dict[str, Any]) -> dict[str, Any]:
    """从终端收集人工审核结果。"""
    print("\n========== 图已暂停：等待人工审核 ==========")
    print(payload.get("message", "请审核"))
    print(json.dumps(payload.get("proposal", {}), ensure_ascii=False, indent=2))

    while True:
        choice = input(
            "\n请选择 [a]批准 / [r]拒绝 / [e]修改："
        ).strip().lower()

        if choice in {"a", "approve"}:
            return {"action": "approve"}

        if choice in {"r", "reject"}:
            reason = input("请输入拒绝原因：").strip()
            return {
                "action": "reject",
                "reason": reason or "人工审核未通过",
            }

        if choice in {"e", "edit"}:
            original = dict(payload.get("proposal", {}))

            edited_action = input(
                f"交易方向 [{original.get('action', 'BUY')}]："
            ).strip().upper()
            if edited_action:
                original["action"] = edited_action

            edited_symbol = input(
                f"股票代码 [{original.get('symbol', '')}]："
            ).strip().upper()
            if edited_symbol:
                original["symbol"] = edited_symbol

            while True:
                quantity_text = input(
                    f"数量 [{original.get('quantity', 1)}]："
                ).strip()

                if not quantity_text:
                    break

                try:
                    quantity = int(quantity_text)
                    if quantity <= 0:
                        raise ValueError
                    original["quantity"] = quantity
                    break
                except ValueError:
                    print("数量必须是大于 0 的整数。")

            return {
                "action": "edit",
                "proposal": original,
            }

        print("输入无效，请输入 a、r 或 e。")


def main() -> None:
    graph = build_graph()

    company = input("请输入股票代码 [AAPL]：").strip().upper() or "AAPL"

    while True:
        quantity_text = input("请输入建议交易数量 [100]：").strip() or "100"
        try:
            quantity = int(quantity_text)
            if quantity <= 0:
                raise ValueError
            break
        except ValueError:
            print("数量必须是大于 0 的整数。")

    # 每个独立任务应使用唯一 thread_id。
    thread_id = f"trade-review-{uuid.uuid4()}"
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    print(f"\nthread_id: {thread_id}")

    # 第一次调用会运行到 interrupt()，然后返回暂停信息。
    result = graph.invoke(
        {
            "company": company,
            "requested_quantity": quantity,
        },
        config=config,
    )

    payload = extract_interrupt_payload(result)
    if payload is None:
        print("\n图没有发生 interrupt，当前结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    human_decision = ask_human(payload)

    # 恢复时必须使用相同的 thread_id。
    final_state = graph.invoke(
        Command(resume=human_decision),
        config=config,
    )

    print("\n========== 最终状态 ==========")
    print(json.dumps(final_state, ensure_ascii=False, indent=2, default=str))
    print("\n最终结果：", final_state.get("final_result"))


if __name__ == "__main__":
    main()
