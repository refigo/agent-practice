import asyncio
import uuid

import streamlit as st
from dotenv import load_dotenv
from openai.types.responses import ResponseTextDeltaEvent

from agents import Agent, Runner, SQLiteSession, handoff

from tools import (
    check_availability,
    find_allergen_free_items,
    get_item_details,
    get_menu,
    make_reservation,
    place_order,
)

load_dotenv()


# ----------------------------- Agent definitions -----------------------------

MENU_INSTRUCTIONS = """\
당신은 한식 레스토랑의 메뉴 전문가입니다.
사용자가 메뉴, 재료, 가격, 알레르기, 채식 옵션에 대해 물으면 친절하게 답하세요.

사용 가능한 도구:
- get_menu: 전체 또는 카테고리별 메뉴 목록을 반환합니다. 채식 옵션도 필터링 가능.
- get_item_details: 특정 메뉴의 재료·알레르기·설명을 조회합니다.
- find_allergen_free_items: 특정 알레르기 성분이 없는 메뉴를 찾습니다.

원칙:
- 질문에 맞는 도구를 꼭 호출해 정확한 정보를 답변하세요. 추측하지 마세요.
- 사용자가 주문을 시작하려 하면 Order 에이전트로 handoff 하세요.
- 예약 관련 질문이 들어오면 Reservation 에이전트로 handoff 하세요.
- 답변은 한국어로 따뜻하게.
"""

ORDER_INSTRUCTIONS = """\
당신은 한식 레스토랑의 주문 담당자입니다.
사용자가 주문하려는 메뉴를 확인하고 place_order 도구로 주문을 확정하세요.

사용 가능한 도구:
- get_menu: 고객이 고를 수 있도록 메뉴를 안내할 때 사용.
- place_order: 주문할 메뉴 이름 리스트를 넘겨 최종 주문을 확정.

원칙:
- 주문 전에 메뉴 이름·수량을 반드시 확인하세요.
- 주문 확정 후 주문 번호와 총 금액을 명확히 안내하세요.
- 메뉴 상세 문의가 들어오면 Menu 에이전트로 handoff.
- 예약 문의가 들어오면 Reservation 에이전트로 handoff.
"""

RESERVATION_INSTRUCTIONS = """\
당신은 한식 레스토랑의 예약 담당자입니다.
사용자의 희망 날짜·시간·인원을 받아 테이블 예약을 도와주세요.

사용 가능한 도구:
- check_availability: 날짜와 인원으로 남은 시간대를 확인.
- make_reservation: 이름·날짜·시간·인원으로 예약을 확정.

원칙:
- 반드시 예약자 이름, 날짜(YYYY-MM-DD), 시간(HH:MM), 인원수를 모두 받은 뒤 확정하세요.
- 먼저 check_availability로 가능 여부를 확인하고 make_reservation으로 확정하세요.
- 메뉴 상세 문의가 들어오면 Menu 에이전트로 handoff.
- 주문 문의가 들어오면 Order 에이전트로 handoff.
"""

TRIAGE_INSTRUCTIONS = """\
당신은 한식 레스토랑의 응대 총괄입니다.
고객의 요청을 분석해 가장 적절한 전문 에이전트로 연결합니다.

라우팅 규칙:
- 메뉴·재료·알레르기·채식 옵션 질문 → Menu 에이전트로 handoff
- 주문·장바구니·결제 관련 → Order 에이전트로 handoff
- 테이블 예약·시간 확인·예약 변경 → Reservation 에이전트로 handoff

원칙:
- 요청이 애매하면 한 번만 짧게 확인 질문을 한 뒤 handoff 하세요.
- 인사말/간단한 응대는 직접 처리해도 됩니다.
- 한국어로 따뜻하게.
"""


@st.cache_resource
def build_agents() -> Agent:
    menu_agent = Agent(
        name="MenuAgent",
        handoff_description="메뉴, 재료, 알레르기, 채식 옵션 전문가",
        instructions=MENU_INSTRUCTIONS,
        model="gpt-4o-mini",
        tools=[get_menu, get_item_details, find_allergen_free_items],
    )
    order_agent = Agent(
        name="OrderAgent",
        handoff_description="주문 접수 및 확정 담당",
        instructions=ORDER_INSTRUCTIONS,
        model="gpt-4o-mini",
        tools=[get_menu, place_order],
    )
    reservation_agent = Agent(
        name="ReservationAgent",
        handoff_description="테이블 예약 담당",
        instructions=RESERVATION_INSTRUCTIONS,
        model="gpt-4o-mini",
        tools=[check_availability, make_reservation],
    )

    # 전문 에이전트끼리도 서로 handoff 할 수 있도록 연결 (예: 예약 중 메뉴 문의).
    menu_agent.handoffs = [handoff(order_agent), handoff(reservation_agent)]
    order_agent.handoffs = [handoff(menu_agent), handoff(reservation_agent)]
    reservation_agent.handoffs = [handoff(menu_agent), handoff(order_agent)]

    triage_agent = Agent(
        name="TriageAgent",
        handoff_description="고객 요청 분석 및 라우팅",
        instructions=TRIAGE_INSTRUCTIONS,
        model="gpt-4o-mini",
        handoffs=[
            handoff(menu_agent),
            handoff(order_agent),
            handoff(reservation_agent),
        ],
    )
    return triage_agent


AGENT_ICONS = {
    "TriageAgent": "🧭 Triage",
    "MenuAgent": "🍽️ Menu",
    "OrderAgent": "🧾 Order",
    "ReservationAgent": "📅 Reservation",
}


def agent_label(name: str) -> str:
    return AGENT_ICONS.get(name, f"🤖 {name}")


# ----------------------------- Session state -----------------------------


def get_session() -> SQLiteSession:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"restaurant-{uuid.uuid4().hex[:8]}"
    return SQLiteSession(st.session_state.session_id, "restaurant_bot.db")


# ----------------------------- Streaming -----------------------------


async def stream_reply(
    user_input: str,
    text_box,
    steps_box,
) -> tuple[str, list[dict], str]:
    """Run the agent; stream text + collect handoff/tool events.

    Returns (final_text, steps, final_agent_name). Steps are persistent markers
    (handoff transitions, tool calls) that will be rendered inline in the chat.
    """
    triage = build_agents()
    session = get_session()

    # Every turn enters from Triage. SQLiteSession preserves prior conversation,
    # so the triage agent sees context and can route appropriately (or handle
    # follow-ups itself if the last specialist's answer was complete).
    result = Runner.run_streamed(triage, user_input, session=session)
    starting_agent = triage

    text_buffer = ""
    steps: list[dict] = []
    last_agent_name = starting_agent.name

    def render_steps() -> None:
        if not steps:
            return
        lines = []
        for step in steps:
            if step["kind"] == "handoff":
                lines.append(
                    f"> ➡️ **{agent_label(step['from'])}** → **{agent_label(step['to'])}** 연결 중..."
                )
            elif step["kind"] == "tool":
                lines.append(f"> 🔧 `{step['name']}` 도구 호출 중...")
            elif step["kind"] == "tool_done":
                lines.append(f"> ✅ `{step['name']}` 완료")
        steps_box.markdown("\n\n".join(lines))

    async for event in result.stream_events():
        # Agent switched (triage → specialist, or specialist → specialist).
        if event.type == "agent_updated_stream_event":
            new_agent = event.new_agent.name
            if new_agent != last_agent_name:
                steps.append(
                    {"kind": "handoff", "from": last_agent_name, "to": new_agent}
                )
                last_agent_name = new_agent
                render_steps()
            continue

        # Token-level streaming from the active agent.
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            text_buffer += event.data.delta
            text_box.markdown(text_buffer)
            continue

        # Tool calls and outputs.
        if event.type == "run_item_stream_event":
            item = event.item
            if item.type == "tool_call_item":
                raw = getattr(item, "raw_item", None)
                raw_type = getattr(raw, "type", "") if raw is not None else ""
                if raw_type == "function_call":
                    fn_name = getattr(raw, "name", "unknown")
                    # Hide handoff "tool" calls — those are surfaced via
                    # agent_updated_stream_event instead, to avoid noise.
                    if not fn_name.startswith("transfer_to_"):
                        steps.append({"kind": "tool", "name": fn_name})
                        render_steps()
            elif item.type == "tool_call_output_item":
                # Mark the most recent tool step as done (if any).
                for step in reversed(steps):
                    if step["kind"] == "tool" and not step.get("done"):
                        step["done"] = True
                        step["kind"] = "tool_done"
                        break
                render_steps()

    return text_buffer, steps, last_agent_name


# ----------------------------- Rendering -----------------------------


def render_steps_markdown(steps: list[dict]) -> str:
    lines = []
    for step in steps:
        if step["kind"] == "handoff":
            lines.append(
                f"> ➡️ **{agent_label(step['from'])}** → **{agent_label(step['to'])}** 연결 중..."
            )
        elif step["kind"] == "tool":
            lines.append(f"> 🔧 `{step['name']}` 도구 호출 중...")
        elif step["kind"] == "tool_done":
            lines.append(f"> ✅ `{step['name']}` 완료")
    return "\n\n".join(lines)


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                if msg.get("steps"):
                    st.markdown(render_steps_markdown(msg["steps"]))
                if msg.get("agent"):
                    st.caption(f"응답: {agent_label(msg['agent'])}")
            st.markdown(msg["content"])


# ----------------------------- Main -----------------------------


def main() -> None:
    st.set_page_config(page_title="Restaurant Bot", page_icon="🍚")
    st.title("🍚 한식당 응대 봇")
    st.caption(
        "메뉴 문의 · 주문 · 테이블 예약을 도와드려요. "
        "Triage 에이전트가 요청을 분석해 전문 에이전트에게 연결합니다."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_agent_name" not in st.session_state:
        st.session_state.current_agent_name = "TriageAgent"

    with st.sidebar:
        st.subheader("세션")
        st.code(st.session_state.get("session_id", "(아직 시작 전)"), language="text")
        st.markdown(f"**현재 응대 중**: {agent_label(st.session_state.current_agent_name)}")
        if st.button("새 대화 시작", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pop("session_id", None)
            st.session_state.current_agent_name = "TriageAgent"
            st.rerun()

        st.divider()
        st.subheader("에이전트 구성")
        for name in AGENT_ICONS:
            st.markdown(f"- {agent_label(name)}")

        st.divider()
        st.subheader("예시 질문")
        st.markdown(
            "- 채식 메뉴 뭐 있어?\n"
            "- 비빔밥 재료 알려줘\n"
            "- 비빔밥이랑 식혜 주문할게\n"
            "- 금요일 저녁 2명 예약 가능해?"
        )

    render_history()

    user_input = st.chat_input("무엇을 도와드릴까요?")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        steps_box = st.empty()
        text_box = st.empty()
        try:
            final_text, steps, final_agent = asyncio.run(
                stream_reply(user_input, text_box, steps_box)
            )
        except Exception as e:  # noqa: BLE001
            final_text = f"⚠️ 오류가 발생했어요: {e}"
            steps = []
            final_agent = st.session_state.current_agent_name
            text_box.markdown(final_text)

        if steps:
            st.caption(f"응답: {agent_label(final_agent)}")

    st.session_state.current_agent_name = final_agent
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": final_text,
            "steps": steps,
            "agent": final_agent,
        }
    )


if __name__ == "__main__":
    main()
