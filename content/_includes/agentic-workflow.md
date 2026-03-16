# Part III: Agentic Workflow

This part documents the human--AI collaboration framework used to build the pipeline and write the manuscript. The project involved 475 commits over five months, with a single human author directing an AI coding agent (Claude, via Anthropic's Claude Code CLI). The workflow evolved from ad hoc prompting into a structured protocol, codified in a living specification (`AGENTS.md`, 53 revisions). We describe the framework, tooling, collaboration patterns, and lessons learned.

## 12. Workflow Framework

### Dragon Dreaming for AI agents

The project adopted Dragon Dreaming --- a participatory project management methodology --- as the organizing metaphor for human--AI collaboration. Every task passes through four phases:

1. **Dreaming.** Interactive discussion between human and agent. The human surfaces motivations, explores what success looks like, and brainstorms freely. No code, no commits. The deliverable is a shared vision.

2. **Planning.** The agent reads code, researches alternatives, and drafts a plan. The artifact is a GitHub Issue written as a *handoff document*: full context, acceptance criteria, and a first test specification. The human reviews and refines the ticket.

3. **Doing.** The agent works autonomously in a fresh conversation context, using the ticket as its only input. This context isolation prevents "window pollution" --- the accumulation of stale assumptions from earlier phases. The inner cycle is strict test-driven development: write a failing test (Red), write the minimum code to pass it (Green), refactor, commit, open a pull request.

4. **Celebrating.** After the PR is merged, the agent reflects on what worked, updates project state files, saves durable lessons to persistent memory, and cleans up artifacts. This is not a formality --- it closes the energy cycle and prevents context from leaking into the next task.

The key adaptation for AI agents is the *context boundary* between Planning and Doing. Human team members carry implicit knowledge across phases; an AI agent's context window is its only memory. By making the ticket a self-contained document, the Doing phase can run in a fresh conversation without loss. This also enables parallelism: multiple tickets can execute simultaneously in independent agent sessions.

### GitHub Issues as handoff documents

Each issue follows a template: problem statement, relevant files, acceptance criteria, and a first test. The test specification is mandatory --- it anchors the Doing phase's TDD cycle. Issues are the project's primary planning artifact: 158 were opened, 97.5% were closed.

### Escalation protocol

When the agent is stuck, it follows a five-step escalation ladder: (1) fix directly if feedback is straightforward, (2) try an alternative approach, (3) fan out to parallel expert sub-agents, (4) re-ticket with a diagnosis if the problem is mis-specified, (5) stop and ask the human author. A feedback memory is saved at each escalation step, recording what failed and why. The agent stops if it detects it is repeating itself.

## 13. Tooling

### DVC as pipeline contract

Data Version Control (DVC) serves as the contract language between pipeline phases. Each DVC stage declares its inputs (`deps`), outputs (`outs`), and the command that transforms one into the other. This makes stage boundaries explicit and machine-verifiable: `dvc repro` will only re-run stages whose dependencies have changed. The pipeline DAG (@fig-dag) is generated directly from `dvc.yaml`, ensuring documentation stays synchronized with the actual execution graph.

The pipeline was initially a flat Makefile. Migrating to DVC (issues #101--#104) forced each stage's data contract to be declared explicitly, which exposed several implicit couplings between scripts. The migration itself was a significant refactoring effort, but the resulting stage isolation made parallel development possible.

### Worktrees for parallel agent work

Git worktrees allow multiple branches to be checked out simultaneously in separate directories. The project uses worktrees extensively: each ticket gets its own worktree (`git worktree add ../t{N}-description -b t{N}-description`), enabling parallel agent sessions to work on independent tasks without interfering with each other. A post-checkout hook automatically symlinks the `.env` file from the main worktree, ensuring scripts find their API keys and data paths in any worktree.

### Pre-commit hooks as quality gates

The `hooks/` directory contains git hooks that enforce project invariants at commit time:

- **No commits on main.** All work happens on feature branches; main is updated only via merge.
- **CLAUDE.md is locked.** The agent specification entry point cannot be modified accidentally.
- **No secrets.** Patterns matching API keys and tokens are rejected.
- **No large files.** Binaries over 500 KB are blocked (data lives in DVC, not git).
- **No conflict markers.** Prevents accidental commits of unresolved merges.

These hooks run locally on every commit, serving as a fast quality gate before the slower CI checks.

### Memory system

The agent has no persistent memory between conversations. To compensate, the project maintains a structured memory file (`MEMORY.md`) with entries for user preferences, machine-specific configuration, naming conventions, and workflow feedback. Entries have size caps (e.g., 5 feedback entries, 3 corpus statistics) and time-to-live values (e.g., corpus statistics expire after 30 days). A sweep procedure during the Celebrating phase evicts stale entries and archives resolved ones.

Longer-lived knowledge is stored in dedicated memory files (e.g., `project_dvc_integration.md`, `project_doifetch_sync.md`) that document multi-step procedures too complex for a bullet point. The memory system is a pragmatic workaround for the fundamental limitation of conversation-scoped context windows.

### Agent identity

The agent operates under a dedicated GitHub account (`HDMX-coding-agent`) with its own credentials stored in `.env`. This separates human and agent contributions in git history, making authorship auditable. The agent's git name and email are set at the start of each conversation via the `on-start` trigger, ensuring consistent attribution.

## 14. Collaboration Patterns

### Quantitative portrait

The git history provides a quantitative picture of the collaboration:

- **475 commits**: 72.5% human-authored, 25.4% agent-authored, 2.1% co-authored.
- **158 issues** opened, 97.5% closed. Issues served as the primary planning and handoff mechanism.
- **60 pull requests** merged, with a median time-to-merge of 6.4 minutes. Fast merges reflect the tight feedback loop: the human reviews while the agent is still in context.
- **298 tests** grown from zero in five days. The test suite was the agent's primary contribution during the pipeline stabilization phase.

### Division of labor

The human author performs all Dreaming and most Planning: choosing research questions, interpreting results, making judgment calls about periodization, writing manuscript prose. The agent performs most Doing: implementing scripts, writing tests, debugging pipeline failures, managing DVC stages, formatting outputs.

The boundary is not rigid. The human sometimes writes code directly (especially for figure aesthetics and manuscript formatting), and the agent sometimes drafts prose (especially for the technical report). But the general pattern holds: the human decides *what* and *why*; the agent executes *how*.

### AGENTS.md as living specification

`AGENTS.md` is the project's most-revised file (53 revisions). It began as a short prompt and grew into a comprehensive specification covering workflow phases, trigger-based runbooks, git discipline, memory management, and autonomous wave cycles. Each revision typically followed a failure: the agent did something unexpected, and the specification was tightened to prevent recurrence.

This iterative refinement is itself a form of programming --- writing natural-language instructions that reliably produce desired behavior from an AI agent. The specification's evolution mirrors how codebases grow: from scripts to frameworks, from implicit conventions to explicit contracts.

## 15. Lessons Learned

### What worked

**Test-driven development.** TDD was the single most effective practice. Tests served three functions: (1) specification --- the ticket's test defined what "done" means; (2) regression protection --- 298 tests caught breakage during refactoring; (3) confidence --- the human could merge agent PRs quickly because `make check` passed. The test suite grew from zero to 298 in five days, a pace only possible because the agent could generate test scaffolding rapidly.

**Worktree isolation.** Worktrees eliminated the "dirty working directory" problem that plagues long-running agent sessions. Each task got a clean checkout, and the agent never had to stash or context-switch. This was especially valuable when running parallel agent sessions on independent tickets.

**Tickets as context boundaries.** The one-ticket-per-conversation rule prevented context window pollution and made agent behavior more predictable. When a task revealed sub-issues, they were filed as new tickets rather than pursued in the current conversation. This discipline was initially frustrating (it felt slow) but paid off in reduced debugging time.

### What did not work

**Monolithic DVC stages.** The initial pipeline had a single `enrich` stage that ran all enrichment scripts sequentially. When one script failed, the entire stage had to be re-run. Splitting into granular stages (issue #152) improved reliability but required significant rework. Lesson: design for granularity from the start.

**No log flushing.** Early agent sessions on a remote machine (`padme`) ran long tasks via `nohup`, but Python's output buffering meant logs were empty until the process completed. The agent could not monitor progress and sometimes restarted tasks unnecessarily. Adding `PYTHONUNBUFFERED=1` and explicit `flush=True` calls solved this, but only after several wasted runs.

**Budget exhaustion.** The OpenAlex premium API key ($2/day) was consumed faster than expected during development iterations. The agent would re-run the full discovery pipeline when only one source needed updating. Incremental filtering (issue #153, `--from-date` flag) and per-source DVC stages (issue #152) reduced waste, but the cost was already sunk.

### The autonomy dial

The central design tension is how much autonomy to grant the agent. Too little autonomy creates a bottleneck: the human must review every intermediate step, and the agent waits idle. Too much autonomy creates waste: the agent pursues approaches the human would have rejected, consuming API budget and context window on dead ends.

The project converged on a practical heuristic: *high autonomy for implementation, low autonomy for judgment*. The agent can freely choose how to implement a feature, which libraries to use, how to structure tests. But decisions about what to build, how to interpret results, and what trade-offs to accept require human approval. The ticket system enforces this boundary: the human writes the "what" (Dreaming/Planning), the agent executes the "how" (Doing).

This division works because the cost of agent implementation errors is low (tests catch them, git reverts them) while the cost of judgment errors is high (wrong research direction, wasted weeks). The workflow optimizes for fast recovery from implementation mistakes while preventing judgment mistakes from compounding.
