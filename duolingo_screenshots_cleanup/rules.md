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

**SpanishDict app:**
- A screenshot from the SpanishDict app (identifiable by tabs like "Dictionary / Examples / Pronunciation", or the SpanishDict logo/branding)
- The subject word is the `[headword/title]` element (the Spanish word being looked up)

**The presence of a `[standalone translation hint]` element is always a strong signal that this is a Spanish lesson.**

## 2. Identify the subject word or phrase

The subject word is the **main Spanish vocabulary item being taught**, not every Spanish word present.

### Priority rule: standalone translation hint
If a `[standalone translation hint]` element is present (a single English word or short phrase appearing in isolation, not part of a sentence):
1. Treat it as the English translation of the vocabulary item being taught
2. Find the Spanish word or phrase in the `[sentence]` elements whose meaning matches that English hint
3. That Spanish word/phrase is the subject word — **never pick a `[word-bank option]` as the subject word**

### Other screen types (when no standalone translation hint is present)
- Word-introduction screen → the word shown prominently (usually the largest text)
- Translation exercise → see rule below
- Matching or tap exercise → the word highlighted or being answered
- Reading comprehension with a translation balloon → the Spanish word the balloon points to

### Translation exercise rule (no standalone hint)
When the screen shows a full sentence to translate and there is no `[standalone translation hint]`:
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
