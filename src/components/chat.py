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
    """Format a value for display, escaping HTML."""
    if val is None:
        return fallback
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else fallback
    return str(val).replace("<", "&lt;").replace(">", "&gt;")


def build_comparison_table(rows: list[tuple[str, str, str]]) -> str:
    """Build an HTML table for side-by-side comparison.

    Args:
        rows: List of (label, ollama_value, bedrock_value) tuples
    """
    html = """
    <style>
    .comparison-table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
    }
    .comparison-table th, .comparison-table td {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: left;
        vertical-align: top;
    }
    .comparison-table th {
        background-color: #f5f5f5;
        font-weight: bold;
    }
    .comparison-table th.provider {
        width: 40%;
    }
    .comparison-table th.label {
        width: 20%;
    }
    .comparison-table tr:nth-child(even) {
        background-color: #fafafa;
    }
    </style>
    <table class="comparison-table">
    <thead>
        <tr>
            <th class="label">Field</th>
            <th class="provider">Ollama</th>
            <th class="provider">Bedrock</th>
        </tr>
    </thead>
    <tbody>
    """

    for label, ollama_val, bedrock_val in rows:
        html += f"""
        <tr>
            <td><strong>{label}</strong></td>
            <td>{ollama_val}</td>
            <td>{bedrock_val}</td>
        </tr>
        """

    html += "</tbody></table>"
    return html


def format_conjugations_html(conjugations: dict | None) -> str:
    """Format conjugations as HTML mini-table."""
    if not conjugations:
        return "<em>N/A</em>"

    html = "<table style='font-size: 0.9em; border-collapse: collapse;'>"
    html += "<tr style='background: #f0f0f0;'><th style='padding: 3px 6px;'>Tense</th><th>yo</th><th>tú</th><th>él</th><th>nosotros</th><th>ellos</th></tr>"

    for tense, forms in conjugations.items():
        if forms:
            html += f"<tr><td style='padding: 3px 6px;'><em>{tense}</em></td>"
            html += f"<td style='padding: 3px 6px;'>{forms.get('yo', '-')}</td>"
            html += f"<td style='padding: 3px 6px;'>{forms.get('tu', '-')}</td>"
            html += f"<td style='padding: 3px 6px;'>{forms.get('el', '-')}</td>"
            html += f"<td style='padding: 3px 6px;'>{forms.get('nosotros', '-')}</td>"
            html += f"<td style='padding: 3px 6px;'>{forms.get('ellos', '-')}</td></tr>"

    html += "</table>"
    return html


def format_adjective_forms_html(forms: dict | None) -> str:
    """Format adjective forms as HTML."""
    if not forms:
        return "<em>N/A</em>"

    return f"""
    <ul style='margin: 0; padding-left: 20px;'>
        <li>Masc. Sing.: {forms.get('masculine_singular', '-')}</li>
        <li>Fem. Sing.: {forms.get('feminine_singular', '-')}</li>
        <li>Masc. Plur.: {forms.get('masculine_plural', '-')}</li>
        <li>Fem. Plur.: {forms.get('feminine_plural', '-')}</li>
    </ul>
    """


def format_similar_words_html(similar_words: list | None) -> str:
    """Format similar words as HTML."""
    if not similar_words:
        return "<em>None provided</em>"

    html = "<ul style='margin: 0; padding-left: 20px;'>"
    for item in similar_words:
        if isinstance(item, dict):
            word = item.get('word', '-')
            meaning = item.get('meaning', '-')
            note = item.get('note', '')
            html += f"<li><strong>{word}</strong>: {meaning}"
            if note:
                html += f" <em>({note})</em>"
            html += "</li>"
    html += "</ul>"
    return html


def format_examples_html(examples: list | None) -> str:
    """Format examples as HTML."""
    if not examples:
        return "<em>None provided</em>"

    html = "<ol style='margin: 0; padding-left: 20px;'>"
    for ex in examples:
        if isinstance(ex, dict):
            spanish = ex.get('spanish', '')
            english = ex.get('english', '')
            html += f"<li><strong>{spanish}</strong><br/><em>{english}</em></li>"
        else:
            html += f"<li>{ex}</li>"
    html += "</ol>"
    return html


def display_structured_comparison(ollama_data: dict | None, bedrock_data: dict | None):
    """Display structured JSON data from both providers in an aligned HTML table."""
    ollama_data = ollama_data or {}
    bedrock_data = bedrock_data or {}

    # Build rows for the comparison table
    rows = []

    # Word & Type
    ollama_word = f"<strong style='font-size: 1.2em;'>{ollama_data.get('word', 'N/A')}</strong> ({ollama_data.get('word_type', 'N/A')})"
    bedrock_word = f"<strong style='font-size: 1.2em;'>{bedrock_data.get('word', 'N/A')}</strong> ({bedrock_data.get('word_type', 'N/A')})"
    rows.append(("Word & Type", ollama_word, bedrock_word))

    # Meaning
    rows.append(("Meaning", format_value(ollama_data.get('meaning')), format_value(bedrock_data.get('meaning'))))

    # CEFR Level
    rows.append(("CEFR Level", format_value(ollama_data.get('cefr_level')), format_value(bedrock_data.get('cefr_level'))))

    # Etymology
    rows.append(("Etymology", format_value(ollama_data.get('etymology')), format_value(bedrock_data.get('etymology'))))

    # English Cognates
    rows.append(("English Cognates", format_value(ollama_data.get('english_cognates')), format_value(bedrock_data.get('english_cognates'))))

    # Gender (for nouns)
    if ollama_data.get('gender') or bedrock_data.get('gender'):
        rows.append(("Gender", format_value(ollama_data.get('gender')), format_value(bedrock_data.get('gender'))))

    # Plural (for nouns)
    if ollama_data.get('plural') or bedrock_data.get('plural'):
        rows.append(("Plural", format_value(ollama_data.get('plural')), format_value(bedrock_data.get('plural'))))

    # Conjugations (for verbs)
    if ollama_data.get('conjugations') or bedrock_data.get('conjugations'):
        rows.append(("Conjugations",
                    format_conjugations_html(ollama_data.get('conjugations')),
                    format_conjugations_html(bedrock_data.get('conjugations'))))

    # Adjective Forms
    if ollama_data.get('adjective_forms') or bedrock_data.get('adjective_forms'):
        rows.append(("Adjective Forms",
                    format_adjective_forms_html(ollama_data.get('adjective_forms')),
                    format_adjective_forms_html(bedrock_data.get('adjective_forms'))))

    # Similar Words
    rows.append(("Similar Words",
                format_similar_words_html(ollama_data.get('similar_words')),
                format_similar_words_html(bedrock_data.get('similar_words'))))

    # Examples
    rows.append(("Examples",
                format_examples_html(ollama_data.get('examples')),
                format_examples_html(bedrock_data.get('examples'))))

    # Render the HTML table
    html_table = build_comparison_table(rows)
    st.markdown(html_table, unsafe_allow_html=True)


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
        render_conjugation_table(data.get('conjugations'), "")

    # Adjective Forms
    if data.get('adjective_forms'):
        forms = data.get('adjective_forms')
        st.markdown("**Adjective Forms:**")
        st.markdown(f"- Masculine Singular: {forms.get('masculine_singular', '-')}")
        st.markdown(f"- Feminine Singular: {forms.get('feminine_singular', '-')}")
        st.markdown(f"- Masculine Plural: {forms.get('masculine_plural', '-')}")
        st.markdown(f"- Feminine Plural: {forms.get('feminine_plural', '-')}")

    # Similar Words
    if data.get('similar_words'):
        st.markdown("**Similar-Looking Words:**")
        render_similar_words_table(data.get('similar_words'))

    # Example Sentences
    if data.get('examples'):
        st.markdown("**Example Sentences:**")
        render_examples(data.get('examples'))


def extract_word_info_from_json(data: dict | None, user_input: str) -> tuple[str, str, str]:
    """Extract word info from JSON response for vocabulary tracking."""
    if not data:
        return user_input.strip().split()[0], "unknown", ""

    word = data.get('word', user_input.strip().split()[0])
    word_type = data.get('word_type', 'unknown')
    meaning = data.get('meaning', '')

    return word, word_type, meaning


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
        for message in st.session_state.messages:
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
                elif is_structured and (ollama_content or bedrock_content):
                    content = ollama_content or bedrock_content
                    data = parse_json_response(content)
                    with st.chat_message("assistant"):
                        render_single_structured(data)
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
                elif ollama_content:
                    with st.chat_message("assistant"):
                        st.markdown(ollama_content)
                elif bedrock_content:
                    with st.chat_message("assistant"):
                        st.markdown(bedrock_content)
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
