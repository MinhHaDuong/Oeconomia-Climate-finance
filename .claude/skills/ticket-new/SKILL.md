---
name: ticket-new
description: Create a local %erg v1 file for agent coordination.
disable-model-invocation: false
user-invocable: true
argument-hint: [title]
---

# Create local ticket

**Input:** anything — a title, a sentence, a JSON blob from `gh`, a paste
from a conversation. Extract the intent and normalize to `%erg v1`.

## Steps

1. Determine the next ID:
   ```bash
   ls tickets/*.erg tickets/archive/*.erg 2>/dev/null \
     | sed 's|.*/||; s|-.*||' | sort -n | tail -1
   ```
   Increment by 1, zero-pad to 4 digits. If empty, start at `0001`.

2. Choose a slug: lowercase kebab-case, ASCII only (`[a-z0-9-]`), derived from the title.

3. Create `tickets/{ID}-{slug}.erg` with this exact structure:
   ```
   %erg v1
   Title: {imperative title}
   Status: open
   Created: {YYYY-MM-DD}
   Author: {agent or user}

   --- log ---
   {YYYY-MM-DD}T{HH:MM}Z {author} created

   --- body ---
   ## Context
   {why this work exists}

   ## Actions
   1. {concrete step}

   ## Test
   {first test to write — TDD red step}

   ## Exit criteria
   {definition of done}
   ```

4. Commit the ticket file.

## Rules

- **Closed header set**: Title, Status, Created, Author, Blocked-by. No other headers.
- **Blocked-by**: one line per dependency. Use 4-digit ticket IDs or `gh#N` for GitHub issues.
- **Log**: append-only. Format: `{ISO-timestamp} {actor} {verb} [{detail}]`
- Verbs: `created`, `status`, `note`
