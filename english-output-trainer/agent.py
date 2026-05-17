"""Language Feedback Echo Loop — LangGraph agent.

Pipeline (with Orchestrator-Workers advanced pattern):

    START
      |
      v
    collect_feedback ── [has_content?] ── (empty) ──► emit_empty_deck ──► END
      |                                                                    ^
      v (entries present)                                                  |
    select_entries (orchestrator)                                          |
      |                                                                    |
      v (Send fan-out, one per selected entry)                             |
    generate_one_card (worker, parallel)                                   |
      |                                                                    |
      v (rendezvous after all workers)                                     |
    enrich_with_glossary ──► format_and_emit ──► END
"""

from __future__ import annotations

import json
import operator
import os
import re
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

load_dotenv()


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------

class FeedbackEntry(TypedDict):
    timestamp: str
    original: str
    corrected: str
    notes: str
    source_lang: Literal["en", "ko", "mixed"]


class DrillCard(TypedDict, total=False):
    target_en: str
    original_mistake: str
    mistake_note_en: str
    pattern_tag: str
    paraphrases_en: list[str]
    pattern_explanation: str


class TrainerState(TypedDict, total=False):
    target_date: str
    feedback_paths: list[str]
    feedback_text: str  # inline markdown content (alternative to feedback_paths)
    raw_entries: list[FeedbackEntry]
    selected_entries: list[FeedbackEntry]
    # Workers append in parallel — reducer concatenates worker outputs.
    raw_cards: Annotated[list[DrillCard], operator.add]
    # Enriched, final form written by enrich_with_glossary.
    drill_cards: list[DrillCard]
    output_paths: dict[str, str]
    deck_cap: int


# ----------------------------------------------------------------------------
# Feedback file parser
# ----------------------------------------------------------------------------

ENTRY_BLOCK_RE = re.compile(r"^### (.*?)$\n(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)
ORIGINAL_RE = re.compile(r"^\*\*Original(?: \(Korean\))?:\*\*\s*(.+?)$", re.MULTILINE)
CORRECTED_RE = re.compile(r"^\*\*(?:Corrected|Translated):\*\*\s*(.+?)$", re.MULTILINE)
NOTES_RE = re.compile(r"^\*\*Notes:\*\*\s*(.+?)$", re.MULTILINE)
NO_CORRECTION_RE = re.compile(r"\*\*\(No corrections needed\.\)\*\*")


def parse_feedback_text(text: str) -> list[FeedbackEntry]:
    """Parse feedback markdown content directly (no file IO)."""
    entries: list[FeedbackEntry] = []
    for m in ENTRY_BLOCK_RE.finditer(text):
        ts = m.group(1).strip()
        if ts.startswith("$("):
            ts = ""
        body = m.group(2)
        orig_m = ORIGINAL_RE.search(body)
        if not orig_m:
            continue
        is_ko = "Original (Korean):" in body
        corr_m = CORRECTED_RE.search(body)
        notes_m = NOTES_RE.search(body)
        corrected = "" if NO_CORRECTION_RE.search(body) else (corr_m.group(1).strip() if corr_m else "")
        entries.append(FeedbackEntry(
            timestamp=ts,
            original=orig_m.group(1).strip(),
            corrected=corrected,
            notes=notes_m.group(1).strip() if notes_m else "",
            source_lang="ko" if is_ko else "en",
        ))
    return entries


def parse_feedback_file(path: Path) -> list[FeedbackEntry]:
    return parse_feedback_text(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# Node: collect_feedback
# ----------------------------------------------------------------------------

def collect_feedback(state: TrainerState) -> dict:
    entries: list[FeedbackEntry] = []
    if state.get("feedback_text"):
        entries.extend(parse_feedback_text(state["feedback_text"]))
    for p in state.get("feedback_paths") or []:
        path = Path(p).expanduser()
        if path.is_file():
            entries.extend(parse_feedback_file(path))
        elif path.is_dir():
            for fp in sorted(path.glob("*.md")):
                entries.extend(parse_feedback_file(fp))
    entries = [e for e in entries if e["corrected"]]
    return {"raw_entries": entries}


# ----------------------------------------------------------------------------
# Node: select_entries (Orchestrator)
# ----------------------------------------------------------------------------

def _is_cosmetic(entry: FeedbackEntry) -> bool:
    """Drop entries where the only change is capitalization/punctuation."""
    a = entry["original"].strip().lower().rstrip(".!?, ")
    b = entry["corrected"].strip().lower().rstrip(".!?, ")
    return a == b


def select_entries(state: TrainerState) -> dict:
    """Orchestrator: filter cosmetic entries, dedupe by original text, cap at N."""
    cap = state.get("deck_cap") or 10
    seen: set[str] = set()
    selected: list[FeedbackEntry] = []
    for e in state["raw_entries"]:
        if _is_cosmetic(e):
            continue
        key = e["original"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(e)
        if len(selected) >= cap:
            break
    return {"selected_entries": selected}


# ----------------------------------------------------------------------------
# Worker: generate_one_card
# ----------------------------------------------------------------------------

class _DrillCardModel(BaseModel):
    target_en: str = Field(description="The corrected, natural English sentence the user should drill (shadowing/self-production).")
    original_mistake: str = Field(description="What the user actually said/wrote, copied verbatim.")
    mistake_note_en: str = Field(description="One concise English sentence explaining what was wrong or unnatural. English only — do not write Korean.")
    pattern_tag: Literal[
        "article", "tense", "preposition", "word-choice", "phrasal-verb", "register", "translation", "other"
    ] = Field(description="Closed taxonomy tag for the error pattern.")
    paraphrases_en: list[str] = Field(description="1-2 alternative natural English phrasings of the same idea.")


_WORKER_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.3).with_structured_output(_DrillCardModel)

_WORKER_PROMPT = """You are crafting ONE English-output drill card for a Korean speaker who is internalizing English directly (no Korean translation step).

The feedback entry below is a single real correction. Produce one drill card:

- target_en: the corrected/natural English sentence (use the corrected/translated form from the entry).
- original_mistake: what the user originally produced (copy verbatim).
- mistake_note_en: ONE concise English sentence on what was wrong. English only — do not write Korean.
- pattern_tag: pick from: article, tense, preposition, word-choice, phrasal-verb, register, translation, other.
- paraphrases_en: 1-2 alternative natural English phrasings of the same idea.

Feedback entry (JSON):
{entry_json}
"""


class _WorkerInput(TypedDict):
    """Input payload passed via Send to each worker."""
    entry: FeedbackEntry


def generate_one_card(payload: _WorkerInput) -> dict:
    """Worker: take ONE feedback entry, emit ONE drill card.

    Returns a partial state update that the `operator.add` reducer concatenates
    onto `raw_cards`.
    """
    entry_json = json.dumps(payload["entry"], ensure_ascii=False, indent=2)
    card_model: _DrillCardModel = _WORKER_LLM.invoke(_WORKER_PROMPT.format(entry_json=entry_json))
    return {"raw_cards": [card_model.model_dump()]}


def dispatch_workers(state: TrainerState) -> list[Send]:
    """Conditional edge that fans out one Send per selected entry."""
    return [Send("generate_one_card", {"entry": e}) for e in state["selected_entries"]]


# ----------------------------------------------------------------------------
# Tool: pattern_glossary_lookup
# ----------------------------------------------------------------------------

PATTERN_GLOSSARY: dict[str, str] = {
    "article": "Articles (a/an/the) — English requires articles before most singular countable nouns; common L1-Korean omission.",
    "tense": "Tense / verb form — match the time frame; after modals, 'to', or auxiliaries use the bare infinitive.",
    "preposition": "Prepositions are highly idiomatic; learn them as fixed chunks with their host verb or noun.",
    "word-choice": "Word choice — pick the natural collocate native speakers actually use, not just a dictionary-correct synonym.",
    "phrasal-verb": "Phrasal verbs are verb + particle units with non-compositional meaning; memorize as whole chunks.",
    "register": "Register — match formality to the context (chat / email / academic / spoken).",
    "translation": "Direct translation from Korean often produces grammatical-but-unnatural English; learn the L2-native phrasing instead.",
    "other": "General usage / naturalness issue — read the corrected sentence aloud and notice what shifted.",
}


@tool
def pattern_glossary_lookup(pattern_tag: str) -> str:
    """Return a brief English-learning glossary explanation for a given pattern tag.

    Args:
        pattern_tag: One of: article, tense, preposition, word-choice, phrasal-verb, register, translation, other.
    """
    return PATTERN_GLOSSARY.get(pattern_tag, PATTERN_GLOSSARY["other"])


def enrich_with_glossary(state: TrainerState) -> dict:
    """Rendezvous after workers: enrich each card with a glossary note via the tool."""
    enriched: list[DrillCard] = []
    for card in state.get("raw_cards", []):
        explanation = pattern_glossary_lookup.invoke({"pattern_tag": card["pattern_tag"]})
        enriched.append({**card, "pattern_explanation": explanation})
    return {"drill_cards": enriched}


# ----------------------------------------------------------------------------
# Node: format_and_emit
# ----------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = Path("./decks")


def format_and_emit(state: TrainerState) -> dict:
    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
    target = state["target_date"]
    md_path = DEFAULT_OUTPUT_DIR / f"deck-{target}.md"
    json_path = DEFAULT_OUTPUT_DIR / f"deck-{target}.json"

    lines: list[str] = [f"# Drill Deck — {target}", ""]
    for i, c in enumerate(state["drill_cards"], 1):
        lines += [
            f"## Card {i} — `{c['pattern_tag']}`",
            f"**Target:** {c['target_en']}",
            f"**Note:** {c['mistake_note_en']}",
            f"**Originally said:** {c['original_mistake']}",
        ]
        if c.get("pattern_explanation"):
            lines.append(f"**Pattern:** {c['pattern_explanation']}")
        lines.append("**Paraphrases:**")
        lines.extend(f"- {p}" for p in c["paraphrases_en"])
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(state["drill_cards"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"output_paths": {"md": str(md_path), "json": str(json_path)}}


def emit_empty_deck(state: TrainerState) -> dict:
    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
    target = state["target_date"]
    md_path = DEFAULT_OUTPUT_DIR / f"deck-{target}.md"
    md_path.write_text(
        f"# Drill Deck — {target}\n\n*No actionable feedback found for this date — nothing to drill today.*\n",
        encoding="utf-8",
    )
    return {"output_paths": {"md": str(md_path), "json": ""}}


# ----------------------------------------------------------------------------
# Conditional edges
# ----------------------------------------------------------------------------

def has_content(state: TrainerState) -> Literal["select_entries", "emit_empty_deck"]:
    return "select_entries" if state.get("raw_entries") else "emit_empty_deck"


# ----------------------------------------------------------------------------
# Graph builder
# ----------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(TrainerState)
    graph.add_node("collect_feedback", collect_feedback)
    graph.add_node("select_entries", select_entries)
    graph.add_node("generate_one_card", generate_one_card)
    graph.add_node("enrich_with_glossary", enrich_with_glossary)
    graph.add_node("format_and_emit", format_and_emit)
    graph.add_node("emit_empty_deck", emit_empty_deck)

    graph.add_edge(START, "collect_feedback")
    graph.add_conditional_edges(
        "collect_feedback",
        has_content,
        {"select_entries": "select_entries", "emit_empty_deck": "emit_empty_deck"},
    )
    graph.add_conditional_edges(
        "select_entries",
        dispatch_workers,
        ["generate_one_card"],
    )
    graph.add_edge("generate_one_card", "enrich_with_glossary")
    graph.add_edge("enrich_with_glossary", "format_and_emit")
    graph.add_edge("format_and_emit", END)
    graph.add_edge("emit_empty_deck", END)
    return graph.compile()


# Module-level compiled app for convenience.
app = build_graph()


def run_for_date(target_date: str, feedback_paths: list[str], *, deck_cap: int = 10) -> dict:
    """Convenience: invoke the compiled graph with a clean initial state."""
    return app.invoke({
        "target_date": target_date,
        "feedback_paths": feedback_paths,
        "feedback_text": "",
        "raw_entries": [],
        "selected_entries": [],
        "raw_cards": [],
        "drill_cards": [],
        "output_paths": {},
        "deck_cap": deck_cap,
    })


def run_for_text(target_date: str, feedback_text: str, *, deck_cap: int = 10) -> dict:
    """Convenience: run the agent over inline markdown feedback text (no file IO)."""
    return app.invoke({
        "target_date": target_date,
        "feedback_paths": [],
        "feedback_text": feedback_text,
        "raw_entries": [],
        "selected_entries": [],
        "raw_cards": [],
        "drill_cards": [],
        "output_paths": {},
        "deck_cap": deck_cap,
    })


# ----------------------------------------------------------------------------
# Standalone Q&A LLM for chat follow-ups in the Streamlit UI.
# ----------------------------------------------------------------------------

_QA_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)


def answer_card_question(card: DrillCard, question: str) -> str:
    """English-only tutor reply for a follow-up question about a specific drill card."""
    prompt = (
        "You are an English speaking tutor. Reply in ENGLISH ONLY — never use Korean. "
        "Keep it under 5 short sentences.\n\n"
        f"The learner is drilling this card:\n"
        f"- Target sentence: {card.get('target_en')}\n"
        f"- Their original mistake: {card.get('original_mistake')}\n"
        f"- Pattern: {card.get('pattern_tag')} — {card.get('pattern_explanation','')}\n\n"
        f"Their question: {question}\n\n"
        "Reply concisely. If they ask for more example sentences, give 2-3 natural ones."
    )
    return _QA_LLM.invoke(prompt).content
