ifeq ($(OS),Windows_NT)
PYTHON ?= venv/Scripts/python.exe
else
PYTHON ?= venv/bin/python
endif

.PHONY: help dev qa prod test install compile

help:
	@echo "FinanceManager commands:"
	@echo "  make dev      Run the development environment"
	@echo "  make qa       Run the QA environment"
	@echo "  make prod     Run the production environment"
	@echo "  make test     Run the test suite"
	@echo "  make install  Install requirements"
	@echo "  make compile  Compile Python files"

dev:
	$(PYTHON) run.py --env dev

qa:
	$(PYTHON) run.py --env qa

prod:
	$(PYTHON) run.py --env prod

test:
	$(PYTHON) -m pytest -q

install:
	$(PYTHON) -m pip install -r requirements.txt

compile:
	$(PYTHON) -m compileall -q run.py api app data views
