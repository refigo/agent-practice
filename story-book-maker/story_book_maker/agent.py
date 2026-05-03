"""Story Book Maker — Google ADK pipeline (Sequential + Parallel + Callbacks).

Pipeline:
    SequentialAgent
      ├─ story_writer        (LlmAgent, output_schema=StoryBook → state["story"])
      └─ parallel_illustrator (ParallelAgent of 5 page-bound illustrators)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "gemini-2.5-flash-image"
PAGE_COUNT = 5


class StoryPage(BaseModel):
    page: int = Field(description="1-indexed page number")
    text: str = Field(
        description="Page text in Korean — 1 to 2 short, warm sentences for young children",
    )
    visual: str = Field(
        description="Concise English visual description for the illustrator",
    )


class StoryBook(BaseModel):
    title: str = Field(description="Story title in Korean")
    theme: str = Field(description="Echo of the theme the user requested")
    pages: list[StoryPage] = Field(description=f"Exactly {PAGE_COUNT} pages, in order")


# ---------- Story Writer ----------

def _writer_before(callback_context: CallbackContext) -> Optional[types.Content]:
    print("📝 스토리 작성 중...", flush=True)
    return None


def _writer_after(callback_context: CallbackContext) -> Optional[types.Content]:
    story = callback_context.state.get("story")
    if isinstance(story, dict):
        title = story.get("title", "(제목 없음)")
        pages = len(story.get("pages", []))
        print(f"✅ 스토리 완성: 「{title}」 ({pages}페이지)", flush=True)
    return None


story_writer = LlmAgent(
    name="story_writer",
    model=TEXT_MODEL,
    description="Writes a 5-page children's story for a given theme.",
    instruction=(
        f"You are a children's book author. The user provides a theme. "
        f"Write a warm, simple {PAGE_COUNT}-page story — 1 to 2 short Korean sentences per page. "
        "For each page also write a concise English visual description that an "
        "illustrator can draw. Return strictly the StoryBook schema, no extra prose."
    ),
    output_schema=StoryBook,
    output_key="story",
    before_agent_callback=_writer_before,
    after_agent_callback=_writer_after,
)


# ---------- Page-bound Illustrators ----------

def _make_page_illustrator(page_num: int) -> LlmAgent:
    async def generate_page_image(tool_context: ToolContext) -> dict:
        story = tool_context.state.get("story") or {}
        pages = story.get("pages", [])
        if page_num > len(pages):
            return {"status": "error", "page": page_num, "message": "page not in state"}

        page = pages[page_num - 1]
        prompt = (
            "Children's storybook illustration, soft watercolor style, whimsical and friendly. "
            f"{page['visual']}. No text in image."
        )
        client = genai.Client()
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        img_bytes: bytes | None = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                img_bytes = part.inline_data.data
                break
        if not img_bytes:
            return {"status": "error", "page": page_num, "message": "no image bytes"}

        artifact = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        artifact_name = f"page_{page_num}.png"
        await tool_context.save_artifact(artifact_name, artifact)
        return {"status": "ok", "page": page_num, "artifact": artifact_name}

    generate_page_image.__name__ = f"generate_page_{page_num}_image"
    generate_page_image.__doc__ = (
        f"Generate page {page_num}'s illustration from state['story'] and save it as page_{page_num}.png."
    )

    def _before(callback_context: CallbackContext) -> Optional[types.Content]:
        print(f"🎨 이미지 {page_num}/{PAGE_COUNT} 생성 중...", flush=True)
        return None

    def _after(callback_context: CallbackContext) -> Optional[types.Content]:
        print(f"✅ 이미지 {page_num}/{PAGE_COUNT} 완료", flush=True)
        return None

    return LlmAgent(
        name=f"page_{page_num}_illustrator",
        model=TEXT_MODEL,
        description=f"Generates the illustration for page {page_num}.",
        instruction=(
            f"Call `generate_page_{page_num}_image` exactly once. "
            "When it returns, reply with a single short Korean sentence confirming the artifact was saved."
        ),
        tools=[generate_page_image],
        before_agent_callback=_before,
        after_agent_callback=_after,
    )


parallel_illustrator = ParallelAgent(
    name="parallel_illustrator",
    description="Generates all 5 page illustrations concurrently.",
    sub_agents=[_make_page_illustrator(i) for i in range(1, PAGE_COUNT + 1)],
)


# ---------- Root ----------

def _root_after(callback_context: CallbackContext) -> Optional[types.Content]:
    print("🎉 동화책 완성!", flush=True)
    return None


root_agent = SequentialAgent(
    name="story_book_maker",
    description="Two-step pipeline: write a 5-page children's story, then illustrate each page in parallel.",
    sub_agents=[story_writer, parallel_illustrator],
    after_agent_callback=_root_after,
)
