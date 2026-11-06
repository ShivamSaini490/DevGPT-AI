import sys
from pathlib import Path

from langchain_core.messages import HumanMessage


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.agents import get_agent  # noqa: E402
from app.db import init_db  # noqa: E402


init_db()

agent = get_agent("openai/gpt-oss-120b")

config = {
    "configurable": {
        "thread_id": "test_thread_id",
    }
}

for message_chunk, metadata in agent.stream(
    {"messages": [HumanMessage(content="What is My name?")]},
    config=config,
    stream_mode="messages",
):
    if message_chunk.content:
        print(message_chunk.content, end=" ", flush=True)
