import sqlite3
from datetime import datetime

from bagels.currencies import get_default_currency_code


def convert_date(date_str):
    """Convert YYYYMMDD to datetime with time set to 12:00 PM"""
    if not date_str:
        return datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    try:
        # Convert from YYYYMMDD format
        year = int(str(date_str)[:4])
        month = int(str(date_str)[4:6])
        day = int(str(date_str)[6:8])
        return datetime(year, month, day, 12, 0)
    except Exception:
        return datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)


def ensure_default_category(bagels_cur):
    """Create or get default category for uncategorized transactions."""
    bagels_cur.execute(
        """
        INSERT OR IGNORE INTO category (
            createdAt, updatedAt, name, nature, color, parentCategoryId
        ) VALUES (?, ?, ?, ?, ?, ?)
    """,
        (datetime.now(), datetime.now(), "Uncategorized", "WANT", "#808080", None),
    )

    default_category = bagels_cur.execute("""
        SELECT id FROM category 
        WHERE name = 'Uncategorized' AND parentCategoryId IS NULL
        AND deletedAt IS NULL
    """).fetchone()

    return default_category[0]


class BudgetToBagelsMigration:
    def __init__(self, budget_db_path: str, bagels_db_path: str):
        self.budget_conn = sqlite3.connect(budget_db_path)
        self.bagels_conn = sqlite3.connect(bagels_db_path)
        self.budget_cur = self.budget_conn.cursor()
        self.bagels_cur = self.bagels_conn.cursor()
        self.category_map = {}
        self.account_map = {}
        self.default_category_id = None

    def migrate_accounts(self):
        accounts = self.budget_cur.execute("""
            SELECT id, name, balance_current, official_name, offbudget, closed 
            FROM accounts WHERE tombstone = 0
        """).fetchall()

        for acc_id, name, balance, official_name, offbudget, closed in accounts:
            # Convert cents to dollars
            balance_float = float(balance or 0) / 100
            description = official_name if official_name is not None else ""

            self.bagels_cur.execute(
                """
                INSERT INTO account (createdAt, updatedAt, name, description, 
                                   beginningBalance, hidden, currencyCode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now(),
                    datetime.now(),
                    name or "",
                    description,
                    balance_float,
                    bool(offbudget or closed),
                    get_default_currency_code(),
                ),
            )

            self.account_map[acc_id] = self.bagels_cur.lastrowid

    def migrate_categories(self):
        self.default_category_id = ensure_default_category(self.bagels_cur)

        groups = self.budget_cur.execute("""
            SELECT id, name, is_income 
            FROM category_groups WHERE tombstone = 0
        """).fetchall()

        for group_id, name, is_income in groups:
            self.bagels_cur.execute(
                """
                INSERT INTO category (createdAt, updatedAt, name, nature, color,
                                    parentCategoryId)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now(),
                    datetime.now(),
                    name or "",
                    "MUST" if is_income else "WANT",
                    "#808080",
                    None,
                ),
            )
            parent_id = self.bagels_cur.lastrowid

            categories = self.budget_cur.execute(
                """
                SELECT id, name, is_income 
                FROM categories 
                WHERE cat_group = ? AND tombstone = 0
            """,
                (group_id,),
            ).fetchall()

            for cat_id, cat_name, cat_is_income in categories:
                self.bagels_cur.execute(
                    """
                    INSERT INTO category (createdAt, updatedAt, name, nature,
                                        color, parentCategoryId)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        datetime.now(),
                        datetime.now(),
                        cat_name or "",
                        "MUST" if cat_is_income else "WANT",
                        "#808080",
                        parent_id,
                    ),
                )
                self.category_map[cat_id] = self.bagels_cur.lastrowid

    def migrate_transactions(self):
        transactions = self.budget_cur.execute("""
            SELECT id, account, category, amount, date, 
                   starting_balance_flag, transfer_id, is_parent
            FROM v_transactions_internal 
            WHERE tombstone = 0 AND is_child = 0
            AND (transfer_id IS NULL OR amount >= 0)
        """).fetchall()

        for (
            trans_id,
            account_id,
            category_id,
            amount,
            date,
            is_starting_balance,
            transfer_id,
            is_parent,
        ) in transactions:
            if account_id not in self.account_map:
                continue

            transaction_date = convert_date(date)

            amount_float = abs(float(amount or 0) / 100)
            if amount_float == 0:
                continue

            account_bagels_id = self.account_map[account_id]
            category_bagels_id = self.category_map.get(
                category_id, self.default_category_id
            )

            category_info = self.budget_cur.execute(
                """
                SELECT is_income FROM categories WHERE id = ?
            """,
                (category_id,),
            ).fetchone()
            is_income = category_info[0] if category_info else 0

            transfer_to_account_id = None
            is_transfer = bool(transfer_id)
            if transfer_id:
                transfer_account = self.budget_cur.execute(
                    """
                    SELECT account FROM v_transactions_internal WHERE id = ?
                """,
                    (transfer_id,),
                ).fetchone()
                if transfer_account and transfer_account[0] in self.account_map:
                    transfer_to_account_id = self.account_map[transfer_account[0]]

            self.bagels_cur.execute(
                """
                INSERT INTO record (
                    createdAt, updatedAt, label, amount, date,
                    accountId, categoryId, isIncome, isTransfer,
                    transferToAccountId, isInProgress
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now(),
                    datetime.now(),
                    "Imported transaction",
                    amount_float,
                    transaction_date,
                    account_bagels_id,
                    category_bagels_id,
                    bool(is_income),
                    is_transfer,
                    transfer_to_account_id,
                    False,
                ),
            )

    def verify_and_fix_categories(self):
        """Verify all records have valid categories and fix any issues"""
        self.bagels_cur.execute(
            """
            UPDATE record 
            SET categoryId = ? 
            WHERE categoryId IS NULL OR 
                  categoryId NOT IN (SELECT id FROM category)
        """,
            (self.default_category_id,),
        )

        null_categories = self.bagels_cur.execute("""
            SELECT COUNT(*) 
            FROM record 
            WHERE categoryId IS NULL
        """).fetchone()[0]

        if null_categories > 0:
            raise Exception(
                f"Found {null_categories} records with NULL categories after fix"
            )

    def migrate(self):
        self.bagels_conn.execute("BEGIN TRANSACTION")
        try:
            self.migrate_accounts()
            self.migrate_categories()
            self.migrate_transactions()
            self.verify_and_fix_categories()
            self.bagels_conn.commit()
            print("Migration completed successfully!")
        except Exception as e:
            self.bagels_conn.rollback()
            raise e
        finally:
            self.budget_conn.close()
            self.bagels_conn.close()


if __name__ == "__main__":
    migrator = BudgetToBagelsMigration("db.sqlite", "bagels.db")
    migrator.migrate()
