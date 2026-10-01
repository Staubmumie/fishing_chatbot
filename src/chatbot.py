"""Generate chatbot answers from retrieval, the chat model and tools.

No Streamlit code here, the UI lives in chatbot_ui.py.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from functools import lru_cache
from typing import Any, Callable

from langchain.agents import create_agent
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from .retrieval import retrieve_documents
from .tools import TOOL_LABELS, get_chat_tools


SYSTEM_PROMPT = """
You are a Fishing Assistant for recreational fishing in Germany.
Today's date is {today}.

Only answer fishing-related questions. If a request is unrelated, briefly say that you can only help with fishing topics.

Use available tools when relevant.

For fish species and general fishing knowledge, use `search_fishing_knowledge` before answering. This includes habitat, behavior, seasons, water conditions, diet, spawning, size, and fishing techniques. Use the results to verify your answer. Do not use this tool for regulations or personal catches.

For fishing regulations, use the retrieved legal context as the primary source. Regulations may differ by Bundesland, so only apply rules to the state they come from. Do not invent or infer unsupported regulations. Cite the relevant § and Bundesland when using legal context. If the Bundesland is required but unclear, ask for it. If the context is insufficient, say so.

Answer in the user's language. Be concise, clear, and practical.

Retrieved legal context:
{context}""".strip()


@lru_cache(maxsize=8)
def get_model(model_name: str, temperature: float) -> ChatOpenAI:
    """Create/reuse the LangChain chat model configured through OpenRouter."""
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_retries=2,
    )


def _format_pages(page: Any, page_end: Any) -> str | None:
    """A paragraph can span a page break, e.g. "pages 3-4"."""
    if page is None:
        return None

    if page_end is not None and page_end != page:
        return f"pages {page}-{page_end}"

    return f"page {page}"


def _format_context(documents: list[Document]) -> str:
    if not documents:
        return "No relevant legal passages were retrieved."

    chunks: list[str] = []

    for index, document in enumerate(documents, start=1):
        bundesland = document.metadata.get("bundesland")
        document_name = document.metadata.get("document", "unknown document")
        paragraph = document.metadata.get("paragraph")
        pages = _format_pages(
            document.metadata.get("page"),
            document.metadata.get("page_end"),
        )

        label_parts = [str(document_name)]
        if bundesland:
            label_parts.append(str(bundesland))
        if paragraph:
            label_parts.append(f"§ {paragraph}")
        if pages:
            label_parts.append(pages)

        chunks.append(
            f"[Source {index}: {', '.join(label_parts)}]\n"
            f"{document.page_content}"
        )

    return "\n\n".join(chunks)


def _extract_sources(documents: list[Document]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    for document in documents:
        document_name = document.metadata.get("document", "Unknown document")
        paragraph = document.metadata.get("paragraph")
        page = document.metadata.get("page")
        # Chunks are legal paragraphs now, so a page alone is not unique.
        key = (document_name, paragraph, page)

        if key in seen:
            continue

        seen.add(key)
        sources.append(
            {
                "document": document_name,
                "paragraph": paragraph,
                "page": page,
                "page_end": document.metadata.get("page_end"),
                "bundesland": document.metadata.get("bundesland"),
            }
        )

    return sources


def _extract_chunks(documents: list[Document]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    for index, document in enumerate(documents, start=1):
        chunks.append(
            {
                "index": index,
                "content": document.page_content,
                "document": document.metadata.get("document", "Unknown document"),
                "paragraph": document.metadata.get("paragraph"),
                "page": document.metadata.get("page"),
                "page_end": document.metadata.get("page_end"),
                "bundesland": document.metadata.get("bundesland"),
            }
        )

    return chunks


def _parse_tool_content(content: Any) -> Any:
    """Turn ToolMessage content back into Python data where possible.

    LangChain stores tool output as a (JSON) string or a list of text blocks.
    """
    if isinstance(content, list):
        content = "\n".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in content
        )

    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content

    return content


def _extract_tool_calls(new_messages: list[Any]) -> list[dict[str, Any]]:
    """Pair each tool call of this turn with the result the model received."""
    args_by_id: dict[str, dict[str, Any]] = {}
    tool_calls: list[dict[str, Any]] = []

    for message in new_messages:
        for tool_call in getattr(message, "tool_calls", None) or []:
            args_by_id[tool_call["id"]] = tool_call.get("args", {})

        if getattr(message, "type", None) == "tool":
            tool_calls.append(
                {
                    "name": message.name,
                    "args": args_by_id.get(message.tool_call_id, {}),
                    "result": _parse_tool_content(message.content),
                }
            )

    return tool_calls


def _to_langchain_history(
    history: list[dict[str, Any]],
    max_messages: int,
) -> list[dict[str, str]]:
    # messages[-0:] would return everything, so 0 needs its own case.
    if max_messages == 0:
        return []

    messages: list[dict[str, str]] = []

    for message in history:
        role = message.get("role")
        content = message.get("content", "")

        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    return messages[-max_messages:]


def _message_to_text(message: Any) -> str:
    content = getattr(message, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        return "\n".join(part for part in text_parts if part)

    return str(content)


def generate_response(
    prompt: str,
    history: list[dict[str, Any]],
    *,
    model_name: str,
    temperature: float,
    max_history_messages: int = 10,
    on_status: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Retrieve legal context, run the LangChain agent and return the answer.

    ``on_status`` is called with a short description of each processing step
    (retrieval, tool calls, answer generation) so a UI can show progress.
    """

    return asyncio.run(
        _generate_response_async(
            prompt=prompt,
            history=history,
            model_name=model_name,
            temperature=temperature,
            max_history_messages=max_history_messages,
            on_status=on_status,
        )
    )


async def _generate_response_async(
    prompt: str,
    history: list[dict[str, Any]],
    *,
    model_name: str,
    temperature: float,
    max_history_messages: int = 10,
    on_status: Callable[[str], None] | None = None,
) -> dict[str, Any]:

    def report(step: str) -> None:
        if on_status is not None:
            on_status(step)

    report("Searching fishing regulations")
    documents = retrieve_documents(prompt)

    context = _format_context(documents)
    model = get_model(model_name, temperature)

    # Local tools + MCP weather tools
    report("Loading tools")
    tools = await get_chat_tools()

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT.format(
            today=date.today().isoformat(),
            context=context,
        ),
    )

    messages = _to_langchain_history(
        history,
        max_messages=max_history_messages,
    )

    messages.append({
        "role": "user",
        "content": prompt,
    })

    # MCP tools are asynchronous, therefore astream instead of stream.
    # "values" yields the full state after every step, so the newest message
    # tells us whether the model is calling tools or has answered.
    report("Generating answer")
    result: dict[str, Any] = {"messages": messages}

    async for state in agent.astream({"messages": messages}, stream_mode="values"):
        result = state
        last_message = state["messages"][-1]

        for tool_call in getattr(last_message, "tool_calls", None) or []:
            name = tool_call["name"]
            report(f"Calling tool: {TOOL_LABELS.get(name, name)}")

        if getattr(last_message, "type", None) == "tool":
            report("Generating answer")

    final_message = result["messages"][-1]
    # Everything after the input messages was produced during this turn.
    new_messages = result["messages"][len(messages):]

    return {
        "answer": _message_to_text(final_message),
        "sources": _extract_sources(documents),
        "chunks": _extract_chunks(documents),
        "tool_calls": _extract_tool_calls(new_messages),
    }