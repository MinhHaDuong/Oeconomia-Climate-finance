# git-erg — agent-native local ticket system
#
# Usage:
#   make build      Build the erg binary
#   make test       Run shell integration tests
#   make validate   Validate tickets in tickets/
#   make ready      List ready tickets
#   make archive    Dry-run archive (pass EXECUTE=1 to commit)

.PHONY: build test validate ready archive clean

ERG_BIN := tickets/tools/go/erg

build:
	cd tickets/tools/go && go build -o erg .

test: build
	@sh tests/test_validate.sh
	@sh tests/test_ready.sh
	@sh tests/test_archive.sh
	@echo "ALL TESTS PASSED"

validate: build
	$(ERG_BIN) validate tickets/

ready: build
	$(ERG_BIN) ready tickets/

DAYS ?= 90
EXECUTE ?=
archive: build
	$(ERG_BIN) archive tickets/ --days=$(DAYS) $(if $(EXECUTE),--execute)

clean:
	rm -f $(ERG_BIN)
