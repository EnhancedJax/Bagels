import warnings
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field
from bagels.locations import config_file
from pathlib import Path


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
    check_for_updates: bool = True


class Config(BaseModel):
    hotkeys: Hotkeys = Hotkeys()
    symbols: Symbols = Symbols()
    defaults: Defaults = Defaults()
    state: State = State()

    def __init__(self, **data):
        config_data = self._load_yaml_config()
        merged_data = {**self.model_dump(), **config_data, **data}
        super().__init__(**merged_data)
        self.ensure_yaml_fields()

    def _load_yaml_config(self) -> dict[str, Any]:
        config_path = config_file()
        if not config_path.is_file():
            return {}

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                return config if isinstance(config, dict) else {}
        except Exception as e:
            warnings.warn(f"Error loading config file: {e}")
            return {}

    def ensure_yaml_fields(self):
        try:
            with open(config_file(), "r") as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            config = {}

        def update_config(default, current):
            for key, value in default.items():
                if isinstance(value, dict):
                    current[key] = update_config(value, current.get(key, {}))
                elif key not in current:
                    current[key] = value
            return current

        default_config = self.model_dump()
        config = update_config(default_config, config)

        with open(config_file(), "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    @classmethod
    def get_default(cls):
        return cls(
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

    # update the global config object
    global CONFIG
    setattr(CONFIG.state, key, value)
