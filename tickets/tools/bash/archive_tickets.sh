#!/usr/bin/env bash
# DAG-safe archival of old closed tickets.
#
# Usage:
#     archive_tickets.sh [tickets/] [--days N] [--execute]
#
# Default: dry-run. Pass --execute to actually move files and commit.
# Exit 0 on success, exit 1 on error.

set -euo pipefail

DAG_HEADERS="Blocked-by X-Discovered-from X-Supersedes"

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
declare -a TICKET_FILES=()
declare -A TICKET_ID=()
declare -A TICKET_STATUS=()
declare -A TICKET_PATH=()      # filename -> full path
declare -A TICKET_LAST_LOG=()  # filename -> last log timestamp string

TMPDIR_PARSE=""
cleanup() { [[ -n "$TMPDIR_PARSE" ]] && rm -rf "$TMPDIR_PARSE"; }
trap cleanup EXIT
TMPDIR_PARSE=$(mktemp -d)

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
parse_ticket() {
    local filepath="$1"
    local filename
    filename=$(basename "$filepath")
    local section="headers"
    local body_seen=false
    local dag_file="$TMPDIR_PARSE/${filename}.dag_refs"
    : > "$dag_file"

    TICKET_PATH["$filename"]="$filepath"

    local last_log_ts=""

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
                        Id)     TICKET_ID["$filename"]="$val" ;;
                        Status) TICKET_STATUS["$filename"]="$val" ;;
                    esac
                    # Check if this is a DAG header
                    for dh in $DAG_HEADERS; do
                        if [[ "$key" == "$dh" ]]; then
                            echo "$val" >> "$dag_file"
                            break
                        fi
                    done
                fi
                ;;
            gap) ;;
            log)
                local log_trimmed
                log_trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                if [[ -n "$log_trimmed" ]]; then
                    # Extract timestamp from log line
                    if [[ "$log_trimmed" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z?) ]]; then
                        last_log_ts="${BASH_REMATCH[1]}"
                    fi
                fi
                ;;
            body) ;;
        esac
    done < "$filepath"

    TICKET_LAST_LOG["$filename"]="$last_log_ts"
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
# Date comparison: is timestamp older than cutoff?
# Returns 0 (true) if ts < cutoff_epoch, 1 otherwise
# ---------------------------------------------------------------------------
ts_to_epoch() {
    # Convert "2026-03-21T12:00Z" or "2026-03-21T12:00" to epoch seconds
    local ts="$1"
    # Ensure Z suffix for consistent parsing
    if [[ ! "$ts" =~ Z$ ]]; then
        ts="${ts}Z"
    fi
    # Convert to format date can parse: replace T with space, remove Z
    local dt="${ts/T/ }"
    dt="${dt%Z}"
    date -u -d "$dt" +%s 2>/dev/null || echo "0"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local execute=false
    local days=90
    local ticket_dir="tickets"
    local -a pos_args=()

    # Parse arguments
    local i=0
    local -a raw_args=("$@")
    while (( i < ${#raw_args[@]} )); do
        local arg="${raw_args[$i]}"
        if [[ "$arg" == "--execute" ]]; then
            execute=true
        elif [[ "$arg" =~ ^--days= ]]; then
            days="${arg#--days=}"
        elif [[ "$arg" == "--days" ]] && (( i + 1 < ${#raw_args[@]} )); then
            (( i++ ))
            days="${raw_args[$i]}"
        elif [[ ! "$arg" =~ ^-- ]]; then
            ticket_dir="$arg"
        fi
        (( i++ )) || true
    done

    if [[ ! -d "$ticket_dir" ]]; then
        echo "Directory not found: $ticket_dir"
        exit 1
    fi

    load_tickets "$ticket_dir"

    # Calculate cutoff epoch
    local cutoff_epoch
    cutoff_epoch=$(date -u -d "$days days ago" +%s)

    # Collect all IDs referenced by DAG headers in live AND archived tickets
    declare -A referenced_ids
    local archive_dir="${ticket_dir%/}/archive"

    # Collect DAG refs from live tickets (already parsed)
    for filename in "${TICKET_FILES[@]}"; do
        local dag_file="$TMPDIR_PARSE/${filename}.dag_refs"
        if [[ -s "$dag_file" ]]; then
            while IFS= read -r ref; do
                referenced_ids["$ref"]=1
            done < "$dag_file"
        fi
    done

    # Also scan archived tickets for DAG refs
    if [[ -d "$archive_dir" ]]; then
        for af in "$archive_dir"/*.ticket; do
            [[ -e "$af" ]] || continue
            local af_name
            af_name=$(basename "$af")
            # Quick parse for DAG headers only
            local af_section="headers"
            local af_body_seen=false
            while IFS= read -r line || [[ -n "$line" ]]; do
                if [[ "$af_body_seen" == "false" ]]; then
                    local trimmed
                    trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                    if [[ "$trimmed" == "--- log ---" ]]; then af_section="log"; continue; fi
                    if [[ "$trimmed" == "--- body ---" ]]; then af_section="body"; af_body_seen=true; continue; fi
                fi
                case "$af_section" in
                    headers)
                        [[ -z "$(echo "$line" | tr -d '[:space:]')" ]] && af_section="gap" && continue
                        if [[ "$line" =~ ^([A-Za-z][A-Za-z0-9_-]*)[[:space:]]*:[[:space:]]*(.*) ]]; then
                            local key="${BASH_REMATCH[1]}"
                            local val="${BASH_REMATCH[2]}"
                            val=$(echo "$val" | sed 's/[[:space:]]*$//')
                            for dh in $DAG_HEADERS; do
                                if [[ "$key" == "$dh" ]]; then
                                    referenced_ids["$val"]=1
                                    break
                                fi
                            done
                        fi
                        ;;
                    gap|log|body) ;;
                esac
            done < "$af"
        done
    fi

    # Find candidates: closed tickets with last log older than cutoff
    declare -a candidates=()
    for filename in "${TICKET_FILES[@]}"; do
        local st="${TICKET_STATUS[$filename]:-}"
        [[ "$st" != "closed" ]] && continue

        local last_ts="${TICKET_LAST_LOG[$filename]:-}"
        [[ -z "$last_ts" ]] && continue

        local ts_epoch
        ts_epoch=$(ts_to_epoch "$last_ts")
        [[ "$ts_epoch" == "0" ]] && continue

        if (( ts_epoch < cutoff_epoch )); then
            candidates+=("$filename")
        fi
    done

    # Split candidates into archivable vs DAG-protected
    declare -a archivable=()
    declare -a dag_protected=()
    for filename in "${candidates[@]}"; do
        local tid="${TICKET_ID[$filename]:-}"
        if [[ -n "${referenced_ids[$tid]:-}" ]]; then
            dag_protected+=("$filename")
        else
            archivable+=("$filename")
        fi
    done

    # Output DAG-protected
    if [[ ${#dag_protected[@]} -gt 0 ]]; then
        local protected_ids=""
        for filename in "${dag_protected[@]}"; do
            [[ -n "$protected_ids" ]] && protected_ids+=", "
            protected_ids+="${TICKET_ID[$filename]:-}"
        done
        echo "DAG-protected (skipping ${#dag_protected[@]}): $protected_ids"
    fi

    # Output archivable
    if [[ ${#archivable[@]} -eq 0 ]]; then
        echo "Nothing to archive (threshold: $days days)."
        exit 0
    fi

    local archive_ids=""
    for filename in "${archivable[@]}"; do
        [[ -n "$archive_ids" ]] && archive_ids+=", "
        archive_ids+="${TICKET_ID[$filename]:-}"
    done
    echo "Will archive ${#archivable[@]} ticket(s): $archive_ids"

    if [[ "$execute" == "false" ]]; then
        echo "Dry run. Pass --execute to proceed."
        exit 0
    fi

    # Execute: move files and commit
    mkdir -p "$archive_dir"
    for filename in "${archivable[@]}"; do
        local src="${TICKET_PATH[$filename]}"
        local dest="$archive_dir/$filename"
        git mv "$src" "$dest"
        echo "  moved $filename"
    done

    local msg="archive ${#archivable[@]} closed tickets (>${days} days, DAG-safe)"
    git commit -m "$msg"
    echo "Committed: $msg"
    exit 0
}

main "$@"
