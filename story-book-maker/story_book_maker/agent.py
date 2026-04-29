"""Story Book Maker — Google ADK pipeline (Gemini + native image gen).

StoryWriter writes a 5-page children's story to state["story"];
Illustrator reads it back and saves one PNG per page as an Artifact.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "gemini-2.5-flash-image"


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
    pages: list[StoryPage] = Field(description="Exactly 5 pages, in order")


story_writer = LlmAgent(
    name="story_writer",
    model=TEXT_MODEL,
    description="Writes a 5-page children's story for a given theme.",
    instruction=(
        "You are a children's book author. The user provides a theme. "
        "Write a warm, simple 5-page story — 1 to 2 short Korean sentences per page. "
        "For each page also write a concise English visual description that an "
        "illustrator can draw. Return strictly the StoryBook schema, no extra prose."
    ),
    output_schema=StoryBook,
    output_key="story",
)


async def generate_illustrations(tool_context: ToolContext) -> dict:
    """Read state['story'] and save one image per page as page_<n>.png."""
    story = tool_context.state.get("story")
    if not story:
        return {"status": "error", "message": "No story found in state."}

    pages = story.get("pages", [])
    client = genai.Client()
    saved: list[dict] = []

    for page in pages:
        n = page["page"]
        prompt = (
            "Children's storybook illustration, soft watercolor style, whimsical and friendly. "
            f"{page['visual']}. No text in image."
        )
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
            return {"status": "error", "page": n, "message": "No image bytes returned"}

        artifact = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        artifact_name = f"page_{n}.png"
        await tool_context.save_artifact(artifact_name, artifact)
        saved.append({"page": n, "artifact": artifact_name})

    return {"status": "ok", "count": len(saved), "saved": saved}


illustrator = LlmAgent(
    name="illustrator",
    model=TEXT_MODEL,
    description="Generates illustrations for the story pages saved in state.",
    instruction=(
        "A 5-page story is already written and stored in state['story']. "
        "Call the `generate_illustrations` tool exactly once — it reads state and "
        "saves one PNG artifact per page. After it returns, write a short Korean "
        "summary listing each page number and its saved artifact filename."
    ),
    tools=[generate_illustrations],
)


root_agent = SequentialAgent(
    name="story_book_maker",
    description="Two-step pipeline: write a 5-page children's story, then illustrate each page.",
    sub_agents=[story_writer, illustrator],
)
