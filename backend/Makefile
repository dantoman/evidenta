# Comenzile stau în Makefile-ul din rădăcină, fiindcă majoritatea ating și `infra/`, nu doar
# backend-ul. Acest fișier doar redirecționează, ca `make test` să funcționeze și din `backend/`,
# unde se lucrează efectiv — altfel prima încercare răspunde „No rule to make target".

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

.DEFAULT_GOAL := help

.PHONY: help
help:
	@$(MAKE) --no-print-directory -C $(ROOT) help

%:
	@$(MAKE) --no-print-directory -C $(ROOT) $@
