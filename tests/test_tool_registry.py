"""
Tests for tool_registry.py — intent → required tools mapping
and coverage checking.
"""

from app.agents.tool_registry import (
    ALL_INTENTS,
    INTENT_EXPLAIN_MOVEMENT,
    INTENT_PORTFOLIO_CHANGES,
    INTENT_PORTFOLIO_HISTORY,
    INTENT_PORTFOLIO_SUMMARY,
    check_tool_coverage,
    get_optional_tools,
    get_required_tools,
    is_valid_intent,
)


def test_all_intents_defined():
    assert INTENT_EXPLAIN_MOVEMENT in ALL_INTENTS
    assert INTENT_PORTFOLIO_SUMMARY in ALL_INTENTS
    assert INTENT_PORTFOLIO_HISTORY in ALL_INTENTS
    assert INTENT_PORTFOLIO_CHANGES in ALL_INTENTS
    assert len(ALL_INTENTS) == 4


def test_explain_movement_requires_three_tools():
    required = get_required_tools(INTENT_EXPLAIN_MOVEMENT)

    assert "get_portfolio_movers" in required
    assert "get_portfolio_summary" in required
    assert "get_portfolio_sectors" in required
    assert len(required) == 3


def test_explain_movement_changes_is_optional():
    optional = get_optional_tools(INTENT_EXPLAIN_MOVEMENT)
    assert "get_portfolio_changes" in optional


def test_portfolio_summary_requires_one_tool():
    required = get_required_tools(INTENT_PORTFOLIO_SUMMARY)
    assert required == ["get_portfolio_summary"]


def test_portfolio_history_requires_one_tool():
    required = get_required_tools(INTENT_PORTFOLIO_HISTORY)
    assert required == ["get_portfolio_history"]


def test_portfolio_changes_requires_one_tool():
    required = get_required_tools(INTENT_PORTFOLIO_CHANGES)
    assert required == ["get_portfolio_changes"]


def test_get_required_tools_unknown_intent_returns_empty():
    assert get_required_tools("nonexistent") == []


def test_is_valid_intent():
    assert is_valid_intent(INTENT_EXPLAIN_MOVEMENT) is True
    assert is_valid_intent("nonexistent") is False


# =========================================================
# check_tool_coverage
# =========================================================

def test_coverage_all_called():
    result = check_tool_coverage(
        INTENT_EXPLAIN_MOVEMENT,
        [
            "get_portfolio_movers",
            "get_portfolio_summary",
            "get_portfolio_sectors",
        ],
    )

    assert result["satisfied"] is True
    assert result["missing"] == []
    assert result["coverage"] == 1.0
    assert result["intent"] == INTENT_EXPLAIN_MOVEMENT


def test_coverage_one_missing():
    result = check_tool_coverage(
        INTENT_EXPLAIN_MOVEMENT,
        ["get_portfolio_movers", "get_portfolio_summary"],
    )

    assert result["satisfied"] is False
    assert "get_portfolio_sectors" in result["missing"]
    assert result["coverage"] == round(2 / 3, 4)


def test_coverage_extra_optional_called():
    result = check_tool_coverage(
        INTENT_EXPLAIN_MOVEMENT,
        [
            "get_portfolio_movers",
            "get_portfolio_summary",
            "get_portfolio_sectors",
            "get_portfolio_changes",
        ],
    )

    assert result["satisfied"] is True
    assert result["coverage"] == 1.0


def test_coverage_none_called():
    result = check_tool_coverage(INTENT_EXPLAIN_MOVEMENT, [])

    assert result["satisfied"] is False
    assert len(result["missing"]) == 3
    assert result["coverage"] == 0.0


def test_coverage_unknown_intent():
    result = check_tool_coverage("nonexistent", ["whatever"])

    assert result["satisfied"] is True
    assert result["coverage"] == 1.0
    assert result["required"] == []