#!/usr/bin/make
TEAM := $(LOGNAME)
PYTHONPATH := $(PYTHONPATH):$(PWD)/reactive:$(PWD)/lib
PYTHON := python3
CHARM_NAME := ntp
CS_CHANNEL := candidate
CSDEST := cs:~$(TEAM)/$(CHARM_NAME)

test:
	$(PYTHON) -m unittest unit_tests/test_ntp_*.py

lint: test
	@python3 -m flake8 --max-line-length=120 lib reactive

build: lint
	charm build

push: build
	cd $(JUJU_REPOSITORY)/builds/$(CHARM_NAME) && \
	    version=`charm push . $(CSDEST) | awk '/^url:/ {print $$2}'` && \
	    charm release --channel $(CS_CHANNEL) $$version

upgrade: push
	juju upgrade-charm $(CHARM_NAME) --channel $(CS_CHANNEL)
