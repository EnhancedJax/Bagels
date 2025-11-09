# Testing Guide

This repository relies on `pytest` and the [`uv`](https://github.com/astral-sh/uv) toolchain for managing virtual environments. The sections below outline how to install dependencies, run the full suite, execute focused subsets, and add new tests that match the project's standards.

## 1. Environment Setup

1. Ensure you have Python 3.13+ available on your path.
2. Install project dependencies with uv:
   ```bash
   uv sync
   ```
   This command reads `pyproject.toml` and `uv.lock`, creating the `.venv/` virtual environment with all runtime and development packages (including `pytest`, `pytest-mock`, snapshot tooling, and linting utilities).

If you add or upgrade dependencies, regenerate the lockfile with:
```bash
uv lock
```

## 2. Running Tests

### Full Suite

Run every test, including snapshot comparisons and Textual UI checks:
```bash
uv run pytest
```

### Targeted Runs

- Specific file: `uv run pytest tests/managers/test_splits.py`
- Single test node: `uv run pytest tests/components/modules/test_people.py::TestPeopleModule::test_action_edit_person_updates_successfully`
- With coverage: `uv run pytest --cov=bagels --cov-report=term-missing`

Passing `-k "<expression>"` lets you filter by substring (e.g., `-k "split and not delete"`).

## 3. Writing Tests

When extending the suite:

- **Structure**: Group related tests inside classes and keep helper functions private to the file. Co-locate fixtures near the tests that use them.
- **Parametrization**: Prefer `@pytest.mark.parametrize` for exercising multiple scenarios in a single test body. This keeps assertions DRY and ensures edge cases stay visible.
- **Mocking**: Use the `mocker` fixture from `pytest-mock` for patching collaborators. Spy on existing functions when you want call verification and rely on `MagicMock` for simulating external dependencies.
- **Edge Cases**: Include failure paths (exceptions, empty responses, missing records) alongside the happy path.
- **Snapshot & UI Tests**: For Textual components, rely on the existing snapshot helpers or slim `SimpleNamespace` fakes to avoid heavy UI bootstrapping.

Follow the existing naming convention (`test_<unit>.py`) and keep files under `tests/`.

## 4. Continuous Integration Expectations

- New tests must pass with `uv run pytest` before a pull request is opened.
- Update `pyproject.toml` and `uv.lock` when introducing additional dependencies.
- Keep commit messages descriptive so reviewers understand why changes were made (e.g., “Add CRUD coverage tests for split manager”).

## 5. Troubleshooting

- **Virtual environment issues**: Remove `.venv/` and re-run `uv sync`.
- **Snapshot diffs**: Accept new baselines only after verifying the textual output manually.
- **Textual warnings**: These often stem from missing `CONFIG`. Import `bagels.config` and use `Config.get_default()` in tests to seed defaults without reading user config files.

By following this workflow, your tests will integrate cleanly with the project’s automation and provide clear coverage of success, error, and edge scenarios.
