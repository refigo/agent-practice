"""Streamlit chat UI for the Language Feedback Echo Loop agent.

Run locally:
    uv run streamlit run app.py

Deployed on Streamlit Cloud — set OPENAI_API_KEY in app secrets.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import streamlit as st


# ----------------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Language Feedback Echo Loop", page_icon=":speech_balloon:")
st.title("Language Feedback Echo Loop")
st.caption(
    "Turn yesterday's English mistakes into tonight's spoken reps. "
    "Paste your `english-feedback` log (or use the built-in sample), then generate a personalized drill deck."
)


# ----------------------------------------------------------------------------
# Secret / API key bootstrap — must happen before importing agent.py
# ----------------------------------------------------------------------------

def _bootstrap_api_key() -> bool:
    """Pull OPENAI_API_KEY from st.secrets if not already in os.environ."""
    if os.environ.get("OPENAI_API_KEY"):
        return True
    try:
        key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        return False
    if key:
        os.environ["OPENAI_API_KEY"] = key
        return True
    return False


_has_key = _bootstrap_api_key()
if not _has_key:
    st.error(
        "🔑 **OPENAI_API_KEY is not configured.** "
        "Set it in your `.env` file (local) or in *Settings → Secrets* on Streamlit Cloud, then reload."
    )
    st.stop()

# Import only after the key is in the env, so ChatOpenAI sees it.
from agent import answer_card_question, run_for_date, run_for_text  # noqa: E402


# ----------------------------------------------------------------------------
# Built-in sample feedback (so reviewers can try without uploading anything)
# ----------------------------------------------------------------------------

SAMPLE_FEEDBACK = """# English Feedback - 2026-05-18

---

### 09:12

**Original:** I want to asking you about the code
**Corrected:** I want to ask you about the code.
**Notes:** After "want to," use the base form of the verb ("ask"), not the gerund ("asking").

---

### 10:30

**Original:** I make a light agent skill like this english feedback feature.
**Corrected:** I made a lightweight agent skill like this English feedback feature.
**Notes:** Past tense; "lightweight" is one word; capitalize "English."

---

### 11:05

**Original (Korean):** 이 함수가 어떻게 동작하는지 설명해줘
**Translated:** Can you explain how this function works?
**Notes:** Standard polite request form.

---

### 14:22

**Original:** I'm interesting in this topic
**Corrected:** I'm interested in this topic.
**Notes:** Use the -ed form for the speaker's feeling; -ing describes the topic itself.
"""


# ----------------------------------------------------------------------------
# Sidebar — config
# ----------------------------------------------------------------------------

DEFAULT_FEEDBACK_DIR = os.path.expanduser("~/workspaces/english-feedbacks/feedbacks")

with st.sidebar:
    st.header("Settings")
    target = st.date_input("Target date", value=date.today())
    deck_cap = st.slider("Deck cap (max cards)", 1, 20, 10)

    st.divider()
    st.subheader("Feedback source")
    source_mode = st.radio(
        "Choose how to provide the day's feedback log:",
        options=("Paste / edit text", "Upload .md file", "Local directory (dev only)"),
        index=0,
        help="Paste mode includes a sample you can try immediately.",
    )

    feedback_text = ""
    feedback_paths: list[str] = []

    if source_mode == "Paste / edit text":
        if st.button("Load sample", use_container_width=True):
            st.session_state["pasted_text"] = SAMPLE_FEEDBACK
        feedback_text = st.text_area(
            "Feedback markdown",
            value=st.session_state.get("pasted_text", SAMPLE_FEEDBACK),
            height=260,
            key="pasted_text",
        )
    elif source_mode == "Upload .md file":
        up = st.file_uploader("Upload a feedback markdown file", type=["md", "markdown", "txt"])
        if up is not None:
            feedback_text = up.read().decode("utf-8")
            st.success(f"Loaded `{up.name}` ({len(feedback_text):,} chars)")
    else:
        feedback_dir = st.text_input("Feedback directory", value=DEFAULT_FEEDBACK_DIR)
        feedback_paths = [feedback_dir]

    st.divider()
    if st.button("Generate today's deck", type="primary", use_container_width=True):
        st.session_state["pending_generation"] = {
            "target_date": target.isoformat(),
            "deck_cap": deck_cap,
            "feedback_text": feedback_text,
            "feedback_paths": feedback_paths,
            "source_mode": source_mode,
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
    deck_cap = pending["deck_cap"]
    feedback_text = pending["feedback_text"]
    feedback_paths = pending["feedback_paths"]
    source_mode = pending["source_mode"]

    _push("user", f"Generate the drill deck for **{target_date}**.")
    with st.spinner("Fanning out workers across the day's feedback…"):
        try:
            if source_mode == "Local directory (dev only)":
                result = run_for_date(target_date, feedback_paths, deck_cap=deck_cap)
            else:
                if not feedback_text.strip():
                    _push("assistant", "⚠️ No feedback text provided. Paste your log or load the sample.")
                    st.rerun()
                result = run_for_text(target_date, feedback_text, deck_cap=deck_cap)

            st.session_state["deck"] = result
            n_entries = len(result.get("raw_entries", []))
            n_cards = len(result.get("drill_cards", []))
            paths = result.get("output_paths", {})
            if n_cards == 0:
                summary = (
                    f"No actionable feedback found for **{target_date}** — nothing to drill today."
                )
            else:
                summary = (
                    f"Parsed **{n_entries}** entries → fanned out to **{n_cards}** parallel workers "
                    f"→ enriched and rendered the deck below."
                )
            _push("assistant", summary)
        except Exception as e:
            _push("assistant", f"❌ Generation failed: `{type(e).__name__}: {e}`")


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
    reply: str
    deck = st.session_state.get("deck")
    if not deck or not deck.get("drill_cards"):
        reply = "Generate a deck first (use the sidebar)."
    else:
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
                reply = f"❌ Tutor reply failed: `{type(e).__name__}: {e}`"
    _push("assistant", reply)
    st.rerun()
