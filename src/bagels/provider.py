import platform
import subprocess
from functools import partial
from typing import TYPE_CHECKING, cast

from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.types import IgnoreReturnCallbackType

from bagels.config import CONFIG, write_state
from bagels.currencies import get_currency_items
from bagels.locations import config_file
from bagels.managers.accounts import get_all_accounts
from bagels.managers.currency import warm_rates_for_currencies
from bagels.managers.samples import create_sample_entries
from bagels.models.database.app import wipe_database

if TYPE_CHECKING:
    from bagels.app import App


class AppProvider(Provider):
    @property
    def commands(
        self,
    ) -> tuple[tuple[str, IgnoreReturnCallbackType, str, bool], ...]:
        app = self.app

        commands_to_show: list[tuple[str, IgnoreReturnCallbackType, str, bool]] = [
            ("app: quit", app.action_quit, "Quit App", True),
            (
                "config: toggle update check",
                self._action_toggle_update_check,
                "Toggle update check on startup",
                True,
            ),
            (
                "config: toggle footer",
                self._action_toggle_footer,
                "Toggle the footer and hide hotkey hints",
                True,
            ),
            (
                "config: open config file",
                self._action_open_config_file,
                "Open the config file in the default editor",
                True,
            ),
            (
                "config: refresh exchange rates",
                self._action_refresh_exchange_rates,
                "Fetch and cache latest exchange rates for all account currencies",
                True,
            ),
            (
                "dev: create sample entries",
                self._action_create_sample_entries,
                "Create sample entries defined in static/sample_entries.yaml",
                False,
            ),
            (
                "dev: wipe database",
                self._action_wipe_database,
                "Delete everything from the database",
                False,
            ),
            *self.get_theme_commands(),
            *self.get_currency_commands(),
        ]

        return tuple(commands_to_show)

    async def discover(self) -> Hits:
        """Handle a request for the discovery commands for this provider.

        Yields:
            Commands that can be discovered.
        """
        for name, runnable, help_text, show_discovery in self.commands:
            if show_discovery:
                yield DiscoveryHit(
                    name,
                    runnable,
                    help=help_text,
                )

    async def search(self, query: str) -> Hits:
        """Handle a request to search for commands that match the query.

        Args:
            query: The user input to be matched.

        Yields:
            Command hits for use in the command palette.
        """
        matcher = self.matcher(query)
        for name, runnable, help_text, _ in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(name),
                    runnable,
                    help=help_text,
                )

    def get_theme_commands(
        self,
    ) -> tuple[tuple[str, IgnoreReturnCallbackType, str, bool], ...]:
        app = self.app
        return tuple(self.get_theme_command(theme) for theme in app.themes)

    def get_theme_command(
        self, theme_name: str
    ) -> tuple[str, IgnoreReturnCallbackType, str, bool]:
        return (
            f"theme: {theme_name}",
            partial(self.app.command_theme, theme_name),
            f"Set the theme to {theme_name}",
            True,
        )

    def get_currency_commands(
        self,
    ) -> tuple[tuple[str, IgnoreReturnCallbackType, str, bool], ...]:
        return tuple(self.get_currency_command(code) for code, _ in get_currency_items())

    def get_currency_command(
        self, currency_code: str
    ) -> tuple[str, IgnoreReturnCallbackType, str, bool]:
        return (
            f"currency: set main {currency_code}",
            partial(self._action_set_main_currency, currency_code),
            f"Set main currency to {currency_code}",
            True,
        )

    @property
    def app(self) -> "App":
        return cast("App", self.screen.app)

    def _action_create_sample_entries(self) -> None:
        create_sample_entries()
        self.app.refresh(layout=True, recompose=True)

    def _action_wipe_database(self) -> None:
        wipe_database()
        self.app.refresh(layout=True, recompose=True)

        # def check_delete(result) -> None:

        # self.app.push_screen(
        #     ConfirmationModal(
        #         message="Are you sure you want to wipe the database?",
        #     ),
        #     callback=check_delete,
        # )

    def _action_toggle_update_check(self) -> None:
        cur = CONFIG.state.check_for_updates
        write_state("check_for_updates", not cur)
        self.app.notify(
            f"Update check {'enabled' if not cur else 'disabled'} on startup"
        )

    def _action_open_config_file(self) -> None:
        try:
            file = config_file()
            if platform.system() == "Darwin":  # macOS
                subprocess.call(("open", file))
            elif platform.system() == "Windows":  # Windows
                subprocess.call(("start", file), shell=True)
            else:  # Linux and other Unix-like systems
                subprocess.call(("xdg-open", file))
            self.app.exit(message="Opened config file in default editor!")
        except Exception as e:
            self.app.notify(
                f"Failed to open config file: {e}", title="Error", severity="error"
            )

    def _action_toggle_footer(self) -> None:
        cur = CONFIG.state.footer_visibility
        write_state("footer_visibility", not cur)
        self.app.refresh(layout=True, recompose=True)
        self.app.notify(f"Footer {'enabled' if not cur else 'disabled'}")

    def _action_set_main_currency(self, currency_code: str) -> None:
        write_state("currency.main_currency", currency_code)
        self.app.refresh(layout=True, recompose=True)
        self.app.notify(f"Main currency set to {currency_code}")

    def _action_refresh_exchange_rates(self) -> None:
        accounts = get_all_accounts(get_hidden=True)
        warm_rates_for_currencies(
            currencies=[getattr(account, "currencyCode", None) for account in accounts],
            target_currency=CONFIG.state.currency.main_currency,
        )
        self.app.notify("Exchange rates refreshed", timeout=2)
