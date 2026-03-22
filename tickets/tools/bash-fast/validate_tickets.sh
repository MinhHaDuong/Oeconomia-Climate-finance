#!/bin/sh
# Validate .ticket files: required headers, unique IDs, valid references, cycle detection.
# POSIX sh + awk — runs on Alpine, Busybox, dash, any /bin/sh.
#
# Usage:
#     validate_tickets.sh [tickets/]
#     validate_tickets.sh tickets/foo.ticket tickets/bar.ticket
#
# Exit 0 on success, exit 1 with diagnostics on failure.
#
# Deps: sh, awk, sort (standard on any system with git)

set -eu

# ---------------------------------------------------------------------------
# Collect ticket files from arguments
# ---------------------------------------------------------------------------
collect_files() {
    for arg in "$@"; do
        if [ -d "$arg" ]; then
            for f in "$arg"/*.ticket; do
                [ -e "$f" ] && printf '%s\n' "$f"
            done
        elif [ -f "$arg" ] && case "$arg" in *.ticket) true;; *) false;; esac; then
            printf '%s\n' "$arg"
        else
            echo "WARNING: skipping $arg (not a .ticket file or directory)" >&2
        fi
    done
}

# Collect archived IDs
collect_archive_ids() {
    for arg in "$@"; do
        if [ -d "$arg" ]; then
            archive_dir="${arg%/}/archive"
            if [ -d "$archive_dir" ]; then
                for af in "$archive_dir"/*.ticket; do
                    [ -e "$af" ] || continue
                    awk '/^Id[[:space:]]*:/ { sub(/^Id[[:space:]]*:[[:space:]]*/, ""); sub(/[[:space:]]*$/, ""); print; exit }' "$af"
                done
            fi
        fi
    done
}

# ---------------------------------------------------------------------------
# Main — all validation logic lives in a single awk program.
# Input: ticket files on stdin (one path per line), then a separator, then
#        archived IDs (one per line).
# We feed everything to awk which does multi-file parsing + validation.
# ---------------------------------------------------------------------------

if [ $# -eq 0 ]; then
    set -- "tickets/"
fi

# Collect file list
file_list=$(collect_files "$@")
if [ -z "$file_list" ]; then
    echo "No .ticket files found."
    exit 0
fi

archive_ids=$(collect_archive_ids "$@")

# Feed file list + archive IDs into a single awk that:
#   1. Reads the file list and archive IDs from a control pipe
#   2. Parses each ticket file
#   3. Validates everything
#   4. Detects cycles via DFS
# We use a two-pass approach: first pass parses, second pass validates.
# Both passes are in awk — shell just orchestrates the pipe.

# Pass 1: Parse all tickets in one awk invocation, emit structured records.
# shellcheck disable=SC2086
parsed=$(echo "$file_list" | xargs awk '
BEGIN { section = "headers" }

FNR == 1 {
    if (NR > 1) emit()
    reset()
    file = FILENAME
    n = split(file, parts, "/")
    fname = parts[n]
    stem = fname
    sub(/\.ticket$/, "", stem)
    idx = index(stem, "-")
    fn_id = (idx > 0) ? substr(stem, 1, idx - 1) : stem
}

section == "headers" {
    if ($0 ~ /^[[:space:]]*$/) { section = "gap"; next }
    if ($0 ~ /^[A-Za-z][A-Za-z0-9_-]*[[:space:]]*:/) {
        colon = index($0, ":")
        key = substr($0, 1, colon - 1)
        val = substr($0, colon + 1)
        sub(/^[[:space:]]+/, "", key); sub(/[[:space:]]+$/, "", key)
        sub(/^[[:space:]]+/, "", val); sub(/[[:space:]]+$/, "", val)
        hdrs = hdrs (hdrs ? "," : "") key
        if (key == "Id") tid = val
        else if (key == "Status") status = val
        else if (key == "Blocked-by") blocked = blocked (blocked ? "," : "") val
        else if (key == "X-Phase") xphases = xphases (xphases ? "," : "") val
    }
    next
}
section == "gap" {
    if ($0 ~ /^[[:space:]]*--- log ---[[:space:]]*$/) { section = "log"; next }
    if ($0 ~ /^[[:space:]]*--- body ---[[:space:]]*$/) { section = "body"; next }
    next
}
section == "log" {
    if ($0 ~ /^[[:space:]]*--- body ---[[:space:]]*$/) { section = "body"; next }
    next
}
section == "body" { next }

function reset() {
    section = "headers"
    tid = ""; status = ""; blocked = ""; xphases = ""; hdrs = ""
}
function emit() {
    printf "%s\x01%s\x01%s\x01%s\x01%s\x01%s\x01%s\n", fname, tid, fn_id, status, blocked, xphases, hdrs
}
END { if (NR > 0) emit() }
')

# Pass 2: Feed parsed records + archive IDs into a validation awk program.
# This awk does all validation including cycle detection.
printf '%s\n---ARCHIVE---\n%s\n' "$parsed" "$archive_ids" | awk '
BEGIN {
    FS = "\x01"
    phase = "records"
    nerrors = 0
    ntickets = 0

    split("Id,Title,Author,Status,Created", req_hdrs, ",")
    split("closed,doing,open,pending", vs, ",")
    for (i in vs) valid_status[vs[i]] = 1
    split("celebrating,doing,dreaming,planning", vp, ",")
    for (i in vp) valid_phase[vp[i]] = 1
}

# Separator between parsed records and archive IDs
/^---ARCHIVE---$/ { phase = "archive"; next }

phase == "archive" {
    if ($0 != "") archive_id[$0] = 1
    next
}

phase == "records" {
    ntickets++
    fname  = $1; tid = $2; fn_id = $3; status = $4
    blocked = $5; xphases = $6; hdrs = $7

    # Store ticket data for cycle detection
    ticket_fname[ntickets] = fname
    ticket_id[ntickets]    = tid
    ticket_fn_id[ntickets] = fn_id
    ticket_status[ntickets]= status
    ticket_blocked[ntickets]= blocked
    ticket_xphases[ntickets]= xphases
    ticket_hdrs[ntickets]  = hdrs

    if (tid != "") {
        all_ids[tid] = 1
        id_status[tid] = status
        if (tid in id_files)
            id_files[tid] = id_files[tid] "," fname
        else
            id_files[tid] = fname
    }
    next
}

END {
    # Add archive IDs to known set
    for (aid in archive_id) all_ids[aid] = 1

    # Check duplicates
    for (tid in id_files) {
        n = split(id_files[tid], flist, ",")
        if (n > 1) {
            # Find base and next available
            base = tid; sub(/[0-9]+$/, "", base)
            max_num = 1
            for (other in id_files) {
                if (other == base) { if (1 > max_num) max_num = 1 }
                else if (index(other, base) == 1) {
                    suffix = substr(other, length(base) + 1)
                    if (suffix ~ /^[0-9]+$/ && suffix + 0 > max_num)
                        max_num = suffix + 0
                }
            }
            error(sprintf("duplicate Id '\''%s'\'' in: %s -- next available: %s%d", tid, id_files[tid], base, max_num + 1))
        }
    }

    # Per-ticket validation
    for (i = 1; i <= ntickets; i++) {
        fname = ticket_fname[i]; tid = ticket_id[i]
        fn_id = ticket_fn_id[i]; status = ticket_status[i]
        blocked = ticket_blocked[i]; xphases = ticket_xphases[i]
        hdrs = ticket_hdrs[i]

        # Required headers
        for (r in req_hdrs) {
            h = req_hdrs[r]
            if (index("," hdrs ",", "," h ",") == 0)
                error(fname ": missing required header '\''" h "'\''")
        }

        # Id/filename consistency
        if (tid != "" && fn_id != tid)
            error(fname ": Id '\''" tid "'\'' does not match filename prefix '\''" fn_id "'\''")

        # Valid Status
        if (status != "" && !(status in valid_status))
            error(fname ": invalid Status '\''" status "'\'' (expected one of: closed, doing, open, pending)")

        # Valid X-Phase
        if (xphases != "") {
            np = split(xphases, parr, ",")
            for (p = 1; p <= np; p++) {
                if (!(parr[p] in valid_phase))
                    error(fname ": invalid X-Phase '\''" parr[p] "'\'' (expected one of: celebrating, doing, dreaming, planning)")
            }
        }

        # Blocked-by references exist
        if (blocked != "") {
            nb = split(blocked, barr, ",")
            for (b = 1; b <= nb; b++) {
                if (!(barr[b] in all_ids))
                    error(fname ": Blocked-by '\''" barr[b] "'\'' references unknown ticket ID")
            }
        }
    }

    # Cycle detection via DFS
    # Build adjacency: node -> comma-separated blocked-by
    for (i = 1; i <= ntickets; i++) {
        tid = ticket_id[i]
        if (tid == "") continue
        adj[tid] = ticket_blocked[i]
        color[tid] = 0  # WHITE
    }

    # Sort IDs for deterministic output
    n_ids = asorti_simple(adj, sorted_ids)
    for (si = 1; si <= n_ids; si++) {
        tid = sorted_ids[si]
        if (color[tid] == 0)
            dfs(tid, "")
    }

    # Report
    if (nerrors > 0) {
        printf "TICKET VALIDATION FAILED (%d error(s)):\n", nerrors
        for (e = 1; e <= nerrors; e++)
            printf "  %s\n", errors[e]
        exit 1
    }
    printf "TICKET VALIDATION: PASS (%d tickets)\n", ntickets
}

function error(msg) {
    nerrors++
    errors[nerrors] = msg
}

function dfs(node, path_str,    neighbors, nn, neighbor, cycle_str, parts, np, found, p) {
    color[node] = 1  # GRAY
    if (path_str == "")
        path_str = node
    else
        path_str = path_str "," node

    if (adj[node] != "") {
        nn = split(adj[node], neighbors, ",")
        for (ni = 1; ni <= nn; ni++) {
            neighbor = neighbors[ni]
            if (!(neighbor in color)) continue
            if (color[neighbor] == 1) {
                # Found cycle — extract from path
                np = split(path_str, parts, ",")
                cycle_str = ""; found = 0
                for (p = 1; p <= np; p++) {
                    if (parts[p] == neighbor) found = 1
                    if (found) {
                        if (cycle_str != "") cycle_str = cycle_str " -> "
                        cycle_str = cycle_str parts[p]
                    }
                }
                cycle_str = cycle_str " -> " neighbor
                error("dependency cycle: " cycle_str)
            } else if (color[neighbor] == 0) {
                dfs(neighbor, path_str)
            }
        }
    }
    color[node] = 2  # BLACK
}

# Simple sort of array keys (POSIX awk has no asorti)
function asorti_simple(arr, dest,    k, n, i, j, tmp) {
    n = 0
    for (k in arr) { n++; dest[n] = k }
    # Insertion sort
    for (i = 2; i <= n; i++) {
        tmp = dest[i]
        j = i - 1
        while (j >= 1 && dest[j] > tmp) {
            dest[j+1] = dest[j]
            j--
        }
        dest[j+1] = tmp
    }
    return n
}
'
