Id: d4b1c8e
Title: Specify authority rule for Assigned-to vs forge assignee
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
DevOps review: the `Assigned-to` header can go stale relative to the
forge assignee. If forge says agent-x owns gh#42 but the ticket file
says `Assigned-to: agent-y`, which wins?

Add to spec:
- For `Coordination: local` tickets: `Assigned-to` header is
  authoritative (no forge to contradict it).
- For `Coordination: forge#N` tickets: the forge assignee is
  authoritative. The `Assigned-to` header is a cache — agents should
  refresh it from the forge when online.
