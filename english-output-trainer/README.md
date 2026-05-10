# Language Feedback Echo Loop

LangGraph agent that closes the **output side** of an English-learning loop: it takes a day's worth of grammar/translation corrections — collected during real Claude Code sessions by the companion `english-feedback` skill — and emits a personalized **drill deck** the user can speak through that evening.

## Why

The companion skill (`~/workspaces/english-feedbacks`) already records every correction to `feedbacks/YYYY-MM-DD.md`. Mistakes are logged but never re-encountered for production practice. This agent closes that loop.

**Pedagogy: English immersion.** Drill cards hold a target English sentence + English-only supplementary notes. **No Korean cue, no translation step** — real-time speaking shouldn't route through Korean translation, so practice shouldn't teach that habit either.

## Pipeline

```
                                            ┌── (no entries) ──► emit_empty_deck ─► END
START ─► collect_feedback ──[conditional]───┤
                                            └─► generate_drill_cards ─► enrich_with_glossary ─► format_and_emit ─► END
```

| Component | Role |
|-----------|------|
| `collect_feedback` | Deterministic regex parser for the daily feedback markdown files. Drops entries with no correction. |
| `generate_drill_cards` | LLM node (gpt-4o-mini, structured output). Selects, deduplicates, and converts entries into `DrillCard` records. |
| `enrich_with_glossary` | Calls the `pattern_glossary_lookup` tool for each card and attaches a learning note. |
| `format_and_emit` | Writes `decks/deck-YYYY-MM-DD.md` (human) and `.json` (machine contract for the future TTS / scoring agent). |
| `emit_empty_deck` | Fallback when no actionable entries — emits a "nothing to drill today" deck. |
| `pattern_glossary_lookup` (`@tool`) | Custom in-process LangChain tool: returns a 1-sentence learning note for a given pattern tag (article, tense, preposition, …). |
| `has_content` (conditional) | Branches on `raw_entries` count — empty → `emit_empty_deck`, else → `generate_drill_cards`. |

## State

```python
class TrainerState(TypedDict):
    target_date: str              # "YYYY-MM-DD"
    feedback_paths: list[str]     # source files/dirs
    raw_entries: list[FeedbackEntry]
    drill_cards: list[DrillCard]  # incl. pattern_explanation after enrich
    output_paths: dict[str, str]  # {"md": "...", "json": "..."}
```

## Drill card fields (English-immersion contract)

- `target_en` — corrected, natural English sentence (the core thing to drill)
- `original_mistake` — what the user originally produced
- `mistake_note_en` — one English sentence on what was wrong
- `pattern_tag` — closed taxonomy: `article`, `tense`, `preposition`, `word-choice`, `phrasal-verb`, `register`, `translation`, `other`
- `paraphrases_en` — 1-2 alternative natural phrasings
- `pattern_explanation` — added by `enrich_with_glossary` via the tool

## Run

```bash
cp .env.example .env
# fill in OPENAI_API_KEY (https://platform.openai.com/api-keys)

uv sync
uv run jupyter nbconvert --to notebook --execute notebook.ipynb --output notebook.ipynb
```

The smoke run inside the notebook parses `~/workspaces/english-feedbacks/feedbacks/2026-04-07.md` and writes `decks/deck-2026-04-07.{md,json}`.

A second smoke cell verifies the conditional-edge path by feeding the graph an empty file — it should branch through `emit_empty_deck` instead.

## Documents

- `DESIGN.md` — full design rationale, open questions, roadmap
- `notebook.ipynb` — implementation + smoke runs (start here)

## Out of scope (separate downstream agent)

- TTS / audio playback
- Speech-to-text + spoken-answer scoring
- Scheduling / push notifications
