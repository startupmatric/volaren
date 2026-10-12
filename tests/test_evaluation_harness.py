from app.evaluation.datasets import GOLDEN_CASES
from app.evaluation.harness import (
    run_all_cases,
    run_case_by_name,
    run_single_case,
    summarize,
)


CANNED = {
    "nvda_led_gain": (
        "Your portfolio is up +3.71%, currently worth $17,475.00. "
        "NVDA is the largest contributor, adding +1.78pp. "
        "GOOGL dragged by -0.30pp. "
        "Semiconductors led at +2.67pp."
    ),
    "flat_portfolio": "Your portfolio is flat at $10,000.00.",
    "negative_portfolio": (
        "Your portfolio is down -2.50%, currently worth $9,750.00. "
        "MSFT is the biggest contributor at +0.60pp. "
        "NVDA is the biggest drag at -3.10pp. "
        "Technology led at +0.60pp and Semiconductors lagged at -3.10pp."
    ),
    "single_holding": (
        "Your portfolio is up +9.09%, currently worth $3,600.00. "
        "NVDA is the sole contributor at +9.09pp. "
        "Semiconductors led at +9.09pp."
    ),
    "unclassified_sector": (
        "Your portfolio is up +2.00%, currently worth $10,200.00. "
        "ACME is the biggest contributor at +2.00pp. "
        "Unclassified led at +2.00pp."
    ),
}


def mock_runner(case):
    return CANNED.get(case["name"], "")


# =========================================================
# Full suite
# =========================================================

def test_run_all_cases_all_pass():
    report = run_all_cases(mock_runner)
    assert report["total"] == 5
    assert report["passed"] == 5
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0


def test_run_all_cases_one_failure():
    def bad_runner(case):
        if case["name"] == "nvda_led_gain":
            return (
                "Your portfolio is up +3.71%. "
                "NVDA added +5.99pp. "
                "Semiconductors led at +2.67pp."
            )
        return CANNED[case["name"]]

    report = run_all_cases(bad_runner)
    assert report["passed"] == 4
    assert report["failed"] == 1


# =========================================================
# Single case
# =========================================================

def test_run_single_case():
    case = GOLDEN_CASES[0]
    result = run_single_case(case, mock_runner)
    assert result["passed"] is True
    assert "explanation" in result


def test_run_case_by_name_found():
    result = run_case_by_name("flat_portfolio", mock_runner)
    assert result is not None
    assert result["passed"] is True


def test_run_case_by_name_missing():
    result = run_case_by_name("nonexistent_case", mock_runner)
    assert result is None


# =========================================================
# Error handling
# =========================================================

def test_harness_handles_runner_exception():
    def broken_runner(case):
        raise RuntimeError("Simulated agent failure")

    report = run_all_cases(broken_runner)
    assert report["passed"] == 0
    assert report["total"] == 5
    # Each result should have an error field
    for r in report["results"]:
        assert "error" in r


# =========================================================
# Summary
# =========================================================

def test_summarize_averages():
    report = run_all_cases(mock_runner)
    summary = summarize(report)

    assert summary["avg_grounding"] == 1.0
    assert summary["avg_ticker_accuracy"] == 1.0
    assert summary["avg_fact_accuracy"] == 1.0


def test_summarize_empty():
    summary = summarize({"results": []})
    assert summary["avg_grounding"] == 0.0