import re
import concurrent.futures

import streamlit as st

from session_state import (
    add_message,
    get_messages,
    clear_messages,
    add_vocabulary_item,
)
from llm import OllamaClient, BedrockClient
from prompts.spanish_tutor import get_system_prompt, detect_input_type, parse_json_response


def get_ollama_client():
    """Get Ollama client."""
    return OllamaClient(
        base_url=st.session_state.ollama_base_url,
        model=st.session_state.ollama_model,
    )


def get_bedrock_client():
    """Get Bedrock client."""
    return BedrockClient(
        model_id=st.session_state.bedrock_model_id,
        region=st.session_state.bedrock_region,
    )


def query_llm(client, messages, system_prompt):
    """Query an LLM client and return the response."""
    try:
        return client.chat(messages, system_prompt)
    except Exception as e:
        return f"Error: {e}"


def format_value(val, fallback="N/A"):
    """Format a value for display."""
    if val is None:
        return fallback
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else fallback
    return str(val)


def format_conjugations(conjugations: dict | None) -> str:
    """Format conjugations as markdown text."""
    if not conjugations:
        return "*N/A*"

    lines = []
    for tense, forms in conjugations.items():
        if forms:
            line = f"**{tense.title()}:** "
            parts = []
            for person, form in forms.items():
                if form:
                    parts.append(f"{person}: {form}")
            line += ", ".join(parts)
            lines.append(line)
    return "\n".join(lines) if lines else "*N/A*"


def format_adjective_forms(forms: dict | None) -> str:
    """Format adjective forms as markdown text."""
    if not forms:
        return "*N/A*"

    lines = [
        f"- Masc. Sing.: {forms.get('masculine_singular', '-')}",
        f"- Fem. Sing.: {forms.get('feminine_singular', '-')}",
        f"- Masc. Plur.: {forms.get('masculine_plural', '-')}",
        f"- Fem. Plur.: {forms.get('feminine_plural', '-')}",
    ]
    return "\n".join(lines)


def format_similar_words(similar_words: list | None) -> str:
    """Format similar words as markdown text."""
    if not similar_words:
        return "*None provided*"

    lines = []
    for item in similar_words:
        if isinstance(item, dict):
            word = item.get('word', '-')
            meaning = item.get('meaning', '-')
            note = item.get('note', '')
            line = f"- **{word}**: {meaning}"
            if note:
                line += f" *({note})*"
            lines.append(line)
    return "\n".join(lines) if lines else "*None provided*"


def format_examples(examples: list | None) -> str:
    """Format examples as markdown text."""
    if not examples:
        return "*None provided*"

    lines = []
    for i, ex in enumerate(examples, 1):
        if isinstance(ex, dict):
            spanish = ex.get('spanish', '')
            english = ex.get('english', '')
            lines.append(f"{i}. **{spanish}**")
            lines.append(f"   *{english}*")
        else:
            lines.append(f"{i}. {ex}")
    return "\n".join(lines) if lines else "*None provided*"


def render_comparison_row(label: str, ollama_val: str, bedrock_val: str):
    """Render a single comparison row with label and two columns."""
    st.markdown(f"**{label}**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(ollama_val)
    with col2:
        st.markdown(bedrock_val)
    st.divider()


def display_structured_comparison(ollama_data: dict | None, bedrock_data: dict | None):
    """Display structured JSON data from both providers side by side."""
    ollama_data = ollama_data or {}
    bedrock_data = bedrock_data or {}

    # Header
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Ollama")
    with col2:
        st.markdown("### Bedrock")
    st.divider()

    # Word & Type
    ollama_word = f"**{ollama_data.get('word', 'N/A')}** ({ollama_data.get('word_type', 'N/A')})"
    bedrock_word = f"**{bedrock_data.get('word', 'N/A')}** ({bedrock_data.get('word_type', 'N/A')})"
    render_comparison_row("Word & Type", ollama_word, bedrock_word)

    # Meaning
    render_comparison_row("Meaning",
                         format_value(ollama_data.get('meaning')),
                         format_value(bedrock_data.get('meaning')))

    # CEFR Level
    render_comparison_row("CEFR Level",
                         format_value(ollama_data.get('cefr_level')),
                         format_value(bedrock_data.get('cefr_level')))

    # Etymology
    render_comparison_row("Etymology",
                         format_value(ollama_data.get('etymology')),
                         format_value(bedrock_data.get('etymology')))

    # English Cognates
    render_comparison_row("English Cognates",
                         format_value(ollama_data.get('english_cognates')),
                         format_value(bedrock_data.get('english_cognates')))

    # Gender (for nouns)
    if ollama_data.get('gender') or bedrock_data.get('gender'):
        render_comparison_row("Gender",
                             format_value(ollama_data.get('gender')),
                             format_value(bedrock_data.get('gender')))

    # Plural (for nouns)
    if ollama_data.get('plural') or bedrock_data.get('plural'):
        render_comparison_row("Plural",
                             format_value(ollama_data.get('plural')),
                             format_value(bedrock_data.get('plural')))

    # Conjugations (for verbs)
    if ollama_data.get('conjugations') or bedrock_data.get('conjugations'):
        render_comparison_row("Conjugations",
                             format_conjugations(ollama_data.get('conjugations')),
                             format_conjugations(bedrock_data.get('conjugations')))

    # Adjective Forms
    if ollama_data.get('adjective_forms') or bedrock_data.get('adjective_forms'):
        render_comparison_row("Adjective Forms",
                             format_adjective_forms(ollama_data.get('adjective_forms')),
                             format_adjective_forms(bedrock_data.get('adjective_forms')))

    # Similar Words (English words with same etymology)
    render_comparison_row("Related English Words",
                         format_similar_words(ollama_data.get('similar_words')),
                         format_similar_words(bedrock_data.get('similar_words')))

    # Examples
    render_comparison_row("Examples",
                         format_examples(ollama_data.get('examples')),
                         format_examples(bedrock_data.get('examples')))


def render_single_structured(data: dict | None):
    """Render structured JSON data for a single provider."""
    if not data:
        st.markdown("*Failed to parse response*")
        return

    # Word & Type
    word = data.get('word', 'N/A')
    word_type = data.get('word_type', 'N/A')
    st.markdown(f"## {word} - {word_type.title()}")

    # Meaning
    st.markdown(f"**Meaning:** {data.get('meaning', 'N/A')}")

    # CEFR Level
    st.markdown(f"**CEFR Level:** {data.get('cefr_level', 'N/A')}")

    # Etymology
    st.markdown(f"**Etymology:** {data.get('etymology', 'N/A')}")

    # English Cognates
    cognates = data.get('english_cognates', [])
    if cognates:
        st.markdown(f"**English Cognates:** {', '.join(cognates) if isinstance(cognates, list) else cognates}")

    # Gender & Plural (for nouns)
    if data.get('gender'):
        st.markdown(f"**Gender:** {data.get('gender')}")
    if data.get('plural'):
        st.markdown(f"**Plural:** {data.get('plural')}")

    # Conjugations (for verbs)
    if data.get('conjugations'):
        st.markdown("**Conjugations:**")
        st.markdown(format_conjugations(data.get('conjugations')))

    # Adjective Forms
    if data.get('adjective_forms'):
        st.markdown("**Adjective Forms:**")
        st.markdown(format_adjective_forms(data.get('adjective_forms')))

    # Related English Words (words with same etymology)
    if data.get('similar_words'):
        st.markdown("**Related English Words:**")
        st.markdown(format_similar_words(data.get('similar_words')))

    # Example Sentences
    if data.get('examples'):
        st.markdown("**Example Sentences:**")
        st.markdown(format_examples(data.get('examples')))


def extract_word_info_from_json(data: dict | None, user_input: str) -> tuple[str, str, str]:
    """Extract word info from JSON response for vocabulary tracking."""
    if not data:
        return user_input.strip().split()[0], "unknown", ""

    word = data.get('word', user_input.strip().split()[0])
    word_type = data.get('word_type', 'unknown')
    meaning = data.get('meaning', '')

    return word, word_type, meaning


@st.dialog("Raw Model Output", width="large")
def show_raw_output_dialog(ollama_content: str | None, bedrock_content: str | None):
    """Dialog to show raw model output."""
    if ollama_content and bedrock_content:
        tab1, tab2 = st.tabs(["Ollama", "Bedrock"])
        with tab1:
            st.code(ollama_content, language="json")
        with tab2:
            st.code(bedrock_content, language="json")
    elif ollama_content:
        st.markdown("**Ollama Response:**")
        st.code(ollama_content, language="json")
    elif bedrock_content:
        st.markdown("**Bedrock Response:**")
        st.code(bedrock_content, language="json")


def render_inspect_button(message_idx: int, ollama_content: str | None, bedrock_content: str | None):
    """Render an inspect button that shows raw model output in a dialog."""
    if st.button("🔍 Inspect", key=f"inspect_{message_idx}", help="View raw model output"):
        show_raw_output_dialog(ollama_content, bedrock_content)


def render_chat_interface():
    """Render the main chat interface."""
    use_ollama = st.session_state.use_ollama
    use_bedrock = st.session_state.use_bedrock
    both_enabled = use_ollama and use_bedrock

    # Display current provider info
    providers = []
    if use_ollama:
        providers.append(f"Ollama: {st.session_state.ollama_model}")
    if use_bedrock:
        providers.append(f"Bedrock: {st.session_state.bedrock_model_id.split('.')[-1]}")

    provider_info = " | ".join(providers) if providers else "No provider selected"
    st.caption(f"Using {provider_info} | CEFR: {st.session_state.cefr_level}")

    # Chat messages container
    chat_container = st.container()

    with chat_container:
        for idx, message in enumerate(st.session_state.messages):
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(message["content"])
            else:
                ollama_content = message.get("ollama_content")
                bedrock_content = message.get("bedrock_content")
                is_structured = message.get("is_structured", False)

                if is_structured and ollama_content and bedrock_content:
                    # Parse JSON and display structured comparison
                    ollama_data = parse_json_response(ollama_content)
                    bedrock_data = parse_json_response(bedrock_content)
                    with st.container():
                        display_structured_comparison(ollama_data, bedrock_data)
                        render_inspect_button(idx, ollama_content, bedrock_content)
                elif is_structured and (ollama_content or bedrock_content):
                    content = ollama_content or bedrock_content
                    data = parse_json_response(content)
                    with st.chat_message("assistant"):
                        render_single_structured(data)
                    render_inspect_button(idx, ollama_content, bedrock_content)
                elif ollama_content and bedrock_content:
                    # Non-structured dual response
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### Ollama")
                        with st.chat_message("assistant"):
                            st.markdown(ollama_content)
                    with col2:
                        st.markdown("#### Bedrock")
                        with st.chat_message("assistant"):
                            st.markdown(bedrock_content)
                    render_inspect_button(idx, ollama_content, bedrock_content)
                elif ollama_content:
                    with st.chat_message("assistant"):
                        st.markdown(ollama_content)
                    render_inspect_button(idx, ollama_content, None)
                elif bedrock_content:
                    with st.chat_message("assistant"):
                        st.markdown(bedrock_content)
                    render_inspect_button(idx, None, bedrock_content)
                else:
                    with st.chat_message("assistant"):
                        st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Enter a Spanish word or start a conversation..."):
        if not use_ollama and not use_bedrock:
            st.error("Please select at least one LLM provider in Settings")
            return

        add_message("user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        # Determine if this is a word lookup (use structured JSON) or conversation
        input_type = detect_input_type(prompt)
        use_structured = input_type == "word"

        system_prompt = get_system_prompt(st.session_state.cefr_level, structured=use_structured)
        messages = get_messages()

        ollama_response = None
        bedrock_response = None

        if both_enabled:
            # Show loading indicators
            loading_placeholder = st.empty()
            with loading_placeholder.container():
                col1, col2 = st.columns(2)
                with col1:
                    st.info("Querying Ollama...")
                with col2:
                    st.info("Querying Bedrock...")

            # Query both in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                ollama_future = executor.submit(
                    query_llm, get_ollama_client(), messages, system_prompt
                )
                bedrock_future = executor.submit(
                    query_llm, get_bedrock_client(), messages, system_prompt
                )
                ollama_response = ollama_future.result()
                bedrock_response = bedrock_future.result()

            # Clear loading
            loading_placeholder.empty()

            if use_structured:
                # Parse and display structured comparison
                ollama_data = parse_json_response(ollama_response)
                bedrock_data = parse_json_response(bedrock_response)
                with st.container():
                    display_structured_comparison(ollama_data, bedrock_data)

                # Track vocabulary
                data_for_vocab = ollama_data or bedrock_data
                if data_for_vocab:
                    word, word_type, meaning = extract_word_info_from_json(data_for_vocab, prompt)
                    add_vocabulary_item(word, word_type, meaning)
            else:
                # Non-structured display
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Ollama")
                    with st.chat_message("assistant"):
                        st.markdown(ollama_response)
                with col2:
                    st.markdown("#### Bedrock")
                    with st.chat_message("assistant"):
                        st.markdown(bedrock_response)

            add_message(
                "assistant",
                content=ollama_response,
                ollama_content=ollama_response,
                bedrock_content=bedrock_response,
                is_structured=use_structured,
            )

        else:
            # Single provider mode
            with st.chat_message("assistant"):
                try:
                    if use_ollama:
                        client = get_ollama_client()
                    else:
                        client = get_bedrock_client()

                    response_placeholder = st.empty()
                    full_response = ""

                    with st.spinner("Thinking..."):
                        try:
                            for chunk in client.chat_stream(messages, system_prompt):
                                full_response += chunk
                                response_placeholder.markdown(full_response + "")
                        except Exception:
                            full_response = client.chat(messages, system_prompt)

                    if use_structured:
                        response_placeholder.empty()
                        data = parse_json_response(full_response)
                        render_single_structured(data)

                        # Track vocabulary
                        if data:
                            word, word_type, meaning = extract_word_info_from_json(data, prompt)
                            add_vocabulary_item(word, word_type, meaning)
                    else:
                        response_placeholder.markdown(full_response)

                    if use_ollama:
                        add_message("assistant", full_response, ollama_content=full_response, bedrock_content=None, is_structured=use_structured)
                    else:
                        add_message("assistant", full_response, ollama_content=None, bedrock_content=full_response, is_structured=use_structured)

                except ConnectionError as e:
                    st.error(f"Connection error: {e}")
                    st.info("Please check your LLM settings in the Settings menu.")
                    return
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    return

    # Clear chat button
    if st.session_state.messages:
        if st.button("Clear Chat", key="clear_chat"):
            clear_messages()
            st.rerun()
