#!/bin/sh
# Integration tests for: erg archive (dry-run only)
set -e

ERG="${ERG_BIN:-tickets/tools/go/erg}"
FIXTURES="tests/fixtures"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

mkdir -p "$FIXTURES/arch"
trap 'rm -rf "$FIXTURES/arch"' EXIT

echo "=== erg archive ==="

# --- Old closed ticket is archivable ---
cat > "$FIXTURES/arch/0001-old.erg" <<'EOF'
%erg v1
Title: Old closed
Status: closed
Created: 2025-01-01
Author: a

--- log ---
2025-01-01T10:00Z a created
2025-01-02T10:00Z a status closed

--- body ---
EOF
output=$($ERG archive "$FIXTURES/arch" --days=1)
if echo "$output" | grep -q "0001"; then
    pass "old closed ticket archivable"
else
    fail "old closed ticket archivable"
fi

# --- Recent closed ticket not archivable ---
cat > "$FIXTURES/arch/0001-old.erg" <<'EOF'
%erg v1
Title: Recent
Status: closed
Created: 2026-03-27
Author: a

--- log ---
2026-03-27T10:00Z a created
2026-03-27T10:01Z a status closed

--- body ---
EOF
output=$($ERG archive "$FIXTURES/arch" --days=90)
if echo "$output" | grep -q "Nothing to archive"; then
    pass "recent closed not archivable"
else
    fail "recent closed not archivable"
fi

# --- Open ticket never archivable ---
cat > "$FIXTURES/arch/0001-old.erg" <<'EOF'
%erg v1
Title: Open
Status: open
Created: 2025-01-01
Author: a

--- log ---
2025-01-01T10:00Z a created

--- body ---
EOF
output=$($ERG archive "$FIXTURES/arch" --days=1)
if echo "$output" | grep -q "Nothing to archive"; then
    pass "open ticket never archivable"
else
    fail "open ticket never archivable"
fi

# --- DAG-protected ticket not archivable ---
cat > "$FIXTURES/arch/0001-old.erg" <<'EOF'
%erg v1
Title: Old dep
Status: closed
Created: 2025-01-01
Author: a

--- log ---
2025-01-01T10:00Z a created
2025-01-02T10:00Z a status closed

--- body ---
EOF
cat > "$FIXTURES/arch/0002-depends.erg" <<'EOF'
%erg v1
Title: Depends
Status: open
Created: 2026-01-01
Author: a
Blocked-by: 0001

--- log ---
2026-01-01T10:00Z a created

--- body ---
EOF
output=$($ERG archive "$FIXTURES/arch" --days=1)
if echo "$output" | grep -q "DAG-protected"; then
    pass "DAG-protected ticket skipped"
else
    fail "DAG-protected ticket skipped"
fi

echo "archive: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
