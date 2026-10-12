"""
LangGraph portfolio agent — with native tool calling.

Flow:
    START
      ↓
    prepare_context        (load minimal evidence, no LLM)
      ↓
    agent                  (LLM decides which tools to call)
      ↓
    [tools_condition]
      ├── has tool_calls → tools → (back to agent)
      └── no tool_calls → validate
                           ↓
                         finalize
                           ↓
                          END

Design principles (unchanged from Day 6):
  - The LLM only writes prose. Every number must come from a tool result.
  - Tool calls are recorded for evaluation.
  - If the LLM errors or the output is ungrounded, we fall back to
    the deterministic explanation.
"""

import json
import os
import time
from typing import Any, Optional, TypedDict

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session

from app.agents.tool_registry import INTENT_EXPLAIN_MOVEMENT
from app.agents.tools import (
    build_fallback,
    gather_evidence,
    validate_numbers,
)
from app.agents.tools_v2 import ALL_TOOLS


class AgentState(TypedDict, total=False):
    portfolio_id: int
    intent: str

    evidence: dict

    messages: list

    llm_text: str
    tool_calls: list

    validation: dict

    final: dict
    error: str


SYSTEM_PROMPT = """You are a portfolio analyst. Your job is to explain, in plain
English, why a portfolio moved and what that means.

You have access to these tools. Call them to get data — do NOT invent numbers.

  - get_portfolio_movers      → top contributors and detractors
  - get_portfolio_summary     → total value, cost basis, P&L, return %
  - get_portfolio_sectors     → sector attribution and leading sector

For an "explain_movement" question, you MUST call ALL THREE tools
(get_portfolio_movers, get_portfolio_summary, get_portfolio_sectors)
before writing the final explanation.

Rules:
1. Use ONLY numbers returned by tools. Do not invent or estimate.
2. Do NOT give investment advice, predictions, or recommendations.
3. Write 3-4 short sentences. Plain prose. No bullet points, no headings.
4. Your explanation MUST cover ALL of the following:
     a) the overall portfolio return percentage
     b) the top contributor ticker and its contribution in percentage points
     c) the top detractor ticker (if any) and its contribution in percentage points
     d) the leading sector (from get_portfolio_sectors)
5. Every percentage must appear verbatim (to 2 decimals) from a tool result.
6. When you have all the data you need, produce the final explanation as
   a plain-text response. Do not call any more tools.
7. Do not add a greeting, sign-off, or any wrapping text.
"""


def _make_agent_node():
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    llm = ChatGroq(
        model=model_name,
        temperature=0.2,
        timeout=60,
        max_retries=2,
    )

    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def node_agent(state: AgentState) -> AgentState:
        messages = state.get("messages") or []

        if not messages:
            evidence = state.get("evidence") or {}
            intent = state.get("intent") or INTENT_EXPLAIN_MOVEMENT

            evidence_json = json.dumps(evidence, indent=2)

            user_prompt = (
                f"Intent: {intent}\n\n"
                f"Portfolio evidence (context only — get numbers from tools):\n"
                f"{evidence_json}\n\n"
                "Call the required tools, then write the explanation."
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

        try:
            response = llm_with_tools.invoke(messages)
        except Exception as exc:
            return {
                **state,
                "error": f"LLM error: {exc.__class__.__name__}: {exc}",
            }

        return {
            **state,
            "messages": messages + [response],
        }

    return node_agent


def _make_tools_node():
    tool_node = ToolNode(ALL_TOOLS)

    def node_tools(state: AgentState) -> AgentState:
        messages = state.get("messages") or []

        ai_msg = None
        for m in reversed(messages):
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                ai_msg = m
                break

        started = time.perf_counter()

        try:
            result = tool_node.invoke({"messages": messages})
        except Exception as exc:
            return {
                **state,
                "error": f"Tool error: {exc.__class__.__name__}: {exc}",
            }

        elapsed_ms = (time.perf_counter() - started) * 1000

        recorded = list(state.get("tool_calls") or [])

        if ai_msg is not None:
            per_call_latency = (
                round(elapsed_ms / max(len(ai_msg.tool_calls), 1), 2)
            )

            for tc in ai_msg.tool_calls:
                recorded.append({
                    "name": tc.get("name"),
                    "args": tc.get("args") or {},
                    "latency_ms": per_call_latency,
                })

        new_messages = result.get("messages") or []

        return {
            **state,
            "messages": messages + new_messages,
            "tool_calls": recorded,
        }

    return node_tools


def route_after_agent(state: AgentState) -> str:
    """If the last AI message has tool calls, run tools. Else validate."""

    if state.get("error"):
        return "validate"

    messages = state.get("messages") or []
    if not messages:
        return "validate"

    last = messages[-1]

    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"

    return "validate"


def node_validate(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    messages = state.get("messages") or []

    final_text = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            final_text = (m.content or "").strip()
            break

    evidence = state.get("evidence") or {}
    result = validate_numbers(final_text, evidence)

    return {
        **state,
        "llm_text": final_text,
        "validation": result,
    }


def node_finalize(state: AgentState) -> AgentState:
    if state.get("error"):
        return {
            **state,
            "final": build_fallback(state.get("evidence") or {}),
        }

    validation = state.get("validation") or {}
    evidence = state.get("evidence") or {}
    llm_text = state.get("llm_text", "")

    if validation.get("valid") and llm_text:
        return {
            **state,
            "final": {
                "explanation": llm_text,
                "source": "llm",
                "validation": validation,
            },
        }

    return {
        **state,
        "final": build_fallback(evidence),
    }


def build_agent_graph(db: Session):
    def node_prepare_context_bound(state: AgentState) -> AgentState:
        portfolio_id = state["portfolio_id"]
        evidence = gather_evidence(db, portfolio_id)

        if evidence is None:
            return {
                **state,
                "error": "No snapshots found for this portfolio",
            }

        return {
            **state,
            "evidence": evidence,
        }

    graph = StateGraph(AgentState)

    graph.add_node("prepare_context", node_prepare_context_bound)
    graph.add_node("agent", _make_agent_node())
    graph.add_node("tools", _make_tools_node())
    graph.add_node("validate", node_validate)
    graph.add_node("finalize", node_finalize)

    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "agent")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "validate": "validate",
        },
    )

    graph.add_edge("tools", "agent")
    graph.add_edge("validate", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_agent(
    db: Session,
    portfolio_id: int,
    intent: str = INTENT_EXPLAIN_MOVEMENT,
) -> Optional[dict]:
    graph = build_agent_graph(db)

    initial_state: AgentState = {
        "portfolio_id": portfolio_id,
        "intent": intent,
    }

    final_state = graph.invoke(initial_state)

    if not final_state.get("evidence"):
        return None

    final = final_state.get("final")
    if final is None:
        return None

    return {
        "portfolio_id": portfolio_id,
        "explanation": final["explanation"],
        "source": final["source"],
        "validation": final["validation"],
        "tool_calls": final_state.get("tool_calls") or [],
    }