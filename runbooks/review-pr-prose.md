# Review PR (Prose) — simulated peer review panel

A prose review spins multiple agents in parallel, each with a distinct disciplinary or editorial perspective adapted to the target audience and text purpose. Run all agents in fresh contexts.

## Setup

1. **Identify the text**: which `.qmd` or `.md` files changed? What is the target venue/audience?
2. **Read the diff**: `gh pr diff <number>`
3. **Select the panel**: adapt perspectives to the text. See panel templates below.

## Panel templates

### For Oeconomia manuscript (HPS journal)

| Agent perspective | Focus | Key question |
|---|---|---|
| **Historian of economics** | Historical accuracy, periodization, actors, prosopography | Are claims grounded in specific dates, documents, people? |
| **STS / constructivism scholar** | Category-making, co-production, performativity | Does this show how the object was constructed? |
| **Climate policy specialist** | Institutional accuracy, missing actors, policy nuance | Would practitioners recognize this account? |
| **Literature specialist** | Deep research on cited and uncited works | What key references are missing? What recent work contradicts or supports claims? |
| **Nitpicking adversarial referee** | Logical gaps, unsupported claims, rhetorical overreach, factual errors | Where exactly does the argument fail? |
| **Copy editor** | AI tells, blacklist words, em-dash density, house style | Does this pass `docs/writing-guidelines.md` and `docs/oeconomia-style.md` checks? |

### For technical report (reproducibility note)

| Agent perspective | Focus | Key question |
|---|---|---|
| **Scientometrician** | Methodology, corpus validity, statistical claims | Are the bibliometric methods sound and well-described? |
| **Replicator** | Can I reproduce this from the instructions? | Are all steps, dependencies, and parameters documented? |
| **Literature specialist** | Related methods, comparable pipelines, benchmarks | What prior work should be cited or compared against? |
| **Nitpicking adversarial referee** | Inconsistencies, missing numbers, vague assertions | Where are the gaps between what's claimed and what's shown? |
| **Copy editor** | AI tells, clarity, figure/table references | Is the prose clean and precise? |

### For agentic workflow paper (Scientometrics / AI methodology)

| Agent perspective | Focus | Key question |
|---|---|---|
| **Software engineering researcher** | Methodology rigor, reproducibility, tooling evaluation | Is the workflow well-specified and the evaluation sound? |
| **Human-AI interaction scholar** | Agency, autonomy, trust, collaboration patterns | Does this advance understanding of human-AI work? |
| **Literature specialist** | Related work completeness, recent publications, positioning | What's missing from the related work? What's been published since the draft? |
| **Nitpicking adversarial referee** | Cherry-picked metrics, survivorship bias, overclaiming | Where does the evidence not support the conclusions? |
| **Copy editor** | AI tells, academic tone, venue formatting | Does this meet journal standards? |

### Custom panels

For any other text, compose a panel by:
1. One perspective per target audience segment
2. Always include **Literature specialist** (deep research on the subject)
3. Always include **Nitpicking adversarial referee**
4. Always include **Copy editor**
5. Add domain experts relevant to the claims being made

## Each agent runs

1. Read the full text (not just the diff — prose needs full context).
2. Evaluate from its assigned perspective.
3. The **Literature specialist** must do actual web searches and cite specific papers, not just suggest "more literature is needed."
4. The **Nitpicking adversarial referee** must quote specific sentences and explain exactly why they fail.
5. For each finding, report **confidence** (high / medium / low) and **severity** (major / minor / suggestion).
6. Return a structured verdict: **accept**, **minor revision**, or **major revision**, with specific findings.

## Synthesis

After all agents return:

1. **Preserve dissent** — when agents contradict each other, surface both positions verbatim. The human author decides.
2. **Triage by severity** — group findings as major (blocks acceptance), minor (should fix), suggestion (nice to have).
3. **Deduplicate** — merge findings that multiple reviewers flagged independently (note the convergence).
4. **Run quality checks**:
   - `make lint-prose` (blacklisted words, AI tells)
   - `make manuscript` or `make papers` (if prose changed)
5. **Check consistency**: are claims in the text consistent with data in `content/*-vars.yml`, figures, and tables?
6. **Post a single review** via `gh pr review <number>`, attributing each finding to its perspective.

## Proportional depth

| Text change | Panel size |
|---|---|
| Typo, formatting, citation fix | Copy editor only |
| Section rewrite, new argument | 3 agents (domain + adversarial + copy) |
| Full paper draft | Full panel (5-6 agents) |
| Submission-ready review | Full panel + response-to-reviewers template |

## Difference from code review

- Prose review reads the **full text**, not just the diff — arguments span sections.
- No "red team" for adversarial inputs; instead **nitpicking adversarial referee** for logical/rhetorical failures.
- **Literature specialist** does active research (web search, citation lookup), not just static analysis.
- Verdict uses journal terminology (accept / minor / major revision), not GitHub (approve / request-changes).
