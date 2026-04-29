# Story Book Maker

Google ADK 두 에이전트로 만드는 5페이지 어린이 동화책 파이프라인.

- **story_writer** — 테마를 받아 5페이지 동화를 `StoryBook` 스키마에 맞춰 작성, `state["story"]`에 저장
- **illustrator** — `state["story"]`를 읽어 페이지별로 이미지 생성, `page_<n>.png` Artifact로 저장
- **root_agent** — 위 둘을 순서대로 실행하는 `SequentialAgent`

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
