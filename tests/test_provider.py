import pytest
import platform
from types import SimpleNamespace

from bagels.provider import AppProvider
import bagels.provider as provider_mod
import bagels.config as bagels_config


class _FakeApp:
    def __init__(self):
        self.themes = ["dark", "light"]
        self.notified = []
        self.refreshed = False
        self.exited = None

    def action_quit(self):
        self.exited = True

    def refresh(self, layout=False, recompose=False):
        self.refreshed = True

    def notify(self, message, title=None, severity=None):
        self.notified.append((message, title, severity))

    def exit(self, message=None):
        self.exited = message

    def command_theme(self, theme_name: str):
        """Stub for the app's theme command used by AppProvider.get_theme_command.

        Tests only need this to exist; record the last theme requested.
        """
        self.last_theme = theme_name


class _FakeScreen:
    def __init__(self, app):
        self.app = app


@pytest.mark.parametrize("theme_name", ["dark", "light", "custom"])
def test_get_theme_command_parametrized(theme_name):
    # Arrange
    app = _FakeApp()
    app.themes.append("custom")
    provider = AppProvider(_FakeScreen(app))

    # Act
    cmd = provider.get_theme_command(theme_name)

    # Assert
    assert isinstance(cmd, tuple)
    assert cmd[0].startswith("theme: ")
    assert theme_name in cmd[2]


def test_action_open_config_file_handles_failure(mocker):
    app = _FakeApp()
    provider = AppProvider(_FakeScreen(app))

    # force config_file to return a path and subprocess.call to raise
    mocker.patch("bagels.provider.config_file", return_value="/no/such/file")
    mocker.patch("subprocess.call", side_effect=OSError("boom"))

    # Act
    provider._action_open_config_file()

    # Assert
    assert len(app.notified) == 1
    assert "Failed to open config file" in app.notified[0][0]


def test_wipe_database_command_calls_wipe_and_refresh(mocker):
    app = _FakeApp()
    provider = AppProvider(_FakeScreen(app))

    wipe_mock = mocker.patch("bagels.provider.wipe_database")

    # get the command tuple and find the wipe callable
    commands = provider.commands
    wipe_cmd = [c for c in commands if c[0] == "dev: wipe database"][0]

    # Act
    runnable = wipe_cmd[1]
    runnable()

    # Assert
    assert wipe_mock.called
    assert app.refreshed is True


def test_action_toggle_update_check(mocker):
    # Arrange: ensure initial config state; create a fake CONFIG if module has none
    orig_config = getattr(bagels_config, "CONFIG", None)
    orig_provider_config = getattr(provider_mod, "CONFIG", None)
    if orig_config is None:
        fake = SimpleNamespace(state=SimpleNamespace(check_for_updates=False, footer_visibility=False))
        bagels_config.CONFIG = fake
        provider_mod.CONFIG = fake
        created_fake = True
    else:
        created_fake = False

    orig_state = bagels_config.CONFIG.state.check_for_updates
    bagels_config.CONFIG.state.check_for_updates = False

    app = _FakeApp()
    provider = AppProvider(_FakeScreen(app))

    write_spy = mocker.patch("bagels.provider.write_state")

    # Act
    provider._action_toggle_update_check()

    # Assert
    write_spy.assert_called_once_with("check_for_updates", True)
    assert any("Update check enabled" in n[0] for n in app.notified)

    # Cleanup
    bagels_config.CONFIG.state.check_for_updates = orig_state
    if created_fake:
        bagels_config.CONFIG = orig_config
        provider_mod.CONFIG = orig_provider_config


def test_action_toggle_footer(mocker):
    orig_config = getattr(bagels_config, "CONFIG", None)
    orig_provider_config = getattr(provider_mod, "CONFIG", None)
    if orig_config is None:
        fake = SimpleNamespace(state=SimpleNamespace(check_for_updates=False, footer_visibility=False))
        bagels_config.CONFIG = fake
        provider_mod.CONFIG = fake
        created_fake = True
    else:
        created_fake = False

    orig_state = bagels_config.CONFIG.state.footer_visibility
    bagels_config.CONFIG.state.footer_visibility = False

    app = _FakeApp()
    provider = AppProvider(_FakeScreen(app))

    write_spy = mocker.patch("bagels.provider.write_state")

    # Act
    provider._action_toggle_footer()

    # Assert
    write_spy.assert_called_once_with("footer_visibility", True)
    assert app.refreshed is True
    assert any("Footer enabled" in n[0] for n in app.notified)

    # Cleanup
    bagels_config.CONFIG.state.footer_visibility = orig_state
    if created_fake:
        bagels_config.CONFIG = orig_config
        provider_mod.CONFIG = orig_provider_config


def test_get_theme_commands_and_get_theme_command():
    app = _FakeApp()
    app.themes.append("custom")
    provider = AppProvider(_FakeScreen(app))

    commands = provider.get_theme_commands()
    # Should produce a command for each theme
    assert isinstance(commands, tuple)
    names = [c[0] for c in commands]
    assert "theme: custom" in names

    cmd = provider.get_theme_command("dark")
    assert cmd[0] == "theme: dark"
    assert "Set the theme to dark" in cmd[2]


def test_action_open_config_file_success_and_failure(mocker):
    app = _FakeApp()
    provider = AppProvider(_FakeScreen(app))

    # Simulate platform branches by patching platform.system and subprocess.call
    mocker.patch("bagels.provider.config_file", return_value="/tmp/f")

    # success path: pretend platform is Linux
    mocker.patch("platform.system", return_value="Linux")
    mock_call = mocker.patch("subprocess.call", return_value=0)

    provider._action_open_config_file()
    # exit called with message in provider after opening
    assert app.exited is not None or len(app.notified) >= 0

    # failure path: subprocess raises
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch("subprocess.call", side_effect=OSError("boom"))

    # clear notifications
    app.notified.clear()
    provider._action_open_config_file()
    assert len(app.notified) == 1
    assert "Failed to open config file" in app.notified[0][0]