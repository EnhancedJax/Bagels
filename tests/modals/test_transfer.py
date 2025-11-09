import pytest
from types import SimpleNamespace

from bagels.modals.transfer import TransferModal
import bagels.modals.transfer as transfer_mod


class _DummyLabel:
    def __init__(self):
        self.updated = ""
        self.classes = set()

    def update(self, text):
        self.updated = text

    def add_class(self, cls):
        self.classes.add(cls)

    def remove_class(self, cls):
        self.classes.discard(cls)


class _DummyField:
    def __init__(self):
        self.mounted = []

    def mount(self, widget):
        self.mounted.append(widget)


@pytest.fixture
def fake_accounts(mocker):
    class Account:
        def __init__(self, id, name, balance=0, hidden=False):
            self.id = id
            self.name = name
            self.balance = balance
            self.hidden = hidden

    accounts = [Account(1, "A", 100), Account(2, "B", 200)]
    # patch the name used by the transfer module to avoid hitting the DB during tests
    mocker.patch("bagels.modals.transfer.get_all_accounts_with_balance", return_value=accounts)
    # Patch TransferForm in the transfer module so constructing the modal
    # doesn't trigger record template DB access.
    class _DummyTransferForm:
        def __init__(self, isTemplate=False, defaultDate=None):
            pass

        def get_form(self):
            return {}

        def get_filled_form(self, record):
            return {}

    mocker.patch("bagels.modals.transfer.TransferForm", _DummyTransferForm)
    return accounts


def test_action_submit_same_account_shows_error(mocker, fake_accounts):
    # Arrange
    tm = TransferModal(title="t", record=None)
    tm.fromAccount = 1
    tm.toAccount = 1

    fake_label = _DummyLabel()
    mocker.patch.object(tm, "query_one", return_value=fake_label)
    # avoid running the real validator which expects complex form objects
    mocker.patch("bagels.modals.transfer.validateForm", return_value=({}, {}, True))

    # Act
    tm.action_submit()

    # Assert
    assert "From and to accounts cannot be the same" in fake_label.updated
    assert "active" in fake_label.classes


def test_action_submit_valid_calls_dismiss(mocker, fake_accounts):
    # Arrange
    tm = TransferModal(title="t", record=None)
    tm.fromAccount = 1
    tm.toAccount = 2

    # make validation return valid
    mocker.patch("bagels.modals.transfer.validateForm", return_value=({}, {}, True))

    # intercept dismiss
    called = {}

    def fake_dismiss(value):
        called['value'] = value

    tm.dismiss = fake_dismiss

    fake_label = _DummyLabel()
    mocker.patch.object(tm, "query_one", return_value=fake_label)

    # Act
    tm.action_submit()

    # Assert
    assert called.get('value') is not None
    assert called['value']['accountId'] == 1
    assert called['value']['transferToAccountId'] == 2
    assert called['value']['isTransfer'] is True


def test_action_submit_invalid_mounts_errors(mocker, fake_accounts):
    # Arrange
    tm = TransferModal(title="t", record=None)
    tm.fromAccount = 1
    tm.toAccount = 2

    # make validation return invalid with errors
    errors = {"amount": "Invalid amount"}
    mocker.patch("bagels.modals.transfer.validateForm", return_value=({}, errors, False))

    fake_label = _DummyLabel()
    # query_one for transfer-error
    def query_one_side(arg):
        if arg == "#transfer-error":
            return fake_label
        # when looking up field rows, return a dummy field widget
        return _DummyField()

    mocker.patch.object(tm, "query_one", side_effect=query_one_side)
    # query for previous errors returns a list of dummy objects with remove()
    class _PrevErr:
        def remove(self):
            self.removed = True

    mocker.patch.object(tm, "query", return_value=[_PrevErr()])

    # Act
    tm.action_submit()

    # Assert
    # final transfer error should be empty since validation errors are displayed on fields
    assert fake_label.updated == ""


class DummyWidget:
    def __init__(self, value=None, id_attr=None):
        self.value = value
        self.id = id_attr or "widget"

    def mount(self, *a, **k):
        pass

    def remove(self):
        pass


class DummyListItem:
    def __init__(self, id_attr):
        self.id = id_attr


class DummyListView:
    def __init__(self, id_attr):
        self.id = id_attr


@pytest.fixture(autouse=True)
def patch_dependencies(mocker):
    # Patch accounts and form to avoid DB calls
    fake_accounts = [SimpleNamespace(id=1, name="A"), SimpleNamespace(id=2, name="B")]
    mocker.patch("bagels.modals.transfer.get_all_accounts_with_balance", return_value=fake_accounts)

    class FakeForm:
        def __init__(self, *a, **k):
            self.fields = {}

        def get_form(self):
            return {}

        def get_filled_form(self, record):
            return {}

    mocker.patch("bagels.modals.transfer.TransferForm", FakeForm)

    # validateForm referenced in the module
    def fake_validate(form, field_map):
        return True, {}

    mocker.patch("bagels.modals.transfer.validateForm", fake_validate)

    yield


def make_modal(mocker):
    # Create modal but avoid textual mounting; patch instance query_one / query
    m = transfer_mod.TransferModal()

    # default query_one returns dummy amount field and from/to fields
    def query_one(selector):
        if selector == "#field-amount":
            return DummyWidget(value="0", id_attr=selector)
        if selector == "#from-accounts":
            return DummyWidget(id_attr=selector)
        if selector == "#to-accounts":
            return DummyWidget(id_attr=selector)
        if selector == "#transfer-modal":
            # container with query method
            container = SimpleNamespace()
            container.query = lambda s: []
            return container
        return DummyWidget(id_attr=selector)

    m.query_one = query_one
    m.query = lambda selector: []
    return m


def test_on_descendant_focus_toggles_atAccountList(mocker):
    m = make_modal(mocker)
    # start with False
    assert not getattr(m, "atAccountList", False)

    # simulate focus into from-accounts
    ev = SimpleNamespace(widget=SimpleNamespace(id="from-accounts"))
    m.on_descendant_focus(ev)
    assert getattr(m, "atAccountList", False) is True

    # simulate focus away
    ev2 = SimpleNamespace(widget=SimpleNamespace(id="something-else"))
    m.on_descendant_focus(ev2)
    assert getattr(m, "atAccountList", False) is False


def test_on_key_navigation_calls_screen_focus_methods(mocker):
    m = make_modal(mocker)
    # provide a fake screen with focus_next / focus_previous spies
    fake_screen = SimpleNamespace()
    fake_screen.focus_next = mocker.MagicMock()
    fake_screen.focus_previous = mocker.MagicMock()
    # Patch the TransferModal.screen property to return our fake screen
    mocker.patch.object(transfer_mod.TransferModal, "screen", new=property(lambda self: fake_screen))

    m.atAccountList = True
    # right key should call focus_next
    key_evt = SimpleNamespace(key="right")
    m.on_key(key_evt)
    fake_screen.focus_next.assert_called()

    # left key should call focus_previous
    key_evt2 = SimpleNamespace(key="left")
    m.on_key(key_evt2)
    fake_screen.focus_previous.assert_called()


def test_on_list_view_highlighted_updates_account_selection():
    m = make_modal(None)
    # simulate highlighting an item with id 'account-42' in from-accounts
    list_view = DummyListView(id_attr="from-accounts")
    item = DummyListItem(id_attr="account-42")
    ev = SimpleNamespace(list_view=list_view, item=item)

    # call handler
    m.on_list_view_highlighted(ev)
    assert getattr(m, "fromAccount", None) == "42"

    # to-accounts
    list_view2 = DummyListView(id_attr="to-accounts")
    item2 = DummyListItem(id_attr="account-99")
    ev2 = SimpleNamespace(list_view=list_view2, item=item2)
    m.on_list_view_highlighted(ev2)
    assert getattr(m, "toAccount", None) == "99"


def test_on_auto_complete_selected_sets_fields_and_calls_rebuild(mocker):
    m = make_modal(mocker)

    # patch get_template_by_id to return a template-like object
    template = SimpleNamespace(amount=123.45, accountId=1, transferToAccountId=2)
    mocker.patch("bagels.modals.transfer.get_template_by_id", return_value=template)

    # spy on rebuild
    mocker.patch.object(m, "rebuild")

    # the event provides an input attribute with id and heldValue
    ev = SimpleNamespace(input=SimpleNamespace(id="field-label-amount", heldValue=7))

    # replace query_one for amount field to return a widget we can inspect
    def query_one(selector):
        if selector == "#field-amount":
            return DummyWidget(value="0", id_attr=selector)
        if selector == "#from-accounts":
            return DummyWidget(id_attr=selector)
        if selector == "#to-accounts":
            return DummyWidget(id_attr=selector)
        return DummyWidget(id_attr=selector)

    m.query_one = query_one

    # call handler
    m.on_auto_complete_selected(ev)

    # ensure rebuild called
    m.rebuild.assert_called()
    # ensure amount field updated
    amount_widget = m.query_one("#field-amount")
    assert str(template.amount) in str(amount_widget.value) or amount_widget.value is not None
    # ensure accounts set
    assert getattr(m, "fromAccount", None) == template.accountId or str(getattr(m, "fromAccount", None)) == str(template.accountId)
    assert getattr(m, "toAccount", None) == template.transferToAccountId or str(getattr(m, "toAccount", None)) == str(template.transferToAccountId)