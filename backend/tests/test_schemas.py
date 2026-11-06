import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.conversations import ConversationRenameRequest


def test_chat_request_strips_values_and_uses_defaults():
    request = ChatRequest(message="  hello  ", thread_id="  thread-1  ")

    assert request.message == "hello"
    assert request.thread_id == "thread-1"
    assert request.model is None

    default_thread = ChatRequest(message="hello")
    assert default_thread.thread_id == "default"

    non_string_model = ChatRequest(message="hello", model=123)
    assert non_string_model.model is None


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"message": ""}, "message"),
        ({"message": "   "}, "message"),
        ({"message": 123}, "message"),
        ({"message": "hello", "thread_id": "   "}, "thread_id"),
        ({"message": "hello", "thread_id": 123}, "thread_id"),
    ],
)
def test_chat_request_rejects_invalid_required_strings(payload, field_name):
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest.model_validate(payload)

    assert exc_info.value.errors()[0]["loc"] == (field_name,)


def test_conversation_rename_request_strips_and_validates_title():
    assert ConversationRenameRequest(title="  Updated title  ").title == (
        "Updated title"
    )

    for title in ("", "   ", "x" * 81):
        with pytest.raises(ValidationError):
            ConversationRenameRequest(title=title)
