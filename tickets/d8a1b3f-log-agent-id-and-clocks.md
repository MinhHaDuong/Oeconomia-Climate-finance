Id: d8a1b3f
Title: Add agent ID to log entries; acknowledge clock limitations
Author: claude
Status: open
Created: 2026-03-21
Coordination: local
X-Discovered-from: gh#237
X-Phase: planning

--- log ---
2026-03-21T12:00Z created
2026-03-21T12:00Z status open

--- body ---
Distributed systems review: log entries have no agent identifier.
In multi-agent scenarios, can't attribute entries, detect conflicts,
or debug issues.

Fix: add agent ID field to log format.
Before: `2026-03-21T10:00Z status open`
After:  `2026-03-21T10:00Z agent-x status open`

Also: acknowledge that ISO timestamps provide wall-clock ordering,
not causal ordering. At minute-level granularity and <5 agents,
clock skew rarely matters. If it does, git commit ordering (DAG)
provides the causal ground truth — the log is supplementary.

Don't add Lamport timestamps. Too heavy for the scale. The git DAG
already provides a partial order.
