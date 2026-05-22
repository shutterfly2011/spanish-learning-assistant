import base64
import json
import re
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
from PIL.ExifTags import TAGS

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


# ---------------------------------------------------------------------------
# Step 1 — Screenshot detection
# ---------------------------------------------------------------------------

def is_screenshot(image_path: Path) -> bool:
    """
    Return True if the image is a smartphone screenshot rather than a camera photo.

    Heuristics (in order):
    - .png  → almost always a screenshot on iPhone
    - .heic → always a camera photo on iPhone
    - JPEG  → check EXIF for camera-specific tags (Make, Model, FocalLength, LensModel);
              their absence means no camera was involved → screenshot
    """
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        return True
    if suffix == ".heic":
        return False
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        named = {TAGS.get(k, k): v for k, v in exif.items()}
        camera_fields = {"Make", "Model", "FocalLength", "LensModel"}
        return not bool(camera_fields.intersection(named.keys()))
    except Exception:
        return True  # can't read EXIF → assume screenshot


# ---------------------------------------------------------------------------
# Step 2 — Vision extraction
# ---------------------------------------------------------------------------

def extract_content(image_path: Path, ollama_base_url: str, vision_model: str) -> str:
    """Call an Ollama vision model to transcribe all text and describe the UI."""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": vision_model,
        "messages": [{
            "role": "user",
            "content": (
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
            ),
            "images": [image_b64],
        }],
        "stream": False,
    }
    url = f"{ollama_base_url.rstrip('/')}/api/chat"
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Step 3 — Rules-based processing
# ---------------------------------------------------------------------------

def process_with_rules(
    content: str,
    rules_text: str,
    ollama_base_url: str,
    text_model: str,
) -> Optional[dict]:
    """
    Send extracted content + rules.md to Ollama text model.
    Returns a dict: {is_spanish_lesson, word, word_type, needs_lookup}.
    """
    prompt = f"""You are analysing content extracted from a smartphone screenshot.

--- RULES ---
{rules_text}
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

    payload = {
        "model": text_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
    }
    url = f"{ollama_base_url.rstrip('/')}/api/chat"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    text = r.json().get("message", {}).get("content", "")

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
# Step 3b — MCP word lookup
# ---------------------------------------------------------------------------

def lookup_word(word: str, mcp_server_url: str) -> dict:
    """
    Fetch all data for a Spanish word via the MCP server's REST endpoint:
      GET /lookup/{word}
    Returns a dict with keys: meanings, etymology, english_cognates.
    """
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
    """Return the first sentence of text, capped at max_chars."""
    if not text:
        return ""
    end = text.find(". ")
    sentence = text[: end + 1] if end != -1 else text
    return sentence[:max_chars].rstrip(" .,")


def _definition_line(word_type: str, meanings: list) -> str:
    """
    Build a single concise definition line tailored to word type.

    Nouns   : strip leading articles / sense numbers
    Verbs   : prepend 'to ' if missing
    Adj/Adv : use as-is
    Phrase  : use as-is
    """
    if not meanings:
        return ""

    raw = meanings[0].get("definition", "")
    # Remove leading sense labels like "1. " or "A. "
    raw = re.sub(r"^[\dA-Za-z]+\.\s*", "", raw)
    # Take only the first sense (before ';' or second comma-clause)
    raw = raw.split(";")[0].split("//")[0].strip()

    if word_type == "verb" and raw and not raw.lower().startswith("to "):
        raw = f"to {raw}"

    return raw


def build_flashcard(word: str, word_type: str, mcp_data: dict) -> str:
    """
    Assemble a flashcard in the format:

        ---
        {word}
        ?
        {definition} ({word_type})
        Etym: {first sentence of etymology}
        Cognates: {english cognates}
    """
    word_type = (word_type or "").lower()
    lines: list[str] = []

    # — Definition line —
    meanings = mcp_data.get("meanings", [])
    definition = _definition_line(word_type, meanings)
    type_label = word_type if word_type not in ("", "null") else ""
    if definition and type_label:
        lines.append(f"{definition} ({type_label})")
    elif definition:
        lines.append(definition)
    elif type_label:
        lines.append(f"({type_label})")

    # — Etymology line —
    etymology = mcp_data.get("etymology", "")
    if etymology and etymology != "No etymology information available":
        lines.append(f"Etym: {_trim(etymology)}")

    # — English cognates line —
    cognates = mcp_data.get("english_cognates", [])
    if cognates:
        lines.append(f"Cognates: {', '.join(cognates[:5])}")

    body = "\n".join(lines) if lines else "(no data retrieved)"
    return f"---\n{word}\n?\n{body}\n"


# ---------------------------------------------------------------------------
# Step 4 (cont.) — Append to markdown
# ---------------------------------------------------------------------------

def append_to_markdown(flashcard: str, output_path: Path) -> None:
    """Append a flashcard block to the output markdown file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(flashcard + "\n")
