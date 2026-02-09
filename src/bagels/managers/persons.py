from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import contains_eager, joinedload, sessionmaker

from bagels.managers.currency import convert_account_amount, get_main_currency
from bagels.managers.utils import get_operator_amount, get_start_end_of_period
from bagels.models.category import Category
from bagels.models.database.app import db_engine
from bagels.models.person import Person
from bagels.models.record import Record
from bagels.models.split import Split

Session = sessionmaker(bind=db_engine)


# region Create


def create_person(data):
    """Create a new person entry in the database."""
    session = Session()
    try:
        new_person = Person(**data)
        session.add(new_person)
        session.commit()
        session.refresh(new_person)
        session.expunge(new_person)
        return new_person
    finally:
        session.close()


# region Read


def get_all_persons() -> list[Person]:
    """Retrieve all undeleted persons from the database."""
    session = Session()
    try:
        return session.scalars(select(Person).where(Person.deletedAt.is_(None))).all()
    finally:
        session.close()


def get_person_by_id(person_id) -> Person:
    """Retrieve a person by their ID."""
    session = Session()
    try:
        return session.get(Person, person_id)
    finally:
        session.close()


def get_persons_with_splits(
    offset: int = 0,
    offset_type: str = "month",
    category_piped_names: str = None,
    operator_amount: str = None,
    label: str = None,
):
    """Get all persons with their splits for the specified period."""
    session = Session()
    try:
        start_of_period, end_of_period = get_start_end_of_period(offset, offset_type)

        # Build the base query
        stmt = (
            select(Person)
            .options(
                contains_eager(Person.splits)
                .contains_eager(Split.record)
                .contains_eager(Record.category),
                contains_eager(Person.splits).contains_eager(Split.account),
            )
            .join(Person.splits)
            .join(Split.record)
            .outerjoin(Record.category)
            .outerjoin(Split.account)
        )

        # Apply date filter
        stmt = stmt.filter(
            and_(Record.date >= start_of_period, Record.date < end_of_period)
        )

        # Apply category filter
        if category_piped_names not in [None, ""]:
            category_names = category_piped_names.split("|")
            stmt = stmt.filter(Category.name.in_(category_names))

        # Apply amount filter
        if operator_amount not in [None, ""]:
            operator, amount = get_operator_amount(operator_amount)
            if operator and amount:
                stmt = stmt.filter(Split.amount.op(operator)(amount))

        # Apply label filter
        if label not in [None, ""]:
            stmt = stmt.filter(Record.label.ilike(f"%{label}%"))

        # Apply ordering and distinct
        stmt = stmt.order_by(Record.date.asc()).distinct()

        result = session.scalars(stmt)
        return result.unique().all()
    finally:
        session.close()


@dataclass
class PersonWithDue:
    person: Person
    due: float


def get_persons_with_net_due() -> list[Person]:
    """Retrieve all persons with their net due amount."""
    session = Session()
    try:
        stmt = (
            select(Person)
            .where(Person.deletedAt.is_(None))
            .options(
                joinedload(Person.splits)
                .joinedload(Split.record)
                .joinedload(Record.account)
            )
        )

        result = session.scalars(stmt).all()
        persons_with_due = []
        main_currency = get_main_currency()
        for person in result:
            due = 0.0
            for split in person.splits:
                if split.isPaid or split.record is None:
                    continue
                split_amount = -split.amount if split.record.isIncome else split.amount
                due += convert_account_amount(
                    split_amount,
                    split.record.account,
                    to_currency=main_currency,
                    at=split.record.date,
                    session=session,
                )
            person.due = round(due, 2)
            persons_with_due.append(person)
        persons_with_due.sort(key=lambda p: (-abs(p.due), p.name or ""))
        return persons_with_due
    finally:
        session.close()


# region Update


def update_person(person_id, data) -> Person:
    """Update a person's information by their ID."""
    session = Session()
    try:
        person = session.get(Person, person_id)
        if person:
            for key, value in data.items():
                setattr(person, key, value)
            session.commit()
            session.refresh(person)
            session.expunge(person)
        return person
    finally:
        session.close()


# region Delete


def delete_person(person_id) -> bool:
    """Delete a person - if they have splits, soft delete by setting deletedAt, otherwise hard delete."""
    session = Session()
    try:
        person = session.get(Person, person_id)
        if person:
            # Check if person has any splits
            has_splits = (
                session.query(Split).filter(Split.personId == person_id).first()
                is not None
            )

            if has_splits:
                # Soft delete if person has splits
                person.deletedAt = func.now()
            else:
                # Hard delete if person has no splits
                session.delete(person)

            session.commit()
            return True
        return False
    finally:
        session.close()
