import importlib
from datetime import datetime
from types import SimpleNamespace

import pytest

from bagels import config as bagels_config

if bagels_config.CONFIG is None:
    bagels_config.CONFIG = bagels_config.Config.get_default()

table_builder = importlib.import_module(
    "bagels.components.modules.records._table_builder"
)


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    """Ensure CONFIG is available for the module under test."""
    monkeypatch.setattr(
        table_builder, "CONFIG", bagels_config.Config.get_default()
    )


@pytest.fixture
def builder():
    instance = table_builder.RecordTableBuilder()
    instance.show_splits = False
    instance.page_parent = SimpleNamespace(
        filter={"offset": 0, "offset_type": "month", "byAccount": False},
        mode={"accountId": {"default_value": 0}},
    )
    instance.FILTERS = {
        "enabled": lambda: False,
        "category": lambda: "",
        "amount": lambda: "",
        "label": lambda: "",
    }
    return instance


class TestRecordTableBuilderHelpers:
    @pytest.mark.parametrize(
        ("show_splits", "record_has_splits", "is_income", "expected"),
        [
            (False, True, True, "[green]=[/green]"),
            (False, True, False, "[red]=[/red]"),
            (True, False, True, "[green]+[/green]"),
            (True, False, False, "[red]-[/red]"),
        ],
    )
    def test_get_flow_icon_handles_modes(
        self, builder, show_splits, record_has_splits, is_income, expected
    ):
        builder.show_splits = show_splits
        assert (
            builder._get_flow_icon(record_has_splits, is_income) == expected
        )

    def test_format_record_fields_uses_self_amount_when_splits_hidden(
        self, builder, mocker
    ):
        builder.show_splits = False
        record = SimpleNamespace(
            isTransfer=False,
            category=SimpleNamespace(color="BLUE", name="Dining Out"),
            amount=100.0,
            splits=[object()],
            id=1,
            account=SimpleNamespace(name="Primary", hidden=False),
        )

        mocker.patch.object(
            table_builder, "get_record_total_split_amount", return_value=60.0
        )

        category_string, amount_string, account_string = (
            builder._format_record_fields(record, "FLOW")
        )

        assert amount_string == "FLOW 40.0"
        assert account_string == "Primary"
        assert "Dining Out" in category_string

    def test_format_record_fields_handles_transfers_with_hidden_accounts(
        self, builder
    ):
        builder.show_splits = True
        record = SimpleNamespace(
            isTransfer=True,
            account=SimpleNamespace(name="Hidden Source", hidden=True),
            transferToAccount=SimpleNamespace(name="Savings", hidden=False),
            amount=250.0,
        )

        category_string, amount_string, account_string = (
            builder._format_record_fields(record, "FLOW")
        )

        assert "[italic]Hidden Source[/italic]" in category_string
        assert "Savings" in category_string
        assert amount_string == 250.0
        assert account_string == "-"

    @pytest.mark.parametrize("is_paid", [True, False])
    def test_get_split_status_icon_reflects_payment_state(
        self, builder, is_paid
    ):
        split = SimpleNamespace(isPaid=is_paid)
        result = builder._get_split_status_icon(split)
        expected_symbol = (
            table_builder.CONFIG.symbols.split_paid
            if is_paid
            else table_builder.CONFIG.symbols.split_unpaid
        )
        assert expected_symbol in result

    def test_add_group_header_row_delegates_to_table(self, builder, mocker):
        table = mocker.MagicMock()
        builder._add_group_header_row(table, "Heading", key="k-1")
        table.add_row.assert_called_once_with(
            "//", "Heading", "", "", "", style_name="group-header", key="k-1"
        )

    def test_add_split_rows_appends_net_summary(self, builder, mocker):
        table = mocker.MagicMock()
        builder.show_splits = True
        split_one = SimpleNamespace(
            id=1,
            person=SimpleNamespace(name="Jordan"),
            amount=25.0,
            isPaid=False,
            account=SimpleNamespace(name="Wallet"),
            paidDate=None,
        )
        split_two = SimpleNamespace(
            id=2,
            person=SimpleNamespace(name="Alex"),
            amount=25.0,
            isPaid=True,
            account=None,
            paidDate=datetime.now(),
        )
        record = SimpleNamespace(
            id=11,
            amount=80.0,
            isIncome=False,
            category=SimpleNamespace(color="BLUE"),
            splits=[split_one, split_two],
        )

        mocker.patch.object(
            table_builder, "get_record_total_split_amount", return_value=50.0
        )
        mocker.patch.object(
            table_builder, "format_date_to_readable", return_value="2025-01-01"
        )

        builder._add_split_rows(table, record, "[green]+[/green]")

        # Called for each split plus the summary line
        assert table.add_row.call_count == 3
        summary_call = table.add_row.call_args_list[-1]
        assert summary_call.kwargs.get("style_name") == "net"
