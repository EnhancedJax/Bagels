import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bagels.models.database.db import Base
from bagels.managers import persons
from unittest.mock import MagicMock


@pytest.fixture(scope="function")
def test_db():
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")

    # Create all tables
    Base.metadata.create_all(engine)

    # Create a new session factory bound to the engine
    persons.Session = sessionmaker(bind=engine)

    yield engine

    # Clean up
    Base.metadata.drop_all(engine)


# updating test to use parameterized testing
@pytest.mark.parametrize(
    "person_data",
    [{"name": "John Doe"}, {"name": "Jane Smith"}, {"name": ""}],
    ids=["normal name", "another normal name", "empty name"],
)
def test_create_person(test_db, person_data):
    # Test data
    # person_data = {"name": "John Doe"}

    # Create person
    new_person = persons.create_person(person_data)

    # Assertions
    assert new_person is not None
    assert new_person.name == person_data["name"]
    assert new_person.id is not None
    assert new_person.createdAt is not None
    assert new_person.updatedAt is not None


def test_get_all_persons(test_db):
    # Create test data
    person_data1 = {"name": "John Doe"}
    person_data2 = {"name": "Jane Smith"}

    persons.create_person(person_data1)
    persons.create_person(person_data2)

    # Get all persons
    all_persons = persons.get_all_persons()

    # Assertions
    assert len(all_persons) == 2
    assert any(p.name == "John Doe" for p in all_persons)
    assert any(p.name == "Jane Smith" for p in all_persons)


# Mock object test for get_all_persons
def test_get_all_persons_returns_mocked_data(mocker):
    mock_session = mocker.MagicMock()
    mock_persons = [persons.Person(name="John Doe"), persons.Person(name="Jane Smith")]

    mocker.patch("bagels.managers.persons.Session", return_value=mock_session)
    mock_session.scalars.return_value.all.return_value = mock_persons

    result = persons.get_all_persons()

    assert result == mock_persons
    mock_session.scalars.assert_called_once()
    mock_session.close.assert_called_once()


# parameterized test for get_all_persons
@pytest.mark.parametrize(
    "people",
    [
        [{"name": "John Doe"}],
        [{"name": "John Doe"}, {"name": "Jane Smith"}],
        [{"name": "John Doe"}, {"name": "Jane Smith"}, {"name": "Foo Bar"}],
        [{"name": ""}],
    ],
    ids=["one person", "two persons", "three persons", "empty name"],
)
def test_get_all_persons_param(test_db, people):
    for p in people:
        if p["name"]:
            persons.create_person(p)

    all_persons = persons.get_all_persons()
    expected_length = len([p for p in people if p["name"]])
    assert len(all_persons) == expected_length


def test_get_person_by_id(test_db):
    # Create test data
    person_data = {"name": "John Doe"}
    new_person = persons.create_person(person_data)

    # Get person by ID
    retrieved_person = persons.get_person_by_id(new_person.id)

    # Assertions
    assert retrieved_person is not None
    assert retrieved_person.id == new_person.id
    assert retrieved_person.name == "John Doe"


def test_get_nonexistent_person(test_db):
    # Try to get a person with non-existent ID
    retrieved_person = persons.get_person_by_id(999)

    # Assertions
    assert retrieved_person is None


# parameterized version of get_person_by_id tests
@pytest.mark.parametrize(
    "person_data, lookup_id, should_exist",
    [
        ({"name": "John Doe"}, 1, True),
        ({"name": "Jane Smith"}, 2, True),
        ({"name": "Foo Bar"}, 999, False),
    ],
    ids=["existing id 1", "existing id 2", "non-existent id"],
)
def test_get_person_by_id(test_db, person_data, lookup_id, should_exist):
    # Create some persons to ensure IDs 1 and 2 exist
    created_people = []
    created_people.append(persons.create_person({"name": "John Doe"}))
    created_people.append(persons.create_person({"name": "Jane Smith"}))

    retrieved_person = persons.get_person_by_id(lookup_id)

    if should_exist:
        assert retrieved_person is not None
        expected_person = next(p for p in created_people if p.id == lookup_id)
        assert retrieved_person.id == expected_person.id
        assert retrieved_person.name == expected_person.name
    else:
        assert retrieved_person is None


def test_update_person(test_db):
    # Create test data
    person_data = {"name": "John Doe"}
    new_person = persons.create_person(person_data)

    # Update data
    update_data = {"name": "John Smith"}
    updated_person = persons.update_person(new_person.id, update_data)

    # Assertions
    assert updated_person is not None
    assert updated_person.name == "John Smith"
    assert updated_person.id == new_person.id


def test_update_nonexistent_person(test_db):
    # Try to update non-existent person
    update_data = {"name": "John Smith"}
    updated_person = persons.update_person(999, update_data)

    # Assertions
    assert updated_person is None


# parameterized/mocked test for update_person
@pytest.mark.parametrize(
    "initial_name, update_data, expected_name",
    [
        ("John Doe", {"name": "John Smith"}, "John Smith"),
        ("Jane Doe", {"name": "Jane Smith"}, "Jane Smith"),
        ("Foo Bar", {"name": ""}, ""),  # Edge case: empty name
    ],
    ids=["update to John Smith", "update to Jane Smith", "update to empty name"],
)
def test_update_person_param_mocked(mocker, initial_name, update_data, expected_name):
    mock_session = mocker.MagicMock()
    mock_person = MagicMock()
    mock_person.id = 1
    mock_person.name = initial_name
    mock_session.get.return_value = mock_person

    mocker.patch("bagels.managers.persons.Session", return_value=mock_session)

    updated_person = persons.update_person(1, update_data)

    assert updated_person.name == expected_name
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


def test_delete_person(test_db):
    # Create test data
    person_data = {"name": "John Doe"}
    new_person = persons.create_person(person_data)

    # Delete person
    result = persons.delete_person(new_person.id)

    # Assertions
    assert result is True
    assert persons.get_person_by_id(new_person.id) is None


def test_delete_nonexistent_person(test_db):
    # Try to delete non-existent person
    result = persons.delete_person(999)

    # Assertions
    assert result is False


# parameterized/mocked test for delete_person
@pytest.mark.parametrize(
    "has_splits, expected_result",
    [
        (True, True),  # Person has splits, should soft delete
        (False, True),  # Person has no splits, should hard delete
    ],
    ids=["soft delete", "hard delete"],
)
def test_delete_person_param_mocked(mocker, has_splits, expected_result):
    mock_session = mocker.MagicMock()
    mock_person = MagicMock()
    mock_session.get.return_value = mock_person

    # Mock the split check
    if has_splits:
        mock_session.query.return_value.filter.return_value.first.return_value = True
    else:
        mock_session.query.return_value.filter.return_value.first.return_value = None

    mocker.patch("bagels.managers.persons.Session", return_value=mock_session)

    result = persons.delete_person(1)

    assert result == expected_result
    mock_session.close.assert_called_once()
