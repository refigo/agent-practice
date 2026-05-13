"""Streamlit chat UI for the Language Feedback Echo Loop agent.

Run with:
    uv run streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import streamlit as st

from agent import answer_card_question, run_for_date


# ----------------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Language Feedback Echo Loop", page_icon=":speech_balloon:")
st.title("Language Feedback Echo Loop")
st.caption(
    "Turn yesterday's English mistakes into tonight's spoken reps. "
    "Generate a drill deck from your `english-feedback` logs, then ask follow-up questions per card."
)


# ----------------------------------------------------------------------------
# Sidebar — config
# ----------------------------------------------------------------------------

DEFAULT_FEEDBACK_DIR = os.path.expanduser("~/workspaces/english-feedbacks/feedbacks")

with st.sidebar:
    st.header("Settings")
    target = st.date_input("Target date", value=date(2026, 4, 7))
    feedback_dir = st.text_input("Feedback directory", value=DEFAULT_FEEDBACK_DIR)
    deck_cap = st.slider("Deck cap (max cards)", 1, 20, 10)
    st.divider()
    if st.button("Generate today's deck", type="primary", use_container_width=True):
        st.session_state["pending_generation"] = {
            "target_date": target.isoformat(),
            "feedback_dir": feedback_dir,
            "deck_cap": deck_cap,
        }


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "deck" not in st.session_state:
    st.session_state["deck"] = None


def _push(role: str, content: str) -> None:
    st.session_state["messages"].append({"role": role, "content": content})


# ----------------------------------------------------------------------------
# Generation trigger
# ----------------------------------------------------------------------------

pending = st.session_state.pop("pending_generation", None)
if pending:
    target_date = pending["target_date"]
    feedback_dir = pending["feedback_dir"]
    deck_cap = pending["deck_cap"]

    # Prefer the day-specific file if it exists; otherwise pass the directory
    # and let collect_feedback walk it.
    day_file = Path(feedback_dir) / f"{target_date}.md"
    feedback_paths = [str(day_file)] if day_file.exists() else [feedback_dir]

    _push("user", f"Generate the drill deck for **{target_date}**.")
    with st.spinner(f"Fanning out workers across the day's feedback…"):
        try:
            result = run_for_date(target_date, feedback_paths, deck_cap=deck_cap)
            st.session_state["deck"] = result
            n_entries = len(result.get("raw_entries", []))
            n_cards = len(result.get("drill_cards", []))
            paths = result.get("output_paths", {})
            if n_cards == 0:
                summary = (
                    f"No actionable feedback found for **{target_date}** — nothing to drill today. "
                    f"(File: `{paths.get('md','?')}`)"
                )
            else:
                summary = (
                    f"Parsed **{n_entries}** entries → fanned out to **{n_cards}** parallel workers "
                    f"→ enriched and wrote `{paths.get('md','?')}` + `{paths.get('json','?')}`."
                )
            _push("assistant", summary)
        except Exception as e:
            _push("assistant", f":x: Generation failed: `{e}`")


# ----------------------------------------------------------------------------
# Conversation render
# ----------------------------------------------------------------------------

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ----------------------------------------------------------------------------
# Deck panel
# ----------------------------------------------------------------------------

deck = st.session_state.get("deck")
if deck and deck.get("drill_cards"):
    st.divider()
    st.subheader(f"Deck — {deck['target_date']}")
    for i, card in enumerate(deck["drill_cards"], 1):
        with st.expander(f"Card {i} — `{card['pattern_tag']}` — {card['target_en']}"):
            st.markdown(f"**Target (drill this):** {card['target_en']}")
            st.markdown(f"**Originally said:** {card['original_mistake']}")
            st.markdown(f"**Note:** {card['mistake_note_en']}")
            if card.get("pattern_explanation"):
                st.markdown(f"**Pattern:** {card['pattern_explanation']}")
            st.markdown("**Paraphrases:**")
            for p in card.get("paraphrases_en", []):
                st.markdown(f"- {p}")

    md_path = deck.get("output_paths", {}).get("md")
    json_path = deck.get("output_paths", {}).get("json")
    cols = st.columns(2)
    if md_path and Path(md_path).exists():
        cols[0].download_button(
            "Download deck.md",
            data=Path(md_path).read_text(encoding="utf-8"),
            file_name=Path(md_path).name,
            use_container_width=True,
        )
    if json_path and Path(json_path).exists():
        cols[1].download_button(
            "Download deck.json",
            data=Path(json_path).read_text(encoding="utf-8"),
            file_name=Path(json_path).name,
            use_container_width=True,
        )


# ----------------------------------------------------------------------------
# Chat input — follow-up Q&A about a card
# ----------------------------------------------------------------------------

prompt = st.chat_input(
    "Ask about a card (e.g., 'Card 2: give me 3 more examples') or just type 'help'."
)
if prompt:
    _push("user", prompt)
    reply = _handle_followup_unused = None
    deck = st.session_state.get("deck")
    if not deck or not deck.get("drill_cards"):
        reply = "Generate a deck first (use the sidebar)."
    else:
        # Heuristic: look for "card N" in the prompt; default to card 1.
        import re
        m = re.search(r"card\s*(\d+)", prompt, re.IGNORECASE)
        idx = int(m.group(1)) - 1 if m else 0
        cards = deck["drill_cards"]
        if idx < 0 or idx >= len(cards):
            reply = f"Card {idx+1} doesn't exist — deck has {len(cards)} cards."
        else:
            try:
                reply = answer_card_question(cards[idx], prompt)
            except Exception as e:
                reply = f":x: Tutor reply failed: `{e}`"
    _push("assistant", reply)
    st.rerun()
