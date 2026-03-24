# The 5 levels of Claude Code (and how to know when you've hit the ceiling on each one)

Author: https://www.reddit.com/user/DevMoses/

 Level 1: Raw prompting. You open Claude Code, describe what you want, and it builds. This works surprisingly well for small tasks. The ceiling: your project grows past what fits in a single conversation. The agent forgets your conventions, introduces patterns you don't use, and you spend more time correcting than building.

Level 2: CLAUDE.md. You create a markdown file at your project root that tells the agent how your codebase works. Tech stack, file structure, naming conventions, patterns to follow, patterns to avoid. This alone changes everything. The ceiling: I let mine grow to 145 lines and discovered compliance degraded well before Anthropic's recommended 200-line limit. Agents followed the top rules and silently ignored the rest. I trimmed it to 77 lines and compliance improved immediately. Keep it tight. And once your sessions get long enough, the agent starts losing the thread anyway: quality drops, earlier decisions get forgotten, it starts repeating itself and gives surface-level answers. That's when you know raw context isn't enough.

Level 3: Skills. Markdown protocol files that teach the agent specialized procedures. Each one is a step-by-step workflow for a specific type of task. They load on demand and cost zero tokens when inactive. Instead of re-explaining how you want components built every session, you point the agent at a skill file. The ceiling: the agent follows your protocols but nobody checks its work automatically. You're still the quality gate.

Level 4: Hooks. Lifecycle scripts that fire at specific moments during a session. PostToolUse to run a per-file typecheck after every edit (instead of flooding the agent with 200+ project-wide errors). Stop hooks for quality gates before task completion. SessionStart to load context before the agent touches anything. This is where you stop telling the agent to validate and start building infrastructure that validates for it. The ceiling: you're still one agent, one session. Your project outgrows what a single context window can hold.

Level 5: Orchestration. Parallel agents in isolated worktrees, persistent campaign files that carry state across sessions, coordination layers that prevent agents from editing the same files. This is where one developer operates at institutional scale. I've run 198 agents across 32 fleet sessions with a 3.1% merge conflict rate. Most projects never need this level. Know when you do.

The pattern: you don't graduate by deciding to. You graduate because you hit a ceiling and the friction forces you up. Each level exists because the one below it broke. Don't skip levels. I tried to jump to Level 5 before I had solid hooks and it was a mess. The infrastructure at each level is what makes the next level possible.

Source: https://www.reddit.com/r/ClaudeAI/comments/1s1ipep/the_5_levels_of_claude_code_and_how_to_know_when/

## TL;DR of the discussion generated automatically after 100 comments.

The community overwhelmingly agrees with OP's 5-level framework, with many users saying it perfectly describes their own journey and the "forced graduation" from one level to the next is a universal experience.

The Level 2 ceiling on CLAUDE.md was the most relatable pain point. Users confirmed that compliance drops significantly as the file grows, with the consensus being to keep it under 100 lines and split larger context into separate, on-demand reference files.

Level 3 (Skills) is widely seen as the biggest unlock, the point where you transition from a prompter to a true power user building a repeatable system. However, a good correction was made: Skills aren't completely zero-token when inactive; there's a small but real discovery cost for the frontmatter.

Other key takeaways from the thread:

    For non-devs on Claude.ai: You can get to Level 3 using custom instructions. Level 4 can be approximated by building manual checks into your prompts, but Level 5 (Orchestration) is currently a developer-only game.

    On CodeX (GPT) vs. Claude Code: The general feeling is that while CodeX's models are very competitive, Claude Code's advanced infrastructure (hooks, skills, worktrees) is its killer feature and the main reason power users are all-in.

    Level 5 (Orchestration) is considered the holy grail, but many warned it's a "maintenance nightmare" if you skip the foundational work in Levels 3 and 4.

Basically, this post gave a name and a structure to a process a lot of you were already feeling out in the dark. Great write-up, OP.
