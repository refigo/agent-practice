# Language Feedback Echo Loop — Design Draft

> **Working title (가제):** *Language Feedback Echo Loop*. Final name TBD — see `NAMING.md`.
> **Status:** v0 draft. Open questions marked with `❓`.

## 1. Problem

The user practices English by prompting Claude Code in English across multiple sessions / workstations. The existing `english-feedback` skill (in `~/workspaces/english-feedbacks`) appends every correction/translation to a daily file:

```
feedbacks/YYYY-MM-DD.md
  ### HH:MM
  **Original:**     <user's text>
  **Corrected:**    <natural English>
  **Notes:**        <one-sentence explanation>
```

Input loop is closed. **Output loop is not.** Mistakes are logged but never re-encountered for production practice. The user wants an agent that takes a day's feedback and turns it into a *spoken-output drill set* the user can practice the same evening or next morning.

Spoken execution + scoring is **explicitly out of scope** for this agent — that becomes a separate downstream agent (auth / record / STT / compare). This agent ends at "drill content emitted as markdown + JSON."

## 2. Agent Spec

### Name
**Language Feedback Echo Loop** *(working title — see `NAMING.md` for candidate list and ranking)*.

### Purpose
Convert daily English-feedback logs (real corrections from real Claude sessions) into a personalized speaking-drill deck targeting the user's actual recurring mistakes.

### Core Features (≥ 3)
1. **Aggregate** — read one or more `feedbacks/YYYY-MM-DD.md` files from a configured source directory (assumed pre-synced via git/iCloud/etc).
2. **Curate** — drop "no corrections needed" entries, dedupe near-identical mistakes, cluster by error pattern (article, tense, word-choice, phrasal verb, etc.).
3. **Select & rank** — prioritize: (a) repeated patterns within the day, (b) corrections with substantive grammatical change vs. cosmetic, (c) variety across error types so the deck isn't monotonous. Cap at N (default 10–15).
4. **Generate drill cards** — *English-immersion model: no Korean cue, no translation step.* The user's pedagogy goal is to internalize English directly without routing through Korean (avoids the translate-from-Korean bottleneck during real conversation). For each selected item, produce a card with:
   - `target_en`: the corrected English sentence — **the core drill artifact**, repeated/shadowed until natural
   - `original_mistake`: what the user actually said (for awareness, not for translation)
   - `mistake_note_en`: brief English note on what was wrong (kept in English to preserve immersion)
   - `pattern_tag`: error category (closed taxonomy)
   - `paraphrases_en`: 1–2 alternative natural phrasings of the same idea — gives variation across reps and prevents memorizing one fixed string
5. **Format & emit** — output a markdown drill sheet (human-readable) **and** a JSON file (machine-readable, for the future TTS/scoring agent).

### Graph Structure (LangGraph)

```
                ┌──────────────────────┐
                │       START          │
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │  collect_feedback    │  read MD files → State.raw_entries
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │  curate_and_cluster  │  drop noise + cluster patterns
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │  select_and_rank     │  pick top-N drill candidates
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │  generate_drill_cards│  LLM: cue_ko + target + paraphrase
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │  format_and_emit     │  write deck.md + deck.json
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │        END           │
                └──────────────────────┘
```

5 nodes total. v0 ships the minimal working slice — `collect_feedback → generate_drill_cards → format_and_emit` — with `curate_and_cluster` and `select_and_rank` initially inlined into the LLM prompt. They split out into dedicated nodes once selection quality demands per-stage observability.

## 3. State (TypedDict)

```python
from typing import TypedDict, Literal
from datetime import date

class FeedbackEntry(TypedDict):
    timestamp: str         # "HH:MM"
    original: str
    corrected: str         # may be empty for "no corrections"
    notes: str
    source_lang: Literal["en", "ko", "mixed"]

class DrillCard(TypedDict):
    target_en: str               # core sentence to drill (immersion model: no KO cue)
    original_mistake: str        # what the user actually said (awareness only)
    mistake_note_en: str         # brief English note on what was wrong
    pattern_tag: str             # error category (closed taxonomy, see §5)
    paraphrases_en: list[str]    # 1-2 alternative natural phrasings

class TrainerState(TypedDict):
    target_date: str               # "YYYY-MM-DD"
    feedback_dirs: list[str]       # source roots
    raw_entries: list[FeedbackEntry]
    selected: list[FeedbackEntry]  # post-curate
    drill_cards: list[DrillCard]
    output_paths: dict[str, str]   # {"md": "...", "json": "..."}
```

## 4. v0 Build Plan

- **Design** — this document. Mirrored as the opening markdown cell of the notebook.
- **Implementation** — `notebook.ipynb`:
  1. Setup cell (langgraph + dependencies via uv, env loading)
  2. State definitions (TypedDicts above)
  3. Node implementations — `collect_feedback` (deterministic parser), `generate_drill_cards` (LLM, structured output), `format_and_emit` (markdown + JSON writer)
  4. Graph wiring (`StateGraph`, edges, compile)
  5. Smoke run on a sample feedback file (`~/workspaces/english-feedbacks/feedbacks/2026-04-07.md`)
  6. Print emitted deck.md to verify output shape end-to-end

## 5. Resolved Decisions

- ✅ **Cross-machine sync.** `english-feedbacks` repo gets a private git remote; each workstation push/pulls. Trainer reads the local working copy. No cloud DB / Dropbox needed.
- ✅ **Drill format.** English-immersion. **No Korean cue.** Core artifact is `target_en`, drilled by shadowing/self-production. Supplementary fields (`original_mistake`, `mistake_note_en`, `pattern_tag`, `paraphrases_en`) stay in English to preserve immersion. Rationale: real-time speaking shouldn't route through Korean translation, so practice shouldn't teach that habit.

## 6. Open Questions ❓

- ❓ **Deck size.** N = 10? 15? Or capped by estimated minutes-to-drill rather than count?
- ❓ **Pattern tags.** Closed taxonomy (article / tense / preposition / word-choice / phrasal / register / other)? Or free-form LLM-generated tags? Closed is more useful for tracking progress over weeks.
- ❓ **Multi-day rollup.** v0 = single day. v1 → "give me the week's deck, deduped against last week"? (Probably yes — defer.)
- ❓ **Run trigger.** Manual `uv run` for now. Later: cron/launchd nightly? Slack/Discord delivery? Out of v0 scope.
- ❓ **Naming.** Selecting from candidate list (see naming doc).

## 7. Non-Goals (v0)

- TTS / audio playback.
- Speech-to-text + spoken-answer scoring (separate downstream agent).
- Scheduling, push notifications, mobile delivery.
- Cross-machine sync mechanism (assumed solved upstream).
- Long-term progress tracking / SRS scheduling. (Strong v2 candidate.)

## 8. Roadmap Sketch

| Stage | Add |
|-------|-----|
| v0     | LangGraph skeleton, 3 working nodes, single-day deck |
| v0.1   | Pattern-tag taxonomy refinement, multi-day rollup, dedupe vs. recent decks |
| v0.2   | Spaced repetition: per-card mastery state, "due today" queue |
| v0.3   | TTS hook (downstream agent contract via deck.json) |
| v0.4   | Speaking-execution agent: record → STT → similarity score |
| v1     | End-to-end loop: yesterday's mistakes → tonight's spoken reps with score |
