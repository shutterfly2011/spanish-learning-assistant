import streamlit as st

from session_state import init_session_state
from components.settings import render_settings_button, render_settings_dialog
from components.vocabulary import render_vocabulary_sidebar
from components.chat import render_chat_interface

# Page configuration
st.set_page_config(
    page_title="Spanish Learning Assistant",
    page_icon="ES",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
    }
    .stChatInput {
        padding-bottom: 1rem;
    }
    div[data-testid="stSidebarContent"] {
        padding-top: 1rem;
    }
    .main .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Initialize session state
    init_session_state()

    # Render settings button in header
    render_settings_button()

    # Show settings dialog if requested
    if st.session_state.show_settings:
        render_settings_dialog()

    # Render vocabulary sidebar
    render_vocabulary_sidebar()

    # Render main chat interface
    render_chat_interface()


if __name__ == "__main__":
    main()
