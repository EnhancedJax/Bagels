import csv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bagels.models.record import Record

from bagels.locations import set_custom_root, database_file

set_custom_root("instance")
db_path = database_file().resolve()

engine = create_engine(
    f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)


def export_to_csv(filepath="bagels_export.csv"):
    session = SessionLocal()
    try:
        records = session.query(Record).all()
        total = 0

        with open(filepath, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Date", "Label", "Amount", "Category", "Account", "Type"])

            for r in records:
                amount = r.amount if r.isIncome else -r.amount
                total += amount
                writer.writerow(
                    [
                        r.date.strftime("%Y-%m-%d"),
                        r.label,
                        amount,
                        r.category.name if r.category else "Uncategorized",
                        r.account.name if r.account else "Unknown",
                        "Income" if r.isIncome else "Expense",
                    ]
                )

        print(f"✅ Export complete! File saved as: {filepath}")
        print(f"💰 Net total (income - expense): {total:.2f}")

    finally:
        session.close()


if __name__ == "__main__":
    export_to_csv()
