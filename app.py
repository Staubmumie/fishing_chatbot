import streamlit as st

from src.ui import catch_collection_ui, chatbot_ui, styles


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Fishing Assistant",
    page_icon="🎣",
    layout="wide",
)

styles.apply_styles()


# ---------------------------------------------------------
# Navigation
# ---------------------------------------------------------

page = st.navigation(
    [
        st.Page(
            chatbot_ui.render_page,
            title="Chatbot",
            icon=":material/forum:",
            url_path="chatbot",
            default=True,
        ),
        st.Page(
            catch_collection_ui.render_page,
            title="Catch Collection",
            icon=":material/set_meal:",
            url_path="catches",
        ),
    ],
    position="top",
)

page.run()
