---
name: code-style
description: Apply the project's code style rules to any Python code you write or review.
---

# Code Style Rules

Apply these rules to **every Python file** in this project.

## Rules

1. **Readability over cleverness.** Prefer explicit, multi-line logic over dense one-liners.
2. **Type hints on every method signature** — both arguments and return values.
3. **Inline comments on complex logic.** Brief "why" comments on non-obvious branches.
4. **Every function does exactly one thing.** If a function needs a comment explaining two halves, split it.
5. **Tight `try`/`except` blocks.** Wrap only the specific line(s) that can raise, never blanket-wrap a whole function body.
6. **Write code in small, reviewable chunks so the user can follow along and provide feedback at each step.**
7. **Clarify when unsure.** If the spec, intent, or design choice is ambiguous, ask the user before proceeding — never guess.