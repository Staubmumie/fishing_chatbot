"""
Chatbot page including the developer panel in the sidebar.
UI only: model/RAG/tool orchestration lives in chatbot.py.
"""

import streamlit as st

from .chatbot import generate_response


# ---------------------------------------------------------
# Developer Panel
# ---------------------------------------------------------

def render_sidebar():

    with st.sidebar:

        st.title("Developer Panel")

        st.subheader("Model")

        st.selectbox(
            "Model",
            [
                "openai/gpt-5-mini",
                "openai/gpt-5-nano",
            ],
            key="model",
        )

        st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=0.7,
            step=0.1,
            key="temperature",
        )

        st.divider()

        st.subheader("Conversation")

        st.slider(
            "Max History Messages",
            min_value=0,
            max_value=20,
            value=10,
            step=1,
            key="max_history_messages",
        )

        st.caption(
            "Number of previous messages sent to the model. 0 disables history."
        )

        st.divider()

        if st.button(
            "Clear Chat",
            use_container_width=True,
        ):
            st.session_state.messages = []
            st.rerun()


# ---------------------------------------------------------
# Small UI helper
# ---------------------------------------------------------

def render_sources(sources):
    if not sources:
        return

    with st.expander("Sources"):
        for source in sources:
            label = str(source.get("source", "Unknown source"))
            page = source.get("page")
            if page is not None:
                label += f" — page {page}"
            st.markdown(f"- {label}")

TOOL_DISPLAY_NAMES = {
    "search_personal_catches": "Personal Catches",
    "search_fishing_knowledge": "Web Search",
    "openmeteo_search_locations": "Weather Location Search",
    "openmeteo_get_forecast": "Weather Forecast",
}


def _is_record_list(value):
    return isinstance(value, list) and all(isinstance(v, dict) for v in value)


def _count_results(result):
    """Number of records a tool returned, or None if it is a single object."""
    if _is_record_list(result):
        return len(result)

    if isinstance(result, dict):
        for value in result.values():
            if _is_record_list(value):
                return len(value)

    return None


def _render_tool_value(value):
    """Show tool output readably: tables for records, key/value otherwise."""
    if value and _is_record_list(value):
        # Web search results read better as links than as a table.
        if all("url" in v for v in value):
            for item in value:
                st.markdown(f"**[{item.get('title') or item['url']}]({item['url']})**")
                if item.get("content"):
                    st.caption(item["content"])
        else:
            st.dataframe(value, use_container_width=True, hide_index=True)

    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                st.markdown(f"**{key}:**")
                _render_tool_value(item)
            else:
                st.markdown(f"**{key}:** {item}")

    elif isinstance(value, list):
        for item in value:
            st.markdown(f"- {item}")

    else:
        st.text(str(value))


def render_context_used(chunks, tool_calls):
    """Developer view of the retrieval chunks and tool results of one answer."""
    if not (chunks or tool_calls):
        return

    st.caption("Context used")

    if chunks:
        with st.expander(f"📚 Regulation Retrieval · {len(chunks)} chunks"):
            for chunk in chunks:
                details = [
                    str(detail)
                    for detail in (
                        chunk.get("source", "Unknown source"),
                        chunk.get("state"),
                        f"page {chunk['page']}" if chunk.get("page") is not None else None,
                    )
                    if detail
                ]

                st.markdown(f"**Chunk {chunk['index']}** · {' · '.join(details)}")
                st.text(chunk.get("content", ""))
                st.divider()

    for tool_call in tool_calls:
        name = tool_call["name"]
        result = tool_call.get("result")
        count = _count_results(result)

        label = f"🔧 {TOOL_DISPLAY_NAMES.get(name, name)}"
        if count is not None:
            label += f" · {count} result{'' if count == 1 else 's'}"

        with st.expander(label):
            args = {k: v for k, v in tool_call.get("args", {}).items() if v is not None}
            if args:
                st.caption(
                    "Arguments: " + ", ".join(f"{k}={v}" for k, v in args.items())
                )

            _render_tool_value(result)

# ---------------------------------------------------------
# Page
# ---------------------------------------------------------

def render_page():

    if "messages" not in st.session_state:
        st.session_state.messages = []

    render_sidebar()

    st.title("🎣 Fishing Regulation Assistant")

    st.caption(
        "Ask questions about fishing regulations in Germany."
    )

    if not st.session_state.messages:

        with st.chat_message("assistant"):
            st.markdown(
                """
                Hi! I can help you understand fishing regulations
                in **Germany**.

                For example:

                - Can I fish for zander today?
                - What is the minimum size for pike?
                - Do I need a fishing license for coarse fishing?
                - Can I use live baitfish?
                """
            )

    # Existing Messages
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            if message.get("content"):
                st.markdown(message["content"])

            for image in message.get("images", []):
                st.image(
                    image["data"],
                    caption=image["name"],
                )

            if message["role"] == "assistant":
                render_sources(message.get("sources", []))
                render_context_used(
                    message.get("chunks", []),
                    message.get("tool_calls", []),
                )

    submission = st.chat_input(
        "Ask about fishing regulations...",
        accept_file=True,
        file_type=["png", "jpg", "jpeg", "webp"],
    )

    if not submission:
        return

    text = submission.text.strip()

    images = []

    for uploaded_file in submission.files:
        images.append(
            {
                "name": uploaded_file.name,
                "type": uploaded_file.type,
                "data": uploaded_file.getvalue(),
            }
        )

    if not (text or images):
        return

    # Keep history BEFORE adding the new user message so the prompt is not
    # sent twice to the model.
    previous_history = list(st.session_state.messages)

    user_message = {
        "role": "user",
        "content": text,
        "images": images,
    }
    st.session_state.messages.append(user_message)

    with st.chat_message("user"):
        if text:
            st.markdown(text)

        for image in images:
            st.image(
                image["data"],
                caption=image["name"],
            )

    # Text/RAG first version: images are displayed by the UI but are not sent
    # to the model yet.
    if not text:
        assistant_response = (
            "Image input is not connected to the model yet. "
            "Please add a text question for this first version."
        )
        sources = []
        chunks = []
        tool_calls = []
    else:
        try:
            with st.status("Thinking...") as status:

                def show_step(step):
                    status.update(label=f"{step}...")
                    status.write(step)

                result = generate_response(
                    prompt=text,
                    history=previous_history,
                    model_name=st.session_state.model,
                    temperature=st.session_state.temperature,
                    max_history_messages=st.session_state.max_history_messages,
                    on_status=show_step,
                )
                status.update(label="Done", state="complete")

            assistant_response = result["answer"]
            sources = result["sources"]
            chunks = result["chunks"]
            tool_calls = result["tool_calls"]

        except Exception as exc:
            assistant_response = f"Error while generating the answer: `{exc}`"
            sources = []
            chunks = []
            tool_calls = []

    assistant_message = {
        "role": "assistant",
        "content": assistant_response,
        "images": [],
        "sources": sources,
        "chunks": chunks,
        "tool_calls": tool_calls,
    }
    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.markdown(assistant_response)

        render_sources(sources)
        render_context_used(chunks, tool_calls)
