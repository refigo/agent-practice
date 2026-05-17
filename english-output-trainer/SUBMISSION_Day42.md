# [DRAFT] Side-project board submission — Day 42

> Fill in the **TBD** placeholders after Streamlit Cloud deploy + screenshots, then paste to
> https://nomadcoders.co/community/side-projects

---

## 제목 (제안)

**Language Feedback Echo Loop — 어제 틀린 영어를, 오늘 밤 입으로 다시 말해보는 에이전트**

(대안)
- "내가 만든 영어 실수를, 그날 저녁의 스피킹 드릴로 — Language Feedback Echo Loop"
- "Echo Loop: AI Agent that turns your day's English mistakes into tonight's speaking reps"

## 최종 배포 URL

> **TBD** — share.streamlit.io 배포 후 URL 입력

## 깃허브 링크

> https://github.com/refigo/agent-practice/tree/main/english-output-trainer
> (해당 커밋 링크는 Day 42 제출 시점 main HEAD)

## 프로젝트 설명

영어 학습의 **인풋(피드백)**과 **아웃풋(말하기 연습)** 사이의 끊어진 고리를 닫는 LangGraph 에이전트입니다.

평소 Claude Code로 영어 메시지를 작성하다 보면 companion 스킬 `english-feedback`이 모든 교정/번역 이력을 `feedbacks/YYYY-MM-DD.md`로 자동 기록합니다. 하지만 그 실수들은 기록만 될 뿐, **다시 입으로 꺼내는 연습으로 이어지지 않습니다.**

이 에이전트는 하루치 피드백 로그를 받아, **개인화된 영어 출력 드릴 덱**을 만들어줍니다. 한국어 큐 없이, **영어로 보고 영어로 말하는** 몰입형 학습을 강제하는 페다고지가 핵심입니다.

### 어떻게 작동하나요? (고급 패턴: Orchestrator-Workers)

```
START → collect_feedback ─[has_content?]─→ select_entries (orchestrator)
                          │                       │
                          │                       ▼  Send fan-out (병렬)
                          │            generate_one_card × N  ← 각 실수마다 1워커
                          │                       │
                          │                       ▼  reducer 로 카드 누적
                          │            enrich_with_glossary → format_and_emit → END
                          └────── (empty) ──→ emit_empty_deck → END
```

LangGraph의 `Send` API로 **각 실수 항목당 하나의 워커**가 병렬 LLM 호출을 수행, `operator.add` reducer로 결과를 모읍니다. 단일 배치 프롬프트보다 한 카드당 집중도가 높고, 늦은 워커가 전체를 막지 않습니다.

## 핵심 기능 설명

### 1. **하루치 피드백 → 개인화 드릴 덱 자동 생성**
- 입력: 마크다운 피드백 로그 (붙여넣기 / 파일 업로드 / 로컬 디렉토리)
- 출력: `target_en` / `original_mistake` / `mistake_note_en` / `pattern_tag` / `paraphrases_en` 5필드를 가진 카드 N장
- **왜 추가했나**: 학습자 본인의 실수에서 직접 생성된 카드여야 "내가 진짜 못하는 패턴"에 집중할 수 있기 때문

### 2. **Orchestrator-Workers 병렬 처리**
- `select_entries`가 cosmetic(대소문자/마침표만 다른) 항목 제거, dedupe, N개 캡으로 워크리스트 결정
- `Send` API로 항목당 1워커 fan-out → 병렬 LLM 호출 → 응답 누적 → 후처리
- **왜 추가했나**: 단일 배치 프롬프트로 한 번에 N장을 만들면 LLM의 attention이 분산되어 카드 품질이 떨어지는 문제 해소. 또한 늦은 워커 1개가 전체 응답을 막지 않음

### 3. **카드별 영어 전용 튜터 Q&A**
- 채팅 입력에 `Card 2: give me 3 more examples` 같은 후속 질문 가능
- 시스템 프롬프트에서 **"Reply in ENGLISH ONLY — never use Korean"**을 강제
- **왜 추가했나**: 영어 몰입(immersion) 페다고지의 일관성 — 실시간 스피킹은 한국어 번역 단계를 거치지 않으므로, 연습도 그 습관을 학습시키지 않게 함

## 예상 사용 시나리오 (대화 예시)

```
사용자: (사이드바에서 오늘 날짜 선택 → "Load sample" 클릭 → "Generate today's deck" 클릭)
에이전트: Parsed **4** entries → fanned out to **4** parallel workers
          → enriched and rendered the deck below.

          ## Card 1 — `tense`
          **Target:** I want to ask you about the code.
          **Originally said:** I want to asking you about the code
          **Note:** After "want to," use the base form, not the gerund.
          **Pattern:** Tense / verb form — match the time frame; after modals,
                       'to', or auxiliaries use the bare infinitive.
          **Paraphrases:**
          - I would like to ask you about the code.
          - I want to inquire about the code.

          (Card 2 ~ 4 생략)

사용자: Card 1: give me 3 more example sentences with the same pattern.
에이전트: Sure! Here are three more examples:
          1. I want to tell you about the project.
          2. She wants to learn more about the topic.
          3. They need to fix the bug before tomorrow.

(다운로드 버튼 클릭 → deck.md / deck.json 로컬 저장 → 자기 전 음독 연습)
```

## 관련 스크린샷

> 배포 후 캡처 첨부 (최소 3장):
>
> 1. **TBD** — 메인 화면 (사이드바 + 빈 채팅)
> 2. **TBD** — 덱 생성 직후 (카드 expander 펼친 상태)
> 3. **TBD** — 채팅 후속 Q&A (Card N에 대한 튜터 응답)

## 개발 기술/스택

- **Agent framework**: LangGraph 1.1+ (`StateGraph`, `Send` API for orchestrator-workers, `Annotated[..., operator.add]` reducer, `add_conditional_edges`)
- **LLM**: OpenAI `gpt-4o-mini` (structured output via Pydantic v2 모델)
- **Tool**: `@tool`-decorated `pattern_glossary_lookup` (in-process custom tool)
- **UI**: Streamlit 1.57 (chat interface + sidebar + expander + file_uploader + download_button)
- **Deploy**: Streamlit Cloud (`requirements.txt` + `st.secrets`)
- **Lang/runtime**: Python 3.11+, `uv` for env/deps

## 엔지니어 클럽을 진행하며 느낀 점과, 다른 멤버들을 위한 팁

> (개인 회고 — 본인 톤에 맞게 다듬어서 사용)

- **회고**:
  - 처음엔 단순한 "내 실수 모음 → 복습 카드" 도구로 시작했는데, 강의에서 Orchestrator-Workers 패턴을 배우면서 자연스럽게 *"한 카드 = 한 워커"* 매핑이 떠올랐다. 단일 LLM 호출로 N장을 만드는 것보다 **카드당 집중된 프롬프트 + 병렬 실행**이 품질·지연 양면에서 우월했다.
  - 강의를 따라가며 "이 패턴은 내 프로젝트에 어떻게 매핑되지?"를 매번 물은 게 가장 큰 학습이었다.
- **다른 멤버들을 위한 팁**:
  1. **에이전트 주제는 본인이 매일 겪는 마찰(friction)에서 골라라.** 동기 부여가 다르고, 더미 데이터 대신 진짜 데이터로 검증할 수 있다.
  2. **고급 패턴은 *왜 필요한지*가 먼저다.** "Send API 써보고 싶어서" 말고 "왜 이 노드를 병렬화해야 하는가?"를 답할 수 있을 때 코드가 깔끔해진다.
  3. **end-to-end로 한 번이라도 돌려보기 전에 "끝났다"고 말하지 마라.** 컴파일이 통과해도 reducer를 잘못 끼우면 카드가 사라지는 일이 흔하다.
  4. **Streamlit Cloud 배포 시**: `requirements.txt`를 추가하고 (pyproject만으론 빌드 실패 사례 있음), 로컬 파일 의존성을 모두 *paste/upload* 옵션으로 대체해두면 리뷰어가 즉시 시연 가능하다.

---

*Built during Nomad Coders AI Agent Challenge (Day 30 → Day 42).*
