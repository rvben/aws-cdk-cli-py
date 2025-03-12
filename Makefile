.PHONY: test test-slow lint clean build install-dev test-local docs help

PYTHON := python3
PIP := $(PYTHON) -m pip
TEST_ENV := test_env
PYTEST := pytest
BUILD := $(PYTHON) -m build
TWINE := $(PYTHON) -m twine

help:
	@echo "AWS CDK Python Wrapper Makefile commands:"
	@echo "----------------------------------------"
	@echo "make install-dev    Install package in development mode"
	@echo "make test           Run basic tests (fast tests only)"
	@echo "make test-slow      Run all tests including slow tests"
	@echo "make test-local     Run local installation test script"
	@echo "make build          Build package distribution files"
	@echo "make check          Check built package with twine"
	@echo "make clean          Clean build artifacts and cache files"
	@echo "make lint           Run code linters (flake8, black)"
	@echo "make format         Format code with black"
	@echo "make docs           Generate documentation"
	@echo "make venv           Create a virtual environment"
	@echo "make bump-version   Bump package version"

# Installation
install-dev:
	$(PIP) install -e .

# Testing
test:
	$(PYTEST) tests/ -v

test-slow:
	$(PYTEST) tests/ -v --slow

test-local:
ifeq ($(OS),Windows_NT)
	.\testing\test_local_install.bat
else
	./testing/test_local_install.sh
endif

test-all: test test-slow

# Virtual environment
venv:
	$(PYTHON) -m venv $(TEST_ENV)
ifeq ($(OS),Windows_NT)
	@echo "Run '$(TEST_ENV)\Scripts\activate' to activate the virtual environment"
else
	@echo "Run 'source $(TEST_ENV)/bin/activate' to activate the virtual environment"
endif

# Building
build: clean
	$(BUILD) --wheel --sdist

check:
	$(TWINE) check dist/*

# Code quality
lint:
	flake8 aws_cdk tests
	black --check aws_cdk tests

format:
	black aws_cdk tests

# Documentation
docs:
	$(PYTHON) -m sphinx.cmd.build -b html docs/source docs/build/html

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete

# Version management
bump-version:
	@echo "Current version is: $$(grep -m 1 version pyproject.toml | cut -d '"' -f 2)"
	@read -p "Enter new version: " new_version; \
	sed -i.bak "s/version = \"[0-9.]*\"/version = \"$$new_version\"/" pyproject.toml; \
	rm pyproject.toml.bak; \
	echo "Version bumped to $$new_version"

# Default target
.DEFAULT_GOAL := help 