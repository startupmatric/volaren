from app.evaluation.validators import (
    collect_evidence_numbers,
    collect_evidence_tickers,
    extract_numbers,
    extract_tickers,
    validate_numbers_grounded,
    validate_tickers_grounded,
)


def _evidence():
    return {
        "portfolio_id": 1,
        "snapshot_id": 12,
        "return_pct": 3.71,
        "portfolio_value": 17475.00,
        "top_contributor": {
            "ticker": "NVDA",
            "contribution_pct": 1.78,
            "return_pct": 9.09,
            "pnl": 300,
            "weight_pct": 20.60,
        },
        "top_detractor": {
            "ticker": "GOOGL",
            "contribution_pct": -0.30,
            "return_pct": -2.08,
            "pnl": -50,
            "weight_pct": 13.45,
        },
        "all_contributors": [],
        "all_detractors": [],
        "leading_sector": {
            "sector": "Semiconductors",
            "contribution_pct": 2.67,
            "return_pct": 6.62,
            "weight_pct": 41.49,
            "holdings": ["AVGO", "NVDA"],
        },
        "lagging_sector": None,
        "all_sectors": [],
        "deterministic_explanation": "",
    }


def test_extract_numbers_basic():
    assert extract_numbers("up +3.71%") == [3.71]


def test_extract_numbers_currency():
    assert 17475.0 in extract_numbers("worth $17,475.00")


def test_extract_numbers_negative():
    assert -0.30 in extract_numbers("dropped -0.30pp")


def test_extract_numbers_empty():
    assert extract_numbers("") == []
    assert extract_numbers(None) == []


def test_extract_tickers_basic():
    assert extract_tickers("NVDA led, GOOGL dragged") == ["NVDA", "GOOGL"]


def test_extract_tickers_filters_stopwords():
    result = extract_tickers("AI is great, USA up, NVDA led")
    assert "NVDA" in result
    assert "AI" not in result
    assert "USA" not in result


def test_extract_tickers_empty():
    assert extract_tickers("") == []


def test_collect_evidence_numbers():
    facts = collect_evidence_numbers(_evidence())
    assert 3.71 in facts
    assert 1.78 in facts
    assert 0.30 in facts
    assert 17475.0 in facts


def test_collect_evidence_tickers():
    tickers = collect_evidence_tickers(_evidence())
    assert "NVDA" in tickers
    assert "GOOGL" in tickers
    assert "AVGO" in tickers


def test_validate_numbers_grounded_pass():
    explanation = (
        "Your portfolio is up +3.71%, worth $17,475.00. "
        "NVDA added +1.78pp, GOOGL dragged -0.30pp."
    )
    result = validate_numbers_grounded(explanation, _evidence())
    assert result["valid"] is True
    assert result["unsupported"] == []


def test_validate_numbers_grounded_fail_on_hallucination():
    explanation = "Your portfolio is up +3.71%. NVDA added +5.99pp."
    result = validate_numbers_grounded(explanation, _evidence())
    assert result["valid"] is False
    assert 5.99 in result["unsupported"]


def test_validate_numbers_ignores_small_integers():
    result = validate_numbers_grounded("The top 3 holdings drove the move.", _evidence())
    assert result["valid"] is True


def test_validate_tickers_grounded_pass():
    result = validate_tickers_grounded("NVDA and AVGO both rose.", _evidence())
    assert result["valid"] is True


def test_validate_tickers_grounded_fail():
    result = validate_tickers_grounded("NVDA rose while TSLA fell.", _evidence())
    assert result["valid"] is False
    assert "TSLA" in result["unsupported"]