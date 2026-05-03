"""Story Book Maker — Google ADK pipeline (Sequential + Parallel + Callbacks).

Pipeline:
    SequentialAgent
      ├─ story_writer        (LlmAgent, output_schema=StoryBook → state["story"])
      └─ parallel_illustrator (ParallelAgent of 5 page-bound illustrators)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from typing import AsyncGenerator

from dotenv import load_dotenv
from google import genai
from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
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


# ---------- Finalizer (assembles the completed storybook view) ----------

class StorybookFinalizer(BaseAgent):
    """Reads state['story'] and emits one combined page-by-page text block.

    Pairs with the artifacts saved by the parallel illustrators so the chat
    output presents a complete storybook (text) alongside the Artifacts tab (images).
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        story = ctx.session.state.get("story") or {}
        title = story.get("title", "(제목 없음)")
        pages = story.get("pages", [])

        lines: list[str] = [f"# 📖 {title}", ""]
        for p in pages:
            n = p.get("page")
            lines.append(f"## Page {n}")
            lines.append(f"**Text:** {p.get('text', '')}")
            lines.append(f"**Visual:** {p.get('visual', '')}")
            lines.append(f"**Image:** `page_{n}.png` (Artifacts 탭 참고)")
            lines.append("")
        lines.append("🎉 동화책이 완성되었습니다!")

        text = "\n".join(lines)
        print(text, flush=True)

        yield Event(
            author=self.name,
            invocationId=ctx.invocation_id,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
        )


finalizer = StorybookFinalizer(
    name="finalizer",
    description="Assembles the final storybook view (text + image references).",
)


# ---------- Root ----------

def _root_after(callback_context: CallbackContext) -> Optional[types.Content]:
    print("🎉 동화책 완성!", flush=True)
    return None


root_agent = SequentialAgent(
    name="story_book_maker",
    description=(
        "Three-step pipeline: write a 5-page children's story, illustrate each "
        "page in parallel, then assemble the final storybook view."
    ),
    sub_agents=[story_writer, parallel_illustrator, finalizer],
    after_agent_callback=_root_after,
)
