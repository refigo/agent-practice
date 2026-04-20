# Life Coach Agent

Streamlit 채팅 UI로 동작하는 라이프 코치 에이전트입니다.
OpenAI Agents SDK의 `Agent` + `Runner`로 구현했고, **세 가지 도구**를 함께 사용합니다.

- 🔎 **WebSearchTool** — 동기부여·습관 형성 등 최신 정보 웹 검색
- 📂 **FileSearchTool** — 사용자의 개인 목표/일지 문서를 벡터스토어에서 검색
- 🎨 **generate_image** (`@function_tool` + DALL-E 3) — 비전 보드, 동기부여 포스터, 축하 이미지 생성

대화는 `SQLiteSession`으로 기억하며, 토큰 단위로 스트리밍 응답합니다.

## Features

- 💬 Streamlit `st.chat_input` / `st.chat_message` 기반 채팅 UI
- 🔎 Agents SDK 내장 `WebSearchTool`로 웹 검색
- 📂 Agents SDK 내장 `FileSearchTool`로 개인 목표 문서 검색 (OpenAI Vector Store)
- 🎨 `@function_tool` + DALL-E 3 API로 비전 보드/동기부여 이미지 생성
- 🧠 `SQLiteSession`으로 대화 메모리 유지 (`life_coach.db`)
- ⚡ `Runner.run_streamed()` + `ResponseTextDeltaEvent`로 토큰 단위 스트리밍
- 🪧 도구 호출 시 (웹/파일/이미지) 진행 상황을 UI에 구분해서 표시

## Setup

```bash
# .env 에 OPENAI_API_KEY 설정 (이미 있다면 생략)
echo "OPENAI_API_KEY=sk-..." > .env

uv sync
```

### 벡터스토어 일회성 셋업

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

User: 2026년 목표로 비전 보드를 만들어줘!
Coach: 📂 목표 문서 검색 중: 2026년 목표
Coach: 🎨 이미지 생성 중...
Coach: [비전 보드 이미지 표시]
Coach: 목표를 담은 비전 보드를 만들었어요! 마라톤, 근력 운동, AI 에이전트 전문성...
```

---

# 📚 Study: Vector Store & File Search

**파일 검색 (File Search)** 기능을 이해하기 위한 핵심 개념을 정리합니다.

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

---

# 🎨 Study: Image Generation

**이미지 생성 (Image Generation)** 기능을 이해하기 위한 핵심 개념을 정리합니다.

## 1. 두 가지 접근법: 내장 도구 vs 커스텀 도구

Agents SDK에서 이미지 생성을 구현하는 방법은 두 가지입니다.

### A. 내장 `ImageGenerationTool` (Responses API 통합)

```python
from agents import ImageGenerationTool
from agents.tool import ImageGeneration

ImageGenerationTool(
    tool_config=ImageGeneration(
        type="image_generation",
        model="gpt-image-1",
        quality="medium",
        size="1024x1024",
    )
)
```

- Responses API에 `image_generation` 도구로 직접 등록됨
- 모델이 도구를 호출하면 서버 측에서 이미지 생성 → base64로 반환
- **제약**: 조직 인증(Organization Verification) 필요 — 미인증 시 403 오류

### B. 커스텀 `@function_tool` + Images API (본 프로젝트 채택)

```python
from agents import function_tool
from openai import OpenAI

@function_tool
def generate_image(prompt: str) -> str:
    client = OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1,
        response_format="b64_json",
    )
    img_bytes = base64.b64decode(response.data[0].b64_json)
    _pending_images.append(img_bytes)  # UI 표시용 사이드채널
    return "Image generated successfully."
```

- Images API(`client.images.generate`)를 직접 호출하는 일반 function tool
- 조직 인증 없이도 사용 가능
- 이미지 바이트를 모듈 변수에 저장하고 짧은 확인 메시지만 반환 → 대화 기록 비대화 방지

## 2. 왜 커스텀 도구를 선택했나

| 항목 | 내장 `ImageGenerationTool` | 커스텀 `@function_tool` |
|---|---|---|
| 조직 인증 | 필요 (403 차단됨) | 불필요 |
| 모델 | `gpt-image-1` | `dall-e-3` (또는 원하는 모델) |
| 반환 방식 | base64가 대화 기록에 포함 | 확인 메시지만 포함 (컨텍스트 절약) |
| 스트림 이벤트 | `image_generation_call` | `function_call` |
| 설정 유연성 | `ImageGeneration` TypedDict 고정 | 자유롭게 커스텀 가능 |

핵심 이유 두 가지:
1. **조직 인증 전파 전에도 바로 사용 가능**
2. **base64(~1.7MB)가 대화 기록에 쌓이지 않아** `gpt-4o-mini` 컨텍스트 초과 방지

## 3. 대화 기록 비대화 문제와 해결

내장 도구를 쓰면 이미지 base64(~1.7MB)가 대화 기록에 그대로 포함됩니다.

```
턴 1: 이미지 생성 → base64 1.7MB가 기록에 저장
턴 2: 이전 기록(1.7MB) + 새 입력 → 컨텍스트 윈도우 초과!
```

커스텀 도구에서는 이미지를 **모듈 변수(`_pending_images`)**에 사이드채널로 저장하고,
도구 반환값은 짧은 문자열만 남깁니다. UI 표시는 스트림 종료 후 별도로 처리합니다.

```python
# 도구: 이미지를 사이드채널에 저장, 짧은 메시지만 반환
_pending_images.append(img_bytes)
return "Image generated successfully."

# UI: 스트림 완료 후 사이드채널에서 이미지를 꺼내 표시
images = list(_pending_images)
for img in images:
    image_container.image(img)
```

## 4. `@function_tool` 이름과 INSTRUCTIONS 일치의 중요성

`@function_tool`로 만든 도구의 이름은 **함수 이름 그대로** 등록됩니다.

```python
@function_tool
def generate_image(prompt: str) -> str:  # → 도구 이름: "generate_image"
```

INSTRUCTIONS에서 이 도구를 안내할 때 **정확히 같은 이름**을 사용해야 합니다.

```
❌ "image_generation 도구를 사용하세요"  → 모델이 도구를 못 찾고 텍스트로만 응답
✅ "generate_image 도구를 사용하세요"   → 모델이 정확히 도구를 호출
```

이름이 다르면 모델이 도구를 호출하지 않고 "이미지를 생성했습니다"라고
텍스트만 출력하는 환각(hallucination)이 발생합니다.

## 5. 스트림 이벤트에서 도구 호출 구분하기

커스텀 function tool은 내장 도구와 다른 이벤트 타입을 사용합니다.

| `raw_item.type` | 도구 종류 | 쿼리/결과 위치 |
|---|---|---|
| `web_search_call` | 내장 WebSearchTool | `raw.action.query` |
| `file_search_call` | 내장 FileSearchTool | `raw.queries` (리스트) |
| `function_call` | 커스텀 @function_tool | `raw.name` (함수 이름) |

```python
if raw_type == "function_call":
    fn_name = getattr(raw, "name", "")
    if fn_name == "generate_image":
        status_box.caption("🎨 이미지 생성 중...")
```

## 6. 세 도구의 협력 패턴

```
User: "2026년 목표로 비전 보드를 만들어줘"
    │
    ▼
① file_search → 사용자의 목표 문서에서 2026년 계획 검색
    │
    ▼
② generate_image → 검색된 목표를 반영한 비전 보드 이미지 생성
    │
    ▼
③ 텍스트 응답 → 이미지와 함께 격려 메시지 전달
```

세 도구가 자연스럽게 협력하려면 **INSTRUCTIONS에 각 도구의 용도와 조합 가이드**를
명시하는 것이 핵심입니다. 예를 들어:

> "이미지 생성 전에 file_search로 사용자의 목표를 먼저 확인하면
> 더 개인화된 이미지를 만들 수 있습니다."

이렇게 안내하면 모델이 file_search → generate_image 순서로 호출하는 패턴을 학습합니다.

## 7. Streamlit에서 이미지 표시 & 히스토리 유지

생성된 이미지를 채팅 히스토리에 유지하려면 `st.session_state.messages`에
이미지 바이트를 함께 저장해야 합니다.

```python
# 저장
st.session_state.messages.append({
    "role": "assistant",
    "content": final_text,
    "images": [img_bytes_1, img_bytes_2, ...],
})

# 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for img in msg.get("images", []):
            st.image(img)
```

주의: `st.empty()`는 하나의 요소만 보유 가능하므로, 이미지 표시에는
`st.container()`를 사용해야 여러 이미지도 안전하게 표시됩니다.

## 8. 비용 고려사항

| 모델 | 해상도 | 대략적 비용 |
|---|---|---|
| `dall-e-3` | 1024×1024 | ~$0.04/장 |
| `dall-e-3` | 1024×1792 | ~$0.08/장 |
| `gpt-image-1` | 1024×1024 (medium) | ~$0.04/장 |

프로토타이핑 시 `dall-e-3` 1024×1024로 충분하며,
프로덕션에서는 사용량 제한(rate limit)과 비용 모니터링이 필요합니다.
