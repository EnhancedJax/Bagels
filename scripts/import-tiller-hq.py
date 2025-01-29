"""Import from TillerHQ CSV to Bagels database.

Can be using uv like:
uv run scripts/import-tiller-hq.py
"""
# /// script
# dependencies = [
#   "bagels",
#   "sqlalchemy",
#   "rich",
# ]
# ///
import csv
import logging
from datetime import datetime
from typing import Dict

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import track
from rich.table import Table
from sqlalchemy.orm import sessionmaker

from bagels.models.account import Account
from bagels.models.category import Category
from bagels.models.database.app import db_engine
from bagels.models.database.db import Base
from bagels.models.record import Record

Session = sessionmaker(bind=db_engine)


def init_db():
    Base.metadata.create_all(db_engine)


# Configure logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
log = logging.getLogger("rich")

Session = sessionmaker(bind=db_engine)
console = Console()


def import_from_csv(csv_filepath: str) -> None:
    """Import data from a CSV file into the database.

    Args:
        csv_filepath: Path to the CSV file.
    """
    session = Session()
    try:
        with open(csv_filepath, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            total_rows = sum(1 for _ in open(csv_filepath, mode="r", encoding="utf-8"))
            for row in track(reader, total=total_rows, description="Importing rows..."):
                process_row(row, session)
        session.commit()
        log.info(
            f"[bold green]Successfully imported data from {csv_filepath}[/bold green]"
        )
    except Exception as e:
        session.rollback()
        log.exception(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        session.close()


def process_row(row: Dict[str, str], session) -> None:
    """Process a single row from the CSV file.

    Args:
        row: Dictionary representing a row from the CSV.
        session: SQLAlchemy session.
    """
    log.debug(f"Processing row: {row}")
    account = get_or_create_account(session, row)
    category = get_or_create_category(session, row)
    create_record(session, row, account, category)


def default(value, default):
    return value.strip() if value.strip() else default


def get_or_create_account(session, row: Dict[str, str]) -> Account:
    """Get or create an account based on the CSV row.

    Args:
        session: SQLAlchemy session.
        row: Dictionary representing a row from the CSV.

    Returns:
        An Account object.
    """
    account_name = default(row["Account"], "Default Account")
    account = session.query(Account).filter_by(name=account_name).first()
    if not account:
        log.info(f"Creating new account: [bold blue]{account_name}[/bold blue]")
        account = Account(
            name=account_name, beginningBalance=0, description=row["Institution"]
        )
        session.add(account)
        session.flush()  # Ensure the account gets an ID
    return account


def get_or_create_category(session, row: Dict[str, str]) -> Category:
    """Get or create a category based on the CSV row.

    Args:
        session: SQLAlchemy session.
        row: Dictionary representing a row from the CSV.

    Returns:
        A Category object.
    """
    category_name = row["Category"]
    if not category_name.strip():
        category_name = "Uncategorized"

    category = session.query(Category).filter_by(name=category_name).first()
    if not category:
        log.info(f"Creating new category: [bold blue]{category_name}[/bold blue]")
        category = Category(
            name=category_name,
            nature="NEED",  # Default nature, adjust as needed
            color="white",
        )  # Default color, adjust as needed
        session.add(category)
        session.flush()  # Ensure the category gets an ID
    return category


def create_record(
    session, row: Dict[str, str], account: Account, category: Category
) -> None:
    """Create a record from the CSV row.

    Args:
        session: SQLAlchemy session.
        row: Dictionary representing a row from the CSV.
        account: The Account object associated with the record.
        category: The Category object associated with the record.
    """
    date_str = row["Date"]
    amount_str = row["Amount"].replace("$", "").replace(",", "")
    amount = float(amount_str)
    description = row["Description"].strip()
    if not description:
        description = "No Description"
    record_data = {
        "label": description,
        "amount": abs(amount),
        "date": datetime.strptime(date_str, "%m/%d/%Y"),
        "accountId": account.id,
        "categoryId": category.id,
        "isIncome": amount > 0,
        "isTransfer": False,
    }

    record = Record(**record_data)
    session.add(record)
    log.info(f"Created record: {record_data}")


# Example usage:
if __name__ == "__main__":
    init_db()
    # Displaying a table of dependencies
    table = Table(title="[bold blue]Script Dependencies[/bold blue]")
    table.add_column("Dependency", style="dim", width=12)
    table.add_row("bagels")
    table.add_row("sqlalchemy")
    table.add_row("rich")
    console.print(
        Panel(table, title="[bold blue]Dependencies[/bold blue]", expand=False)
    )

    csv_file_path = "data.csv"  # Replace with your CSV file path
    import_from_csv(csv_file_path)
