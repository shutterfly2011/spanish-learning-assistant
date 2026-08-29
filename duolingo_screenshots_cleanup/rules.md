# Duolingo Screenshot Processing Rules

## 1. Is this a Spanish lesson?

A screenshot qualifies as a Spanish lesson if it shows **any** of the following:

**Duolingo UI patterns:**
- A Spanish word/phrase introduction screen (large text showing a new word with translation)
- A translation exercise from Spanish to English or vice versa
- A word-matching or tap-the-word exercise
- A fill-in-the-blank exercise with a Spanish word being practiced
- A dictionary lookup with the Spanish word on top and the definition below
- A reading comprehension screen showing Spanish paragraphs — **this always qualifies**, even if there is no obvious exercise structure, as long as Spanish sentences are present
- A block of spanish text, with a `[translation hint]` element (an English word/phrase callout, whether standalone or a tooltip) giving the translation hint to the subject spanish word/phrase

**SpanishDict app:**
- A screenshot from the SpanishDict app (identifiable by tabs like "Dictionary / Examples / Pronunciation", or the SpanishDict logo/branding)
- The subject word is the `[headword/title]` element (the Spanish word being looked up)

**The presence of a `[translation hint]` element is always a strong signal that this is a Spanish lesson.** This includes tooltips, popovers, or any other UI-role label the OCR step used for a short English callout that translates a single Spanish word or phrase — treat any such element as equivalent to `[translation hint]` even if it's labeled differently (e.g. "tool tip").

## 2. Identify the subject word or phrase

The subject word is the **main Spanish vocabulary item being taught**, not every Spanish word present.

### Priority rule: translation hint
If a `[translation hint]` element is present, or any element that is functionally the same thing — a single English word or short phrase appearing in isolation or as a tooltip, not part of a sentence — regardless of what label the OCR step gave it, work through these steps in order:
1. Treat it as the English translation of the vocabulary item being taught
2. **First, build a list**: write out every individual Spanish word that appears anywhere in the extracted content (every sentence, dialogue, narration, or fill-in-the-blank element — not only ones literally tagged `[sentence]`). This is your only allowed candidate pool.
3. **Then, and only then, pick from that list**: go through the list from step 2 and choose the one word whose meaning matches the English hint. Do this by comparison against the list — do not translate the English hint into Spanish independently of the list, since that produces a plausible-sounding but wrong word (e.g. hint "it indicates" translated cold gives `indica`/`indicar`, but if the list from step 2 contains `señala` and not `indica`, the correct answer is `señala` — a different verb that happens to share the meaning).
4. **Verify before answering**: confirm your chosen word is literally present, character-for-character (ignoring conjugation), in the list you built in step 2. If it is not, you have invented a word — go back to step 2 and re-check the list instead of guessing.
5. That Spanish word/phrase is the subject word — **never pick a `[word-bank option]` as the subject word**
6. Word frequency/repetition elsewhere on screen is irrelevant to this rule — the hint's semantic match always wins, even if other words appear more often

### Other screen types (when no translation hint is present)
- Word-introduction screen → the word shown prominently (usually the largest text)
- Translation exercise → see rule below
- Matching or tap exercise → the word highlighted or being answered
- Reading comprehension with a translation balloon → this is a `[translation hint]` per the priority rule above; do not treat it as a separate case

### Translation exercise rule (no translation hint)
When the screen shows a full sentence to translate and there is no `[translation hint]`:
1. **Never return the full sentence** — the subject word is always a single word or short fixed phrase (2–3 words max)
2. Pick the **single most specific or advanced vocabulary word** in the sentence — the word a learner is most likely still acquiring (e.g. `admirar`, `talento` rather than `el`, `ver`, `su`)
3. Prefer nouns, verbs, and adjectives over pronouns, articles, prepositions, and conjunctions
4. If two words are equally specific, prefer the one that is less common in everyday speech

### Base form
Always extract the **dictionary/base form**: infinitive for verbs (e.g. `luchar` not `luchaban`), singular for nouns (e.g. `herramienta` not `herramientas`), base adjective form.

If multiple candidate words are visible, pick the one most central to the lesson objective.

## 3 Lookup the word or phrase
- once subject word or phrase is identified, set 'needs_lookup: true'

## 4. word type dependent output
besides meanings, eptymology, follow the following guidelines for extra information to include:
| Type        | Signals in screenshot                         |
|-------------|-----------------------------------------------|
| noun      | Include gender                                  |
| verb      | If it's irregular verb, include conjugations    |
| adjective | Include gender                                  |
| phrase    | Include an example usage                        |
