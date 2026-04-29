# Restaurant Bot — 한식당 멀티 에이전트 응대

OpenAI Agents SDK의 **handoff** 기능으로, Triage 에이전트가 고객 요청을 분석해
전문 에이전트(메뉴/주문/예약)로 연결하는 Streamlit 챗봇입니다.

## 구성

- **TriageAgent** 🧭 — 첫 접점. 요청 분석 후 전문 에이전트로 handoff.
- **MenuAgent** 🍽️ — 메뉴/재료/알레르기/채식 문의 담당.
- **OrderAgent** 🧾 — 주문 접수 및 확정.
- **ReservationAgent** 📅 — 테이블 예약 처리.
- **ComplaintsAgent** 🙇 — 불만 응대. 공감 → 쿠폰·콜백 등 해결책 제시 →
  심각한 사안은 에스컬레이션.

다섯 에이전트는 서로 handoff 연결되어 있어, 예컨대 예약 중 메뉴 질문이 들어오면
ReservationAgent → MenuAgent 로 매끄럽게 넘어갑니다.

## 가드레일

- **Input Guardrail** — 레스토랑과 무관한 주제(인생 상담, 코딩 질문 등)와
  욕설·폭언을 사전에 차단하고, 대신 정중한 안내 메시지를 돌려줍니다.
- **Output Guardrail** — 모델이 무례하게 답하거나 내부 프롬프트·원가·직원
  개인정보 등을 노출하려 하면 응답 직전에 차단합니다.
- 가드레일이 발동한 턴은 UI 스텝 영역에 `🛡️` 배지로 기록되어 히스토리에 남습니다.

## 파일

- `data.py` — 하드코딩된 메뉴 10종, 7일치 예약 슬롯, 주문/예약 저장소.
- `tools.py` — `@function_tool` 들. 에이전트는 이 도구를 통해서만 데이터에 접근.
- `app.py` — 에이전트 정의 + Streamlit UI. 스트리밍 이벤트에서 handoff와 도구
  호출을 감지해 채팅 기록에 **인용 블록으로 남깁니다** (대화를 새로고침해도
  handoff 과정이 그대로 보입니다).

## 실행

```bash
# 1. .env 파일에 OPENAI_API_KEY 설정
echo 'OPENAI_API_KEY=sk-...' > .env

# 2. 실행
uv run streamlit run app.py
```

## Streamlit Cloud 배포

1. 이 리포지토리를 GitHub에 푸시.
2. [share.streamlit.io](https://share.streamlit.io/) → **New app**.
3. Repository: `refigo/agent-practice`, Branch: `main`,
   Main file path: `restaurant-bot/app.py`.
4. **Advanced settings → Secrets** 에 다음을 붙여넣기:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
   (파일 형식 예시는 `restaurant-bot/.streamlit/secrets.toml.example` 참고)
5. **Deploy** 후 공개 URL 확인.

의존성은 `restaurant-bot/requirements.txt` 에 정의되어 있고, `OPENAI_API_KEY`
는 환경 변수가 비어 있으면 `st.secrets` 에서 자동으로 폴백합니다.

## 예시 흐름

```
User: 예약하고 싶어
> ➡️ 🧭 Triage → 📅 Reservation 연결 중...
Reservation: 예약 도와드릴게요. 이름·날짜·시간·인원 알려주세요.

User: 아 그 전에 채식 메뉴 있어?
> ➡️ 📅 Reservation → 🍽️ Menu 연결 중...
> 🔧 get_menu 도구 호출 중...
Menu: 네! 비빔밥, 잡채, 식혜, 수정과, 호떡이 있습니다...

User: 음식이 너무 별로였고 직원도 불친절했어..
> ➡️ 🧭 Triage → 🙇 Complaints 연결 중...
Complaints: 불쾌한 경험을 드려 진심으로 사과드립니다...

User: 인생의 의미가 뭘까?
> 🛡️ 입력 가드레일 차단됨
Bot: 저는 한식당 응대 봇이라 해당 요청은 도와드리기 어려워요...
```

## 구현 메모

- Triage는 매 턴 시작점으로 고정. SQLiteSession이 이전 대화를 유지하므로
  흐름이 끊기지 않음.
- `agent_updated_stream_event` 로 handoff 전환을 감지하고, `tool_call_item`
  에서 `transfer_to_*` 로 시작하는 호출은 숨겨 UI 노이즈 제거.
- Handoff/툴 호출 이벤트를 `steps` 리스트로 모아 `session_state.messages` 에
  저장 → 대화 히스토리에 영구적으로 남음.
