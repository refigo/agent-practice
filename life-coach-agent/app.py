import asyncio
import uuid

import streamlit as st
from dotenv import load_dotenv
from openai.types.responses import ResponseTextDeltaEvent

from agents import Agent, Runner, SQLiteSession, WebSearchTool

load_dotenv()


INSTRUCTIONS = """\
당신은 따뜻하고 진심 어린 라이프 코치입니다.
사용자의 목표와 고민을 존중하며, 격려하는 톤으로 대화하세요.

원칙:
- 동기부여, 자기개발, 습관 형성, 생산성, 마인드셋과 관련된 질문을 받으면
  반드시 web_search 도구로 최신·검증된 정보를 먼저 찾아보세요.
- 검색 결과를 그대로 나열하지 말고, 사용자의 상황에 맞춰 핵심을 정리해 주세요.
- 답변은 한국어로, 따뜻하고 구체적으로. 실행 가능한 1~3개의 다음 행동을 함께 제안하세요.
- 이전 대화 내용을 기억하고 일관되게 사용자를 응원하세요.
"""


@st.cache_resource
def get_agent() -> Agent:
    return Agent(
        name="Life Coach",
        instructions=INSTRUCTIONS,
        model="gpt-4o-mini",
        tools=[WebSearchTool()],
    )


def get_session() -> SQLiteSession:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"life-coach-{uuid.uuid4().hex[:8]}"
    return SQLiteSession(st.session_state.session_id, "life_coach.db")


async def stream_reply(user_input: str, text_box, status_box) -> str:
    """Run the agent with streaming and incrementally update the UI.

    Returns the final assistant text.
    """
    agent = get_agent()
    session = get_session()
    result = Runner.run_streamed(agent, user_input, session=session)

    text_buffer = ""
    async for event in result.stream_events():
        # Token-by-token deltas from the model.
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            text_buffer += event.data.delta
            text_box.markdown(text_buffer)
            continue

        # High-level run items: tool calls, tool outputs, messages.
        if event.type == "run_item_stream_event":
            item = event.item
            if item.type == "tool_call_item":
                # WebSearchTool call → show "검색 중" hint.
                raw = getattr(item, "raw_item", None)
                query = None
                if raw is not None:
                    # Try common shapes for the search query.
                    query = getattr(raw, "query", None)
                    if query is None:
                        action = getattr(raw, "action", None)
                        if action is not None:
                            query = getattr(action, "query", None)
                label = f"🔎 웹 검색 중: {query}" if query else "🔎 웹 검색 중..."
                status_box.caption(label)
            elif item.type == "tool_call_output_item":
                status_box.caption("✅ 검색 결과 수신, 답변 정리 중...")

    return text_buffer


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def main() -> None:
    st.set_page_config(page_title="Life Coach", page_icon="🌱")
    st.title("🌱 Life Coach")
    st.caption(
        "동기부여 · 자기개발 · 습관 형성에 대해 무엇이든 물어보세요. "
        "필요하면 웹에서 최신 정보를 찾아 답해드릴게요."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.subheader("세션")
        st.code(st.session_state.get("session_id", "(아직 시작 전)"), language="text")
        if st.button("새 대화 시작", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pop("session_id", None)
            st.rerun()

    render_history()

    user_input = st.chat_input("무엇을 코칭해드릴까요?")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status_box = st.empty()
        text_box = st.empty()
        try:
            final_text = asyncio.run(stream_reply(user_input, text_box, status_box))
        except Exception as e:  # noqa: BLE001
            final_text = f"⚠️ 오류가 발생했어요: {e}"
            text_box.markdown(final_text)
        finally:
            status_box.empty()

    st.session_state.messages.append({"role": "assistant", "content": final_text})


if __name__ == "__main__":
    main()
