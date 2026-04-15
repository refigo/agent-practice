"""One-off setup: upload goals.txt and create an OpenAI vector store.

Usage:
    uv run python setup_vector_store.py

Prints the created vector store ID. Copy the printed line into .env so that
app.py can pick it up:

    OPENAI_VECTOR_STORE_ID=vs_...

Re-run this script only when you want to rebuild the index from scratch
(e.g., after editing goals.txt). Note: it creates a NEW vector store each time
— you must update .env with the new ID.
"""

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GOALS_PATH = Path(__file__).parent / "goals.txt"
VECTOR_STORE_NAME = "life-coach-goals"


def main() -> None:
    if not GOALS_PATH.exists():
        raise FileNotFoundError(f"{GOALS_PATH} not found")

    client = OpenAI()

    print(f"[1/3] Uploading {GOALS_PATH.name} to OpenAI Files...")
    with GOALS_PATH.open("rb") as f:
        file = client.files.create(file=f, purpose="assistants")
    print(f"      file_id = {file.id}")

    print(f"[2/3] Creating vector store '{VECTOR_STORE_NAME}'...")
    vs = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"      vector_store_id = {vs.id}")

    print("[3/3] Attaching file and waiting for indexing...")
    client.vector_stores.files.create_and_poll(
        vector_store_id=vs.id,
        file_id=file.id,
    )
    print("      indexed ✅")

    print()
    print("=" * 64)
    print("Done! Add this line to life-coach-agent/.env:")
    print()
    print(f"    OPENAI_VECTOR_STORE_ID={vs.id}")
    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
