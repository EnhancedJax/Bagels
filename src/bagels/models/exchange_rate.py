from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from .database.db import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"
    __table_args__ = (
        UniqueConstraint(
            "baseCurrency",
            "quoteCurrency",
            "rateDate",
            name="uq_exchange_rate_base_quote_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    baseCurrency = Column(String(3), nullable=False, index=True)
    quoteCurrency = Column(String(3), nullable=False, index=True)
    rateDate = Column(DateTime, nullable=False, index=True)
    rate = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default="frankfurter")
    fetchedAt = Column(DateTime, nullable=False, default=datetime.now)
    validUntil = Column(
        DateTime, nullable=False, default=lambda: datetime.now() + timedelta(hours=24)
    )
