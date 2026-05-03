# Story Book Maker

Google ADK Workflow Agents로 만드는 5페이지 어린이 동화책 파이프라인.

```
SequentialAgent (root)
  ├─ story_writer            # LlmAgent + output_schema=StoryBook → state["story"]
  ├─ parallel_illustrator    # ParallelAgent
  │    ├─ page_1_illustrator # LlmAgent + tool: generate_page_1_image
  │    ├─ page_2_illustrator
  │    ├─ page_3_illustrator
  │    ├─ page_4_illustrator
  │    └─ page_5_illustrator
  └─ finalizer               # Custom BaseAgent: assembles 텍스트+이미지 동화책 view
```

- **SequentialAgent** — Writer → Parallel Illustrator → Finalizer 흐름 관리
- **ParallelAgent** — 5개 페이지 일러스트를 동시에 생성
- **Callbacks** — `before_agent_callback` / `after_agent_callback`으로 진행 상황 출력 (`스토리 작성 중...`, `이미지 N/5 생성 중...` 등). 실행 중인 터미널에서 확인.
- **Finalizer** — 채팅창에 페이지별 (Text + Visual + Image 참조) 마크다운 묶음을 한 번에 출력. 이미지 본체는 Artifacts 탭.

## 모델

- 텍스트: Gemini `gemini-2.5-flash`
- 이미지: Gemini `gemini-2.5-flash-image-preview` (네이티브 이미지 생성)

## 실행

```bash
cp story_book_maker/.env.example story_book_maker/.env
# .env에 GOOGLE_API_KEY 채우기 (https://aistudio.google.com/apikey)

uv sync
uv run adk web        # 브라우저에서 story_book_maker 선택
```

`adk web`이 켜지면 좌측에서 `story_book_maker`를 골라 테마(예: "별을 모으는 작은 토끼")를 입력. 파이프라인이 끝나면:

- 본문은 채팅에, 페이지별 일러스트는 Artifacts 탭에서 확인할 수 있다.
