"""Custom CSS for what the Streamlit theme (.streamlit/config.toml) cannot do.

Selectors only use Streamlit's data-testid attributes and the
``st-key-<key>`` classes that Streamlit adds to containers with a key.
"""

import streamlit as st


# Keep in sync with primaryColor in .streamlit/config.toml.
ACCENT_TINT = "rgba(46, 107, 94, 0.07)"

APP_CSS = f"""
<style>
/* Keep lines readable on wide screens; chat input gets the same width. */
[data-testid="stMainBlockContainer"],
[data-testid="stBottomBlockContainer"] {{
    max-width: 64rem;
}}

/* Chat: user messages get a light tinted bubble, answers stay plain. */
[data-testid="stChatMessage"] {{
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
}}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
    background-color: {ACCENT_TINT};
}}

/* Sources and developer context below an answer: visually secondary. */
[class*="st-key-answer_context"] [data-testid="stExpander"] summary {{
    font-size: 0.85rem;
    padding-top: 0.35rem;
    padding-bottom: 0.35rem;
}}

[class*="st-key-answer_context"] [data-testid="stExpander"] details {{
    border-color: transparent;
    background-color: {ACCENT_TINT};
}}

/* Catch cards: same image format for every card so the grid lines up. */
[class*="st-key-catch_card_"] [data-testid="stImage"] img {{
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: 0.5rem;
}}

/* Developer panel: small section labels instead of large headings. */
[data-testid="stSidebar"] h3 {{
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.65;
    padding-bottom: 0;
}}
</style>
"""


def apply_styles():
    st.html(APP_CSS)
