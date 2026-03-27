#!/bin/sh
# Integration tests for: erg ready
set -e

ERG="${ERG_BIN:-tickets/tools/go/erg}"
FIXTURES="tests/fixtures"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

mkdir -p "$FIXTURES/ready"
trap 'rm -rf "$FIXTURES/ready"' EXIT

echo "=== erg ready ==="

# --- Open ticket with no blockers is ready ---
cat > "$FIXTURES/ready/0001-open.erg" <<'EOF'
%erg v1
Title: Open
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0001"; then
    pass "open ticket is ready"
else
    fail "open ticket is ready"
fi

# --- Closed ticket not in ready list ---
cat > "$FIXTURES/ready/0001-open.erg" <<'EOF'
%erg v1
Title: Closed
Status: closed
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0001"; then
    fail "closed ticket excluded"
else
    pass "closed ticket excluded"
fi

# --- Doing ticket not in ready list ---
cat > "$FIXTURES/ready/0001-open.erg" <<'EOF'
%erg v1
Title: Doing
Status: doing
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0001"; then
    fail "doing ticket excluded"
else
    pass "doing ticket excluded"
fi

# --- Pending ticket not in ready list ---
cat > "$FIXTURES/ready/0001-open.erg" <<'EOF'
%erg v1
Title: Pending
Status: pending
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0001"; then
    fail "pending ticket excluded"
else
    pass "pending ticket excluded"
fi

# --- Blocked by open ticket: not ready ---
rm -f "$FIXTURES/ready/"*.erg
cat > "$FIXTURES/ready/0001-blocker.erg" <<'EOF'
%erg v1
Title: Blocker
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
cat > "$FIXTURES/ready/0002-blocked.erg" <<'EOF'
%erg v1
Title: Blocked
Status: open
Created: 2026-01-01
Author: a
Blocked-by: 0001

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0002"; then
    fail "blocked ticket excluded from ready"
else
    pass "blocked ticket excluded from ready"
fi
# But the blocker itself is ready
if echo "$output" | grep -q "0001"; then
    pass "unblocked ticket is ready"
else
    fail "unblocked ticket is ready"
fi

# --- Blocked by closed ticket: ready ---
cat > "$FIXTURES/ready/0001-blocker.erg" <<'EOF'
%erg v1
Title: Blocker
Status: closed
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -q "0002"; then
    pass "unblocked after close is ready"
else
    fail "unblocked after close is ready"
fi

# --- JSON output ---
output=$($ERG ready --json "$FIXTURES/ready")
if echo "$output" | grep -q '"id"'; then
    pass "JSON output works"
else
    fail "JSON output works"
fi

# --- Empty dir ---
rm -f "$FIXTURES/ready/"*.erg
output=$($ERG ready "$FIXTURES/ready")
if echo "$output" | grep -qi "no tickets"; then
    pass "empty dir handled"
else
    fail "empty dir handled"
fi

echo "ready: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
