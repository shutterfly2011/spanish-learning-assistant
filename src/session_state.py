from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import streamlit as st

from config import load_config, AppConfig


@dataclass
class VocabularyItem:
    word: str
    word_type: str
    meaning: str
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "new"  # "new", "learning", "learned"


def init_session_state():
    """Initialize all session state variables."""
    if "initialized" not in st.session_state:
        config = load_config()

        # LLM settings
        st.session_state.llm_provider = config.llm_provider
        st.session_state.ollama_base_url = config.ollama.base_url
        st.session_state.ollama_model = config.ollama.model
        st.session_state.bedrock_model_id = config.bedrock.model_id
        st.session_state.bedrock_region = config.bedrock.region
        st.session_state.cefr_level = config.cefr_level

        # Chat history
        st.session_state.messages = []

        # Vocabulary tracking
        st.session_state.vocabulary = []

        # Settings modal state
        st.session_state.show_settings = False

        st.session_state.initialized = True


def get_llm_settings() -> dict:
    """Get current LLM settings from session state."""
    return {
        "provider": st.session_state.llm_provider,
        "ollama": {
            "base_url": st.session_state.ollama_base_url,
            "model": st.session_state.ollama_model,
        },
        "bedrock": {
            "model_id": st.session_state.bedrock_model_id,
            "region": st.session_state.bedrock_region,
        },
    }


def update_llm_settings(
    provider: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    ollama_model: Optional[str] = None,
    bedrock_model_id: Optional[str] = None,
    bedrock_region: Optional[str] = None,
    cefr_level: Optional[str] = None,
):
    """Update LLM settings in session state."""
    if provider is not None:
        st.session_state.llm_provider = provider
    if ollama_base_url is not None:
        st.session_state.ollama_base_url = ollama_base_url
    if ollama_model is not None:
        st.session_state.ollama_model = ollama_model
    if bedrock_model_id is not None:
        st.session_state.bedrock_model_id = bedrock_model_id
    if bedrock_region is not None:
        st.session_state.bedrock_region = bedrock_region
    if cefr_level is not None:
        st.session_state.cefr_level = cefr_level


def add_message(role: str, content: str):
    """Add a message to chat history."""
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })


def get_messages() -> list[dict]:
    """Get chat history (without timestamps for LLM)."""
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in st.session_state.messages
    ]


def clear_messages():
    """Clear chat history."""
    st.session_state.messages = []


def add_vocabulary_item(word: str, word_type: str, meaning: str):
    """Add a word to the vocabulary tracker."""
    # Check if word already exists
    for item in st.session_state.vocabulary:
        if item.word.lower() == word.lower():
            # Update existing item
            item.timestamp = datetime.now()
            return

    # Add new item
    st.session_state.vocabulary.append(
        VocabularyItem(word=word, word_type=word_type, meaning=meaning)
    )


def update_vocabulary_status(word: str, status: str):
    """Update the status of a vocabulary item."""
    for item in st.session_state.vocabulary:
        if item.word.lower() == word.lower():
            item.status = status
            return


def get_vocabulary() -> list[VocabularyItem]:
    """Get all vocabulary items, sorted by most recent first."""
    return sorted(
        st.session_state.vocabulary,
        key=lambda x: x.timestamp,
        reverse=True
    )


def clear_vocabulary():
    """Clear all vocabulary items."""
    st.session_state.vocabulary = []
