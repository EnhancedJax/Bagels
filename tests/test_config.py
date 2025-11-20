import pytest
from unittest.mock import patch, mock_open
from bagels.config import Config, CONFIG, write_state, ConfigurationError
import bagels.config as config_module


def test_default_config_creation():
    """Ensure get_default() returns a valid Config object with defaults."""
    config = Config.get_default()
    assert config.defaults.period == "week"
    assert config.state.theme == "tokyo-night"


@patch("builtins.open", new_callable=mock_open, read_data="{}")
def test_load_yaml_config(mock_file):
    """_load_yaml_config should read YAML and return a dict."""
    cfg = Config()
    data = cfg._load_yaml_config()
    assert isinstance(data, dict)
    assert mock_file.called


@patch("builtins.open", new_callable=mock_open)
def test_write_state(mock_file):
    config_module.CONFIG = config_module.Config.get_default()
    config_module.write_state("footer_visibility", False)
    mock_file.assert_called()


@patch("builtins.open", new_callable=mock_open)
def test_write_state_file_error(mock_file):
    """Simulate write failure and ensure IOError is raised."""
    mock_file.side_effect = IOError("Cannot write")
    with pytest.raises(IOError):
        write_state("state.footer_visibility", True)


def test_write_state_nested_key():
    config_module.CONFIG = config_module.Config.get_default()
    config_module.write_state("budgeting.savings_percentage", 0.5)
    assert config_module.CONFIG.state.budgeting.savings_percentage == 0.5


@patch("builtins.open", new_callable=mock_open)
def test_ensure_yaml_fields_creates_missing_keys(mock_file):
    """ensure_yaml_fields should create YAML file if missing fields."""
    cfg = Config.get_default()
    cfg.ensure_yaml_fields()
    mock_file.assert_called()
