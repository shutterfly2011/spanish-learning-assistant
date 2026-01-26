import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from config import load_config, AppConfig


# Path to persist user settings
SETTINGS_FILE = Path(__file__).parent.parent / "user_settings.json"


@dataclass
class VocabularyItem:
    word: str
    word_type: str
    meaning: str
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "new"  # "new", "learning", "learned"


def load_saved_settings() -> dict:
    """Load saved settings from file."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_settings_to_file():
    """Save current settings to file."""
    settings = {
        "use_ollama": st.session_state.use_ollama,
        "use_bedrock": st.session_state.use_bedrock,
        "ollama_base_url": st.session_state.ollama_base_url,
        "ollama_model": st.session_state.ollama_model,
        "bedrock_model_id": st.session_state.bedrock_model_id,
        "bedrock_region": st.session_state.bedrock_region,
        "cefr_level": st.session_state.cefr_level,
    }
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except IOError:
        pass  # Silently fail if we can't write


def init_session_state():
    """Initialize all session state variables."""
    if "initialized" not in st.session_state:
        config = load_config()
        saved = load_saved_settings()

        # LLM settings - load from saved settings first, then fall back to config
        st.session_state.use_ollama = saved.get("use_ollama", config.llm_provider == "ollama")
        st.session_state.use_bedrock = saved.get("use_bedrock", config.llm_provider == "bedrock")
        st.session_state.ollama_base_url = saved.get("ollama_base_url", config.ollama.base_url)
        st.session_state.ollama_model = saved.get("ollama_model", config.ollama.model)
        st.session_state.bedrock_model_id = saved.get("bedrock_model_id", config.bedrock.model_id)
        st.session_state.bedrock_region = saved.get("bedrock_region", config.bedrock.region)
        st.session_state.cefr_level = saved.get("cefr_level", config.cefr_level)

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
        "use_ollama": st.session_state.use_ollama,
        "use_bedrock": st.session_state.use_bedrock,
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
    use_ollama: Optional[bool] = None,
    use_bedrock: Optional[bool] = None,
    ollama_base_url: Optional[str] = None,
    ollama_model: Optional[str] = None,
    bedrock_model_id: Optional[str] = None,
    bedrock_region: Optional[str] = None,
    cefr_level: Optional[str] = None,
    persist: bool = True,
):
    """Update LLM settings in session state and optionally persist to file."""
    if use_ollama is not None:
        st.session_state.use_ollama = use_ollama
    if use_bedrock is not None:
        st.session_state.use_bedrock = use_bedrock
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

    # Persist settings to file
    if persist:
        save_settings_to_file()


def add_message(role: str, content: str, ollama_content: str = None, bedrock_content: str = None, is_structured: bool = False):
    """Add a message to chat history.

    For user messages, only content is used.
    For assistant messages, ollama_content and bedrock_content store provider-specific responses.
    is_structured indicates if the response is structured JSON for word analysis.
    """
    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if role == "assistant":
        msg["ollama_content"] = ollama_content
        msg["bedrock_content"] = bedrock_content
        msg["is_structured"] = is_structured
    st.session_state.messages.append(msg)


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
