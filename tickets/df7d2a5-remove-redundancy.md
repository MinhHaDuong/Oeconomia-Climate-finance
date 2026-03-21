Id: df7d2a5
Title: Remove redundant content across sections
Author: claude
Status: open
Created: 2026-03-21
Coordination: local
Blocked-by: db3c7e2
Blocked-by: dc4a8f1
X-Discovered-from: gh#237
X-Phase: planning

--- log ---
2026-03-21T12:00Z created
2026-03-21T12:00Z status open

--- body ---
PEP/structure review: same content appears multiple times.

Specific instances:
1. "Mutable header + append-only log" — appears in Recommendation
   (line 155), Design decisions (line 165), and Specification
   (lines 253-257). Three treatments.
2. "RFC 822 not YAML" — appears in Design decisions (line 166) and
   Specification (lines 218-221). Two treatments.
3. "Forge-agnostic" — appears in Design philosophy point 6 (line 42),
   Forge compatibility (lines 188-195), and Specification's
   Coordination header (line 223). Three treatments.

Fix: after structural reorganization, each concept should appear
exactly once — rationale in Rationale, specification in Specification.
Cross-reference, don't repeat.

Depends on db3c7e2 and dc4a8f1 (the restructure determines where
each concept's canonical home is).
