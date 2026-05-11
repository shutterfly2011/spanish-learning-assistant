import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field


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


if __name__ == "__main__":
    client = BuenoSpanish()
    entry = client.lookup("pantalla")

    print(f"=== {entry.word} ===")
    print(f"Smart definition : {entry.smart_definition}")
    print(f"Meanings:")
    for m in entry.meanings:
        print(f"  - {m.definition}")
        print(f"    ES: {m.example_es}")
        print(f"    EN: {m.example_en}")
    print(f"\nEtymology        : {entry.etymology}")
    print(f"Related Spanish  : {entry.related_spanish}")
    print(f"Related English  : {entry.related_english}")
    print(f"English cognates : {entry.english_cognates}")
