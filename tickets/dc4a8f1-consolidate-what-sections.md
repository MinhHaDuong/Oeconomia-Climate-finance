Id: dc4a8f1
Title: Consolidate "what" content into Specification
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
PEP/structure review: "what we're building" appears in both
Recommendation (lines 159-169) and Specification. PEP convention
puts all concrete details in Specification.

Fix: move the "what" parts of Recommendation into Specification as
an overview/preamble. What remains (Forge compatibility, Transition)
becomes standalone sections. Delete the Recommendation heading.

Depends on db3c7e2 (consolidating "why") to avoid double-restructure.
