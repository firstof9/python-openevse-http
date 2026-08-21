---
name: openevse-dev-workflow
description: >-
  Use this skill when running tests, formatting code, checking linters,
  running type checks, or managing tox environments in python-openevse-http.
---

# OpenEVSE Development & Testing Workflow

This skill guides you through executing tests, linting, formatting, and type checks within the `python-openevse-http` repository.

## Environment & Tooling

The project uses `tox` for managing isolated virtual environments and running test tools (`pytest`, `ruff`, `mypy`).

### 1. Running Unit Tests

Run full test suite via tox:
```bash
tox -e py314
```

To run fast targeted test runs with the existing tox environment:
```bash
# Run all tests
.tox/py314/bin/pytest

# Run a specific test file
.tox/py314/bin/pytest tests/test_commands.py

# Run a single test function
.tox/py314/bin/pytest tests/test_commands.py -k "test_toggle_override"

# Run with verbose output and stdout
.tox/py314/bin/pytest -v -s tests/test_client.py
```

### 2. Formatting & Linting (Ruff)

Check formatting and linting:
```bash
tox -e lint
```

To auto-format or auto-fix lint errors:
```bash
# Format code
.tox/lint/bin/ruff format ./

# Auto-fix linting issues
.tox/lint/bin/ruff check --fix openevsehttp tests
```

### 3. Type Checking (Mypy)

Run static type checks:
```bash
tox -e mypy
```
Or directly:
```bash
.tox/mypy/bin/mypy openevsehttp
```

### 4. Running All CI Checks Together

Before submitting PRs or finalizing tasks, verify everything in one step:
```bash
tox -e py314,lint,mypy
```

### 5. Pre-commit Hooks

Pre-commit hooks are configured via `.pre-commit-config.yaml`. They run automatically on `git commit`, or you can trigger them manually:
```bash
pre-commit run --all-files
```

### 6. Pull Requests & Issue Creation

- **Pull Requests**:
  - Always use the template in [`.github/pull_request_template.md`](../../.github/pull_request_template.md).
  - Include a summary, issue link (`Fixes #<number>`), type of change, and completed checklist.
  - Follow conventional commits in PR titles (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- **Issues & Feature Requests**:
  - Use [`.github/ISSUE_TEMPLATE/bug_report.yml`](../../.github/ISSUE_TEMPLATE/bug_report.yml) for bugs (`[Bug]: <summary>`).
  - Use [`.github/ISSUE_TEMPLATE/feature_request.yml`](../../.github/ISSUE_TEMPLATE/feature_request.yml) for feature requests (`[Feature Request]: <summary>`).
