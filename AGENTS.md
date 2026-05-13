# Codex Guidelines

Derived from Andrej Karpathy's observations on LLM coding pitfalls.

## 1. Think Before Coding

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and ask.

## 2. Simplicity First

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

## 3. Surgical Changes

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Transform tasks into verifiable goals:
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → ensure tests pass before and after.

For multi-step tasks, state a brief plan with verification steps before starting.

## 5. Knowledge Management

For multi-session work where context accumulates over time (research,
investigations, course notes, vendor evaluations, ongoing builds), use the
**LLM Wiki** pattern: a directory of LLM-maintained markdown that compounds
across sessions instead of being re-derived each time.

### Architecture

Three layers:

1. **Raw sources** — immutable inputs (articles, schemas, transcripts, data
   files). The LLM reads from these but never modifies them.
2. **The wiki** — LLM-maintained markdown: entity pages, decision records,
   investigations, summaries. The LLM owns this layer entirely.
3. **The schema** — this section in `AGENTS.md` (plus a per-project
   subsection) tells the LLM where the wiki lives and how to maintain it.

### Operations

- **Ingest.** When the user shares a source (a schema, a doc, a conversation
  snippet), read it, file it to the appropriate page, update `index.md`,
  append to `log.md`.
- **Query.** When asked a project-context question, read `index.md` and the
  tail of `log.md` first, then drill into linked pages. Cite wiki pages.
- **Lint.** Periodically health-check the wiki: contradictions, stale claims,
  orphan pages, missing cross-references.

### Conventions

- `index.md` — catalog. Every page listed once with a one-line summary,
  organized by category (entities, decisions, investigations). Read first;
  updated on every page change.
- `log.md` — chronological. Append-only, newest at the bottom, one heading
  per entry: `## [YYYY-MM-DD] <kind> | <title>` where `<kind>` is one of
  `ingest`, `decision`, `investigation`, `lint`.
- Page filenames: `kebab-case.md`. Cross-links: relative paths.
- After substantive work: update affected pages, refresh `index.md`, append
  to `log.md`. Pages can graduate to canonical docs once stable.

When starting a project that fits this shape, proactively suggest setting one
up. When resuming work on a project that already has one, read the relevant
pages before answering.

## 6. Project setup

When starting work in a project (working directory) that does **not** have a
project-level `AGENTS.md`, offer a one-time bootstrap as a single-line opt-in:

1. Copy `~/.Codex/AGENTS.md` to the repo root as `AGENTS.md` so the same
   baseline applies for anyone working in the repo.
2. Create a `wiki/` skeleton at the repo root (sibling of any existing
   `docs/`, not nested inside it) — `index.md`, `log.md`, and the
   `entities/`, `decisions/`, `investigations/` directories empty. Add a
   short "Wiki for this project" subsection to the new `AGENTS.md`
   describing read/write expectations and pointing at `wiki/`. The wiki
   pattern itself is already documented in section 5.

Rules:

- Make the offer at most once per conversation.
- Frame as a single sentence ("Want me to bootstrap a project `AGENTS.md` and
  llm-wiki here?"), not a prerequisite.
- Skip entirely for clearly throwaway work — one-off scripts, a single quick
  fix in a repo the user is not coming back to.
- If the user declines, do not raise it again in the same conversation.
- If a project-level `AGENTS.md` already exists, do nothing — assume it is
  intentional.

## Wiki for this project

This repo has an LLM Wiki at `wiki/` (see section 5 for the pattern).

- **Read first:** `wiki/index.md` (catalog) and the tail of `wiki/log.md` before answering project-context questions.
- **Write to:** `wiki/entities/`, `wiki/decisions/`, `wiki/investigations/` as appropriate. Update `index.md` and append to `log.md` after substantive work.
