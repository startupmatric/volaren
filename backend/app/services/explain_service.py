from typing import Optional

from sqlalchemy.orm import Session

from app.services.attribution_service import (
    get_movers,
    get_sector_attribution,
)


def _format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _format_pp(value: float) -> str:
    """Percentage points, with explicit sign."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}pp"


def _format_pp_unsigned(value: float) -> str:
    """Percentage points, no leading sign (magnitude only)."""
    return f"{abs(value):.2f}pp"


def _format_currency(value: float) -> str:
    sign = "-" if value < 0 else "+"
    return f"{sign}${abs(value):,.2f}"


def _direction_word(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _join_tickers(tickers: list) -> str:
    if not tickers:
        return ""
    if len(tickers) == 1:
        return tickers[0]
    if len(tickers) == 2:
        return f"{tickers[0]} and {tickers[1]}"
    return ", ".join(tickers[:-1]) + f", and {tickers[-1]}"


def explain_attribution(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Deterministic natural-language explanation of the latest
    snapshot's performance.

    Returns None if the portfolio has no snapshots.
    """

    movers = get_movers(db, portfolio_id)

    if movers is None:
        return None

    attribution = get_sector_attribution(db, portfolio_id)

    return_pct = movers["return_pct"]
    portfolio_value = movers["portfolio_value"]

    contributors = movers["top_contributors"]
    detractors = movers["top_detractors"]
    sectors = attribution["sectors"] if attribution else []

    sentences = []

    # ------------------------------------------------------
    # Sentence 1 — overall direction
    # ------------------------------------------------------

    direction = _direction_word(return_pct)
    value_str = _format_currency(portfolio_value).replace("+", "")

    if return_pct == 0:
        sentences.append(
            f"Your portfolio is flat at {value_str}."
        )
    else:
        sentences.append(
            f"Your portfolio is {direction} "
            f"{_format_pct(return_pct)}, currently worth "
            f"{value_str}."
        )

    # ------------------------------------------------------
    # Sentence 2 — biggest contributor
    # ------------------------------------------------------

    if contributors:
        top = contributors[0]
        sentences.append(
            f"{top['ticker']} is the biggest contributor, "
            f"adding {_format_pp(top['contribution_pct'])} "
            f"to portfolio return."
        )

    # ------------------------------------------------------
    # Sentence 3 — biggest drag
    # ------------------------------------------------------

    if detractors:
        worst = detractors[0]
        sentences.append(
            f"{worst['ticker']} is the biggest drag, "
            f"subtracting {_format_pp_unsigned(worst['contribution_pct'])} "
            f"from portfolio return."
        )

    # ------------------------------------------------------
    # Sentence 4 — leading sector (highest positive contribution)
    # ------------------------------------------------------

    leading_sector_name = None

    if sectors:
        leading = max(
            sectors,
            key=lambda s: s["contribution_pct"],
        )
        leading_sector_name = leading["sector"]

        if leading["contribution_pct"] > 0:
            member_str = _join_tickers(leading["holdings"])
            sentences.append(
                f"{leading['sector']} led performance at "
                f"{_format_pp(leading['contribution_pct'])}, "
                f"driven by {member_str}."
            )

    # ------------------------------------------------------
    # Sentence 5 — lagging sector (must be negative and not the leader)
    # ------------------------------------------------------

    if sectors:
        lagging = min(
            sectors,
            key=lambda s: s["contribution_pct"],
        )

        if (
            lagging["contribution_pct"] < 0
            and lagging["sector"] != leading_sector_name
        ):
            member_str = _join_tickers(lagging["holdings"])
            sentences.append(
                f"{lagging['sector']} lagged at "
                f"{_format_pp(lagging['contribution_pct'])}, "
                f"held back by {member_str}."
            )

    # ------------------------------------------------------
    # Assemble
    # ------------------------------------------------------

    explanation = " ".join(sentences)

    return {
        "portfolio_id": portfolio_id,
        "snapshot_id": movers["snapshot_id"],
        "return_pct": return_pct,
        "portfolio_value": portfolio_value,
        "headline": sentences[0] if sentences else "",
        "explanation": explanation,
        "sentences": sentences,
    }