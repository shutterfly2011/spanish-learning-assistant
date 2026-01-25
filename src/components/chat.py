import re

import streamlit as st

from session_state import (
    add_message,
    get_messages,
    clear_messages,
    add_vocabulary_item,
)
from llm import OllamaClient, BedrockClient
from prompts.spanish_tutor import get_system_prompt, detect_input_type


def get_llm_client():
    """Get the appropriate LLM client based on settings."""
    if st.session_state.llm_provider == "ollama":
        return OllamaClient(
            base_url=st.session_state.ollama_base_url,
            model=st.session_state.ollama_model,
        )
    else:
        return BedrockClient(
            model_id=st.session_state.bedrock_model_id,
            region=st.session_state.bedrock_region,
        )


def extract_word_info(response: str, user_input: str) -> tuple[str, str, str]:
    """Extract word type and meaning from the response for vocabulary tracking.

    Returns: (word, word_type, meaning)
    """
    word = user_input.strip().split()[0]  # Get first word

    # Try to extract word type from response
    word_type = "unknown"
    type_patterns = [
        r"\*\*([Vv]erb)\*\*",
        r"\*\*([Nn]oun)\*\*",
        r"\*\*([Aa]djective)\*\*",
        r"\*\*([Aa]dverb)\*\*",
        r"\*\*([Pp]reposition)\*\*",
        r"- ([Vv]erb)",
        r"- ([Nn]oun)",
        r"- ([Aa]djective)",
        r"- ([Aa]dverb)",
        r"- ([Pp]reposition)",
    ]
    for pattern in type_patterns:
        match = re.search(pattern, response)
        if match:
            word_type = match.group(1).lower()
            break

    # Try to extract meaning
    meaning = ""
    meaning_patterns = [
        r"\*\*Meaning:\*\*\s*(.+?)(?:\n|$)",
        r"[Mm]eaning:\s*(.+?)(?:\n|$)",
        r"means\s+[\"'](.+?)[\"']",
    ]
    for pattern in meaning_patterns:
        match = re.search(pattern, response)
        if match:
            meaning = match.group(1).strip()
            break

    if not meaning:
        # Fallback: use first 50 chars of response
        meaning = response[:50] + "..." if len(response) > 50 else response

    return word, word_type, meaning


def render_chat_interface():
    """Render the main chat interface."""
    # Display current provider info
    provider = st.session_state.llm_provider
    if provider == "ollama":
        model_info = f"Ollama: {st.session_state.ollama_model}"
    else:
        model_info = f"Bedrock: {st.session_state.bedrock_model_id.split('.')[-1]}"

    st.caption(f"Using {model_info} | CEFR: {st.session_state.cefr_level}")

    # Chat messages container
    chat_container = st.container()

    with chat_container:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Enter a Spanish word or start a conversation..."):
        # Add user message
        add_message("user", prompt)

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            try:
                client = get_llm_client()
                system_prompt = get_system_prompt(st.session_state.cefr_level)
                messages = get_messages()

                # Stream the response
                response_placeholder = st.empty()
                full_response = ""

                with st.spinner("Thinking..."):
                    try:
                        for chunk in client.chat_stream(messages, system_prompt):
                            full_response += chunk
                            response_placeholder.markdown(full_response + "")
                    except Exception:
                        # Fallback to non-streaming if streaming fails
                        full_response = client.chat(messages, system_prompt)

                response_placeholder.markdown(full_response)

                # Add assistant message to history
                add_message("assistant", full_response)

                # Track vocabulary if it was a word lookup
                input_type = detect_input_type(prompt)
                if input_type == "word":
                    word, word_type, meaning = extract_word_info(full_response, prompt)
                    add_vocabulary_item(word, word_type, meaning)

            except ConnectionError as e:
                st.error(f"Connection error: {e}")
                st.info("Please check your LLM settings in the Settings menu.")
            except Exception as e:
                st.error(f"An error occurred: {e}")

    # Clear chat button
    if st.session_state.messages:
        if st.button("Clear Chat", key="clear_chat"):
            clear_messages()
            st.rerun()
