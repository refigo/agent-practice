# Movie Expert Agent

OpenAI `gpt-4o-mini`를 사용한 영화 정보 에이전트입니다. 사용자의 자연어 질문에 따라 적절한 API 함수를 자동으로 선택하여 영화 정보를 조회합니다.

## 사전 준비

1. [uv](https://docs.astral.sh/uv/) 설치
2. OpenAI API 키 발급

## 설정

```bash
cd movie-expert-agent

# 의존성 설치
uv sync

# .env 파일에 API 키 설정
echo "OPENAI_API_KEY=your-key-here" > .env
```

## 실행

### Jupyter Notebook으로 실행

```bash
uv run jupyter notebook movie_expert_agent.ipynb
```

브라우저에서 노트북이 열리면 셀을 순서대로 실행하세요.

### 전체 셀 일괄 실행 (CLI)

```bash
uv run jupyter nbconvert --to notebook --execute movie_expert_agent.ipynb --output movie_expert_agent.ipynb
```

## 사용 가능한 기능

| 함수 | 설명 | 예시 질문 |
|------|------|----------|
| `get_popular_movies()` | 현재 인기 영화 목록 조회 | "지금 인기 있는 영화가 뭐야?" |
| `get_movie_details(movie_id)` | 특정 영화의 상세 정보 조회 | "movie ID 550 영화가 뭐야?" |
| `get_movie_credits(movie_id)` | 특정 영화의 출연진/제작진 조회 | "movie ID 550 영화에 누가 출연해?" |

## API

- Base URL: `https://nomad-movies.nomadcoders.workers.dev`
- `GET /movies` — 인기 영화 목록
- `GET /movies/:id` — 영화 상세 정보
- `GET /movies/:id/credits` — 출연진 및 제작진
