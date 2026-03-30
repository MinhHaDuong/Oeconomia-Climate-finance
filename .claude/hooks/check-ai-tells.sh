#!/bin/bash
# PostToolUse(Edit) hook: check for AI-tell words in content/ files.
# Deterministic enforcement — replaces probabilistic rule compliance.

# Only check edits to content/ files
FILE_PATH="$TOOL_INPUT_FILE_PATH"
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *content/* ]]; then
    exit 0
fi

# Only check prose files
case "$FILE_PATH" in
    *.qmd|*.md) ;;
    *) exit 0 ;;
esac

BLACKLISTED_WORDS="delve|nuanced|multifaceted|pivotal|crucial|intricate|comprehensive|meticulous|vibrant|arguably|showcasing|underscores|foster|tapestry"
BLACKLISTED_PHRASES="it is important to note|in the realm of|stands as a testament to|plays a vital role|the landscape of|navigating the complexities|the interplay between|sheds light on|a growing body of literature|offers a lens through which|it is worth noting|cannot be overstated"

HITS=""

if [ -f "$FILE_PATH" ]; then
    WORD_HITS=$(grep -inE "\b($BLACKLISTED_WORDS)\b" "$FILE_PATH" | grep -v "robust.*statistic\|CPI.*Landscape\|Global Landscape" || true)
    PHRASE_HITS=$(grep -inE "$BLACKLISTED_PHRASES" "$FILE_PATH" || true)
    HITS="${WORD_HITS}${PHRASE_HITS}"
fi

if [ -n "$HITS" ]; then
    echo "AI-tell words/phrases detected in $FILE_PATH:"
    echo "$HITS"
    echo ""
    echo "Replace these with precise, non-generic alternatives."
    exit 2  # Non-zero = block the edit with message
fi

exit 0
