import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from dataclasses import asdict

from fastmcp.server.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

_SUPERSCRIPTS = re.compile(r"\s*\d+\s*")

BASE_URL = "https://buenospanish.com/dictionary"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


@dataclass
class Meaning:
    definition: str
    example_es: str
    example_en: str


@dataclass
class WordEntry:
    word: str
    smart_definition: str | None = None
    meanings: list[Meaning] = field(default_factory=list)
    etymology: str | None = None
    related_spanish: str | None = None
    related_english: str | None = None

    @property
    def english_cognates(self) -> list[str]:
        if not self.related_english:
            return []
        return [w for w in re.findall(r"'([a-z]+)'", self.related_english) if w != self.word]


class BuenoSpanish:
    def __init__(self, timeout: int = 10):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._timeout = timeout

    def lookup(self, word: str) -> WordEntry:
        entry = WordEntry(word=word)
        self._fill_definition(entry)
        self._fill_etymology(entry)
        return entry

    # ------------------------------------------------------------------
    def _get(self, url: str) -> BeautifulSoup:
        r = self._session.get(url, timeout=self._timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _fill_definition(self, entry: WordEntry) -> None:
        soup = self._get(f"{BASE_URL}/{entry.word}")

        for div in soup.find_all("div"):
            text = div.get_text(" ", strip=True)
            if f"{entry.word.capitalize()} means" in text and len(text) < 400:
                entry.smart_definition = _SUPERSCRIPTS.sub(" ", text).strip()
                break

        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)
            if "//" not in text:
                continue
            es_part, en_part = text.split("//", 1)
            # es_part: "sense label. definition sentence. Spanish example sentence."
            chunks = es_part.rsplit(".", 1)
            definition = chunks[0].strip() if len(chunks) == 2 else es_part.strip()
            example_es = chunks[1].strip() if len(chunks) == 2 else ""
            entry.meanings.append(Meaning(
                definition=definition,
                example_es=example_es,
                example_en=en_part.strip(),
            ))

    def _fill_etymology(self, entry: WordEntry) -> None:
        soup = self._get(f"{BASE_URL}/{entry.word}/etymology")

        for div in soup.find_all("div"):
            text = div.get_text(" ", strip=True)
            if entry.etymology is None and text.startswith("Etymology") and len(text) > 100:
                # Trim at the first related-words section to avoid bleed
                body = text.removeprefix("Etymology").strip()
                cutoff = body.find("Related Spanish Words")
                entry.etymology = body[:cutoff].strip() if cutoff != -1 else body
            elif entry.related_spanish is None and text.startswith("Related Spanish Words"):
                entry.related_spanish = text.removeprefix("Related Spanish Words").strip()
            elif entry.related_english is None and text.startswith("Related English Words"):
                entry.related_english = text.removeprefix("Related English Words").strip()


# MCP Server setup
app = FastMCP("Spanish Dictionary MCP Server")

client = BuenoSpanish()


@app.tool()
def lookup_word(word: str) -> str:
    """
    Look up a Spanish word and return detailed information including meanings,
    etymology, and related words.

    Args:
        word: The Spanish word to look up

    Returns:
        A formatted string containing the word information
    """
    try:
        entry = client.lookup(word)

        result = f"=== {entry.word} ===\n"

        if entry.smart_definition:
            result += f"Smart definition: {entry.smart_definition}\n\n"

        if entry.meanings:
            result += "Meanings:\n"
            for i, m in enumerate(entry.meanings, 1):
                result += f"  {i}. {m.definition}\n"
                if m.example_es:
                    result += f"     ES: {m.example_es}\n"
                result += f"     EN: {m.example_en}\n"
            result += "\n"

        if entry.etymology:
            result += f"Etymology: {entry.etymology}\n\n"

        if entry.related_spanish:
            result += f"Related Spanish: {entry.related_spanish}\n\n"

        if entry.related_english:
            result += f"Related English: {entry.related_english}\n\n"

        if entry.english_cognates:
            result += f"English cognates: {', '.join(entry.english_cognates)}\n"

        return result

    except Exception as e:
        return f"Error looking up word '{word}': {str(e)}"


@app.tool()
def get_word_meanings(word: str) -> list[dict]:
    """
    Get the meanings of a Spanish word as structured data.

    Args:
        word: The Spanish word to look up

    Returns:
        A list of dictionaries containing definition, Spanish example, and English example
    """
    try:
        entry = client.lookup(word)
        return [
            {
                "definition": m.definition,
                "example_es": m.example_es,
                "example_en": m.example_en
            }
            for m in entry.meanings
        ]
    except Exception as e:
        return [{"error": f"Failed to lookup word '{word}': {str(e)}"}]


@app.tool()
def get_etymology(word: str) -> str:
    """
    Get the etymology of a Spanish word.

    Args:
        word: The Spanish word to look up

    Returns:
        The etymology information as a string
    """
    try:
        entry = client.lookup(word)
        return entry.etymology or "No etymology information available"
    except Exception as e:
        return f"Error getting etymology for '{word}': {str(e)}"


@app.tool()
def get_related_words(word: str) -> dict:
    """
    Get related Spanish and English words for a given Spanish word.

    Args:
        word: The Spanish word to look up

    Returns:
        A dictionary with related Spanish words, related English words, and English cognates
    """
    try:
        entry = client.lookup(word)
        return {
            "related_spanish": entry.related_spanish,
            "related_english": entry.related_english,
            "english_cognates": entry.english_cognates
        }
    except Exception as e:
        return {"error": f"Failed to get related words for '{word}': {str(e)}"}


# ---------------------------------------------------------------------------
# Custom REST endpoints
# These sit alongside the MCP protocol endpoint (/mcp) and are used by
# non-MCP clients such as the duolingo_screenshots_cleanup processor.
# ---------------------------------------------------------------------------

@app.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.custom_route("/lookup/{word}", methods=["GET"])
async def lookup_rest(request: Request) -> JSONResponse:
    """Return all data for a word as a single JSON object."""
    word = request.path_params["word"]
    try:
        entry = client.lookup(word)
        data = asdict(entry)  # converts Meaning dataclasses too
        data["english_cognates"] = entry.english_cognates  # computed property
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    # host="0.0.0.0" is required so the container is reachable from the LAN.
    # The default (127.0.0.1) only accepts loopback connections inside the container.
    app.run(transport="streamable-http", host="0.0.0.0")