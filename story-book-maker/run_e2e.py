"""End-to-end test of the Story Book Maker pipeline."""
import asyncio
import json

from google.adk.runners import InMemoryRunner
from google.genai import types

from story_book_maker import root_agent


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="story_book_test")
    session = await runner.session_service.create_session(
        app_name="story_book_test", user_id="u1"
    )

    msg = types.Content(
        role="user",
        parts=[types.Part(text="별을 모으는 작은 토끼")],
    )

    final_texts: list[str] = []
    async for event in runner.run_async(
        user_id="u1", session_id=session.id, new_message=msg
    ):
        author = getattr(event, "author", "?")
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{author}] {part.text[:200]}")
                    if event.is_final_response():
                        final_texts.append(part.text)
                if part.function_call:
                    print(f"[{author}] -> tool call: {part.function_call.name}")
                if part.function_response:
                    print(
                        f"[{author}] <- tool result: "
                        f"{json.dumps(part.function_response.response, ensure_ascii=False)[:200]}"
                    )

    final_session = await runner.session_service.get_session(
        app_name="story_book_test", user_id="u1", session_id=session.id
    )
    story = final_session.state.get("story")
    print("\n=== VERIFICATION ===")
    print("story in state:", bool(story))
    if story:
        print("title:", story.get("title"))
        print("pages:", len(story.get("pages", [])))

    artifact_keys = await runner.artifact_service.list_artifact_keys(
        app_name="story_book_test", user_id="u1", session_id=session.id
    )
    print("artifacts:", artifact_keys)


if __name__ == "__main__":
    asyncio.run(main())
