#!/usr/bin/env bash
# Validate .ticket files: required headers, unique IDs, valid references, cycle detection.
#
# Usage:
#     validate_tickets.sh [tickets/]
#     validate_tickets.sh tickets/foo.ticket tickets/bar.ticket
#
# Exit 0 on success, exit 1 with diagnostics on failure.

set -euo pipefail

REQUIRED_HEADERS="Id Title Author Status Created"
VALID_STATUSES="closed doing open pending"
VALID_PHASES="celebrating doing dreaming planning"

# ---------------------------------------------------------------------------
# Parser: parse_ticket FILE
#   Outputs header lines as KEY=VALUE, one per line, to stdout.
#   Sets global arrays via temp files for multi-value fields.
# ---------------------------------------------------------------------------

# We store parsed data in temp files keyed by ticket path.
TMPDIR_PARSE=""

cleanup() {
    [[ -n "$TMPDIR_PARSE" ]] && rm -rf "$TMPDIR_PARSE"
}
trap cleanup EXIT

TMPDIR_PARSE=$(mktemp -d)

# Global accumulators
declare -a ALL_ERRORS=()
declare -a ALL_TICKET_FILES=()

# Associative arrays for ticket data
declare -A TICKET_ID=()         # file -> id
declare -A TICKET_TITLE=()      # file -> title
declare -A TICKET_STATUS=()     # file -> status
declare -A TICKET_FILENAME_ID=()  # file -> filename-derived id

# Per-ticket headers stored in temp files:
#   $TMPDIR_PARSE/<file>.blocked_by   (one ref per line)
#   $TMPDIR_PARSE/<file>.xphase       (one phase per line)
#   $TMPDIR_PARSE/<file>.headers      (one "Key" per line, may repeat)

parse_ticket() {
    local filepath="$1"
    local filename
    filename=$(basename "$filepath")
    local section="headers"
    local body_seen=false

    local hdr_file="$TMPDIR_PARSE/${filename}.headers"
    local blocked_file="$TMPDIR_PARSE/${filename}.blocked_by"
    local phase_file="$TMPDIR_PARSE/${filename}.xphase"

    : > "$hdr_file"
    : > "$blocked_file"
    : > "$phase_file"

    # Extract filename ID (part before first dash)
    local stem="${filename%.ticket}"
    local fn_id="${stem%%-*}"
    # If there's no dash, fn_id == stem, which is fine
    TICKET_FILENAME_ID["$filename"]="$fn_id"

    while IFS= read -r line || [[ -n "$line" ]]; do
        # Check for section markers (only before body)
        if [[ "$body_seen" == "false" ]]; then
            local trimmed
            trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [[ "$trimmed" == "--- log ---" ]]; then
                section="log"
                continue
            fi
            if [[ "$trimmed" == "--- body ---" ]]; then
                section="body"
                body_seen=true
                continue
            fi
        fi

        case "$section" in
            headers)
                # Blank line ends headers
                if [[ -z "$(echo "$line" | tr -d '[:space:]')" ]]; then
                    section="gap"
                    continue
                fi
                # Parse "Key: value"
                if [[ "$line" =~ ^([A-Za-z][A-Za-z0-9_-]*)[[:space:]]*:[[:space:]]*(.*) ]]; then
                    local key="${BASH_REMATCH[1]}"
                    local val="${BASH_REMATCH[2]}"
                    val=$(echo "$val" | sed 's/[[:space:]]*$//')
                    echo "$key" >> "$hdr_file"

                    case "$key" in
                        Id)
                            TICKET_ID["$filename"]="$val"
                            ;;
                        Title)
                            TICKET_TITLE["$filename"]="$val"
                            ;;
                        Status)
                            TICKET_STATUS["$filename"]="$val"
                            ;;
                        Blocked-by)
                            echo "$val" >> "$blocked_file"
                            ;;
                        X-Phase)
                            echo "$val" >> "$phase_file"
                            ;;
                    esac
                fi
                ;;
            gap)
                # Ignore lines between header block and section separators
                ;;
            log)
                # We don't need log lines for validation
                ;;
            body)
                # We don't need body for validation
                ;;
        esac
    done < "$filepath"
}

load_tickets() {
    local dir="$1"
    local f
    for f in "$dir"/*.ticket; do
        [[ -e "$f" ]] || continue
        parse_ticket "$f"
        ALL_TICKET_FILES+=("$(basename "$f")")
    done
}

validate_tickets() {
    # Collect all IDs for reference checking
    declare -A id_to_files
    local filename tid

    for filename in "${ALL_TICKET_FILES[@]}"; do
        tid="${TICKET_ID[$filename]:-}"
        if [[ -n "$tid" ]]; then
            if [[ -n "${id_to_files[$tid]:-}" ]]; then
                id_to_files["$tid"]="${id_to_files[$tid]} $filename"
            else
                id_to_files["$tid"]="$filename"
            fi
        fi
    done

    # Check for duplicate IDs
    for tid in $(echo "${!id_to_files[@]}" | tr ' ' '\n' | sort); do
        local files="${id_to_files[$tid]}"
        local count
        count=$(echo "$files" | wc -w)
        if (( count > 1 )); then
            # Format files with commas
            local files_csv
            files_csv=$(echo "$files" | tr ' ' '\n' | sort | paste -sd', ')
            # Compute next available suffix
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
            ALL_ERRORS+=("duplicate Id '${tid}' in: ${files_csv} -- next available: ${base}${next_num}")
        fi
    done

    # Build the set of all known IDs (live + extra/archived)
    declare -A all_ids
    for tid in "${!id_to_files[@]}"; do
        all_ids["$tid"]=1
    done
    for tid in "${EXTRA_IDS[@]:-}"; do
        [[ -n "$tid" ]] && all_ids["$tid"]=1
    done

    # Per-ticket validation
    for filename in "${ALL_TICKET_FILES[@]}"; do
        local hdr_file="$TMPDIR_PARSE/${filename}.headers"
        local blocked_file="$TMPDIR_PARSE/${filename}.blocked_by"
        local phase_file="$TMPDIR_PARSE/${filename}.xphase"

        # Required headers
        for hdr in $REQUIRED_HEADERS; do
            if ! grep -qx "$hdr" "$hdr_file" 2>/dev/null; then
                ALL_ERRORS+=("${filename}: missing required header '${hdr}'")
            fi
        done

        # Id/filename consistency
        local file_tid="${TICKET_ID[$filename]:-}"
        local file_fnid="${TICKET_FILENAME_ID[$filename]:-}"
        if [[ -n "$file_tid" && "$file_fnid" != "$file_tid" ]]; then
            ALL_ERRORS+=("${filename}: Id '${file_tid}' does not match filename prefix '${file_fnid}'")
        fi

        # Valid Status
        local file_status="${TICKET_STATUS[$filename]:-}"
        if [[ -n "$file_status" ]]; then
            local status_valid=false
            for s in $VALID_STATUSES; do
                [[ "$file_status" == "$s" ]] && status_valid=true && break
            done
            if [[ "$status_valid" == "false" ]]; then
                ALL_ERRORS+=("${filename}: invalid Status '${file_status}' (expected one of: closed, doing, open, pending)")
            fi
        fi

        # Valid X-Phase
        if [[ -s "$phase_file" ]]; then
            while IFS= read -r phase; do
                local phase_valid=false
                for p in $VALID_PHASES; do
                    [[ "$phase" == "$p" ]] && phase_valid=true && break
                done
                if [[ "$phase_valid" == "false" ]]; then
                    ALL_ERRORS+=("${filename}: invalid X-Phase '${phase}' (expected one of: celebrating, doing, dreaming, planning)")
                fi
            done < "$phase_file"
        fi

        # Blocked-by references exist
        if [[ -s "$blocked_file" ]]; then
            while IFS= read -r ref; do
                if [[ -z "${all_ids[$ref]:-}" ]]; then
                    ALL_ERRORS+=("${filename}: Blocked-by '${ref}' references unknown ticket ID")
                fi
            done < "$blocked_file"
        fi
    done

    # Cycle detection via DFS
    detect_cycles
}

detect_cycles() {
    # Build adjacency list from ticket blocked-by relationships
    # We use temp files for the DFS state

    declare -A adj       # id -> space-separated blocked-by ids
    declare -A color     # id -> 0(white) 1(gray) 2(black)

    for filename in "${ALL_TICKET_FILES[@]}"; do
        local tid="${TICKET_ID[$filename]:-}"
        [[ -z "$tid" ]] && continue
        local blocked_file="$TMPDIR_PARSE/${filename}.blocked_by"
        local deps=""
        if [[ -s "$blocked_file" ]]; then
            deps=$(tr '\n' ' ' < "$blocked_file")
        fi
        adj["$tid"]="$deps"
        color["$tid"]=0
    done

    # DFS with explicit path tracking
    dfs_visit() {
        local node="$1"
        shift
        local -a path=("$@")

        color["$node"]=1
        path+=("$node")

        local neighbor
        for neighbor in ${adj[$node]:-}; do
            # Skip unknown IDs
            [[ -z "${color[$neighbor]+x}" ]] && continue

            if [[ "${color[$neighbor]}" == "1" ]]; then
                # Found cycle - extract from path
                local cycle_str=""
                local found=false
                for p in "${path[@]}"; do
                    if [[ "$p" == "$neighbor" ]]; then
                        found=true
                    fi
                    if [[ "$found" == "true" ]]; then
                        [[ -n "$cycle_str" ]] && cycle_str+=" -> "
                        cycle_str+="$p"
                    fi
                done
                cycle_str+=" -> $neighbor"
                ALL_ERRORS+=("dependency cycle: $cycle_str")
            elif [[ "${color[$neighbor]}" == "0" ]]; then
                dfs_visit "$neighbor" "${path[@]}"
            fi
        done

        color["$node"]=2
    }

    for tid in $(echo "${!adj[@]}" | tr ' ' '\n' | sort); do
        if [[ "${color[$tid]}" == "0" ]]; then
            dfs_visit "$tid"
        fi
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    local -a args=("$@")
    declare -a EXTRA_IDS=()

    if [[ ${#args[@]} -eq 0 ]]; then
        args=("tickets/")
    fi

    local arg
    for arg in "${args[@]}"; do
        if [[ -d "$arg" ]]; then
            load_tickets "$arg"
        elif [[ -f "$arg" && "$arg" == *.ticket ]]; then
            parse_ticket "$arg"
            ALL_TICKET_FILES+=("$(basename "$arg")")
        else
            echo "WARNING: skipping $arg (not a .ticket file or directory)"
        fi
    done

    if [[ ${#ALL_TICKET_FILES[@]} -eq 0 ]]; then
        echo "No .ticket files found."
        exit 0
    fi

    # Load archived ticket IDs as extra valid Blocked-by targets
    for arg in "${args[@]}"; do
        if [[ -d "$arg" ]]; then
            local archive_dir="${arg%/}/archive"
            if [[ -d "$archive_dir" ]]; then
                local af
                for af in "$archive_dir"/*.ticket; do
                    [[ -e "$af" ]] || continue
                    # Quick parse: just extract the Id header
                    local aid
                    aid=$(grep -m1 '^Id[[:space:]]*:' "$af" 2>/dev/null | sed 's/^Id[[:space:]]*:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    if [[ -n "$aid" ]]; then
                        EXTRA_IDS+=("$aid")
                    fi
                done
            fi
        fi
    done

    validate_tickets

    if [[ ${#ALL_ERRORS[@]} -gt 0 ]]; then
        echo "TICKET VALIDATION FAILED (${#ALL_ERRORS[@]} error(s)):"
        for e in "${ALL_ERRORS[@]}"; do
            echo "  $e"
        done
        exit 1
    fi

    echo "TICKET VALIDATION: PASS (${#ALL_TICKET_FILES[@]} tickets)"
    exit 0
}

main "$@"
