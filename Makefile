PY := venv/bin/python
# If the bin version does not exist look in venv/local/bin
ifeq ($(wildcard venv/bin/pip),)
  PIP = venv/local/bin/pip
else
  PIP = venv/bin/pip
endif
# If the bin version does not exist look in venv/local/bin
NOSE = venv/bin/nosetests
ENV?=development
# ###########
# Build
# ###########

.PHONY: install
install: venv develop

venv: $(PY)
$(PY):
	virtualenv venv

.PHONY: clean_all
clean_all: clean clean_venv clean_db

.PHONY: clean_db
clean_db:
	rm -f backend.sqlite

.PHONY: clean_venv
clean_venv:
	rm -rf venv devel

.PHONY: clean
clean:
	find . -name '*.pyc' -delete
	find . -name '*.bak' -delete
	rm -f .coverage

develop: lib/python*/site-packages/reviewq.egg-link
lib/python*/site-packages/reviewq.egg-link:
	$(PY) setup.py develop

.PHONY: sysdeps
sysdeps:
	sudo apt-get $(shell tty -s || echo -y) install python3-dev

# ###########
# Develop
# ###########

$(NOSE): $(PY)
	@$(PIP) install -U -r requirements.test.txt

.PHONY: test
test: unit_test functional_test

unit_test: $(NOSE)
	@$(NOSE) --nologcapture

functional_test: $(NOSE)
	@$(NOSE) --nologcapture test_func

.PHONY: coverage
coverage: $(NOSE)
	@echo Testing with coverage...
	@$(NOSE) --nologcapture --with-coverage --cover-package=reviewq

.PHONY: lint
lint:
	@find $(sources) -type f \( -iname '*.py' ! -iname '__init__.py' ! -iwholename '*venv/*' \) -print0 | xargs -r0 flake8

.PHONY: check
check: test lint

.PHONY: all
all: clean venv coverage lint

database:
	@venv/bin/initialize_backend_db $(ENV).ini

.PHONY: start
start: develop
	@venv/bin/pserve $(ENV).ini --reload
