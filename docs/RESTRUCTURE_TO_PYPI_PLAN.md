# Plan: Restructure Project to PyPI Package Standards

This document outlines the step-by-step plan to restructure `leetcode-notes-generator` into a standard, distribution-ready Python package suitable for publishing to PyPI and installing via `pip` or `uv`.

---

## 1. Objectives

1. **Adopt the Standard `src/` Layout**: Move application code under `src/leetcode_notes_generator/` to adhere to modern PyPA (Python Packaging Authority) best practices.
2. **Standardize Build & Metadata**: Configure PEP 517/518/621 build standards using `hatchling` (Astral/uv standard) in [pyproject.toml](file:///home/gajeet/Projects/leetcode_notes_generator/pyproject.toml).
3. **Register Console Entrypoints**: Provide standard command line executable entrypoints (`leetnotes` and `leetcode-notes`) via `[project.scripts]`.
4. **Package Resources Properly**: Move and bundle templates and prompt files inside the package so wheels built for PyPI are 100% self-contained and work outside the repository directory.
5. **Add Standard PyPI Folders & Files**:
   - `tests/` directory with `pytest` unit tests.
   - `LICENSE` file (MIT License).
   - `py.typed` marker (PEP 561).
   - `src/leetcode_notes_generator/__main__.py` to support `python -m leetcode_notes_generator`.
6. **Maintain Backward Compatibility**: Provide shim entrypoints (`cli.py`, `settings.py`) in root so existing developer workflows, scripts, and commands (`python cli.py ...`) continue functioning seamlessly.

---

## 2. Target Directory Structure

```
leetcode_notes_generator/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── LICENSE                                # NEW: Standard MIT License
├── README.md
├── cli.py                                 # Backwards-compatibility shim
├── pyproject.toml                         # UPDATED: PEP 517/518/621 metadata & build system
├── uv.lock
│
├── src/                                   # NEW: Standard PyPI src-layout
│   └── leetnotes/
│       ├── __init__.py                    # Version (__version__ = "0.1.0")
│       ├── __main__.py                    # NEW: python -m leetnotes
│       ├── py.typed                       # NEW: PEP 561 typing marker
│       ├── config.py                      # Base project configuration & path resolver
│       ├── logging_config.py              # Structured logging configuration
│       │
│       ├── cli/                           # CLI commands
│       │   ├── __init__.py
│       │   ├── main.py                    # Entrypoint for project.scripts
│       │   ├── root.py
│       │   ├── common.py
│       │   ├── notes.py
│       │   ├── picker.py
│       │   ├── problems.py
│       │   ├── problems_data.py
│       │   ├── problems_db.py
│       │   ├── problems_recent.py
│       │   └── problems_render.py
│       │
│       ├── leetcode/                      # LeetCode client, models, parsers, storage
│       │   ├── __init__.py
│       │   ├── auth_cache.py
│       │   ├── client.py
│       │   ├── image_processor.py
│       │   ├── models.py
│       │   ├── recent_activity.py
│       │   ├── settings.py
│       │   ├── parsers/
│       │   └── storage/
│       │
│       ├── render/                        # Markdown rendering logic
│       │   ├── __init__.py
│       │   ├── markdown_notes.py
│       │   ├── markdown_problem.py
│       │   ├── settings.py
│       │   └── utils.py
│       │
│       ├── sync/                          # Pipeline orchestration
│       │   ├── __init__.py
│       │   └── pipeline.py
│       │
│       ├── ai_prefill/                    # AI note drafting
│       │   ├── __init__.py
│       │   ├── generator.py
│       │   ├── prompt_builder.py
│       │   ├── schema.py
│       │   ├── settings.py
│       │   ├── storage.py
│       │   └── providers/
│       │
│       └── resources/                     # Embedded package assets (included in wheel)
│           ├── __init__.py
│           ├── prompts/
│           │   └── ai_prefill/
│           │       ├── system.txt
│           │       └── user.j2
│           └── templates/
│               ├── leetcode_notes_obsidian.md.j2
│               ├── leetcode_notes_plain.md.j2
│               └── leetcode_problem.md.j2
│
├── tests/                                 # Empty test folder (tests added later)
│   └── .gitkeep
│
├── docs/                                  # Documentation
│   └── AI_PREFILL.md
├── scripts/                               # Maintenance / migration scripts
│   ├── migrate_json_to_sqlite.py
│   └── rebake_local_image_paths.py
└── shell/                                 # Shell completions & wrapper
    ├── README.md
    └── leetnotes
```

---

## 3. Detailed Step-by-Step Execution Plan

### Step 1: Create Standard Package Skeleton
- Create directory tree `src/leetcode_notes_generator/` and its subpackages.
- Create `src/leetcode_notes_generator/__init__.py` with version info (`__version__ = "0.1.0"`).
- Create `src/leetcode_notes_generator/__main__.py` invoking `main()`.
- Create empty `src/leetcode_notes_generator/py.typed`.
- Create `LICENSE` (MIT License).

### Step 2: Relocate Code & Resources
- Move modules:
  - `modules/cli` → `src/leetcode_notes_generator/cli`
  - `modules/leetcode` → `src/leetcode_notes_generator/leetcode`
  - `modules/render` → `src/leetcode_notes_generator/render`
  - `modules/sync` → `src/leetcode_notes_generator/sync`
  - `modules/ai_prefill` → `src/leetcode_notes_generator/ai_prefill`
- Move root configuration & logging:
  - `settings.py` → `src/leetcode_notes_generator/config.py` (and maintain root shim)
  - `logging_config.py` → `src/leetcode_notes_generator/logging_config.py` (and maintain root shim)
- Bundle resources inside package:
  - Copy `resources/` into `src/leetcode_notes_generator/resources/` so they are packaged into wheels and installable via pip.

### Step 3: Modernize Resource Loading & Path Resolution
- Update resource paths in `render/settings.py` and `ai_prefill/settings.py` using `importlib.resources` with fallback to local path, so templates and prompts are discovered whether installed as a pip package or run locally.
- In `config.py` (`BaseProjectSettings`), enhance `PROJECT_ROOT_DIR` resolution to detect repository root or fall back to current working directory when used as an installed CLI tool.

### Step 4: Update Imports
- Update all internal imports across the package:
  - Replace `from modules.<submodule>` with `from leetcode_notes_generator.<submodule>` (or relative package imports).
  - Replace `from settings import ...` with `from leetcode_notes_generator.config import ...`.
  - Replace `from logging_config import ...` with `from leetcode_notes_generator.logging_config import ...`.
- Add `main.py` entrypoint inside `src/leetcode_notes_generator/cli/main.py`:
  ```python
  def main():
      ...
  ```

### Step 5: Update `pyproject.toml`
- Configure `[build-system]` with `hatchling`.
- Enrich `[project]` metadata:
  - Add `description`, `readme`, `authors`, `license`, `classifiers`, `keywords`.
  - Add `[project.scripts]`:
    - `leetnotes = "leetcode_notes_generator.cli.main:main"`
    - `leetcode-notes = "leetcode_notes_generator.cli.main:main"`
  - Add `[project.urls]` (repository, issues, documentation).
- Configure `[tool.hatch.build.targets.wheel]` to include package assets in `resources/`.
- Add `pytest` to `[dependency-groups].dev`.

### Step 6: Create Test Suite (`tests/`)
- Setup standard test structure:
  - `tests/conftest.py`: Shared test fixtures.
  - `tests/test_cli.py`: CLI invocation and `--help` tests using Click's `CliRunner`.
  - `tests/test_models.py`: Pydantic model serialization and validation tests.
  - `tests/test_parsers.py`: HTML to Markdown conversion tests.
  - `tests/test_render.py`: Template loading and Jinja rendering tests.

### Step 7: Compatibility Shims & Cleanup
- Place a backwards-compatible `cli.py` at the repo root delegating to `leetcode_notes_generator.cli.main.main()`.
- Place root shims for `settings.py` and `logging_config.py`.
- Remove obsolete `modules/` directory once all code is migrated and verified.
- Update `scripts/` imports.
- Update `shell/leetnotes` to invoke `uv run leetnotes` or `uv run python -m leetcode_notes_generator`.
- Update `CLAUDE.md` and `README.md` documentation to reflect the new structure.

### Step 8: Verification & Packaging Build
- Run `uv sync` to install editable package in `.venv`.
- Run test suite: `uv run pytest`.
- Verify CLI: `uv run leetnotes --help` and `uv run python -m leetcode_notes_generator --help`.
- Build package wheel & sdist: `uv build`.
- Inspect built wheel contents with `unzip -l dist/*.whl` or `tar -tf dist/*.tar.gz` to ensure resources (`.j2`, `.txt`) and package files are properly packaged.

---

## 4. Key Questions & Decisions

> [!NOTE]
> **CLI Binary Names**: We propose registering both `leetnotes` (the project's existing preferred shorthand) and `leetcode-notes` in `[project.scripts]`.
>
> **Build Backend**: We recommend `hatchling`, which is the official default for `uv`, fast, and requires zero external C/wheel overhead.
