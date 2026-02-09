from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from bagels.config import CONFIG
from bagels.constants import OUTSIDE_SOURCE_ACCOUNT_NAME
from bagels.currencies import get_default_currency_code, normalize_currency_code
from bagels.locations import database_file

# -------- create all imports -------- #
from bagels.models.account import Account
from bagels.models.category import Category, Nature
from bagels.models.database.db import Base
from bagels.models.person import Person  # noqa: F401
from bagels.models.record import Record  # noqa: F401
from bagels.models.record_template import RecordTemplate  # noqa: F401
from bagels.models.split import Split  # noqa: F401
from bagels.models.exchange_rate import ExchangeRate  # noqa: F401

db_engine = create_engine(f"sqlite:///{database_file().resolve()}")
Session = sessionmaker(bind=db_engine)


def _create_outside_source_account(session):
    outside_account = session.query(Account).filter_by(
        name=OUTSIDE_SOURCE_ACCOUNT_NAME
    ).first()
    if not outside_account:
        main_currency = (
            normalize_currency_code(CONFIG.state.currency.main_currency)
            if CONFIG is not None
            else get_default_currency_code()
        )
        outside_account = Account(
            name=OUTSIDE_SOURCE_ACCOUNT_NAME,
            description="Default account for external transactions",
            beginningBalance=0.0,
            hidden=True,
            currencyCode=main_currency,
        )
        session.add(outside_account)
        session.commit()


def _create_default_categories(session):
    category_count = session.query(Category).count()
    if category_count > 0:
        return

    yaml_path = (
        Path(__file__).parent.parent.parent / "static" / "default_categories.yaml"
    )

    with open(yaml_path, "r") as file:
        default_categories = yaml.safe_load(file)

    for category in default_categories:
        parent = Category(
            name=category["name"],
            nature=getattr(Nature, category["nature"]),
            color=category["color"],
            parentCategoryId=None,
        )
        session.add(parent)
        session.commit()

        for subcategory in category["subcategories"]:
            child = Category(
                name=subcategory["name"],
                nature=getattr(Nature, subcategory["nature"]),
                color=category["color"],
                parentCategoryId=parent.id,
            )
            session.add(child)
            session.commit()


def _fix_dangling_categories(session):
    dangling_subcategories = (
        session.query(Category)
        .filter(
            Category.parentCategoryId.isnot(None),
            Category.deletedAt.is_(None),
            Category.parentCategoryId.in_(
                session.query(Category.id).filter(Category.deletedAt.isnot(None))
            ),
        )
        .all()
    )

    for subcategory in dangling_subcategories:
        subcategory.deletedAt = datetime.now()
        session.add(subcategory)

    session.commit()


def _sync_account_currencies(session):
    main_currency = (
        normalize_currency_code(CONFIG.state.currency.main_currency)
        if CONFIG is not None
        else get_default_currency_code()
    )
    accounts = session.query(Account).all()
    updated = False
    for account in accounts:
        normalized = normalize_currency_code(account.currencyCode, fallback=main_currency)
        if account.currencyCode != normalized:
            account.currencyCode = normalized
            session.add(account)
            updated = True
    if updated:
        session.commit()


def _sync_database_schema():
    def _default_to_sql(column) -> str:
        if column.default is None:
            return ""
        default_value = getattr(column.default, "arg", None)
        if callable(default_value):
            return ""
        if default_value is None:
            return ""
        if isinstance(default_value, bool):
            return f"DEFAULT {1 if default_value else 0}"
        if isinstance(default_value, str):
            escaped = default_value.replace("'", "''")
            return f"DEFAULT '{escaped}'"
        return f"DEFAULT {default_value}"

    try:
        inspector = inspect(db_engine)
        existing_tables = inspector.get_table_names()

        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                table.create(db_engine)
            else:
                existing_columns = {
                    col["name"] for col in inspector.get_columns(table.name)
                }
                model_columns = {col.name for col in table.columns}

                for column_name in model_columns - existing_columns:
                    column = table.columns[column_name]
                    with db_engine.begin() as conn:
                        conn.execute(
                            text(
                                f'ALTER TABLE {table.name} ADD COLUMN "{column_name}" '
                                f"{column.type} "
                                f"{'NOT NULL' if not column.nullable else ''} "
                                f"{_default_to_sql(column)}"
                            )
                        )
    except Exception as e:
        raise Exception(f"Failed to sync database schema: {str(e)}")


def init_db():
    _sync_database_schema()
    Base.metadata.create_all(db_engine)
    session = Session()
    _create_outside_source_account(session)
    _create_default_categories(session)
    _fix_dangling_categories(session)
    _sync_account_currencies(session)
    session.close()


def wipe_database():
    Base.metadata.drop_all(db_engine)
    _sync_database_schema()
    Base.metadata.create_all(db_engine)
    session = Session()
    _create_outside_source_account(session)
    _create_default_categories(session)
    _sync_account_currencies(session)
    session.close()
