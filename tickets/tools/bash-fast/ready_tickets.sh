#!/usr/bin/env bash
# Find open tickets whose blockers are all resolved.
# Fast variant using awk for single-pass parsing.
#
# Usage:
#     ready_tickets.sh [tickets/]
#     ready_tickets.sh --json [tickets/]
#
# Deps: bash, awk, sort (standard on any dev machine with git)

set -euo pipefail

# Single-pass awk parser: extracts Id, Title, Status, Blocked-by per file.
# Output: FILENAME \t ID \t TITLE \t STATUS \t BLOCKED_BY(comma-sep)
parse_all_tickets() {
    awk '
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
    function emit() { printf "%s\x01%s\x01%s\x01%s\x01%s\n", fname, tid, title, status, blocked }
    END { if (NR > 0) emit() }
    ' "$@"
}

main() {
    local use_json=false
    local -a args=()

    for a in "$@"; do
        if [[ "$a" == "--json" ]]; then
            use_json=true
        else
            args+=("$a")
        fi
    done

    local ticket_dir="${args[0]:-tickets}"

    if [[ ! -d "$ticket_dir" ]]; then
        echo "Directory not found: $ticket_dir"
        exit 1
    fi

    local -a files=()
    local f
    for f in "$ticket_dir"/*.ticket; do
        [[ -e "$f" ]] && files+=("$f")
    done

    if [[ ${#files[@]} -eq 0 ]]; then
        if [[ "$use_json" == "true" ]]; then
            echo "[]"
        else
            echo "No ready tickets."
        fi
        exit 0
    fi

    local parsed
    parsed=$(parse_all_tickets "${files[@]}")

    # Build status-by-id map
    local -A status_by_id=()
    while IFS=$'\x01' read -r fname tid title status blocked; do
        [[ -n "$tid" ]] && status_by_id["$tid"]="$status"
    done <<< "$parsed"

    # Find ready tickets
    local -a ready_ids=() ready_files=() ready_titles=()
    while IFS=$'\x01' read -r fname tid title status blocked; do
        [[ "$status" != "open" ]] && continue

        local is_blocked=false
        if [[ -n "$blocked" ]]; then
            IFS=',' read -ra refs <<< "$blocked"
            for ref in "${refs[@]}"; do
                local ref_status="${status_by_id[$ref]:-}"
                if [[ -z "$ref_status" ]]; then
                    echo "WARNING: ${fname}: Blocked-by '${ref}' not found (treating as satisfied)" >&2
                elif [[ "$ref_status" != "closed" ]]; then
                    is_blocked=true
                    break
                fi
            done
        fi

        if [[ "$is_blocked" == "false" ]]; then
            ready_ids+=("$tid")
            ready_files+=("$fname")
            ready_titles+=("$title")
        fi
    done <<< "$parsed"

    # Output
    if [[ "$use_json" == "true" ]]; then
        if [[ ${#ready_ids[@]} -eq 0 ]]; then
            echo "[]"
        else
            echo "["
            local i
            for (( i=0; i<${#ready_ids[@]}; i++ )); do
                local comma=""
                (( i < ${#ready_ids[@]} - 1 )) && comma=","
                printf '  {"id": "%s", "title": "%s", "file": "%s"}%s\n' \
                    "${ready_ids[$i]}" "${ready_titles[$i]}" "${ready_files[$i]}" "$comma"
            done
            echo "]"
        fi
    else
        if [[ ${#ready_ids[@]} -eq 0 ]]; then
            echo "No ready tickets."
        else
            echo "Ready tickets (${#ready_ids[@]}):"
            local i
            for (( i=0; i<${#ready_ids[@]}; i++ )); do
                printf "  %-8s %-40s %s\n" "${ready_ids[$i]}" "${ready_files[$i]}" "${ready_titles[$i]}"
            done
        fi
    fi
}

main "$@"
