#!/usr/bin/env bash
# DAG-safe archival of old closed tickets.
# Fast variant using awk for single-pass parsing.
#
# Usage:
#     archive_tickets.sh [tickets/] [--days N] [--execute]
#
# Default: dry-run. Pass --execute to actually move files and commit.
#
# Deps: bash, awk, sort, date, git (standard on any dev machine)

set -euo pipefail

DAG_HEADERS="Blocked-by X-Discovered-from X-Supersedes"

# Single-pass awk parser: extracts Id, Status, last log timestamp, DAG refs.
# Output: FILENAME \t ID \t STATUS \t LAST_LOG_TS \t DAG_REFS(comma-sep)
parse_all_tickets() {
    awk -v dag_hdrs="Blocked-by,X-Discovered-from,X-Supersedes" '
    BEGIN { split(dag_hdrs, dh, ",") }
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
        # Track last non-empty log line timestamp
        if ($0 ~ /[^[:space:]]/) {
            if (match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z?/)) {
                last_ts = substr($0, RSTART, RLENGTH)
            }
        }
        next
    }
    section == "body" { next }
    function reset() {
        section = "headers"; tid = ""; status = ""; last_ts = ""; dag_refs = ""
    }
    function emit() {
        printf "%s\x01%s\x01%s\x01%s\x01%s\n", fname, tid, status, last_ts, dag_refs
    }
    END { if (NR > 0) emit() }
    ' "$@"
}

main() {
    local execute=false
    local days=90
    local ticket_dir="tickets"
    local -a positional=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --execute) execute=true; shift ;;
            --days=*) days="${1#--days=}"; shift ;;
            --days) days="$2"; shift 2 ;;
            --*) shift ;;
            *) positional+=("$1"); shift ;;
        esac
    done

    [[ ${#positional[@]} -gt 0 ]] && ticket_dir="${positional[0]}"

    if [[ ! -d "$ticket_dir" ]]; then
        echo "Directory not found: $ticket_dir"
        exit 1
    fi

    # Collect all ticket files (live + archived) for DAG reference scan
    local -a live_files=() all_files=()
    local f
    for f in "$ticket_dir"/*.ticket; do
        [[ -e "$f" ]] && live_files+=("$f") && all_files+=("$f")
    done
    local archive_dir="${ticket_dir%/}/archive"
    if [[ -d "$archive_dir" ]]; then
        for f in "$archive_dir"/*.ticket; do
            [[ -e "$f" ]] && all_files+=("$f")
        done
    fi

    if [[ ${#live_files[@]} -eq 0 ]]; then
        echo "Nothing to archive (threshold: ${days} days)."
        exit 0
    fi

    # Parse all files in one pass
    local parsed
    parsed=$(parse_all_tickets "${all_files[@]}")

    # Collect all referenced IDs (from DAG headers across all tickets)
    local -A referenced_ids=()
    while IFS=$'\x01' read -r fname tid status last_ts dag_refs; do
        if [[ -n "$dag_refs" ]]; then
            IFS=',' read -ra refs <<< "$dag_refs"
            for ref in "${refs[@]}"; do
                referenced_ids["$ref"]=1
            done
        fi
    done <<< "$parsed"

    # Compute cutoff timestamp
    local cutoff_epoch
    cutoff_epoch=$(date -d "-${days} days" +%s 2>/dev/null || date -v-${days}d +%s 2>/dev/null)

    # Find archivable candidates from live files only
    local -a archivable=() dag_protected=()
    # Re-parse only live files for candidate selection
    local live_parsed
    live_parsed=$(parse_all_tickets "${live_files[@]}")

    while IFS=$'\x01' read -r fname tid status last_ts dag_refs; do
        [[ "$status" != "closed" ]] && continue
        [[ -z "$last_ts" ]] && continue

        # Parse timestamp
        local ts_clean="$last_ts"
        [[ "$ts_clean" != *Z ]] && ts_clean="${ts_clean}Z"
        # Convert ISO to epoch (GNU date or BSD date)
        local ts_epoch
        ts_epoch=$(date -d "${ts_clean}" +%s 2>/dev/null || date -jf "%Y-%m-%dT%H:%M:%SZ" "${ts_clean}" +%s 2>/dev/null || echo 0)

        (( ts_epoch >= cutoff_epoch )) && continue

        # DAG protection check
        if [[ -n "${referenced_ids[$tid]:-}" ]]; then
            dag_protected+=("$tid")
        else
            archivable+=("$fname")
        fi
    done <<< "$live_parsed"

    if [[ ${#dag_protected[@]} -gt 0 ]]; then
        local protected_list
        protected_list=$(printf '%s\n' "${dag_protected[@]}" | sort | paste -sd', ')
        echo "DAG-protected (skipping ${#dag_protected[@]}): ${protected_list}"
    fi

    if [[ ${#archivable[@]} -eq 0 ]]; then
        echo "Nothing to archive (threshold: ${days} days)."
        exit 0
    fi

    local archivable_ids
    archivable_ids=$(printf '%s\n' "${archivable[@]}" | sed 's/-.*//' | sort | paste -sd', ')
    echo "Will archive ${#archivable[@]} ticket(s): ${archivable_ids}"

    if [[ "$execute" != "true" ]]; then
        echo "Dry run. Pass --execute to proceed."
        exit 0
    fi

    mkdir -p "$archive_dir"
    for fname in "${archivable[@]}"; do
        git mv "${ticket_dir}/${fname}" "${archive_dir}/${fname}"
        echo "  moved ${fname}"
    done

    local msg="archive ${#archivable[@]} closed tickets (>${days} days, DAG-safe)"
    git commit -m "$msg"
    echo "Committed: ${msg}"
}

main "$@"
