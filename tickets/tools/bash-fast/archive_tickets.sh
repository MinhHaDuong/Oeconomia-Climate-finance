#!/bin/sh
# DAG-safe archival of old closed tickets.
# POSIX sh + awk — runs on Alpine, Busybox, dash, any /bin/sh.
#
# Usage:
#     archive_tickets.sh [tickets/] [--days N] [--execute]
#
# Default: dry-run. Pass --execute to actually move files and commit.
#
# Deps: sh, awk, date, git (standard on any system)

set -eu

# ---------------------------------------------------------------------------
# Argument parsing (no arrays — just variables)
# ---------------------------------------------------------------------------
execute=false
days=90
ticket_dir="tickets"

while [ $# -gt 0 ]; do
    case "$1" in
        --execute)        execute=true; shift ;;
        --days=*)         days="${1#--days=}"; shift ;;
        --days)           days="$2"; shift 2 ;;
        --*)              shift ;;
        *)                ticket_dir="$1"; shift ;;
    esac
done

case "$days" in
    ''|*[!0-9]*) echo "Error: --days must be a positive integer, got '$days'" >&2; exit 1 ;;
esac

if [ ! -d "$ticket_dir" ]; then
    echo "Directory not found: $ticket_dir"
    exit 1
fi

# ---------------------------------------------------------------------------
# Collect file lists
# ---------------------------------------------------------------------------
live_files=""
for f in "$ticket_dir"/*.ticket; do
    [ -e "$f" ] && live_files="$live_files $f"
done

all_files="$live_files"
archive_dir="${ticket_dir%/}/archive"
if [ -d "$archive_dir" ]; then
    for f in "$archive_dir"/*.ticket; do
        [ -e "$f" ] && all_files="$all_files $f"
    done
fi

if [ -z "$live_files" ]; then
    echo "Nothing to archive (threshold: ${days} days)."
    exit 0
fi

# ---------------------------------------------------------------------------
# Compute cutoff epoch
# ---------------------------------------------------------------------------
cutoff_epoch=$(date -d "-${days} days" +%s 2>/dev/null || date -v-${days}d +%s 2>/dev/null)

# ---------------------------------------------------------------------------
# Single awk program: parse all files, find archivable tickets.
# Output lines:
#   ARCHIVABLE <filename>
#   DAGPROTECTED <id>
#   NOTHING
# ---------------------------------------------------------------------------
# shellcheck disable=SC2086
result=$(awk -v cutoff="$cutoff_epoch" -v dag_hdrs="Blocked-by,X-Discovered-from,X-Supersedes,X-Parent" '
BEGIN {
    split(dag_hdrs, dh, ",")
    section = "headers"
}

FNR == 1 {
    if (NR > 1) emit()
    reset()
    file = FILENAME
    n = split(file, parts, "/")
    fname = parts[n]
    # Track whether this file is "live" (not in archive/ subpath)
    is_live = (file !~ /\/archive\//)
}

section == "headers" {
    if ($0 ~ /^[[:space:]]*$/) { section = "gap"; next }
    if ($0 ~ /^[A-Za-z][A-Za-z0-9_-]*[[:space:]]*:/) {
        colon = index($0, ":")
        key = substr($0, 1, colon - 1)
        val = substr($0, colon + 1)
        sub(/^[[:space:]]+/, "", key); sub(/[[:space:]]+$/, "", key)
        sub(/^[[:space:]]+/, "", val); sub(/[[:space:]]+$/, "", val)
        if (key == "Id") tid = val
        else if (key == "Status") status = val
        else {
            for (i in dh) {
                if (key == dh[i]) {
                    dag_refs = dag_refs (dag_refs ? "," : "") val
                    break
                }
            }
        }
    }
    next
}
section == "gap" {
    if ($0 ~ /^[[:space:]]*--- log ---/) { section = "log"; next }
    if ($0 ~ /^[[:space:]]*--- body ---/) { section = "body"; next }
    next
}
section == "log" {
    if ($0 ~ /^[[:space:]]*--- body ---/) { section = "body"; next }
    if ($0 ~ /[^[:space:]]/) {
        if (match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z?/))
            last_ts = substr($0, RSTART, RLENGTH)
    }
    next
}
section == "body" { next }

function reset() {
    section = "headers"; tid = ""; status = ""; last_ts = ""; dag_refs = ""
}
function emit() {
    ntix++
    tix_fname[ntix]  = fname
    tix_id[ntix]     = tid
    tix_status[ntix] = status
    tix_last_ts[ntix]= last_ts
    tix_live[ntix]   = is_live

    # Collect DAG references from all tickets (live + archived)
    if (dag_refs != "") {
        nr = split(dag_refs, drefs, ",")
        for (r = 1; r <= nr; r++)
            referenced[drefs[r]] = 1
    }
}

END {
    if (NR > 0) emit()

    narchivable = 0
    nprotected = 0

    for (i = 1; i <= ntix; i++) {
        if (!tix_live[i]) continue
        if (tix_status[i] != "closed") continue
        if (tix_last_ts[i] == "") continue

        # Parse timestamp to epoch
        ts = tix_last_ts[i]
        sub(/Z$/, "", ts)
        # YYYY-MM-DDTHH:MM(:SS)?
        if (length(ts) < 16) continue
        Y  = substr(ts, 1, 4) + 0
        Mo = substr(ts, 6, 2) + 0
        D  = substr(ts, 9, 2) + 0
        H  = substr(ts, 12, 2) + 0
        Mi = substr(ts, 15, 2) + 0
        S  = 0
        if (length(ts) >= 19 && substr(ts, 17, 1) == ":")
            S = substr(ts, 18, 2) + 0

        # Simplified epoch (same formula both sides use for comparison)
        # Use days-since-epoch approach for reliable comparison
        # Julian Day Number (simplified, good enough for recent dates)
        a = int((14 - Mo) / 12)
        y = Y + 4800 - a
        m = Mo + 12 * a - 3
        jdn = D + int((153 * m + 2) / 5) + 365 * y + int(y/4) - int(y/100) + int(y/400) - 32045
        ts_epoch = (jdn - 2440588) * 86400 + H * 3600 + Mi * 60 + S

        if (ts_epoch >= cutoff + 0) continue

        # DAG protection check
        if (tix_id[i] in referenced) {
            nprotected++
            protected_ids = protected_ids (protected_ids ? ", " : "") tix_id[i]
        } else {
            narchivable++
            archivable[narchivable] = tix_fname[i]
            archivable_ids = archivable_ids (archivable_ids ? ", " : "") tix_id[i]
        }
    }

    if (nprotected > 0)
        printf "DAG-protected (skipping %d): %s\n", nprotected, protected_ids

    if (narchivable == 0) {
        print "NOTHING"
    } else {
        printf "SUMMARY %d %s\n", narchivable, archivable_ids
        for (i = 1; i <= narchivable; i++)
            printf "ARCHIVABLE %s\n", archivable[i]
    }
}
' $all_files)

# ---------------------------------------------------------------------------
# Process awk output
# ---------------------------------------------------------------------------
if echo "$result" | grep -q "^NOTHING$"; then
    # Print any DAG-protected lines first
    echo "$result" | grep "^DAG-protected" || true
    echo "Nothing to archive (threshold: ${days} days)."
    exit 0
fi

# Print DAG-protected info
echo "$result" | grep "^DAG-protected" || true

# Extract summary
summary_line=$(echo "$result" | grep "^SUMMARY")
count=$(echo "$summary_line" | awk '{print $2}')
ids=$(echo "$summary_line" | sed 's/^SUMMARY [0-9]* //')

echo "Will archive ${count} ticket(s): ${ids}"

if [ "$execute" != true ]; then
    echo "Dry run. Pass --execute to proceed."
    exit 0
fi

mkdir -p "$archive_dir"
# Avoid subshell: extract filenames first, then loop without pipe.
archivable_files=$(echo "$result" | grep "^ARCHIVABLE " | awk '{print $2}')
for fname in $archivable_files; do
    git mv "${ticket_dir}/${fname}" "${archive_dir}/${fname}" || {
        echo "error: git mv failed for ${fname}" >&2
        exit 1
    }
    echo "  moved ${fname}"
done

msg="archive ${count} closed tickets (>${days} days, DAG-safe)"
git commit -m "$msg" || { echo "error: git commit failed" >&2; exit 1; }
echo "Committed: ${msg}"
