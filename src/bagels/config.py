import warnings
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings
from bagels.locations import config_file


class Defaults(BaseModel):
    period: Literal["day", "week", "month", "year"] = "week"
    first_day_of_week: int = Field(ge=0, le=6, default=6)
    date_format: str = "%d/%m"
    round_decimals: int = 2


class DatemodeHotkeys(BaseModel):
    go_to_day: str = "g"


class HomeHotkeys(BaseModel):
    categories: str = "c"
    budgets: str = "b"
    new_transfer: str = "t"
    toggle_splits: str = "s"
    display_by_date: str = "q"
    display_by_person: str = "w"
    cycle_offset_type: str = "."
    toggle_income_mode: str = "/"
    select_prev_account: str = "["
    select_next_account: str = "]"
    toggle_use_account: str = "\\"
    datemode: DatemodeHotkeys = DatemodeHotkeys()


class RecordModalHotkeys(BaseModel):
    new_split: str = "ctrl+a"
    new_paid_split: str = "ctrl+s"
    delete_last_split: str = "ctrl+d"


class CategoriesHotkeys(BaseModel):
    new_subcategory: str = "s"
    browse_defaults: str = "b"


class Hotkeys(BaseModel):
    new: str = "a"
    delete: str = "d"
    edit: str = "e"
    toggle_jump_mode: str = "v"
    home: HomeHotkeys = HomeHotkeys()
    record_modal: RecordModalHotkeys = RecordModalHotkeys()
    categories: CategoriesHotkeys = CategoriesHotkeys()


class Symbols(BaseModel):
    line_char: str = "│"
    finish_line_char: str = "╰"
    split_paid: str = "✓"
    split_unpaid: str = "⨯"
    category_color: str = "●"
    amount_positive: str = "+"
    amount_negative: str = "-"


class State(BaseModel):
    theme: str = "dark"


class Config(YamlBaseSettings):
    hotkeys: Hotkeys = Hotkeys()
    symbols: Symbols = Symbols()
    defaults: Defaults = Defaults()
    state: State = State()
    model_config = SettingsConfigDict(
        yaml_file=str(config_file()),
        yaml_file_encoding="utf-8",
    )

    def __init__(self, **data):
        super().__init__(**data)
        self.ensure_yaml_fields()

    def ensure_yaml_fields(self):
        # Load current config or create a new one if it doesn't exist
        try:
            with open(config_file(), "r") as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            config = {}

        # Update config with default values for missing fields
        def update_config(default, current):
            for key, value in default.items():
                if isinstance(value, dict):
                    current[key] = update_config(value, current.get(key, {}))
                elif key not in current:
                    current[key] = value
            return current

        default_config = self.model_dump()
        config = update_config(default_config, config)

        # Write back to the YAML file
        with open(config_file(), "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    @classmethod
    def get_default(cls):
        # Create a default instance without reading from file
        return cls.model_construct(
            hotkeys=Hotkeys(), symbols=Symbols(), defaults=Defaults(), state=State()
        )


CONFIG = Config()


def load_config():
    f = config_file()
    if not f.exists():
        try:
            f.touch()
            with open(f, "w") as f:
                yaml.dump(Config.get_default().model_dump(), f)
        except OSError:
            pass

    global CONFIG
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        CONFIG = Config()  # ignore warnings about empty env file


def write_state(key: str, value: Any) -> None:
    """Write a state value to the config.yaml file."""
    try:
        with open(config_file(), "r") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}

    if "state" not in config:
        config["state"] = {}
    config["state"][key] = value

    with open(config_file(), "w") as f:
        yaml.dump(config, f, default_flow_style=False)
