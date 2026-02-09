from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship, validates

from bagels.config import CONFIG

from .database.db import Base


def _round_decimals() -> int:
    return CONFIG.defaults.round_decimals if CONFIG is not None else 2


class Split(Base):
    __tablename__ = "split"

    createdAt = Column(DateTime, nullable=False, default=datetime.now)
    updatedAt = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    id = Column(Integer, primary_key=True, index=True)
    recordId = Column(
        Integer, ForeignKey("record.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Float, nullable=False)
    personId = Column(Integer, ForeignKey("person.id"), nullable=False)
    isPaid = Column(Boolean, nullable=False, default=False)
    paidDate = Column(DateTime, nullable=True)
    accountId = Column(Integer, ForeignKey("account.id"), nullable=True)

    record = relationship("Record", foreign_keys=[recordId], back_populates="splits")
    person = relationship("Person", foreign_keys=[personId], back_populates="splits")
    account = relationship("Account", foreign_keys=[accountId], back_populates="splits")

    @validates("amount")
    def validate_amount(self, key, value):
        if value is not None:
            return round(value, _round_decimals())
        return value
