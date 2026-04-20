import asyncio
import base64
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from openai.types.responses import ResponseTextDeltaEvent

from agents import (
    Agent,
    FileSearchTool,
    Runner,
    SQLiteSession,
    WebSearchTool,
    function_tool,
)
from openai import OpenAI

load_dotenv()


INSTRUCTIONS = """\
당신은 따뜻하고 진심 어린 라이프 코치입니다.
사용자의 목표와 고민을 존중하며, 격려하는 톤으로 대화하세요.

사용 가능한 도구:
- file_search: 사용자의 개인 목표/운동 루틴/훈련 일지가 담긴 문서를 검색합니다.
  사용자의 현재 상태·목표·진행 상황과 관련된 질문이면 이 도구를 먼저 쓰세요.
- web_search: 동기부여, 자기개발, 습관 형성, 생산성에 대한 최신 정보를 웹에서 찾습니다.
- generate_image: 비전 보드, 동기부여 포스터, 축하 이미지 등을 생성합니다.

원칙:
- 개인 목표·진행 상황 질문 → 먼저 file_search로 기록을 참조.
- 일반적인 팁/방법론 질문 → web_search 활용.
- 가능하면 두 결과를 결합해 "당신의 목표(file_search)에 맞는 방법(web_search)"을
  구체적으로 제안하세요.
- 검색 결과를 그대로 나열하지 말고, 사용자 상황에 맞춰 정리해 답하세요.
- 답변은 한국어로, 따뜻하고 구체적으로. 실행 가능한 1~3개의 다음 행동을 함께 제안하세요.
- 이전 대화 내용을 기억하고 일관되게 사용자를 응원하세요.

이미지 생성 원칙:
- 사용자가 비전 보드, 동기부여 이미지, 축하 이미지를 요청하면 generate_image를 사용하세요.
- 목표 달성 축하, 진행 상황 시각화, 새해/새달 비전 보드 등에 적극 활용하세요.
- 이미지 생성 전에 file_search로 사용자의 목표를 먼저 확인하면 더 개인화된 이미지를 만들 수 있습니다.
- 프롬프트는 영어로 작성하되, 이미지 내 텍스트가 필요하면 한국어를 포함하세요.
- generate_image 도구를 호출할 때 prompt 인자에 영어로 된 상세한 이미지 설명을 넣으세요.
"""


_pending_images: list[bytes] = []


@function_tool
def generate_image(prompt: str) -> str:
    """Generate a motivational image, vision board, or celebration poster.

    Args:
        prompt: A detailed English description of the image to generate.
    """
    client = OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1,
        response_format="b64_json",
    )
    img_bytes = base64.b64decode(response.data[0].b64_json)
    _pending_images.append(img_bytes)
    return "Image generated successfully. It will be displayed in the chat."


@st.cache_resource
def get_agent() -> Agent:
    tools: list = [WebSearchTool(), generate_image]
    vs_id = os.getenv("OPENAI_VECTOR_STORE_ID")
    if vs_id:
        tools.append(FileSearchTool(vector_store_ids=[vs_id], max_num_results=5))
    return Agent(
        name="Life Coach",
        instructions=INSTRUCTIONS,
        model="gpt-4o-mini",
        tools=tools,
    )


def get_session() -> SQLiteSession:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"life-coach-{uuid.uuid4().hex[:8]}"
    return SQLiteSession(st.session_state.session_id, "life_coach.db")


async def stream_reply(
    user_input: str, text_box, status_box
) -> tuple[str, list[bytes]]:
    """Run the agent with streaming and incrementally update the UI.

    Returns (final_text, list_of_generated_images_as_bytes).
    """
    agent = get_agent()
    session = get_session()
    result = Runner.run_streamed(agent, user_input, session=session)

    _pending_images.clear()
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
                raw = getattr(item, "raw_item", None)
                raw_type = getattr(raw, "type", "") if raw is not None else ""

                if raw_type == "function_call":
                    fn_name = getattr(raw, "name", "")
                    if fn_name == "generate_image":
                        status_box.caption("🎨 이미지 생성 중...")
                elif "file_search" in raw_type:
                    queries = getattr(raw, "queries", None)
                    label = (
                        f"📂 목표 문서 검색 중: {', '.join(queries)}"
                        if queries
                        else "📂 목표 문서 검색 중..."
                    )
                    status_box.caption(label)
                else:
                    query = None
                    if raw is not None:
                        query = getattr(raw, "query", None)
                        if query is None:
                            action = getattr(raw, "action", None)
                            if action is not None:
                                query = getattr(action, "query", None)
                    label = f"🔎 웹 검색 중: {query}" if query else "🔎 웹 검색 중..."
                    status_box.caption(label)
            elif item.type == "tool_call_output_item":
                if _pending_images:
                    status_box.caption("🎨 이미지 생성 완료!")
                else:
                    status_box.caption("✅ 검색 결과 수신, 답변 정리 중...")

    images = list(_pending_images)
    _pending_images.clear()
    return text_buffer, images


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for img in msg.get("images", []):
                st.image(img)


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

        st.divider()
        st.subheader("연결된 도구")
        st.markdown("- 🔎 Web Search")
        st.markdown("- 🎨 Image Generation")
        vs_id = os.getenv("OPENAI_VECTOR_STORE_ID")
        if vs_id:
            st.markdown(f"- 📂 File Search\n\n  `{vs_id}`")
        else:
            st.warning(
                "File Search 비활성: `OPENAI_VECTOR_STORE_ID`가 .env에 없습니다. "
                "`uv run python setup_vector_store.py`로 생성하세요."
            )

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
        image_container = st.container()
        try:
            final_text, images = asyncio.run(
                stream_reply(user_input, text_box, status_box)
            )
        except Exception as e:  # noqa: BLE001
            final_text = f"⚠️ 오류가 발생했어요: {e}"
            images = []
            text_box.markdown(final_text)
        finally:
            status_box.empty()

        for img in images:
            image_container.image(img)

    st.session_state.messages.append(
        {"role": "assistant", "content": final_text, "images": images}
    )


if __name__ == "__main__":
    main()
