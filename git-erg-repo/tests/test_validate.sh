#!/bin/sh
# Integration tests for: erg validate
set -e

ERG="${ERG_BIN:-tickets/tools/go/erg}"
FIXTURES="tests/fixtures"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

mkdir -p "$FIXTURES"
trap 'rm -rf "$FIXTURES"/*.erg "$FIXTURES"/dup/' EXIT

echo "=== erg validate ==="

# --- Valid ticket passes ---
cat > "$FIXTURES/0001-valid.erg" <<'EOF'
%erg v1
Title: Valid ticket
Status: open
Created: 2026-01-01
Author: claude

--- log ---
2026-01-01T10:00Z claude created

--- body ---
Test body.
EOF
if $ERG validate "$FIXTURES/0001-valid.erg" >/dev/null 2>&1; then
    pass "valid ticket passes"
else
    fail "valid ticket passes"
fi

# --- Missing magic line fails ---
cat > "$FIXTURES/0002-no-magic.erg" <<'EOF'
Title: No magic
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/0002-no-magic.erg" >/dev/null 2>&1; then
    fail "missing magic line detected"
else
    pass "missing magic line detected"
fi

# --- Unknown header fails ---
cat > "$FIXTURES/0003-bad-header.erg" <<'EOF'
%erg v1
Title: Bad header
Status: open
Created: 2026-01-01
Author: a
X-Phase: dreaming

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/0003-bad-header.erg" >/dev/null 2>&1; then
    fail "unknown header rejected"
else
    pass "unknown header rejected"
fi

# --- Invalid status fails ---
cat > "$FIXTURES/0004-bad-status.erg" <<'EOF'
%erg v1
Title: Bad status
Status: invalid
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/0004-bad-status.erg" >/dev/null 2>&1; then
    fail "invalid status rejected"
else
    pass "invalid status rejected"
fi

# --- All four valid statuses pass ---
for status in open doing closed pending; do
    cat > "$FIXTURES/0005-status.erg" <<EOF
%erg v1
Title: Status test
Status: $status
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
    if $ERG validate "$FIXTURES/0005-status.erg" >/dev/null 2>&1; then
        pass "status '$status' accepted"
    else
        fail "status '$status' accepted"
    fi
done

# --- Bad filename pattern fails ---
cat > "$FIXTURES/abc-bad-name.erg" <<'EOF'
%erg v1
Title: Bad name
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/abc-bad-name.erg" >/dev/null 2>&1; then
    fail "bad filename pattern rejected"
else
    pass "bad filename pattern rejected"
fi

# --- Missing separators fail ---
cat > "$FIXTURES/0006-no-sep.erg" <<'EOF'
%erg v1
Title: No separators
Status: open
Created: 2026-01-01
Author: a
EOF
if $ERG validate "$FIXTURES/0006-no-sep.erg" >/dev/null 2>&1; then
    fail "missing separators rejected"
else
    pass "missing separators rejected"
fi

# --- Blocked-by unknown ID fails ---
cat > "$FIXTURES/0007-bad-ref.erg" <<'EOF'
%erg v1
Title: Bad ref
Status: open
Created: 2026-01-01
Author: a
Blocked-by: 9999

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/0007-bad-ref.erg" >/dev/null 2>&1; then
    fail "unknown blocked-by rejected"
else
    pass "unknown blocked-by rejected"
fi

# --- gh#N references pass ---
cat > "$FIXTURES/0008-gh-ref.erg" <<'EOF'
%erg v1
Title: GitHub ref
Status: open
Created: 2026-01-01
Author: a
Blocked-by: gh#435

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/0008-gh-ref.erg" >/dev/null 2>&1; then
    pass "gh#N reference accepted"
else
    fail "gh#N reference accepted"
fi

# --- Malformed log line fails ---
cat > "$FIXTURES/0009-bad-log.erg" <<'EOF'
%erg v1
Title: Bad log
Status: open
Created: 2026-01-01
Author: a

--- log ---
this is not valid

--- body ---
EOF
if $ERG validate "$FIXTURES/0009-bad-log.erg" >/dev/null 2>&1; then
    fail "malformed log line rejected"
else
    pass "malformed log line rejected"
fi

# --- Duplicate IDs fail ---
mkdir -p "$FIXTURES/dup"
cat > "$FIXTURES/dup/0001-one.erg" <<'EOF'
%erg v1
Title: One
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
cat > "$FIXTURES/dup/0001-two.erg" <<'EOF'
%erg v1
Title: Two
Status: open
Created: 2026-01-01
Author: a

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/dup" >/dev/null 2>&1; then
    fail "duplicate IDs rejected"
else
    pass "duplicate IDs rejected"
fi

# --- Dependency cycle fails ---
mkdir -p "$FIXTURES/dup"
cat > "$FIXTURES/dup/0001-one.erg" <<'EOF'
%erg v1
Title: One
Status: open
Created: 2026-01-01
Author: a
Blocked-by: 0002

--- log ---
--- body ---
EOF
cat > "$FIXTURES/dup/0002-two.erg" <<'EOF'
%erg v1
Title: Two
Status: open
Created: 2026-01-01
Author: a
Blocked-by: 0001

--- log ---
--- body ---
EOF
if $ERG validate "$FIXTURES/dup" >/dev/null 2>&1; then
    fail "dependency cycle rejected"
else
    pass "dependency cycle rejected"
fi

# --- Real tickets pass ---
if $ERG validate tickets/ >/dev/null 2>&1; then
    pass "real tickets pass"
else
    fail "real tickets pass"
fi

echo "validate: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
