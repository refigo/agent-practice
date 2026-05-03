"""End-to-end test of the Story Book Maker pipeline (Sequential + Parallel)."""
import asyncio
import time

from google.adk.runners import InMemoryRunner
from google.genai import types

from story_book_maker import root_agent


async def run_one(theme: str) -> None:
    app = f"e2e_{abs(hash(theme)) % 10_000}"
    runner = InMemoryRunner(agent=root_agent, app_name=app)
    session = await runner.session_service.create_session(app_name=app, user_id="u1")

    msg = types.Content(role="user", parts=[types.Part(text=theme)])

    print(f"\n========== THEME: {theme} ==========")
    started = time.perf_counter()
    async for event in runner.run_async(
        user_id="u1", session_id=session.id, new_message=msg
    ):
        # Tool calls / responses from each parallel sub-agent
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"  [{event.author}] -> {part.function_call.name}()")
    elapsed = time.perf_counter() - started

    final_session = await runner.session_service.get_session(
        app_name=app, user_id="u1", session_id=session.id
    )
    story = final_session.state.get("story") or {}
    artifacts = await runner.artifact_service.list_artifact_keys(
        app_name=app, user_id="u1", session_id=session.id
    )

    print(f"\n--- VERIFY '{theme}' ---")
    print(f"title:     {story.get('title')}")
    print(f"pages:     {len(story.get('pages', []))}")
    print(f"artifacts: {sorted(artifacts)}")
    print(f"elapsed:   {elapsed:.1f}s")
    assert len(story.get("pages", [])) == 5, "expected 5 pages"
    assert sorted(artifacts) == [f"page_{i}.png" for i in range(1, 6)], "missing artifacts"
    print("OK ✓")


async def main() -> None:
    for theme in ["용감한 아기 고양이 이야기", "달빛을 따라가는 작은 다람쥐"]:
        await run_one(theme)


if __name__ == "__main__":
    asyncio.run(main())
