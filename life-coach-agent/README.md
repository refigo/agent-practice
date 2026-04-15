# Life Coach Agent

Nomad Coder AI Agent Challenge - Day 9 + Day 10.

Streamlit 채팅 UI로 동작하는 라이프 코치 에이전트입니다.
OpenAI Agents SDK의 `Agent` + `Runner`로 구현했고, **두 가지 검색 도구**를 함께 사용합니다.

- 🔎 **WebSearchTool** — 동기부여·습관 형성 등 최신 정보 웹 검색 (Day 9)
- 📂 **FileSearchTool** — 사용자의 개인 목표/일지 문서를 벡터스토어에서 검색 (Day 10)

대화는 `SQLiteSession`으로 기억하며, 토큰 단위로 스트리밍 응답합니다.

## Features

- 💬 Streamlit `st.chat_input` / `st.chat_message` 기반 채팅 UI
- 🔎 Agents SDK 내장 `WebSearchTool`로 웹 검색
- 📂 Agents SDK 내장 `FileSearchTool`로 개인 목표 문서 검색 (OpenAI Vector Store)
- 🧠 `SQLiteSession`으로 대화 메모리 유지 (`life_coach.db`)
- ⚡ `Runner.run_streamed()` + `ResponseTextDeltaEvent`로 토큰 단위 스트리밍
- 🪧 도구 호출 시 (웹/파일) 진행 상황을 UI에 구분해서 표시

## Setup

```bash
# .env 에 OPENAI_API_KEY 설정 (이미 있다면 생략)
echo "OPENAI_API_KEY=sk-..." > .env

uv sync
```

### Day 10 — 벡터스토어 일회성 셋업

개인 목표 문서(`goals.txt`)를 OpenAI 벡터스토어로 인덱싱합니다.
한 번만 실행하면 되고, 끝나면 출력된 `OPENAI_VECTOR_STORE_ID`를 `.env`에 추가하세요.

```bash
uv run python setup_vector_store.py
```

출력 예시:

```
[1/3] Uploading goals.txt to OpenAI Files...
      file_id = file-abc123
[2/3] Creating vector store 'life-coach-goals'...
      vector_store_id = vs_xyz789
[3/3] Attaching file and waiting for indexing...
      indexed ✅

Done! Add this line to life-coach-agent/.env:

    OPENAI_VECTOR_STORE_ID=vs_xyz789
```

`goals.txt`를 수정했다면 스크립트를 다시 실행해서 **새로운** 벡터스토어를 만들고,
`.env`의 ID도 새 값으로 교체하세요.

## Run

```bash
uv run streamlit run app.py
```

브라우저가 자동으로 열리지 않으면 터미널에 표시된 URL(`http://localhost:8501`)
로 접속하세요. 사이드바의 "새 대화 시작" 버튼으로 세션을 초기화할 수 있습니다.

## 예시 대화

```
User: 내 운동 목표 달성은 잘 되어가고 있어?
Coach: 📂 목표 문서 검색 중: 운동 목표, 근력 운동 루틴
Coach: 🔎 웹 검색 중: 장거리 러닝 15km 훈련법
Coach: 기록을 보니 이번 주 월·수 근력 운동과 화·목 장거리 15km까지는 잘 지키고 계세요.
       하프 마라톤을 위해 거리 확장을 노리신다면, 주 1회만 17km로 늘려보시는 걸 추천...
```

---

# 📚 Study: Vector Store & File Search

Day 10에 등장하는 **파일 검색 (File Search)** 기능을 이해하기 위한 핵심 개념을 정리합니다.

## 1. 왜 Vector Store가 필요한가

에이전트에게 "내 목표가 뭐였지?"라고 물으면 모델은 내 문서를 **본 적이 없기 때문에** 답할 수 없습니다.
문서를 매번 프롬프트에 통째로 넣을 수도 있지만, 그러면 다음 문제가 생깁니다.

- 문서가 길어질수록 비용·지연 시간이 계속 증가
- 컨텍스트 윈도우 한계에 도달하면 아예 불가능
- 모델이 긴 문서에서 관련 부분만 골라내는 데 실패하기 쉬움

해결책은 **검색 → 관련 조각만 주입**하는 RAG (Retrieval-Augmented Generation) 패턴입니다.
이때 "관련 조각을 빠르게 찾는 저장소" 역할을 하는 것이 **벡터스토어**입니다.

## 2. 벡터스토어가 동작하는 방식

```
 원본 문서 (goals.txt)
        │
        ▼
 ┌─────────────────┐
 │  Chunking       │   문서를 수백 토큰 단위 조각으로 자름
 └─────────────────┘
        │
        ▼
 ┌─────────────────┐
 │  Embedding      │   각 조각을 고차원 벡터(숫자 배열)로 변환
 └─────────────────┘   예: 1536차원 float
        │
        ▼
 ┌─────────────────┐
 │  Vector Store   │   벡터 + 원문 조각을 함께 저장,
 └─────────────────┘   유사도(cosine 등)로 빠른 검색을 지원
```

질의 시점에는:

```
 사용자 질문 → 같은 모델로 임베딩 → 벡터스토어에서 코사인 유사도 top-k 조각 반환
 → 모델에 원문 조각을 주입 → 답변 생성
```

즉 **임베딩(의미 벡터)** + **근사 최근접 이웃 검색(ANN)** 의 조합입니다.

## 3. OpenAI Vector Store 객체 모델

OpenAI의 Files/Vector Stores/Assistants API는 다음 3개 리소스로 구성됩니다.

| 리소스 | ID prefix | 역할 |
|---|---|---|
| **File** | `file-...` | 업로드한 원본 파일. 여러 벡터스토어에 재사용 가능 |
| **Vector Store** | `vs_...` | 여러 파일을 인덱싱한 검색 컬렉션. 이름, 만료 정책 등 메타 보유 |
| **Vector Store File** | (join) | 특정 File이 특정 Vector Store에 attach된 상태 |

본 프로젝트의 `setup_vector_store.py`가 하는 일:

```python
# 1) 원본 파일 업로드
file = client.files.create(file=open("goals.txt", "rb"), purpose="assistants")
#   → file-abc123

# 2) 빈 벡터스토어 생성
vs = client.vector_stores.create(name="life-coach-goals")
#   → vs_xyz789

# 3) 파일을 벡터스토어에 attach & 인덱싱 완료까지 poll
client.vector_stores.files.create_and_poll(
    vector_store_id=vs.id,
    file_id=file.id,
)
#   내부적으로 chunking + embedding이 수행됨
```

## 4. Vector Store ID란?

- `vs_xyz789` 형태의 **불투명 문자열(opaque ID)** 입니다.
- 해당 OpenAI 계정의 벡터스토어 리소스를 가리키는 포인터로, 내용/구조는 외부에 노출되지 않습니다.
- 런타임에 `FileSearchTool`에 넘기면, 에이전트가 이 벡터스토어에 한정해서만 검색합니다.

```python
from agents import FileSearchTool

FileSearchTool(
    vector_store_ids=["vs_xyz789"],  # ← 여기에 발급받은 ID
    max_num_results=5,
)
```

> 📌 **왜 코드에 하드코딩하지 않고 `.env`에?**
> - ID는 환경(개발/스테이징/프로덕션)마다 다를 수 있음
> - Git에 커밋되면 타인이 읽기 요청을 보낼 수 있음 (계정 리소스 노출)
> - `goals.txt`를 갱신해 새 벡터스토어를 만들 때 ID만 교체하면 되어 편함

## 5. OpenAI 벡터스토어 vs 직접 구축

| 항목 | OpenAI Managed | 직접 (e.g. pgvector, Qdrant) |
|---|---|---|
| 임베딩 모델 선택 | 고정 (`text-embedding-3-large`) | 자유 |
| Chunking 전략 | 자동 | 직접 튜닝 |
| 인프라 운영 | 없음 | 호스팅·백업 필요 |
| 비용 모델 | 저장 용량 + 쿼리 | 인프라 비용 |
| Agents SDK 연동 | `FileSearchTool` 한 줄 | 커스텀 `@function_tool` 작성 |

학습·소규모 프로토타이핑에는 OpenAI managed가 압도적으로 편하고,
특수 임베딩 모델이나 대규모 인덱스를 원한다면 직접 구축 쪽이 유연합니다.

## 6. Agents SDK에서의 `FileSearchTool`

```python
from agents import Agent, FileSearchTool, WebSearchTool

agent = Agent(
    name="Life Coach",
    instructions="...",
    tools=[
        WebSearchTool(),
        FileSearchTool(vector_store_ids=["vs_xyz789"], max_num_results=5),
    ],
)
```

이렇게 두 도구를 함께 등록하면 모델이 질문 의도에 따라 선택적으로 호출합니다.

- "내 목표가 뭐였지?" → `file_search` 선택
- "습관 만들기 팁 알려줘" → `web_search` 선택
- "내 운동 목표에 맞는 보강 운동?" → `file_search` → `web_search` 순차 호출

도구 선택 로직은 모델이 결정하지만, `instructions`에서 **언제 어떤 도구를 쓸지 가이드**를
명시하면 품질이 크게 올라갑니다. 본 프로젝트 `app.py`의 `INSTRUCTIONS` 블록 참고.

## 7. Stream 이벤트에서 도구 호출 구분하기

`Runner.run_streamed()`는 `run_item_stream_event`로 도구 호출을 알려줍니다.
`raw_item.type`으로 어느 도구가 호출되었는지 구분할 수 있습니다.

| `raw_item.type` | 의미 | 쿼리 위치 |
|---|---|---|
| `web_search_call` | 웹 검색 호출 | `raw.action.query` 등 |
| `file_search_call` | 파일 검색 호출 | `raw.queries` (리스트) |

본 프로젝트는 이 타입을 보고 UI에 `🔎 웹 검색 중` / `📂 목표 문서 검색 중` 으로 구분해 표시합니다
(`app.py::stream_reply`).

## 8. 더 읽어볼 자료

- [OpenAI Vector Stores API](https://platform.openai.com/docs/api-reference/vector-stores)
- [OpenAI File Search guide](https://platform.openai.com/docs/assistants/tools/file-search)
- [Agents SDK — FileSearchTool](https://openai.github.io/openai-agents-python/tools/)
- [Anthropic: Retrieval-Augmented Generation](https://www.anthropic.com/research) (RAG 개론)
