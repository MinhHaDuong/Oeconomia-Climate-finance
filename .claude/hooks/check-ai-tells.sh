#!/bin/bash
# PostToolUse hook: check for AI-tell words after editing content files.
# Receives tool call info via stdin as JSON.
# Only runs on Edit tool calls targeting content/** files.

# Read the tool input from stdin
input=$(cat)

# Extract file_path from the JSON input
file_path=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # tool_input contains the Edit parameters
    tool_input = data.get('tool_input', {})
    print(tool_input.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

# Exit silently if no file path
[ -z "$file_path" ] && exit 0

# Only check content/** files
case "$file_path" in
    */content/*) ;;
    *) exit 0 ;;
esac

# Exit if the file doesn't exist (deleted, etc.)
[ -f "$file_path" ] || exit 0

# Blacklisted AI-tell words (from writing.md)
# Uses -i (case-insensitive) without -w, matching word stems via regex
WORD_PATTERNS=(
    "\bdelv"
    "\bnuance"
    "\bmultifacet"
    "\bpivotal"
    "\bcrucial"
    "\brobust"
    "\bintricat"
    "\bcomprehensiv"
    "\bmeticulou"
    "\bvibrant"
    "\barguabl"
    "\bshowcas"
    "\bunderscore"
    "\bfoster"
    "\btapestr"
    "\blandscape"
)

# Labels for each pattern (for reporting)
WORD_LABELS=(
    "delve"
    "nuanced"
    "multifaceted"
    "pivotal"
    "crucial"
    "robust"
    "intricate"
    "comprehensive"
    "meticulous"
    "vibrant"
    "arguably"
    "showcasing"
    "underscores"
    "foster"
    "tapestry"
    "landscape"
)

# Blacklisted AI-tell phrases
PHRASES=(
    "it is important to note"
    "in the realm of"
    "stands as a testament to"
    "plays a vital role"
    "the landscape of"
    "navigating the complexities"
    "the interplay between"
    "sheds light on"
    "a growing body of literature"
    "offers a lens through which"
    "it is worth noting"
    "cannot be overstated"
)

found=()

# Check word patterns (case-insensitive, stem-matching)
for i in "${!WORD_PATTERNS[@]}"; do
    pattern="${WORD_PATTERNS[$i]}"
    label="${WORD_LABELS[$i]}"

    if grep -qiE "$pattern" "$file_path" 2>/dev/null; then
        # Skip "robust" used in statistical context
        if [ "$label" = "robust" ]; then
            # Only flag if NOT followed by common stats terms
            if grep -iE "\brobust" "$file_path" 2>/dev/null | grep -qivE "robust (standard error|regression|estimat|check|test|statistic)"; then
                found+=("$label")
            fi
            continue
        fi
        # Skip "landscape" when used as part of a proper noun
        if [ "$label" = "landscape" ]; then
            if grep -iE "\blandscape" "$file_path" 2>/dev/null | grep -qivE "Global Landscape|CPI.*Landscape"; then
                found+=("$label")
            fi
            continue
        fi
        found+=("$label")
    fi
done

# Check phrases (case-insensitive)
for phrase in "${PHRASES[@]}"; do
    if grep -qi "$phrase" "$file_path" 2>/dev/null; then
        found+=("$phrase")
    fi
done

# Report findings
if [ ${#found[@]} -gt 0 ]; then
    echo "AI-tell words/phrases found in $(basename "$file_path"):"
    for item in "${found[@]}"; do
        echo "  - $item"
    done
    echo "Please replace these with more precise language."
fi

exit 0
