import streamlit as st

from config import has_aws_credentials
from session_state import update_llm_settings
from llm import OllamaClient


def render_settings_button():
    """Render the settings gear icon button in the header."""
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("Spanish Learning Assistant")
    with col2:
        if st.button("Settings", key="settings_btn", help="Configure LLM settings"):
            st.session_state.show_settings = True
            st.rerun()


@st.dialog("Settings")
def render_settings_dialog():
    """Render the settings dialog."""
    st.subheader("LLM Configuration")

    # Provider selection
    provider = st.selectbox(
        "LLM Provider",
        options=["ollama", "bedrock"],
        index=0 if st.session_state.llm_provider == "ollama" else 1,
        key="settings_provider",
    )

    st.divider()

    # Ollama settings
    st.subheader("Ollama Settings")
    ollama_base_url = st.text_input(
        "Ollama Base URL",
        value=st.session_state.ollama_base_url,
        key="settings_ollama_url",
        help="URL of your Ollama server (e.g., http://192.168.1.100:11434)",
    )
    ollama_model = st.text_input(
        "Ollama Model",
        value=st.session_state.ollama_model,
        key="settings_ollama_model",
        help="Model name to use (e.g., llama3, mistral, openai-oss-20b)",
    )

    # Test Ollama connection
    if st.button("Test Ollama Connection", key="test_ollama"):
        with st.spinner("Testing connection..."):
            client = OllamaClient(base_url=ollama_base_url, model=ollama_model)
            if client.is_available():
                models = client.list_models()
                st.success(f"Connected! Available models: {', '.join(models[:5])}")
            else:
                st.error("Could not connect to Ollama server")

    st.divider()

    # Bedrock settings
    st.subheader("Bedrock Settings")

    if not has_aws_credentials():
        st.warning(
            "AWS credentials not found. Set AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY environment variables to use Bedrock."
        )

    bedrock_model_id = st.text_input(
        "Bedrock Model ID",
        value=st.session_state.bedrock_model_id,
        key="settings_bedrock_model",
        help="Claude model ID (e.g., anthropic.claude-3-sonnet-20240229-v1:0)",
    )
    bedrock_region = st.selectbox(
        "AWS Region",
        options=["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"],
        index=["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"].index(
            st.session_state.bedrock_region
        ) if st.session_state.bedrock_region in ["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"] else 0,
        key="settings_bedrock_region",
    )

    st.divider()

    # CEFR Level
    st.subheader("Learning Settings")
    cefr_level = st.selectbox(
        "CEFR Level",
        options=["all", "A1", "A2", "B1", "B2", "C1", "C2"],
        index=["all", "A1", "A2", "B1", "B2", "C1", "C2"].index(
            st.session_state.cefr_level
        ) if st.session_state.cefr_level in ["all", "A1", "A2", "B1", "B2", "C1", "C2"] else 0,
        key="settings_cefr",
        help="Filter content by your Spanish proficiency level",
    )

    st.divider()

    # Save button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save", type="primary", use_container_width=True):
            update_llm_settings(
                provider=provider,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
                bedrock_model_id=bedrock_model_id,
                bedrock_region=bedrock_region,
                cefr_level=cefr_level,
            )
            st.session_state.show_settings = False
            st.success("Settings saved!")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_settings = False
            st.rerun()
