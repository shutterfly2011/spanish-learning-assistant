import re
import concurrent.futures
from typing import Optional

import streamlit as st

from session_state import (
    add_message,
    get_messages,
    clear_messages,
    add_vocabulary_item,
)
from llm import OllamaClient, BedrockClient
from prompts.spanish_tutor import get_system_prompt, detect_input_type


# Section definitions for parsing responses
SECTIONS = [
    ("header", r"^###?\s*\[?(\w+)\]?\s*[-–—]"),  # ### [Word] - Type
    ("meaning", r"\*\*(?:Meaning|Definici[oó]n|Definition)s?:?\*\*"),
    ("cefr", r"\*\*(?:CEFR|Level|Nivel).*?:?\*\*"),
    ("etymology", r"\*\*(?:Etymology|Etimolog[ií]a|Origin|Origen).*?:?\*\*"),
    ("cognates", r"\*\*(?:English\s+)?(?:Cognates?|Cognados?).*?:?\*\*"),
    ("conjugations", r"\*\*(?:Common\s+)?(?:Conjugations?|Conjugaci[oó]n|Conjugaciones).*?:?\*\*"),
    ("gender", r"\*\*(?:Gender|G[eé]nero).*?:?\*\*"),
    ("plural", r"\*\*(?:Plural).*?:?\*\*"),
    ("forms", r"\*\*(?:Forms?|Formas?).*?:?\*\*"),
    ("similar", r"\*\*(?:Similar[- ]?Looking\s+Words?|Palabras?\s+[Ss]imilar).*?:?\*\*"),
    ("examples", r"\*\*(?:Example\s+Sentences?|Ejemplos?|Oraciones?).*?:?\*\*"),
]

SECTION_LABELS = {
    "header": "Word & Type",
    "meaning": "Meaning",
    "cefr": "CEFR Level",
    "etymology": "Etymology",
    "cognates": "English Cognates",
    "conjugations": "Conjugations",
    "gender": "Gender",
    "plural": "Plural",
    "forms": "Forms",
    "similar": "Similar-Looking Words",
    "examples": "Example Sentences",
    "other": "Additional Information",
}


def parse_response_sections(response: str) -> dict[str, str]:
    """Parse an LLM response into sections.

    Returns a dict mapping section names to their content.
    """
    sections = {}
    lines = response.split('\n')
    current_section = "header"
    current_content = []

    for line in lines:
        # Check if this line starts a new section
        new_section = None
        for section_name, pattern in SECTIONS:
            if re.search(pattern, line, re.IGNORECASE):
                new_section = section_name
                break

        if new_section and new_section != current_section:
            # Save current section
            if current_content:
                content = '\n'.join(current_content).strip()
                if content:
                    sections[current_section] = content
            current_section = new_section
            current_content = [line]
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        content = '\n'.join(current_content).strip()
        if content:
            sections[current_section] = content

    # If parsing didn't find clear sections, try alternative parsing
    if len(sections) <= 1:
        sections = parse_response_by_bold_headers(response)

    return sections


def parse_response_by_bold_headers(response: str) -> dict[str, str]:
    """Alternative parsing using bold headers (**Header:**)."""
    sections = {}

    # Split by bold headers
    pattern = r'\*\*([^*]+):\*\*'
    parts = re.split(pattern, response)

    if len(parts) <= 1:
        # No bold headers found, return whole response as "other"
        return {"other": response}

    # First part before any header
    if parts[0].strip():
        sections["header"] = parts[0].strip()

    # Process header-content pairs
    for i in range(1, len(parts) - 1, 2):
        header = parts[i].strip().lower()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""

        # Map header to section name
        section_name = map_header_to_section(header)

        # Combine header with content for display
        full_content = f"**{parts[i]}:** {content}"

        if section_name in sections:
            sections[section_name] += "\n\n" + full_content
        else:
            sections[section_name] = full_content

    return sections


def map_header_to_section(header: str) -> str:
    """Map a header string to a standard section name."""
    header = header.lower()

    mapping = {
        "meaning": "meaning",
        "definición": "meaning",
        "definition": "meaning",
        "cefr": "cefr",
        "level": "cefr",
        "nivel": "cefr",
        "etymology": "etymology",
        "etimología": "etymology",
        "origin": "etymology",
        "cognate": "cognates",
        "cognates": "cognates",
        "english cognate": "cognates",
        "conjugation": "conjugations",
        "conjugations": "conjugations",
        "common conjugations": "conjugations",
        "gender": "gender",
        "género": "gender",
        "plural": "plural",
        "form": "forms",
        "forms": "forms",
        "similar": "similar",
        "similar-looking": "similar",
        "similar looking": "similar",
        "similar words": "similar",
        "example": "examples",
        "examples": "examples",
        "example sentences": "examples",
    }

    for key, section in mapping.items():
        if key in header:
            return section

    return "other"


def display_sections_side_by_side(ollama_sections: dict, bedrock_sections: dict):
    """Display parsed sections from both providers side by side."""
    # Get all unique section names, maintaining order
    all_sections = []
    section_order = ["header", "meaning", "cefr", "etymology", "cognates",
                     "conjugations", "gender", "plural", "forms", "similar",
                     "examples", "other"]

    for section in section_order:
        if section in ollama_sections or section in bedrock_sections:
            all_sections.append(section)

    # Add any sections not in our predefined order
    for section in list(ollama_sections.keys()) + list(bedrock_sections.keys()):
        if section not in all_sections:
            all_sections.append(section)

    # Display header row
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ollama")
    with col2:
        st.markdown("#### Bedrock")

    st.divider()

    # Display each section side by side
    for section in all_sections:
        ollama_content = ollama_sections.get(section, "")
        bedrock_content = bedrock_sections.get(section, "")

        # Skip if both are empty
        if not ollama_content and not bedrock_content:
            continue

        label = SECTION_LABELS.get(section, section.title())
        st.markdown(f"**{label}**")

        col1, col2 = st.columns(2)
        with col1:
            if ollama_content:
                st.markdown(ollama_content)
            else:
                st.markdown("*Not provided*")
        with col2:
            if bedrock_content:
                st.markdown(bedrock_content)
            else:
                st.markdown("*Not provided*")

        st.divider()


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


def extract_word_info(response: str, user_input: str) -> tuple[str, str, str]:
    """Extract word type and meaning from the response for vocabulary tracking."""
    word = user_input.strip().split()[0]

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
        meaning = response[:50] + "..." if len(response) > 50 else response

    return word, word_type, meaning


def query_llm(client, messages, system_prompt):
    """Query an LLM client and return the response."""
    try:
        return client.chat(messages, system_prompt)
    except Exception as e:
        return f"Error: {e}"


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

                if ollama_content and bedrock_content:
                    # Parse and display sections side by side
                    with st.container():
                        ollama_sections = parse_response_sections(ollama_content)
                        bedrock_sections = parse_response_sections(bedrock_content)
                        display_sections_side_by_side(ollama_sections, bedrock_sections)
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

        system_prompt = get_system_prompt(st.session_state.cefr_level)
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

            # Clear loading and display results
            loading_placeholder.empty()

            # Parse and display sections
            with st.container():
                ollama_sections = parse_response_sections(ollama_response)
                bedrock_sections = parse_response_sections(bedrock_response)
                display_sections_side_by_side(ollama_sections, bedrock_sections)

            add_message(
                "assistant",
                content=ollama_response,
                ollama_content=ollama_response,
                bedrock_content=bedrock_response,
            )

            response_for_vocab = ollama_response if not ollama_response.startswith("Error") else bedrock_response

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

                    response_placeholder.markdown(full_response)

                    if use_ollama:
                        add_message("assistant", full_response, ollama_content=full_response, bedrock_content=None)
                    else:
                        add_message("assistant", full_response, ollama_content=None, bedrock_content=full_response)

                    response_for_vocab = full_response

                except ConnectionError as e:
                    st.error(f"Connection error: {e}")
                    st.info("Please check your LLM settings in the Settings menu.")
                    return
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    return

        # Track vocabulary
        input_type = detect_input_type(prompt)
        if input_type == "word" and response_for_vocab and not response_for_vocab.startswith("Error"):
            word, word_type, meaning = extract_word_info(response_for_vocab, prompt)
            add_vocabulary_item(word, word_type, meaning)

    # Clear chat button
    if st.session_state.messages:
        if st.button("Clear Chat", key="clear_chat"):
            clear_messages()
            st.rerun()
