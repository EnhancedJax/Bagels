from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship

from bagels.currencies import get_default_currency_code

from .database.db import Base


class Account(Base):
    __tablename__ = "account"

    createdAt = Column(DateTime, nullable=False, default=datetime.now)
    updatedAt = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
    deletedAt = Column(DateTime, nullable=True)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    beginningBalance = Column(Float, nullable=False)
    currencyCode = Column(
        String(3), nullable=True, default=get_default_currency_code()
    )
    repaymentDate = Column(Integer)

    hidden = Column(Boolean, nullable=False, default=False)

    records = relationship(
        "Record", back_populates="account", foreign_keys="[Record.accountId]"
    )
    transferFromRecords = relationship(
        "Record",
        back_populates="transferToAccount",
        foreign_keys="[Record.transferToAccountId]",
    )
    splits = relationship("Split", back_populates="account")
