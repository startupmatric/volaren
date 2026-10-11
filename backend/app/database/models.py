from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def _utcnow():
    """Timezone-aware UTC now, replacing deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    snapshots = relationship(
        "Snapshot",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        order_by="Snapshot.created_at",
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(
        Integer,
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    portfolio_value = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    return_pct = Column(Float, nullable=False)

    portfolio = relationship("Portfolio", back_populates="snapshots")
    holdings = relationship(
        "Holding",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(
        Integer,
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ticker = Column(String, nullable=False)
    shares = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    sector = Column(String, nullable=True)

    position_value = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    return_pct = Column(Float, nullable=False)
    weight_pct = Column(Float, nullable=False)
    contribution_pct = Column(Float, nullable=False)

    snapshot = relationship("Snapshot", back_populates="holdings")