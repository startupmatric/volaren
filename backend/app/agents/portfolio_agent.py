"""
LangGraph portfolio agent (Groq variant).

Flow:
    START
      ↓
    prepare_context   (gather evidence — no LLM)
      ↓
    reason            (LLM writes prose based on evidence)
      ↓
    validate          (reject any invented numbers)
      ↓
    finalize          (choose LLM output or deterministic fallback)
      ↓
    END

Design principle: the LLM ONLY writes prose. Every number it
references must come from the deterministic evidence dict.
"""

import json
import os
from typing import Optional, TypedDict

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tools import (
    build_fallback,
    gather_evidence,
    validate_numbers,
)


class AgentState(TypedDict, total=False):
    portfolio_id: int
    evidence: dict
    llm_text: str
    validation: dict
    final: dict
    error: str


SYSTEM_PROMPT = """You are a portfolio analyst writing a brief, factual
explanation of why a portfolio moved.

RULES — you must follow every one:
1. Use ONLY the numbers and tickers provided in the evidence JSON.
   Do NOT invent, estimate, or round any numbers.
2. Do NOT give investment advice, predictions, or recommendations.
3. Write 2-4 short sentences. Plain prose. No bullet points. No headings.
4. If a number is not in the evidence, do not mention it.
5. Mention the top contributor, the top detractor (if any), and the
   leading sector.
6. Do not add a greeting, sign-off, or any wrapping text.
7. Your entire response must be the explanation paragraph — nothing else.

Every percentage you write must appear verbatim (to 2 decimals) in the
evidence. If you cannot honor this, output the deterministic_explanation
field verbatim from the evidence instead.
"""


def _make_reason_node():
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    llm = ChatGroq(
        model=model_name,
        temperature=0.2,
        timeout=30,
        max_retries=2,
    )

    def node_reason(state: AgentState) -> AgentState:
        evidence = state.get("evidence")

        if not evidence:
            return {
                **state,
                "error": state.get("error") or "Missing evidence",
            }

        evidence_json = json.dumps(evidence, indent=2)

        user_prompt = (
            "Here is the structured evidence for the latest portfolio "
            "snapshot:\n\n"
            f"{evidence_json}\n\n"
            "Write the explanation now. Remember: use ONLY the numbers "
            "shown above. Every percentage must appear verbatim."
        )

        try:
            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])

            text = (response.content or "").strip()

            return {
                **state,
                "llm_text": text,
            }

        except Exception as exc:
            return {
                **state,
                "error": f"LLM error: {exc.__class__.__name__}: {exc}",
            }

    return node_reason


def node_validate(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    text = state.get("llm_text", "")
    evidence = state.get("evidence", {})

    result = validate_numbers(text, evidence)

    return {
        **state,
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
    graph.add_node("reason", _make_reason_node())
    graph.add_node("validate", node_validate)
    graph.add_node("finalize", node_finalize)

    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "reason")
    graph.add_edge("reason", "validate")
    graph.add_edge("validate", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_agent(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Run the agent end-to-end and return the final explanation dict.

    Returns None if the portfolio has no snapshots (evidence was never
    loaded), so the API layer can return a clean 404.
    """

    graph = build_agent_graph(db)

    initial_state: AgentState = {
        "portfolio_id": portfolio_id,
    }

    final_state = graph.invoke(initial_state)

    # If evidence was never gathered, the portfolio has no snapshots.
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
    }