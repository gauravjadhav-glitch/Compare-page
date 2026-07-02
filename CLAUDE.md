# Ways of Working

This document defines mandatory practices for all implementation work in this project. Follow these rules strictly — no exceptions unless explicitly discussed with the user.

---

## 1. Development Workflow: TDD (Test-Driven Development)

Every feature, bug fix, or refactor **must** follow this cycle:

### Red-Green-Refactor

1. **RED** — Write a failing test that defines the expected behavior
2. **GREEN** — Write the *minimum* code to make the test pass
3. **REFACTOR** — Clean up the code while keeping tests green

**Rules:**
- Never write implementation code before a test exists
- If a test framework isn't set up, set it up first (that's step zero)
- Each test should test ONE behavior, not multiple things
- Test names should read like sentences: `test_broken_image_returns_critical_severity`

### Test Categories
- **Unit tests** — isolated functions, no I/O, fast
- **Integration tests** — modules working together, may use real files/network
- **E2E tests** — full user-facing flows (Playwright, browser, CLI)

Use the simplest test type that covers the behavior. Don't over-test internals.

---

## 2. Small Steps Protocol

Work in **very small increments**. One logical change at a time.

### After each step:
1. **Stop** — do not continue to the next step
2. **Explain** — describe what was done in 1-2 sentences
3. **Suggest** — propose a small, descriptive git commit message
4. **Ask** — wait for confirmation before proceeding

### What counts as "one step":
- Add one test (failing)
- Make one test pass
- Rename a function
- Extract a helper
- Add one validation rule
- Fix one bug

### What is NOT one step:
- "Add the entire feature"
- "Refactor the whole module"
- "Fix all the bugs"
- Multiple unrelated changes in one go

---

## 3. Output Format for Each Step

Use this structure for every implementation step:

```
### Step N: [Brief description]

**What:** [1-2 sentence explanation of the change]

**Test:**
[Code block with the test — failing first]

**Implementation:**
[Code block — only after test is approved, minimal code to pass]

**Refactor:**
[If applicable — clean up while keeping tests green]

**Commit message:**
`[type]: [description]`

**Ready to proceed?**
```

---

## 4. Git Practices

### Commit Message Format
```
type: short description (imperative mood, <70 chars)

Optional body explaining WHY, not what.
```

### Types:
- `feat` — new feature or behavior
- `fix` — bug fix
- `test` — adding or fixing tests
- `refactor` — restructuring without changing behavior
- `chore` — tooling, config, dependencies
- `docs` — documentation only

### Rules:
- Commit after each green step (test passes)
- Each commit should be independently valid (tests pass)
- Never commit broken code
- Never commit secrets, credentials, or `.env` files

---

## 5. Code Quality Standards

### General
- Write code that reads like prose — clear names, obvious flow
- Functions should do ONE thing and be named for that thing
- Keep functions short: aim for < 20 lines, hard max 40 lines
- No magic numbers — use named constants
- No dead code — delete it, don't comment it out

### Naming
- Variables/functions: descriptive, not abbreviated (`element_count` not `ec`)
- Booleans: prefix with `is_`, `has_`, `should_`, `can_`
- Functions: start with a verb (`calculate_score`, `validate_input`, `fetch_report`)
- Classes: noun phrases (`ReportGenerator`, `ImageAnalyzer`)

### Error Handling
- Handle errors at system boundaries (user input, APIs, file I/O)
- Don't swallow exceptions silently — log or re-raise
- Use specific exceptions, not bare `except:`
- Fail fast with clear error messages

### Comments
- Default: no comments (good names replace comments)
- Only comment the WHY — not the what or how
- If you need a comment, consider renaming first

---

## 6. Architecture Principles

### Separation of Concerns
- Each file/module has ONE responsibility
- Business logic stays separate from I/O (files, network, UI)
- Configuration separate from code (use `.env`, config files)

### Dependencies
- Depend on abstractions, not concrete implementations
- Keep dependency chains shallow
- New dependencies need justification — prefer stdlib/existing packages

### File Organization
- Group by feature, not by type (when project grows)
- Keep related code close together
- Tests live next to the code they test, or in a `tests/` mirror

---

## 7. Communication Protocol

### Before Starting Work
- Read the spec/requirements carefully
- Ask clarifying questions if ANYTHING is ambiguous
- Confirm understanding before writing code
- Identify edge cases and discuss them upfront

### During Work
- Narrate what you're doing and why
- Flag risks, trade-offs, or alternative approaches
- If you hit a blocker, say so immediately — don't guess
- If requirements change mid-implementation, pause and realign

### After Work
- Summarize what was built
- List any known limitations or TODOs
- Suggest next steps

### What to Ask (not assume):
- "Should this validate input, or can we trust the caller?"
- "Should this be a separate function or inline?"
- "Do we need to handle this edge case?"
- "Is this the right abstraction level?"

---

## 8. Security Practices

- Never hardcode secrets, API keys, or credentials
- Validate and sanitize all external input
- Use parameterized queries (no string concatenation for SQL/commands)
- Avoid `eval()`, `exec()`, or dynamic code execution
- Check OWASP Top 10 for web-facing code
- Review subprocess calls for command injection risks

---

## 9. Performance Awareness

- Don't optimize prematurely — make it work, then make it fast
- BUT: don't introduce obviously O(n^2) when O(n) is just as simple
- Use appropriate data structures (sets for lookups, dicts for key-value)
- Be mindful of memory with large files/datasets
- Profile before optimizing — measure, don't guess

---

## 10. Specification-Driven Development

### How to Use Specs

Feature specs live in the `specs/` directory. Each spec defines:
- **What** the feature does (user-facing behavior)
- **Why** it exists (motivation/problem)
- **Acceptance criteria** (how to verify it works)
- **Edge cases** (what could go wrong)

### Workflow with Specs
1. Read the spec thoroughly
2. Break it into small, testable steps
3. Create a task list from the spec
4. Implement step-by-step following TDD
5. Check each acceptance criterion as you go
6. Mark the spec as complete when all criteria pass

---

## 11. Pre-Implementation Checklist

Before writing ANY code, verify:

- [ ] Requirements are clear (ask if not)
- [ ] Test framework is set up and running
- [ ] You know where the new code should live
- [ ] You've identified existing code that can be reused
- [ ] You've broken the work into small steps
- [ ] You've created a task list

---

## 12. Definition of Done

A feature/fix is "done" when:

- [ ] All acceptance criteria from the spec are met
- [ ] All tests pass (unit + integration where applicable)
- [ ] Code follows the quality standards above
- [ ] No security vulnerabilities introduced
- [ ] Git history is clean (atomic, well-described commits)
- [ ] The feature works in the actual UI/system (not just in tests)
