Id: dd5b9e3
Title: Extract landscape survey into Rejected Ideas section
Author: claude
Status: open
Created: 2026-03-21
Coordination: local
Blocked-by: db3c7e2
X-Discovered-from: gh#237
X-Phase: planning

--- log ---
2026-03-21T12:00Z created
2026-03-21T12:00Z status open

--- body ---
PEP/structure review: the Rationale section is primarily a survey of
alternatives and why they were rejected. PEP convention separates
this into "Rejected Ideas" (what was considered) vs. "Rationale"
(why the chosen approach works).

Fix: move landscape survey + per-tool analysis + "DB in git"
antipattern + "real cost of extra tooling" into a new "Rejected
Ideas" section. Keep in Rationale only the justification for the
specific design choices of the proposed system.

Depends on db3c7e2 (the "why" consolidation determines what stays
in Rationale).
