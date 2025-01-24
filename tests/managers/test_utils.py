import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bagels.models.database.db import Base
from bagels.models.account import Account
from bagels.models.record import Record
from bagels.models.split import Split
from bagels.models.person import Person
from bagels.models.category import Category, Nature
from bagels.managers import utils
from bagels.config import CONFIG

# Test fixtures
@pytest.fixture(scope="function")
def engine():
    """Create a test-specific database engine."""
    return create_engine("sqlite:///:memory:")

@pytest.fixture(scope="function")
def setup_test_database(engine):
    """Create all tables in the test database."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def session(engine, setup_test_database):
    """Create a new session for a test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def test_data(session):
    """Create test accounts, categories, and people."""
    # Create test accounts
    account1 = Account(name="Account 1", beginningBalance=1000.0)
    account2 = Account(name="Account 2", beginningBalance=500.0)
    session.add_all([account1, account2])
    
    # Create a test category
    category = Category(name="Test Category", nature=Nature.NEED, color="#FF0000")
    session.add(category)
    
    # Create a test person
    person = Person(name="Test Person")
    session.add(person)
    
    session.commit()
    
    return {
        "account1": account1,
        "account2": account2,
        "category": category,
        "person": person
    }

# Test period calculations
@freeze_time("2024-02-15")  # Freeze time to February 15, 2024
def test_get_start_end_of_year():
    """Test year period calculations."""
    # Current year
    start, end = utils._get_start_end_of_year(0)
    assert start == datetime(2024, 1, 1, 0, 0, 0)
    assert end == datetime(2024, 12, 31, 23, 59, 59)
    
    # Previous year
    start, end = utils._get_start_end_of_year(-1)
    assert start == datetime(2023, 1, 1, 0, 0, 0)
    assert end == datetime(2023, 12, 31, 23, 59, 59)
    
    # Next year
    start, end = utils._get_start_end_of_year(1)
    assert start == datetime(2025, 1, 1, 0, 0, 0)
    assert end == datetime(2025, 12, 31, 23, 59, 59)

@freeze_time("2024-02-15")  # Freeze time to February 15, 2024
def test_get_start_end_of_month():
    """Test month period calculations."""
    # Current month
    
    start, end = utils._get_start_end_of_month(0)
    assert start == datetime(2024, 2, 1, 0, 0, 0)
    assert end == datetime(2024, 2, 29, 23, 59, 59)  # 2024 is a leap year
    
    # Previous month
    start, end = utils._get_start_end_of_month(-1)
    assert start == datetime(2024, 1, 1, 0, 0, 0)
    assert end == datetime(2024, 1, 31, 23, 59, 59)
    
    # Next month
    start, end = utils._get_start_end_of_month(1)
    assert start == datetime(2024, 3, 1, 0, 0, 0)
    assert end == datetime(2024, 3, 31, 23, 59, 59)

@freeze_time("2024-02-15")  # Freeze time to February 15, 2024
def test_get_start_end_of_week():
    """Test week period calculations."""
    # Set first day of week to Monday (0)
    CONFIG.defaults.first_day_of_week = 0

    
    # Current week
    start, end = utils._get_start_end_of_week(0)
    assert start == datetime(2024, 2, 12, 0, 0, 0)  # Monday
    assert end == datetime(2024, 2, 18, 23, 59, 59)  # Sunday
    
    # Previous week
    start, end = utils._get_start_end_of_week(-1)
    assert start == datetime(2024, 2, 5, 0, 0, 0)
    assert end == datetime(2024, 2, 11, 23, 59, 59)
    
    # Next week
    start, end = utils._get_start_end_of_week(1)
    assert start == datetime(2024, 2, 19, 0, 0, 0)
    assert end == datetime(2024, 2, 25, 23, 59, 59)

@freeze_time("2024-02-15")  # Freeze time to February 15, 2024
def test_get_start_end_of_day():
    """Test day period calculations."""
    # Current day
    start, end = utils._get_start_end_of_day(0)
    assert start == datetime(2024, 2, 15, 0, 0, 0)
    assert end == datetime(2024, 2, 15, 23, 59, 59)
    
    # Previous day
    start, end = utils._get_start_end_of_day(-1)
    assert start == datetime(2024, 2, 14, 0, 0, 0)
    assert end == datetime(2024, 2, 14, 23, 59, 59)
    
    # Next day
    start, end = utils._get_start_end_of_day(1)
    assert start == datetime(2024, 2, 16, 0, 0, 0)
    assert end == datetime(2024, 2, 16, 23, 59, 59)

@freeze_time("2024-02-15")  # Freeze time to February 15, 2024
def test_get_start_end_of_period():
    """Test generic period calculations."""
    # Test year
    start, end = utils.get_start_end_of_period(0, "year")
    assert start == datetime(2024, 1, 1, 0, 0, 0)
    assert end == datetime(2024, 12, 31, 23, 59, 59)
    
    # Test month
    start, end = utils.get_start_end_of_period(0, "month")
    assert start == datetime(2024, 2, 1, 0, 0, 0)
    assert end == datetime(2024, 2, 29, 23, 59, 59)
    
    # Test week
    CONFIG.defaults.first_day_of_week = 0
    start, end = utils.get_start_end_of_period(0, "week")
    assert start == datetime(2024, 2, 12, 0, 0, 0)
    assert end == datetime(2024, 2, 18, 23, 59, 59)
    
    # Test day
    start, end = utils.get_start_end_of_period(0, "day")
    assert start == datetime(2024, 2, 15, 0, 0, 0)
    assert end == datetime(2024, 2, 15, 23, 59, 59)

# Test figure calculations
@freeze_time("2024-02-15")
def test_get_period_figures(session, test_data):
    """Test period figure calculations."""
    # Create test records
    income_record = Record(
        label="Test Income",
        amount=200.0,
        accountId=test_data["account1"].id,
        categoryId=test_data["category"].id,
        isIncome=True,
        date=datetime(2024, 2, 15)
    )
    expense_record = Record(
        label="Test Expense",
        amount=150.0,
        accountId=test_data["account1"].id,
        categoryId=test_data["category"].id,
        isIncome=False,
        date=datetime(2024, 2, 15)
    )
    transfer_record = Record(
        label="Test Transfer",
        amount=300.0,
        accountId=test_data["account1"].id,
        isTransfer=True,
        transferToAccountId=test_data["account2"].id,
        date=datetime(2024, 2, 15)
    )
    split_record = Record(
        label="Test Split",
        amount=400.0,
        accountId=test_data["account1"].id,
        categoryId=test_data["category"].id,
        isIncome=False,
        date=datetime(2024, 2, 15)
    )
    session.add_all([income_record, expense_record, transfer_record, split_record])
    session.flush()
    
    # Create split
    split = Split(
        recordId=split_record.id,
        amount=200.0,
        personId=test_data["person"].id,
        isPaid=True,
        accountId=test_data["account1"].id,
        paidDate=datetime(2024, 2, 15)
    )
    session.add(split)
    session.commit()
    
    # Test income figures
    income = utils.get_period_figures(
        accountId=test_data["account1"].id,
        offset_type="month",
        offset=0,
        isIncome=True,
        session=session
    )
    assert income == 200.0  # Only the income record
    
    # Test expense figures
    expenses = utils.get_period_figures(
        accountId=test_data["account1"].id,
        offset_type="month",
        offset=0,
        isIncome=False,
        session=session
    )
    assert expenses == 350.0  # 150 (expense) + 200 (split expense after paid split)

# Test average calculations
def test_get_days_in_period():
    """Test days in period calculations."""
    with freeze_time("2024-02-15"):
        # Test month (February 2024 - leap year)
        days = utils._get_days_in_period(0, "month")
        assert days == 29
        
        # Test year
        days = utils._get_days_in_period(0, "year")
        assert days == 366  # 2024 is a leap year
        
        # Test week
        days = utils._get_days_in_period(0, "week")
        assert days == 7
        
        # Test day
        days = utils._get_days_in_period(0, "day")
        assert days == 1

def test_get_period_average():
    """Test period average calculations."""
    with freeze_time("2024-02-15"):
        # Test month average (February 2024)
        avg = utils.get_period_average(net=290, offset=0, offset_type="month")
        assert avg == 10.0  # 290 / 29 days
        
        # Test week average
        avg = utils.get_period_average(net=70, offset=0, offset_type="week")
        assert avg == 10.0  # 70 / 7 days
        
        # Test day average
        avg = utils.get_period_average(net=10, offset=0, offset_type="day")
        assert avg == 10.0  # 10 / 1 day
