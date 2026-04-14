# Life Coach Agent

Nomad Coder AI Agent Challenge - Day 9.

Streamlit chat UI에서 동작하는 라이프 코치 에이전트입니다. OpenAI Agents SDK의
`Agent` + `Runner`로 구현했고, 내장 `WebSearchTool`로 동기부여·자기개발·습관
형성과 관련된 최신 정보를 검색해 답합니다. 대화는 `SQLiteSession`으로 기억합니다.

## Features

- 💬 Streamlit `st.chat_input` / `st.chat_message` 기반 채팅 UI
- 🔎 OpenAI Agents SDK 내장 `WebSearchTool`로 웹 검색
- 🧠 `SQLiteSession`으로 대화 메모리 유지 (`life_coach.db`)
- ⚡ `Runner.run_streamed()` + `ResponseTextDeltaEvent`로 토큰 단위 스트리밍
- 🪧 검색 도구 호출 시 진행 상황을 UI에 표시

## Setup

```bash
# .env 에 OPENAI_API_KEY 설정 (이미 있다면 생략)
echo "OPENAI_API_KEY=sk-..." > .env

uv sync
```

## Run

```bash
uv run streamlit run app.py
```

브라우저가 자동으로 열리지 않으면 터미널에 표시된 URL(`http://localhost:8501`)
로 접속하세요. 사이드바의 "새 대화 시작" 버튼으로 세션을 초기화할 수 있습니다.

## 예시 대화

```
User: 아침에 일찍 일어나고 싶은데 자꾸 알람을 끄게 돼
Coach: 🔎 웹 검색 중: 아침 일찍 일어나는 팁
Coach: 좋은 목표예요! 효과가 검증된 방법을 정리해 드릴게요...
```
