import abc
import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from buenospanish import BuenoSpanish

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

# Small delay before each LLM call — back-to-back requests with no gap have
# been observed to trigger failures against the backend.
_LLM_CALL_PAUSE_SECONDS = 0.15
PROMPTS  = [(
    "Analyse this Duolingo screenshot. For each visible text element, describe:\n"
    "1. The exact text\n"
    "2. Its UI role / position (e.g. isolated tap-target button, word-bank chip, "
    "sentence in a paragraph, translation hint — a short English word/phrase callout "
    "that translates a Spanish word, whether it appears standalone at the bottom of "
    "the screen or as a small tooltip pointing into a sentence, "
    "fill-in-the-blank prompt, header/title, progress indicator)\n\n"
    "Format each element as: [ROLE] text\n\n"
    "Use the single tag [translation hint] for ANY English word/phrase callout that "
    "translates a Spanish word — do not use other names like 'tool tip' for this.\n\n"
    "Example output:\n"
    "[sentence] Sin embargo, esto nos permitió tener una vista del ____.\n"
    "[translation hint] however\n"
    "[word-bank option] sofá\n"
    "[word-bank option] cielo\n"
    "[button] CONTINUE\n\n"
    "Be precise about which words are isolated UI elements vs embedded in sentences."
),
(
    "Analyze the image. "
    "extract all visible text elements and describe their location in the image"
)
]

_VISION_PROMPT = PROMPTS[0]

_RULES_PROMPT = """\
You are analysing content extracted from a smartphone screenshot.

--- RULES ---
{rules}
--- END RULES ---

--- EXTRACTED CONTENT ---
{content}
--- END CONTENT ---

Apply the rules. First, in 2-3 short sentences, reason step by step (briefly) about which
word matches the translation hint (if one is present), quoting the exact candidate words
from the extracted content. Then, on a new line, respond with ONLY a valid JSON object:
{{
  "is_spanish_lesson": <true|false>,
  "word": "<base-form Spanish word or phrase, or null>",
  "word_type": "<noun|verb|adjective|adverb|phrase|null>",
  "needs_lookup": <true|false>
}}"""


def _image_mime(image_path: Path) -> str:
    suffix = image_path.suffix.lower().lstrip(".")
    return "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"


def _parse_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# LLM backend abstraction
# ---------------------------------------------------------------------------

class LLMBackend(abc.ABC):
    @abc.abstractmethod
    def vision(self, image_path: Path, prompt: str) -> str: ...

    @abc.abstractmethod
    def text(self, prompt: str) -> str: ...


class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str, vision_model: str, text_model: str, timeout: int = 300):
        self._url = base_url.rstrip("/") + "/api/chat"
        self._vision_model = vision_model
        self._text_model = text_model
        self._timeout = timeout

    def vision(self, image_path: Path, prompt: str) -> str:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": self._vision_model,
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
            "stream": False,
        }
        r = requests.post(self._url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")

    def text(self, prompt: str) -> str:
        payload = {
            "model": self._text_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
        }
        r = requests.post(self._url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


class OpenAIBackend(LLMBackend):
    def __init__(self, api_key: str, vision_model: str, text_model: str):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._vision_model = vision_model
        self._text_model = text_model

    def vision(self, image_path: Path, prompt: str) -> str:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        mime = _image_mime(image_path)
        response = self._client.chat.completions.create(
            model=self._vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            ]}],
        )
        return response.choices[0].message.content or ""

    def text(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._text_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str, vision_model: str, text_model: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        self._vision_model = vision_model
        self._text_model = text_model

    def vision(self, image_path: Path, prompt: str) -> str:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        mime = _image_mime(image_path)
        model = self._genai.GenerativeModel(self._vision_model)
        response = model.generate_content([prompt, {"mime_type": mime, "data": image_bytes}])
        return response.text or ""

    def text(self, prompt: str) -> str:
        model = self._genai.GenerativeModel(self._text_model)
        return model.generate_content(prompt).text or ""


class BedrockBackend(LLMBackend):
    def __init__(self, region: str, vision_model: str, text_model: str, api_key: str = ""):
        import boto3, os
        if api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._vision_model = vision_model
        self._text_model = text_model

    def _invoke(self, model_id: str, messages: list) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": messages,
        })
        response = self._client.invoke_model(modelId=model_id, body=body)
        return json.loads(response["body"].read())["content"][0]["text"]

    _MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Bedrock hard limit on raw image bytes

    def vision(self, image_path: Path, prompt: str) -> str:
        image_bytes = self._resize_if_needed(image_path)
        image_b64 = base64.b64encode(image_bytes).decode()
        mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        messages = [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_b64}},
            {"type": "text", "text": prompt},
        ]}]
        return self._invoke(self._vision_model, messages)

    def _resize_if_needed(self, image_path: Path) -> bytes:
        with open(image_path, "rb") as f:
            raw = f.read()
        if len(raw) <= self._MAX_IMAGE_BYTES:
            return raw
        import io
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        quality = 85
        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            data = buf.getvalue()
            if len(data) <= self._MAX_IMAGE_BYTES or quality <= 30:
                return data
            quality -= 15

    def text(self, prompt: str) -> str:
        return self._invoke(self._text_model, [{"role": "user", "content": prompt}])


def build_backend(config: dict) -> LLMBackend:
    provider = config.get("provider", "ollama").lower()

    if provider == "openai":
        return OpenAIBackend(
            api_key=config["openai_api_key"],
            vision_model=config.get("vision_model", "gpt-4o"),
            text_model=config.get("text_model", "gpt-4o"),
        )
    if provider == "gemini":
        return GeminiBackend(
            api_key=config["gemini_api_key"],
            vision_model=config.get("vision_model", "gemini-1.5-pro"),
            text_model=config.get("text_model", "gemini-1.5-flash"),
        )
    if provider == "bedrock":
        return BedrockBackend(
            region=config.get("aws_region", "us-east-1"),
            vision_model=config.get("vision_model", "us.anthropic.claude-sonnet-4-6"),
            text_model=config.get("text_model", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            api_key=config.get("bedrock_api_key", ""),
        )
    # Default: ollama
    return OllamaBackend(
        base_url=config.get("ollama_base_url", "http://localhost:11434"),
        vision_model=config.get("vision_model", "llava:latest"),
        text_model=config.get("text_model", "llama3"),
    )


# ---------------------------------------------------------------------------
# Step 1 — Screenshot detection
# ---------------------------------------------------------------------------

def is_screenshot(image_path: Path) -> bool:
    return image_path.suffix.lower() == ".png"


# ---------------------------------------------------------------------------
# Step 2 — Vision extraction
# ---------------------------------------------------------------------------

def extract_content(image_path: Path, backend: LLMBackend) -> str:
    time.sleep(_LLM_CALL_PAUSE_SECONDS)
    return backend.vision(image_path, _VISION_PROMPT)


# ---------------------------------------------------------------------------
# Step 3 — Rules-based processing
# ---------------------------------------------------------------------------

def process_with_rules(content: str, rules_text: str, backend: LLMBackend) -> Optional[dict]:
    time.sleep(_LLM_CALL_PAUSE_SECONDS)
    prompt = _RULES_PROMPT.format(rules=rules_text, content=content)
    return _parse_json(backend.text(prompt))


# ---------------------------------------------------------------------------
# Step 3b — BuenoSpanish lookup
# ---------------------------------------------------------------------------

_BUENO_SPANISH = BuenoSpanish(timeout=15)


def lookup_word(word: str) -> dict:
    entry = _BUENO_SPANISH.lookup(word)
    return {
        "meanings": [
            {
                "definition": meaning.definition,
                "example_es": meaning.example_es,
                "example_en": meaning.example_en,
            }
            for meaning in entry.meanings
        ],
        "etymology": entry.etymology or "",
        "english_cognates": entry.english_cognates,
    }


# ---------------------------------------------------------------------------
# Step 4 — Flashcard formatting
# ---------------------------------------------------------------------------

_ETYM_INTRO_RE = re.compile(
    r"^The Spanish \w+ '[^']*'\s*\(meaning '[^']*'\)\s*"
    r"(?:traces back to|has an interesting (?:etymology|history|origin)(?: that)?)\s*",
    re.IGNORECASE,
)


def _clean_etymology(text: str) -> str:
    """Strip the boilerplate intro ("The Spanish word 'X' (meaning 'Y')
    traces back to / has an interesting etymology that...") so the summary
    goes straight to the substance."""
    if not text:
        return ""
    text = _ETYM_INTRO_RE.sub("", text).strip()
    return text[:1].upper() + text[1:] if text else text


def _trim(text: str, max_chars: int = 220) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for sentence in sentences:
        candidate = f"{out} {sentence}".strip() if out else sentence
        if out and len(candidate) > max_chars:
            break
        out = candidate
        if len(out) >= max_chars:
            break
    return out.rstrip(" .,")


def _definition_line(word_type: str, meanings: list) -> str:
    if not meanings:
        return ""
    raw = meanings[0].get("definition", "")
    raw = re.sub(r"^[\dA-Za-z]+\.\s*", "", raw)
    raw = raw.split(";")[0].split("//")[0].strip()
    if word_type == "verb" and raw and not raw.lower().startswith("to "):
        raw = f"to {raw}"
    return raw


def build_flashcard(word: str, word_type: str, lookup_data: dict, source_filename: Optional[str] = None) -> str:
    word_type = (word_type or "").lower()
    lines: list[str] = []

    meanings = lookup_data.get("meanings", [])
    definition = _definition_line(word_type, meanings)
    type_label = word_type if word_type not in ("", "null") else ""
    if definition and type_label:
        lines.append(f"{definition} ({type_label})")
    elif definition:
        lines.append(definition)
    elif type_label:
        lines.append(f"({type_label})")

    etymology = lookup_data.get("etymology", "")
    if etymology and etymology != "No etymology information available":
        lines.append(f"Etym: {_trim(_clean_etymology(etymology))}")

    cognates = lookup_data.get("english_cognates", [])
    if cognates:
        lines.append(f"Cognates: {', '.join(cognates[:5])}")

    if source_filename:
        lines.append(f"Source: {source_filename}")

    body = "\n".join(lines) if lines else "(no data retrieved)"
    return f"---\n{word}\n?\n{body}\n"


# ---------------------------------------------------------------------------
# Step 4 (cont.) — Append to markdown
# ---------------------------------------------------------------------------

def append_to_markdown(flashcard: str, output_path: Path) -> bool:
    card_lines = flashcard.splitlines()
    word = card_lines[1].strip() if len(card_lines) > 1 else ""
    if output_path.exists() and word:
        existing_lines = output_path.read_text(encoding="utf-8").splitlines()
        existing_words = {
            existing_lines[index + 1].strip()
            for index, line in enumerate(existing_lines)
            if line.strip() == "---" and index + 1 < len(existing_lines)
        }
        if word in existing_words:
            return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(flashcard + "\n")
    return True
