import logging
import re
import time

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.messages.utils import count_tokens_approximately
from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from uuid import uuid4

from app.agents.current_info import live_search_query, needs_live_web_search
from app.agents.prompts import SYSTEM_PROMPT, build_system_prompt  # noqa: F401
from app.schemas.chat import CHAT_MODES
from app.core.config import (
    DEEP_RESEARCH_CONTEXT_TOKENS,
    DEFAULT_GROQ_MODEL,
    LANGGRAPH_DATABASE_URL,
    MAX_CONTEXT_TOKENS,
    MAX_TOOL_OUTPUT_CHARS,
)
from app.tools import all_tools, tools, tools_for_mode


DEFAULT_MODEL = DEFAULT_GROQ_MODEL
logger = logging.getLogger(__name__)



class AgentState(MessagesState, total=False):
    # Set on every request; they are not part of the conversation itself.
    mode: str
    instructions: str
    auto_web_search: bool
    auto_tool_call: bool
    auto_image_generation: bool

ALLOWED_MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
}
MODEL_FALLBACK_ORDER = (
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
)
MODEL_RATE_LIMIT_COOLDOWN_SECONDS = 60

_CHECKPOINT_POOL = ConnectionPool(
    conninfo=LANGGRAPH_DATABASE_URL,
    min_size=1,
    max_size=10,
    open=True,
    kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    },
)
_CHECKPOINTER = PostgresSaver(_CHECKPOINT_POOL)
_CHECKPOINTER.setup()

_TRUNCATION_SUFFIX = "... [truncated]"


def _truncate_tool_message(message: ToolMessage) -> ToolMessage:
    output_limit = max(MAX_TOOL_OUTPUT_CHARS, len(_TRUNCATION_SUFFIX))
    if not isinstance(message.content, str) or len(message.content) <= output_limit:
        return message

    content = (
        message.content[: output_limit - len(_TRUNCATION_SUFFIX)]
        + _TRUNCATION_SUFFIX
    )
    return message.model_copy(update={"content": content})


def _truncate_tool_outputs(messages: list[BaseMessage]) -> list[BaseMessage]:
    truncated = []

    for message in messages:
        if isinstance(message, ToolMessage):
            message = _truncate_tool_message(message)

        truncated.append(message)

    return truncated


def _truncate_tool_call_result(request, execute):
    result = execute(request)
    if isinstance(result, ToolMessage):
        return _truncate_tool_message(result)
    return result


def _remove_orphan_tool_messages(
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    cleaned = []
    pending_tool_call_ids: set[str] = set()

    for message in messages:
        if isinstance(message, HumanMessage):
            pending_tool_call_ids.clear()
            cleaned.append(message)
        elif isinstance(message, AIMessage):
            pending_tool_call_ids = {
                str(tool_call["id"])
                for tool_call in message.tool_calls
                if tool_call.get("id")
            }
            cleaned.append(message)
        elif isinstance(message, ToolMessage):
            tool_call_id = str(message.tool_call_id)
            if tool_call_id in pending_tool_call_ids:
                cleaned.append(message)
                pending_tool_call_ids.remove(tool_call_id)
        else:
            pending_tool_call_ids.clear()
            cleaned.append(message)

    return cleaned


def _messages_for_model(
    messages: list[BaseMessage],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> list[BaseMessage]:
    shortened = _truncate_tool_outputs(messages)
    trimmed = trim_messages(
        shortened,
        max_tokens=max_tokens,
        token_counter=count_tokens_approximately,
        strategy="last",
        start_on="human",
    )
    trimmed = _remove_orphan_tool_messages(trimmed)

    latest_human_index = next(
        (
            index
            for index in range(len(shortened) - 1, -1, -1)
            if isinstance(shortened[index], HumanMessage)
        ),
        None,
    )

    if latest_human_index is None:
        return trimmed

    latest_human = shortened[latest_human_index]
    if any(message is latest_human for message in trimmed):
        return trimmed

    current_turn = _remove_orphan_tool_messages(
        shortened[latest_human_index:]
    )
    if count_tokens_approximately(current_turn) <= max_tokens:
        return current_turn

    return [latest_human]


def normalize_model_name(model_name: str | None) -> str:
    """
    Validate selected model from frontend.
    If model is missing or not allowed, fallback to DEFAULT_MODEL.
    """

    if not model_name:
        return DEFAULT_MODEL

    model_name = model_name.strip()

    if model_name not in ALLOWED_MODELS:
        return DEFAULT_MODEL

    return model_name


def _is_model_rate_limit_error(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return (
        "rate limit" in error_text
        or "rate_limit" in error_text
        or "tokens per minute" in error_text
        or "tpm" in error_text
        or "request too large" in error_text
        or "error code: 429" in error_text
    )


def _model_attempt_order(selected_model: str) -> list[str]:
    return [selected_model] + [
        model for model in MODEL_FALLBACK_ORDER if model != selected_model
    ]


def _latest_human_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content
    return ""


_IMAGE_REFINEMENT = re.compile(
    r"\b(?:make|change|turn|add|remove|replace|use|want|variation|version|"
    r"style|background|colour|color|pose|wearing|with|without|instead|"
    r"saiyan|ssj)\b",
    re.IGNORECASE,
)
_LEGACY_IMAGE_QUALITY_SUFFIX = (
    " High-quality polished anime illustration, accurate anatomy, coherent "
    "face and hands, crisp sharp details, balanced dynamic composition, "
    "cinematic lighting, no text, no captions, no logo, no signature, and "
    "no watermark."
)
_IMAGE_QUALITY_SUFFIX = (
    " High-quality polished image that faithfully follows the requested "
    "subject and visual style, accurate anatomy, coherent face and hands, "
    "crisp sharp details, balanced composition, no captions, no logo, no "
    "signature, and no watermark."
)
_IMAGE_USER_REQUEST_MARKER = "\nUser image request: "


def _previous_image_prompt(messages: list[BaseMessage]) -> str:
    latest_human_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        len(messages),
    )
    for message in reversed(messages[:latest_human_index]):
        if not isinstance(message, AIMessage):
            continue
        for call in reversed(message.tool_calls):
            if call.get("name") != "generate_image":
                continue
            prompt = (call.get("args") or {}).get("prompt")
            if isinstance(prompt, str) and prompt.strip():
                prompt = prompt.strip()
                if _IMAGE_USER_REQUEST_MARKER in prompt:
                    return prompt.rsplit(_IMAGE_USER_REQUEST_MARKER, 1)[1].strip()
                return prompt
    return ""


def _is_image_refinement(message: str, previous_prompt: str) -> bool:
    return bool(
        previous_prompt
        and len(message.strip()) <= 300
        and _IMAGE_REFINEMENT.search(message)
    )


def _image_generation_prompt(
    message: str,
    previous_prompt: str = "",
) -> str:
    request = message.strip()
    if previous_prompt:
        for suffix in (_IMAGE_QUALITY_SUFFIX, _LEGACY_IMAGE_QUALITY_SUFFIX):
            previous_prompt = previous_prompt.removesuffix(suffix)
        if previous_prompt.startswith("Original image request:"):
            request = f"{previous_prompt} Additional requested revision: {request}."
        else:
            request = (
                f"Original image request: {previous_prompt}. "
                f"Requested revision: {request}."
            )

    details = ""
    is_goku = bool(re.search(r"\b(?:son\s+)?goku\b", request, re.I))
    is_ben_10 = bool(re.search(r"\bben\s*(?:10|ten)\b", request, re.I))
    is_super_saiyan_3 = bool(re.search(
        r"\b(?:sup(?:er|per)\s+saiyan\s*3|ssj\s*3)\b",
        request,
        re.I,
    ))
    if is_goku and is_super_saiyan_3:
        details = (
            "STRICT flat 2D cel-animation of canonical Son Goku from Dragon "
            "Ball Z in Super Saiyan 3 form. Single full-body character with "
            "extremely long dense golden hair flowing below his waist, no "
            "eyebrows, a heavy brow ridge, teal-green eyes, familiar face, "
            "bright orange gi with dark-blue undershirt, belt and wristbands, "
            "gold aura and blue-white lightning. Show all his hair. Clean black "
            "outlines and flat saturated colors. No short hair, realism, 3D, "
            "collage, text, signature, or watermark."
        )
    elif is_goku:
        details = (
            "STRICT flat 2D cel-animation of canonical Son Goku from Dragon "
            "Ball Z. Single centered front-facing waist-up character: large "
            "jet-black spiky hair, round open black anime eyes, small nose, "
            "cheerful expression, athletic build, and accurate anatomy. His "
            "bright orange gi must dominate the torso; dark blue appears only "
            "on the undershirt, belt and wristbands. Clean black outlines, flat "
            "saturated colors. No realistic face, angry scowl, 3D, black gi, "
            "cloak, circular frame, moon, collage, text, signature, or watermark."
        )
    elif is_ben_10:
        details = (
            "STRICT flat 2D western TV-cartoon image of canonical Ben Tennyson "
            "from the original 2005 Ben 10 series. Exactly one 10-year-old boy "
            "with child proportions, short tousled brown hair, green eyes, and a "
            "friendly determined expression. He wears the original outfit: a "
            "white short-sleeve crew-neck T-shirt with one bold black vertical "
            "center stripe from collar to hem and black sleeve trim, olive-green "
            "cargo pants, and black-and-white sneakers. Green appears only on the "
            "Omnitrix dial and cargo pants, never on the shirt. Show both arms and "
            "his raised left forearm; the large black-and-green Omnitrix is clearly "
            "visible on his left wrist. Clean black outlines and flat cel colors. "
            "No adult, woman, girl, diagonal stripe, green shirt, high collar, "
            "long sleeves, bodysuit, realism, 3D, circular frame, collage, text, "
            "signature, or watermark."
        )

    if details:
        return details + _IMAGE_USER_REQUEST_MARKER + request
    return request + _IMAGE_QUALITY_SUFFIX


def _current_turn_used_web_search(messages: list[BaseMessage]) -> bool:
    """Return whether Tavily was already requested after the latest user message."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if isinstance(message, AIMessage) and any(
            call.get("name") == "tavily_search" for call in message.tool_calls
        ):
            return True
    return False


def _tools_for_model_turn(mode: str, messages: list[BaseMessage]) -> list:
    if mode != "deep_research" and _current_turn_used_web_search(messages):
        return []
    return tools_for_mode(mode)


def _flatten_current_web_search(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Turn the automatic tool exchange into plain evidence for final answering."""
    latest_human_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        None,
    )
    if latest_human_index is None:
        return messages

    search_call_ids = {
        str(call["id"])
        for message in messages[latest_human_index + 1 :]
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call.get("name") == "tavily_search" and call.get("id")
    }
    if not search_call_ids:
        return messages

    search_results = [
        str(message.content)
        for message in messages[latest_human_index + 1 :]
        if isinstance(message, ToolMessage)
        and str(message.tool_call_id) in search_call_ids
    ]
    if not search_results:
        return messages

    latest_human = messages[latest_human_index]
    enriched_human = latest_human.model_copy(
        update={
            "content": (
                f"{latest_human.content}\n\n"
                "[Live web search evidence already retrieved. Answer from "
                "this evidence; do not request another search.]\n"
                + "\n\n".join(search_results)
            )
        }
    )
    cleaned_current_turn = []
    for message in messages[latest_human_index + 1 :]:
        if isinstance(message, AIMessage) and any(
            str(call.get("id")) in search_call_ids
            for call in message.tool_calls
        ):
            continue
        if isinstance(message, ToolMessage) and (
            str(message.tool_call_id) in search_call_ids
        ):
            continue
        cleaned_current_turn.append(message)

    return (
        messages[:latest_human_index]
        + [enriched_human]
        + cleaned_current_turn
    )


def _automatic_tool_router(state: AgentState):
    """Deterministically start tools that should not depend on model choice."""
    mode = state.get("mode") or ""
    message = _latest_human_text(state["messages"])
    previous_image_prompt = _previous_image_prompt(state["messages"])
    image_request = mode == "image" or _is_image_refinement(
        message,
        previous_image_prompt,
    )

    if image_request:
        return {
            "auto_web_search": False,
            "auto_tool_call": True,
            "auto_image_generation": True,
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "generate_image",
                            "args": {
                                "prompt": _image_generation_prompt(
                                    message,
                                    previous_image_prompt,
                                )
                            },
                            "id": f"auto-image-{uuid4()}",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
        }

    should_search = needs_live_web_search(message, mode)

    if not should_search:
        return {
            "auto_web_search": False,
            "auto_tool_call": False,
            "auto_image_generation": False,
        }

    return {
        "auto_web_search": True,
        "auto_tool_call": True,
        "auto_image_generation": False,
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "tavily_search",
                        "args": {"query": live_search_query(message)},
                        "id": f"auto-web-search-{uuid4()}",
                        "type": "tool_call",
                    }
                ],
            )
        ],
    }


def _route_automatic_tool(state: AgentState) -> str:
    return "tools" if state.get("auto_tool_call") else "chatbot"


def _current_turn_used_image_generation(messages: list[BaseMessage]) -> bool:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if isinstance(message, AIMessage) and any(
            call.get("name") == "generate_image" for call in message.tool_calls
        ):
            return True
    return False


def _current_image_tool_result(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if (
            isinstance(message, ToolMessage)
            and message.name == "generate_image"
            and isinstance(message.content, str)
        ):
            return message.content
    return ""


def _route_after_tools(state: AgentState) -> str:
    if (
        state.get("auto_image_generation")
        and _current_turn_used_image_generation(state["messages"])
    ):
        return "image_confirmation"
    return "chatbot"


def _image_confirmation_node(state: AgentState):
    result = _current_image_tool_result(state["messages"])
    if "IMAGE_URL:" in result:
        content = "Done — I created the image and displayed it above."
    else:
        content = (
            result
            if result.startswith("Image generation failed:")
            else "Image generation failed. Please try again."
        )
    return {"messages": [AIMessage(content=content)]}


def build_agent(model_name: str):
    """Build one LangGraph agent for a selected Groq model."""

    selected_model = normalize_model_name(model_name)

    llms = {}
    bound_by_model_and_mode = {}
    rate_limited_until = {}

    def model_for(
        mode: str,
        offered_tools: list,
        model_name: str = selected_model,
    ):
        if model_name not in llms:
            llms[model_name] = ChatGroq(
                model=model_name,
                temperature=0.3,
                streaming=True,
                # Fail over immediately instead of making the user wait while
                # the same model remains over its per-minute quota.
                max_retries=0,
                timeout=30,
            )

        tool_names = tuple(tool.name for tool in offered_tools)
        cache_key = (model_name, mode, tool_names)
        if cache_key not in bound_by_model_and_mode:
            extra = {}
            # GPT-OSS exposes an adjustable reasoning budget.
            if mode == "thinking" and model_name.startswith("openai/gpt-oss"):
                extra["reasoning_effort"] = "high"
            if offered_tools:
                bound = llms[model_name].bind_tools(offered_tools, **extra)
            elif extra:
                bound = llms[model_name].bind(**extra)
            else:
                bound = llms[model_name]
            bound_by_model_and_mode[cache_key] = bound
        return bound_by_model_and_mode[cache_key]

    def chatbot_node(state: AgentState):
        mode = state.get("mode") or ""
        mode = mode if mode in CHAT_MODES else ""
        max_tokens = (
            max(MAX_CONTEXT_TOKENS, DEEP_RESEARCH_CONTEXT_TOKENS)
            if mode == "deep_research"
            else MAX_CONTEXT_TOKENS
        )
        history = _messages_for_model(state["messages"], max_tokens)
        answering_from_web_search = (
            mode != "deep_research"
            and _current_turn_used_web_search(state["messages"])
        )
        if answering_from_web_search:
            history = _flatten_current_web_search(history)
        system_prompt = build_system_prompt(mode, state.get("instructions"))
        messages = [SystemMessage(content=system_prompt)] + history
        offered_tools = _tools_for_model_turn(mode, state["messages"])
        last_rate_limit_error = None
        for attempt_model in _model_attempt_order(selected_model):
            if rate_limited_until.get(attempt_model, 0) > time.monotonic():
                continue
            try:
                response = model_for(
                    mode,
                    offered_tools,
                    attempt_model,
                ).invoke(messages)
                return {"messages": [response]}
            except Exception as exc:
                if not _is_model_rate_limit_error(exc):
                    raise
                last_rate_limit_error = exc
                rate_limited_until[attempt_model] = (
                    time.monotonic() + MODEL_RATE_LIMIT_COOLDOWN_SECONDS
                )
                logger.warning(
                    "Model %s reached a rate limit; trying the next model",
                    attempt_model,
                )

        if last_rate_limit_error is not None:
            raise last_rate_limit_error
        raise RuntimeError("All configured chat models are cooling down.")

    tool_node = ToolNode(all_tools, wrap_tool_call=_truncate_tool_call_result)

    workflow = StateGraph(AgentState)
    workflow.add_node("automatic_tool_router", _automatic_tool_router)
    workflow.add_node("chatbot", chatbot_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("image_confirmation", _image_confirmation_node)
    workflow.add_edge(START, "automatic_tool_router")
    workflow.add_conditional_edges(
        "automatic_tool_router",
        _route_automatic_tool,
        {"tools": "tools", "chatbot": "chatbot"},
    )
    workflow.add_conditional_edges("chatbot", tools_condition)
    workflow.add_conditional_edges(
        "tools",
        _route_after_tools,
        {"image_confirmation": "image_confirmation", "chatbot": "chatbot"},
    )
    workflow.add_edge("image_confirmation", END)

    return workflow.compile(checkpointer=_CHECKPOINTER)


_AGENT_CACHE = {}


def get_agent(model_name: str | None = None):
    """
    Return cached LangGraph agent for selected model.
    If not created yet, create it once and reuse it.
    """

    selected_model = normalize_model_name(model_name)

    if selected_model not in _AGENT_CACHE:
        _AGENT_CACHE[selected_model] = build_agent(selected_model)

    return _AGENT_CACHE[selected_model]
