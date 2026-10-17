# Development entrypoint (uv):
#
#   make              show the target list
#   make check        lint + test, what `make check` of ingots-libs runs
#   make logo         rebuild the final logo (final-pyramid.*)

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

SRC := logo_gen tests

# The final logo: the camera picked on the grid, committed as final-pyramid.*
LOGO_ARGS := --preset pyramid --az 50 --el 25 --r 750 --out final --png 128 256 512


##@ Checks

.PHONY: check
check: lint test  ## Every check: lint + test

.PHONY: lint
lint:  ## black --check, flake8, mypy --strict
	uv run black --check --diff $(SRC)
	uv run flake8 $(SRC)
	uv run mypy $(SRC)

.PHONY: test
test:  ## unittest
	uv run python -m unittest discover -s tests -t .

.PHONY: format
format:  ## Format code with black
	uv run black $(SRC)


##@ Logo

.PHONY: logo
logo:  ## Rebuild the final logo: final-pyramid.svg + PNGs
	uv run logo-gen $(LOGO_ARGS)


##@ Housekeeping

.PHONY: clean
clean:  ## Remove caches (keeps the virtualenv)
	rm -rf .mypy_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

.PHONY: help
help:  ## Show this help
	@echo "logo-gen - make targets:"
	@awk 'BEGIN {FS = ":.*## "} \
		/^##@ / {printf "\n%s\n", substr($$0, 5); next} \
		/^[a-z][a-zA-Z0-9_-]*:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
