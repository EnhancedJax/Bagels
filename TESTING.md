# Bagels Testing Guide

## Overview

This document explains how to run the tests for the Bagels project, what files were created or modified for testing, and summarizes coverage and known issues. The tests were written by wagscoll and svanalex.
These tests were developed as part of a project for CS4499.

## Running the Tests

### Step 1:

* Activate virtual environment

```
source .venv/bin/activate
```

### Step 2:

* Run pytest

```
uv run pytest
```

**Note: testpaths[] within pyproject.toml has been modified to only run the tests Alex and I have written.*

## Files Modified

The file '/managers/utils/valdiaton.py' has been modified to improve error handling and validation clarity throughout the Bagels project.
Both exceptions are used in validation helper functions:

* _validate_number()
* _validate_date()
* _validate_autocomplete()
* validateForm()

Each function uses try/except blocks to catch these exceptions and populate an errors dictionary — ensuring the user gets meaningful error messages without crashing the application.

**Example:**

```
except (InvalidFormDataException, AutocompleteOptionMismatchException) as e:
    errors[fieldKey] = str(e)
    isValid = False
```

### InvalidFormDataException

**Purpose:**

> Raised when a form field contains invalid or inconsistent data such as:

* Missing required fields
* Numeric values outside allowed min/max bounds
* Incorrect date formats

**Example:**

```
if not value and field.is_required:
    raise InvalidFormDataException(f"Field '{field.key}' is required")

if field.min is not None and num_val <= field.min:
    raise InvalidFormDataException(f"Value must be greater than {field.min}")
```

**Usefulness:**
It replaces generic ValueError exceptions with a clear, domain-specific error type that tells the user why a form input failed.

### AutocompleteOptionMismatchException

**Purpose:**
Raised when a user’s input doesn’t match any of the allowed autocomplete options — either because the selection wasn’t tab-confirmed, or because it’s missing entirely.

**Example Usage:**

```
if not field.options or not field.options.items:
    return True, None

if not matching_items:
    raise AutocompleteOptionMismatchException(f"Invalid selection for field '{field.key}'")
```

**Usefulness:**
This exception provides a precise mechanism to handle invalid dropdown/autocomplete entries instead of failing silently or producing unclear errors.

## Files Tested

The following files have been added and tested:

* tests/test_config.py
* tests/utils/test_validation.py
* tests/components/modules/test_incomemode.py
* tests/managers/test_person.py
* tests/modules/test_accountmode.py
* tests/modules/test_people.py

## Notable Coverage

* `components/modules/incomemode.py`: 96%

* `components/modules/people.py`: 87%

* `utils/validation.py`: 84%

* `config.py`: 69%

* `managers/persons.py`: 69%

* Total statements: 3,375

* Statements covered: 1,030

* Overall coverage: 31%
