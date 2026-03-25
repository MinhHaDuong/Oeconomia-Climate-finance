#!/bin/sh
# Find open tickets whose blockers are all resolved.
# POSIX sh + awk — runs on Alpine, Busybox, dash, any /bin/sh.
#
# Usage:
#     ready_tickets.sh [tickets/]
#     ready_tickets.sh --json [tickets/]
#
# Deps: sh, awk (standard on any system with git)

set -eu

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
use_json=false
ticket_dir="tickets"

for a in "$@"; do
    case "$a" in
        --json) use_json=true ;;
        *)      ticket_dir="$a" ;;
    esac
done

if [ ! -d "$ticket_dir" ]; then
    echo "Directory not found: $ticket_dir"
    exit 1
fi

# ---------------------------------------------------------------------------
# Detect .wip signals (soft coordination across worktrees)
# ---------------------------------------------------------------------------
wip_dir=""
git_common=$(git rev-parse --git-common-dir 2>/dev/null) && wip_dir="${git_common}/ticket-wip"

# Build wip lookup: "id\tline" pairs
wip_data=""
if [ -n "$wip_dir" ] && [ -d "$wip_dir" ]; then
    for w in "$wip_dir"/*.wip; do
        [ -e "$w" ] || continue
        wid=$(basename "$w" .wip)
        wline=$(head -1 "$w")
        wip_data="${wip_data}${wid}	${wline}
"
    done
fi

# Collect ticket files
file_list=""
for f in "$ticket_dir"/*.ticket; do
    [ -e "$f" ] && file_list="$file_list $f"
done

if [ -z "$file_list" ]; then
    if [ "$use_json" = true ]; then
        echo "[]"
    else
        echo "No tickets found."
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# Single awk program: parse all tickets, find ready ones, output results.
# ---------------------------------------------------------------------------
# shellcheck disable=SC2086
awk -v use_json="$use_json" -v wip_raw="$wip_data" '
BEGIN {
    # Parse wip_raw (newline-separated "id\tline" pairs) into wip[] lookup
    nw = split(wip_raw, wip_lines, "\n")
    for (wi = 1; wi <= nw; wi++) {
        if (wip_lines[wi] == "") continue
        tab = index(wip_lines[wi], "\t")
        if (tab > 0) {
            wip_id = substr(wip_lines[wi], 1, tab - 1)
            wip[wip_id] = substr(wip_lines[wi], tab + 1)
        }
    }
}
# --- Parser ---
FNR == 1 {
    if (NR > 1) emit()
    reset()
    file = FILENAME
    n = split(file, parts, "/")
    fname = parts[n]
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
        else if (key == "Title") title = val
        else if (key == "Status") status = val
        else if (key == "Blocked-by") blocked = blocked (blocked ? "," : "") val
    }
    next
}
section == "gap" || section == "log" {
    if ($0 ~ /^[[:space:]]*--- log ---/) { section = "log"; next }
    if ($0 ~ /^[[:space:]]*--- body ---/) { section = "body"; next }
    next
}
section == "body" { next }
function reset() { section = "headers"; tid = ""; title = ""; status = ""; blocked = "" }
function emit() {
    ntix++
    tix_fname[ntix] = fname; tix_id[ntix] = tid
    tix_title[ntix] = title; tix_status[ntix] = status
    tix_blocked[ntix] = blocked
    if (tid != "") status_by_id[tid] = status
}

END {
    if (NR > 0) emit()

    nready = 0
    for (i = 1; i <= ntix; i++) {
        if (tix_status[i] != "open") continue
        is_blocked = 0
        if (tix_blocked[i] != "") {
            nb = split(tix_blocked[i], refs, ",")
            for (r = 1; r <= nb; r++) {
                ref = refs[r]
                if (!(ref in status_by_id)) {
                    printf "WARNING: %s: Blocked-by '\''%s'\'' not found (treating as satisfied)\n", tix_fname[i], ref > "/dev/stderr"
                } else if (status_by_id[ref] != "closed") {
                    is_blocked = 1
                    break
                }
            }
        }
        if (!is_blocked) {
            nready++
            ready_id[nready] = tix_id[i]
            ready_title[nready] = tix_title[i]
            ready_file[nready] = tix_fname[i]
        }
    }

    # Count open tickets
    nopen = 0
    for (i = 1; i <= ntix; i++) {
        if (tix_status[i] == "open") nopen++
    }

    if (use_json == "true") {
        if (nready == 0) {
            print "[]"
        } else {
            print "["
            for (i = 1; i <= nready; i++) {
                comma = (i < nready) ? "," : ""
                wip_field = ""
                if (ready_id[i] in wip) wip_field = sprintf(", \"wip\": \"%s\"", json_esc(wip[ready_id[i]]))
                printf "  {\"id\": \"%s\", \"title\": \"%s\", \"file\": \"%s\"%s}%s\n", \
                    json_esc(ready_id[i]), json_esc(ready_title[i]), json_esc(ready_file[i]), wip_field, comma
            }
            print "]"
        }
    } else {
        if (nready == 0) {
            if (ntix == 0) {
                print "No tickets found."
            } else if (nopen == 0) {
                printf "All %d tickets are closed.\n", ntix
            } else {
                printf "%d open tickets, all blocked.\n", nopen
            }
        } else {
            printf "Ready tickets (%d):\n", nready
            for (i = 1; i <= nready; i++) {
                suffix = ""
                if (ready_id[i] in wip) suffix = "  (wip: " wip[ready_id[i]] ")"
                printf "  %-8s %-40s %s%s\n", ready_id[i], ready_file[i], ready_title[i], suffix
            }
        }
    }
}

function json_esc(s) {
    gsub(/\\/, "\\\\", s)
    gsub(/"/, "\\\"", s)
    gsub(/\n/, "\\n", s)
    gsub(/\r/, "\\r", s)
    gsub(/\t/, "\\t", s)
    return s
}
' $file_list
