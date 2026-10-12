from app.evaluation.datasets import GOLDEN_CASES, get_case_by_name
from app.evaluation.evaluator import evaluate_explanation


def _case(name):
    c = get_case_by_name(name)
    assert c is not None, f"missing case {name}"
    return c


def test_evaluate_passing_explanation():
    case = _case("nvda_led_gain")
    explanation = (
        "Your portfolio is up +3.71%, currently worth $17,475.00. "
        "NVDA is the largest contributor, adding +1.78pp. "
        "GOOGL dragged by -0.30pp. "
        "Semiconductors led at +2.67pp."
    )
    result = evaluate_explanation(explanation, case)

    assert result["passed"] is True
    assert result["scores"]["grounding"] == 1.0
    assert result["scores"]["ticker_accuracy"] == 1.0
    assert result["scores"]["fact_accuracy"] == 1.0
    assert result["unsupported_numbers"] == []
    assert result["unsupported_tickers"] == []
    assert result["missing_expected_facts"] == {}


def test_evaluate_hallucinated_number():
    case = _case("nvda_led_gain")
    explanation = (
        "Your portfolio is up +3.71%. NVDA added +5.99pp. "
        "Semiconductors led at +2.67pp."
    )
    result = evaluate_explanation(explanation, case)

    assert result["passed"] is False
    assert 5.99 in result["unsupported_numbers"]


def test_evaluate_hallucinated_ticker():
    case = _case("nvda_led_gain")
    explanation = (
        "Your portfolio is up +3.71%. TSLA was the top contributor. "
        "GOOGL dragged by -0.30pp."
    )
    result = evaluate_explanation(explanation, case)

    assert result["passed"] is False
    assert "TSLA" in result["unsupported_tickers"]


def test_evaluate_missing_facts():
    case = _case("nvda_led_gain")
    result = evaluate_explanation("Your portfolio is up +3.71%.", case)

    assert result["passed"] is False
    assert result["scores"]["fact_accuracy"] < 0.8


def test_evaluate_empty_explanation():
    case = _case("nvda_led_gain")
    result = evaluate_explanation("", case)

    assert result["passed"] is False
    assert result.get("reason") == "empty_explanation"


def test_evaluate_flat_portfolio():
    case = _case("flat_portfolio")
    result = evaluate_explanation("Your portfolio is flat at $10,000.00.", case)

    assert result["passed"] is True
    assert result["scores"]["fact_accuracy"] == 1.0


def test_evaluate_negative_portfolio():
    case = _case("negative_portfolio")
    explanation = (
        "Your portfolio is down -2.50%, currently worth $9,750.00. "
        "MSFT is the biggest contributor at +0.60pp. "
        "NVDA is the biggest drag at -3.10pp. "
        "Technology led at +0.60pp and Semiconductors lagged at -3.10pp."
    )
    result = evaluate_explanation(explanation, case)

    assert result["passed"] is True


GOOD_EXPLANATIONS = {
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


def test_all_golden_cases_pass_with_good_explanations():
    for case in GOLDEN_CASES:
        explanation = GOOD_EXPLANATIONS.get(case["name"], "")
        result = evaluate_explanation(explanation, case)
        assert result["passed"] is True, f"{case['name']} failed: {result}"