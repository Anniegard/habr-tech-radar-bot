.PHONY: install install-dev lint format typecheck test check precommit run help

PYTHON ?= python

help:
	@echo "install      - pip install -e ."
	@echo "install-dev  - pip install -e .[dev] and pre-commit install"
	@echo "lint         - ruff check src tests"
	@echo "format       - ruff format src tests"
	@echo "typecheck    - mypy src tests"
	@echo "test         - pytest"
	@echo "check        - lint + typecheck + test"
	@echo "precommit    - pre-commit run --all-files"
	@echo "run          - python -m habr_tech_radar"

install:
	$(PYTHON) -m pip install -e .

install-dev: install
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pre_commit install

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests

typecheck:
	$(PYTHON) -m mypy src tests

test:
	$(PYTHON) -m pytest

check: lint typecheck test

precommit:
	$(PYTHON) -m pre_commit run --all-files

run:
	$(PYTHON) -m habr_tech_radar
