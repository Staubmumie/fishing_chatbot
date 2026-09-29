import streamlit as st

from src import catch_collection_ui, chatbot_ui


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Fishing Regulation Assistant",
    page_icon="🎣",
    layout="wide",
)


# ---------------------------------------------------------
# Navigation
# ---------------------------------------------------------

page = st.radio(
    "Navigation",
    ["🎣 Chatbot", "🐟 Catch Collection"],
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()


if page == "🎣 Chatbot":
    chatbot_ui.render_page()

elif page == "🐟 Catch Collection":
    catch_collection_ui.render_page()
