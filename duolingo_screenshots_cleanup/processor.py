import abc
import base64
import json
import re
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

_VISION_PROMPT = (
    "Analyse this Duolingo screenshot. For each visible text element, describe:\n"
    "1. The exact text\n"
    "2. Its UI role / position (e.g. isolated tap-target button, word-bank chip, "
    "sentence in a paragraph, standalone translation hint at the bottom, "
    "fill-in-the-blank prompt, header/title, progress indicator)\n\n"
    "Format each element as: [ROLE] text\n\n"
    "Example output:\n"
    "[sentence] Sin embargo, esto nos permitió tener una vista del ____.\n"
    "[standalone translation hint] however\n"
    "[word-bank option] sofá\n"
    "[word-bank option] cielo\n"
    "[button] CONTINUE\n\n"
    "Be precise about which words are isolated UI elements vs embedded in sentences."
)

_RULES_PROMPT = """\
You are analysing content extracted from a smartphone screenshot.

--- RULES ---
{rules}
--- END RULES ---

--- EXTRACTED CONTENT ---
{content}
--- END CONTENT ---

Apply the rules and respond with ONLY a valid JSON object (no other text):
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
    return backend.vision(image_path, _VISION_PROMPT)


# ---------------------------------------------------------------------------
# Step 3 — Rules-based processing
# ---------------------------------------------------------------------------

def process_with_rules(content: str, rules_text: str, backend: LLMBackend) -> Optional[dict]:
    prompt = _RULES_PROMPT.format(rules=rules_text, content=content)
    return _parse_json(backend.text(prompt))


# ---------------------------------------------------------------------------
# Step 3b — MCP word lookup
# ---------------------------------------------------------------------------

def lookup_word(word: str, mcp_server_url: str) -> dict:
    url = f"{mcp_server_url.rstrip('/')}/lookup/{word}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return {
        "meanings": data.get("meanings", []),
        "etymology": data.get("etymology") or "",
        "english_cognates": data.get("english_cognates", []),
    }


# ---------------------------------------------------------------------------
# Step 4 — Flashcard formatting
# ---------------------------------------------------------------------------

def _trim(text: str, max_chars: int = 160) -> str:
    if not text:
        return ""
    end = text.find(". ")
    sentence = text[: end + 1] if end != -1 else text
    return sentence[:max_chars].rstrip(" .,")


def _definition_line(word_type: str, meanings: list) -> str:
    if not meanings:
        return ""
    raw = meanings[0].get("definition", "")
    raw = re.sub(r"^[\dA-Za-z]+\.\s*", "", raw)
    raw = raw.split(";")[0].split("//")[0].strip()
    if word_type == "verb" and raw and not raw.lower().startswith("to "):
        raw = f"to {raw}"
    return raw


def build_flashcard(word: str, word_type: str, mcp_data: dict) -> str:
    word_type = (word_type or "").lower()
    lines: list[str] = []

    meanings = mcp_data.get("meanings", [])
    definition = _definition_line(word_type, meanings)
    type_label = word_type if word_type not in ("", "null") else ""
    if definition and type_label:
        lines.append(f"{definition} ({type_label})")
    elif definition:
        lines.append(definition)
    elif type_label:
        lines.append(f"({type_label})")

    etymology = mcp_data.get("etymology", "")
    if etymology and etymology != "No etymology information available":
        lines.append(f"Etym: {_trim(etymology)}")

    cognates = mcp_data.get("english_cognates", [])
    if cognates:
        lines.append(f"Cognates: {', '.join(cognates[:5])}")

    body = "\n".join(lines) if lines else "(no data retrieved)"
    return f"---\n{word}\n?\n{body}\n"


# ---------------------------------------------------------------------------
# Step 4 (cont.) — Append to markdown
# ---------------------------------------------------------------------------

def append_to_markdown(flashcard: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(flashcard + "\n")
