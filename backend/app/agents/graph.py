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
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

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



class AgentState(MessagesState, total=False):
    # Set on every request; they are not part of the conversation itself.
    mode: str
    instructions: str

ALLOWED_MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
}

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


def build_agent(model_name: str):
    """Build one LangGraph agent for a selected Groq model."""

    selected_model = normalize_model_name(model_name)

    llm = ChatGroq(
        model=selected_model,
        temperature=0.3,
        streaming=True,
        max_retries=1,
        timeout=30,
    )

    bound_by_mode = {}

    def model_for(mode: str):
        if mode not in bound_by_mode:
            extra = {}
            # GPT-OSS exposes an adjustable reasoning budget.
            if mode == "thinking" and selected_model.startswith("openai/gpt-oss"):
                extra["reasoning_effort"] = "high"
            bound_by_mode[mode] = llm.bind_tools(tools_for_mode(mode), **extra)
        return bound_by_mode[mode]

    def chatbot_node(state: AgentState):
        mode = state.get("mode") or ""
        mode = mode if mode in CHAT_MODES else ""
        max_tokens = (
            max(MAX_CONTEXT_TOKENS, DEEP_RESEARCH_CONTEXT_TOKENS)
            if mode == "deep_research"
            else MAX_CONTEXT_TOKENS
        )
        history = _messages_for_model(state["messages"], max_tokens)
        system_prompt = build_system_prompt(mode, state.get("instructions"))
        messages = [SystemMessage(content=system_prompt)] + history
        response = model_for(mode).invoke(messages)

        return {"messages": [response]}

    tool_node = ToolNode(all_tools, wrap_tool_call=_truncate_tool_call_result)

    workflow = StateGraph(AgentState)
    workflow.add_node("chatbot", chatbot_node)
    workflow.add_node("tools", tool_node)
    workflow.add_edge(START, "chatbot")
    workflow.add_conditional_edges("chatbot", tools_condition)
    workflow.add_edge("tools", "chatbot")

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
