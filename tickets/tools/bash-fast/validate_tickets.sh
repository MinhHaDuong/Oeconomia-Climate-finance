#!/usr/bin/env bash
# Validate .ticket files: required headers, unique IDs, valid references, cycle detection.
# Fast variant using awk for single-pass parsing.
#
# Usage:
#     validate_tickets.sh [tickets/]
#     validate_tickets.sh tickets/foo.ticket tickets/bar.ticket
#
# Exit 0 on success, exit 1 with diagnostics on failure.
#
# Deps: bash, awk, sort, cut (standard on any dev machine with git)

set -euo pipefail

# ---------------------------------------------------------------------------
# Parse all ticket files in a single awk pass.
# Output: tab-separated records, one per ticket, to stdout.
# Format: FILENAME \t ID \t FILENAME_ID \t STATUS \t BLOCKED_BY \t XPHASES \t HEADERS
#   BLOCKED_BY and XPHASES are comma-separated lists.
#   HEADERS is a comma-separated list of header names found.
# ---------------------------------------------------------------------------
parse_all_tickets() {
    awk '
    BEGIN { section = "headers" }

    # When we start a new file, emit the previous record
    FNR == 1 {
        if (NR > 1) emit()
        reset()
        file = FILENAME
        # Extract filename (basename)
        n = split(file, parts, "/")
        fname = parts[n]
        # Extract filename ID (before first dash)
        stem = fname
        sub(/\.ticket$/, "", stem)
        idx = index(stem, "-")
        fn_id = (idx > 0) ? substr(stem, 1, idx - 1) : stem
    }

    section == "headers" {
        # Blank line ends headers
        if ($0 ~ /^[[:space:]]*$/) { section = "gap"; next }
        # Parse "Key: value" — portable (no gawk match-with-array)
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
    # body: skip all remaining lines
    section == "body" { next }

    function reset() {
        section = "headers"
        tid = ""; status = ""; blocked = ""; xphases = ""; hdrs = ""
    }
    function emit() {
        printf "%s\x01%s\x01%s\x01%s\x01%s\x01%s\x01%s\n", fname, tid, fn_id, status, blocked, xphases, hdrs
    }
    END { if (NR > 0) emit() }
    ' "$@"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local -a args=("$@")
    if [[ ${#args[@]} -eq 0 ]]; then
        args=("tickets/")
    fi

    # Collect ticket files
    local -a files=()
    local arg
    for arg in "${args[@]}"; do
        if [[ -d "$arg" ]]; then
            local f
            for f in "$arg"/*.ticket; do
                [[ -e "$f" ]] && files+=("$f")
            done
        elif [[ -f "$arg" && "$arg" == *.ticket ]]; then
            files+=("$arg")
        else
            echo "WARNING: skipping $arg (not a .ticket file or directory)"
        fi
    done

    if [[ ${#files[@]} -eq 0 ]]; then
        echo "No .ticket files found."
        exit 0
    fi

    # Collect archived IDs (valid Blocked-by targets but not validated)
    local -A extra_ids=()
    for arg in "${args[@]}"; do
        if [[ -d "$arg" ]]; then
            local archive_dir="${arg%/}/archive"
            if [[ -d "$archive_dir" ]]; then
                local af
                for af in "$archive_dir"/*.ticket; do
                    [[ -e "$af" ]] || continue
                    local aid
                    aid=$(awk '/^Id[[:space:]]*:/ { sub(/^Id[[:space:]]*:[[:space:]]*/, ""); sub(/[[:space:]]*$/, ""); print; exit }' "$af")
                    [[ -n "$aid" ]] && extra_ids["$aid"]=1
                done
            fi
        fi
    done

    # Single-pass parse
    local parsed
    parsed=$(parse_all_tickets "${files[@]}")

    # Build ID maps and validate
    local -a errors=()
    local -A id_to_files=()
    local -A id_to_status=()
    local -A all_ids=()
    local -a ticket_data=()
    local count=0

    while IFS=$'\x01' read -r fname tid fn_id status blocked xphases hdrs; do
        (( ++count )) || true
        ticket_data+=("$fname|$tid|$fn_id|$status|$blocked|$xphases|$hdrs")

        if [[ -n "$tid" ]]; then
            all_ids["$tid"]=1
            id_to_status["$tid"]="$status"
            if [[ -n "${id_to_files[$tid]:-}" ]]; then
                id_to_files["$tid"]="${id_to_files[$tid]},$fname"
            else
                id_to_files["$tid"]="$fname"
            fi
        fi
    done <<< "$parsed"

    # Add archived IDs
    for aid in "${!extra_ids[@]}"; do
        all_ids["$aid"]=1
    done

    # Check for duplicate IDs
    for tid in $(printf '%s\n' "${!id_to_files[@]}" | sort); do
        local files_str="${id_to_files[$tid]}"
        local file_count
        file_count=$(echo "$files_str" | tr ',' '\n' | wc -l)
        if (( file_count > 1 )); then
            local base
            base=$(echo "$tid" | sed 's/[0-9]*$//')
            local max_num=1
            for other_id in "${!id_to_files[@]}"; do
                if [[ "$other_id" == "$base" ]]; then
                    (( 1 > max_num )) && max_num=1
                elif [[ "$other_id" == "$base"* ]]; then
                    local suffix="${other_id#$base}"
                    if [[ "$suffix" =~ ^[0-9]+$ ]]; then
                        (( suffix > max_num )) && max_num="$suffix"
                    fi
                fi
            done
            local next_num=$(( max_num + 1 ))
            errors+=("duplicate Id '${tid}' in: ${files_str} -- next available: ${base}${next_num}")
        fi
    done

    # Per-ticket validation
    local entry
    for entry in "${ticket_data[@]}"; do
        IFS='|' read -r fname tid fn_id status blocked xphases hdrs <<< "$entry"

        # Required headers
        local hdr
        for hdr in Id Title Author Status Created; do
            if [[ ",$hdrs," != *",$hdr,"* ]]; then
                errors+=("${fname}: missing required header '${hdr}'")
            fi
        done

        # Id/filename consistency
        if [[ -n "$tid" && "$fn_id" != "$tid" ]]; then
            errors+=("${fname}: Id '${tid}' does not match filename prefix '${fn_id}'")
        fi

        # Valid Status
        if [[ -n "$status" ]]; then
            case "$status" in
                closed|doing|open|pending) ;;
                *) errors+=("${fname}: invalid Status '${status}' (expected one of: closed, doing, open, pending)") ;;
            esac
        fi

        # Valid X-Phase(s)
        if [[ -n "$xphases" ]]; then
            IFS=',' read -ra phase_arr <<< "$xphases"
            local phase
            for phase in "${phase_arr[@]}"; do
                case "$phase" in
                    celebrating|doing|dreaming|planning) ;;
                    *) errors+=("${fname}: invalid X-Phase '${phase}' (expected one of: celebrating, doing, dreaming, planning)") ;;
                esac
            done
        fi

        # Blocked-by references exist
        if [[ -n "$blocked" ]]; then
            IFS=',' read -ra ref_arr <<< "$blocked"
            local ref
            for ref in "${ref_arr[@]}"; do
                if [[ -z "${all_ids[$ref]:-}" ]]; then
                    errors+=("${fname}: Blocked-by '${ref}' references unknown ticket ID")
                fi
            done
        fi
    done

    # Cycle detection via DFS
    # Build adjacency: id -> comma-separated blocked-by
    local -A adj=()
    local -A color=()
    for entry in "${ticket_data[@]}"; do
        IFS='|' read -r fname tid fn_id status blocked xphases hdrs <<< "$entry"
        [[ -z "$tid" ]] && continue
        adj["$tid"]="$blocked"
        color["$tid"]=0
    done

    dfs_visit() {
        local node="$1"
        shift
        local -a path=("$@")

        color["$node"]=1
        path+=("$node")

        if [[ -n "${adj[$node]:-}" ]]; then
            IFS=',' read -ra neighbors <<< "${adj[$node]}"
            local neighbor
            for neighbor in "${neighbors[@]}"; do
                [[ -z "${color[$neighbor]+x}" ]] && continue
                if [[ "${color[$neighbor]}" == "1" ]]; then
                    local cycle_str="" found=false p
                    for p in "${path[@]}"; do
                        [[ "$p" == "$neighbor" ]] && found=true
                        if [[ "$found" == "true" ]]; then
                            [[ -n "$cycle_str" ]] && cycle_str+=" -> "
                            cycle_str+="$p"
                        fi
                    done
                    cycle_str+=" -> $neighbor"
                    errors+=("dependency cycle: $cycle_str")
                elif [[ "${color[$neighbor]}" == "0" ]]; then
                    dfs_visit "$neighbor" "${path[@]}"
                fi
            done
        fi

        color["$node"]=2
    }

    for tid in $(printf '%s\n' "${!adj[@]}" | sort); do
        if [[ "${color[$tid]}" == "0" ]]; then
            dfs_visit "$tid"
        fi
    done

    # Report
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "TICKET VALIDATION FAILED (${#errors[@]} error(s)):"
        for e in "${errors[@]}"; do
            echo "  $e"
        done
        exit 1
    fi

    echo "TICKET VALIDATION: PASS (${count} tickets)"
    exit 0
}

main "$@"
