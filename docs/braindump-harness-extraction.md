# Brain dump: Extract harness into its own repo

Date: 2026-03-19

## Three ideas

### 1. Split the harness into its own repo

The harness — `AGENTS.md`, `runbooks/`, `hooks/`, the Dragon Dreaming workflow, `make check`, the trigger system — has matured into something genuinely reusable. It's domain-agnostic: nothing in the workflow machinery is specific to climate finance or Oeconomia. A separate repo would let you (and others) drop it into any research project.

**What would move:**
- `AGENTS.md` (becomes the new repo's core doc)
- `runbooks/` (the full trigger system)
- `hooks/` (pre-commit, post-checkout)
- `Makefile` targets related to workflow (`make setup`, `make check`, `make check-fast`)
- `docs/coding-guidelines.md`, `docs/writing-guidelines.md` (as templates)
- The Dragon Dreaming phase model documentation

**What stays in Oeconomia:**
- `CLAUDE.md` pointing to a lightweight local `AGENTS.md` that `@includes` the harness
- `content/`, `data/`, `scripts/`, `dvc.yaml` — all domain-specific
- `docs/oeconomia-style.md` — journal-specific
- `STATE.md`, `ROADMAP.md` — project-specific

**Open questions:**
- **Consumption model**: git submodule? Template repo you fork? Package you install? Submodule keeps it updatable but adds friction. A template repo is simpler but drifts.
- **Customization points**: the harness needs project-specific hooks (e.g. what `make check` runs, what goes in `.env`). How do you separate the framework from the project config?
- **Name**: this deserves a good name.

### 2. Review harness against seminal software engineering books

Intellectual audit — positioning what we've built against the canon.

| Book | Key idea | Harness connection |
|------|----------|-------------------|
| **Programming Pearls** (Bentley) | Problem decomposition, back-of-envelope, test-first thinking | TDD Red/Green/Refactor cycle, `make check-fast` |
| **Code Complete** (McConnell) | Construction as craft, checklists, defensive programming | Runbooks as checklists, pre-commit hooks as guardrails |
| **Extreme Programming Explained** (Beck) | Small releases, pair programming, continuous integration, courage | Wave cycles, one-change-per-commit, escalation ladder |
| **The Mythical Man-Month** (Brooks) | Conceptual integrity, surgical team, plan to throw one away | One ticket per conversation, agent identity, Dreaming phase |
| **Algorithms + Data Structures = Programs** (Wirth) | Stepwise refinement, data structures drive programs | DVC pipeline as stepwise refinement, phase separation |
| **The Pragmatic Programmer** (Hunt & Thomas) | DRY, tracer bullets, orthogonality, automation | Runbook triggers, hook system, worktree isolation |
| **Refactoring** (Fowler) | Small behavior-preserving transformations, code smells | Red/Green/Refactor, one change per commit, `make check` as safety net |
| **Test-Driven Development** (Beck) | Red-green-refactor as design technique, not just testing | Core of the Doing phase — the harness enforces this as the inner loop |
| **A Philosophy of Software Design** (Ousterhout) | Deep vs shallow modules, complexity as the enemy | Phase separation (dreaming/planning/doing), one ticket per conversation scope control |
| **The Design of Everyday Things** (Norman) | Affordances, error prevention, conceptual models | Pre-commit hooks as error prevention, triggers as affordances, runbooks as conceptual models |
| **Peopleware** (DeMarco & Lister) | Flow, team chemistry, workspace matters | Dragon Dreaming's Celebrating phase, feedback memories, escalation with human contact |
| **Clean Code** (Martin) | Readability, single responsibility, meaningful names | One change per commit with why-not-what messages, branch naming conventions |
| **Structure and Interpretation of Computer Programs** (Abelson & Sussman) | Abstraction barriers, metalinguistic abstraction | The harness itself is a metalinguistic abstraction — a language for describing development workflow |
| **The Art of Unix Programming** (Raymond) | Rule of Modularity, Rule of Composition, text streams | Makefile pipeline, DVC DAG, gitignored intermediates, separation of concerns |
| **Lean Software Development** (Poppendieck) | Eliminate waste, defer commitment, deliver fast | Wave cycles with learn/adapt, Dreaming phase defers commitment, feedback memories eliminate repeated waste |
| **Managing the Design Factory** (Reinertsen) | Queuing theory for product development, cost of delay, batch size | Small commits as small batches, wave cycle as cadenced flow, escalation ladder as WIP limit |

The review could surface gaps, validate design choices, and give the harness intellectual credibility. Could become a "Design Rationale" or "Intellectual Lineage" document in the new repo.

### 3. Launch coding team leader in background to poll tickets

A background agent that watches `gh issue list`, picks ripe tickets (dependencies met, labels ready), and either starts work or alerts. Automating the "Select" step of the wave cycle.

Depends on idea #1 being solid first. But it's the natural next step: the harness already describes the wave cycle, this adds the cron.

## Arc

These three ideas form a coherent sequence: extract the methodology (1), validate it intellectually (2), then operationalize it (3).
