#!/usr/bin/make
PYTHON := /usr/bin/env PYTHONPATH=$(PWD)/hooks python3
CHARM_NAME := ntp
CSDEST := cs:~$(LOGNAME)/$(CHARM_NAME)

test:
	$(PYTHON) -m unittest unit_tests/test_ntp_*.py

lint: test
	@python3 -m flake8 --max-line-length=120 --exclude hooks/charmhelpers hooks
	@charm proof

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
        > bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-sync.yaml

git:
	git push $(LOGNAME)

cspush: lint
	version=`charm push . $(CSDEST) | awk '/^url:/ {print $$2}'` && \
	    charm release $$version

upgrade: cspush
	juju upgrade-charm $(CHARM_NAME)
