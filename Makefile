#!/usr/bin/make
TEAM := $(LOGNAME)
PYTHONPATH := $(PYTHONPATH):$(PWD)/reactive:$(PWD)/lib:$(PWD)/actions
PYTHON := python3
CHARM_NAME := ntp
CS_CHANNEL := candidate
CSDEST := cs:~$(TEAM)/$(CHARM_NAME)

clean:
	@echo "Cleaning files"
	@rm -rf ./.tox
	@rm -rf ./.pytest_cache
	@rm -rf ./unit_tests/__pycache__ ./reactive/__pycache__ ./lib/__pycache__ ./actions/__pycache__
	@rm -rf ./.coverage ./.unit-state.db

test: unittest

unittest:
	@tox -e unit

lint:
	@echo "Running flake8"
	@tox -e lint

build: lint
	charm build

push: build
	cd $(JUJU_REPOSITORY)/builds/$(CHARM_NAME) && \
	    version=`charm push . $(CSDEST) | awk '/^url:/ {print $$2}'` && \
	    charm release --channel $(CS_CHANNEL) $$version

upgrade: push
	juju upgrade-charm $(CHARM_NAME) --channel $(CS_CHANNEL)
