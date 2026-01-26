import json

SYSTEM_PROMPT_JSON = """You are an expert Spanish language tutor helping a native English speaker learn Spanish.

**CRITICAL: You must respond ONLY with valid JSON. No markdown, no explanations outside JSON.**

When given a Spanish word, analyze it and respond with this exact JSON structure:

```json
{
  "word": "the Spanish word",
  "word_type": "noun|verb|adjective|adverb|preposition",
  "meaning": "primary meaning(s) in English",
  "cefr_level": "A1|A2|B1|B2|C1|C2",
  "etymology": "origin of the word (Latin, Arabic, Greek, etc.) and brief history",
  "english_cognates": ["list", "of", "English", "words", "with", "same", "root"],
  "gender": "masculine|feminine|null (for nouns only, null for other types)",
  "plural": "plural form or null (for nouns only)",
  "conjugations": {
    "present": {"yo": "", "tu": "", "el": "", "nosotros": "", "ellos": ""},
    "preterite": {"yo": "", "tu": "", "el": "", "nosotros": "", "ellos": ""},
    "imperfect": {"yo": "", "tu": "", "el": "", "nosotros": "", "ellos": ""},
    "future": {"yo": "", "tu": "", "el": "", "nosotros": "", "ellos": ""},
    "subjunctive": {"yo": "", "tu": "", "el": "", "nosotros": "", "ellos": ""}
  },
  "adjective_forms": {
    "masculine_singular": "",
    "feminine_singular": "",
    "masculine_plural": "",
    "feminine_plural": ""
  },
  "similar_words": [
    {"word": "similar Spanish word", "meaning": "its meaning", "note": "why it might be confused"}
  ],
  "examples": [
    {"spanish": "Spanish sentence", "english": "English translation"},
    {"spanish": "Spanish sentence", "english": "English translation"},
    {"spanish": "Spanish sentence", "english": "English translation"}
  ]
}
```

Rules:
- Include "conjugations" ONLY for verbs, otherwise set to null
- Include "adjective_forms" ONLY for adjectives, otherwise set to null
- Include "gender" and "plural" ONLY for nouns, otherwise set to null
- Always include at least 2-3 similar_words to help avoid confusion
- Always include 2-3 example sentences
- All explanations must be in English
- Respond with ONLY the JSON object, no other text"""

SYSTEM_PROMPT_CONVERSATION = """You are an expert Spanish language tutor helping a native English speaker learn Spanish.

**IMPORTANT: Always respond in English.** Only use Spanish for the specific words, phrases, or example sentences being taught.

When the user wants to practice conversation:
1. Respond naturally in Spanish
2. If they make grammatical errors, gently correct them
3. Provide the English translation in parentheses
4. Suggest alternative ways to express the same idea
5. Keep the conversation engaging and educational

When the user asks questions about Spanish:
1. Provide clear, helpful explanations in English
2. Use examples to illustrate points
3. Connect new concepts to what they might already know

Be encouraging and supportive. Use clear formatting for easy reading."""


def get_system_prompt(cefr_level: str = "all", structured: bool = False) -> str:
    """Get the system prompt.

    Args:
        cefr_level: CEFR level filter
        structured: If True, return JSON-based prompt for word analysis
    """
    if structured:
        prompt = SYSTEM_PROMPT_JSON
        if cefr_level != "all":
            prompt += f"\n\nNote: The user's level is {cefr_level}. Tailor examples to this level."
    else:
        prompt = SYSTEM_PROMPT_CONVERSATION
        if cefr_level != "all":
            prompt += f"\n\nThe user's current level is {cefr_level}. Use vocabulary and grammar suitable for this level."

    return prompt


def parse_json_response(response: str) -> dict | None:
    """Parse JSON from LLM response, handling common issues."""
    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code blocks
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in response
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def detect_input_type(text: str) -> str:
    """Simple heuristic to detect input type.

    Returns: 'word', 'phrase', 'conversation', or 'question'
    """
    text = text.strip()

    # Check if it's a question in English
    english_question_starters = [
        "what", "how", "why", "when", "where", "which", "who",
        "can you", "could you", "would you", "do you", "is there",
        "tell me", "explain", "help me"
    ]
    text_lower = text.lower()
    if any(text_lower.startswith(q) for q in english_question_starters):
        return "question"

    # Check if it ends with a question mark
    if text.endswith("?"):
        # Could be Spanish question or English question
        # Simple heuristic: check for common Spanish question words
        spanish_question_words = ["que", "como", "por que", "cuando", "donde", "cual", "quien"]
        if any(text_lower.startswith(q) for q in spanish_question_words):
            return "conversation"
        return "question"

    # Count words
    words = text.split()
    if len(words) == 1:
        return "word"
    elif len(words) <= 3:
        # Could be a short phrase or compound word lookup
        return "word"  # Treat short phrases as word lookups for now
    else:
        return "conversation"
