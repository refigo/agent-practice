# Language Feedback Echo Loop

LangGraph agent that closes the **output side** of an English-learning loop: it takes a day's worth of grammar/translation corrections — collected during real Claude Code sessions by the companion `english-feedback` skill — and emits a personalized **drill deck** the user can speak through that evening.

## Why

The companion skill (`~/workspaces/english-feedbacks`) already records every correction to `feedbacks/YYYY-MM-DD.md`. Mistakes are logged but never re-encountered for production practice. This agent closes that loop.

**Pedagogy: English immersion.** Drill cards hold a target English sentence + English-only supplementary notes. **No Korean cue, no translation step** — real-time speaking shouldn't route through Korean translation, so practice shouldn't teach that habit either.

## Pipeline (Orchestrator-Workers, parallel)

```
                                            ┌── (no entries) ──► emit_empty_deck ─► END
START ─► collect_feedback ──[has_content]───┤
                                            └─► select_entries (orchestrator)
                                                   │
                                                   ▼  Send fan-out, one worker per selected entry
                                                generate_one_card  generate_one_card  generate_one_card  ...
                                                   │  │  │
                                                   ▼  ▼  ▼  (rendezvous; raw_cards accumulated via reducer)
                                                enrich_with_glossary ─► format_and_emit ─► END
```

| Component | Role |
|-----------|------|
| `collect_feedback` | Deterministic regex parser for the daily feedback markdown files. Drops entries with no correction. |
| `select_entries` *(orchestrator)* | Filters cosmetic-only diffs, dedupes by original text, caps the deck at N. Produces the worker work-list. |
| `generate_one_card` *(worker)* | LLM call (gpt-4o-mini, structured output) that converts **one** feedback entry into **one** `DrillCard`. Run in parallel — one Send per selected entry. |
| `enrich_with_glossary` | Rendezvous after workers. For each card, calls the `pattern_glossary_lookup` tool and attaches `pattern_explanation`. |
| `format_and_emit` | Writes `decks/deck-YYYY-MM-DD.md` (human) and `.json` (machine contract for the future TTS / scoring agent). |
| `emit_empty_deck` | Fallback when no actionable entries — emits a "nothing to drill today" deck. |
| `pattern_glossary_lookup` (`@tool`) | Custom in-process LangChain tool: returns a 1-sentence learning note for a given pattern tag (article, tense, preposition, …). |
| `has_content` (conditional edge) | Branches on `raw_entries` count — empty → `emit_empty_deck`, else → `select_entries`. |
| `dispatch_workers` (conditional edge, `Send`) | Fans out one `Send("generate_one_card", {"entry": e})` per selected entry. Workers run in parallel; results merge via an `operator.add` reducer on `raw_cards`. |

### Advanced pattern — Orchestrator-Workers (LangGraph `Send` API)

`select_entries` plays the **orchestrator** role (deterministic curation in v0; can be upgraded to an LLM-driven planner later). It hands a per-entry payload to each `generate_one_card` **worker** via `Send`. Workers execute in parallel, each producing one card focused on a single mistake (better prompt-per-task than the prior single-shot batch generator). The reducer on `raw_cards` concatenates all worker outputs before the graph proceeds to enrichment and emission.

## State

```python
class TrainerState(TypedDict, total=False):
    target_date: str                                       # "YYYY-MM-DD"
    feedback_paths: list[str]                              # source files/dirs
    raw_entries: list[FeedbackEntry]
    selected_entries: list[FeedbackEntry]                  # orchestrator output
    raw_cards: Annotated[list[DrillCard], operator.add]    # parallel-worker reducer
    drill_cards: list[DrillCard]                           # enriched final
    output_paths: dict[str, str]                           # {"md": "...", "json": "..."}
    deck_cap: int                                          # max cards (default 10)
```

## Drill card fields (English-immersion contract)

- `target_en` — corrected, natural English sentence (the core thing to drill)
- `original_mistake` — what the user originally produced
- `mistake_note_en` — one English sentence on what was wrong
- `pattern_tag` — closed taxonomy: `article`, `tense`, `preposition`, `word-choice`, `phrasal-verb`, `register`, `translation`, `other`
- `paraphrases_en` — 1-2 alternative natural phrasings
- `pattern_explanation` — added by `enrich_with_glossary` via the tool

## Run

### Try the live demo

The Streamlit Cloud build ships with a built-in sample feedback log — no upload needed. Just hit **Generate today's deck** to see the orchestrator-workers pipeline produce a deck end-to-end.

> *Deployed URL: **TBD** (fill in after `share.streamlit.io` deploy)*

### Run locally

```bash
cp .env.example .env
# fill in OPENAI_API_KEY (https://platform.openai.com/api-keys)

uv sync
uv run streamlit run app.py
```

The sidebar exposes three feedback-source modes:

1. **Paste / edit text** *(default — works anywhere, includes a sample to load)*
2. **Upload .md file** — drag in any `english-feedback` daily log
3. **Local directory (dev only)** — point at `~/workspaces/english-feedbacks/feedbacks` when running locally with the companion skill installed

Each card renders in an expander; download buttons emit `deck.md` and `deck.json`. The chat input accepts per-card follow-ups (e.g., `Card 2: give me 3 more examples` — replies are English-only by design).

### Deploy on Streamlit Cloud

1. Push this repo to GitHub.
2. Visit [share.streamlit.io](https://share.streamlit.io/), click **New app**, point it at this repo with `english-output-trainer/app.py` as the entrypoint.
3. Under *App settings → Secrets*, paste:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
4. Deploy. The app reads `OPENAI_API_KEY` from `st.secrets` and writes deck artifacts to ephemeral disk (downloadable via the in-app buttons).

### Headless / notebook run

```bash
# file-based (local)
uv run python -c "from agent import run_for_date; print(run_for_date('2026-04-07', ['~/workspaces/english-feedbacks/feedbacks/2026-04-07.md']))"

# text-based (works anywhere — same path the Streamlit UI uses)
uv run python -c "from agent import run_for_text; print(run_for_text('2026-05-18', open('sample.md').read()))"

# or full walk-through
uv run jupyter nbconvert --to notebook --execute notebook.ipynb --output notebook.ipynb
```

The smoke runs write `decks/deck-YYYY-MM-DD.{md,json}`. An empty input exercises the `emit_empty_deck` conditional branch.

## Documents & files

- `agent.py` — LangGraph agent module (state, nodes, tool, graph builder, Q&A helper, `run_for_date` / `run_for_text`)
- `app.py` — Streamlit chat UI (imports `agent`; supports paste / upload / local-dir modes; cloud-secrets aware)
- `requirements.txt` — pinned for Streamlit Cloud
- `.streamlit/secrets.toml.example` — secrets template (real `secrets.toml` is gitignored)
- `notebook.ipynb` — implementation walkthrough + smoke runs
- `DESIGN.md` — full design rationale, open questions, roadmap

## Out of scope (separate downstream agent)

- TTS / audio playback
- Speech-to-text + spoken-answer scoring
- Scheduling / push notifications
