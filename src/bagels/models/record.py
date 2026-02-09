from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship, validates

from bagels.config import CONFIG

from .database.db import Base


def _round_decimals() -> int:
    return CONFIG.defaults.round_decimals if CONFIG is not None else 2


class Record(Base):
    __tablename__ = "record"

    createdAt = Column(DateTime, nullable=False, default=datetime.now)
    updatedAt = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    amount = Column(Float, CheckConstraint("amount > 0"), nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.now)
    accountId = Column(Integer, ForeignKey("account.id"), nullable=False)
    categoryId = Column(Integer, ForeignKey("category.id"), nullable=True)

    tags = Column(String, nullable=True)  # unimplemented
    isInProgress = Column(Boolean, nullable=False, default=False)  # unimplemented

    # if record adds money to account
    isIncome = Column(Boolean, nullable=False, default=False)
    # if record is transfer to this account
    isTransfer = Column(
        Boolean,
        CheckConstraint("(isTransfer = FALSE) OR (isIncome = FALSE)"),
        nullable=False,
        default=False,
    )
    transferToAccountId = Column(Integer, ForeignKey("account.id"), nullable=True)
    transferToAmount = Column(Float, nullable=True)

    account = relationship(
        "Account", foreign_keys=[accountId], back_populates="records"
    )
    category = relationship("Category", back_populates="records")
    transferToAccount = relationship(
        "Account",
        foreign_keys=[transferToAccountId],
        back_populates="transferFromRecords",
    )
    splits = relationship(
        "Split", back_populates="record", cascade="all, delete-orphan"
    )

    @validates("amount", "transferToAmount")
    def validate_amount(self, key, value):
        if value is not None:
            return round(value, _round_decimals())
        return value
