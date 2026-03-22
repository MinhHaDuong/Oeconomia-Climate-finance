#!/usr/bin/env bash
# Find open tickets whose blockers are all resolved.
#
# Usage:
#     ready_tickets.sh [tickets/]
#     ready_tickets.sh --json
#
# A ticket is "ready" when:
#   - Status is open (not doing, not closed)
#   - Every Blocked-by reference points to a closed ticket (or doesn't exist)

set -euo pipefail

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
declare -a TICKET_FILES=()
declare -A TICKET_ID=()
declare -A TICKET_TITLE=()
declare -A TICKET_STATUS=()
declare -A STATUS_BY_ID=()

TMPDIR_PARSE=""
cleanup() { [[ -n "$TMPDIR_PARSE" ]] && rm -rf "$TMPDIR_PARSE"; }
trap cleanup EXIT
TMPDIR_PARSE=$(mktemp -d)

# ---------------------------------------------------------------------------
# Parser (simplified — only needs Id, Title, Status, Blocked-by)
# ---------------------------------------------------------------------------
parse_ticket() {
    local filepath="$1"
    local filename
    filename=$(basename "$filepath")
    local section="headers"
    local body_seen=false
    local blocked_file="$TMPDIR_PARSE/${filename}.blocked_by"
    : > "$blocked_file"

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$body_seen" == "false" ]]; then
            local trimmed
            trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [[ "$trimmed" == "--- log ---" ]]; then section="log"; continue; fi
            if [[ "$trimmed" == "--- body ---" ]]; then section="body"; body_seen=true; continue; fi
        fi

        case "$section" in
            headers)
                [[ -z "$(echo "$line" | tr -d '[:space:]')" ]] && section="gap" && continue
                if [[ "$line" =~ ^([A-Za-z][A-Za-z0-9_-]*)[[:space:]]*:[[:space:]]*(.*) ]]; then
                    local key="${BASH_REMATCH[1]}"
                    local val="${BASH_REMATCH[2]}"
                    val=$(echo "$val" | sed 's/[[:space:]]*$//')
                    case "$key" in
                        Id)         TICKET_ID["$filename"]="$val" ;;
                        Title)      TICKET_TITLE["$filename"]="$val" ;;
                        Status)     TICKET_STATUS["$filename"]="$val" ;;
                        Blocked-by) echo "$val" >> "$blocked_file" ;;
                    esac
                fi
                ;;
            gap|log|body) ;;
        esac
    done < "$filepath"
}

load_tickets() {
    local dir="$1"
    for f in "$dir"/*.ticket; do
        [[ -e "$f" ]] || continue
        parse_ticket "$f"
        TICKET_FILES+=("$(basename "$f")")
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local use_json=false
    local -a pos_args=()

    for arg in "$@"; do
        if [[ "$arg" == "--json" ]]; then
            use_json=true
        else
            pos_args+=("$arg")
        fi
    done

    local ticket_dir="${pos_args[0]:-tickets}"

    if [[ ! -d "$ticket_dir" ]]; then
        echo "Directory not found: $ticket_dir"
        exit 1
    fi

    load_tickets "$ticket_dir"

    # Build status lookup by ID
    for filename in "${TICKET_FILES[@]}"; do
        local tid="${TICKET_ID[$filename]:-}"
        local st="${TICKET_STATUS[$filename]:-}"
        [[ -n "$tid" ]] && STATUS_BY_ID["$tid"]="$st"
    done

    # Find ready tickets
    declare -a ready_ids=()
    declare -a ready_files=()
    declare -a ready_titles=()
    declare -a warnings=()

    for filename in "${TICKET_FILES[@]}"; do
        local st="${TICKET_STATUS[$filename]:-}"
        [[ "$st" != "open" ]] && continue

        local blocked=false
        local blocked_file="$TMPDIR_PARSE/${filename}.blocked_by"
        if [[ -s "$blocked_file" ]]; then
            while IFS= read -r ref; do
                local ref_status="${STATUS_BY_ID[$ref]:-}"
                if [[ -z "$ref_status" ]]; then
                    warnings+=("${filename}: Blocked-by '${ref}' not found (treating as satisfied)")
                elif [[ "$ref_status" != "closed" ]]; then
                    blocked=true
                    break
                fi
            done < "$blocked_file"
        fi

        if [[ "$blocked" == "false" ]]; then
            ready_ids+=("${TICKET_ID[$filename]:-}")
            ready_files+=("$filename")
            ready_titles+=("${TICKET_TITLE[$filename]:-}")
        fi
    done

    # Print warnings to stderr
    for w in "${warnings[@]+"${warnings[@]}"}"; do
        echo "WARNING: $w" >&2
    done

    # Output
    if [[ "$use_json" == "true" ]]; then
        if [[ ${#ready_ids[@]} -eq 0 ]]; then
            echo "[]"
        else
            echo "["
            local i
            for (( i=0; i<${#ready_ids[@]}; i++ )); do
                local comma=","
                (( i == ${#ready_ids[@]} - 1 )) && comma=""
                printf '  {\n    "id": "%s",\n    "title": "%s",\n    "file": "%s"\n  }%s\n' \
                    "${ready_ids[$i]}" "${ready_titles[$i]}" "${ready_files[$i]}" "$comma"
            done
            echo "]"
        fi
    else
        if [[ ${#ready_ids[@]} -eq 0 ]]; then
            echo "No ready tickets."
        else
            echo "Ready tickets (${#ready_ids[@]}):"
            for (( i=0; i<${#ready_ids[@]}; i++ )); do
                printf "  %-8s %-40s %s\n" "${ready_ids[$i]}" "${ready_files[$i]}" "${ready_titles[$i]}"
            done
        fi
    fi

    exit 0
}

main "$@"
